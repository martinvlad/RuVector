"""Independent E39 DEV evaluation and separate metadata publication binding.

No model/tokenizer/native imports. EVALUATE only follows authenticated SOURCE and
physical closure and uses retained once-joined labels, never the original oracle.
"""
import argparse,json,re
from pathlib import Path
import finfact_io as I
import finfact_closure as C
import finfact_metrics as M
import finfact_execution as X
import finfact_input_audit as A
import finfact_data as D
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None,'benchmark_generalization_claim':False}

def evaluate(admission_ref,joined_ref,protocol_ref,project):
 checked=C.checked_bundle(admission_ref,project);plan=checked['objects']['plan'];raw=checked['objects']['raw'];protocol=I.load_ref(protocol_ref,project);I.envelope(protocol);I.require(protocol['root_contract']==plan['root_contract']and protocol['arms']==M.ARMS and protocol['primary']=='b354_native'and protocol['reference']=='xxlarge_source_order','EXACT_FROZEN_PROTOCOL_REQUIRED');root=I.load_ref(protocol['root_contract'],project);I.require(root['DEV_gates']==protocol['DEV_gates']and root['arms']==M.ARMS,'ROOT_GATES_UNMODIFIED_REQUIRED');ids=checked['ids'];I.require(protocol['data_roles']==plan['data_roles'],'FIXED_DEV_IDENTITIES_REQUIRED')
 # All readout/source/lifecycle/resource audits finish before retained labels are
 # semantically accessed. The worker never sees these joined labels.
 execution=X.execution_audit(raw,plan,protocol['expected_counters_source'],project);features=[x for x in plan['external_data_assets']if x['role']=='dev_features'];I.require(len(features)==1,'ONE_HASH_PINNED_EXTERNAL_FEATURE_BANK_REQUIRED');f=features[0];records=D.load_private_features(f['path'],f['sha256'],ids);I.require(len(records)==12,'ALL_SOURCE_RECORDS_REQUIRED');private_ref=raw['external_evidence']['nli_input_audits'];private=I.load_ref(private_ref);I.envelope(private);I.require(private['source_plan_sha256']==checked['source_plan_sha256'],'PRIVATE_AUDIT_PLAN_MISMATCH');saved=private['readouts'];I.require(type(saved)is list and len(saved)==48 and len({s['readout_id']for s in saved})==48,'ALL_FORTY_EIGHT_SAVED_INPUT_AUDITS_REQUIRED');saved={s['readout_id']:s for s in saved};coverage={};by_id={r['id']:r for r in records};native=I.load_ref(raw['external_evidence']['native_output']);native_cases={}
 for doc in native['documents']:
  I.require(len(doc['queries'])==1,'ONE_NATIVE_QUERY_PER_CASE_REQUIRED');q=doc['queries'][0];caseid=q['case_id'].removesuffix('::retrieval:original');I.require(caseid not in native_cases,'DUPLICATE_NATIVE_CASE');native_cases[caseid]=(doc,q)
 I.require(set(native_cases)==set(ids),'COMPLETE_REAL_NATIVE_CASE_SET_REQUIRED')
 for row in raw['cases']:
  record=by_id[row['id']];I.require(row['input_sha256']==record['input_sha256']and row['record_ordinal']==record['record_ordinal']and row['document_id']==record['document_id']and row['hypothesis_id']==record['hypothesis_id']and row['url_group_sha256']==record['url_group_sha256'],'PUBLIC_SOURCE_IDENTITY_MISMATCH');source_ids=list(range(len(record['evidence'])));I.require(row['source_unit_ids']==source_ids,'COMPLETE_SOURCE_UNIT_SET_REQUIRED');doc,query=native_cases[row['id']];I.require(doc['initialized_vectors']==len(source_ids)and query['requested_k']==len(source_ids)and len(query['ids'])==len(source_ids)and all(type(i)is int for i in query['ids'])and set(query['ids'])==set(source_ids)and query['ids']==row['native_order_ids'],'ACTUAL_ALL_N_NATIVE_RANK_PROVENANCE_REQUIRED');words=set(re.findall(r'\w+',record['claim'].lower()));sentence_words=[set(re.findall(r'\w+',u['sentence'].lower()))for u in record['evidence']];lexical_scores=[len(words&w)/max(1,len(words|w))for w in sentence_words];lexical=sorted(source_ids,key=lambda i:(-lexical_scores[i],i));I.require(row['lexical_order_ids']==lexical,'MATCHED_FIXED_LEXICAL_RANKING_MISMATCH');I.require(row['claim_sha256']==A.digest(record['claim'])and row['evidence_list_sha256']==A.digest(json.dumps([u['sentence']for u in record['evidence']],ensure_ascii=False,separators=(',',':'))),'CLAIM_EVIDENCE_HASH_MISMATCH');coverage[row['id']]={}
  for arm in M.ARMS:
   r=row['readouts'][arm];order=source_ids if arm.endswith('source_order')else row['native_order_ids']if arm=='b354_native'else row['lexical_order_ids'];I.require(r['input_audit']['ordered_unit_ids']==order,'MATCHED_ARM_UNIT_ORDER_MISMATCH');coverage[row['id']][arm]=A.check_saved_input(record,arm,r,saved[r['readout_id']])
 # Only the retained join is decoded; neither vault nor original dataset labels
 # are touched by EVALUATE, and every label is retained even if gates fail.
 joined_path=Path(joined_ref['path']);joined_path=joined_path if joined_path.is_absolute()else Path(project)/joined_path;I.put(Path(str(joined_path)+'.EVALUATE_LABEL_READ_ATTEMPT.json'),{'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','source_plan_sha256':checked['source_plan_sha256'],'joined_labels':joined_ref,'scorer_original_oracle_reads':0,'scorer_retained_join_read_attempts':1,'automatic_retry':False});joined=I.load_ref(joined_ref,project);I.envelope(joined);I.require(joined['source_plan_sha256']==checked['source_plan_sha256']and joined['selected_ids']==ids and joined['semantic_labels_decoded']==12 and joined['label_reader_calls']==1 and joined['all_labels_decoded_after_forecasts_and_physical_closure']is True and joined['used_confirmation_identities']==[],'EXACT_ONCE_POST_CLOSURE_JOIN_REQUIRED');I.require(joined['evidence']['admission']==admission_ref and joined['evidence']['raw']==checked['references']['raw']and joined['evidence']['physical_closure']==checked['references']['physical_closure'],'JOIN_FORECAST_CLOSURE_REFERENCE_MISMATCH');labels=joined['labels'];I.require(set(labels)==set(ids),'ALL_SELECTED_LABELS_RETAINED_REQUIRED');results={arm:M.metrics(raw['cases'],arm,labels)for arm in M.ARMS};gates=M.gates(results,True);passed=all(gates.values());paired={}
 for control in M.CONTROLS:
  pairs=list(zip(results[M.PRIMARY]['scores'],results[control]['scores']));paired[control]={'N':12,'both_correct':sum(a['correct']and b['correct']for a,b in pairs),'primary_only_correct':sum(a['correct']and not b['correct']for a,b in pairs),'control_only_correct':sum(b['correct']and not a['correct']for a,b in pairs),'both_wrong':sum(not a['correct']and not b['correct']for a,b in pairs),'mean_Brier_difference_primary_minus_control':results[M.PRIMARY]['Brier']-results[control]['Brier'],'mean_NLL_difference_primary_minus_control':results[M.PRIMARY]['NLL']-results[control]['NLL']}
 return {'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','source_checkpoint':I.SOURCE,'source_plan_sha256':checked['source_plan_sha256'],'status':'ACCEPTED_DEV_PILOT_ONLY'if passed else'REJECTED_DEV_PILOT','checks_passed':True,'dev_passed':passed,'benchmark_accuracy':None,'official_rank':None,'official_eligibility':'HOLD','model_selection_lineage':'HOLD','used_confirmation_identities':[],'data_roles':plan['data_roles'],'primary':M.PRIMARY,'reference':M.REFERENCE,'arms':M.ARMS,'actual_NLI_forwards':48,'all_cases_retained_denominator':12,'gate_checks':gates,'metrics':results,'paired_control_comparisons':paired,'uncertainty':'Only12 deterministic URL-grouped realDEV examples; all retained. Accuracy/proper differences and twelve-observation tail quantiles are descriptive; no independent confirmation, population confidence or fullbenchmark placement is established. No statistical-significance gate was fitted.','input_coverage_audits':coverage,'actual_execution':{'owned_live_processes_closed':True,'worker_attempts':1,'known_corpus_batches_attempted_at_last_capture':1,'known_corpus_batches_completed_at_last_capture':1,**execution},'label_custody':{'semantic_label_decodes':12,'join_reader_calls':1,'scorer_original_oracle_reads':0,'scorer_retained_join_reads':1},'evidence':{'protocol':protocol_ref,'admission':admission_ref,'joined_labels':joined_ref,**checked['references']},'limitations':['DEV12 selected deterministically without labels; no fresh confirmation, training, calibration, full-benchmark score, rank or benchmark-generalization claim.','Raw source-order arm is248-token premise-budgeted, fullclaim preserved; ONLY_FIRST differs from official longest-first.','Brier/stable unclipped logsoftmax NLL are additional metrics; official macro uses observed gold/pred labels union.','Quantity coverage is a fixed regex/retained-offset diagnostic, not numerical correctness; currency-adjacent suffix fragments may be counted.','Native ordering ablation may be null; no retrieval miss proves insufficient evidence.','Underlying pretrained selection/training/evaluation overlap remains unresolved and official eligibility HOLD.'],**FLAGS}

