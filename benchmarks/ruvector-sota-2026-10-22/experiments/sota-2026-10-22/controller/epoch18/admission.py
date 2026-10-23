"""Source-only prelabel proof and fail-closed final measurement admission."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath

STATUS = 'FULL_UNMOCKED_OPERATIONAL_PRELABEL_ADMISSION_PASS'
PREFIX = 'experiments/sota-2026-10-22/'
RECEIPT = PREFIX+'audit/epoch18/prelabel-operational-admission-v1.json'
SOURCE_HEAD = '0eac156990f5a4ee0084af635eb3089913b437ff'
PROJECTION_NAMES = (
    'development24.jsonl', 'confirmation24.jsonl', 'dev-materialization.json',
    'confirmation-materialization.json', 'dev-inputs-only.json', 'confirmation-inputs-only.json',
    'pre-gold-input-validation.json', 'dev-pre-gold-validation.json',
    'confirmation-pre-gold-validation.json', 'dev-input-allowlist.json',
    'confirmation-input-allowlist.json', 'dev-allowlist.json', 'confirmation-allowlist.json')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def checked(root, relative):
    root = Path(root).absolute()
    if (not isinstance(relative,str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(x in ('','.','..') for x in relative.split('/'))):
        raise ValueError('Unsafe source/proof relative path')
    p = root.joinpath(*PurePosixPath(relative).parts)
    for q in (p,*p.parents):
        if q.is_symlink():raise ValueError('Symlink proof/source refused')
        if q == root:break
    if not p.is_file():raise ValueError('Missing regular source/proof: '+relative)
    return p


def relative(root, path):
    path = Path(path).absolute()
    try:value = path.relative_to(Path(root).absolute()).as_posix()
    except ValueError as e:raise ValueError('Source/proof path escapes isolated project')from e
    checked(root,value)
    return value


def assert_unprojected(root):
    root = Path(root); data = root/PREFIX/'legal-transfer/epoch18'; epoch = root/PREFIX/'epoch18'
    if any((data/name).exists() or (data/name).is_symlink() for name in PROJECTION_NAMES):
        raise ValueError('Epoch18 input/choice projection preceded operational admission')
    if any((epoch/name).exists() or (epoch/name).is_symlink() for name in
           ('launch.json','runs','confirmation-selection-lock.json')):
        raise ValueError('Epoch18 native reservation preceded operational admission')


def source_snapshot(root, path, expected):
    rel = relative(root,path); p = checked(root,rel)
    if not isinstance(expected,str) or len(expected)!=64 or sha(p)!=expected:
        raise ValueError('Exact actual source snapshot hash required')
    value = json.loads(p.read_text())
    if value.get('source_checkpoint')!=SOURCE_HEAD or not value.get('files'):
        raise ValueError('Actual current checkpoint source snapshot required')
    seen = set()
    for row in value['files']:
        if row['path'] in seen:raise ValueError('Duplicate source snapshot member')
        seen.add(row['path']); file = checked(root,row['path'])
        if file.stat().st_size!=row['bytes'] or sha(file)!=row['sha256']:
            raise ValueError('Source snapshot member changed: '+row['path'])
    required = {PREFIX+'controller/epoch18/'+name for name in
                ('loop.py','receipts.py','scoring.py','admission.py','operational_preflight.py')}
    if not required <= seen:raise ValueError('Complete actual controller must be source-frozen')
    return rel,value


def operational_contract(plan):
    """Fields fixed before input/gold; final capacities/data-artifact pins differ."""
    keys = ('schema_version','epoch','controller_version','revision','study_id','limits',
            'train','calibration','datasets','lazy_confirmation','expected_native_receipt',
            'expected_nli_revision','expected_nli_sha256','expected_new_reader_receipt',
            'expected_previous_reader_receipt','binary_probability_policy','actual_project',
            'lease_expires_unix','candidate_manifest_sha256','research_plan_sha256',
            'acceptance_contract','inference_python',
            'prior_closed_study_native_attempts','new_study_native_attempt_cap',
            'new_study_native_attempts_before','prior_closed_epoch17_native_attempts')
    value = {k:plan[k] for k in keys}
    value['runtime_formula_id'] = plan['runtime_admission']['formula_id']
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                    ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def verify_measurement_plan(plan, root, controller_path):
    if (plan.get('measurement_plan') is not True
            or plan.get('operational_prelabel_only') is not False
            or plan['runtime_admission'].get('capacity_pending_label_free_inputs') is not False):
        raise ValueError('Only the final measured-capacity plan may reserve a native process')
    ref = plan.get('prelabel_operational_admission',{})
    if ref.get('path')!=RECEIPT:
        raise ValueError('Exact prelabel operational admission receipt required')
    file = checked(root,RECEIPT)
    pins = {r['path']:r['sha256'] for r in plan['pins']}
    if len(pins)!=len(plan['pins']):raise ValueError('Duplicate plan pin path')
    if sha(file)!=ref.get('sha256') or pins.get(RECEIPT)!=ref['sha256']:
        raise ValueError('Prelabel admission receipt not exact and frozen')
    receipt = json.loads(file.read_text())
    expected = {'checks_passed':True,'status':STATUS,'operational_prelabel_only':True,
                'native_execution_admitted':False,'actual_full_require_plan_calls':1,
                'original_case_inputs_or_annotation_choices_projected':0,
                'model_native_fit_paid_GPU_calls':0}
    if any(receipt.get(k)!=v for k,v in expected.items()):
        raise ValueError('Full unmocked prelabel operational admission did not pass')
    if (receipt.get('source_freeze_path')!=plan['lazy_confirmation']['source_freeze_path']
            or receipt.get('source_freeze_sha256')!=plan['lazy_confirmation']['source_freeze_sha256']
            or receipt.get('controller_source_sha256')!=sha(controller_path)
            or receipt.get('inherited_verifier_sha256')!=sha(checked(root,PREFIX+'controller/epoch3_loop.py'))
            or receipt.get('operational_contract_sha256')!=operational_contract(plan)):
        raise ValueError('Operational source/study/budget contract drifted after prelabel admission')
    op_path = receipt['plan_path']; op_file = checked(root,op_path)
    if sha(op_file)!=receipt['plan_sha256'] or pins.get(op_path)!=receipt['plan_sha256']:
        raise ValueError('Exact operational plan is not frozen in final plan')
    return receipt
