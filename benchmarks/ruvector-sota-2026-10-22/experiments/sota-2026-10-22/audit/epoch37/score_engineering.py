"""E37 independent stdlib replay of physically closed real engineering work.

No candidate/model/tokenizer/native imports or original oracle traversal. Every
retained forecast/certificate is audited before once-joined labels are used.
EVALUATE and BIND are distinct immutable operations, authorized by root only.
"""
import argparse,json,math
from pathlib import Path
from data_common import require,write_new,CLASSES,GOLD_NAMES,expected,canonical,digest,AUTHORED_LABEL_MAP_SHA256,finite
from phase_audit import KIND,read,ref,checked,source_checks,phase_integrity,supervisor_closure,physical_ownership_closure,publisher
from model_audit import audit_models
from lifecycle_audit import audit_lifecycle
from evidence_audit import audit_evidence
from nli_metrics import reader_check,metrics,engineering_gates,paired_differences,ARMS,CONTEXTS,REUSE,PRIMARY
from decision_proof_audit import decision_check
from query_audit import policy_check as query_policy_check


def quantile(values,q):
 require(bool(values)and all(finite(v)and v>=0 for v in values),'Nonfinite/empty actual timing');a=sorted(values);x=(len(a)-1)*q;lo=int(x);hi=min(lo+1,len(a)-1);return a[lo]+(x-lo)*(a[hi]-a[lo])

def policy_checks(root,plan):
 proof=read(root/plan['proof_policy_path'],plan['proof_policy_sha256']);contract=read(checked(root,plan['root_contract']))
 require(proof['epoch']==37 and proof['kind']==KIND and proof['policy']=='SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'and proof['grammar']=='typed-financial-affine-cardinality-v1'and proof['proof_enabled_roles']==['engineering']and proof['probability_policy']==contract['probability_policy'],'Frozen proof/role/probability policy changed')
 for k in ['full_source_closed_parse_required','global_source_consistency_required','neutral_concrete_true_false_worlds_required','neutral_entire_source_catalog_coverage_required','exact_quote_offsets_required','retrieval_miss_is_not_insufficiency']:require(proof[k]is True,'Unsound proof admission: '+k)
 require(proof['confirmation']==[]and proof['official_eligibility']=='HOLD'and proof['promotion_allowed']is False,'Proof authorized benchmark/confirmation/promotion')
 return {'query':query_policy_check(read(root/plan['query_policy_path'],plan['query_policy_sha256'])),'proof_policy':ref(root,root/plan['proof_policy_path']),'metrics_policy':plan['metrics_policy'],'no_calibrated_posterior_claim':True}

def role_outputs(root,corpus,bank,plan):
 evidence=audit_evidence(root,corpus,bank,'engineering',plan);rows=[];times={name:{'reader':[],'forward':[],'context':[],'decision':[],'forward_context_decision':[],'native_query':[]}for name in ARMS};certificates={n:[]for n in ARMS};actual=[]
 for case,inp in zip(corpus['cases'],bank['records']):
  require(set(case['readouts'])==set(CONTEXTS)and set(case['arms'])==set(ARMS),'All physical/derived contexts required');raw={};readers={}
  for name in CONTEXTS:
   physical=case['readouts'][name];r=physical['reader'];require(r['role']=='engineering','Nonengineering raw readout');raw[name]=reader_check(r,physical['premise'],inp['hypothesis'],physical['joint_pair_tokens']);actual.append(physical['readout_id'])
  for name in ARMS:
   arm=case['arms'][name];physical=case['readouts'][REUSE[name]];readers[name],proof=decision_check(name,arm,physical,raw[REUSE[name]],case);certificates[name].append({'id':case['id'],**proof});r=physical['reader']
   times[name]['reader'].append(r['reader_seconds']);times[name]['forward'].append(r['forward_seconds']);times[name]['context'].append(physical['context_seconds']);times[name]['decision'].append(arm['decision_seconds']);times[name]['forward_context_decision'].append(r['forward_seconds']+physical['context_seconds']+arm['decision_seconds']);times[name]['native_query'].append(physical['native_query_seconds'])
  rows.append({'id':case['id'],'document_id':case['document_id'],'readers':readers})
 require(len(rows)==12 and len(actual)==len(set(actual))==36 and sum(len(cc)for cc in certificates.values())==60,'Exact36 real readouts and60 derived forecasts required')
 return rows,times,evidence,certificates,actual

