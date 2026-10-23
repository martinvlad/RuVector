from pathlib import Path
from datetime import datetime,timezone
import fcntl,json,time,os,uuid
s=Path(__file__).resolve().parent.parent;e=s/'epoch12';f=(s/'.loop.lock').open('a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('ACTIVE_SCOPED_RUN_STOP')
assert not (e/'lock-owner.json').exists(),'Do not overlap/repeat epoch11'
id=str(uuid.uuid4());expiry=time.time()+3600
(e/'lock-owner.json').write_text(json.dumps({'run_id':id,'pid':os.getpid(),'acquired_at':datetime.now(timezone.utc).isoformat(),'expires_unix':expiry,'scope':'RuVectorSOTAepoch12','native_calls_at_acquisition':0},indent=2)+'\n')
release=e/('release-'+id)
try:
 while time.time()<expiry and not release.exists():time.sleep(.1)
finally:
 (e/'lock-released.json').write_text(json.dumps({'run_id':id,'at':datetime.now(timezone.utc).isoformat(),'explicit_release':release.exists()},indent=2)+'\n');fcntl.flock(f,fcntl.LOCK_UN)
