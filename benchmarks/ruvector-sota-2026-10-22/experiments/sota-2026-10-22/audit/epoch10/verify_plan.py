from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,importlib.util
O=Path(__file__).resolve().parent;S=O.parents[1];ROOT=S.parents[1];P=S/'epoch10/project'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p):return json.loads(p.read_text())
planpath=S/'epoch10/plan.json';expected='eb6f040d544e83632830921281bda98deb740c70a176c54d2b2e5c9d8d86fb84';assert sha(planpath)==expected
assert sha(P/'experiments/sota-2026-10-22/epoch10/plan.json')==expected
plan=obj(planpath);assert len(plan['pins'])==190;assert len({x['path'] for x in plan['pins']})==190
for pin in plan['pins']:
 for root in (ROOT,P):
  p=root/pin['path'];assert p.is_file() and sha(p)==pin['sha256'],str(p)
  if root==P:assert p.resolve().is_relative_to(P.resolve()),str(p)
assert plan['prior_closed_study_native_attempts']==12 and plan['new_study_native_attempt_cap']==2 and plan['new_study_native_attempts_before']==0
assert plan['limits']=={'native_batches':2,'threads':2,'seconds_per_batch':600,'seconds_per_decision':30,'candidate_configs':1,'paid_calls':0,'GPU_calls':0}
assert plan['runtime_admission']['max_DEV_units']==23 and plan['runtime_admission']['max_confirmation_units']==57
assert plan['candidate_manifest_sha256']=='2d67d11ae1052bb048cbeadde6823b33f8c0df41a9f65b11d669a012191c1e87'
assert sha(S/'epoch10/research-plan.json')==plan['research_plan_sha256']
r=obj(S/'epoch10/research-plan.json');assert r['independent_acceptance_sha256']==sha(O/'acceptance-contract-v1.json') and r['confirmation_gate_sha256']==sha(O/'confirmation-gate-v1.json')
assert not (P/'experiments/sota-2026-10-22/epoch10/runs').exists()
for f in ('data-independent-v1.json','runtime-independent-v1.json','context-capacity-independent-v1.json','math-source-independent-v1.json','model-static-independent-v1.json'):
 assert obj(O/f)['checks_passed'] is True
manifest=obj(S/'candidate/epoch10/proposal-manifest.json')
# Explicitly identify the static report's historical source namespace.
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'accepted_for_one_controlled_study':True,'plan_sha256':expected,'actual_project':str(P),'identical_outer_actual_plan':True,'all190pins_verified_outer_and_actual':True,'all_actual_pinned_paths_resolve_inside_project':True,'final_candidate_manifest_sha256':plan['candidate_manifest_sha256'],'final_candidate_sources':{x.name:sha(x) for x in (S/'candidate/epoch10').glob('*.py')},'data_roles':{'train':'Reused exposed72/24docs + TRAIN-only annotations; only these labels/spans enter5fits','development':'Fresh24/8groups no fit or normalization','confirmation':'Preserved48/16groups project-model-unused conditional only, no labels inspected for selection or fitting','calibration':'none'},'source_guards':{'TRAIN_cache_then5fixedfits_then_artifact_and_fitlock_then_DEV_open':True,'same_head_features_and_auxiliary_all3selectors':True,'confirmation_exact_artifact_before_constructor_no_refit':True,'fit_failure_blocks_DEV_CONF_no_fallback':True,'actualCONF_attempt_retires_bank_even_without_HTTP':True},'premeasurement_evidence':{f:sha(O/f) for f in ('acceptance-contract-v1.json','confirmation-gate-v1.json','data-independent-v1.json','runtime-independent-v1.json','context-capacity-independent-v1.json','math-source-independent-v1.json','model-static-independent-v1.json')},'reader9_static_reference_scope':'model-static-independent-v1.json fields final_models/runtime/config/proposal identify historical candidate9 backbone/decoder static reference. They are NOT finalcandidate10 identities. Finalcandidate10 identity is bound separately by this report, math-source report and all190exactpins. Actual model9 assets/tokenizer/ONNX closure are reused unchanged.','DEV_gate':'At least2correct gain vs EACH3controls, proper nonworseALL3 and strictpropermatched, strict24valid/errors0','CONF_gate':'Frozen nominal2000seed20261022 16docbootstrap accuracygain CI lower>0ALL3, propergain CI lower>=-1e-12ALL3, pointnonworse','budgets':plan['limits'],'prior12closed_new_cap2':True,'forecast':'48*maxDEVHTTP*max(1,57/23)+2*phase1wholeinit+60 <=600 AND lease>=forecast+30; hardwatchdog inclfit/init/cleanup remains600 each','scope':'Acceptance authorizes the bounded measurement, not promotion. Internal3hypothesisNDApilot only; no officialscore/rank/SOTA/generalchampion replacement. Weakannotationcoverage is not sufficiency/absence; fullTRAINaux vsOOFshift disclosed. Empirical400step criteria may fail closed.','model_initializations_real_forwards_native_realTRAINfits_paid_calls_by_auditor':0,'no_run_started_at_verification':True}
out=O/'premeasurement-acceptance-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'accepted':True,'sha256':sha(out),'pins':190,'plan':expected}))
