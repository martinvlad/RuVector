"""Freeze all reviewed epoch18 source/role/checker bytes before new inputs/gold.

No labels are projected and no model/native code is imported.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os

ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch18'

def safe(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    assert '..' not in p.parts,'Parent traversal forbidden'
    p.relative_to(ROOT)
    assert not any(x.is_symlink() for x in [p,*p.parents]),'Symlink ancestor forbidden: '+str(p)
    return p
def absent(p):assert not os.path.lexists(safe(p)),'Projection preceded source freeze: '+str(p)
def sha(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}

def main():
    handoff=safe(S/'audit/epoch18/code-handoff-v1.json')
    assert handoff.is_file(),'Independent immutable checker/source handoff required'
    acceptance=json.loads(handoff.read_text())
    assert acceptance.get('checks_passed') is True
    assert acceptance.get('source_and_checker_ready_for_prelabel_freeze') is True
    assert acceptance.get('source_immutable_head')=='0eac156990f5a4ee0084af635eb3089913b437ff'
    assert acceptance.get('native_execution_admitted') is False
    assert acceptance.get('auditor_model_native_fit_paid_GPU_calls')==0
    assert acceptance.get('new_role_annotation_choices_read')==0
    policy=S/'audit/epoch18/acceptance-contract-v1.json'
    assert sha(policy)==acceptance['policy_sha256'],'Reviewed policy changed'
    for category in ['checker_source_and_tests','reviewed_candidate_and_role_sources']:
        assert acceptance[category]
        for row in acceptance[category]:
            f=safe(ROOT/row['path'])
            assert not f.is_symlink() and f.is_file()
            assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
    for name in ['development24.jsonl','confirmation24.jsonl','dev-materialization.json',
                 'confirmation-materialization.json','dev-inputs-only.json','confirmation-inputs-only.json',
                 'pre-gold-input-validation.json','dev-pre-gold-validation.json',
                 'confirmation-pre-gold-validation.json','dev-input-allowlist.json',
                 'confirmation-input-allowlist.json','dev-allowlist.json','confirmation-allowlist.json']:
        absent(S/'legal-transfer/epoch18'/name)
    for p in [E/'launch.json',E/'runs',S/'audit/epoch18/prelabel-operational-admission-v1.json',E/'operational-plan.json']:
        absent(p)
    cp=json.loads((ROOT.parent/'kit/CHECKPOINT_MANIFEST.json').read_text())
    for row in cp['project_files']:
        f=safe(ROOT/row['path']);assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
    files=[]
    for rel in ['candidate/epoch18','controller/epoch18','legal-transfer/epoch18','audit/epoch18','epoch18']:
        for f in sorted(safe(S/rel).rglob('*')):
            safe(f)
            if f.is_file() and '__pycache__' not in f.parts and '/assets/' not in str(f):
                assert not f.is_symlink();files.append(ident(f))
    value={'schema_version':1,'epoch':18,'at':datetime.now(timezone.utc).isoformat(),
        'status':'CANDIDATE_DATA_BUILDER_ROLES_CONTROLLERS_CHECKERS_FROZEN_BEFORE_NEW_INPUTS_AND_GOLD',
        'source_checkpoint':'0eac156990f5a4ee0084af635eb3089913b437ff',
        'planning_lease':'2e6aa4fca5acd9a5149c9f6b37aaf4360c035a45',
        'files':files,'prior_checkpoint_records_verified':len(cp['project_files']),
        'DEV_annotation_choices_projected':0,'CONF_annotation_choices_projected':0,
        'new_case_inputs_inspected':0,'model_native_fit_paid_GPU_calls':0,
        'subsequent_steps':'Actual full unmocked source-only operational require_plan receipt FIRST, then frozen builder input-only projection, source-only capacity verification, DEV-only projection, final plan revalidation and pre-native source publication. No scientific source/checker/gate changes after this freeze.'}
    out=safe(E/'candidate-source-freeze.json')
    with out.open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())
    print(json.dumps({'path':str(out.relative_to(ROOT)),'sha256':sha(out),'source_files':len(files),'new_annotation_choices':0}))

if __name__=='__main__':main()
