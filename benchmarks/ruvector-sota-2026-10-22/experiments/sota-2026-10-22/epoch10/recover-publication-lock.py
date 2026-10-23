from pathlib import Path
from datetime import datetime,timezone
import json,os,fcntl,time,hashlib
s=Path('/workspace/ruvector-eval/experiments/sota-2026-10-22');e=s/'epoch10';p=e/'publication';p.mkdir(exist_ok=True);owner=json.loads((e/'lock-owner.json').read_text());assert owner['run_id']=='35c0d6af-5d4c-4ad4-8412-13ce361772d3';assert time.time()<owner['expires_unix'];assert not Path('/proc/'+str(owner['pid'])).exists();assert json.loads((e/'study-completion.json').read_text())['status']=='REJECTED_DEV_GATE'
f=(s/'.loop.lock').open('a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('ACTIVE_OTHER_SCOPED_RUN_STOP')
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
plan=json.loads((e/'plan.json').read_text());pr=e/'project';assert sha(e/'plan.json')=='eb6f040d544e83632830921281bda98deb740c70a176c54d2b2e5c9d8d86fb84'==sha(pr/'experiments/sota-2026-10-22/epoch10/plan.json')
for x in plan['pins']:assert sha(pr/x['path'])==x['sha256']
snap=json.loads((e/'actual-snapshot.json').read_text())
for x in snap['files']:
 for q in (e/x['path'],pr/'experiments/sota-2026-10-22/epoch10'/x['path']):assert q.stat().st_size==x['bytes'] and sha(q)==x['sha256']
files=json.loads((e/'durable-files.json').read_text())['files']
for x in files:
 b=(e/'durable-kit'/x['path']).read_bytes();assert len(b)==x['bytes'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1']
run=e/'runs/development';runtime=json.loads((run/'runtime.json').read_text());attempt=json.loads((run/'attempt.json').read_text());pids=[owner['pid'],attempt['pid'],*runtime['native_child_pids']];assert all(not Path('/proc/'+str(i)).exists() for i in pids)
def save(n,x):(p/n).write_text(json.dumps(x,indent=2)+'\n')
save('publication-lock-recovered.json',{'run_id':owner['run_id'],'pid':os.getpid(),'old_pid':owner['pid'],'old_pid_absent':True,'at':datetime.now(timezone.utc).isoformat(),'expires_unix':owner['expires_unix'],'scope':'Publication-only OSlock recovery following managed runtime reset AFTER terminal actualphase; exact same unexpiredglobalGitlease24e671/UUID/expiry. No sourcechange/retry or newmeasurements. Fresh connectedref+ACTIVE_RUNidentity checked before acquisition.','frozen_plan_pins_verified':len(plan['pins']),'raw_snapshot_files_verified_both_projects':len(snap['files']),'durable_Git_blob_hashes_verified':len(files),'old_owned_PIDs_absent':pids,'native_model_paid_calls_during_recovery':0})
release=p/('release-publication-'+owner['run_id'])
try:
 while time.time()<owner['expires_unix'] and not release.exists():time.sleep(.1)
finally:
 save('publication-lock-released.json',{'run_id':owner['run_id'],'at':datetime.now(timezone.utc).isoformat(),'explicit_release':release.exists()});fcntl.flock(f,fcntl.LOCK_UN)
