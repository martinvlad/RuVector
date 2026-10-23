"""Inventory exact final public source/artifacts after closed independent rejection."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
scope=Path(__file__).resolve().parent;root=scope/'project';base=root/'experiments/sota-2026-10-22';e=base/'epoch18'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)}
m=json.loads((e/'EPOCH_MANIFEST.json').read_text())
assert m['source_epoch_closed']is True and m['accepted']is False
assert m['actual_execution']['native_process_attempts']==1 and m['actual_execution']['allowed_further_epoch18_native_attempts']==0
files=[]
for part in ['candidate/epoch18','controller/epoch18','legal-transfer/epoch18','audit/epoch18','epoch18']:
    for p in sorted((base/part).rglob('*')):
        assert not any(x.is_symlink()for x in [p,*p.parents])
        if p.is_file():
            assert '__pycache__'not in p.parts and'assets'not in p.parts
            files.append(ident(p))
value={'schema_version':1,'epoch':18,'at':datetime.now(timezone.utc).isoformat(),
 'status':'CLOSED_REJECTED_NATIVE_EPOCH_EXACT_SOURCE_AND_ARTIFACT_INVENTORY',
 'source_checkpoint':'0eac156990f5a4ee0084af635eb3089913b437ff',
 'published_premeasurement_commit':'19106bac59a336accc28e5731744e08be9a825f2',
 'files':files,'scientific_snapshot':ident(e/'candidate-source-freeze.json'),'immutable_plan':ident(e/'plan.json'),
 'actual_independent_decision':ident(base/'audit/epoch18/acceptance-rejection-independent-v1.json'),
 'actual_identity_retirement':ident(base/'legal-transfer/epoch18/postrun-identity-retirement-v1.json'),
 'scope':'All public18source/actualrun/results/reporting/future-protocol artifacts existing after closed independent result consistency review. This inventory excludes itself and later appended final publication reviews to avoid cycles; final CHECKPOINT_MANIFEST covers every published file.',
 'actual_execution':m['actual_execution'],'accepted':False,'champion_unchanged':True,
 'official_score':None,'official_rank':None,'official_SOTA_verified':False,
 'future_qualification_spec_status':'Source-only original generic engineering canaries; zero execution/reservations here, no synthetic benchmark generalization claim.'}
out=e/'SOURCE_MANIFEST.json'
with out.open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps({'source_manifest':ident(out),'listed_files':len(files)}))
