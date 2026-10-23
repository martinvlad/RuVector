"""Independent temporary-root fault probes; never reads corpus/model contents.

The final-validator sentinel is intentionally synthetic. These tests establish
that corrupt metadata is rejected BEFORE that boundary; they are not evidence
of an actual operational require_plan invocation or native execution admission.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SOURCE_HEAD = '0eac156990f5a4ee0084af635eb3089913b437ff'
PREFIX = Path('experiments/sota-2026-10-22')
DIRS = ['candidate/epoch18', 'controller/epoch18', 'legal-transfer/epoch18',
        'audit/epoch18', 'epoch18']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class RootMetadataGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='e18-review-metadata-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.s = self.root / PREFIX
        self.e = self.s / 'epoch18'
        for rel in DIRS:
            (self.s / rel).mkdir(parents=True)
        write(self.base / 'kit/CHECKPOINT_MANIFEST.json', {'project_files': []})

    def module(self, stem):
        m = load('independent_e18_' + stem, HERE / (stem + '.py'))
        m.ROOT, m.S, m.E = self.root, self.s, self.e
        return m

    def row(self, path):
        return {'path': str(path.relative_to(self.root)),
                'bytes': path.stat().st_size, 'sha256': sha(path)}

    def source_handoff(self, reviewed=None):
        checker = self.s / 'audit/epoch18/checker.py'
        checker.write_text('# Generic public checker fixture\n')
        reviewed = reviewed or self.s / 'candidate/epoch18/reader.py'
        if not reviewed.exists():
            reviewed.write_text('# Generic public candidate fixture\n')
        policy = self.s / 'audit/epoch18/acceptance-contract-v1.json'
        write(policy, {'fixture': 'pure metadata'})
        write(self.s / 'audit/epoch18/code-handoff-v1.json', {
            'checks_passed': True, 'source_and_checker_ready_for_prelabel_freeze': True,
            'source_immutable_head': SOURCE_HEAD, 'native_execution_admitted': False,
            'auditor_model_native_fit_paid_GPU_calls': 0, 'new_role_annotation_choices_read': 0,
            'policy_sha256': sha(policy), 'checker_source_and_tests': [self.row(checker)],
            'reviewed_candidate_and_role_sources': [self.row(reviewed)]})

    def assert_source_rejects(self):
        module = self.module('freeze_sources')
        with self.assertRaises((AssertionError, ValueError, PermissionError)):
            with contextlib.redirect_stdout(io.StringIO()):
                module.main()
        self.assertFalse((self.e / 'candidate-source-freeze.json').exists())

    def test_normal_source_freeze_accepts_generic_metadata(self):
        self.source_handoff()
        module = self.module('freeze_sources')
        with contextlib.redirect_stdout(io.StringIO()):
            module.main()
        proof = json.loads((self.e / 'candidate-source-freeze.json').read_text())
        self.assertEqual(proof['source_checkpoint'], SOURCE_HEAD)
        self.assertEqual(proof['new_case_inputs_inspected'], 0)

    def test_source_freeze_rejects_dangling_projection_symlink(self):
        self.source_handoff()
        (self.s / 'legal-transfer/epoch18/development24.jsonl').symlink_to(
            self.base / 'absent-generic-data.jsonl')
        self.assert_source_rejects()

    def test_source_freeze_rejects_ancestor_symlink_in_handoff(self):
        outside = self.base / 'generic-outside'
        outside.mkdir()
        (outside / 'reader.py').write_text('# Generic public source fixture\n')
        target = self.s / 'candidate/epoch18'
        target.rmdir()
        target.symlink_to(outside, target_is_directory=True)
        self.source_handoff(target / 'reader.py')
        self.assert_source_rejects()

    def test_snapshot_rejects_ancestor_symlink(self):
        outside = self.base / 'generic-outside'
        outside.mkdir()
        (outside / 'reader.py').write_text('# Generic public source fixture\n')
        target = self.s / 'candidate/epoch18'
        target.rmdir()
        target.symlink_to(outside, target_is_directory=True)
        write(self.e / 'candidate-source-freeze.json', {
            'source_checkpoint': SOURCE_HEAD, 'files': [self.row(target / 'reader.py')]})
        with self.assertRaises((AssertionError, ValueError, PermissionError)):
            self.module('study_metadata').frozen()

    def final_fixture(self):
        common = self.module('study_metadata')
        old = sys.modules.get('study_metadata')
        sys.modules['study_metadata'] = common
        try:
            final = self.module('freeze_study')
        finally:
            if old is None:
                del sys.modules['study_metadata']
            else:
                sys.modules['study_metadata'] = old
        freeze = self.e / 'candidate-source-freeze.json'
        write(freeze, {'source_checkpoint': SOURCE_HEAD, 'files': []})
        op = self.e / 'operational-plan.json'
        write(op, {'measurement_plan': False, 'operational_prelabel_only': True,
                   'runtime_admission': {}, 'pins': []})
        write(self.s / 'audit/epoch18/prelabel-operational-admission-v1.json', {
            'checks_passed': True, 'actual_full_require_plan_calls': 1,
            'plan_sha256': sha(op), 'source_freeze_sha256': sha(freeze),
            'native_execution_admitted': False})
        builder = self.s / 'legal-transfer/epoch18/build.py'
        builder.write_text('# Generic builder fixture; no corpus access\n')
        selection = self.s / 'legal-transfer/epoch18/document-selection.json'
        write(selection, {'fixture': 'generic identity'})
        data = self.s / 'legal-transfer/epoch18/development24.jsonl'
        data.write_text('Generic fixture bytes, not a benchmark row\n')
        allow = self.s / 'legal-transfer/epoch18/dev-allowlist.json'
        write(allow, {'data_sha256': sha(data), 'records': []})
        receipt = self.s / 'legal-transfer/epoch18/dev-materialization.json'
        write(receipt, {
            'schema_version': 1, 'status': 'FROZEN_DEV24_PROJECTED_ONCE',
            'role': 'dev', 'queries': 24, 'document_groups': 8,
            'data_sha256': sha(data), 'allowlist_sha256': sha(allow),
            'builder_sha256': sha(builder), 'selection_sha256': sha(selection),
            'source_sha256': 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
            'annotation_choices_projected': 24, 'other_role_annotation_choices_accessed': 0,
            'root_source_freeze_sha256': sha(freeze), 'native_model_fit_paid_GPU_calls': 0,
            'old_reserved_CONF48_choices_accessed': 0,
            'CONF_labels_used_for_training_selection': False})
        write(self.s / 'audit/epoch18/context-capacity-independent-v1.json', {
            'checks_passed': True, 'status': 'INDEPENDENT_LABEL_FREE_BOTH_READER_CAPACITY_PASS',
            'model_native_fit_paid_GPU_calls': 0,
            'phases': {'development': {'max_units': 2}, 'confirmation': {'max_units': 3}}})
        return final, data, allow, receipt

    def assert_final_rejects_before_validator(self, corrupt):
        final, data, allow, receipt = self.final_fixture()
        corrupt(data, allow, receipt)
        reached = []

        def boundary(*args):
            reached.append(True)
            raise RuntimeError('SYNTHETIC_VALIDATOR_BOUNDARY_REACHED')

        final.module = boundary
        with self.assertRaises((AssertionError, ValueError, PermissionError)):
            with contextlib.redirect_stdout(io.StringIO()):
                final.main()
        self.assertEqual(reached, [])
        self.assertFalse((self.e / 'plan.json').exists())

    def test_final_freeze_rejects_changed_dev_bytes(self):
        self.assert_final_rejects_before_validator(
            lambda data, allow, receipt: data.write_text('Changed generic fixture bytes\n'))

    def test_final_freeze_rejects_changed_dev_allowlist_bytes(self):
        self.assert_final_rejects_before_validator(
            lambda data, allow, receipt: allow.write_text('{"changed_generic_fixture":true}\n'))

    def test_final_freeze_rejects_internally_inconsistent_data_hash(self):
        def corrupt(data, allow, receipt):
            value = json.loads(allow.read_text())
            value['data_sha256'] = '0' * 64
            write(allow, value)
            value = json.loads(receipt.read_text())
            value['allowlist_sha256'] = sha(allow)
            write(receipt, value)
        self.assert_final_rejects_before_validator(corrupt)

    def test_valid_final_metadata_reaches_only_synthetic_boundary(self):
        final, _, _, _ = self.final_fixture()
        reached = []

        def boundary(*args):
            reached.append(True)
            raise RuntimeError('SYNTHETIC_VALIDATOR_BOUNDARY_REACHED')

        final.module = boundary
        with self.assertRaisesRegex(RuntimeError, '^SYNTHETIC_VALIDATOR_BOUNDARY_REACHED$'):
            with contextlib.redirect_stdout(io.StringIO()):
                final.main()
        self.assertEqual(reached, [True])
        self.assertTrue((self.e / 'plan.json').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
