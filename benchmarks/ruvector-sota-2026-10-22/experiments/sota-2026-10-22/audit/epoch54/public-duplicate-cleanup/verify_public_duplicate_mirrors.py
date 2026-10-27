"""Read-only whole-file hashes of precisely two old public roots and preserved mirrors.
No data/model/tokenizer/corpus parsing, deletion, or project writes.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,os,stat,time
O=Path('/dev/shm/ruvector-e54-data/independent-final/public-duplicate-cleanup')
OLD=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34')
W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch54-6187205840a9')
TARGETS=[OLD/'kit',OLD/'project']
SOURCES=[W/'kit',W/'project',W/'remote-current',OLD/'remote-current',OLD/'after-source']
cache={}
def signature(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def h(p):
 p=Path(p);assert p.is_absolute() and all(not q.is_symlink() for q in [p,*p.parents]);a=p.stat();assert stat.S_ISREG(a.st_mode)
 key=(str(p),signature(a))
 if key not in cache:
  v=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):v.update(b)
  z=p.stat();assert signature(a)==signature(z);cache[key]=v.hexdigest()
 return {'path':str(p),'bytes':a.st_size,'sha256':cache[key],'device':a.st_dev,'inode':a.st_ino,'hardlink_count':a.st_nlink,'mtime_ns':a.st_mtime_ns,'ctime_ns':a.st_ctime_ns}
def put(p,d):
 b=(json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
start=time.monotonic();rows=[];missing=[];counts={};initial={}
for root in TARGETS:
 assert root.is_dir() and all(not q.is_symlink() for q in [root,*root.parents])
 allp=sorted(root.rglob('*'));assert not any(p.is_symlink() for p in allp)
 fs=[p for p in allp if p.is_file()];assert len(fs)>8000
 initial[str(root)]={str(p.relative_to(root)):signature(p.stat()) for p in fs}
 count=0;size=0
 for p in fs:
  old=h(p);rel=p.relative_to(root);found=None
  for base in SOURCES:
   q=base/rel
   if q.is_file() and q.stat().st_size==old['bytes']:
    mirror=h(q)
    if mirror['sha256']==old['sha256']:
     assert (old['device'],old['inode']) != (mirror['device'],mirror['inode'])
     assert not any(q.is_relative_to(t) for t in TARGETS)
     found=mirror;break
  if found is None:missing.append(old)
  else:rows.append({'old_root':str(root),'relative_path':str(rel),'old':old,'preserved_mirror':found,'exact_size_SHA256_match':True,'different_inode_no_hardlink':True})
  count+=1;size+=old['bytes']
 counts[str(root)]={'regular_files':count,'logical_bytes':size,'directories':sum(p.is_dir() for p in allp)+1}
for root in TARGETS:
 current={str(p.relative_to(root)):signature(p.stat()) for p in root.rglob('*') if p.is_file()}
 assert current==initial[str(root)],str(root)+' changed during complete traversal'
manifest=put(O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json',{'schema_version':1,'epoch':54,'kind':'FULL_TWO_PUBLIC_ROOT_HASH_CENSUS','source_checkpoint':'6187205840a9f77db9ab80e97e30be7b222e461e','targets':[str(x) for x in TARGETS],'counts':counts,'files':rows,'unmirrored_old_files':missing,'actual_deletions':0,'actual_data_model_tokenizer_native_Git_calls':0,'scope':'Opaque whole-file SHA256 only. Public source/root proof; no dataset/model parsing.'})
report=put(O/'DUPLICATE_PUBLIC_ROOT_MIRROR_VERIFICATION.actual.v1.json',{'schema_version':1,'epoch':54,'checks_passed':not missing,'all_old_public_files_accounted':not missing,'every_old_file_hashed_SHA256_and_mirrored':len(rows)==sum(x['regular_files'] for x in counts.values()),'old_public_roots_unchanged_during_traversal':True,'no_hardlinks_to_preserved_mirrors':True,'preserved_mirrors_outside_both_deletion_targets':True,'targets':[str(x) for x in TARGETS],'counts':counts,'total_regular_files':sum(x['regular_files'] for x in counts.values()),'total_logical_bytes':sum(x['logical_bytes'] for x in counts.values()),'manifest':manifest,'unmirrored_files':missing,'actual_deletions':0,'actual_scientific_or_Git_calls':0,'wall_seconds':time.monotonic()-start})
print(json.dumps({'report':report,'manifest':manifest,'counts':counts,'unmirrored_files':missing},sort_keys=True))
assert not missing,'Root must preserve exact old control bytes outside targets before deletion approval'
