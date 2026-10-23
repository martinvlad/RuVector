"""Independent zero-inference science and exact terminal-snapshot closure."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch11/project';A=P/'experiments/sota-2026-10-22/epoch11';E=S/'epoch11'
def load(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
rp=O/'actual-independent-v1.json';r=load(rp);assert r['checks_passed'] and r['status']=='REJECTED_DEV_GATE'
assert r['auditor_native_calls']==r['auditor_ONNX_calls']==0
snap=load(E/'actual-snapshot.json');assert len(snap['files'])==43
for x in snap['files']:
 for root in [A,E]:
  p=root/x['path'];assert not p.is_symlink() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],str(p)
assert sha(A/'study-completion.json')==snap['terminal_summary_sha256']
assert snap['actual_attempts']==1 and snap['plan_sha256']==r['plan_SHA256']
plan=load(E/'plan.json');assert len(plan['pins'])==173
for x in plan['pins']:
 p=P/x['path'];assert not p.is_symlink() and sha(p)==x['sha256']
assert not (A/'runs/confirmation').exists() and not (E/'runs/confirmation').exists()
assert r['actual_requests']==24 and r['actual_successful_HTTP_by_corpus']=={'development':24,'confirmation':0}
assert r['training_feature_HTTP_requests']==0 and not r['confirmation_consumed'] and not r['unused_confirmation_labels_read']
assert not r['DEV_gate_passed'] and not r['runtime_admission']['allowed']
assert r['confirmed_native_process_starts']==r['conservative_invocation_reservations']==1
old=load(S/'epoch10/publication/stage/CONTINUATION.json')['execution_observed'];assert old['native_corpus_attempts_including_failed_request']==13 and old['actual_HTTP_successful_decisions']==735
assert old['native_corpus_batches_completed']==11 and old['actual_HTTP_training_feature_requests']==144 and old['actual_HTTP_evaluation_diagnostic_decisions']==591
used=load(E/'USED_IDENTITIES.json');assert used['exposed_originaltrain_groups_total']==173 and used['unreserved_originaltrain_groups_after_fixed_draw']==234
assert not used['new_confirmation_retired_conservatively'] and not used['confirmation_model_consumed_per_independent_report']
assert len(set(used['source_frozen_roles']['development']['source_groups']))==8 and len(set(used['source_frozen_roles']['confirmation']['source_groups']))==16
assert used['source_frozen_roles']['development']['requests_completed']==24 and used['source_frozen_roles']['confirmation']['requests_completed']==0
res=r['resources']['development'];comp=r['completion']['development']
proof={
 'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'decision':'REJECTED_DEV_GATE_DO_NOT_PROMOTE',
 'independent_actual_report_sha256':sha(rp),'frozen_plan_sha256':r['plan_SHA256'],'actual173pins_reverified':True,'raw_snapshot_files_both_actual_and_outer_verified':43,'terminal_snapshot_sha256':sha(E/'actual-snapshot.json'),
 'metrics':r['metrics'],'threeway_metrics':r['multiclass_metrics'],
 'rejection_reason':'Primary12/24 ties both matched lexical/positional12 and trails same-excerptNative10413. Frozen gate requires+2correct againstEACH3controls. PrimaryBrier.8722703894804444/NLL1.580674520685237 improves lexical properloss, worsens positional and104. Do not rescue by changing threshold, labels, readout or context afterDEV.',
 'confirmation48':'No confirmation phase directory, invocation, HTTP or model use; byteidentical850b bank remains reserved/project-model-unused. Tokenizer-only source capacity is not model use. Unknown pretrained contamination persists.',
 'training':'No TRAIN, calibration, head, fitting or model grid. One frozen higher-capacity pretrained threeway reader, T1, E0/N1/C2 mapping. Capacity is an architecture fact, not demonstrated quality gain.',
 'native_evidence':{'native_core_searches':24,'native104_excerpt_predictions':24,'NLI_singleton_pairs':r['actual_NLI_singleton_pairs'],'NLI_input_tokens':r['actual_NLI_input_tokens'],'BGE_texts':r['actual_BGE_texts'],'BGE_batches':r['actual_BGE_batches'],'all24literal_bundles_vectors_and_observed_native_ranks_verified':True,'exact_cosine_top2_candidate_sets_full_order_matches':r['ANN_full_order_agreement_count'],'same_context_pretrained_logit_drift':r['max_same_context_singleton_logit_drift'],'scope':'Exact cosine diagnostics corroborate observed actualnative ranking, never replace it. Existing top2 arm names are legacy aliases for shared512token multianchor coherentcontext.'},
 'resources':{'phase_wall_seconds':comp['wall_seconds_including_model_load'],'CPU_affinity':res['allowed_CPU_ids'],'ORT_threads':res['configured_ORT_threads'],'worker_CPU_seconds':res['worker_cpu_user_seconds']+res['worker_cpu_system_seconds'],'terminated_children_CPU_seconds':res['terminated_children_cpu_user_seconds']+res['terminated_children_cpu_system_seconds'],'worker_peak_RSS_bytes':res['worker_peak_RSS_bytes'],'child_largest_peak_RSS_bytes':res['largest_terminated_child_peak_RSS_bytes'],'scope':'Linuxprocess high-water marks are neither sum nor simultaneous totalRSS. WholeHTTP includes all3NLI arms+excerpt104+embedding/index; primarydeployment latency not measured.'},
 'latency':r['latency_by_phase_seconds'],'runtime_admission':r['runtime_admission'],'uncertainty':r['paired_doc_bootstrap'],'bootstrap_scope':r['bootstrap_scope'],
 'budget':{'prior13closed':True,'new_invocation_reservations':1,'new_confirmed_native_process_starts':1,'new_cap':2,'lifetime_conservative_native_attempts':14,'lifetime_completed_native_batches':12,'unspent_phase_slots':1,'further_attempts_allowed_in_closed_study':0,'successful_HTTP_this_epoch':24,'TRAIN_feature_HTTP':0,'DEV_evaluation_HTTP':24,'CONF_HTTP':0,'lifetime_successful_HTTP':759,'lifetime_TRAIN_feature_HTTP':144,'lifetime_evaluation_diagnostic_HTTP':615,'historic_failed_HTTP':2,'newerrors':0,'paid':0,'GPU':0},
 'exposure':{'newDEV8_permanently_retired':True,'originaltrain_exposed_groups_total':173,'unreserved_groups_after_draw':234,'reserved_confirmation_groups':16,'reserved_confirmation_queries':48},
 'scope_limits':['Licensed internal3hypothesis originalContractNLI NDApilot, not fullLegalBench/currentJev300/ClaimBench or official benchmark rank.','DEVonly8documentgroups; nominal unadjusted bootstrap, no fresh confirmation/generalization claim. Lexical Brier improvement alone cannot pass all-controls gate.','No causal cross-epoch model gain claim on differentDEV. No selection based on unused confirmation labels.','Annotation ANY overlap or each-span SOME overlap, where reported, does not imply complete annotation retention or legal sufficiency. Numeric-source retention is a provenance check, not truth.','Converter metadata links upstreamMITsource but exactupstreamweightcommit/separateconvertedlicense/mixedtrainingterms/unknowncontamination remain disclosed limits.'],
 'next_step':'Preserve negative result, unusedconfirmation and champion. A future distinct mechanism needs a new frozen plan, appropriateunused roles and same-model controls. Runtime704.54s projection also blocks this unchanged candidateCONF under600s cap; do not reattempt unchanged blocker.',
 'champion':'SubmittedNative104/RRF10 unchanged','official_score':None,'official_rank':None,'SOTA_established':False,'new_submissions_or_emails':0,'auditor_model_native_paid_calls':0}
p=O/'science-closure-v1.json'
with p.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p),'raw_snapshot_files':43}))
