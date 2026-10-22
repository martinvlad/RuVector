"""Source-only miniature closures. Never loads addons or model runtimes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch5_runtime_restore', HERE / 'restore_runtime.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


def fixture(root):
    groups = {'core': [], 'typesafe': []}
    for group, count in (('core', 8), ('typesafe', 14)):
        for index in range(count):
            path = ('retrieval/node_modules/core/' if group == 'core' else 'node_modules/typesafe/') + str(index) + '.js'
            raw = (group + str(index)).encode()
            file = root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
            groups[group].append({'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return groups


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.groups = fixture(self.cache)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.caches = dict.fromkeys(self.groups, self.cache)

    def test_exact22_materialize_reuse_and_offline_verify(self):
        receipt = restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(receipt['counts'], {'core': 8, 'typesafe': 14})
        self.assertEqual(receipt['created'], 22)
        self.assertEqual(receipt['native_addon_loads'], 0)
        second = restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['reused_exact'], 22)
        verified = restore.materialize(self.project, self.groups, verify_only=True)
        self.assertEqual(verified['reused_exact'], 22)

    def test_source_tamper_fails_before_any_destination_write(self):
        item = self.groups['typesafe'][-1]
        (self.cache / item['path']).write_bytes(b'bad')
        with self.assertRaises(ValueError):
            restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_destination_collision_is_not_overwritten(self):
        item = self.groups['typesafe'][-1]
        target = self.project / item['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'keep-this')
        with self.assertRaises(ValueError):
            restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(target.read_bytes(), b'keep-this')
        self.assertFalse((self.project / 'retrieval').exists())

    def test_destination_symlink_ancestor_cannot_write_outside(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.project / 'retrieval').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_file_is_rejected(self):
        item = self.groups['typesafe'][-1]
        source = self.cache / item['path']
        held = self.root / 'held'
        source.rename(held)
        source.symlink_to(held)
        with self.assertRaises(OSError):
            restore.materialize(self.project, self.groups, self.caches)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_source_root_symlink_is_rejected(self):
        link = self.root / 'cache-link'
        link.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(OSError):
            restore.materialize(self.project, self.groups, dict.fromkeys(self.groups, link))

    def test_missing_verify_target_fails_without_writes(self):
        with self.assertRaises(ValueError):
            restore.materialize(self.project, self.groups, verify_only=True)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_path_traversal_and_duplicate_paths_rejected(self):
        for value in ('../escape', '/escape', 'a/../b', 'a//b', './a', 'a\\b', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                restore.parts(value)
        groups = {'core': [self.groups['core'][0]], 'typesafe': [self.groups['core'][0]]}
        with self.assertRaises(ValueError):
            restore.materialize(self.project, groups, self.caches)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_real_small_spec_pins_and_runtime_binary_crosscheck(self):
        groups = restore.load_specs()
        self.assertEqual({k: len(v) for k, v in groups.items()}, {'core': 8, 'typesafe': 14})
        copied = self.root / 'specs'
        copied.mkdir()
        for name in restore.SPEC_PINS:
            (copied / name).write_bytes((HERE / name).read_bytes())
        (copied / 'typesafe-runtime-closure.json').write_text('{}')
        with self.assertRaises(ValueError):
            restore.load_specs(copied)


if __name__ == '__main__':
    unittest.main()
