from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil, os

r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch12';pr=e/'project'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
assert not (e/'plan.json').exists(),'Frozen plan cannot be replaced'
base=load(pr/'experiments/sota-2026-10-22/epoch11/plan.json')
cand=load(s/'candidate/epoch12/proposal-manifest.json');data=load(s/'legal-transfer/epoch12/data-contract.json')
owner=load(e/'lock-owner.json');capacity=load(s/'audit/epoch12/context-capacity-independent-v1.json')
assert sha(s/'legal-transfer/epoch12/data-contract.json')=='bfb175660396473ef1f672903530792991725d68a8610aff2d887762597ce63b'
mi=cand['model_identity'];assert mi['revision']=='a70e12f8244efae07cf6fdfa935df30e3ac4a060'
assert mi['onnx_sha256']=='9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b'
tests=load(e/'controller-tests.json');assert tests['status']=='PASS'
hypothesis='One irrevocably fixed FP32 version of the epoch11 larger pretrained three-way NLI checkpoint, with actual native RuVector evidence and matched same-model lexical/positional context. Six already-exposed TRAIN questions compare FP32 versus quantized logits on exactly the same primary context; descriptive numerical fidelity only, no fitting, precision selection, thresholds or fallback. Source-original upstream weight fidelity remains unknown.'
scope='Internal CC-BY original ContractNLI three-predicate NDA pilot. TRAIN sanity is exposed diagnostic data, never benchmark generalization. FP32-versus-quantized comparison is not original-upstream verification. No current JevBench300, full LegalBench or ClaimBench score/rank.'
study='native-fp32-quantization-fidelity-e12'
budget={'native_attempt_cap':2,'attempts_started_before':0,'automatic_retries':0,'seconds_per_phase_including_init_cleanup':600,'CPU_cores':2,'ORT_intra':2,'ORT_inter':1,'paid_calls':0,'GPU_calls':0}
prior={'original':6,'epoch5':1,'epoch6':1,'epoch7':1,'epoch8':2,'epoch9':1,'epoch10':1,'epoch11':1,'lifetime_before':14}
contract={'schema_version':1,'epoch':12,'study_id':study,'frozen_at':datetime.now(timezone.utc).isoformat(),'authorization':'Current explicit continuation; at most two nonretryable CPU2 processes,600seconds each including all model initialization/TRAIN sanity/DEV/cleanup. No actual probes before this freeze.','hypothesis':hypothesis,'prior_closed_studies':prior,'new_study':budget,'candidate_source_manifest_sha256':sha(s/'candidate/epoch12/proposal-manifest.json'),'data_contract_sha256':sha(s/'legal-transfer/epoch12/data-contract.json'),'train':data['train'],'training_feature_questions':0,'train_sanity_questions':6,'calibration':[],'fitting':False,'primary_precision':'FP32_FIXED_BEFORE_TRAIN','development':data['development'],'confirmation':data['confirmation'],'data_frozen_at':data['frozen_at'],'lease_expires_unix':owner['expires_unix'],'champion':'Submitted Native104/RRF10 unchanged until independently accepted development and unused confirmation, then publisher eligibility/protocol required; no automatic promotion/submission'}
save(e/'STUDY_CONTRACT.json',contract)
rt={'formula_id':'48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1','max_DEV_units':capacity['phases']['development']['max_units'],'max_confirmation_units':capacity['phases']['confirmation']['max_units'],'formula':'48*maxDEVHTTPseconds*max(1,maxCONFunits/maxDEVunits)+2*phase1initseconds+60; require<=600 and lease_remaining>=forecast+30','scope':'Conservative admission estimate; only24DEV timings, no TRAIN timings or confirmation labels/model outputs. Actual phase watchdog600seconds.'}
rp={'schema_version':1,'epoch':12,'frozen_at':contract['frozen_at'],'parent_checkpoint':'edb193532821ddc43084eca932f36ec29d045b60','lease_commit':'6ac6e7305c81d7bac165784742f49d28fece493a','hypothesis':hypothesis,'scientific_scope':scope,'train':data['train'],'train_sanity_questions':6,'training_feature_questions':0,'calibration':[],'fitting':False,'temperature':1,'primary_precision':'FP32_FIXED_BEFORE_TRAIN','development':data['development'],'confirmation':data['confirmation'],'data_ordering':{'contract_frozen_at':data['frozen_at'],'document_role_frozen_at':data['roles_frozen_before_new_gold_projection_at'],'candidate_choice_after_data':True},'model_identity':mi,'candidate_manifest_sha256':sha(s/'candidate/epoch12/proposal-manifest.json'),'independent_acceptance_sha256':sha(s/'audit/epoch12/acceptance-contract-v2.json'),'confirmation_gate_sha256':sha(s/'audit/epoch12/confirmation-gate-v1.json'),'DEV_gate':'Primary>=each3controls+2correct; Brier/NLL nonworse ALL3, strict proper gain both matched; all24 strictvalid/errors0. TRAIN outcomes never select or gate the candidate.','confirmation_gate':'Frozen nominal2000 seed20261022 paired16doc bootstrap: accuracygainCI lower>0 ALL3 and proper improvementCI lower>=-1e-12 ALL3; point losses nonworse; independent review.','budget':budget|{'lifetime_attempts_before':14},'context_policy':'Exact reviewed epoch6 context source/policy tokenizer;40anchors+same-paragraph neighbors/source-order/raw512 wholeclaim guard. Same epoch11 active tokenizer for both FP32 and quantized precision and matched retrieval arms. No clipping/padding/truncation or grid.','runtime_admission':rt,'TRAIN_pairing':'6 already exposed TRAIN-only source-frozen identities. Exactly one quantized forward on the same native packed context per TRAIN question alongside primary FP32. Quantized session released after complete6 beforeDEV; never quantized DEV/CONF. Saved raw/centered logits/posteriors/agreements descriptive only.','evidence_scope':'Whole-document labels; packed evidence can omit information. Retrieval miss cannot establish absence or ClaimBench insufficiency. ClaimBench pilot requires verified data/scorer/license/access.','numeric_scope':'Source-position retention and omission only; no numeric truth or sufficiency certificate.','source_license':'Original ContractNLI CC-BY4 source/attribution pinned. Upstream model MIT declaration preserved; mixed training-data terms, converter exact-upstream-weight-commit/license gaps and unknown pretraining overlap disclosed. FP32 and INT8 are from the exact same converter revision; no pretrained weights published.','study_contract_sha256':sha(e/'STUDY_CONTRACT.json'),'prior_exposures':'All prior easy48/Legal96/originaldevCONF96 and173originaltrain groups remain exposed. Reuse2 priorTRAIN groups adds0 exposure. NewDEV8 chosen source-only before model choice; project-unused16groupCONF48 unchanged.'}
rp['replay_reproduction']={'active_source':{'path':'experiments/sota-2026-10-22/audit/epoch12/replay_actual_v1.py','sha256':sha(s/'audit/epoch12/replay_actual_v1.py')},'method':{'path':'experiments/sota-2026-10-22/audit/epoch12/saved-replay-method-v1.json','sha256':sha(s/'audit/epoch12/saved-replay-method-v1.json')},'scope':'Pure saved-output replay; no model/native/session initialization or fitting. Exactsource/assets/runtime closure required; modelbinaries separately acquired andhashverified. Active verifier source prepared BEFORE actual.','command':'OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 retrieval/.venv/bin/python -B experiments/sota-2026-10-22/audit/epoch12/replay_actual_v1.py --project . --out /tmp/ruvector-epoch12-audit-replay-UNUSED.json --expected-plan-sha PLAN_SHA','output_rule':'Use actuallyunusedoutputpath; verifierrefusesoverwrite. PLAN_SHA placeholder resolved toimmutableplan identity in finalmanifest.'}
save(e/'research-plan.json',rp)
def historical_to_keep(q):
 return not any(t in q for t in ('/audit/epoch11/','/legal-transfer/epoch11/','/epoch11/STUDY_CONTRACT.json','/epoch11/research-plan.json','/epoch11/controller-tests.json','/epoch11/native-runtime-restoration.json','/controller/epoch11_loop.py','/controller/test_epoch11_loop.py'))
