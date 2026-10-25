"""Root metadata-only watch; calls the SOURCE-pinned observer once, never science."""
from pathlib import Path
import hashlib,json,os,subprocess,time
W=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
R=W/'project';E=R/'experiments/sota-2026-10-22/epoch40'
def put(name,value):
 with(W/name).open('x')as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
claim=json.loads((E/'DISPATCH_ATTEMPT.json').read_text())
assert (claim['pid'],claim['startticks'],claim['pgid'],claim['sid'])==(122786,28642231,122786,122786)
assert sha(E/'plan.json')=='3083581ef07d43a4e64d635de87f9dc78cfcd444746b15215b2791340301ba31'
plan=json.loads((E/'plan.json').read_text());observer=R/plan['observer_source_path']
assert sha(observer)==plan['observer_source_sha256']
put('NATIVE_METADATA_MONITOR_INVOCATION.v1.json',{'epoch':40,'supervisor':{k:claim[k]for k in ['pid','startticks','pgid','sid']},'observer_source_sha256':sha(observer),'purpose':'Read known identity/state only; SOURCE-pinned observer is sole closure proof. No native/model/label calls, signals, retries or performance selection.','source_execution_limit_seconds':600,'metadata_only_watch_limit_seconds_from_dispatch':615,'at_monotonic':time.monotonic()})
changes=[];last=None;terminal=None
while True:
 try:
  fields=Path('/proc/122786/stat').read_text().rsplit(')',1)[1].split()
  assert (int(fields[19]),int(fields[2]),int(fields[3]))==(28642231,122786,122786)
  state=fields[0]
 except FileNotFoundError:state='ABSENT';fields=None
 elapsed=time.monotonic()-claim['dispatch_monotonic_seconds']
 if state!=last:changes.append({'state':state,'elapsed_from_dispatch_seconds':elapsed});last=state
 if state in ('Z','X','ABSENT'):
  terminal={'state':state,'observed_elapsed_seconds':elapsed,'kernel_wait_status_if_present':int(fields[49])if fields and len(fields)>49 else None};break
 if elapsed>=615:terminal={'state':state,'observed_elapsed_seconds':elapsed,'reason':'METADATA_WATCH_LIMIT_PHYSICAL_CLOSURE_STILL_UNPROVED'};break
 time.sleep(.2)
put('NATIVE_METADATA_TERMINAL_SNAPSHOT.v1.json',{'epoch':40,'terminal':terminal,'state_changes':changes,'proof_is_not_scientific_qualification':True})
argv=['taskset','-c','0,1','/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/bin/python','-I','-B',str(observer),'--project',str(R),'--output',str(W/'SUPERVISOR_OBSERVED_CLOSURE.json'),'--strict-snapshot']
put('NATIVE_OBSERVER_ROOT_INVOCATION.v1.json',{'epoch':40,'argv':argv,'one_invocation':True,'at_monotonic':time.monotonic(),'gold_authorized':False})
t=time.monotonic();result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=R)
for name,body in [('native-observer-root.stdout',result.stdout),('native-observer-root.stderr',result.stderr)]:
 with(W/name).open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
report={'epoch':40,'observer_return_code':result.returncode,'observer_wall_seconds':time.monotonic()-t,'terminal_metadata':terminal,'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest(),'gold_authorized':False,'one_observer_invocation':True}
if (W/'SUPERVISOR_OBSERVED_CLOSURE.json').is_file():report['closure_proof_sha256']=sha(W/'SUPERVISOR_OBSERVED_CLOSURE.json')
put('NATIVE_OBSERVER_ROOT_RESULT.v1.json',report)
print(json.dumps(report,allow_nan=False))
