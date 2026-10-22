"""Independent exact premeasurement acceptance of actual isolated169-pin plan."""
from pathlib import Path
from datetime import datetime,timezone
import fcntl,hashlib,importlib.util,json,os
S=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=S/'epoch7/project';expected='ab0d3fadf4bc23c3d58b36c157ebb665127d2a50487ea56c79d830a8054c0aee'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def obj(p):return json.loads(p.read_text())
planfile=S/'epoch7/plan.json';actual=P/'experiments/sota-2026-10-22/epoch7/plan.json';assert sha(planfile)==sha(actual)==expected
plan=obj(planfile);assert len(plan['pins'])==169 and len({x['path'] for x in plan['pins']})==169
for x in plan['pins']:
 path=P/x['path'];assert not Path(x['path']).is_absolute() and '..' not in Path(x['path']).parts
 assert path.resolve().is_relative_to(P.resolve()),x['path']
 assert sha(path)==x['sha256'],x['path']
 if 'bytes' in x:assert path.stat().st_size==x['bytes'],x['path']
 local=S.parents[1]/x['path'];assert local.exists() and sha(local)==x['sha256'],x['path']
sp=importlib.util.spec_from_file_location('audit_checked_controller7',P/'experiments/sota-2026-10-22/controller/epoch7_loop.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);assert m.require_plan(actual,expected)==plan
research=obj(S/'epoch7/research-plan.json');assert sha(S/'epoch7/research-plan.json')==plan['research_plan_sha256']
assert research['independent_acceptance_sha256']==sha(O/'acceptance-contract-v3.json')=='c9a9c36f3073fc53494bff726b0e853a19cbeca20ed0463bcc2df48239a20429'
assert research['confirmation_gate']['exact_independent_gate_sha256']==sha(O/'confirmation-gate-v1.json')=='2444605411a026e43a24638942082a0ec1b86b5767a1453d3c2bc7005f6b0a46'
assert plan['runtime_admission']['max_DEV_units']==41 and plan['runtime_admission']['max_confirmation_units']==39
assert plan['candidate_manifest_sha256']==sha(S/'candidate/epoch7/proposal-manifest.json')=='21c71d91aec3b403dad1ead613c8a3e1d9bebc991efbf60d28a33bfe6a218ac8'
proposal=obj(S/'candidate/epoch7/proposal-manifest.json');pins={x['path']:x['sha256'] for x in plan['pins']}
for x in proposal['sources']+proposal['read_only_code_dependencies']:
 assert pins.get(x['path'])==x['sha256'],x['path']
for lockname in ['candidate/epoch4/assets.lock.json','candidate/epoch7/model-assets.lock.json']:
 for x in obj(S/lockname)['assets']:assert pins.get(x['path'])==x['sha256'],x['path']
assert not (P/'experiments/sota-2026-10-22/epoch7/launch.json').exists() and not (P/'experiments/sota-2026-10-22/epoch7/runs').exists()
owner=obj(S/'epoch7/lock-owner.json');assert owner['pid']==10560 and owner['run_id']=='1e487a1d-c1ef-4b83-99a4-d8d9ea10044f' and Path('/proc/10560').exists()
with (S/'.loop.lock').open('r') as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:held=True
 else:fcntl.flock(f,fcntl.LOCK_UN);held=False
assert held
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'status':'ACCEPTED_FOR_BOUNDED_MEASUREMENT','checks_passed':True,'plan_sha256':expected,'actual_project':str(P),'exact_actual_and_outer_pins_verified':169,'candidate_proposal_sha256':plan['candidate_manifest_sha256'],'independent_acceptance_sha256':research['independent_acceptance_sha256'],'exact_confirmation_gate_sha256':research['confirmation_gate']['exact_independent_gate_sha256'],'prior_closed_attempts':8,'new_attempt_cap':2,'actual_starts_before_acceptance':0,'allowed_execution':'ONE separately timed DEV24 process, then ONLY if strict statistical gate AND frozen conservative timing/lease admission permit ONE96 process; each<=600includinginit/cleanup,CPU2,paid0,GPU0,no retries.','fixed_runtime_admission':plan['runtime_admission'],'independent_runtime_22file_and5resolve_only_pass':sha(O/'runtime-independent-v1.json'),'model_identity_recursive_static_and_provenance_pass':sha(O/'model-independent-v1.json'),'data_draw_pass':sha(O/'data-independent-v1.json'),'dual_tokenizer_capacity_pass':sha(O/'context-capacity-independent-v1.json'),'source_synthetic_tests_pass':sha(O/'source-review-v1.json'),'OS_lock_observed_held':True,'public_ref_independently_read_via_connected_GitHub':'3953022a31d591ab24a88d58fe01df86f10529c7','guards':'Literal startedrequest fsync before HTTP, actualwire/server/model/native receipts/bundles/counters/resources/cleanup, no confirmation modeluse if gate/admission fails. All saved results independently replayed after terminal before internal promotion.','scope':'Binary public originalContractNLI NDA pilot only. Exact frozen6 policy with one larger binary reader; differentDEV cohorts forbid cross-epoch causal model/context claims. No official score/rank/SOTA or genericJev/RRF champion promotion.','readiness_limit':'Static/resolve-only preflight does not prove ABI/ORT/session/forward compatibility. Only actual bounded phase can test execution.','auditor_model_native_or_paid_calls':0,'official_score':None,'official_rank':None,'SOTA_established':False}
p=O/'premeasurement-acceptance-v1.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'accepted':True,'sha256':sha(p),'plan_sha256':expected,'pins':169}))
