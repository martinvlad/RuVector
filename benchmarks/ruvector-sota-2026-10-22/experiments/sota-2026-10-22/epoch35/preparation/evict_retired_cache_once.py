import hashlib,json,os,stat,time
from pathlib import Path
from mutation_guard import guard
W=Path(__file__).parent
p=Path('/workspace/ruvector-eval/experiments/sota-2026-10-22/candidate/epoch11/assets/nli-large-threeway/onnx/model_quantized.onnx')
plan=Path('/workspace/ruvector-e35-independent-audit/public-e11-quant-cache-eviction-plan-independent-v1.json')
assert hashlib.sha256(plan.read_bytes()).hexdigest()=='2802ff2d54bc8f1a2eef58faf9c6098e9776b600ca4fa143fd511de6fb2a0cdf'
o=guard(); assert not json.loads((W/'remote-current/CONTINUATION.json').read_text())['active_run']['work_active']
assert not any(x.is_symlink() for x in (p,*p.parents))
s=p.stat();assert stat.S_ISREG(s.st_mode) and (s.st_dev,s.st_ino,s.st_nlink,s.st_size)==(27,1845562,1,642587600)
with p.open('rb') as f:
 h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='f28cc7e69eb2834597c5ef2336f2adb7398b7bcb019282fb3f11d0130a3c0010'
assert not any(str(x.resolve())==str(p) for x in Path('/proc/'+str(o['pid'])+'/fd').iterdir())
assert str(p) not in Path('/proc/'+str(o['pid'])+'/maps').read_text()
def put(name,v):
 with (W/name).open('x') as f: json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
before=os.statvfs(W).f_bavail*os.statvfs(W).f_frsize
put('retired-cache-eviction.intent.json',dict(path=str(p),bytes=s.st_size,sha256=h,device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,owner=o['pid'],time=time.time(),free_before=before,scope='single retired public E11 cache; metadata/source/results/champion/current runtime retained',global_FD_observability='UNKNOWN'))
guard();s2=p.stat();assert (s2.st_dev,s2.st_ino,s2.st_nlink,s2.st_size,s2.st_mtime_ns)==(s.st_dev,s.st_ino,s.st_nlink,s.st_size,s.st_mtime_ns)
os.unlink(p)
fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
assert not p.exists()
after=os.statvfs(W).f_bavail*os.statvfs(W).f_frsize
v=dict(path=str(p),unlinked_once=True,absent=True,free_before=before,free_after=after,observed_reclaimed_bytes=after-before,model_native_tokenizer_paid_GPU_calls=0,external_mutations=0,time=time.time())
put('retired-cache-eviction.response.json',v);print(json.dumps(v))
