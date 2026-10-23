"""Future engineering only: immutable17 failure and ONE nonactive shadow check.

No original cases/choices, scoring, model/native imports, source repair or actual
admission. The copied shadow plan lives outside the projected project. Its sole
60->30 edit is hypothetical and cannot authorize the frozen epoch17 controller.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.util
import json

ACTIVE_PLAN_SHA = '9b2d0bb2460b8c44f71e7d82bf185d543c0862ebbac98aac7ff21a6af7499973'
FAILURE_SHA = '948a2fb28aaaa77c92dfd867414444d2ca7dee426f424725b89a8c2f35cc4556'


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--shadow-outside-project', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    shadow = args.shadow_outside_project.absolute()
    assert not shadow.resolve().is_relative_to(project)
    assert not shadow.exists() and not args.report.exists()
    study = project/'experiments/sota-2026-10-22'
    active = study/'epoch17/plan.json'
    failed = study/'audit/epoch17/premeasurement-plan-independent-v1.json'
    assert digest(active) == ACTIVE_PLAN_SHA and digest(failed) == FAILURE_SHA
    failure = json.loads(failed.read_text())
    assert failure['checks_passed'] is False and failure['native_execution_admitted'] is False
    assert failure['actual_exception'] == 'ValueError: Execution limit invalid: seconds_per_decision'
    original = json.loads(active.read_text())
    assert original['limits']['seconds_per_decision'] == 60
    hypothetical = copy.deepcopy(original)
    hypothetical['limits']['seconds_per_decision'] = 30
    undo = copy.deepcopy(hypothetical); undo['limits']['seconds_per_decision'] = 60
    assert undo == original, 'No source/data/model/scorer/gate identity change permitted'
    raw = (json.dumps(hypothetical,indent=2)+'\n').encode()
    with shadow.open('xb') as output: output.write(raw)
    controller = study/'controller/epoch17/loop.py'
    spec = importlib.util.spec_from_file_location('future_only17_admission_shadow',controller)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # This is the sole shadow require_plan call. It imports only source helpers
    # and checks hashes/metadata. Never call worker/parent/run_phase/CandidateEngine.
    outcome = None
    try:
        value = module.require_plan(shadow,digest(shadow))
        assert value == hypothetical
        outcome = {'passed_full_unchanged_require_plan':True,'exception':None}
    except Exception as error:
        outcome = {'passed_full_unchanged_require_plan':False,
                   'exception':type(error).__name__+': '+str(error)}
    assert digest(active) == ACTIVE_PLAN_SHA and digest(failed) == FAILURE_SHA
    assert not (study/'epoch17/launch.json').exists() and not (study/'epoch17/runs').exists()
    result = {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),
        'status':'HYPOTHETICAL_NONACTIVE_SOURCE_ONLY_ADMISSION_DIAGNOSTIC',
        'active17_native_execution_admitted':False,'active17_model_results':None,
        'active17_original_plan_sha256':ACTIVE_PLAN_SHA,'active17_preserved_failure_sha256':FAILURE_SHA,
        'sole_shadow_change':{'path':'limits.seconds_per_decision','old':60,'new':30},
        'shadow_plan_sha256':digest(shadow),'shadow_plan_outside_project':True,
        'actual_shadow_full_require_plan_invocations':1,'shadow_outcome':outcome,
        'interpretation':'Passing shadow checks isolates this metadata obstruction only. It does not repair/admit active17, establish model/runtime compatibility, relax policy, measure accuracy or authorize a future process.',
        'future_required_order':['Freeze intended actual budget/model/reader/scorer/source policy before any new data projection',
            'Run full unchanged dependency chain of require_plan against intended final policy and valid source-only pins; never mock inherited verify_plan',
            'Persist fail-closed outcome and exact source/plan hashes; block input/choice projection on any failure',
            'After label-free capacity, bind final counts/data identities and revalidate exact final plan before native admission',
            'Publish source/readback/exclusivelease gates remain independently required'],
        'original_case_or_annotation_choices_parsed':0,'model_native_fit_paid_GPU_calls':0,
        'active_source_plan_policy_checker_bytes_mutated':0,'actual_native_attempts':0,
        'engineering_fixture_not_benchmark_generalization':True}
    with args.report.open('x') as output: json.dump(result,output,indent=2);output.write('\n')
    print(json.dumps({'report_sha256':digest(args.report),'shadow_outcome':outcome,
                      'active17_native_admitted':False,'model_native_fit_paid_GPU_calls':0}))


if __name__ == '__main__': main()
