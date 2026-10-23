"""Bind one fixed paired semantic study after prelabel source freeze.

Pure hashing and metadata assembly; does not load models or interpret gold.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os

ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch16'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):
    with p.open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())

def main():
    frozen=E/'candidate-source-freeze.json';proof=read(frozen)
    for row in proof['files']:
        p=ROOT/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
    assert not (S/'legal-transfer/epoch16/confirmation24.jsonl').exists()
    dev=S/'legal-transfer/epoch16/development24.jsonl';assert dev.is_file()
    materialized=read(S/'legal-transfer/epoch16/dev-materialization.json')
    assert materialized['annotation_choices_projected']==24 and materialized['other_role_annotation_choices_accessed']==0
    assert materialized['root_source_freeze_sha256']==sha(frozen)
    capacity=read(S/'audit/epoch16/context-capacity-independent-v1.json')
    phases=capacity['phases'];du,cu=phases['development']['max_units'],phases['confirmation']['max_units']
    assert type(du)is int and type(cu)is int and min(du,cu)>0
    old=read(S/'epoch15/plan.v2.json');pins={r['path']:r for r in old['pins']}
    for rel in ['candidate/epoch16','controller/epoch16','legal-transfer/epoch16','audit/epoch16','epoch16']:
        for p in sorted((S/rel).rglob('*')):
            if not p.is_file() or '__pycache__'in p.parts or '/assets/'in str(p):continue
            row=ident(p);pins[row['path']]={'path':row['path'],'sha256':row['sha256']}
    original=ROOT/'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
    assert sha(original)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
    pins[str(original.relative_to(ROOT))]={'path':str(original.relative_to(ROOT)),'sha256':sha(original)}
    for n in ['RESTORE_EPOCH3_DATA.json','restore_original_data.py']:
        p=S/'candidate/epoch3/publication'/n;pins[str(p.relative_to(ROOT))]={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
    research={'schema_version':1,'epoch':16,'hypothesis':'Frozen whole-proposition NOT paired mirrored mean on unchanged official NLI reader, with originalH same-premise causal control and matched native/lexical/positional retrieval.',
        'source_freeze':ident(frozen),'data_contract':ident(S/'legal-transfer/epoch16/data-contract.pre-label.json'),
        'acceptance_contract':ident(S/'audit/epoch16/acceptance-contract-v1.json'),
        'capacity':ident(S/'audit/epoch16/context-capacity-independent-v1.json'),
        'train':[],'calibration':[],'DEV_queries':24,'lazy_CONF_queries':24,
        'new_native_model_calls':0,'paid_GPU_calls':0,'official_score':None,'official_rank':None}
    write(E/'RESEARCH_PLAN.json',research);pins[str((E/'RESEARCH_PLAN.json').relative_to(ROOT))]={'path':str((E/'RESEARCH_PLAN.json').relative_to(ROOT)),'sha256':sha(E/'RESEARCH_PLAN.json')}
    plan={k:old[k]for k in ['expected_native_receipt','expected_nli_revision','expected_nli_sha256','limits','public_model_acquisition','inference_python']}
    plan.update(schema_version=1,epoch=16,revision='paired-whole-proposition-NOT-mirrored-mean-v1',
        study_id='native-paired-whole-proposition-negation-e16',train='none',calibration='none',
        datasets={'development':'experiments/sota-2026-10-22/legal-transfer/epoch16/development24.jsonl',
                  'confirmation':'experiments/sota-2026-10-22/legal-transfer/epoch16/confirmation24.jsonl'},
        lazy_confirmation={'builder_path':'experiments/sota-2026-10-22/legal-transfer/epoch16/build.py',
            'builder_sha256':sha(S/'legal-transfer/epoch16/build.py'),
            'source_path':str(original.relative_to(ROOT)),'source_sha256':sha(original),
            'source_freeze_path':str(frozen.relative_to(ROOT)),'source_freeze_sha256':sha(frozen),
            'input_allowlist':'experiments/sota-2026-10-22/legal-transfer/epoch16/confirmation-input-allowlist.json',
            'source_freeze_and_exact_recipe_are_dataset_identity':True,'annotation_projection_only_after_admission':True},
        prior_closed_study_native_attempts=17,new_study_native_attempt_cap=2,new_study_native_attempts_before=0,
        prior_closed_original_study_attempts=6,prior_closed_epoch5_study_attempts=1,
        prior_closed_epoch6_study_attempts=1,prior_closed_epoch7_study_attempts=1,
        prior_closed_epoch8_study_attempts=2,prior_closed_epoch9_study_attempts=1,
        prior_closed_epoch10_study_attempts=1,prior_closed_epoch11_study_attempts=1,
        prior_closed_epoch12_study_attempts=1,prior_closed_epoch13_study_attempts=1,
        prior_closed_epoch14_native_attempts=0,prior_closed_epoch15_study_attempts=1,
        lease_expires_unix=read(ROOT.parent/'owner.json')['expires_unix'],actual_project=str(ROOT),
        research_plan_sha256=sha(E/'RESEARCH_PLAN.json'),
        candidate_manifest_sha256=sha(S/'candidate/epoch16/proposal-manifest.json'),
        runtime_admission={'formula_id':'24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
            'max_DEV_units':du,'max_confirmation_units':cu,
            'formula':'24*maxDEVHTTP*max(1,CONFmaxunits/DEVmaxunits)+2*fullphaseDEVinit+60; require<=600 and lease>=forecast+30',
            'scope':'Label-free exact source capacity; full actual phase initialization measured from pre-Popen invocation; conservative heuristic, no performance guarantee.'},
        acceptance_contract=ident(S/'audit/epoch16/acceptance-contract-v1.json'),
        source_policy='Exact source shared priority160 and rawH-only retrieval; same whole premise fits bothH/fullNOT-H<=512, no clipping/aliases; numerical surface retention is not arithmetic/evidence sufficiency.',
        promotion='No automaticchampion replacement/submission; frozen independent typed/binary DEV+unusedCONF acceptance AND publisher eligibility/protocol required.',
        selected_model_changed=False,official_score=None,official_rank=None,pins=sorted(pins.values(),key=lambda r:r['path']))
    for row in plan['pins']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    write(E/'plan.json',plan)
    write(E/'freeze-receipt.json',{'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),
        'plan':ident(E/'plan.json'),'source_freeze':ident(frozen),'pins':len(plan['pins']),
        'DEV_annotations_projected':24,'CONF_annotations_projected':0,'actual_native_model_fit_paid_GPU_calls':0})
    print(json.dumps({'plan':ident(E/'plan.json'),'pins':len(plan['pins']),'runtime_source_units':{'development':du,'confirmation':cu}}))

if __name__=='__main__':main()
