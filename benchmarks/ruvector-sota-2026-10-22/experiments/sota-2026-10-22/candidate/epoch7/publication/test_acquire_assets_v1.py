"""Tiny asset fixtures only; no actual HTTP request, model or addon execution."""
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch7_asset_restore', HERE / 'acquire_assets_v1.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dest = self.root / 'project'
        self.dest.mkdir()
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.spec = {'repo': restore.REPO, 'revision': restore.REVISION, 'assets': []}
        self.payloads = {}
        for name in sorted(restore.MEMBERS):
            raw = ('synthetic:' + name).encode()
            path = self.cache / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            item = {'path': restore.PREFIX + name, 'remote_path': name,
                    'url': f'https://huggingface.co/{restore.REPO}/resolve/{restore.REVISION}/{name}',
                    'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            self.spec['assets'].append(item)
            self.payloads[item['url']] = raw

    def test_real_pinned_manifest_has_six_exact_assets(self):
        actual = restore.load_spec()
        self.assertEqual(len(actual['assets']), 6)
        self.assertEqual(sum(item['bytes'] for item in actual['assets']), 547486538)
        model = next(item for item in actual['assets'] if item['remote_path'].endswith('.onnx'))
        self.assertEqual(model['sha256'], '9710e442e94518da4175374e71459be69ca565f7a31369fa10f3a117e1c6d692')

    def test_cache_restore_exact_reuse_and_verify(self):
        first = restore.acquire(self.dest, self.spec, cache_dir=self.cache)
        self.assertEqual(first['cache_files_copied'], 6)
        self.assertEqual(first['network_requests'], 0)
        second = restore.acquire(self.dest, self.spec, cache_dir=self.cache)
        self.assertEqual(second['cache_files_copied'], 0)
        third = restore.acquire(self.dest, self.spec, verify_only=True)
        self.assertTrue(all(item['status'] == 'VERIFIED_EXISTING' for item in third['files']))

    def test_source_tamper_fails_before_any_target_write(self):
        (self.cache / self.spec['assets'][-1]['remote_path']).write_bytes(b'bad')
        with self.assertRaises(ValueError):
            restore.acquire(self.dest, self.spec, cache_dir=self.cache)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_destination_collision_is_never_overwritten(self):
        target = self.dest / self.spec['assets'][-1]['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            restore.acquire(self.dest, self.spec, cache_dir=self.cache)
        self.assertEqual(target.read_bytes(), b'keep')
        self.assertFalse((self.dest / self.spec['assets'][0]['path']).exists())

    def test_symlink_roots_and_cache_files_rejected(self):
        link = self.root / 'linked-project'
        link.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaises(OSError):
            restore.acquire(link, self.spec, cache_dir=self.cache)
        source = self.cache / self.spec['assets'][-1]['remote_path']
        saved = self.root / 'saved'
        source.rename(saved)
        source.symlink_to(saved)
        with self.assertRaises(OSError):
            restore.acquire(self.dest, self.spec, cache_dir=self.cache)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_manifest_tamper_paths_and_urls_rejected(self):
        for field, value in (('remote_path', '../escape'), ('path', '../escape'), ('url', 'http://example.com/asset')):
            changed = copy.deepcopy(self.spec)
            changed['assets'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                restore.validate_spec(changed)
        fake = self.root / 'fake.json'
        fake.write_text('{}')
        with self.assertRaises(ValueError):
            restore.load_spec(fake)

    def test_missing_mode_and_missing_verify_do_not_write(self):
        with self.assertRaises(ValueError):
            restore.acquire(self.dest, self.spec)
        with self.assertRaises(ValueError):
            restore.acquire(self.dest, self.spec, verify_only=True)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_bad_stream_never_admitted_and_temporary_removed(self):
        item = self.spec['assets'][0]
        fd = restore.directory(self.dest)
        try:
            with self.assertRaises(ValueError):
                restore.admit(fd, item, io.BytesIO(b'bad'))
        finally:
            restore.os.close(fd)
        self.assertFalse((self.dest / item['path']).exists())
        self.assertFalse(any(path.name.startswith('.asset-') for path in self.dest.rglob('*')))

    def test_explicit_download_is_mocked_and_exact(self):
        payloads = self.payloads

        class Response(io.BytesIO):
            def __init__(self, url):
                super().__init__(payloads[url])
                self.url = url

        with patch.object(restore.urllib.request, 'urlopen', side_effect=lambda req, timeout: Response(req.full_url)) as mocked:
            result = restore.acquire(self.dest, self.spec, download=True)
        self.assertEqual(mocked.call_count, 6)
        self.assertEqual(result['network_requests'], 6)
        self.assertEqual(result['model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
