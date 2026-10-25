"""E41 admission-blocked metadata only. Never reads archive/features/vault/gold.

Root invokes results, obtains independent publication/privacy review, invokes
manifest, then controls/stage outside project. No scientific SOURCE or replay.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, copy, json
import blocked_common_v1 as c

E=c.P+'epoch41/'
INPUTS=E+'BLOCKED_INPUTS.json'
STATUS='BLOCKED_PRE_DATA_ADMISSION'
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PARENT='fa7fb072d4461b4b91f65dc6ed5622090d3fc933'
TREES={'root':'3de0ebe9a41a46f46e474d9c6a4fb789a118b81d','bench':'70a813bde01550d53817e282c1bf537812b2eea5','scope':'e6645cef260e6fddac7ac2cc82ca9c432a9f60f5'}
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None}
PINNED={
 'root_contract':(6238,'fef319ea3f05753a59fffebd9c0ed94692bc1175b105eb99331b3ac515b9b207'),
 'planning_readback':(3826,'aaa20f0ba53c1b6c60a5995b175bb6de3141f54fc909f6c83d253736fdc11c74'),
 'admission_failure':(8423,'e632d7b16526e4ec2889091456a07e30a19043e90517f43671ac932135d6020b'),
 'physical_closure':(4691,'61d5072727148f28f13a21f2ecd8c0e066e8f076d63cf37cc5613b00b37ce9d6'),
 'materialization_report':(2152,'2c7d5cc3ff2102b76ba1ab043d503176e1b1054f5ee9667d8a993a8145474c98'),
 'materialization_result':(361,'0971730fee9b9f85744c839635cf2a1f16d2785dc2d55e8c656ce4e8ba47326e'),
 'official_refresh_review':(3774,'172fb9df51c2f38db529b542090326d83a6fa0045a95dbd3ecba5bf2f7bb76a4')}
REMAINING={k:0 for k in ('data_custodian','worker','model','tokenizer','native_corpus','native_queries','NLI','gold_join','scorer_EVALUATE','scorer_BIND','train','calibration','confirmation','paid_API','GPU','retry','replacement')}
CUMULATIVE={'corpus_attempts':None,'completed_corpus_batches':None,'verified_corpus_attempts_lower_bound':36,'verified_completed_corpus_batches_lower_bound':34,'bounded_native_process_attempts':41,'legacy_native_qualification_process_attempts':6,'historical_E37_model_corpus_tail':'UNKNOWN_PERMANENTLY','benchmark_HTTP_successes':906,'benchmark_HTTP_failures':2,'current_official_HTTP_successes':3,'current_official_HTTP_failures':0}
NEXT={'status':'PROPOSED_NOT_EXECUTED','direction':'Preserve native104. Do not retry or replace E41. Use the separately completed, independently verified official structural hypothesis-key catalog (canonical keys SHA256549721f44dfd696ae79c2df9b450417388e2c10bc85e60e912b3abcb94ff4762) before selecting any future hypothesis IDs; do not repeat the completed inventory or reuse the invalid literal nda-1..nda-17 assumption. The completed metadata-only catalog cannot reopen E41. Any next measured epoch requires a new licensed document-disjoint frozen policy, context/reader/source/scorer gates, real asset admission and scoped CPU2/time allowance. Retained E41 implementation fixtures are source engineering only.','confirmation':'No confirmation identities used. Preserve old325DEV/74unused/24protected and all previously exposed DEV. E41 provisional reservations were unadmitted and not text/gold exposed.','budget_and_publisher':'Zero paid API/GPU. No publisher resubmission/contact without meaningful independent accepted improvement plus verified protocol/eligibility. No ClaimBench pilot until full data/scorer/license/access verified.'}

def exact_ref(root,row):
 c.require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'} and c.same_fact(c.ref(root,row['path']),row),'Exact public metadata ref required')
 c.require(any(row['path'].startswith(p+'/') for p in c.ROOTS),'Evidence must be within current public roots')
 return row

def facts(value):
 c.require(value.get('status')==STATUS and value.get('epoch')==41 and value.get('kind')==KIND,'Blocked E41 fact identity')
 for k,v in FLAGS.items():c.require(c.same_fact(value.get(k),v),'Forbidden result claim: '+k)
 c.require(value.get('metrics') is None and value.get('benchmark_accuracy') is None and value.get('experiment_executed') is False and value.get('evaluation_executed') is False and value.get('dev_passed') is False,'No scientific result allowed')
 c.require(value.get('used_confirmation_identities')==[] and c.same_fact(value.get('phase_remaining'),REMAINING) and c.same_fact(value.get('cumulative_execution'),CUMULATIVE),'All slots closed; history/UNKNOWN retained')

def verify_failure(f,p,r,x):
 c.require(f.get('checks_passed') is True and f.get('data_admission_passed') is False and f.get('candidate_execution_qualified') is False and f.get('metrics') is None,'Independent failed admission required')
 c.require(p.get('checks_passed') is True and p.get('physical_closure_passed') is True and p.get('actual_materializer_calls')==1 and p.get('actual_materializer_status')=='DATA_ADMISSION_FAILED','Known stopped custodian closure required')
 c.require(r.get('status')=='DATA_ADMISSION_FAILED' and r.get('errors',[{}])[0].get('code')=='EXACT_GLOBAL_HYPOTHESIS_KEYSET','Exact guarded schema blocker required')
 c.require(x.get('child_reaped') is True and x.get('automatic_retry') is False and x.get('signals')==[] and type(x.get('wall_seconds')) is float and x['wall_seconds']==0.6887229919666424,'Exact once-process closure/timing required')
 for k in ('new_selected_document_decodes','new_selected_hypothesis_decodes','selected_raw_choice_tokens_copied','semantic_gold_values_decoded','model_tokenizer_native_calls','actual_NLI_readouts','derived_forecasts','semantic_gold_join_calls','scorer_EVALUATE_calls','scorer_BIND_calls','feature_or_vault_or_selected_identity_outputs'):
  c.require(c.same_fact(f['actual_counts'].get(k),0),'Known preselected guard boundary changed: '+k)
 c.require(c.same_fact(f['actual_counts'].get('root_custodian_calls'),1) and c.same_fact(f['actual_counts'].get('already_exposed_Legal96_input_state_decodes'),96),'Exact priorDEV/custodian counts')


def setup(project,kit):
 root,kit=map(c.directory,(project,kit));c.require(root==c.WORK_SCOPE_DIR/'project','Exact projected root');c.live_owner(root.parent)
 c.require(c.sha(c.content(kit/'CHECKPOINT_MANIFEST.json'))==c.BASE_CP_SHA256,'Exact inherited CP')
 oldcp=c.parse(kit/'CHECKPOINT_MANIFEST.json');c.check_inherited_checkpoint(oldcp);c.check_history(root,oldcp)
 inputs=c.parse(root/INPUTS)
 c.require(set(inputs)=={'schema_version','epoch','kind','status','source_checkpoint','publication_parent','publication_parent_trees','publication_stage_path','evidence','source_only_reviews','key_catalog_review','retire_unadmitted_proposals'},'Exact blocked input schema')
 c.require(inputs['schema_version']==1 and inputs['epoch']==41 and inputs['kind']==KIND and inputs['status']==STATUS and inputs['source_checkpoint']==c.BASE_COMMIT and inputs['publication_parent']==PARENT and inputs['publication_parent_trees']==TREES and inputs['publication_stage_path']==str(root.parent/'stage-final') and inputs['retire_unadmitted_proposals'] is True,'Exact blocked scope/parent')
 c.require(set(inputs['evidence'])==set(PINNED),'Only pinned safe evidence roles')
 docs={}
 for role,(size,digest) in PINNED.items():
  row=exact_ref(root,inputs['evidence'][role]);c.require((row['bytes'],row['sha256'])==(size,digest),'Pinned observed evidence mismatch: '+role);docs[role]=c.parse(root/row['path'])
 verify_failure(docs['admission_failure'],docs['physical_closure'],docs['materialization_report'],docs['materialization_result'])
 pr=docs['planning_readback'];c.require(pr.get('commit')==PARENT and all(pr.get(k)==v for k,v in TREES.items()) and pr.get('checks_passed') is True,'Actual planning readback')
 official=docs['official_refresh_review'];c.require(official.get('checks_passed') is True and official.get('public_whitelist_approved') is True and official.get('actual_source_refresh',{}).get('cumulative_official_HTTP_successes')==906 and official['actual_source_refresh'].get('successes')==3 and official.get('official_goal_met') is False,'Actual official refresh only')
 c.require(isinstance(inputs['source_only_reviews'],list),'Source-only review list required')
 for row in inputs['source_only_reviews']:
  exact_ref(root,row);review=c.parse(root/row['path']);c.require(review.get('checks_passed') is True,'Independent source-only review required')
 if inputs['key_catalog_review'] is not None:
  exact_ref(root,inputs['key_catalog_review']);review=c.parse(root/inputs['key_catalog_review']['path'])
  c.require(review.get('checks_passed') is True and review.get('metadata_key_catalog_only') is True and c.same_fact(review.get('actual_catalog_calls'),1) and c.same_fact(review.get('hypothesis_document_choice_values_read'),0) and review.get('materializer_retry') is False,'Separately approved metadata-only catalog proof');docs['key_catalog_review']=review
 return root,kit,inputs,docs,oldcp

def put(root,name,value):
 body=c.encoded(value,pretty=True);c.public_text(name,body);c.write(root/name,body);return c.ref(root,name)

def assemble_facts(inputs,docs):
 f=docs['admission_failure'];r=docs['materialization_report'];x=docs['materialization_result']
 return dict(schema_version=1,epoch=41,kind=KIND,status=STATUS,phase='PRE_DATA_ADMISSION',source_checkpoint=c.BASE_COMMIT,publication_parent=PARENT,source_admission_executed=False,scientific_SOURCE_commit=None,source_plan=None,experiment_executed=False,evaluation_executed=False,scorer_EVALUATE_calls=0,scorer_BIND_calls=0,data_admission_passed=False,dev_passed=False,metrics=None,benchmark_accuracy=None,all_quality_gates='NOT_EVALUATED',used_confirmation_identities=[],all_slots_closed=True,phase_remaining=copy.deepcopy(REMAINING),actual_execution={'counts':copy.deepcopy(f['actual_counts']),'actual_native_corpus_batches':0,'actual_native_queries':0,'actual_model_tokenizer_calls':0,'actual_NLI_readouts':0,'derived_forecasts':0,'worker_attempts':0,'gold_join_calls':0,'scorer_calls':0,'paid_API_GPU_calls':0,'custodian_function_calls':1,'custodian_status':'FAILED_BEFORE_SELECTED_INPUTS','physical_child_closed':True,'whole_parent_child_seconds':x['wall_seconds'],'CPU_affinity':[0,1],'CPU_threads_configured':2,'peak_RSS_bytes':None,'peak_RSS_status':'NOT_CAPTURED','latency_p50':None,'latency_p95':None,'latency_status':'NOT_RUN_NO_SCIENTIFIC_OPERATIONS'},cumulative_execution=copy.deepcopy(CUMULATIVE),blocker={'code':'EXACT_GLOBAL_HYPOTHESIS_KEYSET','actual_key_names':'UNKNOWN_NOT_RETAINED','actual_key_count':None,'observation_scope':'UNKNOWN_NOT_RETAINED and null count describe ONLY the original stopped materializer report. The separately authorized later metadata-only inventory established17 official keys; its independent key_catalog_step/report is separate and cannot reopen E41.','assumption':'Literal expected nda-1..nda-17 catalog had no official schema proof. Synthetic guard fixtures were not source compatibility evidence.','retry_replacement_authorized':False},evidence=copy.deepcopy(inputs['evidence']),source_only_reviews=copy.deepcopy(inputs['source_only_reviews']),key_catalog_review=copy.deepcopy(inputs['key_catalog_review']),key_catalog_step={'status':'COMPLETED_METADATA_ONLY' if inputs['key_catalog_review'] is not None else 'NOT_RECORDED','independent_safe_metadata':copy.deepcopy(docs.get('key_catalog_review')),'cannot_reopen_E41':True},official_facts=copy.deepcopy(docs['official_refresh_review']['current_official_facts']),model_training_overlap_confirmation_eligibility='HOLD',planned_design={'status':'PENDING_NOT_EXECUTED','documents':4,'hypotheses':3,'provisional_pairs':12,'window_NLI_readouts':72,'derived_forecasts':36,'no_actual_source_or_model_admission':True},**FLAGS)

def results(args):
 root,kit,inputs,docs,oldcp=setup(args.project,args.kit)
 names=[E+n for n in ('RESULTS.json','REJECTION_LEDGER.json','LEARNINGS.json','USED_CONFIRMATION_IDENTITIES.json')]
 c.require(not any((root/n).exists() for n in names),'No partial/result overwrite or replay')
 result=assemble_facts(inputs,docs);facts(result)
 oldcont=c.parse(kit/'CONTINUATION.json');oldledger=c.parse(root/oldcont['rejection_ledger']['path']);ledger=copy.deepcopy(oldledger)
 ledger.setdefault('preparation_blocks',[]).append({'epoch':41,'status':STATUS,'type':'DATA_ADMISSION_BLOCKED_NOT_SCORED','reason':'EXACT_GLOBAL_HYPOTHESIS_KEYSET before selected inputs; no experiment/evaluator execution.','results':E+'RESULTS.json','metrics':None,'confirmation_ids':[]})
 ledger['epoch41_blocked_admission_record']={'measured_rejection':False,'repeat_or_replacement_allowed':False,'scientific_rejections_unchanged':True}
 ids={'schema_version':1,'epoch':41,'status':STATUS,'used_confirmation_identities':[],'actual_measured_ids':[],'actual_new_text_or_gold_exposed_ids':[],'provisional_unadmitted_reservations_retired':docs['materialization_report']['selected_ids'],'reservation_semantics':'Design identifiers only, not validated actual pairs; conservatively unavailable for later fresh confirmation without claiming text/gold exposure.','old423_roles_325_DEV_74_unused_24_protected':'UNCHANGED','all_previous_exposed_DEV':'PRESERVED'}
 learn={'schema_version':1,'epoch':41,'status':STATUS,'finding':'The exact global-keyset guard failed closed before selected hypothesis/document/choice access. Expected literal nda-1..nda-17 was an unverified proposal assumption.','source_fixture_limit':'Pure synthetic fixtures demonstrate code behavior, not official archive schema or benchmark generalization.','metrics':None,'no_scientific_experiment_executed':True,'no_retry_replacement':True,'next_research_priority':copy.deepcopy(NEXT),'independent_failure':inputs['evidence']['admission_failure'],'separate_source_only_reviews':inputs['source_only_reviews'],'separate_key_catalog_review':inputs['key_catalog_review']}
 for name,value in zip(names,(result,ledger,learn,ids)):put(root,name,value)
 return {n:c.ref(root,n) for n in names}

def validate_outputs(root,inputs):
 result=c.parse(root/(E+'RESULTS.json'));facts(result)
 c.require(c.same_fact(result['evidence'],inputs['evidence']) and c.same_fact(result['source_only_reviews'],inputs['source_only_reviews']) and c.same_fact(result['key_catalog_review'],inputs['key_catalog_review']),'Evidence projection changed')
 ids=c.parse(root/(E+'USED_CONFIRMATION_IDENTITIES.json'));c.require(ids['used_confirmation_identities']==[] and ids['actual_measured_ids']==[] and ids['actual_new_text_or_gold_exposed_ids']==[],'No consumed new data/confirmation identity')
 return result

def manifest(args):
 root,kit,inputs,docs,oldcp=setup(args.project,args.kit);result=validate_outputs(root,inputs);c.require(c.same_fact(result,assemble_facts(inputs,docs)),'Exact derived safe-metadata result projection')
 c.require(not any((root/(E+n)).exists() for n in ('SOURCE_MANIFEST.json','EPOCH_MANIFEST.json')),'Manifest output exclusive')
 reportref=c.ref(root,c.relative(args.independent_report));exact_ref(root,reportref);report=c.parse(root/reportref['path'])
 required={'checks_passed':True,'blocked_checkpoint_publication_allowed':True,'data_admission_passed':False,'experiment_executed':False,'evaluation_executed':False,'no_raw_third_party_text_or_private_gold_in_public_files':True,'results':c.ref(root,E+'RESULTS.json'),'blocked_inputs':c.ref(root,INPUTS),'physical_closure':inputs['evidence']['physical_closure']}
 for key,value in required.items():c.require(c.same_fact(report.get(key),value),'Independent blocked publication report mismatch: '+key)
 current=c.walk_current(root);rows=[{'path':p,'bytes':len(b),'sha256':c.sha(b)} for p,b in sorted(current.items())]
 source=put(root,E+'SOURCE_MANIFEST.json',{'schema_version':1,'epoch':41,'kind':KIND,'status':STATUS,'purpose':'Public source/artifact inventory for admission-blocked checkpoint; no scientific SOURCE commit or frozen measurement plan.','files':rows})
 m=copy.deepcopy(result);m.update(results=c.ref(root,E+'RESULTS.json'),blocked_inputs=c.ref(root,INPUTS),rejection_ledger=c.ref(root,E+'REJECTION_LEDGER.json'),learnings=c.ref(root,E+'LEARNINGS.json'),used_identities=c.ref(root,E+'USED_CONFIRMATION_IDENTITIES.json'),source_manifest=source,independent_report=reportref,files=rows+[source],no_project_writes_after_manifest=True,goal_verified=False)
 return put(root,E+'EPOCH_MANIFEST.json',m)

def sealed(root):
 m=c.parse(root/(E+'EPOCH_MANIFEST.json'));facts(m);result=c.parse(root/(E+'RESULTS.json'));c.require(all(c.same_fact(m.get(k),v) for k,v in result.items()),'Every result field retained in manifest');current=c.walk_current(root)
 refs={p:{'path':p,'bytes':len(b),'sha256':c.sha(b)} for p,b in current.items()}
 c.require({r['path']:r for r in m['files']}=={p:r for p,r in refs.items() if p!=E+'EPOCH_MANIFEST.json'},'No project writes after manifest')
 s=c.parse(root/m['source_manifest']['path']);c.require({r['path']:r for r in s['files']}=={p:r for p,r in refs.items() if p not in {E+'SOURCE_MANIFEST.json',E+'EPOCH_MANIFEST.json'}},'Exact nonrecursive source inventory')
 return m,current

def controls(args):
 root,kit,inputs,docs,oldcp=setup(args.project,args.kit);m,current=sealed(root)
 prior=c.directory(args.priorcontrols);out=c.new_output(args.out,(root,kit,prior));c.require(prior==root.parent/'controls-lease' and out==root.parent/'controls-final','Exact outside control paths')
 oldcont=c.parse(prior/'CONTINUATION.json');oldactive=c.parse(prior/'ACTIVE_RUN.json');c.require(c.content(prior/'CHECKPOINT_MANIFEST.json')==c.content(kit/'CHECKPOINT_MANIFEST.json'),'Planning CP unchanged')
 active=copy.deepcopy(oldactive);active.update(state='EPOCH41_BLOCKED_PRE_DATA_ADMISSION_CLOSED',work_active=False,experiments_active=False,checkpoint_parent=PARENT,all_slots_closed=True,phase_remaining=copy.deepcopy(REMAINING),instruction='E41 admission blocked; no model/native/scorer/retry/replacement. Guardian held until independently verified FINAL CAS/readback then root release.')
 for k in ('native_allowed','conditional_train_allowed','conditional_dev_allowed','conditional_calibration_allowed','conditional_engineering_allowed','confirmation_allowed','conditional_confirmation_allowed'):active[k]=0
 cp=copy.deepcopy(oldcp);rows=c.cp_rows(cp)
 for p,b in current.items():c.require(p not in rows,'New-root/historical collision');rows[p]={'path':p,'bytes':len(b),'sha256':c.sha(b)}
 cp['project_files']=[rows[p] for p in sorted(rows)];cp['epoch41_blocked_checkpoint']={'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'status':STATUS,'scientific_SOURCE_executed':False};cpbody=c.encoded(cp,pretty=True)
 cont=copy.deepcopy(oldcont);cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['checkpoint_manifest_sha256']=c.sha(cpbody);cont['prior_published_base_commit']=PARENT
 cont.setdefault('epochs',[]).append({'epoch':41,'status':STATUS,'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'experiment_executed':False})
 cont.setdefault('execution_observed',{})['epoch41_blocked_predata']={'actual_execution':m['actual_execution'],'cumulative_execution':m['cumulative_execution']}
 cont['rejection_ledger']=m['rejection_ledger'];cont['latest_learning']=m['learnings'];cont['next_research_priority']=copy.deepcopy(NEXT)
 cont['benchmark_refresh']={'epoch':41,'independent_review':inputs['evidence']['official_refresh_review'],'official_HTTP_successes':3,'official_HTTP_failures':0,'cumulative_successes':906,'cumulative_failures':2,'official_goal_verified':False}
 cont['epoch41_final']={'status':STATUS,'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'all_slots_closed':True,'no_scientific_SOURCE_or_evaluator':True}
 c.check_transport(root,c.parse(kit/'CONTINUATION.json'),cont,rows,kit=kit)
 out.mkdir(mode=0o700)
 for name,value in [('ACTIVE_RUN.json',active),('CONTINUATION.json',cont),('CHECKPOINT_MANIFEST.json',cp)]:c.write(out/name,c.encoded(value,pretty=True))
 return {'controls':str(out),'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'new_CP_rows':len(rows)}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['results','manifest','controls'])
 for name in ('project','kit'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--independent-report');p.add_argument('--priorcontrols',type=Path);p.add_argument('--out',type=Path)
 a=p.parse_args();print(json.dumps(globals()[a.mode](a),sort_keys=True))
