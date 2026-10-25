"""One root-authorized opaque 8.6MB identity pass; no JSON/tokenizer/model use."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,signal,stat,time
OUT=Path('/workspace/ruvector-e40-model-source-audit/actual-admission-review')
FILE=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05/reader-assets/tasksource-212de447184b/tokenizer.json')
SIZE=8656843
GIT='18edee8d415256429ac65609c6b31df913abc06d'
started=time.monotonic();stamp=datetime.now(timezone.utc).isoformat()
def stop(sig,frame):raise TimeoutError('INDEPENDENT_TOKENIZER_IDENTITY30_SECONDS')
signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,30)
if os.sched_getaffinity(0)!={0,1}:raise ValueError('EXACT_CPU01_REQUIRED')
for p in(FILE,*FILE.parents):
 if p.is_symlink():raise ValueError('TOKENIZER_SOURCE_SYMLINK_REFUSED')
before=FILE.stat()
if not stat.S_ISREG(before.st_mode)or before.st_size!=SIZE or before.st_mode&0o222:raise ValueError('EXACT_READONLY_SOURCE_TOKENIZER_REQUIRED')
fd=os.open(FILE,os.O_RDONLY|os.O_NOFOLLOW);h=hashlib.sha256();g=hashlib.sha1(b'blob '+str(SIZE).encode()+b'\0');count=0
try:
 opened=os.fstat(fd)
 if(opened.st_dev,opened.st_ino,opened.st_size)!=(before.st_dev,before.st_ino,before.st_size):raise ValueError('TOKENIZER_OPEN_IDENTITY_CHANGED')
 while True:
  body=os.read(fd,1048576)
  if not body:break
  count+=len(body)
  if count>SIZE:raise ValueError('TOKENIZER_BYTES_EXCEED_SOURCE')
  h.update(body);g.update(body)
 after=os.fstat(fd)
finally:os.close(fd)
stable=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)
if stable(before)!=stable(after)or stable(before)!=stable(FILE.stat())or count!=SIZE or g.hexdigest()!=GIT:raise ValueError('TOKENIZER_NOT_EXACT_PUBLISHER_GIT_BODY')
elapsed=time.monotonic()-started
if elapsed>30:raise TimeoutError('TOKENIZER_IDENTITY_BOUND_EXCEEDED')
row={'schema_version':1,'epoch':40,'checked_at':stamp,'path':str(FILE),'bytes':count,'sha256':h.hexdigest(),'publisher_Git_blob_SHA1':g.hexdigest(),'expected_publisher_Git_blob_SHA1':GIT,'size_and_publisher_Git_identity_verified_before_SHA256_admission':True,'opaque_byte_passes':1,'JSON_parses':0,'tokenizer_or_model_initializations':0,'other_model_payload_reads':0,'CPU_affinity':sorted(os.sched_getaffinity(0)),'wall_seconds':elapsed,'source_inode':{'device':before.st_dev,'inode':before.st_ino,'mode_octal':oct(stat.S_IMODE(before.st_mode))},'file_stat_stable':True}
b=(json.dumps(row,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
with(OUT/'TOKENIZER_IDENTITY_DERIVATION.once.json').open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
signal.setitimer(signal.ITIMER_REAL,0)
print(json.dumps({'bytes':count,'sha256':h.hexdigest(),'Git_blob_SHA1':g.hexdigest(),'opaque_byte_passes':1,'JSON_parses':0,'wall_seconds':elapsed}))
