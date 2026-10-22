from pathlib import Path
from datetime import datetime,timezone
import fcntl,json,time,os,uuid
s=Path(__file__).resolve().parent.parent;e=s/'epoch9';f=(s/'.loop.lock').open('a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('ACTIVE_SCOPED_RUN_STOP')
id=str(uuid.uuid4());expiry=time.time()+3600
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
save(e/'lock-owner.json',{'run_id':id,'pid':os.getpid(),'acquired_at':datetime.now(timezone.utc).isoformat(),'expires_unix':expiry,'scope':'RuVectorSOTAepoch9','native_calls':0})
release=e/('release-'+id)
try:
 while time.time()<expiry and not release.exists():time.sleep(.1)
finally:
 save(e/'lock-released.json',{'run_id':id,'at':datetime.now(timezone.utc).isoformat(),'explicit_release':release.exists()});fcntl.flock(f,fcntl.LOCK_UN)
