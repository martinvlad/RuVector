"""E39 immutable report/manifest binding only; no inference, case or vault parse."""
import sys
sys.dont_write_bytecode=True
import argparse,copy,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'publication'))
import publication_common_v1 as c
from phase_contract_v1 import *
W=Path('/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508')

def checked(root,row):
 c.require(isinstance(row,dict)and set(row)=={'path','bytes','sha256'}and c.ref(root,row['path'])==row,'Exact public reference required');return row

def write_new(path,value):
 data=c.encoded(value,pretty=True)
 with path.open('xb')as target:target.write(data);target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def cumulative(actual):
 c.require(isinstance(actual,dict)and type(actual.get('worker_attempts'))is int and actual['worker_attempts']in (0,1),'Captured logical worker reservation required')
 attempts=actual.get('known_corpus_batches_attempted_at_last_capture',actual.get('corpus_batches_attempted'));completed=actual.get('known_corpus_batches_completed_at_last_capture',actual.get('completed_corpus_batches'))
 for value in (attempts,completed):c.require(value is None or type(value)is int and value in (0,1),'Captured current lower bound only')
 return {'corpus_attempts':None,'completed_corpus_batches':None,'verified_corpus_attempts_lower_bound':34+(attempts if attempts is not None else 0),'verified_completed_corpus_batches_lower_bound':32+(completed if completed is not None else 0),'bounded_native_process_attempts':39+actual['worker_attempts'],'legacy_native_qualification_process_attempts':6,'historical_E37_model_corpus_tail':'UNKNOWN_PERMANENTLY','benchmark_HTTP_successes':900,'benchmark_HTTP_failures':2,'current_official_HTTP_successes':3,'current_official_HTTP_failures':0}

def replay_ready(value):
 c.require(value.get('epoch')==39 and value.get('kind')==KIND and value.get('phase')==PHASE and value.get('status')in STATUSES,'Current frozen DEV pilot replay required')
 c.require(type(value.get('dev_passed'))is bool and type(value.get('checks_passed'))is bool,'Explicit DEV/integrity verdicts')
 c.require((value['status']=='ACCEPTED_DEV_PILOT_ONLY')is value['dev_passed']and(not value['dev_passed']or value['checks_passed']),'Only checked DEV-only acceptance')
 c.require(value.get('used_confirmation_identities')==[]and value.get('benchmark_accuracy')is None and all(type(value.get(k))is type(v)and value[k]==v for k,v in FLAGS.items()),'Never fullbenchmark/confirmation/promotion claim')
 c.require(isinstance(value.get('actual_execution'),dict),'Captured/UNKNOWN actual execution projection required');cumulative(value['actual_execution']);return value

def preserve_replay(replay,addition):
 c.require('publication_checkpoint'not in replay,'Publication already bound');out=copy.deepcopy(replay);out['publication_checkpoint']=copy.deepcopy(addition)
 c.require(all(out[k]==v for k,v in replay.items()),'Never overwrite or drop any evaluated field');return out

def setup(args):
 c.require(args.scope.absolute()==W,'Exact current isolated scope');root=c.directory(W/'project');c.live_owner(W);plan=c.parse(root/PLAN_PATH);pr=c.ref(root,PLAN_PATH)
 c.require(plan.get('epoch')==39 and plan.get('kind')==KIND and plan.get('phase')==PHASE and plan.get('source_checkpoint')==c.BASE_COMMIT,'Current immutable plan')
 for row in plan['pins']:checked(root,row)
 admission=c.parse(root/(E+'SOURCE_ADMISSION.json'));c.require(admission.get('plan_sha256')==pr['sha256']and admission.get('verified_actual_remote_readback')is True and c.re.fullmatch('[0-9a-f]{40}',admission.get('published_source_commit','')),'Actual source-before-measurement admission required')
 replayref=c.ref(root,args.replay);replay=replay_ready(c.parse(root/args.replay))
 closure=c.ref(root,args.closure_report);proof=c.parse(root/args.closure_report)
 c.require(proof.get('checks_passed')is True and proof.get('physical_closure_passed')is True and proof.get('phase')==PHASE and proof.get('source_plan_sha256')==pr['sha256'],'Independent known physical closure required; UNKNOWN cannot close')
 c.require(replay['actual_execution'].get('owned_live_processes_closed')is True,'Captured ownership closure must remain true')
 for row in replay.get('evidence',{}).values():
  if isinstance(row,dict)and set(row)=={'path','bytes','sha256'}:checked(root,row)
 return root,plan,pr,admission,replayref,replay,closure