def timing_summary(times):
 return {name:{'n':12,**{k+'_p'+str(int(q*100))+'_seconds':quantile(v[k],q)for k in v for q in [.5,.95]},'scope':'Twelve actual singleton component observations for each arm; paired raw/verified arms reuse one real neural forward. forward_context_decision sums measured forward, source packing and decision only. It excludes model/BGE/index initialization, embedding, tokenizer/reader overhead and cleanup; not end-to-end or publisher timing. Native query is shared descriptive work.'}for name,v in times.items()}

def engineering_replay(rows,gate):
 labels=gate['expected_labels'];require(type(labels)is dict and set(labels)=={r[0]for r in expected('engineering')},'Exact12 retained joined labels required');require(digest(canonical(labels).encode())==AUTHORED_LABEL_MAP_SHA256,'Retained label map differs from premeasurement independent authored semantic review')
 require(all(v in GOLD_NAMES for v in labels.values())and {c:sum(GOLD_NAMES[v]==c for v in labels.values())for c in CLASSES}==dict.fromkeys(CLASSES,4),'Fixed4E4C4N labels required')
 require([r['id']for r in rows]==[r[0]for r in expected('engineering')],'Retained case ordering differs')
 for row in rows:row['gold']=GOLD_NAMES[labels[row['id']]]
 scores={name:metrics(rows,name)for name in ARMS};checks=engineering_gates(scores);return all(checks.values()),scores,checks

def gate_fence(raw,plan):
 gate=raw['engineering_gate'];counts=raw['counters'];pins={p['path']:p for p in plan['pins']};oracle=pins[plan['engineering_oracle_path']]
 require(gate['primary_arm']==PRIMARY and gate['frozen_rule']==plan['engineering_gate']and gate['n']==gate['oracle_label_join_count']==12 and gate['oracle']==oracle,'Frozen gate/oracle identity differs')
 for k in ['oracle_join_after_all36_readouts_and60_forecasts','all36_predictions_completed_before_oracle_read','all60_forecasts_completed_before_oracle_read','readers_unloaded_before_oracle','single_reader_lifecycle_closed_before_oracle']:require(gate[k]is True,'Once-join after forecasts/closure fence missing: '+k)
 require(gate['DEV_bank_read_before_gate']is False and gate['benchmark_generalization_claim']is False and gate['native_causal_gain_established']is False,'Forbidden benchmark/generalization/causal claim')
 require(counts['engineering_oracle_reads']==1 and counts['engineering_oracle_expected_labels_accessed']==counts['engineering_native_predictions_compared']==12,'Authored labels not joined exactly once12 after forecasts')
 return gate

def gate_check(raw,plan,rows,scores,passed):
 gate=gate_fence(raw,plan)
 for name in ARMS:
  w=gate['proper_scores_by_arm'][name];r=scores[name]
  for key,target in [('brier','Brier'),('nll','NLL'),('NLL_stable_logsoftmax','NLL'),('NLL_clipped_1e-12','NLL_clipped_1e-12')]:require(finite(w[key])and abs(w[key]-r[target])<=1e-12,'Worker/independent proper score differs: '+name+':'+key)
  require(w['NLL_clip_count']==r['NLL_clip_count']and w['probability_underflow_zero_count']==r['display_probability_underflow_count'],'Worker diagnostic clipping/underflow differs')
 require(gate['passed']is passed and gate['native_correct']==gate['primary_correct']==scores[PRIMARY]['correct']and gate['accuracy_gain_over_full_raw']==scores[PRIMARY]['correct']-scores['full_raw']['correct']and gate['baseline_ceiling_rejection']is(scores['full_raw']['correct']>10),'Worker independent frozen acceptance decision differs')
 require(gate['correct_by_arm']=={name:scores[name]['correct']for name in ARMS}and gate['by_class']=={label:scores[PRIMARY]['by_class'][gold]for label,gold in GOLD_NAMES.items()},'Worker independent confusion/class counts differ')
 require(raw['status']==('ENGINEERING_ADMISSION_PASSED'if passed else'ENGINEERING_ADMISSION_FAILED'),'Worker status differs from exact frozen gates')
 return gate

