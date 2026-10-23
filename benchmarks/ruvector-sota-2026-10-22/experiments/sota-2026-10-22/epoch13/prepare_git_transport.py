from pathlib import Path
import json,hashlib
s=Path('/workspace/ruvector-eval/experiments/sota-2026-10-22/epoch13');pub=s/'publication';stage=pub/'stage';m=json.loads((pub/'publication-map.json').read_text());old={x['path']:x['git_blob_sha1'] for x in json.loads((s/'durable-files.json').read_text())['files']};assert (stage/'experiments/sota-2026-10-22/audit/epoch13/final-publication-review-v1.json').exists()
transport=pub/'transport';transport.mkdir(exist_ok=False);prefix='benchmarks/ruvector-sota-2026-10-22/';big=[];groups=[];current=[]
def write(name,obj):
 raw=json.dumps(obj,ensure_ascii=True,separators=(',',':')).encode('ascii');(transport/name).write_bytes(raw);return {'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
for x in m['files']:
 b=(stage/x['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==x['sha256'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1']
 if old.get(x['path'])==x['git_blob_sha1']:continue
 entry={'path':prefix+x['path'],'mode':'100644','type':'blob','content':b.decode('utf8')}
 if len(json.dumps(entry,ensure_ascii=True,separators=(',',':')))>2200000:
  meta=write(f'blob-{len(big):03d}.json',entry.pop('content'));meta.update(path=x['path'],git_blob_sha1=x['git_blob_sha1'],source_bytes=x['bytes']);big.append(meta);entry['sha']=x['git_blob_sha1']
 candidate=current+[entry]
 if current and len(json.dumps(candidate,ensure_ascii=True,separators=(',',':')))>2200000:
  groups.append(write(f'tree-{len(groups):03d}.json',current));current=[entry]
 else:current=candidate
if current:groups.append(write(f'tree-{len(groups):03d}.json',current))
expected=write('expected-leaves.json',{x['path']:{'sha':x['git_blob_sha1'],'size':x['bytes']} for x in m['files']});manifest={'schema_version':1,'map_sha256':hashlib.sha256((pub/'publication-map.json').read_bytes()).hexdigest(),'public_leaves':len(m['files']),'large_blobs':big,'tree_groups':groups,'expected':expected};(transport/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'large_blobs':len(big),'blob_bridge_bytes':sum(x['bytes'] for x in big),'tree_groups':len(groups),'tree_bridge_bytes':sum(x['bytes'] for x in groups),'leaves':len(m['files'])}))
