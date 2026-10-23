"""Final exact epoch12 plan/data/model/source check; no model/addon/session initialization."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,os,fcntl,time
O=Path(__file__).resolve().parent;S=O.parents[1];ROOT=S.parents[1];P=S/'epoch12/project'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def obj(p):return json.loads(p.read_text())
ap=argparse.ArgumentParser();ap.add_argument('--expected-plan-sha',required=True);a=ap.parse_args();planpath=S/'epoch12/plan.json';expected=a.expected_plan_sha
assert sha(planpath)==expected==sha(P/'experiments/sota-2026-10-22/epoch12/plan.json');plan=obj(planpath)
assert len({x['path'] for x in plan['pins']})==len(plan['pins'])==obj(S/'epoch12/freeze-receipt.json')['pins']
for pin in plan['pins']:
 for root in (ROOT,P):
  p=root/pin['path'];assert p.is_file() and sha(p)==pin['sha256'],str(p)
  if root==P:assert p.resolve().is_relative_to(P.resolve()) and not p.is_symlink(),str(p)
assert plan['limits']=={'native_batches':2,'threads':2,'seconds_per_batch':600,'seconds_per_decision':60,'candidate_configs':1,'paid_calls':0,'GPU_calls':0}
assert plan['prior_closed_study_native_attempts']==14 and plan['new_study_native_attempt_cap']==2 and plan['new_study_native_attempts_before']==0
assert [plan[k] for k in ('prior_closed_original_study_attempts','prior_closed_epoch5_study_attempts','prior_closed_epoch6_study_attempts','prior_closed_epoch7_study_attempts','prior_closed_epoch8_study_attempts','prior_closed_epoch9_study_attempts','prior_closed_epoch10_study_attempts','prior_closed_epoch11_study_attempts')]==[6,1,1,1,2,1,1,1]
assert set(plan['datasets'])=={'train','development','confirmation'} and plan['train']==plan['datasets']['train']=='experiments/sota-2026-10-22/legal-transfer/epoch12/train-sanity6.jsonl'
assert plan['datasets']['development']=='experiments/sota-2026-10-22/legal-transfer/epoch12/development24.jsonl' and plan['datasets']['confirmation']=='experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl'
assert plan['training_questions']==plan['sanity_questions']==plan['train_sanity_questions']==6 and plan['training_feature_questions']==0 and plan['calibration']=='none' and plan['primary_precision']=='FP32_FIXED_BEFORE_TRAIN'
assert plan['runtime_admission']['formula_id']=='48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1' and plan['runtime_admission']['max_DEV_units']==24 and plan['runtime_admission']['max_confirmation_units']==57
assert plan['candidate_manifest_sha256']==sha(S/'candidate/epoch12/proposal-manifest.json')=='e026244f921171860a8cb9a9b9ce0c03de61bd2330d6521653b16db9455b9aaf'
assert plan['expected_nli_revision']=='a70e12f8244efae07cf6fdfa935df30e3ac4a060' and plan['expected_nli_sha256']=='9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b'
assert plan['study_id']=='native-fp32-quantization-fidelity-e12'
research=S/'epoch12/research-plan.json';assert sha(research)==plan['research_plan_sha256'];rp=obj(research)
assert rp['independent_acceptance_sha256']==sha(O/'acceptance-contract-v2.json')=='f8850d7fdb0326a0a96dc4c9d2969a5c5d35339649c4c75f1c75b51118ecb3f7'
assert rp['confirmation_gate_sha256']==sha(O/'confirmation-gate-v1.json')=='4974c23606637d5b56ab3af4d96c706f234f800a93c21550e8c13d00f4516bdb'
reports=('data-independent-v1.json','runtime-independent-v1.json','context-capacity-independent-v1.json','source-tests-independent-v1.json','model-static-independent-v1.json')
for name in reports:assert obj(O/name)['checks_passed'] is True
manifest=obj(S/'candidate/epoch12/proposal-manifest.json')
for item in manifest['sources']+manifest['read_only_code_dependencies']:
 p=ROOT/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
assets=obj(S/'candidate/epoch12/assets.lock.json')['assets'];assert len(assets)==23
for x in assets:
 for root in (ROOT,P):
  p=root/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
choice=obj(S/'candidate/epoch12/model-choice.json');data=obj(S/'legal-transfer/epoch12/data-contract.json')
assert datetime.fromisoformat(choice['selected_at'])>datetime.fromisoformat(data['frozen_at'])>datetime.fromisoformat(data['roles_frozen_before_new_gold_projection_at'])
assert choice['data_contract_sha256']==sha(S/'legal-transfer/epoch12/data-contract.json')=='bfb175660396473ef1f672903530792991725d68a8610aff2d887762597ce63b'
assert not (P/'experiments/sota-2026-10-22/epoch12/runs').exists() and not (P/'experiments/sota-2026-10-22/epoch12/launch.json').exists()
# Exercise only the new local source/pin verifier, never the archived controller.
q=P/'experiments/sota-2026-10-22/controller/epoch12_loop.py';spec=importlib.util.spec_from_file_location('epoch12_verify_only',q);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.require_plan(P/'experiments/sota-2026-10-22/epoch12/plan.json',expected)==plan
owner=obj(S/'epoch12/lock-owner.json');os.kill(owner['pid'],0);assert owner['run_id']=='56c569ef-b9d7-4e8d-9631-4b8d1c8c9016' and time.time()+120<owner['expires_unix']
f=(S/'.loop.lock').open('a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:pass
else:raise AssertionError('Exclusive scoped lock not held')
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'accepted_for_one_controlled_study':True,'plan_sha256':expected,'source_pins_verified_outer_and_actual':len(plan['pins']),'all_actual_pins_materialized_and_resolve_inside_project':True,'candidate_manifest_sha256':plan['candidate_manifest_sha256'],'data_contract_sha256':sha(S/'legal-transfer/epoch12/data-contract.json'),'new_local_controller_verifier_passed':True,'data_roles':{'TRAIN':'Six diagnostics from two already-exposed e10 TRAIN groups; no fits or selection, preserves original TRAIN role.','DEV':'New24/8 source-only draw, excludes prior173/reserved16/official splits. All declared DEV retired conservatively after phase1 Popen.','CONF':'Exact unchanged project-model-unused48/16; no labels used for fitting/selection. Actual Popen attempt retires bank even0HTTP.','calibration':'none'},'source_guards':{'one_fixed_FP32_chosen_before_TRAIN_outputs':True,'Neutral_preserved_E_C_N_T1':True,'same_context_and_model_all_matched_selectors':True,'TRAIN3FP32_and1INT8_native_context_each_once':True,'quant_released_before_DEV_and_not_initialized_CONF':True,'TRAIN_outcomes_not_candidate_gate':True,'no_fit_precision_selection_fallback_or_retry':True,'literal_wire_envelope_preserves_native_input_no_labels':True,'Popen_conservative_invocation_separate_confirmed_PID':True},'premeasurement_evidence':{name:sha(O/name) for name in (*reports,'acceptance-contract-v1.json','acceptance-contract-v2.json','confirmation-gate-v1.json','saved-replay-method-v1.json')},'active_saved_replay':{'path':'experiments/sota-2026-10-22/audit/epoch12/replay_actual_v1.py','sha256':sha(O/'replay_actual_v1.py'),'prepared_before_actual_measurements':True,'no_inference_or_fit':True},'budgets':plan['limits'],'prior14_closed_new_cap2':True,'runtime_admission':'48*maxDEVHTTP*max(1,57/24)+2*wholephase1init+60<=600 AND lease>=forecast+30;600s hard watchdog includes all model init/TRAIN/DEV/cleanup. No timing probe.','scope':'Approve bounded measurement only, not candidate promotion. Co-located FP32/INT8 variants are not verified original-upstream equivalence or exact quantization derivation. No causal quantization or official benchmark claim. Public-source unknown pretraining overlap and model license/converter gaps retained.','no_run_started_at_verification':True,'model_initializations_native_or_paid_calls_by_auditor':0}
out=O/'premeasurement-acceptance-v1.json'
with out.open('x') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
print(json.dumps({'accepted':True,'sha256':sha(out),'pins':len(plan['pins']),'plan':expected}))
