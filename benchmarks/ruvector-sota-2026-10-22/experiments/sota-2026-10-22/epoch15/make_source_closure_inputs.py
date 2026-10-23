"""Declare exact reviewed public source and explicit separately-restored model/native identities."""
from pathlib import Path
import json,hashlib,os
ROOT=Path(__file__).resolve().parents[3];S=ROOT/'experiments/sota-2026-10-22';HERE=Path(__file__).parent;KIT=ROOT.parent/'kit'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def identity(p):
 p=Path(p);return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())
pub={}
def add(r):
 p=r['path'];v={k:r[k] for k in ['path','bytes','sha256']}
 if p in pub and pub[p]!=v:raise ValueError('Conflicting public identity '+p)
 pub[p]=v
for r in read(KIT/'CHECKPOINT_MANIFEST.json')['project_files']:add(r)
for r in read(KIT/'KIT_MANIFEST.json')['project_files']:add(r)
base={r['path']:r for r in read(KIT/'BASE_PUBLIC_MANIFEST.json')['files']}
for name in read(KIT/'BASE_DOWNLOADS.json')['paths']:add(base[name])
new=[]
for d in ['candidate/epoch15','audit/epoch15','legal-transfer/epoch15','controller/epoch15','epoch15']:
 for f in sorted((S/d).rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts or '/candidate/epoch15/assets/' in str(f):continue
  r=identity(f);add(r);new.append(r)
for name in ['model-assets.lock.json','assets.lock.json']:
 assert (S/'candidate/epoch15'/name).is_file()
registry=[]
def external(r,kind,manifest,helper):
 p=ROOT/r['path'];assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],r['path']
 registry.append({**{k:r[k] for k in ['path','bytes','sha256']},'kind':kind,'provenance_manifest':{k:identity(manifest)[k] for k in ['path','sha256']},'acquisition_helper':{k:identity(helper)[k] for k in ['path','sha256']}})
ml=S/'candidate/epoch15/model-assets.lock.json'
for r in read(ml)['assets']:external(r,'model_asset',ml,S/'candidate/epoch15/acquire_assets.py')
for r in read(ROOT/'assets.lock.json')['assets']:external(r,'model_asset',ROOT/'assets.lock.json',ROOT/'acquire_models.py')
core=S/'candidate/epoch5/reconstruction/official-package-closure.json';types=S/'candidate/epoch5/reconstruction/typesafe-runtime-closure.json'
for manifest,rows in [(core,[x for group in read(core)['packages'] for x in group['files']]),(types,read(types)['files'])]:
 for r in rows:
  if r['path'] not in pub:external(r,'native_runtime',manifest,S/'epoch15/preparation/restore_native15.py')
assert len(registry)==13,len(registry)
write(HERE/'declared-public.json',list(sorted(pub.values(),key=lambda x:x['path'])))
write(HERE/'external-registry.json',registry)
write(HERE/'public-source-allowlist.before-native.json',{'schema_version':1,'scope':'Explicit enumerated reviewed public source/prelaunch artifacts, excludes model assets/__pycache__. Later exact results/final reports require separate append review.','files':sorted({r['path']:r for r in new}.values(),key=lambda x:x['path']),'self_and_guard_input_output_cycle_excluded':True})
print(json.dumps({'declared_public_paths':len(pub),'explicit_external_registry':len(registry),'new_public_artifacts':len({x['path'] for x in new}),'model_native_calls':0}))

