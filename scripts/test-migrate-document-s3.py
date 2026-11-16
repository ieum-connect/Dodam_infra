"""Migration safety checks; no AWS requests."""
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from botocore.exceptions import ClientError

spec = importlib.util.spec_from_file_location("migration", Path(__file__).with_name("migrate-document-s3.py"))
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

class Store:
    def __init__(self):
        self.objects = {"unrelated": b"keep"}
        self.writes = 0
    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}
    def put_object(self, **kwargs):
        assert kwargs["ServerSideEncryption"] == "AES256"
        self.objects[kwargs["Key"]] = kwargs["Body"]
        self.writes += 1

class MigrationTest(unittest.TestCase):
    def test_copy_is_verified_repeatable_and_preserves_both_sides(self):
        store = Store()
        with tempfile.TemporaryDirectory() as directory, patch.object(migration.boto3, "client", return_value=store):
            root = Path(directory)
            (root/"a.pdf").write_bytes(b"original")
            migration.migrate(root,"private","ap-southeast-2")
            migration.migrate(root,"private","ap-southeast-2")
            self.assertEqual(store.writes,1)
            self.assertEqual(store.objects["a.pdf"],b"original")
            self.assertEqual(store.objects["unrelated"],b"keep")
            self.assertEqual((root/"a.pdf").read_bytes(),b"original")

    def test_verify_only_never_uploads_missing_or_changed_objects(self):
        store=Store()
        with tempfile.TemporaryDirectory() as directory, patch.object(migration.boto3,"client",return_value=store):
            root=Path(directory); (root/"a.pdf").write_bytes(b"original")
            with self.assertRaises(RuntimeError):
                migration.migrate(root,"private","ap-southeast-2",True)
            self.assertEqual(store.writes,0)

    def test_readback_mismatch_stops_migration(self):
        store=Store()
        def corrupt(**kwargs):
            store.objects[kwargs["Key"]]=b"wrong"
        store.put_object=corrupt
        with tempfile.TemporaryDirectory() as directory, patch.object(migration.boto3,"client",return_value=store):
            root=Path(directory); (root/"a.pdf").write_bytes(b"original")
            with self.assertRaises(RuntimeError):
                migration.migrate(root,"private","ap-southeast-2")
            self.assertEqual((root/"a.pdf").read_bytes(),b"original")

if __name__ == "__main__": unittest.main()
