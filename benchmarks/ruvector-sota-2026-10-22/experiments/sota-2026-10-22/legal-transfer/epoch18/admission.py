"""Fail-closed pre-input operational admission; no corpus or model imports."""
from pathlib import Path, PurePosixPath
import hashlib
import json

PREFIX = 'experiments/sota-2026-10-22/'
RECEIPT = PREFIX + 'audit/epoch18/prelabel-operational-admission-v1.json'
FREEZE = PREFIX + 'epoch18/candidate-source-freeze.json'
CONTROLLER = PREFIX + 'controller/epoch18/loop.py'
INHERITED = PREFIX + 'controller/epoch3_loop.py'
BUILDER = PREFIX + 'legal-transfer/epoch18/build.py'
SELF = PREFIX + 'legal-transfer/epoch18/admission.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(root, relative):
    if (not isinstance(relative, str) or PurePosixPath(relative).is_absolute()
            or '\\' in relative or any(x in ('', '.', '..') for x in relative.split('/'))):
        raise PermissionError('Unsafe operational admission reference')
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise PermissionError('Operational admission escapes isolated project')
    for member in [path, *path.parents]:
        if member == root.parent:
            break
        if member.is_symlink():
            raise PermissionError('Operational admission symlink refused')
    if not path.is_file():
        raise PermissionError('Missing operational admission reference: ' + relative)
    return path


def verify_operational(project, freeze_path, expected_freeze_sha):
    if project is None or freeze_path is None:
        raise PermissionError('Operational PASS and source freeze required before inputs or choices')
    root = Path(project).resolve()
    fixed_freeze = checked(root, FREEZE)
    if Path(freeze_path).resolve() != fixed_freeze.resolve() or digest(fixed_freeze) != expected_freeze_sha:
        raise PermissionError('Operational source freeze identity changed')
    receipt = json.loads(checked(root, RECEIPT).read_text())
    if (receipt.get('checks_passed') is not True
            or receipt.get('status') != 'FULL_UNMOCKED_OPERATIONAL_PRELABEL_ADMISSION_PASS'
            or receipt.get('operational_prelabel_only') is not True
            or receipt.get('native_execution_admitted') is not False
            or receipt.get('actual_full_require_plan_calls') != 1
            or receipt.get('original_case_inputs_or_annotation_choices_projected') != 0
            or receipt.get('model_native_fit_paid_GPU_calls') != 0
            or receipt.get('source_freeze_path') != FREEZE
            or receipt.get('source_freeze_sha256') != expected_freeze_sha):
        raise PermissionError('Exact prelabel operational PASS required before corpus/input/choice projection')
    plan_path = receipt.get('plan_path')
    if not isinstance(plan_path, str) or not plan_path.startswith(PREFIX + 'epoch18/'):
        raise PermissionError('Operational plan must belong to the isolated epoch18 study')
    plan_file = checked(root, plan_path)
    if digest(plan_file) != receipt.get('plan_sha256'):
        raise PermissionError('Operational plan bytes changed')
    plan = json.loads(plan_file.read_text())
    if (plan.get('epoch') != 18 or plan.get('actual_project') != str(root)
            or plan.get('train') != 'none' or plan.get('calibration') != 'none'
            or plan.get('measurement_plan') is not False
            or plan.get('operational_prelabel_only') is not True):
        raise PermissionError('Operational study roles or isolated project changed')
    limits = plan['limits']
    required = {'threads': 2, 'native_batches': 2, 'seconds_per_batch': 600,
                'seconds_per_decision': 30, 'candidate_configs': 1, 'paid_calls': 0, 'GPU_calls': 0}
    if any(type(limits.get(key)) is not int or limits[key] != value for key, value in required.items()):
        raise PermissionError('Operational inherited-compatible CPU2/30request/600batch/paid0 policy changed')
    lazy = plan['lazy_confirmation']
    if (lazy['source_freeze_path'] != FREEZE or lazy['source_freeze_sha256'] != expected_freeze_sha
            or lazy['builder_path'] != BUILDER or lazy['builder_sha256'] != digest(checked(root, BUILDER))):
        raise PermissionError('Operational plan does not bind current builder and source freeze')
    for key, relative in [('controller_source_sha256', CONTROLLER), ('inherited_verifier_sha256', INHERITED)]:
        if receipt.get(key) != digest(checked(root, relative)):
            raise PermissionError('Actual operational validator bytes changed')
    pins = {}
    for row in plan['pins']:
        if row['path'] in pins:
            raise PermissionError('Duplicate operational source pin')
        pins[row['path']] = row['sha256']
    for relative in [BUILDER, SELF, CONTROLLER, INHERITED]:
        if pins.get(relative) != digest(checked(root, relative)):
            raise PermissionError('Operational plan source snapshot changed: ' + relative)
    freeze = json.loads(fixed_freeze.read_text())
    for row in freeze['files']:
        member = checked(root, row['path'])
        if member.stat().st_size != row['bytes'] or digest(member) != row['sha256']:
            raise PermissionError('Operational source-freeze member changed: ' + row['path'])
    return {'plan_sha256': receipt['plan_sha256'], 'source_freeze_sha256': expected_freeze_sha,
            'receipt_sha256': digest(checked(root, RECEIPT))}
