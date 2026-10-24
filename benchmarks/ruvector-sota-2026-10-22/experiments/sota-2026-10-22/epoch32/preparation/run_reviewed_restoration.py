from pathlib import Path
import subprocess,json,os,hashlib
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');K=W/'kit';R=W/'project'
commands=[
('archive22-proof.json',['python','-B',str(K/'experiments/sota-2026-10-22/epoch22/publication/restore_archived_artifact_v1.py'),'--kit-root',str(K),'--archive','experiments/sota-2026-10-22/epoch22/publication/actualarchive.dev.raw.v1.json','--expected-archive-sha256','8ab3d8ec7856b423e6ff295f8e5ef74fc81dcaa3d3382fa2757e21563e0a99c6','--verify-only']),
('archive26-proof.json',['python','-B',str(K/'experiments/sota-2026-10-22/epoch26/publication/restore_epoch26_archives_v1.py'),'--kit-root',str(K),'--manifest','experiments/sota-2026-10-22/epoch26/publication/archive-transport.v1.json','--expected-manifest-sha256','9b79fc0119e1e5d15470201b7180f4b39e55b687a207dac1ff9f333d91a8ef24','--verify-only']),
('bootstrap-proof.json',['python','-B',str(K/'bootstrap.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache')]),
('restore-proof.json',['python','-B',str(K/'restore_checkpoint.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache')]),
('restore-verify-proof.json',['python','-B',str(K/'restore_checkpoint.py'),'--dest',str(R),'--base-local-directory',str(W/'base-cache'),'--verify-only'])]
for name,cmd in commands:
 p=W/name;assert not p.exists();v=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
 result={'argv':cmd,'exit_code':v.returncode,'stdout_sha256':hashlib.sha256(v.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(v.stderr.encode()).hexdigest(),'stdout':v.stdout,'stderr':v.stderr,'no_implicit_model_native_paid_GPU_calls':True}
 with p.open('x')as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
 print(json.dumps({'step':name,'exit_code':v.returncode}),flush=True)
 if v.returncode:raise SystemExit('RESTORATION_STOP_REVIEW_CAPTURED_FAILURE')
print('REVIEWED_BOOTSTRAP_RESTORE_AND_DECODERS_COMPLETED_ALL_HASHES')

