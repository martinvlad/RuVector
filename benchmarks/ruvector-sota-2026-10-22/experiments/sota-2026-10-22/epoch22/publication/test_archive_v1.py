"""Small transport guard tests and an opaque-byte actual archive roundtrip.

These tests do not evaluate the benchmark or run the bootstrap. Root performs
the full unchanged bootstrap/restore test after final controls are prepared.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

PUBLICATION = 'experiments/sota-2026-10-22/epoch22/publication/'


def load(path):
    spec = importlib.util.spec_from_file_location('archive_' + str(id(path)), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + '\n').encode('utf-8')


def reference(path, relative):
    data = path.read_bytes()
    return {'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class ArchiveTests(unittest.TestCase):
    project = None
    recorded_roundtrip = None
    executed_names = []

    @classmethod
    def setUpClass(cls):
        cls.publication = cls.project / PUBLICATION
        cls.builder = load(cls.publication / 'build_archive_v1.py')
        cls.extractor_source = cls.publication / 'restore_archived_artifact_v1.py'
        cls.api = load(cls.extractor_source)
        cls.archive = (cls.project / cls.api.ARCHIVE_PATH).read_bytes()
        cls.archive_sha = cls.api.sha256(cls.archive)

    def setUp(self):
        self.executed_names.append(self.id().rsplit('.', 1)[-1])
        self.temporary = tempfile.TemporaryDirectory(prefix='epoch22-archive-guards-')
        self.addCleanup(self.temporary.cleanup)
        self.kit = Path(self.temporary.name) / 'kit'
        self.kit.mkdir()
        archive_path = self.kit / self.api.ARCHIVE_PATH
        archive_path.parent.mkdir(parents=True)
        archive_path.write_bytes(self.archive)
        source_path = self.kit / self.api.EXTRACTOR_PATH
        shutil.copyfile(self.extractor_source, source_path)
        self.api_fixture = load(source_path)
        self.checkpoint = {'schema_version': 1, 'project_files': [
            self.api.RAW_REF,
            reference(archive_path, self.api.ARCHIVE_PATH),
            reference(source_path, self.api.EXTRACTOR_PATH),
            reference(self.project / self.api.PUBLICATION_HELPER_PATH,
                      self.api.PUBLICATION_HELPER_PATH)]}
        self.write_controls()
        (self.kit / 'ACTIVE_RUN.json').write_bytes(json_bytes({
            'schema_version': 1, 'epoch': 22, 'state': 'EPOCH22_CLOSED',
            'experiments_active': False, 'native_allowed': 0}))

    def write_controls(self, *, continuation_change=None):
        cp = json_bytes(self.checkpoint)
        (self.kit / 'CHECKPOINT_MANIFEST.json').write_bytes(cp)
        rows = {r['path']: r for r in self.checkpoint['project_files']}
        transport = {'format': 'gzip+base64',
                     'archive': rows[self.api.ARCHIVE_PATH],
                     'extractor': rows[self.api.EXTRACTOR_PATH],
                     'restored_artifact': self.api.RAW_REF,
                     'required_before_bootstrap': True,
                     'publication_helper': rows[self.api.PUBLICATION_HELPER_PATH],
                     'standalone_Git_leaf_omitted': self.api.RAW_PATH}
        continuation = {'schema_version': 1,
                        'checkpoint_manifest_sha256': hashlib.sha256(cp).hexdigest(),
                        'artifact_transport': transport}
        if continuation_change:
            continuation_change(continuation)
        (self.kit / 'CONTINUATION.json').write_bytes(json_bytes(continuation))

    def run_restore(self, **kwargs):
        return self.api_fixture.restore(str(self.kit), self.api.ARCHIVE_PATH,
                                        self.archive_sha, **kwargs)

    def test_actual_roundtrip_and_verify_only(self):
        target = self.kit / self.api.RAW_PATH
        verification = self.run_restore(verify_only=True)
        self.assertEqual(verification['status'], 'VERIFIED_ARCHIVE_ONLY')
        self.assertFalse(target.exists())
        restored = self.run_restore()
        self.assertEqual(restored['status'], 'RESTORED_EXCLUSIVE')
        original = (self.project / self.api.RAW_PATH).read_bytes()
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.api.git_sha1(original), self.api.RAW_GIT_SHA1)
        self.assertEqual(self.run_restore()['status'], 'ALREADY_PRESENT_MATCHING')
        type(self).recorded_roundtrip = {
            'fixture_metadata_files': ['CHECKPOINT_MANIFEST.json', 'CONTINUATION.json', 'ACTIVE_RUN.json'],
            'fixture_other_initial_files': [self.api.ARCHIVE_PATH, self.api.EXTRACTOR_PATH],
            'verify_only_created_no_raw': True, 'restored_exclusive': True,
            'restored_bytes_equal_sealed_original': True,
            'restored_sha256': self.api.sha256(original),
            'restored_git_blob_sha1': self.api.git_sha1(original),
            'restored_bytes': len(original), 'second_restore_matching_idempotent': True}

    def test_deterministic_encoding_and_request_limit(self):
        raw = (self.project / self.api.RAW_PATH).read_bytes()
        first, _, sizes = self.builder.encode(raw)
        second, _, _ = self.builder.encode(raw)
        self.assertEqual(first, second)
        self.assertEqual(first, self.archive)
        self.assertLess(len(first), self.api.LIMIT)
        self.assertLess(sizes['Git_API_JSON_request_bound_bytes'], self.api.LIMIT)
        self.assertLess(sizes['Git_API_JSON_request_bound_bytes'], 16 * 1024 * 1024)

    def test_wrong_expected_archive_hash(self):
        with self.assertRaises(ValueError):
            self.api_fixture.restore(str(self.kit), self.api.ARCHIVE_PATH, '0' * 64)

    def test_wrong_archive_path(self):
        with self.assertRaises(ValueError):
            self.api_fixture.restore(str(self.kit), '../outside.json', self.archive_sha)

    def test_archive_corruption(self):
        target = self.kit / self.api.ARCHIVE_PATH
        altered = bytearray(self.archive)
        altered[-2] ^= 1
        target.write_bytes(altered)
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_symlink_archive(self):
        target = self.kit / self.api.ARCHIVE_PATH
        target.unlink()
        target.symlink_to(self.project / self.api.ARCHIVE_PATH)
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_symlink_target_preserved(self):
        target = self.kit / self.api.RAW_PATH
        target.parent.mkdir(parents=True)
        sentinel = Path(self.temporary.name) / 'sentinel'
        sentinel.write_bytes(b'keep')
        target.symlink_to(sentinel)
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertTrue(target.is_symlink())
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_existing_mismatch_preserved(self):
        target = self.kit / self.api.RAW_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(b'keep-existing-mismatch')
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(target.read_bytes(), b'keep-existing-mismatch')

    def test_checkpoint_hash_pin(self):
        self.write_controls(continuation_change=lambda c: c.update(checkpoint_manifest_sha256='0' * 64))
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_raw_checkpoint_pin(self):
        self.checkpoint['project_files'][0] = {**self.api.RAW_REF, 'sha256': '0' * 64}
        self.write_controls()
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_duplicate_checkpoint_path(self):
        self.checkpoint['project_files'].append(self.checkpoint['project_files'][1])
        self.write_controls()
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_extractor_own_source_pin(self):
        with (self.kit / self.api.EXTRACTOR_PATH).open('ab') as stream:
            stream.write(b'\n# changed source\n')
        with self.assertRaises(ValueError):
            self.run_restore()

    def test_invalid_base64_and_extra_payload(self):
        envelope = self.api.strict_json(self.archive)
        envelope['payload_base64'] = '!invalid!'
        with self.assertRaises(ValueError):
            self.api.decode_envelope(json_bytes(envelope))
        envelope = self.api.strict_json(self.archive)
        envelope['hook'] = 'forbidden'
        with self.assertRaises(ValueError):
            self.api.decode_envelope(json_bytes(envelope))

    def test_artifact_path_and_size_guards(self):
        envelope = self.api.strict_json(self.archive)
        envelope['artifact']['path'] = '../outside'
        with self.assertRaises(ValueError):
            self.api.decode_envelope(json_bytes(envelope))
        envelope = self.api.strict_json(self.archive)
        envelope['artifact']['bytes'] += 1
        with self.assertRaises(ValueError):
            self.api.decode_envelope(json_bytes(envelope))

    def test_bounded_gzip_and_trailing_member(self):
        buffer = io.BytesIO()
        with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', mtime=0) as stream:
            stream.write(b'x' * 21)
        compressed = buffer.getvalue()
        with self.assertRaises(ValueError):
            self.api.decompress_bounded(compressed, 20)
        with self.assertRaises(ValueError):
            self.api.decompress_bounded(compressed + compressed, 21)
        with self.assertRaises(ValueError):
            self.api.decompress_bounded(b'x' * (self.api.LIMIT + 1), 21)

    def test_duplicate_json_members(self):
        with self.assertRaises(ValueError):
            self.api.strict_json(b'{"schema_version":1,"schema_version":1}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True)
    arguments = parser.parse_args()
    os.sched_setaffinity(0, {0, 1})
    ArchiveTests.project = Path(arguments.project_root)
    if not ArchiveTests.project.is_absolute() or ArchiveTests.project != ArchiveTests.project.resolve():
        raise ValueError('Canonical absolute project root required')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ArchiveTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    api = ArchiveTests.api
    publication = ArchiveTests.project / PUBLICATION
    envelope = api.strict_json(ArchiveTests.archive)
    sizes = ArchiveTests.builder.encoded_request_sizes(ArchiveTests.archive)
    source_refs = {name: reference(publication / name, PUBLICATION + name) for name in [
        'build_archive_v1.py', 'restore_archived_artifact_v1.py', 'test_archive_v1.py']}
    receipt = {'schema_version': 1, 'epoch': 22,
               'at': datetime.now(timezone.utc).isoformat(),
               'kind': 'OPAQUE_ARTIFACT_ARCHIVE_ROUNDTRIP_AND_TRANSPORT_GUARDS',
               'status': 'PASS', 'checks_passed': True,
               'archive': reference(publication / 'actualarchive.dev.raw.v1.json', api.ARCHIVE_PATH),
               'artifact': envelope['artifact'], 'gzip': envelope['gzip'],
               'sources': source_refs, 'Git_API_request': sizes,
               'archive_below_8MiB': len(ArchiveTests.archive) < api.LIMIT,
               'Git_API_JSON_request_bound_below_8MiB': sizes['Git_API_JSON_request_bound_bytes'] < api.LIMIT,
               'Git_API_JSON_request_bound_below_16MiB': sizes['Git_API_JSON_request_bound_bytes'] < 16 * 1024 * 1024,
               'actual_roundtrip': ArchiveTests.recorded_roundtrip,
               'guard_tests': {'run': result.testsRun, 'failures': len(result.failures),
                               'errors': len(result.errors), 'names': ArchiveTests.executed_names},
               'CPU_affinity': sorted(os.sched_getaffinity(0)),
               'scope': {'raw_parsed_as_JSON': False, 'original_corpus_or_gold_reads': 0,
                         'model_native_tokenizer_calls': 0, 'network_calls': 0,
                         'bootstrap_or_restore_checkpoint_run': False,
                         'benchmark_generalization_claim': False},
               'restoration_order': 'Run this CP-pinned extractor before the unchanged reviewed bootstrap.py and restore_checkpoint.py in a fresh kit; it does not replace either.',
               'CP_still_pins_exact_decoded_original_raw': True}
    output = publication / 'archive-roundtrip-v1.json'
    with output.open('xb') as stream:
        stream.write(json_bytes(receipt))
    print(json.dumps({'receipt': reference(output, PUBLICATION + output.name),
                      'archive': receipt['archive'], 'sources': source_refs,
                      'Git_API_request': sizes, 'tests_run': result.testsRun}, sort_keys=True))


if __name__ == '__main__':
    main()
