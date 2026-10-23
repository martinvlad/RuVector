"""Save the exact v2 source-complete stage before the four final proof additions."""
from pathlib import Path
import json,hashlib,shutil
p=Path(__file__).resolve().parent/'publication';stage=p/'stage';dest=p/'reviewed-base-v2.private'
def sha(b):return hashlib.sha256(b).hexdigest()
assert not dest.exists(),'Never replace the v2 reviewed base'
proofs=('publication-cold-review-v1.json','publication-asset-bindings-v1.json','cold-cached-replay-independent-v1.json','final-publication-review-v1.json')
for n in proofs:assert not (stage/'experiments/sota-2026-10-22/audit/epoch13'/n).exists(),'Finalproof already present'
assert (p/'publication-map.json').read_bytes()==(p/'publication-map-v2.beforeproof.json').read_bytes(),'V2 map changed before review'
m=json.loads((p/'publication-map.json').read_text());assert len({x['path'] for x in m['files']})==len(m['files'])
for x in m['files']:
 f=stage/x['path'];assert f.is_file() and not f.is_symlink();b=f.read_bytes();assert len(b)==x['bytes'] and sha(b)==x['sha256'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1']
c=json.loads((stage/'CONTINUATION.json').read_text());assert c['source_plan_preserved']['pins']==196 and c['source_plan_preserved']['unchanged'] and c['source_plan_preserved']['new_model_native_calls']==0
cor=c['source_closure_correction'];assert sha((stage/cor['path']).read_bytes())==cor['sha256'];assert c['checkpoint_manifest_sha256']==sha((stage/'CHECKPOINT_MANIFEST.json').read_bytes())
dest.mkdir(exist_ok=False)
for n,src in [('publication-map.json',p/'publication-map.json'),('CONTINUATION.json',stage/'CONTINUATION.json'),('CHECKPOINT_MANIFEST.json',stage/'CHECKPOINT_MANIFEST.json')]:shutil.copy2(src,dest/n)
print(json.dumps({'reviewed_v2_base_map_sha256':sha((dest/'publication-map.json').read_bytes()),'exact3files':True,'reviewed_leaf_files':len(m['files']),'proofs_present':False,'source_plan_196_unchanged':True,'native_model_paid_GPU_calls':0}))
