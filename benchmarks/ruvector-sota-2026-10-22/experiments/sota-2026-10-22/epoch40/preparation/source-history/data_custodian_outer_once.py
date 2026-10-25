"""One bounded label-blind data custodian child; no parsing or ML in outer."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,time,sys
sys.dont_write_bytecode=True
W=Path("/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05")
PLAN_SHA='1fa64499888e21c48075641643a8c013b19b57d0840912c5a69823305158f3fa'
OWNER_SHA='f18924b1456dcf51c461181c233ff4511cd3e479982f48b109a0e4126b5c3af0'
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
 review=json.loads(review_path.read_text());child=W/'data_custodian_child_once.py'
 if not(review['checks_passed']is True and review['wrapper_source_sha256']==sha(__file__)and review['child_source_sha256']==sha(child)and review['plan_sha256']==PLAN_SHA):raise ValueError('WRAPPER_SOURCE_REVIEW_MISMATCH')
 plan=json.loads((W/'DATA_CUSTODIAN_PLAN.v2.json').read_text())
 if not(review.get('approved')is True and review.get('only_label_blind_custodian_parser_authorized')is True and review.get('epoch')==40 and review.get('source_checkpoint')==plan['source_checkpoint'] and review.get('predataseal_sha256')==plan['seal']['sha256'] and review.get('policy_sha256')==plan['policy']['sha256']):raise ValueError('EXACT_CUSTODIAN_PARSER_APPROVAL_REQUIRED')
 if sha(W/'DATA_CUSTODIAN_PLAN.v2.json')!=PLAN_SHA or sha(W/'owner.json')!=OWNER_SHA:raise ValueError('FROZEN_DATA_CUSTODIAN_SCOPE_DRIFT')
 owner=json.loads((W/'owner.json').read_text());o=proc(120232)
 if not(o and o['ticks']==27979422 and o['state']not in('Z','X')and time.time()<owner['expires_unix']and not(W/'release.request').exists()):raise ValueError('CURRENT_PHYSICAL_OWNER_REQUIRED')
 if any((W/n).exists()for n in('DATA_CUSTODIAN_E40_OUTER_INVOCATION.json','DATA_CUSTODIAN_E40_ATTEMPT.json','DATA_CUSTODIAN_E40_RESULT.json')):raise ValueError('DATA_CUSTODIAN_ATTEMPT_ALREADY_CONSUMED_NO_RETRY')
 argv=['taskset','-c','0,1','python3','-I','-B',str(child),'--review',a.review,'--review-sha',a.review_sha]
 put(W/'DATA_CUSTODIAN_E40_OUTER_INVOCATION.json',{'schema_version':1,'epoch':40,'argv':argv,'attempts':1,'allowed_retries':0,'child_work_timeout_seconds':175,'owned_cleanup_allowance_seconds':5,'maximum_full_child_seconds':180,'review_sha256':a.review_sha,'plan_sha256':PLAN_SHA,'started_unix':time.time()})
 started=time.monotonic();process=None;identity=None;out=b'';err=b'';signals=[];failure=None
 try:
  process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True,cwd=W)
  identity=proc(process.pid)
  if not(identity and identity['pgid']==process.pid==identity['sid']and identity['state']not in('Z','X')):raise RuntimeError('OWNED_DATA_CUSTODIAN_CHILD_IDENTITY_UNCERTAIN_NO_RETRY')
  put(W/'DATA_CUSTODIAN_E40_OUTER_CHILD_IDENTITY.json',identity)
  try:out,err=process.communicate(timeout=max(.001,175-(time.monotonic()-started)))
  except subprocess.TimeoutExpired:
   failure='DATA_CUSTODIAN_CHILD_175_SECOND_DEADLINE'
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
  for name,value in [('data-custodian-outer.stdout',out),('data-custodian-outer.stderr',err)]:
   with(W/name).open('xb')as f:f.write(value);f.flush();os.fsync(f.fileno())
  module_result=W/'DATA_CUSTODIAN_E40_RESULT.json';result={'schema_version':1,'epoch':40,'status':'COMPLETE'if failure is None and process is not None and process.returncode==0 and elapsed<=180 else'FAILED_STOP_NO_RETRY','full_child_wall_seconds_including_its_final_capture':elapsed,'wall_scope':'From before childPopen through communicate/wait including child final result fsync and pipes closure. Outer bookkeeping stdout/result capture is separately scoped and is not a child-payload operation.','child_return_code':process.returncode if process is not None else None,'child_identity':identity,'owned_signals':signals,'error':failure,'allowed_retries':0,'stdout_sha256':hashlib.sha256(out).hexdigest(),'stderr_sha256':hashlib.sha256(err).hexdigest(),'module_result_sha256':sha(module_result)if module_result.is_file()else None,'model_tokenizer_native_case_calls_by_outer':0}
  put(W/'DATA_CUSTODIAN_E40_OUTER_RESULT.json',result)
 print(json.dumps(result,allow_nan=False))
 if result['status']!='COMPLETE':raise SystemExit(1)
if __name__=='__main__':main()
