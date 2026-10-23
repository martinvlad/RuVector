"""Generic admission fault fixtures only; no real corpus, validators or models."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch18_admission_test', HERE / 'admission.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def fixture(root):
    for relative in [a.BUILDER, a.SELF, a.CONTROLLER, a.INHERITED]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Generic source-only fixture.\n')
    freeze_path = root / a.FREEZE
    files = [{'path': relative, 'bytes': (root / relative).stat().st_size,
              'sha256': a.digest(root / relative)} for relative in [a.BUILDER, a.SELF, a.CONTROLLER, a.INHERITED]]
    write(freeze_path, {'files': files})
    frozen_sha = a.digest(freeze_path)
    plan_path = a.PREFIX + 'epoch18/generic-operational-plan.json'
    plan = {'epoch': 18, 'actual_project': str(root), 'train': 'none', 'calibration': 'none',
        'measurement_plan': False, 'operational_prelabel_only': True,
        'limits': {'threads': 2, 'native_batches': 2, 'seconds_per_batch': 600,
                   'seconds_per_decision': 30, 'candidate_configs': 1, 'paid_calls': 0, 'GPU_calls': 0},
        'lazy_confirmation': {'source_freeze_path': a.FREEZE, 'source_freeze_sha256': frozen_sha,
                              'builder_path': a.BUILDER, 'builder_sha256': a.digest(root / a.BUILDER)},
        'pins': [{'path': r['path'], 'sha256': r['sha256']} for r in files]}
    write(root / plan_path, plan)
    receipt = {'checks_passed': True, 'status': 'FULL_UNMOCKED_OPERATIONAL_PRELABEL_ADMISSION_PASS',
        'operational_prelabel_only': True, 'native_execution_admitted': False,
        'actual_full_require_plan_calls': 1, 'original_case_inputs_or_annotation_choices_projected': 0,
        'model_native_fit_paid_GPU_calls': 0, 'source_freeze_path': a.FREEZE,
        'source_freeze_sha256': frozen_sha, 'plan_path': plan_path, 'plan_sha256': a.digest(root / plan_path),
        'controller_source_sha256': a.digest(root / a.CONTROLLER),
        'inherited_verifier_sha256': a.digest(root / a.INHERITED)}
    write(root / a.RECEIPT, receipt)
    return freeze_path, frozen_sha, plan, receipt


class AdmissionTests(unittest.TestCase):
    def test_generic_valid_structure_accepted_without_any_validator_or_case_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            freeze, frozen_sha, _, receipt = fixture(root)
            self.assertEqual(a.verify_operational(root, freeze, frozen_sha)['plan_sha256'], receipt['plan_sha256'])

    def test_missing_receipt_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); freeze, frozen_sha, _, _ = fixture(root)
            (root / a.RECEIPT).unlink()
            with self.assertRaises(PermissionError):
                a.verify_operational(root, freeze, frozen_sha)

    def test_missing_or_incorrect_receipt_flags_fail_closed(self):
        changes = {'checks_passed': False, 'status': 'PREPARED', 'operational_prelabel_only': False,
            'native_execution_admitted': True, 'actual_full_require_plan_calls': 0,
            'original_case_inputs_or_annotation_choices_projected': 1,
            'model_native_fit_paid_GPU_calls': 1, 'source_freeze_path': '../other.json',
            'source_freeze_sha256': '0' * 64, 'plan_sha256': '0' * 64,
            'controller_source_sha256': '0' * 64, 'inherited_verifier_sha256': '0' * 64}
        for key, value in changes.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); freeze, frozen_sha, _, receipt = fixture(root)
                receipt[key] = value; write(root / a.RECEIPT, receipt)
                with self.assertRaises(PermissionError):
                    a.verify_operational(root, freeze, frozen_sha)

    def test_operational_plan_missing_or_inverted_prelabel_flags_fail(self):
        for key, wrong_value in [('measurement_plan', True), ('operational_prelabel_only', False)]:
            for missing in [True, False]:
                with self.subTest(key=key, missing=missing), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp); freeze, frozen_sha, plan, receipt = fixture(root)
                    if missing:
                        del plan[key]
                    else:
                        plan[key] = wrong_value
                    write(root / receipt['plan_path'], plan)
                    receipt['plan_sha256'] = a.digest(root / receipt['plan_path'])
                    write(root / a.RECEIPT, receipt)
                    with self.assertRaises(PermissionError):
                        a.verify_operational(root, freeze, frozen_sha)

    def test_operational_plan_budget_source_or_role_changes_fail(self):
        for kind in ['request60', 'threads3', 'paid1', 'GPU1', 'wrong_project', 'training', 'builder', 'duplicate_pin', 'missing_pin']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); freeze, frozen_sha, plan, receipt = fixture(root)
                if kind == 'request60': plan['limits']['seconds_per_decision'] = 60
                if kind == 'threads3': plan['limits']['threads'] = 3
                if kind == 'paid1': plan['limits']['paid_calls'] = 1
                if kind == 'GPU1': plan['limits']['GPU_calls'] = 1
                if kind == 'wrong_project': plan['actual_project'] = '/different'
                if kind == 'training': plan['train'] = 'some-training'
                if kind == 'builder': plan['lazy_confirmation']['builder_sha256'] = '0' * 64
                if kind == 'duplicate_pin': plan['pins'].append(copy.deepcopy(plan['pins'][0]))
                if kind == 'missing_pin': plan['pins'].pop()
                write(root / receipt['plan_path'], plan)
                receipt['plan_sha256'] = a.digest(root / receipt['plan_path'])
                write(root / a.RECEIPT, receipt)
                with self.assertRaises(PermissionError):
                    a.verify_operational(root, freeze, frozen_sha)

    def test_changed_frozen_member_or_symlink_refused(self):
        for symlink in [False, True]:
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); freeze, frozen_sha, _, _ = fixture(root)
                if symlink:
                    target = root / a.RECEIPT
                    target.rename(root / 'generic-receipt.json')
                    target.symlink_to(root / 'generic-receipt.json')
                else:
                    (root / a.SELF).write_text('Tampered generic fixture.\n')
                with self.assertRaises(PermissionError):
                    a.verify_operational(root, freeze, frozen_sha)


if __name__ == '__main__':
    unittest.main()