def evaluate(args):
 root=Path(args.project).resolve();planpath=Path(args.plan).resolve();plan,source=source_checks(root,planpath);planref=ref(root,planpath);rawpath=Path(args.raw).resolve();executionpath=Path(args.execution).resolve();closurepath=Path(args.closure).resolve()
 report={'schema_version':1,'epoch':37,'kind':KIND,'status':'REJECTED_ENGINEERING_INTEGRITY','checks_passed':False,'engineering_passed':False,'readiness_qualified':False,'diagnostic_qualified':False,'engineering_only':True,'engineering_metrics':None,'engineering_checks':{},'benchmark_accuracy':None,'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_rank':None,'official_SOTA_verified':False,'training':[],'development':[],'calibration':[],'confirmation':[],'used_confirmation_identities':[],'failed_integrity_checks':[],'failed_engineering_checks':[],'original_annotated_source_json_parsed':False,'annotation_choices_accessed':0,'original_benchmark_oracle_traversals_by_scorer':0,'authored_oracle_traversals_by_scorer':0,'model_native_tokenizer_calls_by_scorer':0,'source_checks':source,'actual_NLI_forwards':None,'final_derived_forecasts':None,'sampling_scope':'Twelve newly authored CC0 formal supplied-source engineering cases,4E4C4N. No benchmark, ClaimBench pilot, development, calibration or fresh-confirmation score.','uncertainty':['Generic exact typed affine/cardinality source certificates, with incompatible/unsupported source abstention, do not imply unrestricted natural-language reasoning.','No calibrated-posterior claim. Correct-certificate proper-score theorem applies to the SAME readout; no cross-context theorem or benchmark generalization claim.','All12 retained, no case filtering; five derived arms60 forecasts reuse36 physical readouts.','Both reader foundation/training lineage and official eligibility remain HOLD; no promotion/submission allowed.','Native/lexical identical coverage-prefix controls can be identical; null result supplies no causal native ranking benefit. Missing retrieval cannot prove source insufficiency.','Fixed serial order, singleton timings/resources include cache/allocator effects; component latency is not publisher latency.'],'evidence':{'plan':planref,'raw':ref(root,rawpath)if rawpath.is_file()else None,'execution':ref(root,executionpath)if executionpath.is_file()else None,'supervisor_observed_closure':ref(root,closurepath),'pretrained_model_source':plan['pretrained_model_source'],'model_profiles':ref(root,root/plan['model_profiles_path']),'original_archive_metadata':ref(root,root/plan['xxlarge_weight_metadata_path']),'legacy_original_load_plan':ref(root,root/plan['legacy_original_load_plan_path']),'metrics_policy':plan['metrics_policy'],'scorer_source':ref(root,Path(__file__).resolve())}}
 try:
  execution=read(executionpath)if executionpath.is_file()else None;proof=read(closurepath)
  if execution is not None:require(execution['plan_sha256']==planref['sha256'],'Execution differs from frozen actual plan bytes')
  report['observed_execution_before_integrity_audit']=execution;report['captured_execution']=execution
  observed=supervisor_closure(root,{'supervisor_observed_closure':ref(root,closurepath),'supervisor_closure_value':proof});report['supervisor_physical_closure']=observed
  report['physical_ownership_closure']=physical_ownership_closure(execution)if execution is not None else {'captured_execution':None,'scope':'Independent supervisor closure proof only; missing execution remains UNKNOWN.'}
  # Parsing raw (which retains joined labels) is prohibited before closure above.
  pub=publisher(root,plan);phase=pub.phase_evidence(root,'engineering',planref,required=True);report['actual_execution']=pub.aggregate_actual(phase)
  require(phase['raw']==report['evidence']['raw']and phase['execution']==report['evidence']['execution']and phase['supervisor_observed_closure']==ref(root,closurepath),'Canonical actual receipt projection differs')
  raw=phase['raw_value']
  if raw is not None:
   report['observed_raw_counters_before_integrity_audit']=raw.get('counters');report['observed_raw_errors_before_integrity_audit']=raw.get('errors');report['observed_raw_status_before_integrity_audit']=raw.get('status')
  require(pub.phase_completed(phase),'Canonical captured engineering phase incomplete/unknown');require(type(execution)is dict and type(raw)is dict and raw['plan_sha256']==planref['sha256'],'Complete execution/raw required')
  require(raw['corpora']['engineering']['corpus_reservation']==phase['corpus_reservations']['engineering'],'Actual corpus not bound to durable one-use reservation')
  integrity=phase_integrity(root,raw,execution,plan);policies=policy_checks(root,plan);model=audit_models(root,raw,plan);lifecycle=audit_lifecycle(raw)
  bank=read(root/plan['engineering_inputs_path'],plan['engineering_inputs_sha256']);rows,times,evidence,certificates,actual=role_outputs(root,raw['corpora']['engineering'],bank,plan)
  require(raw['counters']['native_insertions_completed']==evidence['source_index_vectors']and raw['counters']['native_hit_source_validations']==evidence['native_hits_verified'],'Native vector/hit totals differ')
  # First access to retained joined gold values occurs only now, after all audits.
  joined_gate=gate_fence(raw,plan);passed,scores,checks=engineering_replay(rows,joined_gate);gate_check(raw,plan,rows,scores,passed)
  report.update(checks_passed=True,engineering_passed=passed,readiness_qualified=passed,status='ACCEPTED_ENGINEERING_ADMISSION_ONLY'if passed else'REJECTED_ENGINEERING_ADMISSION',engineering_metrics=scores,engineering_checks=checks,failed_engineering_checks=[k for k,v in checks.items()if not v],paired_differences=paired_differences(scores),engineering_timing=timing_summary(times),engineering_context_audit=evidence,source_certificate_decisions=certificates,pretrained_model_audit=model,reader_lifecycle_audit=lifecycle,frozen_policy_audit=policies,phase_integrity=integrity,actual_operation_counters=raw['counters'],actual_resources=raw['resources'],whole_worker_wall_seconds=raw['wall_seconds_including_initialization_cleanup'],actual_NLI_forwards=36,final_derived_forecasts=60,physical_neural_readout_ids=actual,authored_labels_recomputed_from_existing_joined_records=12,errors_by_arm={name:[r for r in m['scores']if not r['correct']]for name,m in scores.items()})
 except (ValueError,KeyError,TypeError,IndexError,FileNotFoundError)as error:report['failed_integrity_checks'].append(type(error).__name__+': '+str(error))
 write_new(args.output,report);return report

