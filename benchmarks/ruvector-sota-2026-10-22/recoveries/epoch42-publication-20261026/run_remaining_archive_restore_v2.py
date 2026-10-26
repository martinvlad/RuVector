"""Run the reviewed source-only restoration steps once, recording real outcomes."""
from pathlib import Path
import hashlib, json, os, subprocess, time

W=Path('/tmp/ruvector-sota-2026-10-22/epoch42-archive-recovery-20261026T040538'); K=W/'kit'; R=W/'project'; N='recoveries/epoch42-publication-20261026/'
commands=[
 ('epoch42-archive-restore.json',['python','-B',str(K/(N+'restore_epoch42_archive.py')),'--kit-root',str(K),'--dest',str(R),'--restore-scope',str(W),'--archive',N+'immutable-e42-artifacts.zip','--projection',N+'ARCHIVE_PROJECTED_FILES.v1.json']),
 ('legacy26-after-e42-verify.json',['python','-B',str(K/'experiments/sota-2026-10-22/epoch26/publication/restore_epoch26_archives_v1.py'),'--kit-root',str(K),'--manifest','experiments/sota-2026-10-22/epoch26/publication/archive-transport.v1.json','--expected-manifest-sha256','9b79fc0119e1e5d15470201b7180f4b39e55b687a207dac1ff9f333d91a8ef24','--verify-only']),
 ('bootstrap-source.json',['python','-B',str(K/'bootstrap.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache')]),
 ('checkpoint-restore.json',['python','-B',str(K/'restore_checkpoint.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache')]),
 ('checkpoint-verify.json',['python','-B',str(K/'restore_checkpoint.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache'),'--verify-only']),
 ('epoch42-archive-verify.json',['python','-B',str(K/(N+'restore_epoch42_archive.py')),'--kit-root',str(K),'--dest',str(R),'--restore-scope',str(W),'--archive',N+'immutable-e42-artifacts.zip','--projection',N+'ARCHIVE_PROJECTED_FILES.v1.json','--verify-only'])]

def put(p,value):
 b=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)

def main():
 assert os.sched_getaffinity(0)=={0,1}
 assert json.loads((W/'legacy22-verify.json').read_text())['exit_code']==0
 assert json.loads((W/'legacy26-verify.json').read_text())['exit_code']==1
 assert not(W/'epoch42-archive-restore.json').exists()
 source_pins={
  K/'bootstrap.py':'eceb2ca259feaf642bc81172aca57a2a209cc34cd17f9b281861c51f21b95806',
  K/'restore_checkpoint.py':'affd9ecf660f380c3632f78cd14fb7a36e00797ceb097cf48c0c60136fac0be8',
  K/(N+'restore_epoch42_archive.py'):'d44b9ee022c2f05d68edf9e3f9217f4b6d603265bcf2bc85a49ce8863d015890'}
 for p,h in source_pins.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h
 assert not any((W/name).exists()for name,_ in commands)
 put(W/'archive-restoration-remaining-v2-ONCE.json',{'started_unix':time.time(),'commands':commands,'source_pins':{str(p):h for p,h in source_pins.items()},'scientific_or_Git_calls_allowed':0})
 for name,cmd in commands:
  owner=json.loads((W/'owner.json').read_text());assert time.time()<owner['expires_unix'] and not(W/'release.request').exists()
  started=time.monotonic();result=subprocess.run(cmd,cwd=W,capture_output=True,text=True,timeout=120)
  put(W/name,{'argv':cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr.encode()).hexdigest(),'wall_seconds':time.monotonic()-started,'native_model_Gold_EVAL_Git_calls':0})
  print(json.dumps({'step':name,'exit_code':result.returncode}),flush=True)
  if result.returncode:raise SystemExit('STOP_SOURCE_RESTORATION_FAILURE_NO_AUTOMATIC_REPLAY')
 print('ALL_SIX_REMAINING_SOURCE_RESTORATION_STEPS_COMPLETED',flush=True)

if __name__=='__main__':main()
