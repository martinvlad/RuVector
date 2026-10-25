from pathlib import Path
import hashlib,json,os,stat,time
W=Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f');R=W/'project';D=R/'experiments/sota-2026-10-22/epoch38/preparation'
OLD=W.parent/'epoch37-b4e9e4f7a8a4'/'project'
ORIGINAL=Path('/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd')
TARGET=Path('/workspace/ruvector-e38-reader-assets/ms-xxlarge-8f8b43dd')
VENV=W.parent/'epoch33-0522a2c521c9/runtime/.venv'
P='experiments/sota-2026-10-22/'
G={r['path']:r for r in json.loads((W/'actual-git-map.json').read_text())['files']}
CP={r['path']:r for r in json.loads((W/'remote-current/CHECKPOINT_MANIFEST.json').read_text())['project_files']}
def digest(path,algorithm='sha256'):
 h=hashlib.new(algorithm)
 with path.open('rb')as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def regular(p):
 assert not any(v.is_symlink()for v in(p,*p.parents))and stat.S_ISREG(p.stat().st_mode),str(p)
def verified_source(name):
 p=R/name;regular(p);b=p.read_bytes();g=G[name];c=CP[name]
 assert len(b)==g['size']==c['bytes']and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==g['sha']and hashlib.sha256(b).hexdigest()==c['sha256']
 return json.loads(b)
