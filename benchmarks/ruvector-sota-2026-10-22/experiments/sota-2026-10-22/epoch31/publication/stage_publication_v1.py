"""E31 SOURCE/FINAL local publication guards; no model/labels/external calls."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,re
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from phase_receipts_v1 import same_fact,derive_actual,phase_evidence,phase_completed,aggregate_actual,cumulative_counts,checked_ref,require_final_physical_closure
BASE_GIT_LEAVES=4250
BASE_SCOPE_TREE='6fff90294776b2313af0c8342c67516ebede3ae2'
HISTORICAL_MAIN_OBSERVATION='46d816ddc4c2a8a06cd3613534a79b1d557d858b'
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh','exposed_development_sets'}
FINAL_MUTABLE=MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger'}

def leaf(path,body):
 return {'path':path,'mode':'100644','type':'blob','sha':gitsha(body),'size':len(body)}

def tuple_map(document):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Canonical Git file map required')
 require(document.get('scope',SCOPE).rstrip('/')==SCOPE.rstrip('/'),'Wrong Git scope')
 answer={}
 for item in document['files']:
  require(isinstance(item,dict) and set(TUPLE_KEYS)<=set(item),'Incomplete Git tuple')
  row={k:item[k] for k in TUPLE_KEYS};path=row['path']
  require(isinstance(path,str),'Git path must be text')
  if path.startswith(SCOPE):path=path[len(SCOPE):]
  row['path']=relative(path)
  require(row['mode']=='100644' and row['type']=='blob' and re.fullmatch('[0-9a-f]{40}',row['sha'] or '') and type(row['size']) is int and row['size']>=0 and path not in answer,'Invalid/duplicate Git tuple')
  answer[path]=row
 require(CONTROLS<=set(answer),'Original control tuples required')
 return answer

def scope_tree_sha(rows):
 root={}
 for path,row in rows.items():
  node=root;parts=relative(path).split('/')
  for part in parts[:-1]:
   require(part not in node or isinstance(node[part],dict),'Git file/directory collision')
   node=node.setdefault(part,{})
  require(parts[-1] not in node,'Git file/directory collision');node[parts[-1]]=row['sha']
 def digest(node):
  entries=[]
  for name,value in node.items():
   is_dir=isinstance(value,dict);identity=digest(value) if is_dir else value
   entries.append((name.encode()+ (b'/' if is_dir else b''),(b'40000' if is_dir else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(identity)))
  body=b''.join(value for _,value in sorted(entries))
  return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
 return digest(root)

def verify_baseline(kit,index):
 require(index.get('source_commit',BASE_COMMIT)==BASE_COMMIT,'Wrong source checkpoint')
 rows=tuple_map(index)
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original4250 Git identity required')
 for path,row in rows.items():require(leaf(path,content(kit/path))==row,'Historical Git byte drift: '+path)
 return rows

def checked_review(document,current):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Explicit exhaustive review required')
 rows={}
 for row in document['files']:
  require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Canonical review ref required')
  path=relative(row['path']);require(path not in rows,'Duplicate review path');rows[path]=row
 require(set(rows)==set(current),'Review must cover all and only four-root current files')
 for path,body in current.items():require(rows[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Review byte drift: '+path)

def checkpoint_extension(old,new,current):
 before,after=cp_rows(old),cp_rows(new)
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch31_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
 require(set(after)==set(before)|set(current),'Checkpoint must cover exactly original and current public files')
 for path,row in before.items():require(after.get(path)==row,'Historical checkpoint row changed: '+path)
 for path,body in current.items():require(after[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Current checkpoint byte mismatch: '+path)
 return before,after

def controls_at(path,fallback_kit=None):
 directory(path);names={p.name for p in path.iterdir()}
 require(names<=CONTROLS|{'hashes.json'} and {'CONTINUATION.json','ACTIVE_RUN.json'}<=names,'Unexpected control files')
 out={}
 for name in sorted(CONTROLS):
  source=path/name
  if not source.exists():require(name=='CHECKPOINT_MANIFEST.json' and fallback_kit is not None,'Missing control file');source=fallback_kit/name
  out[name]=content(source);public_text(name,out[name])
 return out

def preserve_history(before,after,mutable):
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch31_') for k in after),'Historical continuation metadata removed/new key outside E31')
 for key,value in before.items():
  if key not in mutable:require(after[key]==value,'Historical continuation field changed: '+key)
 for key in ('used_confirmation_sets','champion','epoch27_data_roles'):
  if key in before:require(after[key]==before[key],'Protected source role/champion changed: '+key)
 if 'exposed_development_sets' in mutable:
  old,new=before.get('exposed_development_sets'),after.get('exposed_development_sets')
  if isinstance(old,list):require(isinstance(new,list) and new[:len(old)]==old,'Historical exposed DEV records changed')
  elif isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()),'Historical exposed DEV map changed')
 if 'cumulative_budget_ledger' in mutable:
  old,new=before.get('cumulative_budget_ledger'),after.get('cumulative_budget_ledger')
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch31_') for k in new),'Historical budget ledger changed')

def transport_groups(changed):
 entries=[];blobs=[];groups=[];large_identities={}
 for path,body in sorted(changed.items()):
  text=public_text(path,body);entry={'path':SCOPE+path,'mode':'100644','type':'blob'}
  if len(body)>LARGE_FILE_BYTES:
   payload={'content':text,'encoding':'utf-8'};require(len(encoded(payload))<MAX_BLOB_JSON,'Blob JSON strict cap exceeded')
   identity=gitsha(body)
   if identity in large_identities:require(large_identities[identity]==body,'Refuse unequal large payloads with the same Git blob SHA')
   else:large_identities[identity]=body;blobs.append((path,body,payload))
   entry['sha']=identity
  else:entry['content']=text
  require(len(encoded({'tree_elements':[entry]}))<MAX_TREE_JSON,'Single tree entry strict cap exceeded');entries.append(entry)
 batch=[]
 for entry in entries:
  if len(encoded({'tree_elements':batch+[entry]}))>=MAX_TREE_JSON:require(batch,'Cannot fit tree entry');groups.append(batch);batch=[]
  batch.append(entry)
 if batch:groups.append(batch)
 return blobs,groups

def verify_flags(value):
 for k,v in FLAGS.items():require(same_fact(value.get(k),v),'Forbidden acceptance/promotion/rank: '+k)

def data_role_record():
 return {**copy.deepcopy(ROLES),'hypotheses':HYPOTHESES,'used_confirmation_identities':[],
  'historical_training':{'epoch':30,'document_ids':HISTORICAL_TRAIN_IDS},'retired_document_ids':ROLES['dev'],
  'partition_after_projection':{'exposed':301,'unreserved':98,'reserved_confirmation':24,'total':423},
  'all8_current_DEV_document_ids_permanently_exposed':True}

def retirement_record():
 return {'epoch':31,'kind':'FROZEN_ARCHIVED_ADAPTATION_DEV_ROLES','document_ids':ROLES['dev'],'data_roles':copy.deepcopy(ROLES),
  'hypotheses':HYPOTHESES,'all8_document_ids_permanently_retired':True,'confirmation_consumed':False}

def archive_ready(root,oldrows,seal):
 require(isinstance(seal,dict) and set(seal)==ARCHIVED_SEAL_KEYS and same_fact(seal.get('schema_version'),1) and same_fact(seal.get('epoch'),31)
  and seal.get('kind')==KIND and seal.get('status')=='ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED' and seal.get('source_checkpoint')==BASE_COMMIT,'Wrong exact archived MODEL seal')
 require(same_fact(seal['data_roles'],ROLES) and seal['hypotheses']==HYPOTHESES and same_fact(seal['historical_training_epoch'],30) and seal['historical_training_document_ids']==HISTORICAL_TRAIN_IDS,'Archived/current role attribution changed')
 for key,path in ARCHIVED_SOURCE_PATHS.items():checked_ref(root,seal[key],oldrows,path)
 require(seal['parameter_artifact']['bytes']==5950520 and seal['parameter_artifact']['sha256']=='46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f','Only actual BASE-published E30 artifact allowed')
 report=parse(root/seal['independent_training_report']['path']);require(report.get('epoch')==30 and report.get('train_integrity_passed')is True,'Historical archived TRAIN integrity missing')
 mapping={'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution','plan':'original_source_plan','freeze':'original_source_freeze'}
 require(all(report.get('evidence',{}).get(k)==seal[v] for k,v in mapping.items()),'Historical TRAIN report/archive lineage differs')
 require(parse(root/seal['train_execution']['path']).get('owned_live_processes_closed')is True,'Historical TRAIN closure changed')
 return seal

def check_plan(root,cont,rows,current,phase,oldrows):
 frozen=cont.get('epoch31_frozen_study');require(isinstance(frozen,dict) and set(frozen)=={'plan','source_freeze'},'Exact current source refs required')
 checked_ref(root,frozen['plan'],rows,PLAN_PATH);checked_ref(root,frozen['source_freeze'],rows,FREEZE_PATH)
 plan,freeze=parse(root/PLAN_PATH),parse(root/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==31 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Wrong current source epoch/kind/BASE')
 require(same_fact(plan.get('data_roles'),ROLES) and plan.get('hypotheses')==HYPOTHESES and plan.get('source_freeze')==frozen['source_freeze'] and plan.get('actual_project')==str(root),'Wrong frozen roles/hypotheses/root/freeze')
 expected={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
 require(all(same_fact(plan.get('limits',{}).get(k),v) for k,v in expected.items()),'Fixed one-phase CPU/spend limits differ')
 require(plan.get('dev_inputs_path')in rows and rows[plan['dev_inputs_path']]['sha256']==plan.get('dev_inputs_sha256'),'Frozen DEV input identity missing')
 checked_ref(root,plan.get('archived_model_seal'),rows,ARCHIVED_SEAL_PATH)
 require(cont.get('epoch31_archived_model_seal')==plan['archived_model_seal'],'Continuation archive-seal projection differs')
 archive_ready(root,oldrows,parse(root/ARCHIVED_SEAL_PATH))
 pins=plan.get('pins');require(isinstance(pins,list) and pins,'Current source pins required');indexed={}
 for row in pins:require(row['path']not in indexed,'Duplicate current source pin');checked_ref(root,row);indexed[row['path']]=row
 entries=freeze.get('entries');require(isinstance(entries,list) and entries,'Source-freeze entries required');seen=set()
 for row in entries:
  path=checked_ref(root,row,rows);require(path not in seen and path in current and path not in {PLAN_PATH,FREEZE_PATH} and indexed.get(path)==row,'Invalid/unpinned source-freeze member');seen.add(path)
 if phase=='source':require(seen==set(current)-{PLAN_PATH,FREEZE_PATH},'Current source freeze omits files')
 require(indexed.get(FREEZE_PATH)==frozen['source_freeze'] and indexed.get(ARCHIVED_SEAL_PATH)==plan['archived_model_seal'],'Current freeze/archive seal unpinned')
 return plan

def check_phase_main(value,expected):
 require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{40}',expected) and value.get('main')==expected,'Fresh point-in-time main observation differs; never mutate main')

def check_readback(value,phase,parent,trees):
 require(value.get('commit')==parent and(value.get('verified')is True or value.get('verified_actual_full_tree')is True or(value.get('checks_passed')is True and value.get('verified_actual_remote_readback')is True)),'Actual independent parent readback required')
 require(all(value.get(k)==v for k,v in zip(('root','bench','scope'),trees)),'Actual parent trees differ')
 parents=[value[k]for k in ('parent','sole_parent')if k in value];require(parents and all(v==parents[0]for v in parents),'Missing/conflicting actual sole parent')
 require(parent!=BASE_COMMIT,'SOURCE/FINAL must extend scoped planning/source commit')

def checked_controls(args,root,kit,current):
 phase=args.phase;bodies=controls_at(args.controls);prior=controls_at(args.priorcontrols,kit)
 oldcp,oldcont=parse(kit/'CHECKPOINT_MANIFEST.json'),parse(kit/'CONTINUATION.json')
 require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256==oldcont['checkpoint_manifest_sha256'],'Actual BASE checkpoint hash differs');check_inherited_checkpoint(oldcp);oldrows=check_history(root,oldcp)
 cp,cont,active=(loads(bodies[n])for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'));pcp,pcont,pactive=(loads(prior[n])for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 _,rows=checkpoint_extension(oldcp,cp,current);require(pcont['checkpoint_manifest_sha256']==sha(prior['CHECKPOINT_MANIFEST.json']),'Prior checkpoint hash differs')
 mutable=FINAL_MUTABLE if phase=='final'else MUTABLE;preserve_history(oldcont,cont,mutable);preserve_history(pcont,cont,mutable)
 require(cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json']) and cont['active_run']==dict(active,path='ACTIVE_RUN.json') and cont['prior_published_base_commit']==args.parent and cont.get('goal_met')is False and cont.get('official_rank')is None,'Control/hash/status/parent differs')
 owner=active.get('physical_owner',{});require(active.get('run_id')==OWNER_RUN_ID and(owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==OWNER_PIN and owner.get('expires_unix')==OWNER_EXPIRES_UNIX,'Wrong actual E31 guardian')
 require(type(active.get('native_allowed'))is int and active['native_allowed']==0 and active.get('experiments_active')is False and active.get('checkpoint_parent')==args.parent and active.get('OS_lock_held')is True,'Immediate native execution must remain closed')
 for key in ('confirmation_allowed','conditional_confirmation_allowed','conditional_train_allowed'):require(type(active.get(key))is int and active[key]==0,'TRAIN/CONF allowances must remain zero')
 if phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH31_PLANNING_LEASE' and active.get('state')=='EPOCH31_SOURCE_FROZEN_DEV_PENDING_ADMISSION' and active.get('work_active')is True and type(active.get('conditional_dev_allowed'))is int and active['conditional_dev_allowed']==1,'SOURCE conditional DEV gate differs')
  require(not any(path.startswith(E+'runs/') or path in {E+'RESULTS.json',E+'EPOCH_MANIFEST.json',E+'SOURCE_ADMISSION.json',E+'DEV_ATTEMPT_RESERVATION.json',*DISPATCH_PATHS.values()}for path in current),'Premeasurement SOURCE contains execution/admission/results')
 else:
  require(set(cp)==set(pcp) and all(cp[k]==v for k,v in pcp.items()if k!='project_files') and all(rows.get(k)==v for k,v in cp_rows(pcp).items()),'Previously published checkpoint/source changed')
  require(cont.get('epoch31_frozen_study')==pcont.get('epoch31_frozen_study'),'Published plan/freeze changed')
  require(pactive.get('state')=='EPOCH31_SOURCE_FROZEN_DEV_PENDING_ADMISSION' and active.get('state')=='EPOCH31_CLOSED' and active.get('work_active')is False and type(active.get('conditional_dev_allowed'))is int and active['conditional_dev_allowed']==0,'FINAL current phase closure differs')
 require(same_fact(cont.get('epoch31_planning'),pcont.get('epoch31_planning')) and same_fact(cont.get('epoch31_data_roles'),data_role_record()),'Planning/frozen role history differs')
 require(same_fact(cont.get('exposed_development_sets'),oldcont.get('exposed_development_sets',[])+[retirement_record()]),'Retire exactly8 frozen DEV IDs once; preserve legacy strings/retirements')
 plan=check_plan(root,cont,rows,current,phase,oldrows)
 if phase=='source':require(plan.get('publication_parent')==args.parent and plan.get('publication_parent_trees')==dict(zip(('root','bench','scope'),(args.expected_root,args.expected_bench,args.expected_scope))),'Actual SOURCE parent/trees must be frozen in master plan')
 else:check_final(root,rows,cont,pcont,plan)
 return bodies,prior,oldcp,cp,cont,plan,check_transport(root,oldcont,cont,rows,kit=kit)

def check_final(root,rows,cont,pcont,plan):
 m=parse(root/(E+'EPOCH_MANIFEST.json'));require(m.get('epoch')==31 and m.get('kind')==KIND and m.get('status')in FINAL_STATUSES,'Wrong current diagnostic outcome');verify_flags(m)
 require(m.get('confirmation')==[] and m.get('all_slots_closed')is True and type(m.get('diagnostic_qualified'))is bool and m.get('archived_training_integrity_passed')is True,'Current/historical/confirmation verdict invalid')
 require(same_fact(m.get('phase_remaining'),{'train':0,'dev':0,'confirmation':0}),'Final phase_remaining must be the exact typed-zero current allowance map')
 for key,path in [('plan',PLAN_PATH),('source_freeze',FREEZE_PATH),('results',E+'RESULTS.json'),('archived_model_seal',ARCHIVED_SEAL_PATH)]:checked_ref(root,m.get(key),rows,path)
 result=parse(root/m['results']['path']);verify_flags(result)
 for key in ('status','diagnostic_qualified','archived_training_integrity_passed','actual_execution'):require(same_fact(result.get(key),m[key]),'Manifest/result differs: '+key)
 report_path=checked_ref(root,m.get('independent_report'),rows);require(report_path.startswith(P+'audit/epoch31/'),'Current independent report required')
 report=parse(root/report_path);require(report.get('epoch')==31 and report.get('kind')==KIND and report.get('checks_passed')is True and report.get('diagnostic_qualified')is m['diagnostic_qualified'] and report.get('archived_training_integrity_passed')is True,'Independent current binding/verdict differs')
 evidence=phase_evidence(root,'dev',m['plan'],rows);actual=aggregate_actual(evidence);require_final_physical_closure(actual);require(same_fact(m['actual_execution'],actual),'Current actual effort/resources differ')
 seal=parse(root/ARCHIVED_SEAL_PATH)
 refs={'raw':evidence['raw'],'execution':evidence['execution'],'results':m['results'],'archived_model_seal':m['archived_model_seal'],'parameter_artifact':seal['parameter_artifact']}
 require(all(same_fact(report.get('evidence',{}).get(k),v)for k,v in refs.items()),'Independent current evidence references differ')
 if actual['worker_attempts']:
  ap=E+'SOURCE_ADMISSION.json';ar=ref(root,ap);checked_ref(root,ar,rows,ap);admission=parse(root/ap)
  require(admission.get('epoch')==31 and admission.get('kind')==KIND and admission.get('verified_actual_remote_readback')is True and admission.get('published_source_commit')==cont['prior_published_base_commit'],'Actual SOURCE-before-DEV admission missing')
  require(admission.get('plan_sha256')==m['plan']['sha256'] and admission.get('source_freeze_sha256')==m['source_freeze']['sha256'] and admission.get('archived_model_seal')==m['archived_model_seal'] and admission.get('parameter_artifact')==seal['parameter_artifact'],'Actual admitted archive/source identities differ')
  require(admission.get('owner_pid')==OWNER_PIN[0] and admission.get('owner_startticks')==OWNER_PIN[1],'Actual current admission guardian differs')
 if m['diagnostic_qualified']:require(phase_completed(evidence) and m['status']=='DEV_DIAGNOSTIC_QUALIFIED' and report.get('frozen_DEV_gates_passed')is True,'Positive diagnostic requires complete bounded96 and all frozen gates')
 else:require(m['status']=='REJECTED_DEV_DIAGNOSTIC','Rejected diagnostic status differs')
 before,new=pcont.get('execution_observed',{}),cont.get('execution_observed',{});counts=cumulative_counts(actual)
 require(before.get('epoch30_cumulative_corpus_attempts')==25 and before.get('epoch30_cumulative_completed_corpus_batches')==23 and before.get('epoch30_cumulative_bounded_native_process_attempts')==31,'Verified explicit prior25/23/31 differs')
 require(all(same_fact(new.get(k),v)for k,v in before.items()) and all(k in before or k.startswith('epoch31_')for k in new) and same_fact(new.get('epoch31_actual_execution'),actual),'Historical execution fields changed or current effort missing')
 for key,value in {'epoch31_cumulative_corpus_attempts':counts['corpus_attempts'],'epoch31_cumulative_completed_corpus_batches':counts['completed_corpus_batches'],'epoch31_cumulative_bounded_native_process_attempts':counts['bounded_native_process_attempts']}.items():require(same_fact(new.get(key),value),'Explicit current cumulative count differs: '+key)
 require(same_fact(m.get('cumulative_execution'),counts) and same_fact(result.get('cumulative_execution'),counts),'Manifest/result cumulative count differs')
 oldref=pcont['rejection_ledger'];checked_ref(root,oldref,rows);newref=cont['rejection_ledger'];checked_ref(root,newref,rows,E+'REJECTION_LEDGER.json');oldledger,ledger=parse(root/oldref['path']),parse(root/newref['path'])
 for key,value in oldledger.items():require(same_fact(ledger.get(key,[])[:len(value)],value)if key=='rejections'else same_fact(ledger.get(key),value),'Historical rejection metadata changed: '+key)
 require(all(k in oldledger or k.startswith('epoch31_')for k in ledger),'New rejection key outside current epoch')
 budget={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
 require(same_fact(ledger.get('epoch31_budget'),budget) and same_fact(ledger.get('epoch31_actual_execution'),actual) and same_fact(ledger.get('epoch31_cumulative_execution'),counts) and same_fact(cont.get('cumulative_budget_ledger',{}).get('epoch31_budget'),budget),'Current used/closed budget or effort projection differs')
 decision=ledger.get('epoch31_decision',{});verify_flags(decision)
 for key,value in {'status':m['status'],'diagnostic_qualified':m['diagnostic_qualified'],'archived_training_integrity_passed':True,'results':m['results']}.items():require(same_fact(decision.get(key),value),'Current rejection decision differs: '+key)
 if m['diagnostic_qualified']:require(ledger['rejections']==oldledger['rejections'] and ledger.get('epoch31_diagnostic_qualification',{}).get('results')==m['results'],'Positive diagnostic record missing')
 else:require(len(ledger['rejections'])==len(oldledger['rejections'])+1 and ledger['rejections'][-1].get('epoch')==31 and ledger['rejections'][-1].get('status')==m['status'] and ledger['rejections'][-1].get('results')==m['results'] and bool(ledger['rejections'][-1].get('reason')),'Exact current rejection/reason required')
 summary={**FLAGS,'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':m['results'],'status':m['status'],'diagnostic_qualified':m['diagnostic_qualified'],'archived_training_integrity_passed':True,'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
 require(same_fact(cont.get('epoch31_final'),summary),'Continuation final projection differs')
 epoch={**FLAGS,'epoch':31,'kind':KIND,'status':m['status'],'manifest':summary['manifest'],'results':m['results'],'diagnostic_qualified':m['diagnostic_qualified'],'archived_training_integrity_passed':True}
 require(same_fact(cont.get('epochs'),pcont.get('epochs',[])+[epoch]),'Append exactly one truthful current summary')

def prepare(args):
 root,kit,controls,priorcontrols=map(directory,(args.project,args.kit,args.controls,args.priorcontrols));live_owner(root.parent)
 output=new_output(args.out,(root,kit,controls,priorcontrols))
 for key in ('parent','expected_main','expected_root','expected_bench','expected_scope'):require(re.fullmatch('[0-9a-f]{40}',getattr(args,key) or ''),'Exact Git SHA required: '+key)
 proof_bytes=content(args.parent_readback);parent_proof=loads(proof_bytes);check_phase_main(parent_proof,args.expected_main);check_readback(parent_proof,args.phase,args.parent,(args.expected_root,args.expected_bench,args.expected_scope))
 map_bytes=content(args.source_filemap);baseline=verify_baseline(kit,loads(map_bytes));current=walk_current(root)
 review_bytes=content(args.reviewed_files);checked_review(loads(review_bytes),current)
 bodies,prior,oldcp,cp,cont,plan,transport=checked_controls(args,root,kit,current)
 require(plan.get('publication_stage_paths',{}).get(args.phase)==str(output),'Stage placement must match frozen master plan')
 if args.prior_expected:prior_bytes=content(args.prior_expected);before=tuple_map(loads(prior_bytes))
 else:
  require(args.phase=='source','MODEL/FINAL require exact actual prior full map');before=copy.deepcopy(baseline)
  for name,body in prior.items():before[name]=leaf(name,body)
  prior_bytes=encoded({'scope':SCOPE,'files':[before[k] for k in sorted(before)]})
 for name,body in prior.items():require(before.get(name)==leaf(name,body),'Prior control tuple differs: '+name)
 expected=copy.deepcopy(baseline)
 for path,body in {**current,**bodies}.items():require(path not in baseline or path in CONTROLS,'Historical Git overwrite refused');expected[path]=leaf(path,body)
 require(all(expected.get(k)==v for k,v in before.items() if k not in CONTROLS),'Previously published source/model tuple changed')
 check_transport(root,parse(kit/'CONTINUATION.json'),cont,cp_rows(cp),set(expected),kit=kit)
 changed={path:body for path,body in {**current,**bodies}.items() if before.get(path)!=expected[path]};require(CONTROLS<=set(changed),'Three control updates required')
 blobs,groups=transport_groups(changed)
 meta={'schema_version':1,'stage':args.phase,'prior_controls_name':args.priorcontrols.name,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'source_plan_sha256':sha(content(root/PLAN_PATH)),'publication_parent':args.parent,
  'CAS_guards':{'expected_main':args.expected_main,'expected_root_tree':args.expected_root,'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,'expected_branch_sha':args.parent,'force':False},
  'source_filemap_sha256':sha(map_bytes),'prior_expected_sha256':sha(prior_bytes),'reviewed_files_sha256':sha(review_bytes),'parent_readback_sha256':sha(proof_bytes),
  'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(before),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(cp_rows(cp)),'new_epoch31_public_files':len(current),'expected_Git_leaves':len(expected),
  'changed_files':[],'old_noncontrol_tuples_preserved':True,'old_CP_metadata_preserved':True,'frozen_source_tuples_preserved':True,'inherited_archive_transport_unchanged':transport,'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[]}
 output.mkdir(mode=0o700);(output/'transport').mkdir(mode=0o700)
 for path,body in sorted(changed.items()):meta['changed_files'].append({'path':path,'bytes':len(body),'sha256':sha(body),'git_blob_sha1':gitsha(body)})
 for i,(path,body,payload) in enumerate(blobs):
  name='transport/blob-%03d.json'%i;data=encoded(payload);write(output/name,data);meta['large_blob_requests'].append({'path':path,'file':name,'bytes':len(data),'sha256':sha(data),'expected_blob_sha1':gitsha(body),'must_verify_before_tree':True})
 for i,group in enumerate(groups):
  name='transport/tree-%03d.json'%i;data=encoded({'tree_elements':group});require(len(data)<MAX_TREE_JSON,'Strict serialized tree cap');write(output/name,data);meta['create_tree_groups'].append({'file':name,'bytes':len(data),'sha256':sha(data),'entries':len(group)})
 leaves=encoded({'schema_version':1,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'files':[expected[k] for k in sorted(expected)]});write(output/'expected-leaves.json',leaves)
 meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':sha(leaves),'count':len(expected)};write(output/'metadata.json',encoded(meta,pretty=True))
 return {k:meta[k] for k in ('stage','publication_parent','old_CP_rows','new_CP_rows','expected_Git_leaves','expected_leaves','Git_mutations')}

if __name__=='__main__':
 cli=argparse.ArgumentParser()
 for name in ('project','kit','controls','priorcontrols','source-filemap','reviewed-files','parent-readback','out'):cli.add_argument('--'+name,type=Path,required=True)
 cli.add_argument('--phase',choices=('source','final'),required=True);cli.add_argument('--prior-expected',type=Path)
 for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):cli.add_argument('--'+name,required=True)
 print(json.dumps(prepare(cli.parse_args()),sort_keys=True))
