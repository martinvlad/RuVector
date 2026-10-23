"""Assemble operational metadata from immutable sources without reading labels."""
from pathlib import Path
import copy,hashlib,json,os
ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch18'
DIRS=['candidate/epoch18','controller/epoch18','legal-transfer/epoch18','audit/epoch18','epoch18']
def safe(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    assert '..' not in p.parts,'Parent traversal forbidden'
    p.relative_to(ROOT)
    assert not any(x.is_symlink() for x in [p,*p.parents]),'Symlink ancestor forbidden: '+str(p)
    return p
def absent(p):assert not os.path.lexists(safe(p)),'Forbidden existing output: '+str(p)
def read(p):return json.loads(safe(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def ident(p):
    p=safe(p);return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):
    with safe(p).open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())
def frozen():
    path=E/'candidate-source-freeze.json';value=read(path)
    assert value['source_checkpoint']=='0eac156990f5a4ee0084af635eb3089913b437ff'
    for row in value['files']:
        p=ROOT/row['path'];assert not p.is_symlink()and ident(p)==row,row['path']
    return path,value
def current_files():
    rows=[]
    for rel in DIRS:
        for p in sorted(safe(S/rel).rglob('*')):
            safe(p)
            if '__pycache__'in p.parts or'assets'in p.relative_to(S/rel).parts:continue
            assert not p.is_symlink(),str(p)
            if p.is_file():rows.append(ident(p))
    return rows
def operational_plan():
    freeze,proof=frozen()
    for name in ['development24.jsonl','dev-inputs-only.json','confirmation24.jsonl']:
        absent(S/'legal-transfer/epoch18'/name)
    p=copy.deepcopy(read(S/'epoch17/plan.json'))
    p['limits']['seconds_per_decision']=30
    p.update(epoch=18,controller_version='epoch18-controller-v1',
        revision='official-xlarge-mnli-dynamic-int8-matched-previous-reader-e18-v1',
        study_id='native-microsoft-xlarge-typed-reader-e18',
        prior_closed_epoch17_native_attempts=0,actual_project=str(ROOT),
        lease_expires_unix=json.loads((ROOT.parent/'owner.json').read_text())['expires_unix'],
        candidate_manifest_sha256=sha(S/'candidate/epoch18/proposal-manifest.json'),
        research_plan_sha256=sha(E/'RESEARCH_PLAN.json'),
        acceptance_contract=ident(S/'audit/epoch18/acceptance-contract-v1.json'),
        measurement_plan=False,operational_prelabel_only=True)
    p['datasets']={'development':'experiments/sota-2026-10-22/legal-transfer/epoch18/development24.jsonl',
                   'confirmation':'experiments/sota-2026-10-22/legal-transfer/epoch18/confirmation24.jsonl'}
    p['lazy_confirmation']={'builder_path':'experiments/sota-2026-10-22/legal-transfer/epoch18/build.py',
        'builder_sha256':sha(S/'legal-transfer/epoch18/build.py'),
        'source_path':'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json',
        'source_sha256':'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
        'source_freeze_path':str(freeze.relative_to(ROOT)),'source_freeze_sha256':sha(freeze),
        'input_allowlist':'experiments/sota-2026-10-22/legal-transfer/epoch18/confirmation-input-allowlist.json',
        'source_freeze_and_exact_recipe_are_dataset_identity':True,'annotation_projection_only_after_admission':True}
    p['runtime_admission'].update(max_DEV_units=1,max_confirmation_units=1,capacity_pending_label_free_inputs=True,
        scope='Positive1/1 operational placeholders only. Source capacity unmeasured; no native admission. Actual unit counts are bound after label-free inputs and before measurement.')
    pins={r['path']:r for r in p['pins']}
    for row in proof['files']+[ident(freeze)]:
        pins[row['path']]={'path':row['path'],'sha256':row['sha256']}
    p['pins']=sorted(pins.values(),key=lambda r:r['path'])
    for row in p['pins']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    return p
