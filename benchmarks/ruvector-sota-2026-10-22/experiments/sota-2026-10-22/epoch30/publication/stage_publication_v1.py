"""E30 SOURCE/MODEL/FINAL local staging; no model, labels or external calls."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,re
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from phase_receipts_v1 import same_fact,derive_actual,phase_evidence,phase_completed,aggregate_actual,cumulative_counts,checked_ref,require_final_physical_closure
from parameter_artifact_v1 import validate_artifact
BASE_GIT_LEAVES=4106
BASE_SCOPE_TREE='ec3705bcd83b5e659a27b0726bd6a0a33bff3e63'
SOURCE_PARENT='0928ca97b5a8942e6ad25fa7f4db70567e7848bc'
SOURCE_PARENT_SOLE_PARENT='228e3f25023f90e803283d0766e482e12930ce2f'
SOURCE_TREES=('a34c05f73c027f575a97db74510ab7f7c6bb1126','0c8639fb2f188ba365398618dd9f56210f7f6bc6','a59e44bee63de8a219918c000921bde5855f2e86')
MAIN_COMMIT='46d816ddc4c2a8a06cd3613534a79b1d557d858b'
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh','exposed_development_sets'}
FINAL_MUTABLE=MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger'}
FINAL_STATUSES={'TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED','DEV_DIAGNOSTIC_QUALIFIED','REJECTED_DEV_DIAGNOSTIC'}


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
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original4106 Git identity required')
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
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch30_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
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
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch30_') for k in after),'Historical continuation metadata removed/new key outside E29')
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
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch30_') for k in new),'Historical budget ledger changed')

def transport_groups(changed):
 entries=[];blobs=[];groups=[]
 for path,body in sorted(changed.items()):
  text=public_text(path,body);entry={'path':SCOPE+path,'mode':'100644','type':'blob'}
  if len(body)>LARGE_FILE_BYTES:
   payload={'content':text,'encoding':'utf-8'};require(len(encoded(payload))<MAX_BLOB_JSON,'Blob JSON strict cap exceeded')
   blobs.append((path,body,payload));entry['sha']=gitsha(body)
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
  'retired_document_ids':ROLES['train']+ROLES['dev'],
  'partition_after_projection':{'exposed':293,'unreserved':106,'reserved_confirmation':24,'total':423},
  'all16_document_ids_permanently_exposed_after_projection':True}

def retirement_record():
 return {'epoch':30,'kind':'FROZEN_TRAIN_DEV_PARAMETER_ADAPTATION_ROLES',
  'document_ids':ROLES['train']+ROLES['dev'],'data_roles':copy.deepcopy(ROLES),
  'hypotheses':HYPOTHESES,'all16_document_ids_permanently_retired':True,'confirmation_consumed':False}

def check_plan(root,cont,rows,current,phase):
 frozen=cont.get('epoch30_frozen_study');require(isinstance(frozen,dict) and set(frozen)=={'plan','source_freeze'},'Exact source references required')
 checked_ref(root,frozen['plan'],rows,PLAN_PATH);checked_ref(root,frozen['source_freeze'],rows,FREEZE_PATH)
 plan,freeze=parse(root/PLAN_PATH),parse(root/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==30 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Wrong source epoch/kind/checkpoint')
 require(same_fact(plan.get('data_roles'),ROLES) and plan.get('hypotheses')==HYPOTHESES and plan.get('source_freeze')==frozen['source_freeze'],'Frozen roles/hypotheses/freeze differ')
 expected={'owned_workers':2,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':1,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
 require(all(same_fact(plan.get('limits',{}).get(k),v) for k,v in expected.items()),'Fixed phase/CPU/spend limits differ')
 require(plan.get('actual_project')==str(root),'Wrong isolated project')
 for label in ('train','dev'):
  path=plan.get(label+'_inputs_path');require(path in rows and rows[path]['sha256']==plan.get(label+'_inputs_sha256'),'Frozen phase input identity missing')
 pins=plan.get('pins');require(isinstance(pins,list) and pins,'Source pins required');indexed={}
 for row in pins:
  require(row['path'] not in indexed,'Duplicate source pin');checked_ref(root,row);indexed[row['path']]=row
 entries=freeze.get('entries');require(isinstance(entries,list) and entries,'Source-freeze entries required');seen=set()
 for row in entries:
  path=checked_ref(root,row,rows);require(path not in seen and path in current and path not in {PLAN_PATH,FREEZE_PATH} and indexed.get(path)==row,'Invalid/unpinned source-freeze member');seen.add(path)
 if phase=='source':require(seen==set(current)-{PLAN_PATH,FREEZE_PATH},'Source freeze omits current files')
 require(indexed.get(FREEZE_PATH)==frozen['source_freeze'],'Source-freeze file itself unpinned')
 return plan

def validate_model_seal(root,plan,rows,seal):
 require(isinstance(seal,dict) and set(seal)==MODEL_SEAL_KEYS and seal['schema_version']==1 and seal['epoch']==30 and seal['kind']==KIND and seal['status']=='TRAINED_PARAMETER_ARTIFACT_SEALED' and seal['base_model_sha256']==BASE_MODEL['weights_sha256'],'Wrong exact MODEL seal')
 checked_ref(root,seal['source_plan'],rows,PLAN_PATH);checked_ref(root,seal['source_freeze'],rows,FREEZE_PATH)
 train=phase_evidence(root,'train',seal['source_plan'],rows,required=True)
 require(phase_completed(train) and train['raw']==seal['train_raw'] and train['execution']==seal['train_execution'] and train['raw_value'].get('status')=='COMPLETED_TRAIN_AWAITING_INDEPENDENT_MODEL_SEAL','MODEL requires completed closed accepted TRAIN identity')
 for k,v in plan['expected_operation_counters']['train'].items():require(same_fact(train['raw_value']['counters'].get(k),v),'TRAIN frozen operation count differs: '+k)
 checked_ref(root,seal['parameter_artifact'],rows,ARTIFACT_PATH)
 summary=validate_artifact(content(root/ARTIFACT_PATH),seal['source_plan']['sha256'],plan['train_inputs_sha256'],plan['training_algorithm'])
 for k in ('original_head_preserved','initial_LoRA_B_bit_zero','all_frozen_pretrained_bit_unchanged','all12_trainable_tensors_changed','all4_effective_lora_mechanisms_nonzero'):require(summary[k] is True,'TRAIN functional mechanism/preservation failed: '+k)
 path=checked_ref(root,seal['independent_training_report'],rows);require(path.startswith(P+'audit/epoch30/'),'Independent TRAIN audit must be current')
 report=parse(root/path);require(report.get('epoch')==30 and report.get('kind')==KIND and report.get('train_integrity_passed') is True,'Independent TRAIN functional acceptance required')
 mapping={'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution','plan':'source_plan','freeze':'source_freeze'}
 require(isinstance(report.get('evidence'),dict) and set(report['evidence'])==set(mapping) and all(report['evidence'][k]==seal[v] for k,v in mapping.items()),'TRAIN report/MODEL seal reference mismatch')
 return seal,train,summary

def model_ready(root,plan,rows):
 return validate_model_seal(root,plan,rows,parse(root/MODEL_SEAL_PATH))

def check_readback(value,phase,parent,trees):
 require(value.get('commit')==parent and (value.get('verified') is True or value.get('verified_actual_full_tree') is True or (value.get('checks_passed') is True and value.get('verified_actual_remote_readback') is True)),'Actual independent parent readback required')
 require(all(value.get(k)==v for k,v in zip(('root','bench','scope'),trees)),'Actual parent tree guards differ')
 parents=[value[k] for k in ('parent','sole_parent') if k in value];require(parents and all(v==parents[0] for v in parents),'Missing/conflicting sole parent')
 if phase=='source':require(parent==SOURCE_PARENT and tuple(trees)==SOURCE_TREES and parents[0]==SOURCE_PARENT_SOLE_PARENT,'SOURCE must extend exact durable data reservation')
 else:require(parent not in (BASE_COMMIT,SOURCE_PARENT),'MODEL/FINAL must extend actual SOURCE/MODEL')

def checked_controls(args,root,kit,current):
 phase=args.phase;bodies=controls_at(args.controls);prior=controls_at(args.priorcontrols,kit)
 oldcp,oldcont=parse(kit/'CHECKPOINT_MANIFEST.json'),parse(kit/'CONTINUATION.json')
 require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256==oldcont['checkpoint_manifest_sha256'],'Original CP hash differs');check_inherited_checkpoint(oldcp);check_history(root,oldcp)
 cp,cont,active=(loads(bodies[n]) for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 pcp,pcont,pactive=(loads(prior[n]) for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 _,rows=checkpoint_extension(oldcp,cp,current);require(pcont['checkpoint_manifest_sha256']==sha(prior['CHECKPOINT_MANIFEST.json']),'Prior checkpoint hash differs')
 mutable=FINAL_MUTABLE if phase=='final' else MUTABLE;preserve_history(oldcont,cont,mutable);preserve_history(pcont,cont,mutable)
 require(cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json']) and cont['active_run']==dict(active,path='ACTIVE_RUN.json') and cont['prior_published_base_commit']==args.parent and cont.get('goal_met') is False and cont.get('official_rank') is None,'Control/hash/status/parent differs')
 owner=active.get('physical_owner',{});require(active.get('run_id')==OWNER_RUN_ID and (owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==OWNER_PIN and owner.get('expires_unix')==OWNER_EXPIRES_UNIX,'Wrong exact guardian generation')
 require(type(active.get('native_allowed'))is int and active['native_allowed']==0 and active.get('experiments_active') is False and active.get('checkpoint_parent')==args.parent and active.get('OS_lock_held') is True,'Immediate native execution must remain closed')
 for k in ('confirmation_allowed','conditional_confirmation_allowed'):require(type(active.get(k))is int and active[k]==0,'Confirmation allowance must remain zero')
 if phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH30_PLANNING_LEASE' and active.get('state')=='EPOCH30_SOURCE_FROZEN_TRAIN_PENDING_ADMISSION' and active.get('work_active') is True and active.get('conditional_train_allowed')==1 and active.get('conditional_dev_allowed')==0,'SOURCE conditional TRAIN gate differs')
  require(not any(path.startswith(E+'runs/') or path in {MODEL_SEAL_PATH,E+'RESULTS.json',E+'EPOCH_MANIFEST.json',E+'SOURCE_ADMISSION.json',E+'MODEL_ADMISSION.json'} for path in current),'Premeasurement SOURCE contains execution/admission/model artifacts')
 else:
  require(set(cp)==set(pcp) and all(cp[k]==v for k,v in pcp.items() if k!='project_files') and all(rows.get(k)==v for k,v in cp_rows(pcp).items()),'Previously published CP/source/model changed')
  require(cont.get('epoch30_frozen_study')==pcont.get('epoch30_frozen_study'),'Published source plan/freeze changed')
  if phase=='model':
   require(pactive.get('state')=='EPOCH30_SOURCE_FROZEN_TRAIN_PENDING_ADMISSION' and active.get('state')=='EPOCH30_MODEL_SEALED_DEV_PENDING_ADMISSION' and active.get('work_active') is True and active.get('conditional_train_allowed')==0 and active.get('conditional_dev_allowed')==1,'MODEL conditional DEV gate differs')
   require(not (root/PHASE_RESERVATIONS['dev']).exists() and not (root/(E+'runs/dev')).exists(),'MODEL seal cannot follow DEV consumption')
  else:require(pactive.get('state') in ('EPOCH30_SOURCE_FROZEN_TRAIN_PENDING_ADMISSION','EPOCH30_MODEL_SEALED_DEV_PENDING_ADMISSION') and active.get('state')=='EPOCH30_CLOSED' and active.get('work_active') is False and active.get('conditional_train_allowed')==active.get('conditional_dev_allowed')==0,'FINAL phase closure differs')
 require(same_fact(cont.get('epoch30_planning'),pcont.get('epoch30_planning')) and same_fact(cont.get('epoch30_data_roles'),data_role_record()),'Planning/frozen roles changed')
 require(same_fact(cont.get('exposed_development_sets'),oldcont.get('exposed_development_sets',[])+[retirement_record()]),'Retire exactly16 fixed role IDs once, preserving legacy records')
 plan=check_plan(root,cont,rows,current,phase)
 if phase=='model':
  _,train,_=model_ready(root,plan,rows);require(cont.get('epoch30_model_seal')==ref(root,MODEL_SEAL_PATH) and same_fact(cont.get('epoch30_train_observed'),train['actual']),'MODEL omitted sealed artifact/TRAIN effort')
 if phase=='final':check_final(root,rows,cont,pcont,plan,pactive)
 return bodies,prior,oldcp,cp,cont,plan,check_transport(root,oldcont,cont,rows,kit=kit)

def check_final(root,rows,cont,pcont,plan,pactive):
 m=parse(root/(E+'EPOCH_MANIFEST.json'));require(m.get('epoch')==30 and m.get('kind')==KIND and m.get('status') in FINAL_STATUSES,'Wrong final diagnostic scope/status');verify_flags(m)
 require(m.get('confirmation')==[] and m.get('all_slots_closed') is True and type(m.get('diagnostic_qualified'))is bool and type(m.get('train_integrity_passed'))is bool,'Final phase/confirmation/verdict fields invalid')
 for key,path in [('plan',PLAN_PATH),('source_freeze',FREEZE_PATH),('results',E+'RESULTS.json')]:checked_ref(root,m.get(key),rows,path)
 results=parse(root/m['results']['path']);verify_flags(results)
 for key in ('status','diagnostic_qualified','train_integrity_passed','actual_execution'):require(same_fact(results.get(key),m[key]),'Result/manifest fact differs: '+key)
 report_path=checked_ref(root,m.get('independent_report'),rows);require(report_path.startswith(P+'audit/epoch30/'),'Final report must be current independent audit')
 report=parse(root/report_path);require(report.get('epoch')==30 and report.get('kind')==KIND and report.get('checks_passed') is True and report.get('diagnostic_qualified') is m['diagnostic_qualified'] and report.get('train_integrity_passed') is m['train_integrity_passed'],'Independent phase acceptance/binding differs')
 train=phase_evidence(root,'train',m['plan'],rows);dev=phase_evidence(root,'dev',m['plan'],rows)
 actual=aggregate_actual(train,dev);require_final_physical_closure(actual);require(same_fact(m['actual_execution'],actual),'Published actual phase effort/resources differ')
 refs={'train_raw':train['raw'],'train_execution':train['execution'],'dev_raw':dev['raw'],'dev_execution':dev['execution'],'results':m['results']}
 require(all(same_fact(report.get('evidence',{}).get(k),v) for k,v in refs.items()),'Independent phase receipt references differ')
 accepted=pactive.get('state')=='EPOCH30_MODEL_SEALED_DEV_PENDING_ADMISSION'
 if accepted:
  seal,_,_=model_ready(root,plan,rows);require(cont.get('epoch30_model_seal')==pcont.get('epoch30_model_seal')==ref(root,MODEL_SEAL_PATH) and m['train_integrity_passed'] is True,'Published accepted MODEL identity/training verdict changed')
  require(report.get('evidence',{}).get('model_seal')==ref(root,MODEL_SEAL_PATH) and report.get('evidence',{}).get('parameter_artifact')==seal['parameter_artifact'],'Independent final report omitted exact trained MODEL identity')
  if dev['actual']['worker_attempts']:
   ap=E+'MODEL_ADMISSION.json';ar=ref(root,ap);checked_ref(root,ar,rows,ap);admission=parse(root/ap)
   source_admission_path=E+'SOURCE_ADMISSION.json';sr=ref(root,source_admission_path);checked_ref(root,sr,rows,source_admission_path)
   require(admission.get('epoch')==30 and admission.get('kind')==KIND and admission.get('phase')=='dev' and admission.get('verified_actual_remote_readback') is True,'Actual DEV MODEL readback admission missing')
   require(admission.get('published_model_commit')==cont['prior_published_base_commit'] and admission.get('published_source_commit')==pcont['prior_published_base_commit'],'DEV source/model commit identities differ')
   require(admission.get('model_seal')==ref(root,MODEL_SEAL_PATH) and admission.get('parameter_artifact')==seal['parameter_artifact'] and admission.get('plan_sha256')==m['plan']['sha256'] and admission.get('source_freeze_sha256')==m['source_freeze']['sha256'] and admission.get('source_admission_sha256')==sr['sha256'],'DEV admitted artifact/source byte identities differ')
   require(admission.get('owner_pid')==OWNER_PIN[0] and admission.get('owner_startticks')==OWNER_PIN[1],'DEV admission guardian differs')
  require(m['status'] in ('DEV_DIAGNOSTIC_QUALIFIED','REJECTED_DEV_DIAGNOSTIC'),'Accepted-model final status differs')
 else:require(dev['actual']['status']=='NOT_STARTED' and m['status']=='TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED' and m['diagnostic_qualified'] is False,'Unaccepted MODEL cannot authorize DEV')
 if m['diagnostic_qualified']:require(accepted and phase_completed(dev) and m['status']=='DEV_DIAGNOSTIC_QUALIFIED' and report.get('frozen_DEV_gates_passed') is True,'Qualified diagnostic requires complete accepted-model DEV and all frozen gates')
 else:require(m['status']!='DEV_DIAGNOSTIC_QUALIFIED','Rejected diagnostic claimed success')
 before,new=pcont.get('execution_observed',{}),cont.get('execution_observed',{});counts=cumulative_counts(actual)
 require(before.get('epoch27_cumulative_corpus_attempts')==24 and before.get('epoch27_cumulative_completed_corpus_batches')==22 and before.get('cumulative_bounded_native_process_attempts_including_qualification')==30,'Verified explicit prior24/22 andbounded30 baseline differs')
 require(all(same_fact(new.get(k),v) for k,v in before.items()) and all(k in before or k.startswith('epoch30_') for k in new) and same_fact(new.get('epoch30_actual_execution'),actual),'Historical execution fields changed or current effort missing')
 for key,wanted in {'epoch30_cumulative_corpus_attempts':counts['corpus_attempts'],'epoch30_cumulative_completed_corpus_batches':counts['completed_corpus_batches'],'epoch30_cumulative_bounded_native_process_attempts':counts['bounded_native_process_attempts']}.items():require(same_fact(new.get(key),wanted),'Explicit current cumulative count differs: '+key)
 require(same_fact(m.get('cumulative_execution'),counts) and same_fact(results.get('cumulative_execution'),counts),'Manifest/result cumulative projection differs')
 oldref=pcont['rejection_ledger'];checked_ref(root,oldref,rows);newref=cont['rejection_ledger'];checked_ref(root,newref,rows,E+'REJECTION_LEDGER.json')
 oldledger,ledger=parse(root/oldref['path']),parse(root/newref['path'])
 for k,v in oldledger.items():
  require(same_fact(ledger.get(k,[])[:len(v)],v) if k=='rejections' else same_fact(ledger.get(k),v),'Historical rejection metadata changed: '+k)
 require(all(k in oldledger or k.startswith('epoch30_') for k in ledger),'New rejection metadata outside current epoch')
 require(same_fact(ledger.get('epoch30_cumulative_execution'),counts),'Ledger cumulative execution differs')
 budget={'train_worker_attempts_used':train['actual']['worker_attempts'],'dev_worker_attempts_used':dev['actual']['worker_attempts'],'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
 require(same_fact(ledger.get('epoch30_budget'),budget) and same_fact(ledger.get('epoch30_actual_execution'),actual) and same_fact(cont.get('cumulative_budget_ledger',{}).get('epoch30_budget'),budget),'Current used/closed budget or phase effort differs')
 decision=ledger.get('epoch30_decision',{});verify_flags(decision)
 for k,v in {'status':m['status'],'diagnostic_qualified':m['diagnostic_qualified'],'train_integrity_passed':m['train_integrity_passed'],'results':m['results']}.items():require(same_fact(decision.get(k),v),'Current rejection decision differs: '+k)
 if m['diagnostic_qualified']:require(ledger['rejections']==oldledger['rejections'] and ledger.get('epoch30_diagnostic_qualification',{}).get('results')==m['results'],'Positive diagnostic record missing')
 else:require(len(ledger['rejections'])==len(oldledger['rejections'])+1 and ledger['rejections'][-1].get('epoch')==30 and ledger['rejections'][-1].get('status')==m['status'] and ledger['rejections'][-1].get('results')==m['results'] and bool(ledger['rejections'][-1].get('reason')),'Exact current rejection and reason required')
 summary={**FLAGS,'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':m['results'],'status':m['status'],'diagnostic_qualified':m['diagnostic_qualified'],'train_integrity_passed':m['train_integrity_passed'],'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
 require(same_fact(cont.get('epoch30_final'),summary),'Continuation final projection differs')
 epoch={**FLAGS,'epoch':30,'kind':KIND,'status':m['status'],'manifest':summary['manifest'],'results':m['results'],'diagnostic_qualified':m['diagnostic_qualified'],'train_integrity_passed':m['train_integrity_passed']}
 require(same_fact(cont.get('epochs'),pcont.get('epochs',[])+[epoch]),'Append exactly one truthful epoch summary')
 for key,value in m.get('phase_remaining',{'train':0,'dev':0,'confirmation':0}).items():require(type(value)is int and value==0,'Final leaves a phase budget open')

def prepare(args):
 root,kit,controls,priorcontrols=map(directory,(args.project,args.kit,args.controls,args.priorcontrols));live_owner(root.parent)
 output=new_output(args.out,(root,kit,controls,priorcontrols))
 for key in ('parent','expected_main','expected_root','expected_bench','expected_scope'):require(re.fullmatch('[0-9a-f]{40}',getattr(args,key) or ''),'Exact Git SHA required: '+key)
 require(args.expected_main==MAIN_COMMIT,'Pinned main required')
 proof_bytes=content(args.parent_readback);check_readback(loads(proof_bytes),args.phase,args.parent,(args.expected_root,args.expected_bench,args.expected_scope))
 map_bytes=content(args.source_filemap);baseline=verify_baseline(kit,loads(map_bytes));current=walk_current(root)
 review_bytes=content(args.reviewed_files);checked_review(loads(review_bytes),current)
 bodies,prior,oldcp,cp,cont,plan,transport=checked_controls(args,root,kit,current)
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
 meta={'schema_version':1,'stage':args.phase,'prior_controls_name':args.priorcontrols.name,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'publication_parent':args.parent,
  'CAS_guards':{'expected_main':args.expected_main,'expected_root_tree':args.expected_root,'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,'expected_branch_sha':args.parent,'force':False},
  'source_filemap_sha256':sha(map_bytes),'prior_expected_sha256':sha(prior_bytes),'reviewed_files_sha256':sha(review_bytes),'parent_readback_sha256':sha(proof_bytes),
  'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(before),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(cp_rows(cp)),'new_epoch30_public_files':len(current),'expected_Git_leaves':len(expected),
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
 cli.add_argument('--phase',choices=('source','model','final'),required=True);cli.add_argument('--prior-expected',type=Path)
 for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):cli.add_argument('--'+name,required=True)
 print(json.dumps(prepare(cli.parse_args()),sort_keys=True))
