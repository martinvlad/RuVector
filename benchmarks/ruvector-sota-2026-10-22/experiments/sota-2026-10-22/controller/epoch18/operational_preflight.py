"""Run the full real controller/legacy validator before any epoch18 projection.

Pure source and operational metadata only. This never launches or imports a
candidate model, and its provisional plan cannot reserve a measurement process.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
_spec = importlib.util.spec_from_file_location('epoch18_operational_proof_helpers',HERE/'admission.py')
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)


def verify(root, plan_path, snapshot_path, snapshot_sha, expected_plan_sha=None):
    root = Path(root).absolute()
    if root!=ROOT:raise ValueError('Use only this reconstructed isolated project')
    A.assert_unprojected(root)
    freeze_rel, freeze = A.source_snapshot(root,snapshot_path,snapshot_sha)
    plan_rel = A.relative(root,plan_path); file = A.checked(root,plan_rel)
    actual_plan_sha = A.sha(file)
    if expected_plan_sha and expected_plan_sha!=actual_plan_sha:
        raise ValueError('Operational plan changed before prelabel admission')
    plan = json.loads(file.read_text())
    if (plan.get('measurement_plan') is not False
            or plan.get('operational_prelabel_only') is not True
            or plan.get('actual_project')!=str(root)):
        raise ValueError('Explicit nonmeasurement prelabel operational plan required')
    recipe = plan['lazy_confirmation']
    if (recipe['source_freeze_path']!=freeze_rel or recipe['source_freeze_sha256']!=snapshot_sha):
        raise ValueError('Operational lazy recipe does not bind actual source freeze')
    capacity = plan['runtime_admission']
    if (capacity.get('capacity_pending_label_free_inputs') is not True
            or capacity['max_DEV_units']!=1 or capacity['max_confirmation_units']!=1):
        raise ValueError('Label-free capacity is pending; explicit positive1 placeholders required')
    pins = {r['path']:r['sha256'] for r in plan['pins']}
    if len(pins)!=len(plan['pins']) or pins.get(freeze_rel)!=snapshot_sha:
        raise ValueError('Unique operational pins must include the actual source freeze')
    for row in freeze['files']:
        if pins.get(row['path'])!=row['sha256']:
            raise ValueError('Actual prelabel frozen source is missing from operational pins: '+row['path'])
    for pin in plan['pins']:A.checked(root,pin['path'])
    before = A.sha(HERE/'loop.py')
    spec = importlib.util.spec_from_file_location('epoch18_actual_operational_controller',HERE/'loop.py')
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    # Exactly one real call. T.verify_plan is neither patched nor substituted.
    accepted = controller.require_plan(file,actual_plan_sha)
    if accepted!=plan:raise ValueError('Full unchanged controller returned a different plan')
    if A.sha(HERE/'loop.py')!=before:raise ValueError('Controller changed during operational validation')
    A.assert_unprojected(root)
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),
            'checks_passed':True,'status':A.STATUS,'operational_prelabel_only':True,
            'native_execution_admitted':False,'plan_path':plan_rel,'plan_sha256':actual_plan_sha,
            'source_freeze_path':freeze_rel,'source_freeze_sha256':snapshot_sha,
            'controller_source_sha256':before,
            'inherited_verifier_sha256':A.sha(A.checked(root,A.PREFIX+'controller/epoch3_loop.py')),
            'operational_contract_sha256':A.operational_contract(plan),
            'actual_full_require_plan_calls':1,
            'source_snapshot_members_verified':len(freeze['files']),
            'source_pins_verified_by_full_inherited_chain':len(plan['pins']),
            'capacity_placeholder_scope':'1/1 operational metadata only, not measured source capacity or runtime.',
            'original_case_inputs_or_annotation_choices_projected':0,
            'model_native_fit_paid_GPU_calls':0,
            'scope':'Real full selected controller and unchanged inherited verifier on intended30s operational metadata before any current18 input/gold. No candidate runtime/model imports, benchmark execution, accuracy, resource compatibility or native admission.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--source-freeze',type=Path,required=True)
    parser.add_argument('--expected-sha',required=True,help='Actual source freeze SHA256')
    parser.add_argument('--expected-plan-sha')
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    root = args.project.absolute(); out = args.out.absolute()
    if root!=ROOT or out!=root/A.RECEIPT:
        raise ValueError('Exact current project and audit-owned prelabel receipt output required')
    if out.exists() or out.is_symlink():raise FileExistsError('Preserve prior admission receipt; do not rerun')
    result = verify(root,args.plan,args.source_freeze,args.expected_sha,args.expected_plan_sha)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x')as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'checks_passed':result['checks_passed'],'status':result['status'],
                      'sha256':A.sha(out),'native_execution_admitted':False,
                      'actual_full_require_plan_calls':1,'new_input_or_choice_projections':0,
                      'model_native_fit_paid_GPU_calls':0}))


if __name__=='__main__':main()
