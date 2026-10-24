"""Synthetic transport-only guards; frozen scientific guards are unchanged."""
import sys
sys.dont_write_bytecode = True
import base64
import ast
import copy
import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import publication_common_v1 as c
import stage_publication_v1 as base
import finalstage_archive_v2 as stage
import archive_stage_guards_v2 as g
from test_publication_guards_v1 import Fixture

HERE = Path(__file__).resolve().parent


def packed(body):
    output = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, compresslevel=9, mtime=0) as stream:
        stream.write(body)
    return output.getvalue()


def envelope(path, body, compressed=None):
    compressed = packed(body) if compressed is None else compressed
    spec = g.SPECS[path]
    return {'schema_version': 1, 'epoch': 26, 'source_commit': g.SOURCE_COMMIT,
        'format': 'gzip+base64', 'artifact': {'path': path, 'bytes': len(body),
            'sha256': c.sha(body), 'git_blob_sha1': c.gitsha(body)},
        'gzip': {'bytes': len(compressed), 'sha256': c.sha(compressed), 'mtime': 0},
        'payload_base64': base64.b64encode(compressed).decode('ascii')}


class ArchiveGuards(unittest.TestCase):
    def setUp(self):
        self.raw_path, self.native_path = list(g.SPECS)
        self.body = b'{"public":"exact evidence"}\n'
        self.specs = copy.deepcopy(g.SPECS)
        for value in self.specs.values():
            value.update(bytes=len(self.body), sha256=c.sha(self.body), git_blob_sha1=c.gitsha(self.body))
        patcher = patch.object(g, 'SPECS', self.specs); patcher.start(); self.addCleanup(patcher.stop)

    def decode(self, value=None, body=None, path=None):
        value = envelope(self.raw_path, self.body) if value is None else value
        return g.decode_archive(self.specs[self.raw_path]['archive'], c.encoded(value),
            self.raw_path if path is None else path, self.body if body is None else body)

    def test_exact_roundtrip(self): self.assertEqual(self.decode()['sha256'], c.sha(self.body))

    def test_original_hash_change_rejected(self):
        with self.assertRaises(ValueError): self.decode(body=self.body+b' ')

    def test_wrong_original_path_rejected(self):
        with self.assertRaises(ValueError): self.decode(path=g.E+'runs/dev/native-bundle.json')

    def test_manifest_wrong_source_rejected(self):
        value = envelope(self.raw_path, self.body); value['source_commit'] = 'f'*40
        with self.assertRaises(ValueError): self.decode(value)

    def test_noncanonical_base64_rejected(self):
        value = envelope(self.raw_path, self.body); value['payload_base64'] += '\n'
        with self.assertRaises(ValueError): self.decode(value)

    def test_extra_envelope_key_rejected(self):
        value = envelope(self.raw_path, self.body); value['unreviewed'] = True
        with self.assertRaises(ValueError): self.decode(value)

    def test_gzip_trailing_data_rejected(self):
        value = envelope(self.raw_path, self.body, packed(self.body)+b'trailing')
        with self.assertRaises(ValueError): self.decode(value)

    def test_second_gzip_member_rejected(self):
        value = envelope(self.raw_path, self.body, packed(self.body)+packed(self.body))
        with self.assertRaises(ValueError): self.decode(value)

    def test_decoded_oversize_rejected(self):
        value = envelope(self.raw_path, self.body, packed(self.body+b'overflow'))
        with self.assertRaises(ValueError): self.decode(value)

    def test_tampered_compressed_identity_rejected(self):
        value = envelope(self.raw_path, self.body); value['gzip']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.decode(value)

    def test_nondeterministic_mtime_rejected(self):
        compressed = bytearray(packed(self.body)); compressed[4] = 1
        with self.assertRaises(ValueError): self.decode(envelope(self.raw_path, self.body, bytes(compressed)))

    def test_raw_private_payload_rejected(self):
        private = ('ghp_'+'a'*35).encode()
        value = self.specs[self.raw_path]
        value.update(bytes=len(private), sha256=c.sha(private), git_blob_sha1=c.gitsha(private))
        with self.assertRaises(ValueError): self.decode(envelope(self.raw_path, private), private)

    def test_original_cp_identity_rejected(self):
        with tempfile.TemporaryDirectory(prefix='archive-cp-', dir=HERE) as name:
            root = Path(name); path = self.raw_path
            file = root/path; file.parent.mkdir(parents=True); file.write_bytes(self.body)
            row = c.ref(root, path); drift = dict(row, sha256='0'*64)
            with self.assertRaises(ValueError): g.checked_ref(root, drift, {path: row}, path)

    def test_only_exact_two_leaves_omitted(self):
        current = {self.raw_path: self.body, self.native_path: self.body,
            g.E+'runs/dev/native-bundle.json': b'{}', g.MANIFEST_PATH: b'{}'}
        published = g.publication_items(current, {'ACTIVE_RUN.json': b'{}'}, set(self.specs))
        self.assertTrue(set(self.specs).isdisjoint(published))
        self.assertIn(g.E+'runs/dev/native-bundle.json', published)
        self.assertEqual(len(current), 4)
        with self.assertRaises(ValueError): g.publication_items(current, {}, {self.raw_path})

    def test_frozen_base_pins_unchanged(self): g.frozen_base_unchanged()

    def test_frozen_base_tamper_rejected(self):
        with patch.object(g, 'content', return_value=b'changed frozen source'):
            with self.assertRaises(ValueError): g.frozen_base_unchanged()

    def test_all_frozen_guard_functions_are_exact_copies(self):
        def functions(name):
            tree = ast.parse((HERE/name).read_text())
            return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != 'prepare'}
        self.assertEqual(functions('stage_publication_v1.py'), functions('finalstage_archive_v2.py'))

    def test_end_to_end_rejected_archive_stage(self):
        with tempfile.TemporaryDirectory(prefix='archive-stage-', dir=HERE) as name:
            f = Fixture(Path(name))
            with patch.object(base, 'BASE_GIT_LEAVES', 6), patch.object(c, 'OLD_CP_ROWS', 4), patch.object(base, 'live_owner'):
                base.prepare(f.args())
            manifest = f.final_files()
            raw_file = f.project/self.raw_path; raw = c.loads(raw_file.read_bytes())
            raw.update(source_checkpoint=c.BASE_COMMIT, plan_sha256=f.frozen['plan']['sha256'],
                source_freeze_sha256=f.frozen['source_freeze']['sha256'])
            raw_file.write_bytes(c.encoded(raw, pretty=True))
            bundle_path = g.E+'runs/dev/native-bundle.json'
            bundle = f.project/bundle_path; bundle.write_bytes(b'{"documents":[]}\n')
            native = {'epoch': 26, 'native': True, 'stage': 'HELPER_COMPLETED',
                'native_index_initializations_completed': 8, 'native_queries_completed': 24,
                'Node_network_operations_attempted': 0, 'network_violations': [], 'bundle_sha256': c.sha(bundle.read_bytes())}
            (f.project/self.native_path).write_bytes(c.encoded(native, pretty=True))
            specs = copy.deepcopy(self.specs)
            for path, value in specs.items():
                body = (f.project/path).read_bytes()
                value.update(bytes=len(body), sha256=c.sha(body), git_blob_sha1=c.gitsha(body))
            bootstrap = f.kit/'bootstrap.py'; bootstrap.write_bytes(b'# original bootstrap\n')
            restore = f.kit/'restore_checkpoint.py'; restore.write_bytes(b'# original restore\n')
            with patch.object(g, 'SPECS', specs), patch.object(g, 'SOURCE_COMMIT', 'a'*40), patch.object(g, 'SOURCE_CP_ROWS', len(c.cp_rows(f.source_cp))), \
                    patch.object(g, 'BOOTSTRAP_SHA256', c.sha(bootstrap.read_bytes())), patch.object(g, 'RESTORE_SHA256', c.sha(restore.read_bytes())):
                for path in (g.EXTRACTOR_PATH, g.HELPER_PATH):
                    target = f.project/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'pass\n')
                descriptors = []
                for path, value in specs.items():
                    body = (f.project/path).read_bytes(); archive = f.project/value['archive']
                    archive.parent.mkdir(parents=True, exist_ok=True); archive.write_bytes(c.encoded(envelope(path, body), pretty=True))
                    descriptors.append({'format': 'gzip+base64', 'archive': c.ref(f.project, value['archive']),
                        'extractor': c.ref(f.project, g.EXTRACTOR_PATH), 'restored_artifact': c.ref(f.project, path),
                        'publication_helper': c.ref(f.project, g.HELPER_PATH), 'required_before_bootstrap': True,
                        'standalone_Git_leaf_omitted': path, 'source_commit': 'a'*40})
                (f.project/g.MANIFEST_PATH).write_bytes(c.encoded({'schema_version': 1, 'epoch': 26,
                    'source_commit': 'a'*40, 'format': 'gzip+base64', 'descriptors': descriptors}, pretty=True))
                outer_file = f.project/manifest['execution']['path']; outer = c.loads(outer_file.read_bytes())
                outer.update(raw_bytes=specs[self.raw_path]['bytes'], raw_sha256=specs[self.raw_path]['sha256'])
                outer_file.write_bytes(c.encoded(outer, pretty=True))
                evidence = {'raw': c.ref(f.project, self.raw_path), 'execution': c.ref(f.project, manifest['execution']['path']),
                    'results': manifest['results']}
                report_file = f.project/manifest['independent_report']['path']; report = c.loads(report_file.read_bytes())
                report.update(diagnostic_qualified=False, evidence=evidence); report_file.write_bytes(c.encoded(report, pretty=True))
                manifest.update(diagnostic_qualified=False, status='REJECTED_DEV_DIAGNOSTIC',
                    independent_report=c.ref(f.project, manifest['independent_report']['path']), **evidence)
                (f.project/(g.E+'EPOCH_MANIFEST.json')).write_bytes(c.encoded(manifest, pretty=True))
                cont = c.parse(f.root/'controls-final/CONTINUATION.json')
                cp = f.cp(); cp_bytes = c.encoded(cp, pretty=True)
                cont.update(checkpoint_manifest_sha256=c.sha(cp_bytes),
                    epoch26_artifact_transports={'manifest': c.ref(f.project, g.MANIFEST_PATH), 'descriptors': descriptors},
                    epoch26_restore={'manifest': c.ref(f.project, g.MANIFEST_PATH),
                        'extractor': c.ref(f.project, g.EXTRACTOR_PATH), 'run_after_inherited_epoch22_restore': True,
                        'must_run_before_bootstrap': True, 'original_bootstrap': c.ref(f.kit, 'bootstrap.py'),
                        'original_restore': c.ref(f.kit, 'restore_checkpoint.py'), 'instructions': 'old22, new26, original bootstrap/restore'})
                (f.root/'controls-final/CHECKPOINT_MANIFEST.json').write_bytes(cp_bytes)
                (f.root/'controls-final/CONTINUATION.json').write_bytes(c.encoded(cont, pretty=True))
                f.review('final-reviewed-files.json')
                with patch.object(stage, 'BASE_GIT_LEAVES', 6), patch.object(c, 'OLD_CP_ROWS', 4), patch.object(stage, 'live_owner'):
                    result = stage.prepare(f.args('final'))
                leaves = stage.tuple_map(c.parse(f.root/'stage-final/expected-leaves.json'))
                checkpoint = c.cp_rows(c.parse(f.root/'controls-final/CHECKPOINT_MANIFEST.json'))
                self.assertEqual(result['stage'], 'final')
                self.assertTrue(set(specs).isdisjoint(leaves))
                self.assertTrue(set(specs) <= set(checkpoint))
                self.assertIn(bundle_path, leaves)
                self.assertFalse(manifest['diagnostic_qualified'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ArchiveGuards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'schema_version': 1, 'epoch': 26, 'kind': 'SYNTHETIC_ARCHIVE_TRANSPORT_GUARDS_ONLY',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'checks_passed': result.wasSuccessful(), 'scientific_threshold_changes': 0,
        'frozen_source_files_modified': 0, 'Git_network_mail_model_native_calls': 0,
        'cases': [case._testMethodName for case in unittest.defaultTestLoader.loadTestsFromTestCase(ArchiveGuards)]}
    (HERE/'archive-guard-tests.v2.json').write_bytes(c.encoded(report, pretty=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
