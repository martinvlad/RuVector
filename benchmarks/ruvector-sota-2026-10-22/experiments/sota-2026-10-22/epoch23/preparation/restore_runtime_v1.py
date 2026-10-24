"""Restore hash-pinned public BGE/native assets and CPU wheel members, no inference."""
from pathlib import Path
import argparse,importlib.util,json,hashlib,os,subprocess,sys,zipfile,time

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--public-cache',type=Path,required=True);ap.add_argument('--wheel-cache',type=Path,required=True);ap.add_argument('--receipt-dir',type=Path,required=True);a=ap.parse_args();p=a.project;s=p/'experiments/sota-2026-10-22';start=time.monotonic()
 helper=s/'epoch22/preparation/restore_public_runtime_cache_v1.py'
 expected='328cb60925c97e54f460f7c64ec5d12cd1d2c4d3062a3aaaa7812fbd2d362c20'
 assert hashlib.sha256(helper.read_bytes()).hexdigest()==expected
 spec=importlib.util.spec_from_file_location('reviewed_public_wheel_helpers',helper);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 for x in (p,a.public_cache,a.wheel_cache,a.receipt_dir):h.no_symlink(x)
 a.receipt_dir.mkdir(exist_ok=False)
 bge=json.loads((p/'assets.lock.json').read_text());native=json.loads((s/'epoch17/preparation/runtime-closure.json').read_text())['files'];native=[r for r in native if r['path'].startswith('retrieval/node_modules/')];assert len(native)==8
 assets=[{k:r[k] for k in ('path','bytes','sha256')} for r in bge['assets']+native]
 for r in assets:h.link_asset(a.public_cache/r['path'],p/r['path'],r)
 lock=json.loads((s/'epoch17/preparation/python-wheel-identities.json').read_text());wheels=lock['wheels'];assert len(wheels)==31
 for r in wheels:assert h.identity(a.wheel_cache/r['filename'],r)
 venv=p/'retrieval/.venv';assert not venv.exists();subprocess.run([sys.executable,'-m','venv','--without-pip',str(venv)],check=True)
 query='import sysconfig,json;print(json.dumps(sysconfig.get_paths()))';paths=json.loads(subprocess.check_output([str(venv/'bin/python'),'-B','-I','-c',query],text=True));site=Path(paths['purelib']);oldvenv=a.public_cache/'retrieval/.venv';oldsite=oldvenv/site.relative_to(venv)
 seen={};links=extractions=0
 for wheel in wheels:
  with zipfile.ZipFile(a.wheel_cache/wheel['filename']) as archive:
   for info,digest in h.wheel_members(archive):
    dst=h.wheel_target(info.filename,venv,site);src=h.wheel_target(info.filename,oldvenv,oldsite);assert dst.is_relative_to(venv);rel=str(dst.relative_to(venv));r={'path':rel,'bytes':info.file_size,'sha256':digest,'wheel':wheel['filename']}
    if rel in seen:assert seen[rel]['bytes']==r['bytes'] and seen[rel]['sha256']==digest;continue
    assert not dst.exists();dst.parent.mkdir(parents=True,exist_ok=True)
    if h.identity(src,r):os.link(src,dst,follow_symlinks=False);links+=1
    else:
     with dst.open('xb') as f:f.write(archive.read(info))
     extractions+=1
    assert h.identity(dst,r);seen[rel]=r
 h.put(a.receipt_dir/'python-wheel-members.json',list(seen.values()))
 versions=json.loads(subprocess.check_output([str(venv/'bin/python'),'-B','-I','-c',"import importlib.metadata as m,json;print(json.dumps({x:m.version(x) for x in ['numpy','onnxruntime','tokenizers']}))"],text=True))
 runtime={'schema_version':1,'assets':assets,'BGE_repository':bge['repo'],'BGE_revision':bge['revision'],'BGE_license':bge['base_model_license'],'BGE_license_revision':bge['base_model_license_revision'],'native_NPM_version':'0.1.33','native_platform_NPM_version':'0.1.31','native_core_runtime_version':'2.3.0','python_expected_versions':versions,'BGE_source_path':'experiments/sota-2026-10-22/candidate/epoch3/models.py','BGE_source_sha256':h.digest(s/'candidate/epoch3/models.py'),'wheel_lock_path':'experiments/sota-2026-10-22/epoch17/preparation/python-wheel-identities.json','wheel_lock_sha256':h.digest(s/'epoch17/preparation/python-wheel-identities.json'),'native_closure_path':'experiments/sota-2026-10-22/epoch17/preparation/runtime-closure.json','native_closure_sha256':h.digest(s/'epoch17/preparation/runtime-closure.json'),'model_weights_not_republished':True}
 h.put(s/'epoch23/preparation/runtime-assets.lock.json',runtime)
 report={'status':'FRESH_CPU_RUNTIME_FROM_FULLY_VERIFIED_PUBLIC_BYTES','public_assets':len(assets),'official_CPU_wheels':len(wheels),'verified_wheel_members':len(seen),'byte_identical_hardlinks':links,'official_zip_extractions':extractions,'python_expected_versions':versions,'inference_python':str(venv/'bin/python'),'wheel_members_receipt_sha256':h.digest(a.receipt_dir/'python-wheel-members.json'),'BGE_NLI_native_tokenizer_fit_paid_GPU_network_calls':0,'wall_seconds':time.monotonic()-start,'torch_instantiated':False,'old_environment_not_blindly_reused':True}
 h.put(s/'epoch23/preparation/runtime-restoration.json',report);print(json.dumps(report))

if __name__=='__main__':main()
