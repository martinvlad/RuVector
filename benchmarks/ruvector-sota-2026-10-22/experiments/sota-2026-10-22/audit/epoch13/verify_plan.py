"""Final independent source/data/model/lease acceptance; never initialize model/native."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,fcntl,hashlib,importlib.util,json,os,time
O=Path(__file__).resolve().parent;S=O.parents[1];ROOT=S.parents[1];P=S/'epoch13/project'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def obj(p):return json.loads(p.read_text())
ap=argparse.ArgumentParser();ap.add_argument('--expected-plan-sha',required=True);args=ap.parse_args();expected=args.expected_plan_sha
assert sha(S/'epoch13/plan.json')==expected==sha(P/'experiments/sota-2026-10-22/epoch13/plan.json');plan=obj(S/'epoch13/plan.json')
assert len(plan['pins'])==len({x['path'] for x in plan['pins']})==obj(S/'epoch13/freeze-receipt.json')['pins']
for x in plan['pins']:
 for root in(ROOT,P):
  p=root/x['path'];assert p.is_file() and sha(p)==x['sha256'],str(p)
  if root==P:assert p.resolve().is_relative_to(P.resolve()) and not p.is_symlink(),str(p)
assert plan['limits']=={'native_batches':2,'threads':2,'seconds_per_batch':600,'seconds_per_decision':30,'candidate_configs':1,'paid_calls':0,'GPU_calls':0}
assert plan['prior_closed_study_native_attempts']==15 and plan['new_study_native_attempt_cap']==2 and plan['new_study_native_attempts_before']==0
assert [plan[k] for k in('prior_closed_original_study_attempts','prior_closed_epoch5_study_attempts','prior_closed_epoch6_study_attempts','prior_closed_epoch7_study_attempts','prior_closed_epoch8_study_attempts','prior_closed_epoch9_study_attempts','prior_closed_epoch10_study_attempts','prior_closed_epoch11_study_attempts','prior_closed_epoch12_study_attempts')]==[6,1,1,1,2,1,1,1,1]
assert plan['study_id']=='native-official-roberta-threeway-e13' and plan['train']==plan['calibration']=='none'
assert plan['datasets']=={'development':'experiments/sota-2026-10-22/legal-transfer/epoch13/development24.jsonl','confirmation':'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl'}
assert plan['expected_nli_revision']=='1be0567456f0543475805e758725f151f283705a' and plan['expected_nli_sha256']=='50dbf8939f1fdc45ae31fd6c1e6680489c6560b0f5e37b13da0e7979b8384ad0'
capacity=obj(O/'context-capacity-independent-v1.json');rt=plan['runtime_admission'];assert rt['formula_id']=='48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1'
assert rt['max_DEV_units']==capacity['phases']['development']['max_units'] and rt['max_confirmation_units']==capacity['phases']['confirmation']['max_units']
rp=obj(S/'epoch13/research-plan.json');assert sha(S/'epoch13/research-plan.json')==plan['research_plan_sha256']
assert rp['independent_acceptance_sha256']==sha(O/'acceptance-contract-v1.json')=='921265d872fce1e12d60f1817bbe297e348b84e61553587c27bd5811c0a40612'
assert rp['confirmation_gate_sha256']==sha(O/'confirmation-gate-v1.json')=='95af3f6c2521b9ed8a18f50abd8ba7287a757e805746a7f469cbb58f77f3184e'
reports=('data-independent-v1.json','runtime-independent-v1.json','context-capacity-independent-v1.json','source-tests-independent-v1.json','model-static-independent-v1.json')
for name in reports:assert obj(O/name)['checks_passed'] is True
manifest=obj(S/'candidate/epoch13/proposal-manifest.json');assert sha(S/'candidate/epoch13/proposal-manifest.json')==plan['candidate_manifest_sha256']
for x in manifest['sources']+manifest['read_only_code_dependencies']:
 p=ROOT/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
assets=obj(S/'candidate/epoch13/assets.lock.json')['assets']
for x in assets:
 for root in(ROOT,P):
  p=root/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
choice=obj(S/'candidate/epoch13/model-choice.json');data=obj(S/'legal-transfer/epoch13/data-contract.json')
assert datetime.fromisoformat(choice['chosen_at_utc'])>datetime.fromisoformat(data['frozen_at'])>datetime.fromisoformat(data['roles_frozen_before_new_gold_projection_at'])
assert choice['data_freeze_before_choice']['sha256']==sha(S/'legal-transfer/epoch13/data-contract.json')=='65a5c4777444b24d59922eac927f63ad6f207fe5bdec4e3b46ea9a890bbc1187'
assert not(P/'experiments/sota-2026-10-22/epoch13/runs').exists() and not(P/'experiments/sota-2026-10-22/epoch13/launch.json').exists()
q=P/'experiments/sota-2026-10-22/controller/epoch13/loop.py';spec=importlib.util.spec_from_file_location('epoch13_verify_only',q);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.require_plan(P/'experiments/sota-2026-10-22/epoch13/plan.json',expected)==plan
owner=obj(S/'epoch13/lock-owner.json');assert owner['run_id']=='e3cfa5a1-6bb0-4ad1-b11f-d0b02b7c9356';os.kill(owner['pid'],0);assert time.time()+120<owner['expires_unix']
f=(S/'.loop.lock').open('a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:pass
else:raise AssertionError('Scoped exclusive lock not held')
method=obj(O/'saved-replay-method-v1.json');assert method['prepared_before_measurements'] and method['source_sha256']==sha(O/'replay_actual_v1.py')
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'accepted_for_one_controlled_study':True,'plan_sha256':expected,'source_pins_verified_outer_and_actual':len(plan['pins']),'all_actual_pins_materialized_inside_project':True,'candidate_manifest_sha256':plan['candidate_manifest_sha256'],'data_contract_sha256':sha(S/'legal-transfer/epoch13/data-contract.json'),'new_local_controller_verifier_passed':True,'data_roles':{'TRAIN':[],'calibration':[],'DEV':'NEW24/8 source-only draw; prior181exposed/reserved16/officialdevtest excluded; all8 retire afterphase1marker evenpartial/noPID.','CONF':'Exact unchanged850b48/16 project-model-unused; metadata-only until acceptedDEV/runtime; anyphase2markerretiresall48.'},'source_guards':{'one_fixed_official_FP32_after_DATAfreeze':True,'full_threeway_C0_E1_N2_T1':True,'same_reader_BPE_and_contextalgorithm_all3selectors':True,'epoch6_algorithm_unchanged':True,'historical_policy_or_context_strings_unchanged':False,'raw_BPE512_BGE256_native16KiB':True,'no_fit_calibration_probe_retry_fallback':True,'literal_model_inputs_only_state_questions':True,'all15prior_attempts_closed':True,'prePopen_conservative_count_separate_confirmedPID':True},'premeasurement_evidence':{n:sha(O/n) for n in(*reports,'acceptance-contract-v1.json','confirmation-gate-v1.json','saved-replay-method-v1.json')},'active_saved_replay':{'source':'experiments/sota-2026-10-22/audit/epoch13/replay_actual_v1.py','sha256':sha(O/'replay_actual_v1.py'),'prepared_before_actual_measurements':True,'zero_inference_or_fit':True},'budgets':plan['limits'],'runtime_admission':'48*maxDEVHTTP*max(1,maxCONFunits/maxDEVunits)+2*wholephase1init+60<=600 ANDlease>=forecast+30;600hardwatchdogincludesallinitcleanup.','scope':'Bounded measurement acceptance only. Distinct directly published reader is not proven stronger accuracy or original-upstream export identity. Public-source unknown pretraining overlap. No officialrank/score/SOTA or champion promotion/submission.','no_run_started_at_verification':True,'model_session_native_fit_paid_calls_by_auditor':0}
out=O/'premeasurement-acceptance-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'accepted':True,'sha256':sha(out),'pins':len(plan['pins']),'plan':expected}))