paths={x['path'] for x in base['pins'] if historical_to_keep(x['path'])}
for x in cand['sources']+cand['read_only_code_dependencies']:paths.add(x['path'])
for folder in ('audit/epoch12','legal-transfer/epoch12'):
 for f in (s/folder).iterdir():
  if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md','.txt') and '.private' not in f.name:paths.add(str(f.relative_to(r)))
for q in ('candidate/epoch12/proposal-manifest.json','controller/epoch12_loop.py','controller/test_epoch12_loop.py','controller/epoch12_server.py','epoch12/STUDY_CONTRACT.json','epoch12/research-plan.json','epoch12/native-runtime-restoration.json','epoch12/controller-tests.json'):
 paths.add('experiments/sota-2026-10-22/'+q)
paths.add(data['confirmation']['path'])
for a in load(s/'candidate/epoch12/assets.lock.json')['assets']:
 q=a['path'];src=r/q;dst=pr/q
 if not src.exists() and dst.exists():src=dst
 assert src.is_file() and src.stat().st_size==a['bytes'] and sha(src)==a['sha256'],q
 if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst)
 assert dst.is_file() and sha(dst)==a['sha256'] and dst.resolve().is_relative_to(pr.resolve()),q
 paths.add(q)
for q in sorted(paths):
 src=r/q;dst=pr/q
 if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 assert sha(src)==sha(dst),q
 assert dst.resolve().is_relative_to(pr.resolve()),q
