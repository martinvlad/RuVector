"""Standard-library-only E41 source, lock, external-IO and runtime admission."""
from pathlib import Path,PurePosixPath
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import stat
import sys
import time
HERE=Path(__file__).resolve().parent
CANDIDATE=HERE.parent
ROOT=HERE.parents[4]
SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch41-7a40daab6ad7')
STUDY=ROOT/'experiments/sota-2026-10-22/epoch41'
VENV=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
SOURCE='7a40daab6ad7caf9310f678813bfef42f907bd17'
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PHASES=('dev',)
OWNER_PID,OWNER_TICKS,LOCK_FD,LOCK_DEVICE,LOCK_INODE=124007,29209782,3,33,13626
OWNER_EXPIRY=1792979195.910732
OWNER_SHA='e17ab327cf6d820e4bdc03b85b1f5aab31aa0f9b55debe38896d5b0654f5ec28'
BOOT_ID='4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS_INODE=4026532200
BINARY='retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
MODEL_DIRS={'tasksource':Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05/reader-assets/tasksource-212de447184b')}
ROOT_CONTRACT='experiments/sota-2026-10-22/epoch41/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
ROOT_CONTRACT_SHA='fef319ea3f05753a59fffebd9c0ed94692bc1175b105eb99331b3ac515b9b207'
NATIVE_ROOT=None

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def text_sha(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()
def no_symlink(path):
 if any(p.is_symlink()for p in(Path(path),*Path(path).parents)):raise ValueError('SYMLINK_REFUSED')
def checked(relative):
 if not isinstance(relative,str)or '\\'in relative or PurePosixPath(relative).is_absolute()or any(p in('','.','..')for p in relative.split('/')):raise ValueError('UNSAFE_SOURCE_PATH')
 p=ROOT/relative;no_symlink(p)
 if not p.is_file()or not stat.S_ISREG(p.stat().st_mode):raise ValueError('SOURCE_FILE_MISSING')
 return p
def _pairs(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('DUPLICATE_JSON_KEY')
  out[k]=v
 return out
def read(path):
 no_symlink(path)
 return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=_pairs,
  parse_constant=lambda v:(_ for _ in()).throw(ValueError('NONFINITE_JSON')))
def read_json_line(line):return json.loads(line,object_pairs_hook=_pairs,parse_constant=lambda v:(_ for _ in()).throw(ValueError('NONFINITE_JSON')))
def same(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def put(path,value):
 p=Path(path);no_symlink(p)
 with p.open('x',encoding='utf-8')as f:
  json.dump(value,f,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(path,external=False):
 p=Path(path);return {'path':str(p if external else p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def verify_ref(row):
 if not isinstance(row,dict)or set(row)!={'path','bytes','sha256'}or type(row.get('bytes'))is not int:raise ValueError('BAD_SOURCE_REFERENCE')
 p=checked(row['path'])
 if p.stat().st_size!=row['bytes']or sha(p)!=row['sha256']:raise ValueError('SOURCE_BYTES_CHANGED')
 return p
def load_module(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
def proc(pid):
 try:
  a=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'state':a[0],'ppid':int(a[1]),'pgid':int(a[2]),'sid':int(a[3]),'ticks':int(a[19])}
 except(FileNotFoundError,ProcessLookupError):return None
def remaining(deadline):
 left=deadline-time.time()
 if not 0<left<=600:raise TimeoutError('EXPIRED_BOUNDED_WORKER_DEADLINE')
 return left

def owner_lock(admitted=None):
 if sha(SCOPE/'owner.json')!=OWNER_SHA:raise ValueError('EXACT_CURRENT_OWNER_BYTES_CHANGED')
 owner=read(SCOPE/'owner.json');p=proc(OWNER_PID)
 if (owner.get('pid')!=OWNER_PID or owner.get('startticks')!=OWNER_TICKS or owner.get('expires_unix')!=OWNER_EXPIRY
  or owner.get('generation')!=1 or not p or p['ticks']!=OWNER_TICKS or p['state']in('Z','X')or time.time()>=OWNER_EXPIRY
  or (SCOPE/'release.request').exists()or Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT_ID
  or Path('/proc/self/ns/pid').stat().st_ino!=PIDNS_INODE or Path('/proc/'+str(OWNER_PID)+'/ns/pid').stat().st_ino!=PIDNS_INODE):raise ValueError('GUARDIAN_EXPIRED_REUSED_OR_WRONG_NAMESPACE')
 lock=SCOPE.parent/'exclusive.work.lock';d=Path('/proc/'+str(OWNER_PID)+'/fd/'+str(LOCK_FD));i=d.stat();held=False
 if i.st_dev!=LOCK_DEVICE or i.st_ino!=LOCK_INODE or os.readlink(d)!=str(lock):raise ValueError('GUARDIAN_LOCK_FD_CHANGED')
 for line in Path('/proc/locks').read_text().splitlines():
  words=line.split()
  if len(words)>=8 and words[1:5]==['FLOCK','ADVISORY','WRITE',str(OWNER_PID)]:
   a,b,c=words[5].split(':');held|=(int(a,16),int(b,16),int(c))==(os.major(LOCK_DEVICE),os.minor(LOCK_DEVICE),LOCK_INODE)
 if not held:raise ValueError('GUARDIAN_KERNEL_FLOCK_MISSING')
 if admitted is not None:
  required={'owner_pid':OWNER_PID,'owner_startticks':OWNER_TICKS,'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,
   'owner_lock_fd':LOCK_FD,'owner_lock_device':LOCK_DEVICE,'owner_lock_inode':LOCK_INODE,'owner_generation':1}
  if any(admitted.get(k)!=v for k,v in required.items()):raise ValueError('SOURCE_ADMISSION_OWNER_CHANGED')
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'owner_pid':OWNER_PID,'owner_startticks':OWNER_TICKS,'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,'contender_denied':True}
  fcntl.flock(fd,fcntl.LOCK_UN);raise ValueError('UNEXPECTED_GUARDIAN_LOCK_ACQUISITION')
 finally:os.close(fd)

def external_path(path):
 p=Path(path).absolute();no_symlink(p)
 if ROOT==p or ROOT in p.parents:raise ValueError('PRIVATE_DATA_OR_FEATURES_MUST_BE_OUTSIDE_PUBLIC_PROJECT')
 return p

def model_profiles(plan):
 p=checked(plan['model_profiles_path'])
 if sha(p)!=plan['model_profiles_sha256']:raise ValueError('MODEL_PROFILES_CHANGED')
 value=read(p)
 if value.get('epoch')!=41 or value.get('kind')!=KIND or set(value.get('profiles',{}))!={'tasksource'}:raise ValueError('EXACT_MODEL_PROFILES_REQUIRED')
 for tag,row in value['profiles'].items():
  if row.get('model_directory')!=str(MODEL_DIRS[tag])or row.get('compute_dtype')!='F32':raise ValueError('MODEL_PROFILE_CHANGED')
  for key in('model_source','model_assets_lock','expected_catalog'):verify_ref(row[key])
 return value['profiles']

def verify_model_assets(plan):
 guard=load_module('e41_shared_actual_model_assets',checked(plan['model_assets_validator_path']));rows=model_profiles(plan);profiles={}
 for tag,row in rows.items():
  profiles[tag]={'model_directory':row['model_directory'],'public_lock_path':str(verify_ref(row['model_assets_lock'])),
   'public_lock_sha256':row['model_assets_lock']['sha256'],'expected_catalog_path':str(verify_ref(row['expected_catalog'])),
   'expected_catalog_sha256':row['expected_catalog']['sha256']}
 return guard.validate_inherited_tasksource_profile(profiles,root=ROOT,current_epoch=41,current_kind=KIND,current_source_checkpoint=SOURCE)

def verify_runtime(plan):
 global NATIVE_ROOT
 if Path(sys.prefix)!=VENV or sys.version_info[:2]!=(3,12):raise ValueError('EXACT_SOURCE_CPU_PYTHON_REQUIRED')
 NATIVE_ROOT=external_path(plan['native_asset_root']);lock=read(checked(plan['runtime_assets_lock_path']))
 if sha(checked(plan['runtime_assets_lock_path']))!=plan['runtime_assets_lock_sha256']:raise ValueError('RUNTIME_LOCK_CHANGED')
 guard=load_module('e41_shared_actual_runtime_assets',checked(plan['model_assets_validator_path']))
 members=verify_ref(lock['python_member_manifest']);wheel=verify_ref(lock['python_wheel_lock'])
 receipt=guard.verify_runtime_files(VENV,members,lock['python_member_manifest']['sha256'],lock['assets'],root=ROOT,wheel_identity_path=wheel,native_asset_root=NATIVE_ROOT)
 models=verify_model_assets(plan)
 return {'schema_version':1,'epoch':41,'kind':KIND,'source_checkpoint':SOURCE,
  'status':'FRESH_NINE_INHERITED_MODEL_AND_FULL_RUNTIME_ASSETS_VERIFIED_NO_ML','model_assets':models,'runtime_assets':receipt}

def admission(path,plan,plan_sha,phase):
 if phase!='dev'or Path(path).absolute()!=STUDY/'SOURCE_ADMISSION.json':raise ValueError('EXACT_DEV_SOURCE_ADMISSION_REQUIRED')
 a=read(path)
 needed={'epoch':41,'kind':KIND,'phase':'dev','scope':'benchmarks/ruvector-sota-2026-10-22/','verified_actual_remote_readback':True,
  'plan_sha256':plan_sha,'source_freeze_sha256':plan['source_freeze_sha256']}
 if any(not same(a.get(k),v)for k,v in needed.items())or not isinstance(a.get('published_source_commit'),str)or len(a['published_source_commit'])!=40:raise ValueError('ACTUAL_SOURCE_READBACK_REQUIRED')
 return a,owner_lock(a)

def verify_plan(path,expected,phase):
 if phase!='dev'or Path(path).absolute()!=STUDY/'plan.json'or sha(path)!=expected:raise ValueError('EXACT_FROZEN_DEV_PLAN_REQUIRED')
 p=read(path)
 if (p.get('epoch')!=41 or p.get('kind')!=KIND or p.get('source_checkpoint')!=SOURCE
  or p.get('actual_project')!=str(ROOT)or p.get('guardian_scope')!=str(SCOPE)):raise ValueError('PLAN_SCOPE_CHANGED')
 limits={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,
  'native_corpus_batches':1,'native_indexes':4,'native_queries':12,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'calibration_worker_attempts':0,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0,'retries':0}
 if any(not same(p['limits'].get(k),v)for k,v in limits.items()):raise ValueError('FROZEN_DEV_LIMITS_CHANGED')
 pins={r['path']:r for r in p['pins']}
 if len(pins)!=len(p['pins']):raise ValueError('DUPLICATE_SOURCE_PIN')
 for row in p['pins']:verify_ref(row)
 if pins.get(ROOT_CONTRACT,{}).get('sha256')!=ROOT_CONTRACT_SHA:raise ValueError('ROOT_CONTRACT_MISSING_OR_CHANGED')
 root=read(checked(ROOT_CONTRACT))
 if (p.get('arms')!=root['candidate']['arms']or p.get('model_order')!=['tasksource']or p.get('actual_NLI_forwards')!=72
  or p.get('derived_forecasts')!=36 or p.get('native_indexes')!=4
  or p.get('DEV_cases')!=12 or any(p.get('data_roles',{}).get(k)!=[]for k in('train','calibration','confirmation'))
  or p.get('used_confirmation_identities')!=[]or p.get('champion_promoted')is not False):raise ValueError('ROOT_SCIENCE_OR_ROLE_CHANGED')
 ids=p.get('data_roles',{}).get('dev')
 if not isinstance(ids,list)or len(ids)!=12 or len(set(ids))!=12:raise ValueError('EXACT12_FROZEN_CASE_IDENTITIES_REQUIRED')
 docs=p.get('dev_document_ids');links=p.get('case_ids_by_document')
 if (type(docs)is not list or len(docs)!=4 or len(set(docs))!=4 or any(type(v)is not int for v in docs)
  or type(links)is not dict or set(links)!={str(v)for v in docs}or any(len(links[str(v)])!=3 for v in docs)
  or [i for v in docs for i in links[str(v)]]!=ids):raise ValueError('FOUR_DOCUMENT_THREE_QUERY_IDENTITY_BINDING_CHANGED')
 for key in('worker','native_worker','features_source','model_assets_validator','model_profiles','runtime_assets_lock','observer_source','observer_helper_source','expected_counters_source','source_freeze'):
  name=p[key+'_path']
  if pins.get(name,{}).get('sha256')!=p[key+'_sha256']:raise ValueError('UNPINNED_SOURCE_INTERFACE')
 if Path(p['external_run_directory'])!=SCOPE/'run-external':raise ValueError('EXACT_EXTERNAL_RUN_DIRECTORY_REQUIRED')
 external_path(p['external_run_directory']);external_path(p['native_asset_root'])
 assets=p.get('external_data_assets')
 if not isinstance(assets,list)or len(assets)!=2 or {r.get('role')for r in assets}!={'dev_features','dev_oracle'}:raise ValueError('EXACT_EXTERNAL_DATA_CAPABILITIES_REQUIRED')
 for row in assets:
  file=external_path(row['path'])
  if not file.is_file()or file.stat().st_size!=row['bytes']:raise ValueError('EXTERNAL_DATA_METADATA_CHANGED')
 frozen=read(checked(p['source_freeze_path']))
 if frozen.get('epoch')!=41 or frozen.get('kind')!=KIND or any(pins.get(r['path'])!=r for r in frozen['entries']):raise ValueError('SOURCE_FREEZE_CHANGED')
 model_profiles(p);return p

def dispatch_proof(plan,plan_sha,admission_path,wait_seconds=3):
 claim=read(STUDY/'DISPATCH_RESERVATION.json')
 expected={'schema_version':1,'epoch':41,'kind':KIND,'phase':'dev','plan_sha256':plan_sha,
  'source_freeze_sha256':plan['source_freeze_sha256'],'admission_sha256':sha(admission_path),
  'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
 if any(not same(claim.get(k),v)for k,v in expected.items()):raise ValueError('DISPATCH_SOURCE_RESERVATION_CHANGED')
 if not 0<=time.monotonic()-claim['dispatch_monotonic_seconds']<600:raise TimeoutError('DISPATCH_BUDGET_EXPIRED')
 file=STUDY/'DISPATCH_ATTEMPT.json';until=time.monotonic()+wait_seconds
 while not file.exists():
  if time.monotonic()>=until:raise RuntimeError('UNCERTAIN_DISPATCH_NO_RETRY')
  time.sleep(.01)
 attempt=read(file);actual=proc(os.getpid())
 if (any(not same(attempt.get(k),v)for k,v in expected.items())or attempt.get('pid')!=os.getpid()or not actual
  or attempt.get('startticks')!=actual['ticks']or actual['pgid']!=os.getpid()or actual['sid']!=os.getpid()
  or attempt.get('verified_launcher_start')is not True or attempt.get('uncertain_launcher_start')is not False):raise ValueError('DETACHED_SUPERVISOR_IDENTITY_CHANGED')
 return claim,attempt

def phase_zero(phase):
 if phase!='dev':raise ValueError('ONLY_DEV_PHASE_AUTHORIZED')
 return ('gold_reader_calls','semantic_gold_labels_decoded','TRAIN_input_reads','old_benchmark_DEV_reads','CONF_input_reads','fits','calibration_calls','training_steps','optimizer_initializations','backward_calls','optimizer_steps','paid_calls','GPU_calls','HTTP_requests','generation_calls','full104_requests','Python_network_operations_attempted','Node_network_operations_attempted')
