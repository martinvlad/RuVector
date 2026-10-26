"""Exact inherited fresh CPU-runtime/native file validator; no ML imports."""
from pathlib import Path
import hashlib
import json
import stat
import time
ASSET_PREFLIGHT_BINDINGS_READY=True
NATIVE_BGE_SHA256={'models/bge-small-en-v1.5/model.onnx': '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35', 'models/bge-small-en-v1.5/tokenizer.json': 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66', 'retrieval/node_modules/@ruvector/core/index.js': 'eeba197be4085adb3492b8bc53cd61870f57d6bc18a9a5f1cd2ebec4b1908bee', 'retrieval/node_modules/@ruvector/core/package.json': '729e07f6c040bd47ba687cde8ad5681088187e53812e89d77d646ff48088a5e4', 'retrieval/node_modules/@ruvector/core/README.md': '82b4f4845e0753732a66dc88ddd801502449b60ad1100b273ae34d1035e8b932', 'retrieval/node_modules/@ruvector/core/index.d.ts': '36411710e6879c76dca228c4cff97993c4e95cee70388c2f936c79b01536ac54', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js': 'f392127e6cd14141107fa432a43bbccc2fa1d574630a6fe2611688c66a48a7e9', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json': 'afca994434efaadf637eb7d28bfd48da9dda69f24513bfb498c4ab9459d2fdf4', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/README.md': 'dd25a68639af6bf44b4e0cd1388eb119047a7bd4f21ef99ece9ded424d3a4a89', 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node': 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'}


def no_symlink(path):
 p=Path(path)
 if any(q.is_symlink()for q in(p,*p.parents)):raise ValueError('ASSET_SYMLINK_REFUSED')
 return p


def sha(path):
 h=hashlib.sha256()
 with no_symlink(path).open('rb')as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()


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


def verify_runtime_files(venv,member_manifest_path,member_manifest_sha256,assets,*,root,wheel_identity_path=None,native_asset_root=None):
 """Fresh full runtime hashes only; never import any package or load native code."""
 if not ASSET_PREFLIGHT_BINDINGS_READY:raise RuntimeError('E42_TEMPLATE_PENDING_BINDINGS_NO_RUNTIME_SCAN')
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


