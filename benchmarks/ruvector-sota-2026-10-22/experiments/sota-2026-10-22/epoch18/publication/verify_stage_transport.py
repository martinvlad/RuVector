"""Read-only exact transport and reviewed-control verification."""
from pathlib import Path
import hashlib,json,sys
stage=Path(sys.argv[1]);phase=sys.argv[2];scope=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((stage/'manifest.json').read_text())
for row in m['large_blob_requests']+m['create_tree_groups']:
    p=stage/row['file'];assert p.stat().st_size==row['bytes']and sha(p)==row['sha256']
expected=json.loads((stage/'expected-leaves.json').read_text());prefix=m['scope']
out={}
for row in expected['files']:
    assert row['path'].startswith(prefix);r=dict(row,path=row['path'][len(prefix):]);assert r['path']not in out;out[r['path']]=r
with(scope/('expected-'+phase+'.json')).open('x')as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'));f.write('\n')
print(json.dumps({'stage':str(stage),'stage_manifest_sha256':sha(stage/'manifest.json'),'transport_hashes_verified':len(m['large_blob_requests'])+len(m['create_tree_groups']),'expected_leaves':len(out)}))
