from pathlib import Path
import os,sys,fcntl,json,time,stat
from datetime import datetime,timezone
s=Path(__file__).resolve().parent;p=Path('/tmp/ruvector-sota-2026-10-22/exclusive.work.lock');fd=os.open(p,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600);st=os.fstat(fd);assert stat.S_ISREG(st.st_mode)
try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
 print('ACTIVE_SCOPED_WORK_LOCK_STOP',flush=True);sys.exit(73)
now=time.time();expiry=now+7200;ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
owner={'run_id':'epoch51-0e1f4181df1f-lease16','pid':os.getpid(),'startticks':ticks,'lock':str(p),'lock_inode':st.st_ino,'lock_device':st.st_dev,'started_unix':now,'expires_unix':expiry,'started_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),'expires_at':datetime.fromtimestamp(expiry,timezone.utc).isoformat(),'CPU_affinity':sorted(os.sched_getaffinity(0)),'scope':'ruvnet/RuVector:benchmarks/ruvector-sota-2026-10-22','generation':16,'epoch':51,'purpose':'BOUNDED_RESEARCH_E51_NEW_FROZEN_CONTEXT_AND_TYPED_INFERENCE','scientific_invocation_authorized_by_lock_alone':False,'kernel_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'PID_namespace':os.readlink('/proc/self/ns/pid')}
with(s/'owner.json').open('x')as f:json.dump(owner,f);f.flush();os.fsync(f.fileno())
d=os.open(s,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
print(json.dumps(owner),flush=True)
while time.time()<expiry and not(s/'release.request').exists():
 (s/'heartbeat.txt').write_text(str(time.time()));time.sleep(1)
with(s/'released.json').open('x')as f:json.dump({'pid':os.getpid(),'released_at':datetime.now(timezone.utc).isoformat()},f);f.flush();os.fsync(f.fileno())
fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
