"""Freeze one candidate/data identity and a nonretryable native study; never initializes models."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,os
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];S=HERE.parent
STUDY='native-definition-priority-deberta-threeway-e15'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())
def item(p):
 p=Path(p);return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def candidate_freeze():
 cand=load(S/'candidate/epoch15/proposal-manifest.json')
 assert sha(S/'candidate/epoch15/proposal-manifest.json')=='d08312546400cbab7e7be0c4b597d699fdadd5898afef7a97187dbb247b748c5'
 assert cand['model_identity']['revision']=='bab4bc7178836f731dcfd18c06ca9def0a137712'
 assert cand['priority_token_cap']==160 and cand['training']==cand['calibration']==[]
 for r in cand['sources']+cand['read_only_code_dependencies']+cand['data_role_pins']:
  p=ROOT/r['path'];assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],r['path']
 rows=[item(S/'candidate/epoch15/proposal-manifest.json'),item(S/'legal-transfer/epoch15/data-contract.pre-label.json')]
 rows+=cand['sources']+cand['read_only_code_dependencies']
 for d in ['controller/epoch15','audit/epoch15']:
  for f in sorted((S/d).rglob('*')):
   if f.is_file() and '__pycache__' not in f.parts:rows.append(item(f))
 put(HERE/'candidate-source-freeze.json',{'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'scope':'Candidate/context/controller/acceptance source and label-free role identity frozen before any newDEV annotation projection','candidate_proposal_SHA256':sha(S/'candidate/epoch15/proposal-manifest.json'),'pre_label_contract_SHA256':sha(S/'legal-transfer/epoch15/data-contract.pre-label.json'),'active_acceptance_policy':item(S/'audit/epoch15/acceptance-contract-v2.json'),'source_files':rows,'DEV_annotation_projection_before_this_freeze':False,'new_native_model_fit_calls':0})
def freeze_plan():
 frozen=load(HERE/'candidate-source-freeze.json')
 for r in frozen['source_files']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
 cand=load(S/'candidate/epoch15/proposal-manifest.json');data=load(S/'legal-transfer/epoch15/data-contract.pre-label.json');mat=load(S/'legal-transfer/epoch15/materialization.json');cap=load(S/'audit/epoch15/context-capacity-independent-v1.json')
 owner=load(ROOT.parent/'owner.json');os.kill(owner['pid'],0);mi=cand['model_identity'];at=datetime.now(timezone.utc).isoformat()
 assert mat['data_sha256']==sha(S/'legal-transfer/epoch15/development24.jsonl')
 dev={**data['development'],'file_sha256':mat['data_sha256'],'status':'Fixed DEV24 materialized after candidate/source/role freeze; no fitting/selection; never fresh confirmation','materialization_receipt':item(S/'legal-transfer/epoch15/materialization.json')}
 conf=data['confirmation'];assert sha(ROOT/conf['path'])==conf['sha256']=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
 rt={'formula_id':'48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1','max_DEV_units':cap['phases']['development']['max_units'],'max_confirmation_units':cap['phases']['confirmation']['max_units'],'formula':'48*maxDEVHTTPseconds*max(1,maxCONFunits/maxDEVunits)+2*phase1initseconds+60; require<=600 and lease_remaining>=forecast+30','scope':'Input-only tokenization estimate; no confirmation annotation choices or model outputs'}
 budget={'native_attempt_cap':2,'automatic_retries':0,'seconds_per_phase_including_init_cleanup':600,'CPU_cores':2,'ORT_intra':2,'ORT_inter':1,'paid_calls':0,'GPU_calls':0,'lifetime_before':16}
 rp={'schema_version':1,'epoch':15,'frozen_at':at,'study_id':STUDY,'parent_checkpoint':'0a6379a108919c9aa5ab52966ce1a9aacab8a0f4','hypothesis':cand['hypothesis'],'scientific_scope':data['scope'],'train':[],'calibration':[],'fitting':False,'temperature':1,'development':dev,'confirmation':conf,'model_identity':mi,'candidate_manifest':item(S/'candidate/epoch15/proposal-manifest.json'),'candidate_source_freeze':item(HERE/'candidate-source-freeze.json'),'independent_acceptance':item(S/'audit/epoch15/acceptance-contract-v2.json'),'budget':budget,'runtime_admission':rt,'context_policy':'Fixed160token exact-source definition-priority IDs shared across all3selectors; whole512-token pair, global source order, no clipping/rewriting/inferredaliases; no-priority trace is tokenizer-only, not another inference arm.','source_license':'Original ContractNLI CC-BY-4.0 with pinned attribution; official model Apache-2.0 declaration/SNLI+MNLI. Unknown pretraining/fuzzy overlap and exact training-run lineage remain. No pretrained binaries republished.','comparison_scope':'Matched retrieval effect within same model/context only. Model and context both changed; no independent causal attribution or full submittedNative104 comparison.','numeric_scope':'Source-span character/numerical retention only, never sufficiency or arithmetic correctness','submission':'No automatic champion replacement or submission; strict independentDEV+eligibleunusedCONF and publishereligibility/protocol required','source_frozen_before_new_DEV_labels':True,'confirmation_labels_used_for_training_or_selection':False,'official_score':None,'official_rank':None}
 rp['verifier_revision']={'superseded_unexecuted_plan':item(HERE/'plan.json'),'reason':'Audit-only saved-output verifier strengthening/versioning before any native attempt; candidate/controller/data/gates unchanged','active_numerical_replay':item(S/'audit/epoch15/replay_scores_v2.py'),'active_context_replay':item(S/'audit/epoch15/replay_context_v2.py')}
 put(HERE/'research-plan.v2.json',rp)
 base=load(S/'epoch13/plan.json');paths=set()
 for r in base['pins']:
  q=r['path'];f=ROOT/q
  if any(x in q for x in ['/audit/epoch13/','/legal-transfer/epoch13/','/candidate/epoch13/','/epoch13/','/controller/epoch13/']):continue
  if q.startswith('models/nli/') or ('/candidate/' in q and '/assets/' in q):continue
  if f.is_file():paths.add(q)
 for r in cand['sources']+cand['read_only_code_dependencies']+cand['data_role_pins']:paths.add(r['path'])
 for d in ['candidate/epoch15','controller/epoch15','legal-transfer/epoch15','audit/epoch15','epoch15/preparation']:
  for f in sorted((S/d).rglob('*')):
   if not f.is_file() or '__pycache__' in f.parts or '/candidate/epoch15/assets/' in str(f):continue
   paths.add(str(f.relative_to(ROOT)))
 for r in load(S/'candidate/epoch15/model-assets.lock.json')['assets']:paths.add(r['path'])
 for r in load(ROOT/'assets.lock.json')['assets']:paths.add(r['path'])
 core=load(S/'candidate/epoch5/reconstruction/official-package-closure.json');typ=load(S/'candidate/epoch5/reconstruction/typesafe-runtime-closure.json')
 for r in [x for group in core['packages'] for x in group['files']]+typ['files']:paths.add(r['path'])
 paths.update(['experiments/sota-2026-10-22/audit/epoch14/source_closure.mjs',str((HERE/'make_source_closure_inputs.py').relative_to(ROOT)),conf['path'],'models/manifest.json',str((HERE/'candidate-source-freeze.json').relative_to(ROOT)),str((HERE/'research-plan.v2.json').relative_to(ROOT)),str(Path(__file__).resolve().relative_to(ROOT))])
 plan={k:v for k,v in base.items() if k!='pins'}
 plan.update(epoch=15,revision='official-deberta-definition-priority-160-v1',study_id=STUDY,train='none',calibration='none',actual_project=str(ROOT),research_plan_sha256=sha(HERE/'research-plan.v2.json'),candidate_manifest_sha256=sha(S/'candidate/epoch15/proposal-manifest.json'),expected_nli_revision=mi['revision'],expected_nli_sha256=mi['onnx_sha256'],runtime_admission=rt,lease_expires_unix=owner['expires_unix'],prior_closed_study_native_attempts=16,prior_closed_epoch13_study_attempts=1,prior_closed_epoch14_native_attempts=0,new_study_native_attempt_cap=2,new_study_native_attempts_before=0,source_policy=rp['context_policy'],public_model_acquisition={'inference_calls_before_batch':0,'paid_calls':0,**mi})
 plan['datasets']={'development':dev['path'],'confirmation':conf['path']};plan['limits'].update(native_batches=2,threads=2,seconds_per_batch=600,seconds_per_decision=30,candidate_configs=1,paid_calls=0,GPU_calls=0)
 plan['pins']=[{'path':q,'sha256':sha(ROOT/q)} for q in sorted(paths)]
 put(HERE/'plan.v2.json',plan)
 put(HERE/'freeze-receipt.v2.json',{'at':at,'plan_sha256':sha(HERE/'plan.v2.json'),'pins':len(paths),'new_native_model_calls':0,'prior_closed_native_attempts':16,'all_model_runtime_data_hashes_verified':True})
 print(json.dumps({'status':'EPOCH15_PLAN_FROZEN','plan_SHA256':sha(HERE/'plan.v2.json'),'pins':len(paths)}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--candidate',action='store_true');a.add_argument('--plan',action='store_true');x=a.parse_args()
 if x.candidate==x.plan:raise ValueError('Choose exactly one stage')
 if x.candidate:candidate_freeze()
 else:freeze_plan()

