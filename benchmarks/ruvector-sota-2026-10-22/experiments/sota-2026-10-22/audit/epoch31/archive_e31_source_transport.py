"""Lossless closed derived-cache archival only; no eviction or science calls."""
import argparse,fcntl,gzip,hashlib,json,os,stat,subprocess,sys,tarfile,time
from pathlib import Path
S=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa')
PLAN_SHA='fae1865b699b8511cbce42f79f60bf566fbec6fd24e6af20ea942498d09cdb30'
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def syncdir(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def put(path,value):
 with path.open('x')as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 syncdir(path.parent)
def safe(path):
 p=Path(path).absolute();assert p==p.resolve()and not any(q.is_symlink()for q in(p,*p.parents));return p
def guard():
 subprocess.run([sys.executable,'-B',str(S/'mutation_guard.py'),'guard'],check=True,capture_output=True,text=True)
def check(row):
 p=safe(row['path']);st=p.lstat();assert stat.S_ISREG(st.st_mode)
 for key,actual in [('inode',st.st_ino),('dev',st.st_dev),('nlink',st.st_nlink),('bytes',st.st_size),('mode',stat.S_IMODE(st.st_mode)),('mtime_ns',st.st_mtime_ns),('ctime_ns',st.st_ctime_ns)]:assert row[key]==actual,(str(p),key)
 assert st.st_nlink==1 and digest(p)==row['sha256'];return p
class Capped:
 def __init__(self,f,cap):self.f,self.cap=f,cap
 def write(self,b):
  if self.f.tell()+len(b)>self.cap:raise RuntimeError('Prospective archive output cap exceeded; originals unchanged')
  return self.f.write(b)
 def tell(self):return self.f.tell()
 def flush(self):return self.f.flush()
def strict_verify(output,rows,cap):
 import zlib
 payload=output.read_bytes();assert len(payload)<=cap and payload[:10]==bytes.fromhex('1f8b08000000000000ff')
 decoder=zlib.decompressobj(31);body=decoder.decompress(payload)+decoder.flush()
 assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
 assert len(body)<=sum(512+((r['bytes']+511)//512)*512 for r in rows)+10240
 offset=0
 for row in rows:
  info=tarfile.TarInfo(row['member']);info.size=row['bytes'];info.mode=0o600;info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
  assert body[offset:offset+512]==info.tobuf(format=tarfile.USTAR_FORMAT);offset+=512
  data=body[offset:offset+row['bytes']];assert len(data)==row['bytes']and hashlib.sha256(data).hexdigest()==row['sha256'];offset+=row['bytes']
  padding=(-row['bytes'])%512;assert body[offset:offset+padding]==bytes(padding);offset+=padding
 assert len(body)-offset>=1024 and len(body)%512==0 and not any(body[offset:])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--phase',choices=['e31_source_transport'],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--cap',type=int,required=True);args=ap.parse_args();guard()
 assert digest(args.plan)==PLAN_SHA;plan=json.loads(args.plan.read_text());assert plan['checks_passed']is True and len(plan['files'])==9
 rows=[r for r in plan['files']if r['phase']==args.phase];assert len(rows)==9
 assert args.cap==plan['archive_cap_bytes']==4000000
 assert str(args.output.absolute())==plan['archive_output']
 assert digest(Path(plan['current_WAL_journal']['path']))==plan['current_WAL_journal']['sha256']
 assert digest(Path(plan['source_stage_metadata']['path']))==plan['source_stage_metadata']['sha256']
 protected={(r['dev'],r['inode'])for r in plan['current_WAL_request_files_protected']}
 assert all((r['dev'],r['inode'])not in protected and r['path']not in {x['path']for x in plan['current_WAL_request_files_protected']}for r in rows)
 assert all(safe(r['path']).parent==S/'stage-source/transport'for r in rows)
 output=safe(args.output);assert not output.exists();output.parent.mkdir(mode=0o700,parents=True,exist_ok=True);safe(output.parent)
 v=os.statvfs(output.parent);assert 0<args.cap<=v.f_bavail*v.f_frsize-2097152
 names=set()
 for row in rows:
  assert row['member']not in names and len(row['member'].encode())<=100 and not row['member'].startswith('/')and all(x not in('','..','.')for x in row['member'].split('/'));names.add(row['member']);check(row)
 receipt=output.with_name(output.name+'.receipt.json');started=time.time()
 with output.open('xb')as raw:
  with gzip.GzipFile(filename='',mode='wb',fileobj=Capped(raw,args.cap),compresslevel=6,mtime=0)as zipped:
   with tarfile.open(fileobj=zipped,mode='w|',format=tarfile.USTAR_FORMAT)as archive:
    for row in rows:
     p=check(row);info=tarfile.TarInfo(row['member']);info.size=row['bytes'];info.mode=0o600;info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
     with p.open('rb')as f:archive.addfile(info,f)
     check(row)
  raw.flush();os.fsync(raw.fileno())
 syncdir(output.parent);seen=set();expected={r['member']:r for r in rows}
 with tarfile.open(output,'r:gz')as archive:
  for member in archive:
   assert member.type==tarfile.REGTYPE and not member.pax_headers and member.name in expected and member.name not in seen
   row=expected[member.name];assert member.size==row['bytes'];h=hashlib.sha256();n=0
   with archive.extractfile(member)as f:
    for b in iter(lambda:f.read(1048576),b''):h.update(b);n+=len(b)
   assert n==row['bytes']and h.hexdigest()==row['sha256'];seen.add(member.name)
 assert seen==names
 strict_verify(output,rows,args.cap)
 assert digest(Path(plan['current_WAL_journal']['path']))==plan['current_WAL_journal']['sha256']
 for row in rows:check(row)
 guard()
 result={'epoch':31,'phase':args.phase,'scope':'ONLY9CURRENT_E31_SOURCE_DERIVED_TRANSPORT_PAYLOADS_NO_EVICTION','plan_sha256':PLAN_SHA,'archive':{'path':str(output),'bytes':output.stat().st_size,'sha256':digest(output)},'member_count':len(rows),'all_member_bytes_and_sha256_verified':True,'original_payloads_removed':False,'archive_output_cap_bytes':args.cap,'wall_seconds':time.time()-started,'native_model_paid_GPU_Git_calls':0,'FD_scope':'Known successful SOURCE publication/actualreadback; thiswriter performs no FD sweep and no unlink. Any retained descriptor content is unchanged; later realized freed allocation must be independently measured.'}
 put(receipt,result);print(json.dumps(result))
if __name__=='__main__':main()
