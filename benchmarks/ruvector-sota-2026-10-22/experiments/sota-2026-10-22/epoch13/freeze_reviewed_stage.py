from pathlib import Path
import json,hashlib,shutil
p=Path(__file__).resolve().parent/'publication';stage=p/'stage';dest=p/'reviewed-base.private';dest.mkdir(exist_ok=False)
def sha(b):return hashlib.sha256(b).hexdigest()
proofs=('publication-cold-review-v1.json','publication-asset-bindings-v1.json','cold-cached-replay-independent-v1.json','final-publication-review-v1.json')
for n in proofs:assert not (stage/'experiments/sota-2026-10-22/audit/epoch13'/n).exists(),'Finalproof already present'
m=json.loads((p/'publication-map.json').read_text());assert len({x['path'] for x in m['files']})==len(m['files'])
for x in m['files']:
 f=stage/x['path'];b=f.read_bytes();assert len(b)==x['bytes'] and sha(b)==x['sha256'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1']
for n,src in [('publication-map.json',p/'publication-map.json'),('CONTINUATION.json',stage/'CONTINUATION.json'),('CHECKPOINT_MANIFEST.json',stage/'CHECKPOINT_MANIFEST.json')]:shutil.copy2(src,dest/n)
print(json.dumps({'reviewed_base_map_sha256':sha((dest/'publication-map.json').read_bytes()),'exact3files':True,'reviewed_leaf_files':len(m['files']),'proofs_present':False}))
