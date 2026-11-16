"""Copy the uploads volume without deleting originals; verify every object's SHA-256.

Run with backend and AI stopped for the final copy, then set DOCUMENT_STORAGE_PROVIDER=s3.
Use an S3-enabled AI image with /source mounted read-only and EC2 role credentials.
"""
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def migrate(root: Path, bucket: str, region: str, verify_only: bool = False):
    s3 = boto3.client("s3", region_name=region)
    count = size = copied = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Unexpected symlink in uploads; inspect before migrating")
        if not path.is_file():
            continue
        key = path.relative_to(root).as_posix()
        data = path.read_bytes()
        digest = hashlib.sha256(data).digest()
        remote_digest = None
        try:
            with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
                remote_digest = hashlib.sha256(body.read()).digest()
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                raise
        if remote_digest != digest:
            if verify_only:
                raise RuntimeError("S3 verification failed; local data remains intact")
            s3.put_object(Bucket=bucket, Key=key, Body=data,
                ContentType=mimetypes.guess_type(key)[0] or "application/octet-stream",
                ServerSideEncryption="AES256")
            with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
                if hashlib.sha256(body.read()).digest() != digest:
                    raise RuntimeError("S3 read-back checksum mismatch")
            copied += 1
        count += 1
        size += len(data)
    print(json.dumps({"verified_files": count, "verified_bytes": size, "copied_files": copied}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/source"))
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="ap-southeast-2")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not args.root.is_dir():
        raise SystemExit("Source directory not mounted")
    migrate(args.root, args.bucket, args.region, args.verify_only)
