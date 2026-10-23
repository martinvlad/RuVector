"""Append one reviewed source-closure supplement; never infer, alter a plan or publish remotely."""
from pathlib import Path
import argparse,hashlib,json,shutil
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch13';pub=e/'publication';st=pub/'stage'
V1_MAP_SHA='fdb4372ba2b7cb5645b7d1dd3cbcafd974865470ac4281b58804ea1f2e74236b'
SUPPLEMENT='experiments/sota-2026-10-22/legal-transfer/epoch13/COLD_SOURCE_SUPPLEMENT.v1.json'
CORRECTION='experiments/sota-2026-10-22/epoch13/SOURCE_CLOSURE_CORRECTION.v1.json'
BASE='experiments/sota-2026-10-22/'
REQUIRED_EXTRA={SUPPLEMENT,CORRECTION,*[BASE+'audit/epoch13/'+n for n in ('publication-cold-attempt-v1.json','review_publication_v2.py','bind_publication_assets_v2.py')],*[BASE+'epoch13/'+n for n in ('append_source_closure_supplement_v1.py','freeze_reviewed_stage_v2.py','verify_post_review_inverse_v2.py')]}
def h(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def raw(x):return (json.dumps(x,indent=2)+'\n').encode()
def leaf(q,b):return {'path':q,'bytes':len(b),'sha256':h(b),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}
def safe(q):
 p=Path(q);assert not p.is_absolute() and '..' not in p.parts and p.parts[:2]==('experiments','sota-2026-10-22'),q
 return p
ap=argparse.ArgumentParser();ap.add_argument('--allowlist',type=Path,required=True);args=ap.parse_args()
# Every check through preservation runs before canonical stage mutation.
mp=pub/'publication-map.json';original=mp.read_bytes();assert h(original)==V1_MAP_SHA,'Original v1 map differs';m=json.loads(original);assert len(m['files'])==2082 and m['checkpoint_project_files']==2012 and m['new_project_files']==165
assert (pub/'reviewed-base.private/publication-map.json').read_bytes()==original,'Prior reviewed base must remain byte exact'
assert not (pub/'source-closure-append-v1.private.json').exists(),'No source-closure retry'
assert not (pub/'publication-map-v2.beforeproof.json').exists(),'V2 already exists'
plan=load(e/'plan.json');assert len(plan['pins'])==196;pins={x['path']:x['sha256'] for x in plan['pins']};plan_sha=h((e/'plan.json').read_bytes())
for x in plan['pins']:
 f=e/'project'/x['path'];assert f.is_file() and h(f.read_bytes())==x['sha256'],'Frozen actual196 source/asset differs:'+x['path']
allow=load(args.allowlist);entries=allow['files'];by={x['path']:x for x in entries};assert len(by)==len(entries),'Duplicate approved addition'
sup=load(r/SUPPLEMENT);sf=sup['files'];assert len(sf)==13 and len({x['path'] for x in sf})==13
source_paths={x['path'] for x in sf};assert not source_paths & REQUIRED_EXTRA
assert len(by)==21 and set(by)==source_paths|REQUIRED_EXTRA,'Require exact reviewed source13 + eight fixed public closure artifacts'
old={x['path']:x for x in m['files']};assert not set(by)&set(old),'Source-closure additions must all be new'
for x in sf:
 q=x['path'];safe(q);assert q in pins and pins[q]==x['sha256'],'Supplement must match frozen196 source pin:'+q
 assert by[q]['bytes']==x['bytes'] and by[q]['sha256']==x['sha256']
for q,x in by.items():
 rel=safe(q);f=r/rel;assert f.is_file() and not f.is_symlink();b=f.read_bytes();b.decode('utf8');assert len(b)==x['bytes'] and h(b)==x['sha256'],q
for q,x in old.items():
 f=st/q;assert f.is_file() and not f.is_symlink();b=f.read_bytes();assert leaf(q,b)==x,'Original staged leaf differs:'+q
assert h((st/BASE/'epoch13/plan.json').read_bytes())==plan_sha
for n in ('CONTINUATION.json','CHECKPOINT_MANIFEST.json'):assert (pub/'reviewed-base.private'/n).read_bytes()==(st/n).read_bytes()
cm=load(st/'CHECKPOINT_MANIFEST.json');cmold={x['path']:x for x in cm['project_files']};assert len(cmold)==2012 and len(cmold)-1847==165
assert not set(by)&set(cmold)
# Preserve full v1 bytes independently: copy2, never hardlink to mutable canonical stage.
preserved=pub/'stage-v1.source-gap-preserved.local-only';assert not preserved.exists(),'Do not overwrite v1 stage preservation';shutil.copytree(st,preserved)
for q,x in old.items():assert leaf(q,(preserved/q).read_bytes())==x
with (pub/'publication-map-v1.source-gap-preserved.local-only.json').open('xb') as f:f.write(original)
assert (pub/'reviewed-base.private/publication-map.json').read_bytes()==original
for q,x in by.items():
 dst=st/q;assert not dst.exists();dst.parent.mkdir(parents=True,exist_ok=True);b=(r/q).read_bytes();assert h(b)==x['sha256'];dst.write_bytes(b);cmold[q]={'path':q,'bytes':len(b),'sha256':h(b)}
cm['project_files']=[cmold[q] for q in sorted(cmold)];(st/'CHECKPOINT_MANIFEST.json').write_bytes(raw(cm))
c=load(st/'CONTINUATION.json');c['checkpoint_manifest_sha256']=h((st/'CHECKPOINT_MANIFEST.json').read_bytes());c['source_closure_correction']={'path':CORRECTION,'sha256':h((r/CORRECTION).read_bytes())};c['source_plan_preserved']={'path':BASE+'epoch13/plan.json','sha256':plan_sha,'pins':196,'unchanged':True,'new_model_native_calls':0};(st/'CONTINUATION.json').write_bytes(raw(c))
files=[leaf(str(f.relative_to(st)),f.read_bytes()) for f in sorted(st.rglob('*')) if f.is_file()];new=dict(m);new.update(files=files,checkpoint_project_files=len(cmold),new_project_files=len(cmold)-1847);newraw=raw(new);mp.write_bytes(newraw)
# Assert only the two derived controls changed; all other prior staged leaves are exact.
nb={x['path']:x for x in files};assert set(nb)-set(old)==set(by);changed={q for q in old if nb[q]!=old[q]};assert changed=={'CHECKPOINT_MANIFEST.json','CONTINUATION.json'}
assert (pub/'reviewed-base.private/publication-map.json').read_bytes()==original
with (pub/'publication-map-v2.beforeproof.json').open('xb') as f:f.write(newraw)
receipt={'checks_passed':True,'original_map_sha256':V1_MAP_SHA,'v2_beforeproof_map_sha256':h(newraw),'preserved_v1_stage':preserved.name,'reviewed_v1_base_preserved':True,'additions':[by[q] for q in sorted(by)],'only_existing_changes':sorted(changed),'frozen_plan_sha256':plan_sha,'frozen_candidate_pins':196,'frozen_plan_and_actual_outputs_unchanged':True,'new_project_files':len(cmold)-1847,'checkpoint_project_files':len(cmold),'public_leaves':len(files),'native_model_paid_GPU_calls':0}
with (pub/'source-closure-append-v1.private.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt))
