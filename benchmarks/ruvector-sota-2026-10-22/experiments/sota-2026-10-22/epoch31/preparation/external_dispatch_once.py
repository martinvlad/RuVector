"""One detached invocation of the frozen E31 supervisor; no model imports."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
S=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa')
R=S/'project';E=R/'experiments/sota-2026-10-22/epoch31'
PLAN_SHA='b1f63e8f0df4558c2eb91c856f7d98451f76f738ab375a6158e95b4f973b7196'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def main():
 subprocess.run([sys.executable,'-B',str(S/'mutation_guard.py'),'guard'],check=True,capture_output=True)
 assert sha(E/'plan.json')==PLAN_SHA;p=json.loads((E/'plan.json').read_text());a=json.loads((E/'SOURCE_ADMISSION.json').read_text())
 assert a['verified_actual_remote_readback']is True and a['plan_sha256']==PLAN_SHA and a['source_freeze_sha256']==p['source_freeze_sha256']
 for row in p['pins']:
  q=R/row['path'];assert not any(x.is_symlink()for x in(q,*q.parents))and q.stat().st_size==row['bytes']and sha(q)==row['sha256']
 for name in ['DISPATCH_RESERVATION.json','DISPATCH_ATTEMPT.json','DEV_ATTEMPT_RESERVATION.json','SUPERVISOR_COMPLETION.json','SUPERVISOR_OBSERVED_CLOSURE.json','runs/dev']:
  assert not(E/name).exists(),'Already consumed or uncertain E31: '+name
 assert a['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and a['pid_namespace_inode']==os.stat('/proc/self/ns/pid').st_ino
 stdout=S/'supervisor.stdout';stderr=S/'supervisor.stderr'
 with stdout.open('xb')as out,stderr.open('xb')as err:
  claim={'schema_version':1,'epoch':31,'kind':p['kind'],'phase':'dev','plan_sha256':PLAN_SHA,'source_freeze_sha256':p['source_freeze_sha256'],'archived_model_seal_sha256':p['archived_model_seal_sha256'],'admission_sha256':sha(E/'SOURCE_ADMISSION.json'),'kernel_boot_id':a['kernel_boot_id'],'pid_namespace_inode':a['pid_namespace_inode'],'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time(),'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
  put(E/'DISPATCH_RESERVATION.json',claim)
  argv=['taskset','-c','0,1',p['inference_python'],'-I','-B',str(R/'experiments/sota-2026-10-22/candidate/epoch31/runtime/launch.py'),'--scope',str(S),'--phase','dev','--plan',str(E/'plan.json'),'--admission',str(E/'SOURCE_ADMISSION.json'),'--expected-plan-sha',PLAN_SHA]
  try:
   child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,close_fds=True,cwd=R)
   fields=Path('/proc/'+str(child.pid)+'/stat').read_text().rsplit(')',1)[1].split();pid=child.pid;assert int(fields[2])==pid and int(fields[3])==pid
   attempt={**claim,'pid':pid,'startticks':int(fields[19]),'pgid':pid,'sid':pid,'verified_launcher_start':True,'uncertain_launcher_start':False};put(E/'DISPATCH_ATTEMPT.json',attempt)
   put(S/'dispatch-observer-receipt.json',{'supervisor_identity':{k:attempt[k]for k in ['pid','startticks','pgid','sid']},'stdout':str(stdout),'stderr':str(stderr),'detached_supervisor_exit_code_observed':False,'allowed_further_dispatches':0,'dispatch_controller_sha256':sha(Path(__file__))})
  except BaseException as error:
   put(S/'dispatch-error.json',{'error_type':type(error).__name__,'error':str(error),'dispatch_budget_consumed':1,'actual_supervisor_or_model_start':'UNKNOWN_UNLESS_MATCHING_DURABLE_IDENTITY_PROOF','allowed_further_dispatches':0});raise
 print(json.dumps({'dispatched_once':True,'supervisor_identity':{k:attempt[k]for k in ['pid','startticks','pgid','sid']},'budget_reserved':1,'MODEL_calls_by_bootstrap':0,'supervisor_exit_code_observed':False}))
if __name__=='__main__':main()
