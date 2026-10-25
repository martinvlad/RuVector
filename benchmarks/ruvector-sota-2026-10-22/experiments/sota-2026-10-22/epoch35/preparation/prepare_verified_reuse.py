from pathlib import Path
import hashlib,json,os,stat,time
from mutation_guard import guard
W=Path(__file__).parent;R=W/'project';OLD=Path('/workspace/ruvector-epoch34-047dbc740dc2/project')
E='experiments/sota-2026-10-22/';P=E+'epoch35/preparation/'
V=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
M=Path('/workspace/ruvector-e35-reader-assets/moritz-b3546ea6');OM=Path('/workspace/ruvector-e34-reader-assets/moritz-b3546ea6')
def digest(p):
 assert stat.S_ISREG(p.stat().st_mode) and not any(x.is_symlink()for x in(p,*p.parents))
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def checked(root,row):
 p=root/row['path'];assert p.stat().st_size==row['bytes']and digest(p)==row['sha256'],str(p);return p
def put(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def enc(v):return(json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def ref(path):return dict(path=path,bytes=(R/path).stat().st_size,sha256=digest(R/path))
guard();start=time.monotonic();assert not M.exists() and not (R/(P+'runtime-assets.lock.json')).exists()
base=json.loads((R/(E+'epoch34/preparation/model-assets.lock.json')).read_text());assert digest(R/(E+'epoch34/preparation/model-assets.lock.json'))=='5a5486d1d5448a8d512f63d66b21a3fa49f6e6bf4db2e9ebbe83dfe4a2855c7d'
base.update(epoch=35,kind='ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS',model_directory=str(M));assert len(base['files'])==9
M.mkdir(parents=True);links=[]
for row in base['files']:
 src=checked(OM,row);dest=M/row['path'];os.link(src,dest);checked(M,row)
 s=src.stat();d=dest.stat();assert(s.st_dev,s.st_ino)==(d.st_dev,d.st_ino)
 links.append(dict(path=row['path'],bytes=row['bytes'],sha256=row['sha256'],source_device=s.st_dev,source_inode=s.st_ino,destination_same_device_inode=True))
body=enc(base);put(M/'asset-lock.json',body);put(R/(P+'model-assets.lock.json'),body)
member_ref=dict(path=E+'epoch26/preparation/runtime-members/python-wheel-members.json',bytes=4640799,sha256='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9')
members=json.loads(checked(R,member_ref).read_text());assert len(members)==17498
for row in members:checked(V,row)
lock=json.loads((R/(E+'epoch34/preparation/runtime-assets.lock.json')).read_text());assert digest(R/(E+'epoch34/preparation/runtime-assets.lock.json'))=='30f1413dfe80e7719b4d32f605825544e2a90b9e54cdc1e6d1d43fd799e90c76'
assets=[]
for row in lock['assets']:
 src=checked(OLD,row);dest=R/row['path'];assert not dest.exists()
 put(dest,src.read_bytes());checked(R,row);assert dest.stat().st_ino!=src.stat().st_ino
 assets.append(dict(path=row['path'],bytes=row['bytes'],sha256=row['sha256'],verified_source_and_destination=True,fresh_destination_inode=True))
assert len(assets)==10
receipt=dict(schema_version=1,epoch=35,policy='HASH_VERIFIED_READ_ONLY_E33_RUNTIME',runtime_environment=str(V),inference_python=str(V/'bin/python'),python_wheel_members=len(members),member_manifest=member_ref,all_hashes_checked=True,old_filesystem_assumed=False,old_model_or_runtime_files_modified=False,model_payload_files_verified=9,model_shared_payload_links=links,fresh_model_metadata_lock=True,model_directory=str(M),model_assets_lock=ref(P+'model-assets.lock.json'),native_BGE_project_assets_verified=10,native_BGE_source_destination_verifications=assets,actual_model_tokenizer_native_calls=0,paid_API_GPU_calls=0,source_bytes_republished=False,wall_seconds=time.monotonic()-start,scope='Verified reuse only. Model payloads are read-only shared inodes after source and destination hashing. Current native/BGE assets are fresh copies with both hashes verified. No weights downloaded or ML imported.')
put(R/(P+'runtime-reuse-verification.json'),enc(receipt));lock['epoch']=35;lock['runtime_reuse_verification']=ref(P+'runtime-reuse-verification.json');put(R/(P+'runtime-assets.lock.json'),enc(lock))
guard()
for parent in[M,M.parent,R/P,W]:
 fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(status='HASH_VERIFIED_REUSE_READY',member_count=len(members),model_files=9,native_BGE=10,model_lock=ref(P+'model-assets.lock.json'),runtime_lock=ref(P+'runtime-assets.lock.json'),reuse=ref(P+'runtime-reuse-verification.json'),seconds=time.monotonic()-start)))