def results(args):
 root,plan,pr,admission,replayref,replay,closure=setup(args)
 for name in ('RESULTS.json','REJECTION_LEDGER.json','LEARNINGS.json','USED_CONFIRMATION_IDENTITIES.json','SOURCE_MANIFEST.json','EPOCH_MANIFEST.json'):c.require(not(root/(E+name)).exists(),'Immutable outputs already exist')
 actual=copy.deepcopy(replay['actual_execution']);counts=cumulative(actual)
 addition={'source_commit':admission['published_source_commit'],'plan':pr,'source_freeze':plan['source_freeze'],'root_contract':plan['root_contract'],'qualification_replay':replayref,'independent_physical_closure':closure,'cumulative_execution':counts,'all_slots_closed':True,'remaining_slots':REMAINING,'scope':'Twelve real FinFact DEV identities selected under frozen label-blind policy; supplied evidence only, private text/token/features/vault/logs outside public project. Frozen design has four arms/48NNI; actual completed operations are retained in actual_execution. The design specifies official ordered-threshold decisions and the declared248only-first/claim-preservation pilot policy. No numerical certificate confidence override, fresh confirmation, fullbenchmark placement or champion promotion.','used_confirmation_identities':[]}
 out=preserve_replay(replay,addition);write_new(root/(E+'RESULTS.json'),out);rr=c.ref(root,E+'RESULTS.json')
 prior=c.parse(W/'controls-source/CONTINUATION.json');checked(root,prior['rejection_ledger']);ledger=copy.deepcopy(c.parse(root/prior['rejection_ledger']['path']))
 c.require(not any(v.get('epoch')==39 for v in ledger.get('rejections',[])),'No duplicate rejection')
 decision={'epoch':39,'status':replay['status'],'dev_passed':replay['dev_passed'],'results':rr,'scope':addition['scope'],**FLAGS}
 ledger['epoch39_decision']=decision;ledger['epoch39_actual_execution']=actual;ledger['epoch39_cumulative_execution']=counts;ledger['epoch39_budget']={'worker_attempts_used':actual['worker_attempts'],'remaining_slots':REMAINING,'all_unspent_slots_permanently_closed':True}
 if not replay['dev_passed']:ledger['rejections'].append(decision)
 else:ledger['epoch39_dev_pilot_acceptance']=decision
 write_new(root/(E+'REJECTION_LEDGER.json'),ledger)
 write_new(root/(E+'USED_CONFIRMATION_IDENTITIES.json'),{'epoch':39,'kind':KIND,'train':[],'calibration':[],'confirmation':[],'used_confirmation_identities':[],'new_source_exposed_DEV_identities_forever':plan['data_roles']['dev'],'prior_423_benchmark_partition_unchanged':{'exposed':325,'unused':74,'protected':24}})
 write_new(root/(E+'LEARNINGS.json'),{'epoch':39,'kind':KIND,'phase':PHASE,'status':replay['status'],'dev_passed':replay['dev_passed'],'results':rr,'evaluated_fields_preserved':True,'scope':addition['scope'],'future_work_proposed_not_executed':True,'champion_native104_unchanged':True,'actual_cumulative_corpus_totals':'UNKNOWN_PERMANENTLY_FROM_E37','verified_lower_bounds':counts,'future_paid_GPU_authorization':0})
 return {'status':replay['status'],'results':rr,'every_evaluated_field_preserved':True,'science_Git_calls':0}

