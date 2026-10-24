"""Procedural archive round-trip and hostile-input tests; never runs ML/Git/network."""
from __future__ import annotations
import argparse
import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


HERE = Path(__file__).resolve().parent
RESTORE = load(HERE / 'restore_epoch26_archives_v1.py', 'epoch26_archive_test_restore')
PREPARE = load(HERE / 'prepare_epoch26_archives_v1.py', 'epoch26_archive_test_prepare')
PROJECT = HERE.parents[3]


class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_data = (PROJECT / RESTORE.MANIFEST_PATH).read_bytes()
        cls.manifest = RESTORE.validate_manifest(RESTORE.strict_json(cls.manifest_data))
        cls.archive_data = [(PROJECT / path).read_bytes() for path in RESTORE.ARCHIVES]
        cls.original_hashes_before = [RESTORE.ref((PROJECT / spec['path']).read_bytes(), spec['path'])
                                      for spec in RESTORE.SPECS]

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='epoch26-archive-test-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        paths = {RESTORE.MANIFEST_PATH, RESTORE.EXTRACTOR_PATH, RESTORE.HELPER_PATH, *RESTORE.ARCHIVES}
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / path, target)
        sentinel = b'Full checkpoint source hash proof.\n'
        (root / 'sentinel.txt').write_bytes(sentinel)
        rows = [RESTORE.ref((root / path).read_bytes(), path) for path in sorted(paths)]
        rows += [RESTORE.original_ref(spec) for spec in RESTORE.SPECS]
        rows.append(RESTORE.ref(sentinel, 'sentinel.txt'))
        cp = RESTORE.encode({'schema_version': 1, 'project_files': rows})
        (root / 'CHECKPOINT_MANIFEST.json').write_bytes(cp)
        continuation = {'schema_version': 1, 'checkpoint_manifest_sha256': RESTORE.sha(cp),
                        'artifact_transport': {'inherited_namespace_must_remain': 'unchanged'},
                        'epoch26_artifact_transports': {
                            'manifest': RESTORE.ref(self.manifest_data, RESTORE.MANIFEST_PATH),
                            'descriptors': self.manifest['descriptors']}}
        (root / 'CONTINUATION.json').write_bytes(RESTORE.encode(continuation))
        module = load(root / RESTORE.EXTRACTOR_PATH, 'epoch26_fixture_' + root.name)
        return root, module

    def test_actual_deterministic_archive_roundtrip_and_full_CP_restore(self):
        root, module = self.fixture()
        continuation_before = (root / 'CONTINUATION.json').read_bytes()
        result = module.restore(root)
        self.assertEqual(result['checkpoint_files_verified'], 8)
        self.assertTrue(all(item['status'] == 'RESTORED_EXCLUSIVE' for item in result['artifacts']))
        for spec, archive in zip(RESTORE.SPECS, self.archive_data):
            original = (PROJECT / spec['path']).read_bytes()
            self.assertEqual((root / spec['path']).read_bytes(), original)
            self.assertEqual(PREPARE.envelope_for(RESTORE, original, spec), archive)
            self.assertLess(len(PREPARE.blob_request(archive)), RESTORE.LIMIT)
        self.assertEqual((root / 'CONTINUATION.json').read_bytes(), continuation_before)
        verified = module.restore(root, verify_only=True)
        self.assertTrue(all(item['status'] == 'VERIFIED_EXISTING' for item in verified['artifacts']))
        with self.assertRaises(ValueError): module.restore(root)

    def test_explicit_manifest_requires_expected_hash(self):
        root, module = self.fixture()
        (root / 'CONTINUATION.json').unlink()
        with self.assertRaises(ValueError):
            module.restore(root, manifest_relative=RESTORE.MANIFEST_PATH)
        result = module.restore(root, manifest_relative=RESTORE.MANIFEST_PATH,
                                expected_manifest_sha256=RESTORE.sha(self.manifest_data))
        self.assertEqual(result['checkpoint_files_verified'], 8)

    def test_manifest_archive_helper_and_cp_tamper_rejected(self):
        for path in (RESTORE.MANIFEST_PATH, RESTORE.ARCHIVES[0], RESTORE.HELPER_PATH,
                     'CHECKPOINT_MANIFEST.json'):
            with self.subTest(path=path):
                root, module = self.fixture()
                target = root / path
                target.write_bytes(target.read_bytes() + b' ')
                with self.assertRaises(ValueError): module.restore(root)
                self.assertFalse((root / RESTORE.SPECS[0]['path']).exists())

    def test_existing_different_file_preserved(self):
        root, module = self.fixture()
        target = root / RESTORE.SPECS[0]['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'existing mismatching bytes')
        with self.assertRaises(ValueError): module.restore(root, verify_only=True)
        self.assertEqual(target.read_bytes(), b'existing mismatching bytes')

    def test_symlink_destination_and_source_parent_refused(self):
        root, module = self.fixture()
        target = root / RESTORE.P / 'runs'
        outside = root / 'outside'; outside.mkdir()
        target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): module.restore(root)
        self.assertEqual(list(outside.iterdir()), [])
        with self.assertRaises(ValueError): RESTORE.root_path(root / RESTORE.P / 'runs')

    def test_traversal_extra_descriptor_and_wrong_source_refused(self):
        for mutation in ('path', 'extra', 'source'):
            value = copy.deepcopy(self.manifest)
            if mutation == 'path': value['descriptors'][0]['archive']['path'] = '../escape.json'
            elif mutation == 'extra': value['descriptors'].append(copy.deepcopy(value['descriptors'][0]))
            else: value['source_commit'] = '0' * 40
            with self.assertRaises(ValueError): RESTORE.validate_manifest(value)

    def test_base64_compressed_metadata_and_artifact_pin_tamper(self):
        for mutation in ('base64', 'compressed_hash', 'original', 'mtime'):
            value = RESTORE.strict_json(self.archive_data[0])
            if mutation == 'base64': value['payload_base64'] = '!' + value['payload_base64'][1:]
            elif mutation == 'compressed_hash': value['gzip']['sha256'] = '0' * 64
            elif mutation == 'original': value['artifact']['sha256'] = '0' * 64
            else: value['gzip']['mtime'] = 1
            with self.assertRaises(ValueError):
                RESTORE.decode_envelope(RESTORE.encode(value), RESTORE.SPECS[0])

    def test_gzip_truncation_trailing_concat_expansion_bound(self):
        data = b'x' * 10000
        compressed = PREPARE.canonical_gzip(data)
        self.assertEqual(compressed[4:10], b'\0\0\0\0\x02\xff')
        self.assertEqual(RESTORE.compressed_member(compressed, len(data)), data)
        for payload, size in ((compressed[:-1], len(data)),
                              (compressed + b'junk', len(data)),
                              (compressed + compressed, len(data)), (compressed, 1)):
            with self.assertRaises(ValueError): RESTORE.compressed_member(payload, size)

    def test_strict_UTF8_duplicate_nonfinite_and_overflow_JSON(self):
        for data in (b'\xff', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'):
            with self.assertRaises((ValueError, UnicodeError)): RESTORE.strict_json(data)

    def test_raw_private_material_refused_before_compression(self):
        # Assemble fixtures so the public test source does not contain credentials.
        for value in ('-----BEGIN ' + 'PRIVATE KEY-----',
                      'ghp_' + 'A' * 35, '<' + 'html>page</html>'):
            data = json.dumps({'text': value}).encode()
            with self.assertRaises(ValueError): RESTORE.public_original(data)
        with self.assertRaises(ValueError):
            RESTORE.public_original(('Received' + ': raw message').encode())

    def test_full_checkpoint_unrelated_source_hash_tamper(self):
        root, module = self.fixture()
        (root / 'sentinel.txt').write_bytes(b'altered')
        with self.assertRaises(ValueError): module.restore(root)

    def test_archive_bound_and_exact_allowlist(self):
        with self.assertRaises(ValueError):
            RESTORE.decode_envelope(b' ' * RESTORE.LIMIT, RESTORE.SPECS[0])
        spec = dict(RESTORE.SPECS[0], path='outside.json')
        with self.assertRaises(ValueError): RESTORE.decode_envelope(self.archive_data[0], spec)

    @classmethod
    def tearDownClass(cls):
        after = [RESTORE.ref((PROJECT / spec['path']).read_bytes(), spec['path']) for spec in RESTORE.SPECS]
        if after != cls.original_hashes_before:
            raise AssertionError('Original run bytes changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=HERE / 'archive-tests.v1.json')
    args = parser.parse_args()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ArchiveTests))
    report = {'schema_version': 1, 'epoch': 26, 'kind': 'PROCEDURAL_ARCHIVE_TRANSPORT_TESTS',
              'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'passed': result.wasSuccessful(), 'output': stream.getvalue(),
              'actual_originals': list(RESTORE.SPECS),
              'source_commit': RESTORE.SOURCE_COMMIT,
              'model_native_tokenizer_Git_network_calls': 0,
              'scientific_acceptance_changed': False,
              'conf_labels_or_outputs_read': False,
              'frozen70_source_proof': PREPARE.source_proof(RESTORE, PROJECT),
              'transport_manifest': RESTORE.ref(ArchiveTests.manifest_data, RESTORE.MANIFEST_PATH)}
    args.report.write_bytes(RESTORE.encode(report))
    print(json.dumps({key: report[key] for key in ('tests_run', 'failures', 'errors', 'passed')}, sort_keys=True))
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)


if __name__ == '__main__':
    main()
