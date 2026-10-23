"""Independent complete generic2795-leaf/2718-CP source/final staging fixtures.

All bytes and roots are invented temporary fixtures. No real project staging,
Git requests, case parsing, annotation reads or model/native execution occurs.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCOPE_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('independent_e18_public_stage',
    SCOPE_ROOT / 'project/experiments/sota-2026-10-22/epoch19/publication/prepare_publication.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write(path, value):
    put(path, M.raw_json(value))


class CompletePublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='e18-stager-independent-')
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.project, self.kit = self.p / 'project', self.p / 'kit'
        self.project.mkdir(); self.kit.mkdir()
        historical = []
        for n in range(2718):
            rel = f'historical/generic-{n:04d}.txt'
            raw = ('GENERIC_PUBLIC_SOURCE_' + str(n)).encode()
            put(self.kit / rel, raw)
            historical.append({'path': rel, 'bytes': len(raw), 'sha256': M.sha(raw)})
        self.cp = {'project_files': historical}
        write(self.kit / 'CHECKPOINT_MANIFEST.json', self.cp)
        write(self.kit / 'ACTIVE_RUN.json', {'generic': 'historical'})
        write(self.kit / 'CONTINUATION.json', {'generic': 'historical'})
        for n in range(74):
            put(self.kit / f'metadata/generic-{n:03d}.txt', b'GENERIC_METADATA')
        rows = [M.leaf(f.relative_to(self.kit).as_posix(), f.read_bytes())
                for f in sorted(self.kit.rglob('*')) if f.is_file()]
        self.assertEqual(len(rows), 2795)
        self.filemap = self.p / 'source-filemap.json'
        write(self.filemap, rows)
        M.SOURCE_FILEMAP_SHA = M.sha(self.filemap.read_bytes())
        M.SOURCE_CP_SHA = M.sha((self.kit / 'CHECKPOINT_MANIFEST.json').read_bytes())
        for n, directory in enumerate(M.DIRS):
            put(self.project / directory / 'generic-fixture.txt', f'GENERIC_ROLE_SOURCE_{n}'.encode())
        write(self.project / (M.PREFIX + 'epoch19/large-public-fixture.json'),
              {'generic_unicode': '\u03a9' * 150000})
        self.source_controls = self.p / 'source-controls'
        self.build_controls(self.source_controls, source=True)

    def build_controls(self, directory, source):
        directory.mkdir()
        current = M.walk_current(self.project)
        cp = copy.deepcopy(self.cp)
        cp['project_files'] += [{'path': p, 'bytes': len(b), 'sha256': M.sha(b)}
                                for p, b in sorted(current.items())]
        write(directory / 'CHECKPOINT_MANIFEST.json', cp)
        active = {'run_id': 'GENERIC_EXCLUSIVE_OWNER', 'native_allowed': 0,
                  'experiments_active': source}
        write(directory / 'ACTIVE_RUN.json', active)
        write(directory / 'CONTINUATION.json', {
            'checkpoint_manifest_sha256': M.sha((directory / 'CHECKPOINT_MANIFEST.json').read_bytes()),
            'active_run': active})

    def args(self, name, controls=None, final=False, prior=None):
        return argparse.Namespace(project=self.project, kit=self.kit, source_filemap=self.filemap,
            controls_dir=controls or self.source_controls, out=self.p / name,
            mode='final' if final else 'source', prior_expected=prior, reviewed_files=None)

    def reconstruct(self, stage):
        meta = json.loads((stage / 'manifest.json').read_text())
        blob = {}
        for row in meta['large_blob_requests']:
            raw = (stage / row['file']).read_bytes()
            self.assertEqual(M.sha(raw), row['sha256'])
            self.assertEqual(len(raw), row['bytes'])
            payload = json.loads(raw)
            self.assertEqual(payload['encoding'], 'utf-8')
            b = payload['content'].encode('utf-8')
            self.assertEqual(M.gitsha(b), row['expected_blob_sha1'])
            blob[row['expected_blob_sha1']] = b
        reconstructed = {}
        for row in meta['create_tree_groups']:
            raw = (stage / row['file']).read_bytes()
            self.assertLess(len(raw), 190000)
            self.assertEqual(M.sha(raw), row['sha256'])
            for item in json.loads(raw)['tree_elements']:
                self.assertTrue(item['path'].startswith(M.SCOPE))
                rel = item['path'][len(M.SCOPE):]
                self.assertNotIn(rel, reconstructed)
                self.assertEqual((item['mode'], item['type']), ('100644', 'blob'))
                reconstructed[rel] = item['content'].encode('utf-8') if 'content' in item else blob[item['sha']]
        expected = {row['path']: row for row in meta['new_and_control_files']}
        self.assertEqual(set(expected), set(reconstructed))
        for rel, b in reconstructed.items():
            self.assertEqual(len(b), expected[rel]['bytes'])
            self.assertEqual(M.sha(b), expected[rel]['sha256'])
            self.assertEqual(M.gitsha(b), expected[rel]['git_blob_sha1'])
            self.assertEqual(b, (stage / 'changed' / rel).read_bytes())
        return meta

    def test_full_source_then_append_only_final_exact_transports(self):
        source = self.args('source-stage')
        M.prepare(source)
        meta = self.reconstruct(source.out)
        self.assertTrue(meta['large_blob_requests'])
        self.assertEqual(meta['new_public18_leaves'], 6)
        expected = json.loads((source.out / 'expected-leaves.json').read_text())
        self.assertEqual(len(expected['files']), 2801)
        final_manifest = self.project / (M.PREFIX + 'epoch19/EPOCH_MANIFEST.json')
        write(final_manifest, {'status': 'GENERIC_FINAL_ONLY', 'accepted': False})
        final_controls = self.p / 'final-controls'
        self.build_controls(final_controls, source=False)
        final = self.args('final-stage', final_controls, True, source.out / 'expected-leaves.json')
        M.prepare(final)
        finalmeta = self.reconstruct(final.out)
        self.assertEqual(finalmeta['new_public18_leaves'], 7)
        self.assertEqual(set(row['path'] for row in finalmeta['new_and_control_files']),
                         M.CONTROLS | {M.PREFIX + 'epoch19/EPOCH_MANIFEST.json'})
        self.assertEqual(len(json.loads((final.out / 'expected-leaves.json').read_text())['files']), 2802)

    def test_full_pipeline_rejects_old_source_control_and_published_source_mutations(self):
        # First preserve a complete generic source publication to test final drift.
        source = self.args('source-stage')
        M.prepare(source)
        published = source.out / 'expected-leaves.json'
        # Changed historical raw bytes must fail the exact Git tuple check.
        historical = self.kit / 'historical/generic-0000.txt'
        old = historical.read_bytes(); historical.write_bytes(b'CHANGED_GENERIC_HISTORY')
        with self.assertRaisesRegex(ValueError, 'Historical source Git tuple changed'):
            M.prepare(self.args('bad-history'))
        historical.write_bytes(old)
        # Premature source native allowance must fail before creating any stage.
        active = self.source_controls / 'ACTIVE_RUN.json'; good = active.read_bytes()
        value = json.loads(good); value['native_allowed'] = 2; write(active, value)
        with self.assertRaisesRegex(ValueError, 'zero native admission'):
            M.prepare(self.args('bad-source-allowance'))
        active.write_bytes(good)
        # A source file changed after publication is forbidden in final mode.
        changed = self.project / (M.PREFIX + 'candidate/epoch19/generic-fixture.txt')
        changed.write_bytes(b'CHANGED_PUBLISHED_SCIENTIFIC_SOURCE')
        write(self.project / (M.PREFIX + 'epoch19/EPOCH_MANIFEST.json'), {'generic': 'final'})
        controls = self.p / 'final-controls'; self.build_controls(controls, source=False)
        with self.assertRaisesRegex(ValueError, 'Published18 source changed or disappeared'):
            M.prepare(self.args('bad-final-source', controls, True, published))
        for name in ('bad-history', 'bad-source-allowance', 'bad-final-source'):
            self.assertFalse((self.p / name).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
