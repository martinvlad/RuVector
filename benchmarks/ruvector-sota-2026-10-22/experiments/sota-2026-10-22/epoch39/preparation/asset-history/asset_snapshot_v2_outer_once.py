"""One bounded asset preparation child; no model, dataset or native calls here."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,time,sys
sys.dont_write_bytecode=True
W=Path("/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508")
PLAN_SHA='5021b9a9156017f23b4dd7763b975a7745aeeecf8cc856707c237d643ec934ca'
REQUEST_SHA='afdc17afdd0a0dd988b4ebef180526a17eeba8c8a288d304caa6e18d46e41393'
OWNER_SHA='9520972db7b60ec65a92e00b7c5dd13e9630b2b0291275e11b61570f72865251'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(Path(p).parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def proc(pid):
 try:
  a=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'state':a[0],'ticks':int(a[19]),'pgid':int(a[2]),'sid':int(a[3])}
 except FileNotFoundError:return None
def main():
 p=argparse.ArgumentParser();p.add_argument('--review',required=True);p.add_argument('--review-sha',required=True);a=p.parse_args()
 review_path=Path(a.review)
 if sha(review_path)!=a.review_sha:raise ValueError('EXACT_INDEPENDENT_WRAPPER_REVIEW_REQUIRED')
 review=json.loads(review_path.read_text());child=W/'asset_snapshot_v2_child_once.py'
 if not(review['checks_passed']is True and review['wrapper_source_sha256']==sha(__file__)and review['child_source_sha256']==sha(child)and review['runtime_request_sha256']==REQUEST_SHA):raise ValueError('WRAPPER_SOURCE_REVIEW_MISMATCH')
 if sha(W/'ASSET_REUSE_PLAN.v2.json')!=PLAN_SHA or sha(W/'ASSET_RUNTIME_REQUEST.v1.json')!=REQUEST_SHA or sha(W/'owner.json')!=OWNER_SHA:raise ValueError('FROZEN_ASSET_SCOPE_DRIFT')
 owner=json.loads((W/'owner.json').read_text());o=proc(116430)
 if not(o and o['ticks']==26811853 and o['state']not in('Z','X')and time.time()<owner['expires_unix']and not(W/'release.request').exists()):raise ValueError('CURRENT_PHYSICAL_OWNER_REQUIRED')
 if sha(W/'ASSET_PREPARATION_RESULT.json')!='4e3980d2218ee08f18186145fd3de406d75c5bb446e89ba61fbe472494cfc920':raise ValueError('CLOSED_V1_FAILURE_REQUIRED')
 v1=json.loads((W/'ASSET_OUTER_RESULT.json').read_text())
 if not(v1['status']=='FAILED_STOP_NO_RETRY' and v1['child_return_code']==1 and v1['child_identity']['pid']==117454 and v1['child_identity']['ticks']==27273505 and proc(117454)is None):raise ValueError('V1_CHILD_CLOSURE_REQUIRED')
 if any((W/n).exists()for n in('ASSET_SNAPSHOT_V2_OUTER_INVOCATION.json','ASSET_SNAPSHOT_V2_ATTEMPT.json','ASSET_SNAPSHOT_V2_RESULT.json')):raise ValueError('ASSET_ATTEMPT_ALREADY_CONSUMED_NO_RETRY')
 argv=['taskset','-c','0,1','python3','-I','-B',str(child)]
 put(W/'ASSET_SNAPSHOT_V2_OUTER_INVOCATION.json',{'schema_version':1,'epoch':39,'argv':argv,'attempts':1,'allowed_retries':0,'child_work_timeout_seconds':175,'owned_cleanup_allowance_seconds':5,'maximum_full_child_seconds':180,'review_sha256':a.review_sha,'plan_sha256':PLAN_SHA,'runtime_request_sha256':REQUEST_SHA,'started_unix':time.time()})
 started=time.monotonic();process=None;identity=None;out=b'';err=b'';signals=[];failure=None
 try:
  process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True,cwd=W)
  identity=proc(process.pid)
  if not(identity and identity['pgid']==process.pid==identity['sid']and identity['state']not in('Z','X')):raise RuntimeError('OWNED_ASSET_CHILD_IDENTITY_UNCERTAIN_NO_RETRY')
  put(W/'ASSET_SNAPSHOT_V2_OUTER_CHILD_IDENTITY.json',identity)
  try:out,err=process.communicate(timeout=max(.001,175-(time.monotonic()-started)))
  except subprocess.TimeoutExpired:
   failure='ASSET_CHILD_175_SECOND_DEADLINE'
   current=proc(process.pid)
   if current is not None and (current['ticks'],current['pgid'],current['sid'])!=(identity['ticks'],identity['pgid'],identity['sid']):raise RuntimeError('OWNED_CHILD_CHANGED_REFUSE_SIGNAL')
   if current is not None:os.killpg(process.pid,signal.SIGTERM);signals.append('SIGTERM')
   try:out,err=process.communicate(timeout=min(.5,max(.001,180-(time.monotonic()-started))))
   except subprocess.TimeoutExpired:
    current=proc(process.pid)
    if current is not None and (current['ticks'],current['pgid'],current['sid'])!=(identity['ticks'],identity['pgid'],identity['sid']):raise RuntimeError('OWNED_CHILD_CHANGED_REFUSE_KILL')
    if current is not None:os.killpg(process.pid,signal.SIGKILL);signals.append('SIGKILL')
    out,err=process.communicate(timeout=max(.001,180-(time.monotonic()-started)))
 except BaseException as error:
  failure=type(error).__name__+':'+str(error)
  # Any exceptional path receives the same bounded, identity-only cleanup.
  cleanup_deadline=min(started+180,time.monotonic()+5)
  if process is not None and process.returncode is None:
   current=proc(process.pid)
   owned=identity is not None and current is not None and (current['ticks'],current['pgid'],current['sid'])==(identity['ticks'],identity['pgid'],identity['sid'])
   if owned and current['state']not in('Z','X'):
    os.killpg(process.pid,signal.SIGTERM);signals.append('SIGTERM_EXCEPTION_CLEANUP')
   try:out,err=process.communicate(timeout=min(.5,max(.001,cleanup_deadline-time.monotonic())))
   except subprocess.TimeoutExpired:
    current=proc(process.pid)
    owned=identity is not None and current is not None and (current['ticks'],current['pgid'],current['sid'])==(identity['ticks'],identity['pgid'],identity['sid'])
    if owned and current['state']not in('Z','X'):
     os.killpg(process.pid,signal.SIGKILL);signals.append('SIGKILL_EXCEPTION_CLEANUP')
    try:out,err=process.communicate(timeout=max(.001,cleanup_deadline-time.monotonic()))
    except subprocess.TimeoutExpired:failure+=';OWNED_CLEANUP_UNPROVED_STOP'
 finally:
  elapsed=time.monotonic()-started
  for name,value in [('asset-snapshot-v2-outer.stdout',out),('asset-snapshot-v2-outer.stderr',err)]:
   with(W/name).open('xb')as f:f.write(value);f.flush();os.fsync(f.fileno())
  module_result=W/'ASSET_SNAPSHOT_V2_RESULT.json';result={'schema_version':1,'epoch':39,'status':'COMPLETE'if failure is None and process is not None and process.returncode==0 and elapsed<=180 else'FAILED_STOP_NO_RETRY','full_child_wall_seconds_including_its_final_capture':elapsed,'wall_scope':'From before childPopen through communicate/wait including child final result fsync and pipes closure. Outer bookkeeping stdout/result capture is separately scoped and is not a child-payload operation.','child_return_code':process.returncode if process is not None else None,'child_identity':identity,'owned_signals':signals,'error':failure,'allowed_retries':0,'stdout_sha256':hashlib.sha256(out).hexdigest(),'stderr_sha256':hashlib.sha256(err).hexdigest(),'module_result_sha256':sha(module_result)if module_result.is_file()else None,'model_tokenizer_native_case_calls_by_outer':0}
  put(W/'ASSET_SNAPSHOT_V2_OUTER_RESULT.json',result)
 print(json.dumps(result,allow_nan=False))
 if result['status']!='COMPLETE':raise SystemExit(1)
if __name__=='__main__':main()
