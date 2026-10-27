import json,hashlib,os,shutil,sys,time
from pathlib import Path
W=Path(__file__).resolve().parent;D=Path('/dev/shm/ruvector-e54-data/independent-final/public-duplicate-cleanup');OLD=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34')
sys.path.insert(0,str(W/'publication-helpers'));import guard as g
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(row):
 p=Path(row['path']);assert ref(p)==row;return json.loads(p.read_bytes())
def h(p):
 v=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):v.update(b)
 return v.hexdigest()
def unchanged(row):
 p=Path(row['path']);assert p.is_file()and not p.is_symlink();s=p.stat();assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==tuple(row[k]for k in ['device','inode','bytes','mtime_ns','ctime_ns']);assert h(p)==row['sha256']
def snap():
 root=Path('/sys/fs/cgroup');return {'memory_current_bytes':int((root/'memory.current').read_text()),'memory_max_bytes':int((root/'memory.max').read_text()),'shm_free_bytes':os.statvfs('/dev/shm').f_bavail*os.statvfs('/dev/shm').f_frsize}
def put(p,x):
 with p.open('x')as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
planp=D/'EXACT_TWO_PUBLIC_ROOT_DELETION_PLAN.v1.json';assert ref(planp)['sha256']=='e2c60e4a4fb69bf8ef66bd609678cf831c87e0dfde0d1d2c77442196ee070a1d';plan=json.loads(planp.read_text())
ap=D/'EXACT_OLD_W53_PUBLIC_DUPLICATE_CLEANUP_INDEPENDENT_APPROVAL.v1.json';assert ref(ap)['sha256']=='d1b8ae4569e5c9b812006ffc0773e1ff559c73eed61c59493008a48a11c4c3c3'
targets=[OLD/'kit',OLD/'project'];assert plan['delete_exact_directory_targets']==[str(x)for x in targets];manifest=read(plan['manifest']);assert not manifest['unmirrored_old_files']and len(manifest['files'])==17384
for root in targets:
 assert root.is_dir()and not root.is_symlink();actual={str(x.relative_to(root))for x in root.rglob('*')if x.is_file()};expected={x['relative_path']for x in manifest['files']if x['old_root']==str(root)};assert actual==expected;assert not any(x.is_symlink()for x in root.rglob('*'))
for row in manifest['files']:
 old=Path(row['old']['path']);mirror=Path(row['preserved_mirror']['path']);assert any(old.is_relative_to(x)for x in targets)and not any(mirror.is_relative_to(x)for x in targets);assert (row['old']['device'],row['old']['inode'])!=(row['preserved_mirror']['device'],row['preserved_mirror']['inode']);unchanged(row['old']);unchanged(row['preserved_mirror'])
g.owner_fence();before=snap();siblings={p.name:(p.stat().st_dev,p.stat().st_ino,p.is_dir())for p in OLD.iterdir()if p not in targets};put(W/'OLD_W53_PUBLIC_DUPLICATE_CLEANUP_ATTEMPT.actual.v1.json',{'epoch':54,'exact_targets':[str(x)for x in targets],'plan':ref(planp),'approval':ref(ap),'all_17384_old_and_mirror_hashes_root_reverified':True,'before':before,'science_or_Git_authority':False});started=time.monotonic()
for target in targets:g.owner_fence();shutil.rmtree(target)
assert not any(p.exists()for p in targets);assert siblings=={p.name:(p.stat().st_dev,p.stat().st_ino,p.is_dir())for p in OLD.iterdir()};after=snap();put(W/'OLD_W53_PUBLIC_DUPLICATE_CLEANUP.actual.v1.json',{'epoch':54,'checks_passed':True,'exact_deleted_public_targets':[str(x)for x in targets],'logical_bytes_retired':1131475886,'regular_files_retired':17384,'every_byte_had_SHA_verified_separate_preserved_mirror':True,'all_old_parent_siblings_and_private_runtime_assets_unchanged':True,'before':before,'after':after,'wall_seconds':time.monotonic()-started,'all_E54_scientific_slots_remain_closed':True,'new_native_tokenizer_BGE_model_Git_calls':0,'shared_memory_scope':'Shared snapshots, not candidate incremental RAM or sole cause attribution.'});print((W/'OLD_W53_PUBLIC_DUPLICATE_CLEANUP.actual.v1.json').read_text())