def bind(evaluation_ref,results_ref,project):
 evaluation=I.load_ref(evaluation_ref,project);results=I.load_ref(results_ref,project);I.envelope(evaluation);I.envelope(results);I.require(results['publication_checkpoint']['qualification_replay']==evaluation_ref,'RESULTS_MUST_REFERENCE_EXACT_EVALUATION');I.require(set(results)==set(evaluation)|{'publication_checkpoint'}and all(results[k]==v for k,v in evaluation.items()),'PUBLIC_RESULTS_MUST_PRESERVE_EVERY_EVALUATION_FIELD');return {'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','checks_passed':True,'publication_binding_checks_passed':True,'evaluated_integrity_checks_passed':evaluation['checks_passed'],'dev_passed':evaluation['dev_passed'],'source_plan_sha256':evaluation['source_plan_sha256'],'evidence':{'results':results_ref,'qualification_replay':evaluation_ref},'no_scientific_measurements_or_oracle_reads_in_BIND':True,'used_confirmation_identities':[],**FLAGS}

def failure_execution_capture(admission_ref,project):
 # Failure reporting preserves observed/unknown counts without a second label
 # read, worker execution, inference, or invented successful corpus completion.
 result={'worker_attempts':None,'owned_live_processes_closed':None,'known_corpus_batches_attempted_at_last_capture':None,'known_corpus_batches_completed_at_last_capture':None,'capture_errors':[]}
 try:
  a=I.load_ref(admission_ref,project);I.envelope(a);I.require(a['root_custodian_authorized']is True,'AUTHENTICATED_ROOT_CAPTURE_REQUIRED');refs=a['evidence'];raw=I.load_ref(refs['raw'],project);proof=I.load_ref(refs['physical_closure'],project);dispatch=I.load_ref(refs['dispatch'],project)
  I.require(proof['source_plan_sha256']==a['source_plan_sha256']and proof['physical_closure_passed']is True and proof['physical_supervisor_closed']is True and proof['unknown_physical_ownership']is False and proof['owned_worker_group_members']==[],'KNOWN_PHYSICAL_CLOSURE_REQUIRED');result['owned_live_processes_closed']=True
  # An actual DISPATCH_ATTEMPT authenticated by the root admission records one
  # reserved logical worker attempt even when scientific completion is partial.
  I.envelope(dispatch);I.require(dispatch['plan_sha256']==a['source_plan_sha256'],'DISPATCH_PLAN_MISMATCH');result['worker_attempts']=1
  c=raw.get('counters',{})
  for observed,key in [('corpus_batches_attempted','known_corpus_batches_attempted_at_last_capture'),('corpus_batches_completed','known_corpus_batches_completed_at_last_capture')]:
   value=c.get(observed);result[key]=value if type(value)is int and value in[0,1]else None
  result['captured_actual_counters']=c;result['physical_closure_evidence']=refs['physical_closure'];result['raw_evidence']=refs['raw']
 except Exception as error:result['capture_errors'].append(type(error).__name__+':'+str(error))
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['EVALUATE','BIND'],required=True);p.add_argument('--project',required=True);p.add_argument('--out',required=True)
 for name in ['admission','joined','protocol','evaluation','results']:p.add_argument('--'+name);p.add_argument('--expected-'+name+'-sha256')
 a=p.parse_args()
 def pin(name):
  path=getattr(a,name);wanted=getattr(a,'expected_'+name+'_sha256');I.require(path is not None and wanted is not None,'EXPLICIT_REFERENCE_SHA_REQUIRED:'+name);r=I.command_ref(path,a.project);I.require(r['sha256']==wanted,'COMMAND_REFERENCE_SHA_MISMATCH:'+name);return r
 if a.mode=='EVALUATE':
  admission=pin('admission');joined=pin('joined');protocol=pin('protocol')
  try:r=evaluate(admission,joined,protocol,a.project)
  except Exception as error:r={'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','status':'REJECTED_DEV_INTEGRITY','checks_passed':False,'dev_passed':False,'benchmark_accuracy':None,'used_confirmation_identities':[],'actual_execution':failure_execution_capture(admission,a.project),'errors':[type(error).__name__+':'+str(error)],'evidence':{'admission':admission,'joined_labels':joined,'protocol':protocol},'retained_denominator':12,**FLAGS}
 else:r=bind(pin('evaluation'),pin('results'),a.project)
 output=Path(a.out);output=output if output.is_absolute()else Path(a.project)/output;I.put(output,r);print(json.dumps({'status':r.get('status','BIND_COMPLETE'),'checks_passed':r['checks_passed'],'dev_passed':r['dev_passed']}))
if __name__=='__main__':main()
