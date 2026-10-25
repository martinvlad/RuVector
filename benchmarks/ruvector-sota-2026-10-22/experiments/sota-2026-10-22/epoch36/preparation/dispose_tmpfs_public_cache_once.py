"""Exact reviewed optional old public-cache aliases only; one fsynced unlink each."""
from pathlib import Path
import hashlib,json,os,re,stat,time
from mutation_guard import guard
W=Path('/workspace/ruvector-epoch36-d73fcce4c45f')
B=Path('/tmp/ruvector-sota-2026-10-22')
assert Path(__file__).absolute()==W/'dispose_tmpfs_public_cache_once.py'
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def log(v):
 first=not(W/'tmpfs-cache-unlink-journal.jsonl').exists()
 with(W/'tmpfs-cache-unlink-journal.jsonl').open('a')as f:f.write(json.dumps(v,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 if first:
  fd=os.open(W,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def snapshot():
 c=Path('/sys/fs/cgroup');s=os.statvfs('/tmp')
 return {'tmp_free_bytes':s.f_bavail*s.f_frsize,'cgroup_memory_current_bytes':int((c/'memory.current').read_text()),'cgroup_memory_stat_bytes':{k:int(v)for k,v in map(str.split,(c/'memory.stat').read_text().splitlines())}}
guard();ad=W/'TMPFS_CACHE_CLEANUP_ADMISSION.json';a=json.loads(ad.read_text())
assert a['epoch']==36 and a['independent_plan_approved']is True and a['allowed_unlink_attempts_per_path']==1
p=Path(a['plan_path']);assert p.parent==Path('/workspace/ruvector-e36-independent-audit') and sha(p)==a['plan_sha256']
j=json.loads(p.read_text());assert j['checks_passed'] and j['actual_base_commit']=='d73fcce4c45f7d8f6f1c5bfbf3599ceddf560be3' and j['all_selected_nlink_aliases_within_exact_plan']
groups=[]
for r in j['selected_groups_parts']:
 q=p.parent/r['path'];assert q.parent==p.parent and q.stat().st_size==r['bytes']and sha(q)==r['sha256'];groups+=json.loads(q.read_text())['selected_groups']
assert len(groups)==a['groups']==j['selected_groups_count'] and sum(len(g['paths'])for g in groups)==a['paths']==j['selected_paths_count']
assert len({(g['device'],g['inode'])for g in groups})==len(groups)
allpaths=[n for g in groups for n in g['paths']];assert len(allpaths)==len(set(allpaths))
memberpath=W/'project/experiments/sota-2026-10-22/epoch26/preparation/runtime-members/python-wheel-members.json'
assert sha(memberpath)=='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'
members=json.loads(memberpath.read_text());assert len(members)==17498 and len({r['path']for r in members})==17498
venv=B/'epoch33-0522a2c521c9/runtime/.venv'
protected={(s.st_dev,s.st_ino)for s in [(venv/r['path']).stat()for r in members]}
for g in groups:
 assert g['nlink']==len(g['paths'])and g['nlink']>0 and(g['device'],g['inode'])not in protected and g['device']==B.stat().st_dev
 assert g['kind']in a['allowed_kinds']
 for n in g['paths']:
  q=Path(n);assert q.is_relative_to(B)and not any(x in n for x in ['/../','/epoch33-','/epoch35-','/epoch36-'])
  first=q.relative_to(B).parts[0];m=re.fullmatch(r'epoch(\d+)-[A-Za-z0-9_-]+',first);assert m and 15<=int(m.group(1))<=31
for old in j['old_guardian_physical_observations']:
 q=Path('/proc')/str(old['pid'])/'stat'
 if q.exists():
  f=q.read_text().rsplit(')',1)[1].split();assert f[0]in('Z','X')or int(f[19])!=old['observed_startticks']
assert not(W/'TMPFS_CACHE_UNLINK_RESERVATION.json').exists()and not(W/'tmpfs-cache-unlink-journal.jsonl').exists()and not(W/'tmpfs-cache-unlink-completed.json').exists()
before=snapshot();put(W/'TMPFS_CACHE_UNLINK_RESERVATION.json',{'epoch':36,'admission_sha256':sha(ad),'plan_sha256':a['plan_sha256'],'groups':len(groups),'paths':len(allpaths),'before':before,'started_unix':time.time(),'global_FD_mmap_observability':'UNKNOWN; selected known old owners closed, current exact G33 inodes protected','no_retry':True})
started=time.monotonic();removed=0
for gi,g in enumerate(groups):
 for ai,name in enumerate(g['paths']):
  guard();q=Path(name);assert not any(x.is_symlink()for x in(q,*q.parents));fd=os.open(q,os.O_RDONLY|os.O_NOFOLLOW)
  try:
   s=os.fstat(fd);assert stat.S_ISREG(s.st_mode)and(s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns)==(g['device'],g['inode'],g['bytes'],g['nlink']-ai,g['mtime_ns'])
   with os.fdopen(os.dup(fd),'rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   assert h==g['sha256'];z=os.fstat(fd);t=q.stat();assert(s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_nlink,z.st_mtime_ns,z.st_ctime_ns)and(t.st_dev,t.st_ino)==(s.st_dev,s.st_ino)
   ident=f'g{gi}-a{ai}';log({'id':ident,'phase':'intent','path':name,'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'nlink':s.st_nlink,'sha256':h,'time':time.time()})
   os.unlink(q);pd=os.open(q.parent,os.O_DIRECTORY);os.fsync(pd);os.close(pd)
  finally:os.close(fd)
  assert not q.exists();log({'id':ident,'phase':'response','ok':True,'absent':True,'time':time.time()});removed+=1
  if removed%10000==0:print(json.dumps({'unlinked_once':removed,'total':len(allpaths)}),flush=True)
after=snapshot();v={'epoch':36,'status':'EXACT_REVIEWED_PUBLIC_TMPFS_CACHE_UNLINKS_COMPLETED','groups':len(groups),'paths_unlinked_once':removed,'before':before,'after':after,'observed_tmp_free_increase_bytes':after['tmp_free_bytes']-before['tmp_free_bytes'],'wall_seconds':time.monotonic()-started,'plan_sha256':a['plan_sha256'],'journal_bytes':(W/'tmpfs-cache-unlink-journal.jsonl').stat().st_size,'journal_sha256':sha(W/'tmpfs-cache-unlink-journal.jsonl'),'uncertain_outcomes':0,'Git_model_native_tokenizer_scoring_calls':0,'current_data_runtime_champion_or_private_files_touched':False,'resource_feasibility':'Requires separate unchanged frozen prospective host admission after this process exits; no claim from estimated cache blocks.'}
put(W/'tmpfs-cache-unlink-completed.json',v);print(json.dumps(v),flush=True)
