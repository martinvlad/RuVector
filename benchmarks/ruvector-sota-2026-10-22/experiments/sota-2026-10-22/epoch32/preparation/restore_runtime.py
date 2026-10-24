from pathlib import Path,PurePosixPath
import os,json,hashlib,subprocess,time,sys,stat
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');R=W/'project';G=Path('/tmp/ruvector-sota-2026-10-22/epoch32-f8bcbc4ca7ec');OLD=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa/project');V=G/'runtime/.venv'
MEM='experiments/sota-2026-10-22/epoch26/preparation/runtime-members/python-wheel-members.json';MEM_SHA='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'
LOCK='experiments/sota-2026-10-22/epoch17/preparation/python-wheel-identities.json';LOCK_SHA='6689210699a4171b54a38f8d14edba78c4b4b6390c76b6b05293a32f1ea2b8de'
AS='experiments/sota-2026-10-22/epoch26/preparation/runtime-assets.lock.json';AS_SHA='0229a75ce29f70d2fbed3c2b99abd756a48d0c02eac393985c7b90fea1e4032f'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def safe(p):assert p==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents));return p
def verify(p,r):safe(p);assert stat.S_ISREG(p.stat().st_mode)and p.stat().st_size==r['bytes']and digest(p)==r['sha256'],str(p)
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
started=time.monotonic();subprocess.run(['python','-B',str(W/'mutation_guard.py'),'guard'],check=True,capture_output=True)
for p,h in [(MEM,MEM_SHA),(LOCK,LOCK_SHA),(AS,AS_SHA)]:assert digest(R/p)==h
members=json.loads((R/MEM).read_text());wheels=json.loads((R/LOCK).read_text())['wheels'];assets=json.loads((R/AS).read_text());assert(len(members),len(wheels),len(assets['assets']))==(17498,31,10)
caches=list(Path('/tmp/ruvector-sota-2026-10-22').glob('epoch17-*/python-wheels'));assert len(caches)==1;wheelcache=caches[0]
for row in wheels:verify(wheelcache/row['filename'],row)
assert not V.exists();V.parent.mkdir(mode=0o700,parents=True);subprocess.run([sys.executable,'-m','venv','--without-pip',str(V)],check=True)
for row in members:
 p=PurePosixPath(row['path']);assert not p.is_absolute()and '..'not in p.parts and '\\'not in str(p);src=OLD/'retrieval/.venv'/p;dst=V/p;verify(src,row);dst.parent.mkdir(parents=True,exist_ok=True);safe(dst);assert not dst.exists();os.link(src,dst,follow_symlinks=False);verify(dst,row)
for row in assets['assets']:
 src=OLD/row['path'];dst=R/row['path'];verify(src,row);dst.parent.mkdir(parents=True,exist_ok=True);safe(dst);assert not dst.exists()
 with src.open('rb')as incoming,dst.open('xb')as out:
  for b in iter(lambda:incoming.read(1048576),b''):out.write(b)
  out.flush();os.fsync(out.fileno())
 verify(dst,row)
packages=['torch','transformers','safetensors','numpy','tokenizers','onnxruntime']
q='import importlib.metadata as m,json,sys;print(json.dumps({"versions":{x:m.version(x) for x in '+repr(packages)+'},"ML_loaded":sorted(x for x in sys.modules if x.split(".")[0] in '+repr(packages)+'),"python_version":sys.version,"prefix":sys.prefix}))'
result=json.loads(subprocess.check_output([str(V/'bin/python'),'-I','-B','-c',q],text=True));assert not result['ML_loaded'];expected={'torch':'2.7.1+cpu','transformers':'4.52.4','safetensors':'0.5.3','numpy':'2.2.6','tokenizers':'0.21.4','onnxruntime':'1.22.1'};assert result['versions']==expected
assets.update(epoch=32,python_expected_versions=expected,inference_python=str(V/'bin/python'),fresh_runtime_directory=str(V),python_member_manifest={'path':MEM,'bytes':(R/MEM).stat().st_size,'sha256':MEM_SHA},python_wheel_lock={'path':LOCK,'bytes':(R/LOCK).stat().st_size,'sha256':LOCK_SHA},verified_wheel_members=17498,official_CPU_wheels=31,actual_model_initializations=0,actual_native_initializations=0)
put(W/'runtime-assets.lock.json',assets);report={'epoch':32,'status':'FRESH_VERIFIED_RUNTIME_FROM_FROZEN_OFFICIAL_CPU_WHEELS','inference_python':str(V/'bin/python'),'metadata_only_runtime_query':result,'assets':10,'official_CPU_wheels':31,'all_source_and_destination_member_SHA256_verified':17498,'runtime_member_reference_sha256':MEM_SHA,'runtime_assets_lock_sha256':digest(W/'runtime-assets.lock.json'),'native_assets_fresh_workspace_copies':True,'wheel_files_fresh_current_TMP_hardlinks':True,'old_prefix_not_executed_or_blindly_reused':True,'network_pip_hooks_model_native_tokenizer_calls':0,'wall_seconds':time.monotonic()-started,'tmp_free_bytes':os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize,'workspace_free_bytes':os.statvfs('/workspace').f_bavail*os.statvfs('/workspace').f_frsize}
put(W/'runtime-restoration.json',report);print(json.dumps(report))

