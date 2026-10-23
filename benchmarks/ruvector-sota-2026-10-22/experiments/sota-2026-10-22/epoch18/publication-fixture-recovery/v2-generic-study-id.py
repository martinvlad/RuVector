"""Independent generic temporary-root derived-control checks only.

Never invokes the real operational CLI, parses cases or launches a model/native
process. The tested helper is outside the frozen scientific project.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

REAL_PROJECT = Path(__file__).resolve().parents[4]
HELPER = REAL_PROJECT.parent / 'build_epoch18_metadata.py'
PREFIX = Path('experiments/sota-2026-10-22')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DerivedPublicationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='e18-publication-review-')
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.root = self.p / 'project'
        self.s = self.root / PREFIX
        self.e = self.s / 'epoch18'
        spec = importlib.util.spec_from_file_location('review_e18_derived', HELPER)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.m.P, self.m.ROOT, self.m.S, self.m.E = self.p, self.root, self.s, self.e
        for rel in ['candidate/epoch18', 'controller/epoch18', 'legal-transfer/epoch18',
                    'audit/epoch18', 'epoch18']:
            (self.s / rel).mkdir(parents=True)
        for name in ['plan.json', 'candidate-source-freeze.json',
                     'SOURCE_MANIFEST.pre-native.json', 'USED_IDENTITIES.pre-native.json']:
            write(self.e / name, {'generic_fixture': name})
        write(self.e / 'plan.json', {'study_id': 'generic-bounded-typed-reader-e18'})
        write(self.s / 'audit/epoch18/prelabel-operational-admission-v1.json', {'generic': True})
        self.historical = {'path': 'historical/generic-source.py', 'bytes': 19, 'sha256': 'a' * 64}
        write(self.p / 'kit/CHECKPOINT_MANIFEST.json', {'project_files': [self.historical]})
        self.conf = {
            'input_only_allowlist': {'path': str(PREFIX / 'legal-transfer/epoch16/confirmation-input-allowlist.json'),
                                     'bytes': 100, 'sha256': 'b' * 64},
            'questions': 24, 'document_groups': 8, 'document_ids': list(range(1, 9)),
            'annotation_choices_projected': 0, 'globally_retired': False,
            'status': 'EXACT_LAZY_RECIPE_FROZEN_PROJECT_MODEL_UNUSED_RESERVED'}
        continuation = {
            'epochs': [], 'exposed_development_sets': [], 'used_confirmation_sets': [],
            'unused_confirmation_sets': [self.conf],
            'cumulative_budget_ledger': {'current_epoch_closed': True,
                                         'scope': 'ALL_EPOCHS_CLOSED_THROUGH17'},
            'benchmark_targets': {'JevBench': {'last_observed_at_UTC': 'earlier'},
                                  'ClaimBench': {'last_observed_at_UTC': 'earlier'}}}
        active = {'run_id': 'generic-e18-fixture', 'experiments_active': True, 'native_allowed': 0}
        write(self.p / 'lease-controls.json', {'active': active, 'continuation': continuation})
        write(self.s / 'legal-transfer/epoch18/benchmark-refresh.json', {
            'observed_at_UTC': 'generic-new-observation',
            'JevBench': {'leader': 'GenericPublicLeader', 'Capability_attribute': 85.336,
                         'headline_display': 85.3},
            'ClaimBench': {'decision_leader': {'model': 'generic/decision', 'accuracy_percent': 100.0},
                           'language_models_at100': [{}, {}, {}, {}]}})

    def control(self, phase):
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.controls(phase)
        d = self.p / ('capsule-' + phase)
        return read(d / 'ACTIVE_RUN.json'), read(d / 'CONTINUATION.json'), read(d / 'CHECKPOINT_MANIFEST.json')

    def prepare_final(self, projected):
        self.control('frozen')
        attempts = 2 if projected else 1
        write(self.e / 'EPOCH_MANIFEST.json', {
            'status': 'GENERIC_REJECTED_FIXTURE', 'accepted': False,
            'actual_execution': {'native_process_attempts': attempts},
            'confirmation': {'CONF_annotations_projected': projected},
            'cumulative_execution': {'native_corpus_attempts_including_failed_request': 18 + attempts},
            'originaltrain_partition': {'exposed': 229 if projected else 221,
                                        'unreserved': 178, 'reserved': 16 if projected else 24},
            'next_priority': 'Generic bounded future hypothesis; no scheduled work claimed.'})

    def test_frozen_pending_control_does_not_claim_current_epoch_closed(self):
        active, cont, _ = self.control('frozen')
        self.assertEqual(active['native_allowed'], 0)
        self.assertEqual(active['native_allowed_after_exact_remote_readback'], 2)
        self.assertFalse(cont['cumulative_budget_ledger']['current_epoch_closed'])
        self.assertEqual(cont['benchmark_targets']['JevBench']['last_observed_at_UTC'],
                         'generic-new-observation')
        self.assertEqual(cont['benchmark_targets']['ClaimBench']['last_observed_at_UTC'],
                         'generic-new-observation')

    def test_control_CP_exactly_covers_prior_and_actual_new_project_files(self):
        _, cont, cp = self.control('frozen')
        rows = {row['path']: row for row in cp['project_files']}
        self.assertEqual(len(rows), len(cp['project_files']))
        self.assertEqual(rows.pop(self.historical['path']), self.historical)
        expected = {row['path']: row for row in map(self.m.ident, self.m.allfiles())}
        self.assertEqual(rows, expected)
        self.assertEqual(cont['checkpoint_manifest_sha256'], sha(self.p / 'capsule-frozen/CHECKPOINT_MANIFEST.json'))

    def test_final_closure_clears_conditional_native_allowance(self):
        self.prepare_final(0)
        active, cont, _ = self.control('final')
        self.assertFalse(active['experiments_active'])
        self.assertEqual(active['native_allowed'], 0)
        self.assertEqual(active.get('native_allowed_after_exact_remote_readback', 0), 0)
        self.assertTrue(cont['cumulative_budget_ledger']['current_epoch_closed'])
        self.assertEqual(cont['cumulative_budget_ledger']['epoch18_closed_study']['remaining'], 0)
        self.assertTrue(cont['exposed_development_sets'])
        self.assertTrue(cont['unused_confirmation_sets'])

    def test_final_consumed_confirmation_is_not_claimed_unused(self):
        self.prepare_final(24)
        _, cont, _ = self.control('final')
        old = self.conf['input_only_allowlist']['path']
        for row in cont['unused_confirmation_sets']:
            if row.get('input_only_allowlist', {}).get('path') == old:
                self.assertTrue(row.get('globally_retired'))
                self.assertNotIn('PROJECT_MODEL_UNUSED', row.get('status', ''))
        self.assertTrue(cont['used_confirmation_sets'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
