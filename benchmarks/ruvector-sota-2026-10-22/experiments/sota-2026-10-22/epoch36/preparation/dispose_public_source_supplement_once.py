from pathlib import Path
import hashlib,json,os,stat,time
from mutation_guard import guard
W=Path(__file__).parent
PLAN=Path('/workspace/ruvector-e36-independent-audit/public-source-cache-supplement-independent-v1.json')
assert hashlib.sha256(PLAN.read_bytes()).hexdigest()=='71f4280f5d426e525efe6afdaf3def7541dd5b148dbfb5cfb2189264d3f29078'
J=json.loads(PLAN.read_text());assert J['checks_passed'] and J['all_selected_linksets_complete'] and J['all_old_and_current_private_runtime_model_weights_CONF_champion_Qwen_swarm_database_exclusions_preserved']
assert J['actual_base']=='d73fcce4c45f7d8f6f1c5bfbf3599ceddf560be3'
groups=J['selected_groups'];assert len(groups)==665 and sum(len(g['paths'])for g in groups)==1278
roots=[Path(r)for r in J['source_scope_roots']]
prior=json.loads(Path('/workspace/ruvector-e36-independent-audit/exact-public-cache-disposal-plan-independent-v1.json').read_text())
assert all(not Path(n).exists()for g in prior['optional_weights']+prior['old_published_source_groups']for n in g['paths'])
for group in groups:
 assert group['bytes']<1048576 and group['nlink']==len(group['paths']) and len(set(group['paths']))==len(group['paths'])
 for n in group['paths']:
  assert any(Path(n).is_relative_to(r)for r in roots)and '/ruvector-epoch35-'not in n and '/ruvector-epoch36-'not in n
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def log(v):
 with(W/'public-source-cache-supplement-journal.jsonl').open('a')as f:f.write(json.dumps(v,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 fd=os.open(W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
guard();assert not(W/'PUBLIC_SOURCE_CACHE_SUPPLEMENT_RESERVATION.json').exists();assert not(W/'public-source-cache-supplement-journal.jsonl').exists()
before=os.statvfs(W).f_bavail*os.statvfs(W).f_frsize
put(W/'PUBLIC_SOURCE_CACHE_SUPPLEMENT_RESERVATION.json',dict(epoch=36,attempt=1,groups=665,paths=1278,plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),free_before=before,global_FD_observability='UNKNOWN',scope='Separate remaining exact old published source-cache aliases only; no prior unlinks replayed; all durable Git/source/failure artifacts and latest donor preserved.',time=time.time()))
removed=0;start=time.monotonic()
for gi,g in enumerate(groups):
 for ai,name in enumerate(g['paths']):
  guard();p=Path(name);assert not any(q.is_symlink()for q in(p,*p.parents))
  fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
  try:
   s=os.fstat(fd);assert stat.S_ISREG(s.st_mode) and(s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns)==(g['device'],g['inode'],g['bytes'],g['nlink']-ai,g['mtime_ns'])
   with os.fdopen(os.dup(fd),'rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   assert h==g['sha256'];s2=os.fstat(fd);ps=p.stat();assert(s2.st_dev,s2.st_ino,s2.st_size,s2.st_nlink,s2.st_mtime_ns,s2.st_ctime_ns)==(s.st_dev,s.st_ino,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns);assert(ps.st_dev,ps.st_ino)==(s.st_dev,s.st_ino)
   ident=f'g{gi:03d}-a{ai}'
   log(dict(id=ident,phase='intent',path=name,device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,bytes=s.st_size,sha256=h,time=time.time()))
   os.unlink(p);pd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(pd);os.close(pd)
  finally:os.close(fd)
  assert not p.exists();log(dict(id=ident,phase='response',ok=True,absent=True,time=time.time()));removed+=1
after=os.statvfs(W).f_bavail*os.statvfs(W).f_frsize
v=dict(epoch=36,status='EXACT_PUBLIC_SOURCE_CACHE_SUPPLEMENT_COMPLETED',groups=665,paths_unlinked_once=removed,free_before=before,free_after=after,observed_reclaimed_bytes=after-before,wall_seconds=time.monotonic()-start,Git_or_model_native_tokenizer_scoring_calls=0,uncertain_outcomes=0,other_files_touched=False)
put(W/'public-source-cache-supplement-completed.json',v);print(json.dumps(v))
