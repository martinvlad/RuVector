"""Root-only exact verified duplicate retirement; no scientific or Git execution."""
from pathlib import Path
import json,hashlib,os,shutil,time,stat
W=Path(__file__).resolve().parent;D=Path('/dev/shm/ruvector-e55-data/public-duplicate-cleanup');OLD=W.parent/'epoch54-6187205840a9'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def read(r):
 p=Path(r['path']);assert ref(p)==r;return json.loads(p.read_bytes())
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def signature(p):
 s=p.lstat();return {'ctime_ns':s.st_ctime_ns,'dev':s.st_dev,'ino':s.st_ino,'mode':s.st_mode,'mtime_ns':s.st_mtime_ns,'size':s.st_size}
def fence():
 p=W/'owner.json';assert sha(p)=='bf6380ac1d3776ba3f0f2e28a4aa3acc9eb9d79bb3c9358eebf701a6dbccbec7';o=json.loads(p.read_text());assert time.time()<o['expires_unix']and not(W/'release.request').exists();assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==o['kernel_boot_id'];q=Path('/proc')/str(o['pid']);assert int((q/'stat').read_text().rsplit(')',1)[1].split()[19])==o['startticks'];s=(q/'fd/3').stat();assert(s.st_dev,s.st_ino)==(o['lock_device'],o['lock_inode'])
def snapshot():
 c=Path('/sys/fs/cgroup');v={'memory_current_bytes':int((c/'memory.current').read_text()),'memory_max_bytes':int((c/'memory.max').read_text()),'shm_free_bytes':os.statvfs('/dev/shm').f_bavail*os.statvfs('/dev/shm').f_frsize};v['headroom_bytes']=v['memory_max_bytes']-v['memory_current_bytes'];return v
assert sorted(os.sched_getaffinity(0))==[0,1];fence();planp=D/'OLD_W54_PUBLIC_DUPLICATE_CLEANUP_PLAN.v1.json';assert sha(planp)=='0ec9cc19f87cc4f36818ebe02e3f85c0cc8e50434143fb2d4073500e2ded84b6';plan=json.loads(planp.read_text());manifest=read(plan['full_manifest']);targets=[OLD/'kit',OLD/'project'];assert plan['delete_only']==list(map(str,targets))and len(manifest['rows'])==17602
approval=read(json.loads((W/'CLEANUP_APPROVAL_REF.v1.json').read_text()));assert approval['checks_passed']is True
for root in targets:
 assert root.is_dir()and not root.is_symlink();paths=list(root.rglob('*'));assert not any(p.is_symlink()for p in paths);assert {str(p)for p in paths if p.is_file()}=={r['old']for r in manifest['rows']if Path(r['old']).is_relative_to(root)}
for r in manifest['directories']:assert signature(Path(r['path']))==r['signature']
for r in manifest['rows']:
 a=Path(r['old']);b=Path(r['mirror']);assert any(a.is_relative_to(p)for p in targets)and not any(b.is_relative_to(p)for p in targets);assert(a.stat().st_dev,a.stat().st_ino)!=(b.stat().st_dev,b.stat().st_ino)
 for p,key in [(a,'old_signature'),(b,'mirror_signature')]:assert p.is_file()and not p.is_symlink()and signature(p)==r[key]and p.stat().st_size==r['bytes']and sha(p)==r['sha256']
for r in manifest['preserved_old_siblings']:assert signature(Path(r['path']))==r['signature']
fence();before=snapshot();put(W/'OLD_W54_PUBLIC_DUPLICATE_CLEANUP_ATTEMPT.actual.v1.json',{'epoch':55,'plan':ref(planp),'independent_approval':json.loads((W/'CLEANUP_APPROVAL_REF.v1.json').read_text()),'exact_targets':list(map(str,targets)),'all_17602_old_and_mirror_files_root_SHA_reverified':True,'before':before,'scientific_or_Git_authority':False});started=time.monotonic()
for p in targets:fence();shutil.rmtree(p)
assert not any(p.exists()for p in targets)
for r in manifest['preserved_old_siblings']:assert signature(Path(r['path']))==r['signature']
after=snapshot();v={'schema_version':1,'epoch':55,'checks_passed':True,'exact_deleted_public_targets':list(map(str,targets)),'regular_files_retired':17602,'logical_bytes_retired':1135187077,'every_old_byte_had_separate_inode_SHA_verified_preserved_mirror':True,'old_parent_siblings_controls_private_private_run_publication_journals_basecache_and_runtime_assets_preserved':True,'before':before,'after':after,'wall_seconds':time.monotonic()-started,'native_tokenizer_BGE_typed_model_Git_calls':0,'science_dispatch_authorized':False,'shared_cgroup_scope':'Shared snapshots, not incremental use or sole cause attribution.'};put(W/'OLD_W54_PUBLIC_DUPLICATE_CLEANUP.actual.v1.json',v);print(json.dumps(v))