def bind(args):
 root=Path(args.project).resolve();replay=read(Path(args.replay).resolve());results=read(Path(args.results).resolve());require(replay['epoch']==37 and replay['kind']==KIND,'Wrong engineering replay')
 for k,v in replay.items():require(results.get(k)==v,'Published result differs from immutable independent replay: '+k)
 require(results['benchmark_accuracy']is None and results['used_confirmation_identities']==[]and all(results[k]is False for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'])and results['official_rank']is None,'Forbidden benchmark/promotion/confirmation claim')
 for pin in replay['evidence'].values():
  if pin is not None:checked(root,pin)
 report=json.loads(json.dumps(replay));report['evaluated_integrity_checks_passed']=replay['checks_passed'];report['publication_binding_checks_passed']=True;report['checks_passed']=True;report['evidence']['results']=ref(root,Path(args.results).resolve());report['evidence']['qualification_replay']=ref(root,Path(args.replay).resolve());write_new(args.output,report);return report

if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);ev=sub.add_parser('evaluate')
 for n in ['project','plan','raw','execution','closure','output']:ev.add_argument('--'+n,required=True)
 bi=sub.add_parser('bind')
 for n in ['project','replay','results','output']:bi.add_argument('--'+n,required=True)
 a=p.parse_args();r=evaluate(a)if a.mode=='evaluate'else bind(a);print(json.dumps({'status':r['status'],'checks_passed':r['checks_passed'],'engineering_passed':r['engineering_passed']}))
