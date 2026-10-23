"""Close independent negative research accounting using saved evidence only."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,os
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch13/project';E=S/'epoch13'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x)for x in p.read_text().splitlines()if x]
a=obj(O/'actual-independent-v1.json');plan=obj(E/'plan.json');summary=obj(E/'study-completion.json');snapshot=obj(E/'actual-snapshot.json')
assert a['checks_passed'] and a['status']=='REJECTED_DEV_GATE' and not a['DEV_gate_passed'] and not a['internal_confirmation_gate_passed'] and not a['confirmation_consumed']
assert sha(E/'plan.json')==a['plan_SHA256']=='6aba06f350bb077c604ce2931bf95e302ea91cfac05c9990185d868ec6e82ac3'
for pin in plan['pins']:
 for root in(S.parents[1],P):assert sha(root/pin['path'])==pin['sha256'],pin['path']
assert len(snapshot['files'])==43
for x in snapshot['files']:
 for root in(E,P/'experiments/sota-2026-10-22/epoch13'):
  p=root/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],str(p)
assert summary['actual_native_attempts']==summary['native_processes_started']==1 and summary['lifetime_native_attempts']==16 and summary['unspent_phase_slots']==1 and summary['allowed_further_attempts_in_closed_study']==0
assert summary['development_conservatively_exposed_DEV'] and not summary['confirmation_consumed_or_attempted'] and not summary['confirmation_phase_attempted'] and not summary['confirmation_HTTP_started']
for root in(E,P/'experiments/sota-2026-10-22/epoch13'):
 assert not(root/'runs/confirmation').exists() and not(root/'confirmation-selection-lock.json').exists()
records=rows(E/'runs/development/records.jsonl');wire=rows(E/'runs/development/wire.jsonl');assert len(records)==len(wire)==24 and all(x['status']==200 for x in wire)
assert a['actual_NLI_singleton_pairs']==72 and a['actual_NLI_input_tokens']==35168 and a['actual_BGE_texts']==170 and a['actual_BGE_batches']==45 and a['ANN_full_order_agreement_count']==24 and a['max_same_context_singleton_logit_drift']==0
assert a['runtime_admission']['allowed'] and math.isclose(a['runtime_admission']['projected_confirmation_seconds'],543.4258634099679,abs_tol=1e-10)
attempt=obj(E/'runs/development/attempt.json');runtime=obj(E/'runs/development/runtime.json');pids=[attempt['pid'],*runtime['native_child_pids']];assert not any(Path('/proc',str(p)).exists()for p in pids)
old=obj(E/'durable-kit/experiments/sota-2026-10-22/epoch12/REJECTION_LEDGER.json');current=obj(E/'REJECTION_LEDGER.json');assert current['rejections'][:-1]==old['rejections'] and current['rejections'][-1]['epoch']==13 and current['rejections'][-1]['status']=='REJECTED_DEV_GATE'
manifest=obj(E/'EPOCH_MANIFEST.json');used=obj(E/'USED_IDENTITIES.json');assert manifest['status']=='REJECTED_DEV_GATE' and manifest['budget']['lifetime_native_attempts']==16 and manifest['budget']['allowed_further_attempts_in_closed_study']==0
assert manifest['independent_actual_report']['sha256']==sha(O/'actual-independent-v1.json') and not manifest['confirmation_consumed'] and manifest['confirmation_requests_completed']==0 and not manifest['SOTA_established'] and manifest['official_rank']is None
assert used['train']==used['calibration']==[] and used['new_DEV_groups_retired']==8 and used['exposed_originaltrain_groups_total']==189 and used['unreserved_originaltrain_groups_after_fixed_draw']==218 and not used['new_confirmation_retired_conservatively']
assert used['source_frozen_roles']['confirmation']['sha256']=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50' and used['source_frozen_roles']['confirmation']['requests_started']==used['source_frozen_roles']['confirmation']['requests_completed']==0
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'decision':'REJECTED_DEV_GATE_NO_PROMOTION_OR_SUBMISSION','plan_sha256':sha(E/'plan.json'),'independent_actual_report_sha256':sha(O/'actual-independent-v1.json'),'all196sourcepins_still_exact_outer_actual':True,'all43terminal_snapshotfiles_exact_outer_actual':True,'historical12rejectionprefix_unchanged':True,'new_epoch_root_manifest_sha256':sha(E/'EPOCH_MANIFEST.json'),'used_identities_sha256':sha(E/'USED_IDENTITIES.json'),'rejection_ledger_sha256':sha(E/'REJECTION_LEDGER.json'),'results_sha256':sha(E/'RESULTS.md'),'actual':{'native_processes':1,'conservative_invocation_reservations':1,'HTTP200':24,'failed_HTTP':0,'TRAIN':0,'DEV':24,'CONF':0,'NLI_singleton_pairs':72,'NLI_tokens':35168,'BGE_texts':170,'BGE_batches':45,'ANN_full_order_agreements':24,'same_context_logit_drift':0,'paid_calls':0,'GPU_calls':0},'metrics':a['metrics'],'latency':a['latency_by_phase_seconds'],'resources':a['resources'],'wall_seconds_including_all_init_cleanup':a['completion']['development']['wall_seconds_including_model_load'],'runtime_admission':a['runtime_admission'],'runtime_scope':'543.426s forecast passed runtime-alone admission. Failed DEV forbade CONF; forecast is not executed CONF or guaranteed timing. Whole HTTP contains all3NLIarms/native104/embedding/index; no primary-only latency. Worker/child getrusage peakRSS are not additive aggregate memory.','failure_direction':'Same fixed official RoBERTa reader with native evidence scored12/24 versus lexical14 and positional14; Native104sameexcerpt12. All proper losses worse all3controls, so native evidence selection plus changed reader did not pass. No cross-epoch causalaccuracy/modelsize/quantization comparison; differentDEVdocuments and BPE contexts.','data_roles':{'TRAIN':[],'calibration':[],'prior_exposed_originaltrain':181,'new_DEV_groups_retired':8,'total_exposed_originaltrain':189,'unreserved_after_draw':218,'reserved_CONFIRM_groups':16,'CONF48_model_consumed':False,'unused_confirmation_labels_inspected':False,'old_easy48_Legal96_f018_permanently_DEV':True,'old_TRAIN_roles_preserved':True},'budget':{'prior_closed_attempts':15,'epoch_attempts_used':1,'cap':2,'unspent_slots':1,'further_allowed':0,'all16_attempts_now_closed':True,'maxCPU':2,'seconds_per_phase_including_initcleanup':600,'automatic_retries':0,'paid':0,'GPU':0},'cleanup':{'observed_worker_nativePIDs':pids,'absent_now':True,'saved_owned_group_empty':True,'hard_deadline_met':True,'scoped_worklock_still_required_untilCAS':True},'science_scope':'Internal public CC-BY ContractNLI three-predicate NDA pilot; no currentJev300/fullLegalBench/ClaimBench score/rank or SOTA. Original champion unchanged. Unknown pretraining/fuzzy overlap/source-original export derivation and model dataset terms remain explicit; no weights republished. Numeric retention is exposure, not arithmetic truth/sufficient evidence.','auditor_actual_model_session_native_fit_paid_or_externalwrite_calls':0}
out=O/'science-closure-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'actual_attempts':1,'CONF_consumed':False,'closed_lifetime':16}))
