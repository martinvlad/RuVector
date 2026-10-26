"""Once E43 EVALUATE, metadata-only failure capture, and type-exact publication BIND."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;QUALIFIER_SHA='ebc714faa5d9b06a433f23eea36203d90c126fec48f678eb1a0307d71138836a'
def qualifier():
 p=HERE/'e43_qualification.py';b=p.read_bytes()
 if hashlib.sha256(b).hexdigest()!=QUALIFIER_SHA:raise ValueError('EVALUATOR_QUALIFIER_SOURCE_DRIFT')
 spec=importlib.util.spec_from_file_location('e43_evaluation_qualifier',p);m=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),m.__dict__);return m
Q=qualifier();F=Q.F;M=Q.M
A='experiments/sota-2026-10-22/audit/epoch43/';P='experiments/sota-2026-10-22/epoch43/'
def public_emit(r,project):
 if r is None:return None
 Q.public_reference(r,project);p=Path(r['path']);p=p if p.is_absolute()else Path(project)/p;return {'path':p.relative_to(Path(project).resolve()).as_posix(),'bytes':r['bytes'],'sha256':r['sha256']}
def evidence_emit(role,r,project,contract):
 if r is None:return None
 if role in ['joined_gold','private_features']:
  F.require(r['path']==contract['external_custody_evidence_paths'][role],'EXACT_TWO_PRIVATE_EVIDENCE_ROLES');F.read_ref(r);return r
 return public_emit(r,project)
def flags():return {k:False for k in ['goal_met','benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified','benchmark_generalization_claim']}
def baseline(status,plan_sha,command):return {'schema_version':1,'epoch':43,'kind':F.KIND,'phase':'dev','source_checkpoint':F.SOURCE,'source_plan_sha256':plan_sha,'status':status,'checks_passed':False,'dev_passed':False,'evaluation_executed':False,'metrics':None,'descriptive':None,'gate_checks':{k:'NOT_EVALUATED'for k in M.GATE_NAMES},'benchmark_accuracy':None,'official_rank':None,'official_eligibility':'HOLD','used_confirmation_identities':[],'reserved_confirmation_document_ids':list(F.PROTECTED_DOCUMENT_IDS),'data_roles':{'train':[],'dev':list(F.DEV_CASE_IDS),'calibration':[],'confirmation':[]},'command_execution':command,'evidence':{},'label_custody':{'semantic_label_decodes':None,'decode_attempted_tokens':None,'semantic_decode_count_uncertain':True},**flags()}
def safe_error(error):return {'code':'SOURCE_RUNTIME_OR_CUSTODY_INTEGRITY_STOP','exception_type':type(error).__name__,'message_sha256':F.sha(str(error).encode())}
def report_custody(report):
 F.require(type(report['semantic_decode_count_uncertain'])is bool,'CUSTODY_UNCERTAINTY_BOOLEAN')
 for key in ['semantic_label_decodes','decode_attempted_tokens']:F.require(report[key]is None or type(report[key])is int and 0<=report[key]<=12,'CUSTODY_COUNTS_NEVER_INFERRED')
 return {k:report[k]for k in ['semantic_label_decodes','decode_attempted_tokens','semantic_decode_count_uncertain']}
def capture_failure(admission_ref,project,command,error=None):
 Q.public_reference(admission_ref,project);a=F.load_ref(admission_ref,project);Q.envelope(a);F.require(a['root_metadata_failure_capture_authorized']is True and a['source_checkpoint']==F.SOURCE,'ROOT_METADATA_FAILURE_ADMISSION');ps=a['source_plan_sha256'];refs=a['evidence'];Q.public_reference(refs['plan'],project);plan=F.load_ref(refs['plan'],project);F.require(refs['plan']['sha256']==ps,'EXACT_FAILURE_PLAN_SHA');v=baseline('REJECTED_DEV_INTEGRITY',ps,command);contract=plan['publication_contract'];raw=execution=physical=None;capture_errors=[]
 for name,r in refs.items():
  try:
   if r is not None:v['evidence'][name]=evidence_emit(name,r,project,contract)
   if name in ['raw','execution','physical_closure']and r is not None:
    obj=F.load_ref(r,project);Q.envelope(obj)
    if name=='raw':raw=obj
    elif name=='execution':execution=obj
    else:physical=obj
  except Exception as e:v['evidence'][name]=None;capture_errors.append(dict(role=name,**safe_error(e)))
 gold=refs.get('gold_join_report')
 if gold is not None:
  try:v['label_custody']=report_custody(F.load_ref(gold,project))
  except Exception as e:capture_errors.append(dict(role='gold_join_report',**safe_error(e)))
 counts=raw.get('counters')if type(raw)is dict else None;worker=1 if raw is not None or type(execution)is dict and execution.get('worker_identity')else None;closed=physical is not None and physical.get('physical_closure_passed')is True and physical.get('owned_worker_group_members')==[]
 v['actual_execution']={'worker_attempts':worker,'owned_live_processes_closed':closed,'known_corpus_batches_attempted_at_last_capture':counts.get('corpus_batches_attempted')if counts is not None else None,'known_corpus_batches_completed_at_last_capture':counts.get('corpus_batches_completed')if counts is not None else None,'captured_counters':counts,'backend_forward_batch_count':None,'scope':'Captured receipt facts only. Burned source reservation never implies worker/model/corpus execution; missing receipts remain UNKNOWN and never authorize rerun.','new_invocations_after_owner_loss_forbidden':True}
 if a.get('preparation_only_no_data_or_phase_dispatch')is True:
  F.require(a['verified_preparation_only_receipt']is not None and raw is None and execution is None and not(Path(project)/A/'DATA_ADMISSION.json').exists(),'BLOCKED_ONLY_BEFORE_ANY_DATA_OR_PHASE_DISPATCH');Q.public_reference(a['verified_preparation_only_receipt'],project);proof=F.load_ref(a['verified_preparation_only_receipt'],project);F.require(proof['checks_passed']is True and proof['actual_data_calls']==proof['actual_phase_dispatches']==0,'ACTUAL_ZERO_PREPARATION_BOUNDARY');v['status']='BLOCKED_PREPARATION';v['actual_execution']['worker_attempts']=0
 v['errors']=capture_errors+([safe_error(error)]if error is not None else[]);return v

def evaluate(admission_ref,project,command):
 checked=Q.checked_bundle(admission_ref,project);plan=checked['objects']['plan'];ps=checked['source_plan_sha256'];paths=plan['publication_contract']['external_custody_evidence_paths'];gold_path=Path(project)/A/'GOLD_JOIN_REPORT.json';F.require(gold_path.exists()and Path(paths['joined_gold']).exists(),'RETAINED_COMPLETE_GOLD_JOIN_REQUIRED');report_ref=F.ref(gold_path);report=F.load_ref(report_ref,project);custody=report_custody(report);F.require(report['status']=='GOLD_JOIN_COMPLETE_AFTER_ALL_PHYSICAL_CLOSURE'and report['errors']==[]and custody=={'semantic_label_decodes':12,'decode_attempted_tokens':12,'semantic_decode_count_uncertain':False},'EXACT_ONCE12_LATE_GOLD_CUSTODY');joined_ref=report['evidence']['joined_gold'];F.require(joined_ref['path']==paths['joined_gold'],'EXACT_PRIVATE_JOINED_GOLD_PATH');marker=Path(paths['joined_gold']+'.EVALUATE_READ_ATTEMPT.json');F.require(not marker.exists(),'RETAINED_LABEL_JOIN_ALREADY_USED_FOR_EVALUATION');F.put(marker,{'epoch':43,'kind':F.KIND,'source_plan_sha256':ps,'retained_join_read_attempts':1,'original_vault_reads':0});joined=F.load_ref(joined_ref);Q.envelope(joined);F.require(joined['source_plan_sha256']==ps and joined['selected_ids']==list(F.DEV_CASE_IDS)and joined['semantic_label_decodes']==12 and joined['all_labels_decoded_after_forecasts_and_ALL_physical_closure']is True,'EXACT_RETAINED_POSTFORECAST_GOLD_JOIN');measured=M.evaluate_rows(checked['objects']['raw']['cases'],joined['labels']);v=baseline('DEV_DIAGNOSTIC_PASS_HOLD'if measured['dev_passed']else'REJECTED_DEV_DIAGNOSTIC',ps,command);v.update(checks_passed=True,dev_passed=measured['dev_passed'],evaluation_executed=True,metrics=measured['metrics'],descriptive=measured['descriptive'],gate_checks=measured['gate_checks'],actual_execution=checked['execution_audit'],input_audit=checked['input_audit'],label_custody=custody,errors=[])
 ev=dict(checked['references'],admission=admission_ref,dispatch_admission=checked['dispatch_admission_ref'],data_admission=checked['data_admission_ref'],gold_join_report=report_ref,joined_gold=joined_ref,private_features=checked['data_admission']['private_features']);protocol=plan['publication_contract']['public_absolute_evidence_paths']['protocol'];ev['protocol']=F.ref(protocol);v['evidence']={k:evidence_emit(k,r,project,plan['publication_contract'])for k,r in ev.items()};v['limitations']=['Only12DEV pairs/4source document clusters/3sharedtemplates; no fullbenchmark result or independent12document interpretation.','GenericQ4 causal-model fixedclass-token adapter, not pretrained3way head; unknown training/quantizer/target-source overlap.','Observed positive serverF32 class probabilities after source-verified three-class mask; no rawlogits, smoothing, calibration or original-unrounded-stable-NLL claim.','Selectedsourcewindows only; retrieval miss does not prove full-source insufficient evidence.','Allpoint gates may pass onlyasDEV_DIAGNOSTIC_PASS_HOLD; native104/full104comparison/unusedCONF/publishereligibility remain unverified.'];return v

def bind(replay_ref,results_ref,project):
 Q.public_reference(replay_ref,project);Q.public_reference(results_ref,project);replay=F.load_ref(replay_ref,project);results=F.load_ref(results_ref,project);F.require(set(results)==set(replay)|{'publication_checkpoint'}and all(Q.same_fact(results[k],v)for k,v in replay.items()),'EVERY_REPLAY_FIELD_RETAINED_TYPE_EXACT');return {'schema_version':1,'epoch':43,'kind':F.KIND,'phase':'dev','publication_binding_passed':True,'checks_passed':True,'evaluated_integrity_checks_passed':replay['checks_passed'],'dev_passed':replay['dev_passed'],'evaluation_executed':replay['evaluation_executed'],'evidence':{'qualification_replay':public_emit(replay_ref,project),'results':public_emit(results_ref,project)},'original_oracle_or_join_or_model_reads':0,'scientific_reevaluation_performed':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['EVALUATE','CAPTURE_FAILURE','BIND'],required=True);p.add_argument('--project',required=True);p.add_argument('--out',required=True)
 for name in ['admission','failure-admission','replay','results']:p.add_argument('--'+name);p.add_argument('--expected-'+name+'-sha256')
 args=p.parse_args();project=Path(args.project).resolve();out=Path(args.out);out=out if out.is_absolute()else project/out;want=project/A/('publication-binding.json'if args.mode=='BIND'else'qualification-replay.json');F.require(out==want,'EXACT_CANONICAL_MODE_OUTPUT');refs={}
 for name in ['admission','failure_admission','replay','results']:
  value=getattr(args,name)
  if value:
   path=Path(value);path=path if path.is_absolute()else project/path;r=F.ref(path);Q.public_reference(r,project);F.require(r['sha256']==getattr(args,'expected_'+name+'_sha256'),'EXACT_COMMAND_ADMISSION_REFERENCE');refs[name]=r
 command={'requested_mode':args.mode,'CLI_invocations':1,'evaluate_function_calls':0,'capture_failure_function_calls':0,'bind_function_calls':0};F.put(Path(str(out)+'.CLI_INVOCATION.json'),command)
 if args.mode=='BIND':
  command['bind_function_calls']=1;v=bind(refs['replay'],refs['results'],project);v['command_execution']=command
 elif args.mode=='CAPTURE_FAILURE':
  command['capture_failure_function_calls']=1;v=capture_failure(refs['failure_admission'],project,command)
 else:
  F.require('failure_admission'in refs,'FROZEN_FAILURE_PATH_ADMISSION_REQUIRED');plan_ref=F.load_ref(refs['failure_admission'],project)['evidence']['plan'];plan=F.load_ref(plan_ref,project);paths=plan['publication_contract']['external_custody_evidence_paths'];complete=(Path(paths['joined_gold']).is_file()and(project/A/'GOLD_JOIN_REPORT.json').is_file())
  if not complete:
   command['capture_failure_function_calls']=1;v=capture_failure(refs['failure_admission'],project,command,ValueError('MISSING_OR_PARTIAL_JOIN_GUARD_BEFORE_EVALUATE_FUNCTION'))
  else:
   command['evaluate_function_calls']=1;F.put(Path(str(out)+'.EVALUATE_FUNCTION_ATTEMPT.json'),command)
   try:v=evaluate(refs['admission'],project,command)
   except Exception as error:
    command['capture_failure_function_calls']=1;v=capture_failure(refs['failure_admission'],project,command,error);v['evaluation_executed']=True
 F.put(out,v);print(json.dumps({k:v[k]for k in ['status','checks_passed','dev_passed','evaluation_executed']if k in v}))
if __name__=='__main__':main()