plan={k:v for k,v in base.items() if k not in ('pins','native_package_closure','typesafe_closure_sha256')}
plan.update(epoch=12,revision='fixed-FP32-threeway-TRAIN-quantization-fidelity-v1',study_id=study,train=data['train']['path'],training_questions=6,sanity_questions=6,train_sanity_questions=6,training_feature_questions=0,training_contract='experiments/sota-2026-10-22/legal-transfer/epoch12/data-contract.json',calibration='none',primary_precision='FP32_FIXED_BEFORE_TRAIN',prior_closed_study_native_attempts=14,prior_closed_epoch11_study_attempts=1,new_study_native_attempt_cap=2,new_study_native_attempts_before=0,lease_expires_unix=owner['expires_unix'],research_plan_sha256=sha(e/'research-plan.json'),actual_project=str(pr),candidate_manifest_sha256=sha(s/'candidate/epoch12/proposal-manifest.json'),expected_nli_revision=mi['revision'],expected_nli_sha256=mi['onnx_sha256'],runtime_admission=rt)
plan['datasets']={k:data[k]['path'] for k in ('train','development','confirmation')}
plan['pins']=[{'path':q,'sha256':sha(pr/q)} for q in sorted(paths)]
plan['limits'].update(GPU_calls=0,native_batches=2,seconds_per_decision=60)
plan['source_policy']=rp['context_policy'];plan['public_model_acquisition']={'inference_calls_before_batch':0,'paid_calls':0,**mi}
save(e/'plan.json',plan);shutil.copy2(e/'plan.json',pr/'experiments/sota-2026-10-22/epoch12/plan.json')
save(e/'freeze-receipt.json',{'at':datetime.now(timezone.utc).isoformat(),'plan_sha256':sha(e/'plan.json'),'pins':len(paths),'actual_project':str(pr),'native_model_calls':0,'prior_closed_lifetime_attempts':14,'new_study_started':0})
print(json.dumps({'plan_sha256':sha(e/'plan.json'),'pins':len(paths),'source_frozen':True,'forwards':0}))