def binding_ready(root,args,replay,replayref,closure):
 result=c.parse(root/(E+'RESULTS.json'));c.require(all(result.get(k)==v for k,v in replay.items()),'Result differs from immutable once EVALUATE')
 binding=c.ref(root,args.binding);report=c.parse(root/args.binding)
 c.require(report.get('checks_passed')is True and report.get('publication_binding_checks_passed')is True and report.get('evaluated_integrity_checks_passed')is replay['checks_passed'],'Independent binding distinguishes metadata from scientific integrity')
 evidence=report.get('evidence',{});c.require(evidence.get('results')==c.ref(root,E+'RESULTS.json')and evidence.get('qualification_replay')==replayref,'Binding exact result/replay refs')
 review=c.ref(root,args.acceptance);rv=c.parse(root/args.acceptance)
 c.require(rv.get('checks_passed')is True and rv.get('publication_allowed')is True and rv.get('dev_passed')is replay['dev_passed']and rv.get('no_raw_third_party_text_in_public_files')is True,'Independent final publication/privacy/verdict review')
 c.require(rv.get('results')==c.ref(root,E+'RESULTS.json')and rv.get('binding')==binding and rv.get('closure_report')==closure,'Final review exact identity binding')
 return result,binding,review

def manifest(args):
 root,plan,pr,admission,replayref,replay,closure=setup(args);result,binding,review=binding_ready(root,args,replay,replayref,closure)
 c.require(not(root/(E+'SOURCE_MANIFEST.json')).exists()and not(root/(E+'EPOCH_MANIFEST.json')).exists(),'No manifest overwrite')
 def files():return[{'path':name,'bytes':len(body),'sha256':c.sha(body)}for name,body in sorted(c.walk_current(root).items())]
 write_new(root/(E+'SOURCE_MANIFEST.json'),{'epoch':39,'kind':KIND,'phase':PHASE,'source_checkpoint':c.BASE_COMMIT,'source_commit':admission['published_source_commit'],'plan':pr,'source_freeze':plan['source_freeze'],'files':files(),'rule':'Nonrecursive inventory before two manifests. No project additions/edits after EPOCH seal.'})
 value={'schema_version':1,'epoch':39,'kind':KIND,'phase':PHASE,'status':replay['status'],'dev_passed':replay['dev_passed'],'evaluated_integrity_checks_passed':replay['checks_passed'],'benchmark_accuracy':None,**FLAGS,'source_checkpoint':c.BASE_COMMIT,'source_commit':admission['published_source_commit'],'plan':pr,'source_freeze':plan['source_freeze'],'root_contract':plan['root_contract'],'results':c.ref(root,E+'RESULTS.json'),'rejection_ledger':c.ref(root,E+'REJECTION_LEDGER.json'),'learnings':c.ref(root,E+'LEARNINGS.json'),'used_identities':c.ref(root,E+'USED_CONFIRMATION_IDENTITIES.json'),'source_manifest':c.ref(root,E+'SOURCE_MANIFEST.json'),'qualification_replay':replayref,'binding':binding,'independent_report':review,'physical_closure_report':closure,'actual_execution':replay['actual_execution'],'cumulative_execution':cumulative(replay['actual_execution']),'used_confirmation_identities':[],'all_slots_closed':True,'phase_remaining':REMAINING,'goal_verified':False,'data_roles':plan['data_roles'],'files':files()}
 write_new(root/(E+'EPOCH_MANIFEST.json'),value);return {'status':value['status'],'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'science_Git_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('results','manifest'));parser.add_argument('--scope',type=Path,default=W)
 for name in ('replay','closure-report'):parser.add_argument('--'+name,required=True)
 for name in ('binding','acceptance'):parser.add_argument('--'+name)
 args=parser.parse_args();print(json.dumps(globals()[args.mode](args),sort_keys=True))
