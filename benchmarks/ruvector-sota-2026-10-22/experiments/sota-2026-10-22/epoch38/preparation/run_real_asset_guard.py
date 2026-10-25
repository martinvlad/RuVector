from pathlib import Path
import sys
sys.dont_write_bytecode=True
import hashlib,importlib.util,json,os,time
W=Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f');R=W/'project';P='experiments/sota-2026-10-22/';D=R/(P+'epoch38/preparation')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ref(name):
 p=R/name;assert p.is_file()and not any(x.is_symlink()for x in(p,*p.parents))
 return{'path':name,'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
assert Path(sys.prefix)==Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
assert os.sched_getaffinity(0)=={0,1}
ready=json.loads((D/'guard-source-review/GUARD_SOURCE_READY.v1.json').read_text());pins=list(ready['entries'])
for row in pins:assert ref(row['path'])==row
lock=ref(P+'candidate/epoch38/MODEL_ASSETS.json');assert lock['sha256']=='652e603534a5c526d1c53e734d040caa791eccaf4fb4397728871342b7906bcb';pins.append(lock)
by={r['path']:r for r in pins};common=by[P+'candidate/epoch38/runtime/common.py'];validator=by[P+'candidate/epoch38/runtime/model_assets_guard.py'];expected=by[P+'candidate/epoch38/MODEL_ASSETS.expected.json'];helper=by[P+'candidate/epoch38/asset_identity.py']
plan={'epoch':38,'kind':'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES','source_checkpoint':'7c50ba99848f6a13707eeec6c4947291a8478e5c',
 'model_directory':'/workspace/ruvector-e38-reader-assets/ms-xxlarge-8f8b43dd','pins':pins,
 'model_assets_lock':lock,'model_assets_lock_path':lock['path'],'model_assets_lock_sha256':lock['sha256'],
 'model_assets_expected':expected,'model_assets_expected_path':expected['path'],'model_assets_expected_sha256':expected['sha256'],
 'model_assets_validator':validator,'model_assets_validator_path':validator['path'],'model_assets_validator_sha256':validator['sha256']}
invocation={'source_checkpoint':plan['source_checkpoint'],'runner_source':ref(Path(__file__).relative_to(R).as_posix()),'argv':sys.orig_argv,
 'minimal_plan':plan,'function':'C.verify_model_assets','function_calls_reserved':1,'automatic_retry':False,'stubs_used':False,
 'monkeypatches':[],'ML_tokenizer_native_or_case_calls':0,'started_at_unix':time.time()}
put(W/'FULL_REAL_ASSET_GUARD_INVOCATION.json',invocation)
spec=importlib.util.spec_from_file_location('e38_actual_stdlib_asset_guard_common',R/common['path']);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
C.owner_lock()
started=time.perf_counter()
result=C.verify_model_assets(plan)
seconds=time.perf_counter()-started
for row in pins:assert ref(row['path'])==row
envelope={'schema_version':1,'epoch':38,'source_checkpoint':plan['source_checkpoint'],'status':'PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE',
 'function':'C.verify_model_assets','function_calls':1,'common_source':common,'validator_source':validator,'identity_helper_source':helper,
 'expected_catalog':expected,'public_model_assets_lock':lock,'stubs_used':False,'monkeypatches':[],
 'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,'result':result}
dest=D/'model-assets-guard-admission.json';put(dest,envelope)
put(D/'model-assets-guard-runner-proof.json',{'schema_version':1,'epoch':38,'status':'ACTUAL_SHARED_GUARD_COMPLETED','runner_source':invocation['runner_source'],
 'argv':sys.orig_argv,'function_calls':1,'automatic_retry':False,'stubs_used':False,'monkeypatches':[],
 'started_at_unix':invocation['started_at_unix'],'guard_seconds':seconds,'admission':ref(dest.relative_to(R).as_posix()),
 'source_five_pins_before_and_after_unchanged':True,'ML_tokenizer_native_case_calls':0})
print(json.dumps({'status':envelope['status'],'admission':ref(dest.relative_to(R).as_posix()),'guard_seconds':seconds,'function_calls':1,
 'real_result_status':result['xxlarge']['status'],'actual_model_native_tokenizer_calls':0}))
