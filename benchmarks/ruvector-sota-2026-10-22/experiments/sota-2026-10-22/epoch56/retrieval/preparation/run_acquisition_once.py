"""Root-only one-shot public acquisition; no parser/model/native imports or benchmark scoring."""
import time
START=time.monotonic()
import os,json,hashlib,subprocess,signal,sys
from pathlib import Path
W=Path(__file__).resolve().parent;C=Path('/dev/shm/ruvector-e56-retrieval');Q=Path('/dev/shm/ruvector-e56-audit/retrieval-source-review');sys.path.insert(0,str(W/'publication-helpers'));import guard as g

def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def put(p,x):
 with p.open('x')as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def snap(pid):
 try:
  v=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'startticks':int(v[19]),'state':v[0],'pgid':int(v[2]),'sid':int(v[3])}
 except (FileNotFoundError,ProcessLookupError):return None

def group_live(group):
 result=[]
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   s=snap(int(p.name))
   if s and (s['pgid']==group or s['sid']==group) and s['state']not in('Z','X'):result.append(s)
 return result

def main():
 g.owner_fence();assert sorted(os.sched_getaffinity(0))==[0,1]
 script=C/'acquire_and_extract_parser.py';plan=C/'ACQUISITION_PLAN.v1.json';approval=Q/'ACQUISITION_SOURCE_REVIEW.v2.json'
 assert ref(script)['sha256']=='8058dfc229fd5de526ffb9933e659a6a57bb2c290bfbf7802455a0a791d2355c';assert ref(plan)['sha256']=='5bcca84150bad279afed0e62bef5eb018584ddb5e01007959c067f0ab5b31ce8';assert ref(approval)['sha256']=='277420aa228188bf823e14b246c0d8e8f7b215fa4ebb7fceecb8920e62057998'
 argv=['/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/bin/python','-I','-B',str(script),'--plan',str(plan),'--sha256',ref(plan)['sha256']]
 put(W/'ACQUISITION_ROOT_INTENT.actual.v1.json',{'epoch':56,'argv':argv,'source':ref(script),'plan':ref(plan),'independent_source_approval':ref(approval),'maximum_invocations':1,'Root_outer_hard_seconds':300,'TERM_at_seconds':295,'KILL_at_seconds':298,'parser_imports_authorized':0,'benchmark_or_native_measurements_authorized':0,'automatic_retry':False})
 child=None;identity=None;reason=None;term=False;killed=False;code=None;term_at=None;stop=[False]
 def requested(signum,frame):stop[0]=True
 signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
 try:
  with(W/'ACQUISITION_PRIVATE.stdout').open('xb')as stdout,(W/'ACQUISITION_PRIVATE.stderr').open('xb')as stderr:
   assert not stop[0]
   child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True);identity=snap(child.pid)
   assert identity and identity['pgid']==identity['sid']==child.pid
   put(W/'ACQUISITION_CHILD_STARTED.actual.v1.json',{'epoch':56,'identity':identity,'monotonic':time.monotonic()})
   while child.poll()is None:
    elapsed=time.monotonic()-START
    if stop[0]:reason=reason or 'EXTERNAL_STOP_SIGNAL'
    try:g.owner_fence()
    except Exception:reason=reason or 'OWNER_LOST'
    if elapsed>=295:reason=reason or 'ACQUISITION_HARD_DEADLINE'
    if reason and not term:os.killpg(child.pid,signal.SIGTERM);term=True;term_at=elapsed
    if (elapsed>=298 or(term_at is not None and elapsed-term_at>=2)) and not killed:os.killpg(child.pid,signal.SIGKILL);killed=True
    if elapsed>=298.8:break
    time.sleep(.1)
   code=child.wait(timeout=max(.05,299.3-(time.monotonic()-START)))
   stdout.flush();stderr.flush();os.fsync(stdout.fileno());os.fsync(stderr.fileno())
 except BaseException as exc:
  reason=reason or type(exc).__name__
 finally:
  signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.signal(signal.SIGINT,signal.SIG_IGN)
  if child is not None:
   live=group_live(child.pid)
   if live:
    os.killpg(child.pid,signal.SIGKILL);killed=True
   if child.poll()is None:
    try:code=child.wait(timeout=.25)
    except subprocess.TimeoutExpired:reason=reason or 'CLOSURE_UNVERIFIED'
   else:code=child.returncode
  live=group_live(child.pid)if child else []
  result={'epoch':56,'kind':'PUBLIC_OPAQUE_ASSET_ACQUISITION_ONLY','exit_code':code,'child_identity':identity,'child_after_wait':snap(child.pid)if child else None,'live_owned_group_processes':live,'all_owned_processes_closed':not live and(child is None or child.poll()is not None),'wall_seconds_including_preflight_and_cleanup':time.monotonic()-START,'reason':reason,'TERM_sent':term,'KILL_sent':killed,'automatic_retries':0,'actual_invocations':1,'model_tokenizer_BGE_RuVector_native_Gold_imports':0,'source_or_corpus_publication_authorized':False,'private_stdout':ref(W/'ACQUISITION_PRIVATE.stdout')if(W/'ACQUISITION_PRIVATE.stdout').exists()else None,'private_stderr':ref(W/'ACQUISITION_PRIVATE.stderr')if(W/'ACQUISITION_PRIVATE.stderr').exists()else None}
  result['checks_passed']=code==0 and reason is None and not live and result['wall_seconds_including_preflight_and_cleanup']<300
  put(W/'ACQUISITION_ROOT_OUTER.actual.v1.json',result);print(json.dumps({k:result[k]for k in ['checks_passed','exit_code','wall_seconds_including_preflight_and_cleanup','all_owned_processes_closed','reason']}),flush=True)
 return 0 if result['checks_passed']else 17
if __name__=='__main__':raise SystemExit(main())
