from pathlib import Path
import os,json,hashlib,stat,gzip,tarfile,zlib,subprocess
S=Path('/tmp/ruvector-sota-2026-10-22/epoch32-f8bcbc4ca7ec')
PLAN=Path('/workspace/ruvector-e32-independent-audit/e31-final-derived-storage-plan-v2.json')
PLAN_SHA='32237a0b800b91959318e7dfdb68010e0dd1e9438fb36a58cd8a645c78ce5565'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def guard():subprocess.run(['python','-B',str(S/'mutation_guard.py'),'guard'],check=True,capture_output=True)
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def check(r):
 p=Path(r['path']);t=p.lstat();assert p==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents))and stat.S_ISREG(t.st_mode)
 assert(t.st_dev,t.st_ino,t.st_nlink,t.st_size,stat.S_IMODE(t.st_mode),t.st_mtime_ns,t.st_ctime_ns)==(r['dev'],r['inode'],1,r['bytes'],r['mode'],r['mtime_ns'],r['ctime_ns'])
 assert sha(p)==r['sha256'];return p
class Cap:
 def __init__(self,f,n):self.f,self.n=f,n
 def write(self,b):
  assert self.f.tell()+len(b)<=self.n,'archive cap';return self.f.write(b)
 def flush(self):self.f.flush()
 def tell(self):return self.f.tell()
def main():
 guard();assert sha(PLAN)==PLAN_SHA;p=json.loads(PLAN.read_text());assert p['checks_passed']and len(p['files'])==15
 for r in p['files']:check(r)
 a=p['archive_recipe'];out=Path(a['output_proposed']);assert out.parent==PLAN.parent and not out.exists()and not out.is_symlink()
 v=os.statvfs(out.parent);assert v.f_bavail*v.f_frsize>a['output_cap_bytes']+1048576
 for r in p['WAL']['journals']:assert sha(r['path'])==r['sha256']
 with out.open('xb')as raw:
  with gzip.GzipFile(filename='',mode='wb',fileobj=Cap(raw,a['output_cap_bytes']),compresslevel=6,mtime=0)as z:
   with tarfile.open(fileobj=z,mode='w|',format=tarfile.USTAR_FORMAT)as t:
    for r in p['files']:
     src=check(r);info=tarfile.TarInfo(r['member']);info.size=r['bytes'];info.mode=0o600;info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
     with src.open('rb')as f:t.addfile(info,f)
     check(r)
  raw.flush();os.fsync(raw.fileno())
 d=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
 payload=out.read_bytes();assert len(payload)==a['measured_in_memory_bytes'] and sha(out)==a['measured_in_memory_sha256']
 de=zlib.decompressobj(31);limit=sum(512+((r['bytes']+511)//512)*512 for r in p['files'])+10240
 body=de.decompress(payload,limit+1);assert de.eof and not de.unused_data and not de.unconsumed_tail and len(body)<=limit
 offset=0
 for r in p['files']:
  info=tarfile.TarInfo(r['member']);info.size=r['bytes'];info.mode=0o600;info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
  assert body[offset:offset+512]==info.tobuf(format=tarfile.USTAR_FORMAT);offset+=512
  assert hashlib.sha256(body[offset:offset+r['bytes']]).hexdigest()==r['sha256'];offset+=r['bytes'];n=(-r['bytes'])%512;assert body[offset:offset+n]==bytes(n);offset+=n
 assert len(body)-offset>=1024 and len(body)%512==0 and not any(body[offset:])
 for r in p['files']:check(r)
 for r in p['WAL']['journals']:assert sha(r['path'])==r['sha256']
 guard();receipt={'epoch':32,'purpose':'Verified lossless retention of15closedE31derived publication-cache files; originals untouched','plan_sha256':PLAN_SHA,'archive':{'path':str(out),'bytes':len(payload),'sha256':sha(out)},'strict_all15_members_SHA_USTAR_GZIP_CRC_EOF_verified':True,'originals_removed':False,'no_WAL_project_raw_controls_or_model_changes':True,'native_model_gold_paid_GPU_Git_calls':0}
 put(S/'e31-final-derived-archive-receipt.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':main()

