"""Root-only exact public duplicate retirement with byte-preserving archive/model mirrors."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time
W=Path(__file__).resolve().parent;sys.dont_write_bytecode=True;sys.path.insert(0,str(W/'publication-helpers'));import guard as g

def h(p):
 x=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):x.update(b)
 return x.hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':h(p)}
def read(r):
 p=Path(r['path']);assert ref(p)==r;return json.loads(p.read_bytes())
def sig(p):
 s=p.stat();return {'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'nlink':s.st_nlink}
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def snap():
 p=Path('/tmp');v=os.statvfs(p);return {'tmp_free_bytes':v.f_bavail*v.f_frsize,'memory_current_bytes':int(Path('/sys/fs/cgroup/memory.current').read_text())}
def main():
 assert sorted(os.sched_getaffinity(0))==[0,1];g.owner_fence();planp=W/'DISK_RECOVERY_PUBLIC_SOURCE_PLAN.v1.json';assert h(planp)=='c1090da47bc6b7029f3cf9db3d4a563e52a39f038b9d033bfd3f24f4ef1b0dcb';p=json.loads(planp.read_bytes());approval=read(json.loads((W/'DISK_RECOVERY_APPROVAL_REF.v1.json').read_text()));assert approval['checks_passed']is True
 old=Path('/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4/project/models/bge-small-en-v1.5/model.onnx');root=Path('/tmp/ruvector-sota-2026-10-22/epoch56-parser-ffdd0699f325/parser');assert p['delete_exact']==[str(old),str(root)]
 keep=Path(p['retained_active_BGE']['path']);wheel=Path(p['retained_exact_wrong_ABI_wheel']['path']);assert ref(old)==p['old_BGE_public_duplicate']and sig(old)==p['old_BGE_signature'];assert ref(keep)==p['retained_active_BGE']and sig(keep)==p['retained_active_BGE_signature'];assert ref(wheel)==p['retained_exact_wrong_ABI_wheel'];assert h(old)==h(keep)
 actual=list(root.rglob('*'));assert not root.is_symlink()and not any(q.is_symlink()for q in actual);assert{str(q)for q in actual if q.is_file()}=={r['path']for r in p['extracted_members']}
 for row in p['extracted_members']:assert ref(Path(row['path']))==row
 for row in p['retained_license_ABI_metadata_files']:assert ref(Path(row['path']))==row
 # Fail closed if the retired caches appear in any process memory mapping.
 mapped=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   text=(proc/'maps').read_text()
   if str(old)in text or str(root)+'/'in text:mapped.append(int(proc.name))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 assert not mapped
 # Preserve all three dataset files and the failed partial download by full hash.
 manifest=read(p['retained_wrong_ABI_asset_manifest']);protected=[ref(Path(r['path']))for r in manifest['assets']];partial=Path('/tmp/ruvector-sota-2026-10-22/epoch56-parser-cp312-ffdd0699f325/assets/pyarrow-20.0.0-cp312-cp312-manylinux_2_28_x86_64.whl.partial');protected.append(ref(partial))
 g.owner_fence();before=snap();put(W/'PUBLIC_DISK_DUPLICATE_RETIREMENT_INTENT.actual.v1.json',{'epoch':56,'plan':ref(planp),'exact_targets':p['delete_exact'],'approval':json.loads((W/'DISK_RECOVERY_APPROVAL_REF.v1.json').read_text()),'protected_assets':protected,'active_BGE':ref(keep),'before':before,'no_active_mapping_of_retired_paths':True,'automatic_retry':False});start=time.monotonic()
 old.unlink();g.owner_fence();shutil.rmtree(root)
 assert not old.exists()and not root.exists();assert ref(keep)==p['retained_active_BGE']and sig(keep)==p['retained_active_BGE_signature']
 for r in protected:assert ref(Path(r['path']))==r
 v={'epoch':56,'checks_passed':True,'exact_deleted_paths':p['delete_exact'],'logical_bytes_retired':p['logical_disk_bytes_reclaimable'],'retired_BGE_bytes_preserved_in_active_model38':True,'retired_parser_bytes_preserved_inside_exact_readonly_cp311_wheel':True,'all_three_datasets_wrong_wheel_failed_partial_current_model38_unchanged':True,'before':before,'after':snap(),'wall_seconds':time.monotonic()-start,'model_imports_native_measurements_Git_calls':0,'scope':'Only independently reviewed public duplicate caches; no private, installed-runtime, checkpoint, current-model or native-binary path is deleted.'};put(W/'PUBLIC_DISK_DUPLICATE_RETIREMENT.actual.v1.json',v);print(json.dumps(v))
if __name__=='__main__':main()
