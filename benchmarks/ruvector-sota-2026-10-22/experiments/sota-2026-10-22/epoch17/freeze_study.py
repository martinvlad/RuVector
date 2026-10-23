"""Freeze one official larger-reader study after source and label-free capacity gates.

No model loads, fitting, inference, or annotation choice inspection occurs here.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,copy
ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch17'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):
    with p.open('x')as f:
        json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())

def main():
    frozen=E/'candidate-source-freeze.json';proof=read(frozen)
    for row in proof['files']:
        p=ROOT/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
    assert not (S/'legal-transfer/epoch17/confirmation24.jsonl').exists()
    assert not (E/'launch.json').exists()
    dev=S/'legal-transfer/epoch17/development24.jsonl';assert dev.is_file()
    materialized=read(S/'legal-transfer/epoch17/dev-materialization.json')
    assert materialized['annotation_choices_projected']==24 and materialized['other_role_annotation_choices_accessed']==0
    assert materialized['root_source_freeze_sha256']==sha(frozen)
    capacity=read(S/'audit/epoch17/context-capacity-independent-v1.json')
    assert capacity.get('checks_passed') is True
    assert capacity.get('status')=='INDEPENDENT_LABEL_FREE_BOTH_READER_CAPACITY_PASS'
    assert capacity.get('model_native_fit_paid_GPU_calls')==0
    phases=capacity['phases'];du,cu=phases['development']['max_units'],phases['confirmation']['max_units']
    assert type(du)is int and type(cu)is int and min(du,cu)>0
    old=read(S/'epoch15/plan.v2.json');pins={r['path']:r for r in old['pins']}
    for rel in ['candidate/epoch17','controller/epoch17','legal-transfer/epoch17','audit/epoch17','epoch17']:
        for p in sorted((S/rel).rglob('*')):
            if not p.is_file() or '__pycache__'in p.parts or '/assets/'in str(p):continue
            row=ident(p);pins[row['path']]={'path':row['path'],'sha256':row['sha256']}
    for rel in ['epoch16/source_closure.mjs','epoch16/source-data-LICENSE.txt',
                'candidate/epoch3/publication/RESTORE_EPOCH3_DATA.json',
                'candidate/epoch3/publication/restore_original_data.py']:
        p=S/rel;pins[str(p.relative_to(ROOT))]={'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
    original=S/'legal-transfer/epoch3/sources/original-train.json'
    assert sha(original)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
    pins[str(original.relative_to(ROOT))]={'path':str(original.relative_to(ROOT)),'sha256':sha(original)}
    assets=read(S/'candidate/epoch17/model-assets.lock.json')
    for row in assets['assets']:
        p=ROOT/row['path']
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        pins[row['path']]={'path':row['path'],'sha256':row['sha256']}
    research={'schema_version':1,'epoch':17,
        'hypothesis':'Official Microsoft DeBERTa-v2-xlarge MNLI 900M typed capacity with native exact-source evidence may improve vs previous15 on identical primary premise; matched same-new-reader retrieval ablations, no model/precision/context grid.',
        'source_freeze':ident(frozen),'data_contract':ident(S/'legal-transfer/epoch17/data-contract.pre-label.json'),
        'acceptance_contract':ident(S/'audit/epoch17/acceptance-contract-v1.json'),
        'capacity':ident(S/'audit/epoch17/context-capacity-independent-v1.json'),
        'train':[],'calibration':[],'DEV_queries':24,'lazy_CONF_queries':24,
        'confirmed_legal_superiority_before_measurement':False,
        'new_native_model_calls':0,'paid_GPU_calls':0,'official_score':None,'official_rank':None}
    write(E/'RESEARCH_PLAN.json',research)
    pins[str((E/'RESEARCH_PLAN.json').relative_to(ROOT))]={'path':str((E/'RESEARCH_PLAN.json').relative_to(ROOT)),'sha256':sha(E/'RESEARCH_PLAN.json')}
    plan={k:copy.deepcopy(old[k])for k in ['expected_native_receipt','expected_nli_revision','expected_nli_sha256','limits','inference_python']}
    plan['limits']['seconds_per_decision']=60
    plan.update(schema_version=1,epoch=17,controller_version='epoch17-controller-v1',
        revision='official-xlarge-mnli-dynamic-int8-matched-previous-reader-v1',
        study_id='native-microsoft-xlarge-typed-reader-e17',train='none',calibration='none',
        datasets={'development':'experiments/sota-2026-10-22/legal-transfer/epoch17/development24.jsonl',
                  'confirmation':'experiments/sota-2026-10-22/legal-transfer/epoch17/confirmation24.jsonl'},
        lazy_confirmation={'builder_path':'experiments/sota-2026-10-22/legal-transfer/epoch17/build.py',
            'builder_sha256':sha(S/'legal-transfer/epoch17/build.py'),
            'source_path':str(original.relative_to(ROOT)),'source_sha256':sha(original),
            'source_freeze_path':str(frozen.relative_to(ROOT)),'source_freeze_sha256':sha(frozen),
            'input_allowlist':'experiments/sota-2026-10-22/legal-transfer/epoch17/confirmation-input-allowlist.json',
            'source_freeze_and_exact_recipe_are_dataset_identity':True,'annotation_projection_only_after_admission':True},
        prior_closed_study_native_attempts=18,new_study_native_attempt_cap=2,new_study_native_attempts_before=0,
        prior_closed_original_study_attempts=6,prior_closed_epoch5_study_attempts=1,
        prior_closed_epoch6_study_attempts=1,prior_closed_epoch7_study_attempts=1,
        prior_closed_epoch8_study_attempts=2,prior_closed_epoch9_study_attempts=1,
        prior_closed_epoch10_study_attempts=1,prior_closed_epoch11_study_attempts=1,
        prior_closed_epoch12_study_attempts=1,prior_closed_epoch13_study_attempts=1,
        prior_closed_epoch14_native_attempts=0,prior_closed_epoch15_study_attempts=1,
        prior_closed_epoch16_study_attempts=1,
        lease_expires_unix=read(ROOT.parent/'owner.json')['expires_unix'],actual_project=str(ROOT),
        research_plan_sha256=sha(E/'RESEARCH_PLAN.json'),
        candidate_manifest_sha256=sha(S/'candidate/epoch17/proposal-manifest.json'),
        expected_new_reader_receipt={
            'repo':'microsoft/deberta-v2-xlarge-mnli',
            'revision':'2b65bccdedcead4bc685988bcc30153d4922a789',
            'original_checkpoint_sha256':'cc41eeb065c6ab3f7e88f8dab756334abb1f77a1136fec8cf02442143934c253',
            'config_sha256':'617f9d0b46fe934497a5aab5b44b1b343a751c0c43fec3e56e26b21e76b77c60',
            'tokenizer_sha256':'5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17',
            'precision':'TORCH_DYNAMIC_QINT8_LINEAR_FP32_REMAINDER_FBGEMM',
            'threads':2,'interop_threads':1,
            'versions':{'torch':'2.7.1+cpu','transformers':'4.52.4','sentencepiece':'0.2.0','tokenizers':'0.21.4','safetensors':'0.5.3','protobuf':'5.29.5'},
            'model_initializations':1,'quantization_initializations':1,'initialization_model_forwards':0,
            'quantization_recipe':'torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True);eval;FP32 original loading;fbgemm'},
        expected_previous_reader_receipt={
            'repo':'cross-encoder/nli-deberta-v3-large',
            'revision':'bab4bc7178836f731dcfd18c06ca9def0a137712',
            'model_sha256':'821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'},
        binary_probability_policy={'SUM_TOL':0.001,'strict_valid':True,'renormalized':False,'normalization':'none','typed_raw_tolerance':1e-10},
        public_model_acquisition={'lock':ident(S/'candidate/epoch17/model-assets.lock.json'),
            'helper':ident(S/'candidate/epoch17/acquire_assets.py'),
            'repo':assets['repo'],'revision':assets['revision'],'license':'MIT',
            'inference_calls_before_batch':0,'paid_calls':0,'GPU_calls':0,
            'old_reader_is_actual_control':True,'precision_choices_tested':1},
        runtime_admission={'formula_id':'24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
            'max_DEV_units':du,'max_confirmation_units':cu,
            'formula':'24*maxDEVHTTP*max(1,CONFmaxunits/DEVmaxunits)+2*fullphaseDEVinit+60; require<=600 and lease>=forecast+30',
            'scope':'Label-free exact source capacity; full actual phase initialization measured from pre-Popen invocation; conservative heuristic, no performance guarantee.'},
        acceptance_contract=ident(S/'audit/epoch17/acceptance-contract-v1.json'),
        source_policy='Exact source shared priority160 and rawH-only retrieval; same whole premise fits both actual reader tokenizers<=512, no clipping/aliases; numerical surface retention is not arithmetic/evidence sufficiency.',
        promotion='No automatic champion replacement/submission; frozen independent typed/binary DEV+unusedCONF acceptance AND publisher eligibility/protocol required.',
        selected_model_changed=True,official_score=None,official_rank=None,pins=sorted(pins.values(),key=lambda r:r['path']))
    for row in plan['pins']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    write(E/'plan.json',plan)
    write(E/'freeze-receipt.json',{'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),
        'plan':ident(E/'plan.json'),'source_freeze':ident(frozen),'pins':len(plan['pins']),
        'DEV_annotations_projected':24,'CONF_annotations_projected':0,'actual_native_model_fit_paid_GPU_calls':0})
    print(json.dumps({'plan':ident(E/'plan.json'),'pins':len(plan['pins']),'runtime_source_units':{'development':du,'confirmation':cu}}))
if __name__=='__main__':main()
