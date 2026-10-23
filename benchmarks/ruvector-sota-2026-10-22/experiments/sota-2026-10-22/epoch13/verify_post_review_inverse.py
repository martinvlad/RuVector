from pathlib import Path
import json,hashlib,sys
pub=Path('/workspace/ruvector-eval/experiments/sota-2026-10-22/epoch13/publication');base=pub/'reviewed-base.private';st=pub/'stage'
def h(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def raw(x):return (json.dumps(x,indent=2)+'\n').encode()
old=load(base/'publication-map.json');new=load(pub/'publication-map.json');ob={x['path']:x for x in old['files']};nb={x['path']:x for x in new['files']};added=set(sys.argv[1:]);assert set(nb)-set(ob)==added
changed={p for p in ob if nb.get(p)!=ob[p]};assert changed=={'CONTINUATION.json','CHECKPOINT_MANIFEST.json'}
cm=load(st/'CHECKPOINT_MANIFEST.json');cm['project_files']=[x for x in cm['project_files'] if x['path'] not in added];assert raw(cm)==(base/'CHECKPOINT_MANIFEST.json').read_bytes()
c=load(st/'CONTINUATION.json');c['checkpoint_manifest_sha256']=h(raw(cm));assert raw(c)==(base/'CONTINUATION.json').read_bytes()
inv=dict(new);inv['files']=[ob.get(x['path'],x) for x in new['files'] if x['path'] not in added];inv['checkpoint_project_files']=old['checkpoint_project_files'];inv['new_project_files']=old['new_project_files'];assert raw(inv)==(base/'publication-map.json').read_bytes()
proof={'checks_passed':True,'reviewed_base_map_sha256':h((base/'publication-map.json').read_bytes()),'final_map_sha256':h((pub/'publication-map.json').read_bytes()),'additions':sorted(added),'only_existing_changes':sorted(changed),'inverse_reconstructs_byte_exact_base_map_CONT_CHECKPOINT':True,'final_leaves':len(nb),'final_project_files':new['checkpoint_project_files']}
with (pub/'post-review-inverse.private.json').open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps(proof))
