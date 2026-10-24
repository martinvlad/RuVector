"""Restore exact archived successful E21 request bytes only; never replay requests."""
import argparse,fcntl,hashlib,json,os,stat,tarfile,time
from pathlib import Path
PREFIX=Path('/tmp/ruvector-sota-2026-10-22/epoch21-dd6da5427108/stage-final/transport')
LOCK=Path('/tmp/ruvector-sota-2026-10-22/exclusive.work.lock')
def sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def safe(path):
 p=Path(path).absolute();assert p==p.resolve()and not any(q.is_symlink()for q in(p,*p.parents));return p
def ref(row):
 p=safe(row['path']);assert p.stat().st_size==row['bytes']and sha(p)==row['sha256'];return p
def guard(owner_path):
 owner=json.loads(safe(owner_path).read_text());pid=owner['pid'];row=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
 assert row[0]not in('Z','X')and int(row[19])==owner['startticks']and time.time()<owner['expires_unix']
 assert owner['scope']=='ruvnet/RuVector:benchmarks/ruvector-sota-2026-10-22'and owner['lock']==str(LOCK)
 assert owner['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()and owner['PID_namespace']==os.readlink('/proc/self/ns/pid')
 st=safe(LOCK).stat();other=Path('/proc/'+str(pid)+'/fd/3').stat();assert(st.st_dev,st.st_ino)==(other.st_dev,other.st_ino)and st.st_ino==owner['lock_inode']
 held=False
 for line in Path('/proc/locks').read_text().splitlines():
  words=line.split()
  if len(words)>=8 and words[1:5]==['FLOCK','ADVISORY','WRITE',str(pid)]:
   a,b,c=words[5].split(':');held|=(int(a,16),int(b,16),int(c))==(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
 assert held
 with LOCK.open('rb')as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:fcntl.flock(f,fcntl.LOCK_UN);raise ValueError('Exclusive authorized owner absent')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--index',type=Path,required=True);ap.add_argument('--index-sha256',required=True);ap.add_argument('--restore',action='store_true');ap.add_argument('--owner',type=Path);a=ap.parse_args()
 assert sha(safe(a.index))==a.index_sha256;d=json.loads(a.index.read_text());assert d['kind']=='LOSSLESS_SUCCESSFUL_LEGACY_WAL_PAYLOAD_RELOCATION'and d['request_count']==16
 assert sha(Path(__file__))==d['restore_tool']['sha256'];ref(d['legacy_journal']);archive=ref(d['archive']);rows={r['member']:r for r in d['files']};assert len(rows)==16
 if a.restore:
  assert a.owner is not None;guard(a.owner)
 seen=set();restored=0
 with tarfile.open(archive,'r:gz')as tar:
  for m in tar:
   assert m.type==tarfile.REGTYPE and not m.pax_headers and m.name in rows and m.name not in seen
   row=rows[m.name];target=safe(row['path']);assert target.parent==PREFIX and row['mode']in(0o600,0o644)and m.size==row['bytes']
   with tar.extractfile(m)as f:b=f.read(row['bytes']+1)
   assert len(b)==row['bytes']and hashlib.sha256(b).hexdigest()==row['sha256'];seen.add(m.name)
   if target.exists():assert target.is_file()and target.stat().st_size==row['bytes']and sha(target)==row['sha256'];continue
   if a.restore:
    guard(a.owner);safe(target.parent);tmp=target.with_name(target.name+'.restore-'+row['sha256'][:12]);fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,row['mode'])
    with os.fdopen(fd,'wb')as out:out.write(b);out.flush();os.fsync(out.fileno())
    assert sha(tmp)==row['sha256'];os.link(tmp,target,follow_symlinks=False);tmp.unlink();directory=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory);assert sha(target)==row['sha256'];restored+=1
 assert seen==set(rows)
 print(json.dumps({'members_fully_verified':len(seen),'original_missing_paths_restored':restored,'mode':'restore'if a.restore else'verify-only','historical_inode_or_ctime_restoration_claim':False,'WAL_journal_rewritten':False,'Git_native_model_or_label_calls':0}))
if __name__=='__main__':main()
