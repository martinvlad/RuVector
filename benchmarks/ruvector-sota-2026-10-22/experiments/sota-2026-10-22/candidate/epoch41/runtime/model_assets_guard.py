"""Shared stdlib-only per-profile real payload guard. No ML/tokenizer/native load."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import stat
import time

HERE=Path(__file__).resolve().parent
HELPER=HERE.parent/'asset_identity.py'
HELPER_SHA='f271c0077be23c34fbb29cfb5728d671371a4646ac9030072ec7b538eb819499'
PROFILE_SPECS={
 'b354':{'repository':'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli','revision':'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7','catalog':'MODEL_B354_ASSETS.expected.json','catalog_sha256':'30657c23de7feae478af2b951c814ff5e4be3c69c7a90c08d0f268a2172eea11','files':9},
 'tasksource':{'repository':'sileod/deberta-v3-large-tasksource-nli','revision':'212de447184bda8fb9415a2e5697846864ddf304','catalog':'MODEL_TASKSOURCE_ASSETS.expected.json','catalog_sha256':None,'files':9}}
PREACQ=HERE.parent/'research/CLASSIC_PREACQUISITION_CATALOG.json'
PREACQ_SHA='6023ccec0a48a5cb4f018e8be94a236d0479454ccb92deabd7c25fadf67724d3'

NATIVE_BGE_SHA256={'models/bge-small-en-v1.5/model.onnx': '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35', 'models/bge-small-en-v1.5/tokenizer.json': 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66', 'retrieval/node_modules/@ruvector/core/index.js': 'eeba197be4185adb3492b8bc53cd61870f57d6bc18a9a5f1cd2ebec4b1908bee', 'retrieval/node_modules/@ruvector/core/package.json': '729e07f6c040bd47ba687cde8ad5681088187e53812e89d77d646ff48088a5e4', 'retrieval/node_modules/@ruvector/core/README.md': '82b4f4845e0753732a66dc88ddd801502449b60ad1100b273ae34d1035e8b932', 'retrieval/node_modules/@ruvector/core/index.d.ts': '36411710e6879c76dca228c4cff97993c4e95cee70388c2f936c79b01536ac54', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js': 'f392127e6cd14141107fa432a43bbccc2fa1d574630a6fe2611688c66a48a7e9', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json': 'afca994434efaadf637eb7d28bfd48da9dda69f24513bfb498c4ab9459d2fdf4', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/README.md': 'dd25a68639af6bf44b4e0cd1388eb119047a7bd4f21ef99ece9ded424d3a4a89', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node': 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'}
_IDENTITY=None

def no_symlink(path):
 p=Path(path)
 if any(q.is_symlink()for q in(p,*p.parents)):raise ValueError('ASSET_SYMLINK_REFUSED')
 return p

def sha(path):
 h=hashlib.sha256()
 with no_symlink(path).open('rb')as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()

def source_ref(path,root):
 p=no_symlink(path)
 return {'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)}

def object_pairs(pairs):
 value={}
 for k,v in pairs:
  if k in value:raise ValueError('DUPLICATE_ASSET_METADATA_KEY')
  value[k]=v
 return value

def read_metadata(path):
 p=no_symlink(path)
 if not p.is_file()or not stat.S_ISREG(p.stat().st_mode):raise ValueError('REGULAR_ASSET_METADATA_REQUIRED')
 return json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=object_pairs,
  parse_constant=lambda value:(_ for _ in()).throw(ValueError('NONFINITE_ASSET_METADATA')))

def identities():
 global _IDENTITY
 if _IDENTITY is None:
  if sha(HELPER)!=HELPER_SHA:raise ValueError('TYPED_IDENTITY_SOURCE_CHANGED')
  sp=importlib.util.spec_from_file_location('e39_reviewed_typed_asset_identity',HELPER)
  _IDENTITY=importlib.util.module_from_spec(sp);sp.loader.exec_module(_IDENTITY)
 return _IDENTITY

def scan_payload(file,declaration):
 """Actual full source/payload scan, used identically by prep and final guard."""
 identity=identities().expected_payload(declaration);file=no_symlink(file);before=file.stat()
 if not stat.S_ISREG(before.st_mode):raise ValueError('ASSET_NOT_REGULAR')
 payload=hashlib.sha256();git=(hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')if identity['raw_payload_git_blob_sha1_required']else None)
 count=0;fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  opened=os.fstat(fd)
  if (opened.st_dev,opened.st_ino,opened.st_size)!=(before.st_dev,before.st_ino,before.st_size):raise ValueError('ASSET_CHANGED_BEFORE_SCAN')
  with os.fdopen(fd,'rb',closefd=False)as stream:
   for block in iter(lambda:stream.read(1048576),b''):
    count+=len(block);payload.update(block)
    if git is not None:git.update(block)
  after=os.fstat(fd)
 finally:os.close(fd)
 path_after=file.stat()
 stable=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_mode)
 if stable(before)!=stable(after)or stable(before)!=stable(path_after)or count!=before.st_size:raise ValueError('ASSET_CHANGED_DURING_SCAN')
 actual_sha=payload.hexdigest();actual_git=git.hexdigest()if git is not None else None
 verified=identities().verify_payload_observation(declaration,count,actual_sha,actual_git)
 return {**verified,'actual_payload_bytes_hashed':count,'actual_payload_sha256':actual_sha,
  'actual_ordinary_payload_git_blob_sha1':actual_git,'actual_full_payload_scan':True,
  'payload_git_SHA1_computed':git is not None,'LFS_payload_git_SHA1_not_required':git is None}

def validate_model_assets(directory,public_lock_path,expected_catalog_path,*,root,
 public_lock_sha256,expected_catalog_sha256,epoch,kind,source_checkpoint,repository,revision):
 """Complete actual profile validator; a caller supplies separately pinned authority."""
 started=time.monotonic();root=Path(root);directory=no_symlink(directory)
 public_lock_path=no_symlink(public_lock_path);expected_catalog_path=no_symlink(expected_catalog_path)
 if sha(public_lock_path)!=public_lock_sha256 or sha(expected_catalog_path)!=expected_catalog_sha256:raise ValueError('SOURCE_ASSET_AUTHORITY_CHANGED')
 lock=read_metadata(public_lock_path);expected=read_metadata(expected_catalog_path)
 if (lock.get('epoch')!=epoch or lock.get('kind')!=kind or lock.get('repository')!=repository or lock.get('revision')!=revision
  or lock.get('model_directory')!=str(directory)or expected.get('repository')!=repository or expected.get('revision')!=revision):raise ValueError('ASSET_PROFILE_IDENTITY_MISMATCH')
 direct=no_symlink(directory/'asset-lock.json')
 if not direct.is_file()or direct.read_bytes()!=public_lock_path.read_bytes():raise ValueError('DIRECT_PUBLIC_ASSET_LOCK_MISMATCH')
 rows=lock.get('files');declared=expected.get('files')
 if not isinstance(rows,list)or not isinstance(declared,list)or not declared:raise ValueError('ASSET_CATALOG_MISSING')
 identities().bind_catalog(declared,rows);names={r['path']for r in declared}
 if {p.name for p in directory.iterdir()}!=names|{'asset-lock.json'}:raise ValueError('ASSET_DIRECTORY_INVENTORY_MISMATCH')
 by_source={r['path']:r for r in declared};results=[]
 for row in rows:
  if (directory/row['path']).stat().st_mode&0o222:raise ValueError('MODEL_PAYLOAD_MUST_BE_READONLY')
  result=scan_payload(directory/row['path'],by_source[row['path']])
  if result['actual_payload_sha256']!=row['sha256']or result['actual_payload_bytes_hashed']!=row['bytes']:raise ValueError('PAYLOAD_OBSERVED_LOCK_MISMATCH')
  results.append(result)
 return {'schema_version':1,'epoch':epoch,'kind':kind,'source_checkpoint':source_checkpoint,
  'status':'ALL_PROFILE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES',
  'validator_function':'model_assets_guard.validate_model_assets','validator_source':source_ref(Path(__file__),root),
  'identity_helper_source':source_ref(HELPER,root),'expected_catalog':source_ref(expected_catalog_path,root),
  'public_model_assets_lock':source_ref(public_lock_path,root),'external_direct_lock':{'path':str(direct),'bytes':direct.stat().st_size,'sha256':sha(direct),'byte_identical_to_public':True},
  'repository':repository,'revision':revision,'model_directory':str(directory),'directory_inventory':sorted(p.name for p in directory.iterdir()),
  'actual_payload_files_verified':len(results),'actual_payload_bytes_hashed':sum(r['actual_payload_bytes_hashed']for r in results),
  'ordinary_Git_payloads_verified':sum(r['raw_payload_git_sha1_verified']for r in results),
  'canonical_LFS_pointers_verified':sum(not r['raw_payload_git_sha1_verified']for r in results),'files':results,
  'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,
  'wall_seconds_hash_validation_only':time.monotonic()-started}

def validate_tasksource_catalog(path,expected_sha):
 """Pin to publisher Git/LFS before considering derived tokenizer SHA authority."""
 if sha(PREACQ)!=PREACQ_SHA or sha(path)!=expected_sha:raise ValueError('TASKSOURCE_SOURCE_CATALOG_CHANGED')
 original=read_metadata(PREACQ);catalog=read_metadata(path)
 if (catalog.get('repository'),catalog.get('revision'))!=(original['repository'],original['revision']):raise ValueError('TASKSOURCE_REPO_REVISION_CHANGED')
 sources={r['path']:r for r in original['files']};rows=catalog.get('files',[])
 if len(rows)!=9 or {r['path']for r in rows}!=set(sources):raise ValueError('TASKSOURCE_EXACT_NINEFILES_REQUIRED')
 for row in rows:
  source=sources[row['path']]
  if any(row.get(k)!=source[k]for k in ('bytes','source_url','upstream_git_blob_sha1')):raise ValueError('PUBLISHER_GIT_AUTHORITY_CHANGED')
  if 'upstream_sha256'in source:
   if row.get('upstream_sha256')!=source['upstream_sha256']:raise ValueError('PUBLISHER_LFS_SHA_CHANGED')
  elif 'metadata_body_sha256'in source:
   if row.get('metadata_body_sha256')!=source['metadata_body_sha256']:raise ValueError('PUBLISHER_METADATA_SHA_CHANGED')
  elif row['path']!='tokenizer.json'or not isinstance(row.get('metadata_body_sha256'),str)or len(row['metadata_body_sha256'])!=64:raise ValueError('ONLY_EXACT_TOKENIZER_GIT_MAY_DERIVE_SHA')
 return catalog

def validate_model_profiles(profiles,*,root,epoch,kind,source_checkpoint):
 """Same complete18-file real guard used prefreeze and by runtime callers."""
 if not isinstance(profiles,dict)or set(profiles)!=set(PROFILE_SPECS):raise ValueError('EXACT_TWO_MODEL_PROFILES_REQUIRED')
 results={}
 for tag in ('b354','tasksource'):
  row=profiles[tag];spec=PROFILE_SPECS[tag]
  expected_sha=row.get('expected_catalog_sha256')
  if tag=='b354'and expected_sha!=spec['catalog_sha256']:raise ValueError('SEPARATE_SOURCE_AUTHORITY_REQUIRED')
  if tag=='tasksource':validate_tasksource_catalog(row['expected_catalog_path'],expected_sha)
  result=validate_model_assets(row['model_directory'],row['public_lock_path'],row['expected_catalog_path'],root=root,
   public_lock_sha256=row['public_lock_sha256'],expected_catalog_sha256=expected_sha,epoch=epoch,kind=kind,
   source_checkpoint=source_checkpoint,repository=spec['repository'],revision=spec['revision'])
  if result['actual_payload_files_verified']!=spec['files']:raise ValueError('SOURCE_MODEL_INVENTORY_MISMATCH')
  results[tag]=result
 return {'schema_version':1,'epoch':epoch,'kind':kind,'source_checkpoint':source_checkpoint,
  'status':'BOTH_REAL_MODEL_PROFILES_ALL18_PAYLOADS_VERIFIED_NO_ML','profiles':results,
  'actual_payload_files_verified':sum(v['actual_payload_files_verified']for v in results.values()),
  'ordinary_Git_payloads_verified':sum(v['ordinary_Git_payloads_verified']for v in results.values()),
  'canonical_LFS_pointers_verified':sum(v['canonical_LFS_pointers_verified']for v in results.values()),
  'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0}

def validate_inherited_tasksource_profile(profiles,*,root,current_epoch,current_kind,current_source_checkpoint):
 """Fresh full scan; immutable direct/public asset-lock truthfully retains E40 origin."""
 if not isinstance(profiles,dict)or set(profiles)!={'tasksource'}:raise ValueError('EXACT_ONE_TASKSOURCE_PROFILE_REQUIRED')
 row=profiles['tasksource'];spec=PROFILE_SPECS['tasksource']
 validate_tasksource_catalog(row['expected_catalog_path'],row['expected_catalog_sha256'])
 result=validate_model_assets(row['model_directory'],row['public_lock_path'],row['expected_catalog_path'],root=root,
  public_lock_sha256=row['public_lock_sha256'],expected_catalog_sha256=row['expected_catalog_sha256'],
  epoch=40,kind='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT',
  source_checkpoint='2cf5aba60a050079506a5e9aa5463f44c1efcd5a',repository=spec['repository'],revision=spec['revision'])
 if result['actual_payload_files_verified']!=9:raise ValueError('TASKSOURCE_NINEFILE_INVENTORY_REQUIRED')
 return {'schema_version':1,'epoch':current_epoch,'kind':current_kind,'source_checkpoint':current_source_checkpoint,
  'status':'FRESH_NINE_INHERITED_TASKSOURCE_PAYLOADS_VERIFIED_ORIGIN_LOCK_PRESERVED_NO_ML',
  'profiles':{'tasksource':result},'actual_payload_files_verified':9,
  'ordinary_Git_payloads_verified':result['ordinary_Git_payloads_verified'],
  'canonical_LFS_pointers_verified':result['canonical_LFS_pointers_verified'],
  'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0}


def verify_runtime_files(venv,member_manifest_path,member_manifest_sha256,assets,*,root,wheel_identity_path=None,native_asset_root=None):
 """Fresh full runtime hashes only; never import any package or load native code."""
 started=time.monotonic();venv=no_symlink(venv);root=Path(root);native_asset_root=no_symlink(native_asset_root or root)
 wheel_identity_path=wheel_identity_path or root/'experiments/sota-2026-10-22/epoch17/preparation/python-wheel-identities.json'
 if sha(wheel_identity_path)!='6689210699a4171b54a38f8d14edba78c4b4b6390c76b6b05293a32f1ea2b8de':raise ValueError('CPU_WHEEL_SOURCE_AUTHORITY_CHANGED')
 wheels=read_metadata(wheel_identity_path).get('wheels',[])
 if len(wheels)!=31:raise ValueError('EXACT31_CPU_WHEEL_IDENTITIES_REQUIRED')
 if sha(member_manifest_path)!=member_manifest_sha256 or member_manifest_sha256!='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9':raise ValueError('RUNTIME_MEMBER_AUTHORITY_MISMATCH')
 members=read_metadata(member_manifest_path)
 if not isinstance(members,list)or len(members)!=17498 or len({r['path']for r in members})!=17498:raise ValueError('RUNTIME_MEMBER_INVENTORY_MISMATCH')
 for row in members:
  rel=row['path']
  if not isinstance(rel,str)or Path(rel).is_absolute()or any(x in('','.','..')for x in rel.split('/')):raise ValueError('UNSAFE_RUNTIME_MEMBER')
  file=no_symlink(venv/rel)
  if not file.is_file()or file.stat().st_size!=row['bytes']or sha(file)!=row['sha256']:raise ValueError('RUNTIME_MEMBER_BYTES_CHANGED')
 if not isinstance(assets,list)or len(assets)!=10 or len({r['path']for r in assets})!=10:raise ValueError('NATIVE_BGE_INVENTORY_MISMATCH')
 if {r['path']:r['sha256']for r in assets}!=NATIVE_BGE_SHA256:raise ValueError('NATIVE_BGE_SOURCE_AUTHORITY_CHANGED')
 for row in assets:
  rel=row['path']
  if not isinstance(rel,str)or Path(rel).is_absolute()or any(x in('','.','..')for x in rel.split('/')):raise ValueError('UNSAFE_NATIVE_BGE_ASSET')
  file=no_symlink(native_asset_root/rel)
  if not file.is_file()or file.stat().st_size!=row['bytes']or sha(file)!=row['sha256']:raise ValueError('NATIVE_BGE_BYTES_CHANGED')
 return {'status':'FULL_RUNTIME_FILES_HASH_VERIFIED_NO_PACKAGE_INITIALIZATION','wheel_members':17498,'official_CPU_wheels':31,'wheel_archives_rehashed':False,'native_BGE_assets':10,
  'member_manifest_sha256':member_manifest_sha256,'runtime_environment':str(venv),'native_asset_root':str(native_asset_root),'wall_seconds':time.monotonic()-started,
  'model_tokenizer_native_package_initializations':0,'case_oracle_reads':0,'stubs_used':False,'monkeypatches':[]}
