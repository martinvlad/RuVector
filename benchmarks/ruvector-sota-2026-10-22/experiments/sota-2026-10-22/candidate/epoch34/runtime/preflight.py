"""Pure prospective E34 source/admission fixtures; no real ML/native/tokenizer/data."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fails(call):
    try:
        call()
    except (ValueError, RuntimeError, TimeoutError, AssertionError, FileNotFoundError):
        return
    raise AssertionError('Expected closed source/admission refusal')


def source_guards(temp):
    worker = load('e34_metadata_worker', CANDIDATE/'worker.py')
    C = worker.C
    root = temp/'project'
    cand = root/'experiments/sota-2026-10-22/candidate/epoch34'
    study = root/'experiments/sota-2026-10-22/epoch34'
    cand.mkdir(parents=True)
    study.mkdir(parents=True)
    names = ['runtime/common.py','runtime/launch.py','runtime/network_guard.py',
        'runtime/node_guard.cjs','runtime/cpu_guard.py','worker.py','model.py',
        'algorithm.py','evidence.py','context_engine.py','source_context.py','vector_codec.py',
        'native_helper.cjs','proof.py','query.py','QUERY_POLICY.json','PROOF_POLICY.json',
        'PRETRAINED_MODEL_SOURCE.json','research/MODEL_SOURCE_ADMISSION.json','MODEL_ASSETS.json']
    for name in names:
        dst=cand/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((CANDIDATE/name).read_bytes())
    fake_names = ['runtime-assets.json','dev.inputs.json','engineering.inputs.json','engineering.oracle.json']
    for name in fake_names:
        (cand/name).write_text('AUTHORED_METADATA_ONLY_NOT_A_CORPUS_OR_RUNTIME')
    # This is a public policy source body, not a dataset or model asset.
    addendum = root/'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json'
    addendum.parent.mkdir(parents=True)
    real_root = Path('/workspace/ruvector-epoch34-047dbc740dc2/project')
    addendum.write_bytes((real_root/addendum.relative_to(root)).read_bytes())
    C.ROOT,C.CANDIDATE,C.HERE,C.STUDY = root,cand,cand/'runtime',study
    def ref(p):
        b=p.read_bytes()
        return {'path':str(p.relative_to(root)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
    refs=[ref(cand/name) for name in names+fake_names]+[ref(addendum)]
    freeze = study/'source-freeze.json'
    freeze.write_text(json.dumps({'epoch':34,'kind':C.KIND,'source_checkpoint':C.SOURCE,'entries':refs}))
    refs.append(ref(freeze))
    plan={'epoch':34,'kind':C.KIND,'source_checkpoint':C.SOURCE,'actual_project':str(root),
        'guardian_scope':str(C.SCOPE),'external_python_environment':str(C.VENV),
        'model_directory':str(C.MODEL),'data_roles':{'train':[],'dev':C.DEV_IDS,'calibration':[],'confirmation':[]},
        'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],
            'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':0,
            'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},
        'pins':refs,'worker_path':str((cand/'worker.py').relative_to(root)),
        'native_worker_path':str((cand/'native_helper.cjs').relative_to(root)),
        'expected_operation_counters':{'dev':worker.expected_counters(True)},
        'engineering_rejected_operation_counters':{'dev':worker.expected_counters(False)}}
    for key,p in [('source_freeze',freeze),('runtime_assets_lock',cand/'runtime-assets.json'),
            ('model_assets_lock',cand/'MODEL_ASSETS.json'),('pretrained_model_source',cand/'PRETRAINED_MODEL_SOURCE.json'),
            ('engineering_inputs',cand/'engineering.inputs.json'),('engineering_oracle',cand/'engineering.oracle.json'),
            ('dev_inputs',cand/'dev.inputs.json'),('runtime_policy_addendum',addendum),
            ('proof_source',cand/'proof.py'),('proof_policy',cand/'PROOF_POLICY.json'),
            ('query_source',cand/'query.py'),('query_policy',cand/'QUERY_POLICY.json'),('source_context',cand/'source_context.py')]:
        plan[key+'_path'],plan[key+'_sha256']=str(p.relative_to(root)),ref(p)['sha256']
    plan['pretrained_model_source']=ref(cand/'PRETRAINED_MODEL_SOURCE.json')
    planfile=study/'plan.json'
    def write_plan(v):
        planfile.write_text(json.dumps(v));return ref(planfile)['sha256']
    plansha=write_plan(plan)
    original_sha=C.sha
    dev=cand/'dev.inputs.json'
    def sha_no_DEV(p):
        if Path(p)==dev:raise AssertionError('DEV content opened before engineering gate')
        return original_sha(p)
    C.sha=sha_no_DEV
    C.verify_plan(planfile,plansha,'dev')
    for change in [lambda p:p['data_roles']['dev'].reverse(),
                   lambda p:p['limits'].__setitem__('CPU_threads',3),
                   lambda p:p.__setitem__('source_checkpoint','0'*40),
                   lambda p:p.__setitem__('source_context_sha256','0'*64),
                   lambda p:p.__setitem__('query_policy_sha256','0'*64),
                   lambda p:p.__setitem__('proof_policy_sha256','0'*64)]:
        bad=copy.deepcopy(plan);change(bad);badsha=write_plan(bad)
        fails(lambda:C.verify_plan(planfile,badsha,'dev'))
    plansha=write_plan(plan)
    C.owner_lock=lambda *args:{'EXPLICIT_AUTHOR_TEST_MOCK':True}
    admission={'epoch':34,'kind':C.KIND,'phase':'dev','scope':'benchmarks/ruvector-sota-2026-10-22/',
        'verified_actual_remote_readback':True,'plan_sha256':plansha,
        'source_freeze_sha256':plan['source_freeze_sha256'],'published_source_commit':'a'*40,
        'pretrained_model_source':plan['pretrained_model_source'],'model_assets_lock_sha256':plan['model_assets_lock_sha256']}
    ap=study/'SOURCE_ADMISSION.json';ap.write_text(json.dumps(admission));C.admission(ap,plan,plansha,'dev')
    for key,value in [('verified_actual_remote_readback',False),('plan_sha256','0'*64),('model_assets_lock_sha256','0'*64)]:
        ap.write_text(json.dumps({**admission,key:value}));fails(lambda:C.admission(ap,plan,plansha,'dev'))
    ap.write_text(json.dumps(admission))
    claim={'schema_version':1,'epoch':34,'kind':C.KIND,'phase':'dev','plan_sha256':plansha,
        'source_freeze_sha256':plan['source_freeze_sha256'],'pretrained_model_source_sha256':plan['pretrained_model_source_sha256'],
        'model_assets_lock_sha256':plan['model_assets_lock_sha256'],'admission_sha256':C.sha(ap),
        'kernel_boot_id':C.BOOT_ID,'pid_namespace_inode':C.PIDNS_INODE,
        'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time(),
        'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
    cp=study/'DISPATCH_RESERVATION.json';cp.write_text(json.dumps(claim))
    attempt={**claim,'pid':os.getpid(),'startticks':123,'pgid':os.getpid(),'sid':os.getpid(),
        'verified_launcher_start':True,'uncertain_launcher_start':False}
    C.proc=lambda pid:{'pid':pid,'ticks':123,'pgid':pid,'sid':pid}
    dp=study/'DISPATCH_ATTEMPT.json';dp.write_text(json.dumps(attempt));C.dispatch_proof(plan,plansha,ap,0)
    for key,value in [('startticks',124),('uncertain_launcher_start',True),('pgid',0),('sid',0)]:
        dp.write_text(json.dumps({**attempt,key:value}));fails(lambda:C.dispatch_proof(plan,plansha,ap,0))
    dp.unlink();fails(lambda:C.dispatch_proof(plan,plansha,ap,0))
    return ['source_plan_exact_roles_CPU2_context_query_proof_hash_binding_and_DEV_body_deferred',
        'SOURCE_actual_readback_plan_model_binding_false_or_changed_refusal',
        'one_shot_dispatch_exact_PID_ticks_PGID_SID_uncertainty_and_missing_receipt_refusal']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    checks=[]
    for p in CANDIDATE.rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
    for p in CANDIDATE.rglob('*.cjs'):subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
    checks.append('Python_AST_and_Node_syntax_all_current_candidate_sources')
    with tempfile.TemporaryDirectory(prefix='e34-authored-source-fixtures-',dir=args.output.parent) as t:
        checks.extend(source_guards(Path(t)))
    assert not any(name in sys.modules for name in ('torch','transformers','numpy','onnxruntime','tokenizers'))
    result={'schema_version':1,'epoch':34,'passed':True,'checks':checks,
        'actual_model_native_tokenizer_or_benchmark_gold_calls':0,'real_observer_invocations':0,
        'real_dispatches':0,'scope':'Authored metadata and exact public source only; mocked source/admission/PID receipts. No actual corpus/model/runtime execution.'}
    with args.output.open('x')as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(result))


if __name__=='__main__':main()
