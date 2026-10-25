"""Independent ContractNLI all12 helper-based pilot and frozen failure capture."""
import argparse,json,re
from pathlib import Path
import contractnli_io as I
import contractnli_closure as C
import contractnli_metrics as M
import contractnli_execution as X
import contractnli_input_audit as A
import contractnli_data as D
import contractnli_failure as F
FLAGS=F.FLAGS

def evaluate(admission_ref,joined_ref,gold_report_ref,protocol_ref,project):
 checked=C.checked_bundle(admission_ref,project);plan=checked['objects']['plan'];raw=checked['objects']['raw'];protocol=I.load_ref(protocol_ref,project);I.envelope(protocol);I.require(protocol['root_contract']==plan['root_contract']and protocol['arms']==M.ARMS and protocol['primary']==M.PRIMARY and protocol['reference']==M.REFERENCE,'EXACT_FROZEN_PROTOCOL');ids=checked['ids'];I.require(protocol['data_roles']==plan['data_roles'],'FIXED_DEV_IDENTITIES')
 report=I.load_ref(gold_report_ref,project)if gold_report_ref is not None else None;custody=F.custody_from_report(report)
 actual_base={'worker_attempts':1,'owned_live_processes_closed':True,'known_corpus_batches_attempted_at_last_capture':raw['counters']['corpus_batches_attempted'],'known_corpus_batches_completed_at_last_capture':raw['counters']['corpus_batches_completed'],'supervisor_execution_qualification':checked['supervisor_qualification']}
 # Missing/partial gold is handled before any retained-label pin or parse.
 if joined_ref is None or report is None or report['status']!='GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE' or custody['semantic_label_decodes']!=12 or custody['semantic_decode_count_uncertain']is not False:
  return F.replay(plan,checked['source_plan_sha256'],actual_base,{'admission':admission_ref,'protocol':protocol_ref,'joined_labels':joined_ref,'gold_join_report':gold_report_ref,**checked['references']},custody,[{'code':'GOLD_JOIN_MISSING_PARTIAL_OR_UNCERTAIN','quality':'NOT_EVALUATED'}],False)
 I.require(report['joined_labels']['sha256']==joined_ref['sha256']and report['joined_labels']['bytes']==joined_ref['bytes'],'EXACT_ONCE_JOIN_REFERENCE');execution=X.execution_audit(raw,plan,protocol['expected_counters_source'],project);features=[x for x in plan['external_data_assets']if x['role']=='dev_features'];I.require(len(features)==1,'ONE_EXTERNAL_FEATURE_BANK');f=features[0];records=D.load_private_features(f['path'],f['sha256'],ids);private=I.load_ref(raw['external_evidence']['nli_input_audits']);I.envelope(private);I.require(private['source_plan_sha256']==checked['source_plan_sha256'],'PRIVATE_AUDIT_PLAN');saved=private['readouts'];I.require(type(saved)is list and len(saved)==48 and len({s['readout_id']for s in saved})==48,'ALL48_PRIVATE_AUDITS');saved={s['readout_id']:s for s in saved};by_id={r['id']:r for r in records};native=I.load_ref(raw['external_evidence']['native_output']);native_cases={}
 for doc in native['documents']:
  I.require(len(doc['queries'])==1,'ONE_NATIVE_QUERY_PER_CASE');q=doc['queries'][0];cid=q['case_id'].removesuffix('::retrieval:original');I.require(cid not in native_cases,'DUPLICATE_NATIVE_CASE');native_cases[cid]=(doc,q)
 I.require(set(native_cases)==set(ids),'COMPLETE_NATIVE_CASE_SET');coverage={}
 for row in raw['cases']:
  record=by_id[row['id']]
  for key in ['record_ordinal','document_id','hypothesis_id','input_sha256','source_group_sha256','source_document_sha256','normalized_document_sha256','source_filename_key_sha256']:I.require(row[key]==record[key],'PUBLIC_SOURCE_IDENTITY_MISMATCH:'+key)
  source=list(range(len(record['evidence'])));I.require(row['source_unit_ids']==source,'COMPLETE_SOURCE_UNITS');doc,q=native_cases[row['id']];I.require(doc['initialized_vectors']==len(source)and q['requested_k']==len(source)and len(q['ids'])==len(source)and set(q['ids'])==set(source)and all(type(i)is int for i in q['ids'])and q['ids']==row['native_order_ids'],'ACTUAL_ALL_N_NATIVE_PROVENANCE');words=set(re.findall(r'\w+',record['claim'].lower()));sets=[set(re.findall(r'\w+',u['sentence'].lower()))for u in record['evidence']];scores=[len(words&w)/max(1,len(words|w))for w in sets];lex=sorted(source,key=lambda i:(-scores[i],i));I.require(row['lexical_order_ids']==lex,'MATCHED_LEXICAL_ORDER');I.require(row['claim_sha256']==A.digest(record['claim'])and row['evidence_list_sha256']==A.digest(json.dumps([u['sentence']for u in record['evidence']],ensure_ascii=False,separators=(',',':'))),'INPUT_CONTENT_HASHES');coverage[row['id']]={}
  for arm in M.ARMS:
   r=row['readouts'][arm];order=source if arm.endswith('source_order')else row['native_order_ids']if arm==M.PRIMARY else row['lexical_order_ids'];I.require(r['input_audit']['ordered_unit_ids']==order,'ARM_ORDER_MISMATCH');coverage[row['id']][arm]=A.check_saved_input(record,arm,r,saved[r['readout_id']])
 # One retained join read only after all source/physical/input audits. No vault.
 p=Path(joined_ref['path']);p=p if p.is_absolute()else Path(project)/p;I.put(Path(str(p)+'.EVALUATE_LABEL_READ_ATTEMPT.json'),{'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','source_plan_sha256':checked['source_plan_sha256'],'joined_labels':joined_ref,'automatic_retry':False});joined=I.load_ref(joined_ref,project);I.envelope(joined);I.require(joined['source_plan_sha256']==checked['source_plan_sha256']and joined['selected_ids']==ids and joined['semantic_labels_decoded']==12 and joined['label_reader_calls']==1 and joined['all_labels_decoded_after_forecasts_and_physical_closure']is True and joined['used_confirmation_identities']==[]and joined['evidence']['admission']==admission_ref and joined['evidence']['raw']==checked['references']['raw'],'EXACT_POST_CLOSURE_JOIN');labels=joined['labels'];I.require(set(labels)==set(ids),'FULL_FIXED_LABEL_MAP');results={a:M.metrics(raw['cases'],a,labels)for a in M.ARMS};gates=M.gates(results,True);passed=all(gates.values());return {'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','source_checkpoint':I.SOURCE,'source_plan_sha256':checked['source_plan_sha256'],'status':'ACCEPTED_DEV_PILOT_ONLY'if passed else'REJECTED_DEV_PILOT','checks_passed':True,'dev_passed':passed,'evaluation_executed':True,'metrics':results,'gate_checks':gates,'data_roles':plan['data_roles'],'arms':M.ARMS,'primary':M.PRIMARY,'reference':M.REFERENCE,'actual_NLI_forwards':48,'all_cases_retained_denominator':12,'input_coverage_audits':coverage,'label_custody':dict(custody,scorer_original_oracle_reads=0,scorer_retained_join_reads=1),'actual_execution':dict(actual_base,**execution),'evidence':{'protocol':protocol_ref,'admission':admission_ref,'joined_labels':joined_ref,'gold_join_report':gold_report_ref,**checked['references']},'benchmark_accuracy':None,'used_confirmation_identities':[],'official_eligibility':'HOLD','limitations':['12 officialTEST documents designatedDEV after excluding originalTRAIN423/Legal96aliases; sharedhypothesis templates and unknown modeltraining overlap prevent confirmation/generalization claims.','All12 unfiltered evaluate_class helper formulas; not full evaluate_all binary-filtered classification, evidence identification or paper/fullbenchmark score.','Author E/C undefined values remain null+UNDEFINED_AUTHOR_NAN and required gates fail; no class balancing/drops/hypothesis changes.','512ONLY_FIRST and blankline quote assembly are declared context adaptations; source-order is budgeted, no retrievalmiss proves NotMentioned.','Source tasksource has600-task training claims, but superiority and complete exclusion are unverified; rawT1 is not calibratedposterior.'],**FLAGS}

