"""Root-only once-bound stdlib asset hash admission; never initializes ML/native.

Run only inside an independently reviewed root outer bound:175work+5cleanup.
The returned combined receipt preserves every actual nine-payload/runtime hash.
Inference SOURCE remains disabled. A consumed/uncertain marker forbids replay.
"""
import time
INVOCATION_MONOTONIC=time.monotonic()
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import sys
import traceback

W=Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b')
R=W/'project'
E=R/'experiments/sota-2026-10-22/epoch42'
SOURCE='222874558c0b696f92824e5fce3775494877f821'
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
OWNER_SHA='a5723c70ca695c14212083ba4123d1a26ca4835ffe76833e63a9ef2d2bb36e62'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for part in iter(lambda:stream.read(1048576),b''):digest.update(part)
    return digest.hexdigest()


def regular(path):
    path=Path(path)
    if any(p.is_symlink()for p in(path,*path.parents))or not path.is_file():raise ValueError('REGULAR_NONSYMLINK_SOURCE_REQUIRED')
    return path


def put(path,value):
    path=Path(path)
    if any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('SYMLINK_CAPTURE_REFUSED')
    with path.open('x',encoding='utf-8')as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--expected-plan-sha',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}',args.expected_plan_sha):raise ValueError('EXACT_PLAN_SHA_REQUIRED')
    if Path(__file__).absolute()!=E/'preparation/asset_preflight.py':raise ValueError('RUN_ONLY_CANONICAL_REVIEWED_SOURCE')
    if args.plan.absolute()!=E/'preparation/ASSET_PREFLIGHT_PLAN.v2.json'or sha(regular(args.plan))!=args.expected_plan_sha:
        raise ValueError('EXACT_BOUND_PREFLIGHT_PLAN_REQUIRED')
    plan=json.loads(args.plan.read_text())
    if (plan.get('epoch')!=42 or plan.get('kind')!=KIND or plan.get('source_checkpoint')!=SOURCE
        or plan.get('function')!='C.verify_runtime'or plan.get('max_total_seconds')!=180
        or plan.get('root_outer_work_seconds')!=175 or plan.get('owned_cleanup_seconds')!=5
        or plan.get('CPU_threads')!=2 or plan.get('CPU_affinity')!=[0,1]
        or plan.get('paid_calls')!=0 or plan.get('GPU_calls')!=0 or plan.get('network_calls')!=0
        or plan.get('function_calls')!=1 or plan.get('retries')!=0):raise ValueError('EXACT_ZERO_ML_BOUNDED_SCOPE_REQUIRED')
    if plan.get('root_outer_bound_required')is not True:raise ValueError('REVIEWED_ROOT_OUTER_BOUND_REQUIRED')
    pins=plan.get('source_files');seen=set()
    if not isinstance(pins,list)or not pins:raise ValueError('EXACT_SOURCE_PINS_REQUIRED')
    for row in pins:
        rel=row['path']
        if (not isinstance(rel,str)or Path(rel).is_absolute()or any(p in('','.','..')for p in rel.split('/'))
            or rel in seen):raise ValueError('INVALID_OR_DUPLICATE_SOURCE_PIN')
        seen.add(rel);path=regular(R/rel)
        if path.stat().st_size!=row['bytes']or sha(path)!=row['sha256']:raise ValueError('PREFLIGHT_SOURCE_BYTES_CHANGED')
    own='experiments/sota-2026-10-22/epoch42/preparation/asset_preflight.py'
    common='experiments/sota-2026-10-22/candidate/epoch42/runtime/common.py'
    if own not in seen or common not in seen:raise ValueError('PREFLIGHT_ENTRY_AND_COMMON_MUST_BE_PINNED')
    if sha(regular(W/'owner.json'))!=OWNER_SHA or plan.get('owner_sha256')!=OWNER_SHA:raise ValueError('EXACT_CURRENT_OWNER_REQUIRED')
    spec=importlib.util.spec_from_file_location('e42_preflight_stdlib_common',R/common)
    C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
    if C.SOURCE_BINDINGS_READY is not False or C.ASSET_PREFLIGHT_BINDINGS_READY is not True:
        raise ValueError('ASSET_ONLY_BINDINGS_REQUIRED_INFERENCE_MUST_STAY_DISABLED')
    if C.OWNER_EXPIRY-time.time()<185:raise ValueError('INSUFFICIENT_OWNER_LEASE_FOR_FULL_BOUND')
    C.owner_lock();os.sched_setaffinity(0,{0,1})
    if sorted(os.sched_getaffinity(0))!=[0,1]:raise ValueError('CPU_AFFINITY_REQUIRED')
    attempt=W/'ASSET_PREFLIGHT_ATTEMPT.json';result=W/'ASSET_PREFLIGHT_RESULT.json'
    error_path=W/'asset-preflight-exact-error.txt'
    if any(p.exists()or p.is_symlink()for p in(attempt,result,error_path)):
        raise ValueError('EXISTING_CONSUMED_OR_UNCERTAIN_PREFLIGHT_NO_RETRY')
    put(attempt,{'schema_version':1,'epoch':42,'kind':KIND,'source_checkpoint':SOURCE,
        'plan_sha256':args.expected_plan_sha,'function':'C.verify_runtime','calls_reserved':1,
        'before_function_call':True,'automatic_retry':False,'at_unix':time.time()})
    captured={'schema_version':1,'epoch':42,'kind':KIND,'source_checkpoint':SOURCE,
        'status':'INITIALIZING','plan_sha256':args.expected_plan_sha,'function':'C.verify_runtime',
        'function_calls_attempted':0,'function_calls_completed':0,'result':None,'errors':[],
        'model_tokenizer_native_initializations_or_calls':0,'case_oracle_reads':0,'paid_calls':0,'GPU_calls':0,
        'stubs_used':False,'monkeypatches':[],'CPU_affinity':[0,1],
        'wall_scope':'Innerelapsed before result capture; independent root outer must retain actual full initialization/capture/cleanup wall<=180. Not NLI/publisher latency.'}
    def bounded(signum,frame):raise TimeoutError('BOUNDED_ASSET_PREFLIGHT_STOP')
    code=0
    try:
        signal.signal(signal.SIGALRM,bounded);signal.signal(signal.SIGTERM,bounded)
        signal.setitimer(signal.ITIMER_REAL,max(.001,INVOCATION_MONOTONIC+175-time.monotonic()))
        captured['function_calls_attempted']=1
        captured['result']=C.verify_runtime(plan['runtime_request'])
        captured['function_calls_completed']=1;C.owner_lock()
        captured['status']='FRESH_NINE_MODEL_FULL_RUNTIME_ASSETS_PASSED_NO_ML'
    except BaseException as error:
        code=2;captured['status']='FAILED_ASSET_PREFLIGHT_NO_ML'
        captured['errors'].append({'type':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()})
        with error_path.open('x',encoding='utf-8')as stream:
            stream.write(traceback.format_exc());stream.flush();os.fsync(stream.fileno())
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        captured['wall_seconds_before_result_capture']=time.monotonic()-INVOCATION_MONOTONIC
        put(result,captured)
    return code


if __name__=='__main__':raise SystemExit(main())
