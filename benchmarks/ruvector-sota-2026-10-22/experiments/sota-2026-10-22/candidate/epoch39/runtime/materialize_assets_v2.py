"""New one-shot E39 v2 readonly physical snapshot preparation; definitions only until root invocation.

No download, ML/tokenizer/native initialization, case parsing or source mutation.
The immutable price0 plan and exact guardian are mandatory before payload reads.
"""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import stat
import time
import traceback

HERE=Path(__file__).resolve().parent
PLAN_SHA='5021b9a9156017f23b4dd7763b975a7745aeeecf8cc856707c237d643ec934ca'
SOURCE='74dbbcb10508ced7e0edf53a0c736f14c19a19a1'
KIND='REAL_FINFACT_DEV_TRANSFER_PILOT'
SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508')
BOOT='4632fb06-b0ef-4df5-b72b-0e875bbad810'
PID,TICKS,FD,DEVICE,INODE=116430,26811853,3,33,13626
OWNER_SHA='9520972db7b60ec65a92e00b7c5dd13e9630b2b0291275e11b61570f72865251'


def load_guard():
 sp=importlib.util.spec_from_file_location('e39_same_real_asset_guard',HERE/'model_assets_guard.py')
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def put(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8')as stream:
  json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

def guardian():
 g=load_guard();owner=SCOPE/'owner.json'
 if g.sha(owner)!=OWNER_SHA:raise ValueError('ASSET_PLAN_GUARDIAN_BYTES_CHANGED')
 record=g.read_metadata(owner);p=Path('/proc/'+str(PID));fields=(p/'stat').read_text().rsplit(')',1)[1].split()
 descriptor=p/'fd'/str(FD);info=descriptor.stat();lock=SCOPE.parent/'exclusive.work.lock'
 if (record.get('pid')!=PID or record.get('startticks')!=TICKS or record.get('generation')!=1
  or time.time()>=record.get('expires_unix',0)or fields[0]in('Z','X')or int(fields[19])!=TICKS
  or Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT
  or Path('/proc/self/ns/pid').stat().st_ino!=4026532200 or (p/'ns/pid').stat().st_ino!=4026532200 or info.st_dev!=DEVICE or info.st_ino!=INODE
  or os.readlink(descriptor)!=str(lock)or (SCOPE/'release.request').exists()):raise ValueError('ASSET_PLAN_GUARDIAN_NOT_CURRENT')
 held=False
 for line in Path('/proc/locks').read_text().splitlines():
  words=line.split()
  if len(words)>=8 and words[1:5]==['FLOCK','ADVISORY','WRITE',str(PID)]:
   a,b,c=words[5].split(':');held|=(int(a,16),int(b,16),int(c))==(os.major(DEVICE),os.minor(DEVICE),INODE)
 if not held:raise ValueError('EXACT_GUARDIAN_KERNEL_FLOCK_ABSENT')
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  fcntl.flock(fd,fcntl.LOCK_UN);raise ValueError('ASSET_PLAN_GUARDIAN_LOCK_NOT_HELD')
 finally:os.close(fd)

def validate_frozen_plan(path):
 g=load_guard()
 if g.sha(path)!=PLAN_SHA:raise ValueError('IMMUTABLE_ZERO_ACQUISITION_PLAN_REQUIRED')
 plan=g.read_metadata(path)
 expected={'epoch':39,'source_checkpoint':SOURCE,'paid_API_cap_USD':0,'paid_API_calls':0,'GPU_calls':0,
  'network_requests_allowed':0,'weights_downloads_allowed':0,'maximum_wall_seconds_including_hashes_and_cleanup':180,
  'CPU_threads':2,'CPU_affinity':[0,1],'materialization_attempts':1,'allowed_retries':0,'model_or_data_measurement_authorization':0}
 if any(plan.get(k)!=v for k,v in expected.items())or set(plan.get('source_profiles',{}))!={'b354','xxlarge'}:raise ValueError('ACQUISITION_PLAN_POLICY_CHANGED')
 return plan

def existing_parent(path):
 path=Path(path)
 while not path.exists():path=path.parent
 return path


def select_transfer(tag,declaration,info,original,dest,allowance):
 """The frozen v2 plan permits exactly one new physical weight snapshot."""
 special=(tag=='b354' and declaration['path']=='model.safetensors'
  and declaration['bytes']==870182606 and declaration.get('upstream_sha256')=='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b')
 if special:
  required={'profile':tag,'path':declaration['path'],'source_path':str(original),'target_path':str(dest),
   'bytes':declaration['bytes'],'sha256':declaration['upstream_sha256'],'force_new_physical_copy':True,
   'maximum_stream_chunk_bytes':1048576,'target_mode':'0444','source_mode_mtime_bytes_unchanged':True,
   'source_link_count_unchanged_for_copy':True,'all_other_writable_files_above_16MiB':'STOP_NO_FALLBACK'}
  if allowance!=required:raise ValueError('EXACT_FROZEN_WEIGHT_COPY_ALLOWANCE_REQUIRED')
  return 'READONLY_PHYSICAL_WEIGHT_SNAPSHOT'
 if info.st_mode&0o222:
  if info.st_size>16777216:raise ValueError('WRITABLE_LARGE_SOURCE_STOP_NO_COPY_OR_DOWNLOAD')
  return 'READONLY_COPY_OF_WRITABLE_METADATA'
 return 'HARDLINK_OF_ALREADY_READONLY_HASH_VERIFIED_SOURCE'

def copy_readonly(original,dest,before):
 """Physical bounded-chunk copy; only the new destination is chmodded."""
 with original.open('rb')as inp,dest.open('xb')as out:
  shutil.copyfileobj(inp,out,1048576);out.flush();os.fsync(out.fileno())
 os.utime(dest,ns=(before.st_atime_ns,before.st_mtime_ns));dest.chmod(0o444)
 after=original.stat()
 if (before.st_size,before.st_mode,before.st_mtime_ns,before.st_nlink)!=(after.st_size,after.st_mode,after.st_mtime_ns,after.st_nlink):
  raise ValueError('PHYSICAL_COPY_CHANGED_ORIGINAL_METADATA')
 if original.stat().st_ino==dest.stat().st_ino:raise ValueError('PHYSICAL_SNAPSHOT_IS_A_HARDLINK')


def _prepare_impl(plan,root,result):
 g=load_guard()
 inventory={};copy_total=0;metadata_copy_total=0
 for tag,row in plan['source_profiles'].items():
  spec=g.PROFILE_SPECS[tag];authority=Path(row['expected_catalog']['path'])
  if g.sha(authority)!=spec['catalog_sha256']or authority.stat().st_size!=row['expected_catalog']['bytes']:raise ValueError('FROZEN_EXPECTED_SOURCE_CHANGED')
  canonical=HERE.parent/spec['catalog']
  if g.sha(canonical)!=spec['catalog_sha256']:raise ValueError('CANONICAL_SOURCE_AUTHORITY_CHANGED')
  expected=g.read_metadata(canonical);source=g.no_symlink(row['cache_directory']);target=g.no_symlink(row['target_directory'])
  if target.exists():raise ValueError('FRESH_ASSET_TARGET_ALREADY_EXISTS_NO_RETRY')
  names={r['path']for r in expected['files']}
  if {p.name for p in source.iterdir()}-{'asset-lock.json'}!=names:raise ValueError('SOURCE_CACHE_INVENTORY_MISMATCH')
  files=[]
  for declaration in expected['files']:
   file=g.no_symlink(source/declaration['path']);info=file.stat()
   if not stat.S_ISREG(info.st_mode)or info.st_size!=declaration['bytes']:raise ValueError('SOURCE_CACHE_PAYLOAD_METADATA_MISMATCH')
   method=select_transfer(tag,declaration,info,file,target/declaration['path'],plan['large_readonly_copy_allowance'])
   if method!='HARDLINK_OF_ALREADY_READONLY_HASH_VERIFIED_SOURCE':copy_total+=info.st_size
   if method=='READONLY_COPY_OF_WRITABLE_METADATA':metadata_copy_total+=info.st_size
   files.append((declaration,info,method))
  inventory[tag]=(source,target,canonical,expected,files)
 if metadata_copy_total>16777216 or min(shutil.disk_usage(existing_parent(target.parent)).free for source,target,canonical,expected,files in inventory.values())<copy_total+plan['minimum_copy_staging_margin_bytes']+plan['minimum_workspace_free_bytes']:raise ValueError('ASSET_PREPARATION_COPY_SPACE_FAILED')
 result['copy_bytes_planned']=copy_total;result['metadata_copy_bytes_planned']=metadata_copy_total
 for tag,(source,target,canonical,expected,files)in inventory.items():
  guardian();target.mkdir(parents=True,exist_ok=False);observed=[];transfers=[]
  result['profiles'][tag]={'source_directory':str(source),'target_directory':str(target),'transfers':transfers}
  for declaration,before,method in files:
   guardian();original=source/declaration['path'];dest=target/declaration['path'];verified=g.scan_payload(original,declaration)
   if method!='HARDLINK_OF_ALREADY_READONLY_HASH_VERIFIED_SOURCE':
    copy_readonly(original,dest,before)
    target_verified=g.scan_payload(dest,declaration)
    if target_verified['actual_payload_sha256']!=verified['actual_payload_sha256']:raise ValueError('NEW_PHYSICAL_COPY_HASH_MISMATCH')
   else:os.link(original,dest)
   after=original.stat();stable=lambda s:(s.st_size,s.st_mode,s.st_mtime_ns)
   if stable(before)!=stable(after):raise ValueError('ORIGINAL_SOURCE_BYTES_MODE_MTIME_CHANGED')
   observed.append({'path':declaration['path'],'bytes':verified['actual_payload_bytes_hashed'],'sha256':verified['actual_payload_sha256'],
    'source_url':declaration['source_url'],'upstream_git_blob_sha1':declaration['upstream_git_blob_sha1']})
   transfers.append({'path':declaration['path'],'method':method,'source_payload_full_hash_verified':True,
    'original_bytes_mode_mtime_unchanged':True,'source_nlink_before':before.st_nlink,'source_nlink_after':after.st_nlink,
    'nlink_ctime_changes_disclosed':method=='HARDLINK_OF_ALREADY_READONLY_HASH_VERIFIED_SOURCE','target_readonly':not bool(dest.stat().st_mode&0o222)})
  lock={'schema_version':1,'epoch':39,'kind':KIND,'repository':expected['repository'],'revision':expected['revision'],
   'model_directory':str(target),'files':observed}
  direct=target/'asset-lock.json';put(direct,lock);direct.chmod(0o444);target.chmod(0o555)
  public=HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.json');put(public,lock);public.chmod(0o444)
  result['profiles'][tag].update(public_lock=g.source_ref(public,root),direct_lock_sha256=g.sha(direct))
 profiles={tag:{'model_directory':str(target),'public_lock_path':str(HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.json')),
  'public_lock_sha256':g.sha(HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.json')),'expected_catalog_path':str(canonical),
  'expected_catalog_sha256':g.PROFILE_SPECS[tag]['catalog_sha256']}for tag,(source,target,canonical,expected,files)in inventory.items()}
 result['actual_complete_validator']=g.validate_model_profiles(profiles,root=root,epoch=39,kind=KIND,source_checkpoint=SOURCE)
 result['status']='BOTH_MODEL_CACHES_PREPARED_AND_FULL14_PAYLOAD_GUARD_PASSED_NO_ML'
 return result


def prepare_assets(plan_path,*,root,runtime_request):
 """Root-only once entry point. Valid authorization precedes durable reservation;
 every subsequent cache/preflight/hash/mutation failure is captured outside R.
 """
 started=time.monotonic();plan=validate_frozen_plan(plan_path);guardian();root=Path(root)
 reservation=SCOPE/'ASSET_SNAPSHOT_V2_ATTEMPT.json'
 put(reservation,{'schema_version':1,'epoch':39,'kind':KIND,'source_checkpoint':SOURCE,'plan_sha256':PLAN_SHA,
  'before_payload_reads_and_target_mutations':True,'attempts_reserved':1,'allowed_retries':0,'at_unix':time.time()})
 result={'schema_version':1,'epoch':39,'kind':KIND,'source_checkpoint':SOURCE,'plan_sha256':PLAN_SHA,
  'status':'PREPARING','profiles':{},'copy_bytes_planned':None,'errors':[],
  'model_tokenizer_native_initializations_or_calls':0,'case_oracle_reads':0,'network_calls':0}
 old_handler=signal.getsignal(signal.SIGALRM)
 def timeout(sig,frame):raise TimeoutError('ASSET_PREPARATION_180_SECOND_BOUND')
 try:
  signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,180-(time.monotonic()-started)))
  os.sched_setaffinity(0,{0,1})
  if os.sched_getaffinity(0)!={0,1}:raise ValueError('ASSET_PREPARATION_CPU_POLICY_FAILED')
  _prepare_impl(plan,root,result)
  result['runtime_closure']=load_guard().verify_runtime_files(root=root,**runtime_request)
  result['materializer_source']=load_guard().source_ref(Path(__file__),root)
  result['status']='BOTH_MODEL_CACHES_AND_FULL_RUNTIME_CLOSURE_PASSED_NO_ML'
 except BaseException as error:
  result['status']='ASSET_PREPARATION_FAILED_STOP_NO_RETRY';result['errors'].append({'type':type(error).__name__,'message':str(error)})
  (SCOPE/'ASSET_SNAPSHOT_V2_exact-error.txt').write_text(traceback.format_exc());raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler)
  result['wall_seconds_including_hashes_and_cleanup']=time.monotonic()-started
  result['inner_wall_scope']='PRE_FINAL_RESULT_FSYNC_CAPTURE_ONLY_OUTER175_PLUS5_ENFORCES_TOTAL'
  if result['wall_seconds_including_hashes_and_cleanup']>180:
   result['status']='ASSET_PREPARATION_FAILED_STOP_NO_RETRY';result['errors'].append({'type':'TimeoutError','message':'ASSET_TOTAL_WALL_BOUND_EXCEEDED'})
  result['CPU_affinity']=sorted(os.sched_getaffinity(0));put(SCOPE/'ASSET_SNAPSHOT_V2_RESULT.json',result)
 if result['status']!='BOTH_MODEL_CACHES_AND_FULL_RUNTIME_CLOSURE_PASSED_NO_ML':raise TimeoutError('ASSET_TOTAL_WALL_BOUND_EXCEEDED')
 return result
