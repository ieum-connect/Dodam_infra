"""Offline tests: production config generation must never replace live secrets."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('production', Path(__file__).with_name('init-production.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ProductionConfigTests(unittest.TestCase):
    def test_sydney_config_and_preserve_existing_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / '.env.production'
            module.create_config('dodam.test', 'release-abc123', target)
            before = target.read_bytes()
            values = dict(line.split('=', 1) for line in before.decode().splitlines() if '=' in line and not line.startswith('#'))
            self.assertEqual(values['AWS_REGION'], 'ap-southeast-2')
            self.assertEqual(values['NGINX_MODE'], 'bootstrap')
            self.assertEqual(values['PUBLIC_ORIGIN'], 'https://dodam.test')
            keys = [values[key] for key in ('POSTGRES_PASSWORD', 'JWT_SECRET', 'AI_INTERNAL_TOKEN')]
            self.assertEqual(len(set(keys)), 3)
            for value in keys:
                self.assertRegex(value, r'^[0-9a-f]{64}$')
            self.assertEqual(values['OPENAI_API_KEY'], '')
            with self.assertRaises(FileExistsError):
                module.create_config('dodam.test', 'another-release', target)
            self.assertEqual(target.read_bytes(), before)

    def test_bad_domain_and_tag_do_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / '.env.production'
            for domain, tag in [('https://dodam.test', 'ok'), ('example.com', 'ok'), ('dodam.test', '../bad'), ('bad\nvalue', 'ok')]:
                with self.subTest(domain=domain, tag=tag):
                    with self.assertRaises(ValueError):
                        module.create_config(domain, tag, target)
                    self.assertFalse(target.exists())

if __name__ == '__main__':
    unittest.main()