def put(p,b):
 p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def encoded(x):return(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def ref(name):
 p=R/name;return{'path':name,'bytes':p.stat().st_size,'sha256':digest(p)}
started=time.monotonic()
expected=verified_source(P+'epoch37/future-source-review/asset-identity-fix/MODEL_ASSETS.expected.json')
observed=verified_source(P+'candidate/epoch37/MODEL_ASSETS.json')
lock=verified_source(P+'epoch37/preparation/runtime-assets.lock.json')
assert TARGET.is_dir() and not any(TARGET.iterdir()),'Only the observed empty fresh target may be completed'
# Target was freshly created by failed source-mode assertion; independent empty inventory verified.
rows=[];known={r['path']:r for r in expected['files']}
assert len(known)==5 and {r['path']for r in observed['files']}==set(known)
for row in observed['files']:
 exp=known[row['path']];want=exp.get('upstream_sha256')or exp.get('metadata_body_sha256')
 assert want==row['sha256']and exp['bytes']==row['bytes']and exp['source_url']==row['source_url']
 src=ORIGINAL/row['path'];dst=TARGET/row['path'];regular(src);before=src.stat()
 assert before.st_size==row['bytes'] and digest(src)==want
 copied=bool(before.st_mode&0o222)
 if copied:
  assert row['path'] in {'config.json','tokenizer_config.json','LICENSE'} and row['bytes']<2048
  put(dst,src.read_bytes());os.chmod(dst,0o444);os.utime(dst,ns=(before.st_atime_ns,before.st_mtime_ns))
 else:os.link(src,dst)
 regular(dst);after=src.stat()
 assert (dst.stat().st_ino==before.st_ino and dst.stat().st_dev==before.st_dev)is(not copied) and digest(dst)==want and dst.stat().st_mode&0o222==0
 assert(before.st_mode,before.st_mtime_ns)==(after.st_mode,after.st_mtime_ns)and after.st_nlink==before.st_nlink+(0 if copied else 1)
 rows.append({'path':row['path'],'bytes':row['bytes'],'sha256':want,'same_payload_inode_read_only_reuse':not copied,
 'payload_bytes_mode_mtime_unchanged':True,'hardlink_nlink_ctime_metadata_changed':not copied,
 'materialization':'FRESH_READ_ONLY_METADATA_COPY' if copied else 'READ_ONLY_EXISTING_PAYLOAD_HARDLINK',
 'source_mode':before.st_mode,'destination_mode':dst.stat().st_mode})
observed['epoch']=38;observed['model_directory']=str(TARGET)
body=encoded(observed);model_path=P+'candidate/epoch38/MODEL_ASSETS.json'
put(R/model_path,body);put(TARGET/'asset-lock.json',body);os.chmod(TARGET/'asset-lock.json',0o444);os.chmod(TARGET,0o555)
put(D/'model-assets.lock.json',body)
member=lock['python_member_manifest'];assert ref(member['path'])==member
members=json.loads((R/member['path']).read_text());assert len(members)==17498 and len({v['path']for v in members})==17498
wheel=verified_source(lock['wheel_lock_path']);assert len(wheel['wheels'])==31
for row in members:
 name=row['path'];assert not Path(name).is_absolute()and all(x not in('','.','..')for x in name.split('/'))and '\\'not in name
 p=VENV/name;regular(p);assert p.stat().st_size==row['bytes']and digest(p)==row['sha256'],name
assets=[]
for row in lock['assets']:
 src=OLD/row['path'];dst=R/row['path'];regular(src);assert src.stat().st_size==row['bytes']and digest(src)==row['sha256']
 if dst.exists():
  regular(dst);assert dst.stat().st_size==row['bytes']and digest(dst)==row['sha256'];how='RESTORED_CP_ALREADY_PRESENT_VERIFIED'
 else:
  put(dst,src.read_bytes());assert dst.stat().st_size==row['bytes']and digest(dst)==row['sha256'];how='FRESH_OPT_IN_COPY_HASH_VERIFIED'
 assets.append({**row,'destination':how,'source_directory':str(OLD)})
assert len(assets)==10 and sum(r['destination']=='FRESH_OPT_IN_COPY_HASH_VERIFIED'for r in assets)==3
reuse={'schema_version':1,'epoch':38,'status':'ONE_PROFILE_RUNTIME_ASSETS_HASH_VERIFIED_NO_ML','policy':'HASH_VERIFIED_READ_ONLY_E33_RUNTIME',
 'source_checkpoint':'7c50ba99848f6a13707eeec6c4947291a8478e5c','actual_model_native_tokenizer_paid_GPU_calls':0,'fresh_environment_installs':0,
 'member_manifest':member,'verified_wheel_members':17498,'official_CPU_wheels':31,'external_environment':str(VENV),
 'model_profiles_verified':{'xxlarge':{'model_directory':str(TARGET),'payload_files':5,'model_assets_lock':ref(model_path),'payloads':rows,
 'original_directory':str(ORIGINAL),'original_payloads_byte_mode_mtime_unchanged':True,'same_inodes_hardlinks_read_only':False,'nlink_ctime_changes_disclosed':True,
 'copied_metadata_files':3,'hardlinked_payload_files':2,'all_payload_files_read_only':True,
 'materialization_policy':'THREE_SMALL_READ_ONLY_METADATA_COPIES_TWO_LARGE_READ_ONLY_HARDLINKS'}},
 'native_BGE_assets':assets,'actual_original_weight_dtype_and_legacy_qualification':'REUSED_EXACT_GIT_CP_BOUND_E36_METADATA_AND_SUCCESSFUL_CPU_RESTRICTED_LOAD; no repeat inspection',
 'immutable_original_source_guards':'Original hashes, typed separate expected authority, strict directory inventory and full shared real-asset validator required before freeze and again at runtime; no fallback.',
 'wall_seconds':time.monotonic()-started}
reuse_path=P+'epoch38/preparation/runtime-reuse-verification.json';put(R/reuse_path,encoded(reuse))
lock['epoch']=38;lock['runtime_reuse_verification']=ref(reuse_path)
put(D/'runtime-assets.lock.json',encoded(lock))
for directory in(D,TARGET,R/(P+'candidate/epoch38')):
 fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps({'model_assets_lock':ref(model_path),'runtime_reuse':ref(reuse_path),'runtime_assets_lock':ref(P+'epoch38/preparation/runtime-assets.lock.json'),
 'actual_source_and_destination_payload_hashes_checked':5,'actual_wheel_members_hashed':17498,'native_BGE_assets_hashed':10,'fresh_optins':3,
 'no_ML_tokenizer_native_calls':True,'full_shared_guard_status':'PENDING_SEPARATE_UNSTUBBED_CALL','seconds':time.monotonic()-started}))

