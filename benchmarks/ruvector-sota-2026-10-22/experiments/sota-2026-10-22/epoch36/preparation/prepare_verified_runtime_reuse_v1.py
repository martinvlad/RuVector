from pathlib import Path
import hashlib,json,os,time
from mutation_guard import guard
W=Path(__file__).parent;R=W/'project';OLD=Path('/workspace/ruvector-epoch35-4d51073072c4/project');P='experiments/sota-2026-10-22/';E=P+'epoch36/preparation/';V=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
def digest(p):
 assert p.is_file()and not any(x.is_symlink()for x in(p,*p.parents))
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def checked(root,row):
 p=root/row['path'];assert p.stat().st_size==row['bytes']and digest(p)==row['sha256'],str(p);return p
def ref(name):return dict(path=name,bytes=(R/name).stat().st_size,sha256=digest(R/name))
def enc(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
guard();start=time.monotonic();assert not(R/(E+'runtime-reuse-verification.json')).exists()and not(R/(E+'runtime-assets.lock.json')).exists()
member_ref=dict(path=P+'epoch26/preparation/runtime-members/python-wheel-members.json',bytes=4640799,sha256='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9')
members=json.loads(checked(R,member_ref).read_text());assert len(members)==17498
for row in members:checked(V,row)
oldlock=R/(P+'epoch35/preparation/runtime-assets.lock.json');assert digest(oldlock)=='940fbb16830c8e6312a622167fa5fea8105ff5402772df6965ad97966df1605f';lock=json.loads(oldlock.read_text());union={x['path']:x for x in json.loads((W/'expected-project-union.json').read_text())['files']};assets=[];copied=[]
for row in lock['assets']:
 src=checked(OLD,row);dst=R/row['path']
 if dst.exists():
  assert row['path']in union and all(union[row['path']][k]==row[k]for k in('bytes','sha256'));checked(R,row)
 else:put(dst,src.read_bytes());checked(R,row);copied.append(row['path'])
 assert dst.stat().st_ino!=src.stat().st_ino;assets.append(dict(path=row['path'],bytes=row['bytes'],sha256=row['sha256'],verified_source_and_destination=True,fresh_destination_inode=True))
assert len(assets)==10 and len(copied)==3
profiles={}
for tag,dirpath,lockname,n in [('b354','/workspace/ruvector-e36-reader-assets/moritz-b3546ea6','BASELINE_MODEL_ASSETS.json',9),('xxlarge','/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd','MODEL_ASSETS.json',5)]:
 lr=ref(P+'candidate/epoch36/'+lockname);val=json.loads((R/lr['path']).read_text());M=Path(dirpath);assert(M/'asset-lock.json').read_bytes()==(R/lr['path']).read_bytes();assert len(val['files'])==n and{p.name for p in M.iterdir()}=={r['path']for r in val['files']}|{'asset-lock.json'}
 for row in val['files']:checked(M,row)
 profiles[tag]=dict(model_directory=dirpath,model_payload_files_verified=n,model_assets_lock=lr)
receipt=dict(schema_version=1,epoch=36,policy='HASH_VERIFIED_READ_ONLY_E33_RUNTIME',runtime_environment=str(V),inference_python=str(V/'bin/python'),python_wheel_members=17498,member_manifest=member_ref,all_hashes_checked=True,old_filesystem_assumed=False,old_model_or_runtime_files_modified=False,model_profiles_verified=profiles,model_payload_files_verified=14,native_BGE_project_assets_verified=10,native_BGE_source_destination_verifications=assets,fresh_model_metadata_lock=True,model_directory=profiles['xxlarge']['model_directory'],model_assets_lock=profiles['xxlarge']['model_assets_lock'],baseline_model_directory=profiles['b354']['model_directory'],baseline_model_assets_lock=profiles['b354']['model_assets_lock'],actual_model_tokenizer_native_calls=0,paid_API_GPU_calls=0,source_bytes_republished=False,wall_seconds=time.monotonic()-start,scope='All17498 reused runtime members and14 model payload/metadata files hash-verified; original profile locks are fresh. Baseline payloads are verified read-only shared inodes; creating new aliases may change inode link counts/ctime but no original byte content is changed. Native/BGE assets have fresh destination inodes. No ML import, model/tokenizer/native initialization or weight conversion performed. Source serialization/dtype qualification is separate and pending approved inert legacy metadata.')
put(R/(E+'runtime-reuse-verification.json'),enc(receipt));lock['epoch']=36;lock['runtime_reuse_verification']=ref(E+'runtime-reuse-verification.json');put(R/(E+'runtime-assets.lock.json'),enc(lock));guard()
print(json.dumps(dict(status='TWO_PROFILE_RUNTIME_ASSETS_HASH_VERIFIED_NO_ML',members=17498,model_payloads=14,native_BGE=10,reuse=ref(E+'runtime-reuse-verification.json'),runtime_lock=ref(E+'runtime-assets.lock.json'),wall_seconds=time.monotonic()-start)))