def bind(evaluation_ref,results_ref,project):
 v=I.load_ref(evaluation_ref,project);r=I.load_ref(results_ref,project);I.envelope(v);I.envelope(r);I.require(r['publication_checkpoint']['qualification_replay']==evaluation_ref and set(r)==set(v)|{'publication_checkpoint'}and all(I.same_fact(r[k],value)for k,value in v.items()),'PUBLIC_RESULT_MUST_PRESERVE_EVERY_REPLAY_FIELD');return {'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','checks_passed':True,'publication_binding_checks_passed':True,'evaluated_integrity_checks_passed':v['checks_passed'],'dev_passed':v['dev_passed'],'evaluation_executed':v['evaluation_executed'],'source_plan_sha256':v['source_plan_sha256'],'evidence':{'results':results_ref,'qualification_replay':evaluation_ref},'no_measurement_or_label_reads_in_BIND':True,'used_confirmation_identities':[],**FLAGS}

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['EVALUATE','CAPTURE_FAILURE','BIND'],required=True);p.add_argument('--project',required=True);p.add_argument('--out',required=True)
 for name in ['admission','joined','gold-report','protocol','failure-admission','evaluation','results']:p.add_argument('--'+name);p.add_argument('--expected-'+name+'-sha256')
 a=p.parse_args()
 if a.mode=='EVALUATE':I.require(a.failure_admission is not None and a.expected_failure_admission_sha256 is not None,'FROZEN_FAILURE_FALLBACK_COMMAND_REFERENCE_REQUIRED')
 def pin(name,optional=False):
  path=getattr(a,name.replace('-','_'));wanted=getattr(a,'expected_'+name.replace('-','_')+'_sha256')
  if path is None and optional:return None
  I.require(path is not None and wanted is not None,'EXACT_COMMAND_REF_REQUIRED:'+name);file=Path(path);file=file if file.is_absolute()else Path(a.project)/file
  if optional and not file.exists():return None
  r=I.command_ref(path,a.project);I.require(r['sha256']==wanted,'COMMAND_REF_SHA_MISMATCH:'+name);return r
 evaluation_function_calls=0;capture_function_calls=0;bind_function_calls=0
 if a.mode=='CAPTURE_FAILURE':capture_function_calls=1;r=F.capture_failure(pin('failure-admission'),a.project)
 elif a.mode=='BIND':bind_function_calls=1;r=bind(pin('evaluation'),pin('results'),a.project)
 else:
  # Optional join pins are inside guarded handling; absent files never escape
  # before the SOURCE-frozen failure path can preserve exact custody metadata.
  evaluation_called=False
  try:
   joined_pin=pin('joined',True);gold_pin=pin('gold-report',True);gold_meta=I.load_ref(gold_pin,a.project)if gold_pin is not None else None
   complete=gold_meta is not None and gold_meta['status']=='GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE'and gold_meta['semantic_labels_decoded']==12 and gold_meta['semantic_decode_count_uncertain']is False and joined_pin is not None
   if not complete:capture_function_calls+=1;r=F.capture_failure(pin('failure-admission'),a.project)
   else:
    admission_pin=pin('admission');protocol_pin=pin('protocol');evaluation_called=True;evaluation_function_calls+=1;r=evaluate(admission_pin,joined_pin,gold_pin,protocol_pin,a.project)
  except Exception as error:
   failure=pin('failure-admission',True);I.require(failure is not None,'FROZEN_FAILURE_ADMISSION_REQUIRED_FOR_GUARDED_EVALUATE_ERROR');capture_function_calls+=1;r=F.capture_failure(failure,a.project);r['evaluation_executed']=evaluation_called;r['errors'].append({'code':'EVALUATE_SOURCE_OR_CUSTODY_INTEGRITY_STOP','exception_type':type(error).__name__,'message_sha256':I.sha(str(error).encode())})
 r['command_execution']={'requested_mode':a.mode,'CLI_invocations':1,'evaluate_function_calls':evaluation_function_calls,'capture_failure_function_calls':capture_function_calls,'bind_function_calls':bind_function_calls,'model_or_oracle_calls_by_command_dispatcher':0}
 output=Path(a.out);output=output if output.is_absolute()else Path(a.project)/output;I.put(output,r);print(json.dumps({'status':r.get('status','BIND_COMPLETE'),'checks_passed':r['checks_passed'],'dev_passed':r['dev_passed'],'evaluation_executed':r['evaluation_executed']}))
if __name__=='__main__':main()
