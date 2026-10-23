"""Freeze all reviewed epoch17 source/role/checker bytes before new inputs/gold.

No labels are projected and no model/native code is imported.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os

ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch17'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}

def main():
    handoff=S/'audit/epoch17/code-handoff-v1.json'
    assert handoff.is_file(),'Independent immutable checker/source handoff required'
    acceptance=json.loads(handoff.read_text())
    assert acceptance.get('checks_passed') is True
    assert acceptance.get('source_and_checker_ready_for_prelabel_freeze') is True
    assert acceptance.get('source_immutable_head')=='cec9a7bbdc8c4ced83e5d1b826bce67da18339df'
    assert acceptance.get('native_execution_admitted') is False
    assert acceptance.get('auditor_model_native_fit_paid_GPU_calls')==0
    assert acceptance.get('new_role_annotation_choices_read')==0
    policy=S/'audit/epoch17/acceptance-contract-v1.json'
    assert sha(policy)==acceptance['policy_sha256'],'Reviewed policy changed'
    for category in ['checker_source_and_tests','reviewed_candidate_and_role_sources']:
        assert acceptance[category]
        for row in acceptance[category]:
            f=ROOT/row['path']
            assert not f.is_symlink() and f.is_file()
            assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
    for name in ['development24.jsonl','confirmation24.jsonl','dev-materialization.json',
                 'confirmation-materialization.json','dev-inputs-only.json','confirmation-inputs-only.json',
                 'pre-gold-input-validation.json','dev-pre-gold-validation.json',
                 'confirmation-pre-gold-validation.json','dev-input-allowlist.json',
                 'confirmation-input-allowlist.json','dev-allowlist.json','confirmation-allowlist.json']:
        assert not (S/'legal-transfer/epoch17'/name).exists(),'Projection preceded source freeze: '+name
    assert not (E/'launch.json').exists()
    cp=json.loads((ROOT.parent/'kit/CHECKPOINT_MANIFEST.json').read_text())
    for row in cp['project_files']:
        f=ROOT/row['path'];assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
    files=[]
    for rel in ['candidate/epoch17','controller/epoch17','legal-transfer/epoch17','audit/epoch17','epoch17']:
        for f in sorted((S/rel).rglob('*')):
            if f.is_file() and '__pycache__' not in f.parts and '/assets/' not in str(f):
                assert not f.is_symlink();files.append(ident(f))
    value={'schema_version':1,'epoch':17,'at':datetime.now(timezone.utc).isoformat(),
        'status':'CANDIDATE_DATA_BUILDER_ROLES_CONTROLLERS_CHECKERS_FROZEN_BEFORE_NEW_INPUTS_AND_GOLD',
        'source_checkpoint':'cec9a7bbdc8c4ced83e5d1b826bce67da18339df',
        'planning_lease':'15c99814e08879b5591651389ce45086d02e5e1f',
        'files':files,'prior_checkpoint_records_verified':len(cp['project_files']),
        'DEV_annotation_choices_projected':0,'CONF_annotation_choices_projected':0,
        'new_case_inputs_inspected':0,'model_native_fit_paid_GPU_calls':0,
        'subsequent_steps':'Frozen builder input-only projection, source-only capacity verification, DEV-only projection, exact plan and pre-native source publication. No scientific source/checker/gate changes after this freeze.'}
    out=E/'candidate-source-freeze.json'
    with out.open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())
    print(json.dumps({'path':str(out.relative_to(ROOT)),'sha256':sha(out),'source_files':len(files),'new_annotation_choices':0}))

if __name__=='__main__':main()
