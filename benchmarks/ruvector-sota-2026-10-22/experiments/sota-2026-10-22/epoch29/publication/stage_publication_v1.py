"""Stage append-only E29 public engineering evidence; no external operations.

This CLI verifies the caller's reviewed controls and actual-parent receipt. It
does not grant native execution admission or interpret an engineering result
as a benchmark score. Output consists only of bounded Git transport requests.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse, copy, hashlib, re
from pathlib import Path
from publication_common_v1 import (P,SCOPE,ROOTS,CONTROLS,BASE_COMMIT,
 BASE_CP_SHA256,OWNER_RUN_ID,OWNER_PIN,OWNER_EXPIRES_UNIX,check_inherited_checkpoint,
 check_history,check_transport,content,cp_rows,directory,encoded,gitsha,live_owner,
 loads,new_output,parse,public_text,ref,relative,require,sha,walk_current,write)

MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
BASE_GIT_LEAVES=3958
BASE_SCOPE_TREE='81b91392c8894f41eef45bd2e5cb68ac9aa03d2a'
LEASE_COMMIT='b216e8fff685d253f418b98c2eee617d5b5adcb3'
SOURCE_PARENT_SOLE_PARENT='8747b6d0aebba8971df69ada6dafa11a94038b75'
MAIN_COMMIT='46d816ddc4c2a8a06cd3613534a79b1d557d858b'
LEASE_TREES=('f29eefdd915ca2ea3a9a5ff2502bf67f53697b2c',
 '54c165435a2ad4945269b0c1444e784d1c768a73',
 'd4ce7c699993682f11e85bbfb69511c4d9dd2cf9')
KIND='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
E=P+'epoch29/'
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
TUPLE_KEYS=('path','mode','type','sha','size')
SOURCE_MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh','exposed_development_sets'}
FINAL_MUTABLE=SOURCE_MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger','exposed_development_sets'}
FORBIDDEN_RESULT_FLAGS=('benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified')
OUTCOME_STATUSES={'DATA_ADMISSION_HOLD_WITH_ENGINEERING_QUALIFIED','REJECTED_ENGINEERING_QUALIFICATION'}
HOLD_REF={'path':P+'audit/epoch29/data-projection-hold.json','bytes':7079,'sha256':'2a2dd48bf50e07a3ef77db5a29ffc6cc0d69472c59fc6799b2ecce4780851f20'}
HELD_ROLES={'train':[309,369,386,593,579,505,536,383],'dev':[548,203,492,252,162,200,529,589],'calibration':[],'confirmation':[]}
EMPTY_ROLES={'train':[],'dev':[],'calibration':[],'confirmation':[]}

def held_data_admission(project):
 checked_ref(project,HOLD_REF)
 report=parse(project/HOLD_REF['path'])
 require(report.get('data_admissible') is False and report.get('fixed_roles')==HELD_ROLES and report.get('annotation_choices_accessed')==0 and report.get('model_tokenizer_native_imports_or_initializations')==0,'Exact original allocation HOLD required')
 return {'status':'HOLD_FIXED_DATA_NORMALIZED_ALIAS_NO_REDRAW_NO_MODEL_ATTEMPT','report':copy.deepcopy(HOLD_REF),
  'fixed_data_roles':copy.deepcopy(HELD_ROLES),'all16_fixed_ids_retired':True,
  'retired_document_ids':HELD_ROLES['train']+HELD_ROLES['dev'],
  'partition_after_retirement':{'exposed':277,'unreserved':122,'reserved_confirmation':24,'total':423},
  'parameter_adaptation_executed':False,'TRAIN_DEV_confirmation_label_reads':0,
  'new_engineering_data_roles':copy.deepcopy(EMPTY_ROLES)}

def retirement_record(project):
 return {'epoch':29,'kind':'RETIRED_FIXED_ALLOCATION_AFTER_NORMALIZED_ALIAS_HOLD',
  'document_ids':HELD_ROLES['train']+HELD_ROLES['dev'],'original_data_roles':copy.deepcopy(HELD_ROLES),
  'source_admission':copy.deepcopy(HOLD_REF),'all16_fixed_ids_permanently_retired':True,'confirmation_consumed':False}

def same_fact(left,right):
 if type(left) is not type(right):return False
 if isinstance(left,dict):return set(left)==set(right) and all(same_fact(left[key],right[key]) for key in left)
 if isinstance(left,list):return len(left)==len(right) and all(same_fact(a,b) for a,b in zip(left,right))
 return left==right

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
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original3958 Git identity required')
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

def checked_ref(project,row,checkpoint=None,expected_path=None):
 require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Canonical three-key reference required')
 require(type(row['bytes']) is int and row['bytes']>=0 and isinstance(row['sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['sha256']),'Invalid canonical reference fields')
 path=relative(row['path'])
 require(expected_path is None or path==expected_path,'Unexpected reference path')
 require(ref(project,path)==row,'Actual reference drift: '+path)
 if checkpoint is not None:require(checkpoint.get(path)==row,'Reference absent/different in checkpoint: '+path)
 return path

def checkpoint_extension(old,new,current):
 before,after=cp_rows(old),cp_rows(new)
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch29_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
 require(set(after)==set(before)|set(current),'Checkpoint must cover exactly original and current public files')
 for path,row in before.items():require(after.get(path)==row,'Historical checkpoint row changed: '+path)
 for path,body in current.items():require(after[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Current checkpoint byte mismatch: '+path)
 return before,after

def checked_plan(project,cont,checkpoint,current,phase):
 frozen=cont.get('epoch29_frozen_study')
 require(isinstance(frozen,dict) and set(frozen)=={'plan','source_freeze'},'Exact E29 plan/freeze refs required')
 checked_ref(project,frozen['plan'],checkpoint,PLAN_PATH);checked_ref(project,frozen['source_freeze'],checkpoint,FREEZE_PATH)
 plan,freeze=parse(project/PLAN_PATH),parse(project/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==29 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Wrong E29 engineering source/kind')
 require(plan.get('source_freeze')==frozen['source_freeze'],'Plan/freeze binding differs')
 checked_ref(project,plan.get('held_parameter_adaptation'),checkpoint,HOLD_REF['path']);require(plan['held_parameter_adaptation']==HOLD_REF,'Original held allocation reference changed')
 held_data_admission(project)
 require(not any(p in current for p in (E+'MODEL_SEAL.json',P+'candidate/epoch29/trained-parameters.public.json')),'Data-HOLD identity epoch cannot publish a trained model or MODEL permit')
 require(plan.get('data_roles')=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Engineering work must not consume benchmark roles')
 ids=plan.get('engineering_ids');require(isinstance(ids,list) and bool(ids) and all(isinstance(x,str) and x for x in ids) and len(ids)==len(set(ids)),'Unique frozen engineering IDs required')
 limits=plan.get('limits',{})
 for key,value in {'owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':0,'engineering_batches':1,'paid_calls':0,'GPU_calls':0}.items():
  require(type(limits.get(key)) is type(value) and limits[key]==value,'Exact engineering limit differs: '+key)
 for key in ('CONF_worker_attempts','confirmation_calls','training_steps','optimizer_steps','calibration_calls','generation_calls'):
  if key in limits:require(type(limits[key]) is int and limits[key]==0,'Nonzero forbidden allowance: '+key)
 pins=plan.get('pins');require(isinstance(pins,list) and bool(pins),'Source/runtime metadata pins required')
 pinpaths=set()
 for row in pins:
  path=checked_ref(project,row);require(path not in pinpaths,'Duplicate plan pin');pinpaths.add(path)
 entries=freeze.get('entries');require(isinstance(entries,list) and bool(entries),'Frozen source entries required')
 frozenpaths=set()
 for row in entries:
  path=checked_ref(project,row,checkpoint);require(path not in frozenpaths and path not in {PLAN_PATH,FREEZE_PATH} and path in current,'Invalid/duplicate source-freeze member')
  frozenpaths.add(path)
 require(frozenpaths<=pinpaths,'All frozen source files must be pinned by plan')
 if phase=='source':require(frozenpaths==set(current)-{PLAN_PATH,FREEZE_PATH},'Source-freeze omits premeasurement files')
 for key in ('actual_project',):
  if key in plan:require(plan[key]==str(project),'Wrong projected project')
 return plan,freeze

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
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch29_') for k in after),'Historical continuation metadata removed/new key outside E29')
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
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch29_') for k in new),'Historical budget ledger changed')

def checked_controls(controls,priorcontrols,kit,project,current,phase,parent):
 bodies=controls_at(controls);priorb=controls_at(priorcontrols,kit)
 oldcp,oldcont=parse(kit/'CHECKPOINT_MANIFEST.json'),parse(kit/'CONTINUATION.json')
 require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256==oldcont['checkpoint_manifest_sha256'],'Pinned original CP hash required')
 check_inherited_checkpoint(oldcp);check_history(project,oldcp)
 cp,cont,active=(loads(bodies[n]) for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 pcp,pcont,pactive=(loads(priorb[n]) for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 _,after=checkpoint_extension(oldcp,cp,current)
 require(pcont['checkpoint_manifest_sha256']==sha(priorb['CHECKPOINT_MANIFEST.json']),'Prior CP binding mismatch')
 preserve_history(oldcont,cont,FINAL_MUTABLE if phase=='final' else SOURCE_MUTABLE)
 preserve_history(pcont,cont,FINAL_MUTABLE if phase=='final' else SOURCE_MUTABLE)
 require(cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json']) and cont['active_run']==dict(active,path='ACTIVE_RUN.json') and cont.get('goal_met') is False and cont.get('official_rank') is None and cont.get('prior_published_base_commit')==parent,'Control hash/active/status/parent binding differs')
 o=active.get('physical_owner',{})
 require(active.get('run_id')==OWNER_RUN_ID and (o.get('pid'),o.get('startticks'),o.get('lock_inode'))==OWNER_PIN and o.get('expires_unix')==OWNER_EXPIRES_UNIX and active.get('checkpoint_parent')==parent and active.get('OS_lock_held') is True and active.get('experiments_active') is False and type(active.get('native_allowed')) is int and active['native_allowed']==0,'Wrong owner or immediate allowance')
 for key,value in active.items():
  if ('confirmation' in key.lower() or 'CONF' in key):require(type(value) is int and value==0,'Nonzero confirmation allowance')
 if phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH29_PLANNING_LEASE' and active.get('work_active') is True and active.get('state')=='EPOCH29_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION' and active.get('native_allowed_after_exact_remote_readback')==1,'Source must extend exact planning lease into conditional engineering admission')
  require(not any(x.startswith(E+'runs/') or x in {E+'EPOCH_MANIFEST.json',E+'RESULTS.json',E+'execution.json',E+'NATIVE_ADMISSION.json'} for x in current),'Execution/results present before source freeze')
 else:
  require(pactive.get('state')=='EPOCH29_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION' and active.get('work_active') is False and active.get('state')=='EPOCH29_CLOSED','Final must close actual source stage')
  require(set(cp)==set(pcp) and all(cp[k]==v for k,v in pcp.items() if k!='project_files') and all(after.get(p)==r for p,r in cp_rows(pcp).items()),'Final changed frozen CP metadata/source rows')
  for key,value in active.items():
   if any(w in key.lower() for w in ('allowed','allowance','remaining')) and type(value) is int:require(value==0,'Final allowance open')
  require(cont.get('epoch29_frozen_study')==pcont.get('epoch29_frozen_study'),'Published frozen study refs changed')
 require(cont.get('epoch29_planning')==pcont.get('epoch29_planning') and isinstance(cont.get('epoch29_planning'),dict),'Planning record changed')
 require(same_fact(cont.get('epoch29_data_admission'),held_data_admission(project)),'Continuation dropped/changed exact held allocation and retirement')
 before_exposure=oldcont.get('exposed_development_sets',[]);after_exposure=cont.get('exposed_development_sets',[])
 require(isinstance(before_exposure,list) and same_fact(after_exposure,before_exposure+[retirement_record(project)]),'Append exactly the frozen16-ID retirement without redraw')
 if phase=='final':require(same_fact(cont.get('epoch29_data_admission'),pcont.get('epoch29_data_admission')) and same_fact(cont.get('exposed_development_sets'),pcont.get('exposed_development_sets')),'Published HOLD/exposure records changed')
 plan,freeze=checked_plan(project,cont,after,current,phase)
 transport=check_transport(project,oldcont,cont,after,kit=kit)
 return bodies,priorb,oldcp,cp,cont,active,plan,freeze,transport

def check_readback(doc,phase,parent,trees):
 require(doc.get('commit')==parent and (doc.get('verified') is True or doc.get('verified_actual_full_tree') is True or (doc.get('checks_passed') is True and doc.get('verified_actual_remote_readback') is True)),'Actual independently verified parent readback required')
 for key,value in zip(('root','bench','scope'),trees):require(doc.get(key)==value,'Parent tree guard differs: '+key)
 parents=[doc[key] for key in ('parent','sole_parent') if key in doc]
 require(parents and all(value==parents[0] for value in parents),'Parent/sole_parent absent or conflicting')
 if phase=='source':require(parent==LEASE_COMMIT and tuple(trees)==LEASE_TREES and parents[0]==SOURCE_PARENT_SOLE_PARENT,'Source must extend exact E29 durable data-HOLD lease')
 else:require(parent not in (BASE_COMMIT,LEASE_COMMIT),'Final must extend new actual source commit')

def false_benchmark_flags(doc):
 for key in FORBIDDEN_RESULT_FLAGS:require(doc.get(key) is False,'Engineering report may not assert '+key)
 require(doc.get('official_rank') is None,'Engineering report may not assert official rank')

def derive_actual(raw,execution):
 """Canonical factual projection of the captured E29 raw/launcher receipts.

 Error count preserves all raw errors and adds only launcher/cleanup error
 objects not already present by canonical JSON identity. An expected original
 boundary refusal is a request outcome and never added to the raw error list.
 """
 require((raw is None or isinstance(raw,dict)) and isinstance(execution,dict),'Captured raw/execution objects required')
 for doc in ((raw,execution) if raw is not None else (execution,)):
  require(doc.get('epoch')==29 and doc.get('kind')==KIND,'Captured evidence must belong to actual E29 qualification')
  if 'phase' in doc:require(doc['phase']=='engineering','Historical/nonengineering phase refused')
 if raw is not None:require(raw.get('source_checkpoint')==BASE_COMMIT and raw.get('data_roles')=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Raw source/empty benchmark roles differ')
 counters=raw.get('counters') if raw is not None else {}
 require(isinstance(counters,dict) and (execution.get('raw_operation_counters')==counters if raw is not None else execution.get('raw_operation_counters') in (None,{})),'Captured raw/launcher counters differ')
 require(all(isinstance(key,str) and type(value) in (int,float) and value>=0 for key,value in counters.items()),'Invalid raw operation counters')
 n=execution.get('worker_attempts_reserved');starts=execution.get('verified_worker_starts')
 require(type(n) is int and 0<=n<=1 and type(starts) is int and 0<=starts<=n,'Captured reservation/start count invalid')
 require(type(execution.get('uncertain_start')) is bool,'Captured start uncertainty required')
 require(execution.get('owned_live_group_members')==[] and execution.get('owned_live_processes_closed') is True,'Captured owned process group is not closed')
 for key in ('wall_seconds_including_init_cleanup','children_user_seconds','children_system_seconds','largest_child_peak_RSS_bytes'):
  require(type(execution.get(key)) in (int,float) and execution[key]>=0,'Captured resource missing/invalid: '+key)
 require(type(execution['largest_child_peak_RSS_bytes']) is int,'Captured RSS must be bytes integer')
 require(execution.get('CPU_affinity')==[0,1] and all(type(x) is int for x in execution['CPU_affinity']),'Captured CPU affinity differs')
 require(execution.get('allowed_further_epoch29_workers')==0,'Captured remaining worker allowance is open')
 errors=raw.get('errors') if raw is not None else [];cleanup=execution.get('cleanup_errors')
 require(isinstance(errors,list) and isinstance(cleanup,list),'Captured error lists required')
 identities={encoded(error) for error in errors};error_count=len(errors)
 extra=([execution['launcher_error']] if execution.get('launcher_error') is not None else [])+cleanup
 for error in extra:
  identity=encoded(error)
  if identity not in identities:error_count+=1;identities.add(identity)
 overlay={'worker_attempts':n,'verified_worker_starts':starts,'uncertain_start':execution['uncertain_start'],
  'wall_seconds_including_init_cleanup':execution['wall_seconds_including_init_cleanup'],
  'CPU_affinity':copy.deepcopy(execution['CPU_affinity']),'owned_live_processes_closed':True,
  'peak_RSS_bytes':execution['largest_child_peak_RSS_bytes'],'user_seconds':execution['children_user_seconds'],
  'system_seconds':execution['children_system_seconds'],'errors':error_count if raw is not None else None}
 counter_source=execution.get('raw_operation_counters_source')
 require(counter_source in ('raw.json','raw.partial.json','UNKNOWN') and ((raw is None)==(counter_source=='UNKNOWN')),'Captured counter discriminator does not identify the supplied full/partial/unknown evidence')
 partial=counter_source=='raw.partial.json'
 if counter_source=='raw.json':require(type(execution.get('raw_bytes')) is int and execution['raw_bytes']>=0 and isinstance(execution.get('raw_sha256'),str) and re.fullmatch('[0-9a-f]{64}',execution['raw_sha256']),'Final raw counter source requires exact captured full seal')
 complete=counter_source=='raw.json';backend_scope='NOT_APPLICABLE_FINAL_RAW' if complete else 'UNKNOWN'
 require(execution.get('raw_operation_counters_source')==counter_source and execution.get('operation_counts_complete') is complete and execution.get('backend_execution_since_checkpoint')==backend_scope,'Captured full/partial/unknown counter source discriminator differs')
 overlay.update(raw_operation_counters_source=counter_source,operation_counts_complete=complete,backend_execution_since_checkpoint=backend_scope)
 if partial:
  require(execution.get('status')=='WORKER_FAILED_OR_TIMEOUT' and type(execution['partial_raw_bytes']) is int and execution['partial_raw_bytes']>=0 and isinstance(execution.get('partial_raw_sha256'),str) and re.fullmatch('[0-9a-f]{64}',execution['partial_raw_sha256']),'Partial checkpoint requires explicit failed captured execution and exact seal')
  overlay.update(operation_counts_complete=False,backend_execution_since_checkpoint='UNKNOWN')
 if raw is None:
  require(execution.get('status')=='WORKER_FAILED_OR_TIMEOUT','Unknown raw counts require explicit failed execution')
  overlay.update(parsed_raw_available=False,operation_counts_complete=False,known_launcher_cleanup_errors=error_count)
 require(not set(counters)&set(overlay),'Raw counter collides with captured resource alias')
 return {**copy.deepcopy(counters),**overlay}

def closed_epoch29_allowances(document):
 def walk(value):
  if isinstance(value,dict):
   for key,child in value.items():
    if any(word in key.lower() for word in ('remaining','allowed','allowance')) and not isinstance(child,(dict,list)):require(type(child) in (int,float,bool) and child==0,'Nonzero/ambiguous durable E29 allowance: '+key)
    walk(child)
  elif isinstance(value,list):
   for child in value:walk(child)
 for key,value in document.items():
  if key.startswith('epoch29_'):walk({key:value})

def check_current_outcome(ledger,oldledger,m,actual):
 status=m.get('status');qualified=m['engineering_qualified']
 require(status in OUTCOME_STATUSES and ((status=='DATA_ADMISSION_HOLD_WITH_ENGINEERING_QUALIFIED') is qualified),'Missing/inconsistent current E29 outcome status')
 expected_budget={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
 require(same_fact(ledger.get('epoch29_budget'),expected_budget),'Exact current E29 used/closed budget required')
 require(same_fact(ledger.get('epoch29_actual_execution'),actual),'Current rejection/qualification ledger actual effort differs')
 decision=ledger.get('epoch29_decision');require(isinstance(decision,dict) and decision.get('status')==status and decision.get('engineering_qualified') is qualified,'Current E29 ledger decision differs')
 require(decision.get('results')==m['results'],'Current decision results identity differs')
 false_benchmark_flags(decision);closed_epoch29_allowances(ledger)
 previous=oldledger.get('rejections',[]);now=ledger.get('rejections',[])
 require(isinstance(previous,list) and isinstance(now,list) and now[:len(previous)]==previous,'Historical rejections changed')
 if qualified:
  require(now==previous,'Successful engineering result cannot add a rejection')
  record=ledger.get('epoch29_qualification');require(isinstance(record,dict) and record.get('epoch')==29 and record.get('status')==status and record.get('engineering_qualified') is True and isinstance(record.get('reason'),str) and bool(record['reason'].strip()),'Explicit current qualification record required')
  require(record.get('results')==m['results'],'Qualification results identity differs')
  false_benchmark_flags(record)
 else:
  require(len(now)==len(previous)+1 and now[-1].get('epoch')==29 and now[-1].get('status')==status and isinstance(now[-1].get('reason'),str) and bool(now[-1]['reason'].strip()) and now[-1].get('results')==m['results'] and 'epoch29_qualification' not in ledger,'Explicit current E29 rejection/reason required')

def checked_current_projections(cont,pcont,m,ledger,manifestref):
 require(same_fact(cont.get('cumulative_budget_ledger',{}).get('epoch29_budget'),ledger['epoch29_budget']),'Continuation/current-ledger E29 budget projections differ')
 flags={key:False for key in FORBIDDEN_RESULT_FLAGS}
 expected_final={**flags,'manifest':manifestref,'results':m['results'],'status':m['status'],
  'engineering_qualified':m['engineering_qualified'],'official_rank':None,'goal_met':False,
  'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
 require(same_fact(cont.get('epoch29_final'),expected_final),'Continuation current final summary differs from exact manifest/result outcome')
 before,after=pcont.get('epochs',[]),cont.get('epochs',[])
 require(isinstance(before,list) and isinstance(after,list) and after[:len(before)]==before and len(after)==len(before)+1,'Append exactly one actual E29 epoch')
 expected_epoch={**flags,'epoch':29,'kind':KIND,'status':m['status'],'manifest':manifestref,
  'results':m['results'],'engineering_qualified':m['engineering_qualified'],'official_rank':None}
 require(same_fact(after[-1],expected_epoch),'Current epoch summary differs from exact manifest/result outcome')

def checked_final(project,cp,cont,pcont,plan):
 m=parse(project/(E+'EPOCH_MANIFEST.json'));require(m.get('epoch')==29 and m.get('kind')==KIND and m.get('all_slots_closed') is True and m.get('confirmation')==[] and type(m.get('engineering_qualified')) is bool,'Honest closed engineering manifest required')
 false_benchmark_flags(m)
 for key,path in [('plan',PLAN_PATH),('source_freeze',FREEZE_PATH),('results',E+'RESULTS.json')]:checked_ref(project,m.get(key),cp,path)
 r=parse(project/m['results']['path']);false_benchmark_flags(r)
 require(m.get('held_parameter_adaptation')==r.get('held_parameter_adaptation')==HOLD_REF,'Engineering result must retain the separate original data HOLD')
 require(same_fact(cont.get('epoch29_data_admission'),held_data_admission(project)),'Final current data HOLD missing')
 require(r.get('engineering_qualified') is m['engineering_qualified'] and r.get('confirmation',[])==[] and r.get('status')==m.get('status'),'Result scope/status/verdict differs')
 report_path=checked_ref(project,m.get('independent_report'),cp);require(report_path.startswith(P+'audit/epoch29/'),'Independent report must be current E29 audit evidence');a=parse(project/report_path)
 require(a.get('epoch')==29 and a.get('kind')==KIND and a.get('checks_passed') is True and a.get('engineering_qualified') is m['engineering_qualified'],'Independent scope/integrity/engineering verdict differs')
 evidence=a.get('evidence');require(isinstance(evidence,dict),'Independent canonical evidence refs required')
 for key,path in [('execution',E+'execution.json'),('results',E+'RESULTS.json')]:checked_ref(project,evidence.get(key),cp,path)
 require(evidence['results']==m['results'],'Independent report results ref differs')
 actual=m.get('actual_execution');require(isinstance(actual,dict) and same_fact(r.get('actual_execution'),actual),'Actual execution counters must match')
 execution=parse(project/evidence['execution']['path']);rawref=evidence.get('raw')
 if rawref is not None:
  rawpath=checked_ref(project,rawref,cp)
  require(rawpath in (E+'runs/engineering/raw.json',E+'runs/engineering/raw.partial.json'),'Raw evidence is not an exact current E29 full/partial path')
  partial=rawpath==E+'runs/engineering/raw.partial.json'
  if partial:
   require(execution.get('raw_operation_counters_source')=='raw.partial.json' and execution.get('operation_counts_complete') is False and execution.get('backend_execution_since_checkpoint')=='UNKNOWN','Selected partial evidence path cannot be relabelled as complete final raw')
   require(m['engineering_qualified'] is False and execution.get('status')=='WORKER_FAILED_OR_TIMEOUT' and execution.get('partial_raw_bytes')==rawref['bytes'] and execution.get('partial_raw_sha256')==rawref['sha256'],'Partial checkpoint must retain failed/incomplete status and exact captured partial seal')
   if execution.get('raw_bytes') is not None or execution.get('raw_sha256') is not None:
    fullpath=E+'runs/engineering/raw.json';fullref=ref(project,fullpath);checked_ref(project,fullref,cp,fullpath)
    require(execution.get('raw_bytes')==fullref['bytes'] and execution.get('raw_sha256')==fullref['sha256'],'Retained malformed full raw must match its captured full seal')
    try:parse(project/fullpath)
    except (ValueError,UnicodeError):pass
    else:raise ValueError('A valid final raw cannot be hidden behind a partial checkpoint')
   else:require(execution.get('raw_bytes') is None and execution.get('raw_sha256') is None,'Incomplete full raw seal refused')
  else:require(execution.get('raw_bytes')==rawref['bytes'] and execution.get('raw_sha256')==rawref['sha256'],'Captured raw seal does not bind actual raw evidence')
  try:raw=parse(project/rawref['path'])
  except (ValueError,UnicodeError):
   require(m['engineering_qualified'] is False and not partial,'Malformed raw cannot qualify or supply partial counters');raw=None
   if execution.get('partial_raw_bytes') is not None or execution.get('partial_raw_sha256') is not None:
    partialpath=E+'runs/engineering/raw.partial.json';knownref=ref(project,partialpath);checked_ref(project,knownref,cp,partialpath)
    require(execution.get('partial_raw_bytes')==knownref['bytes'] and execution.get('partial_raw_sha256')==knownref['sha256'],'Retained checkpoint must match its captured partial seal')
    try:knownpartial=parse(project/partialpath)
    except (ValueError,UnicodeError):knownpartial=None
    require(not (isinstance(knownpartial,dict) and isinstance(knownpartial.get('counters'),dict)),'Known sealed checkpoint counters cannot be hidden behind an unparseable final raw')
  if not partial and raw is not None:require(execution.get('raw_operation_counters_source')=='raw.json' and execution.get('operation_counts_complete') is True and execution.get('backend_execution_since_checkpoint')=='NOT_APPLICABLE_FINAL_RAW','Selected parsed final evidence must have the final counter discriminator')
 else:
  require('raw' in evidence and m['engineering_qualified'] is False and execution.get('raw_bytes') is None and execution.get('raw_sha256') is None and execution.get('partial_raw_bytes') is None and execution.get('partial_raw_sha256') is None,'Absent raw must be an explicit sealed failure without a hidden known partial');raw=None
 require(same_fact(actual,derive_actual(raw,execution)),'Published actual effort/resources differ from captured receipts')
 if raw is not None:require(raw.get('plan_sha256')==m['plan']['sha256'],'Captured raw source plan identity differs')
 if execution.get('status')=='WORKER_FAILED_OR_TIMEOUT':require(m['engineering_qualified'] is False and m.get('status')=='REJECTED_ENGINEERING_QUALIFICATION','Failed captured execution cannot qualify')
 n=actual.get('worker_attempts');require(type(n) is int and 0<=n<=1,'At most one owned worker attempt')
 elapsed=actual.get('wall_seconds_including_init_cleanup');require(type(elapsed) in (int,float) and elapsed>=0,'Actual elapsed including initialization/cleanup required')
 require(actual.get('owned_live_processes_closed') is True,'All owned process groups must be closed before final publication')
 if m['engineering_qualified']:
  require(n==1 and elapsed<=600 and actual.get('CPU_affinity')==[0,1] and type(actual.get('errors')) is int and actual.get('errors')==0,'Qualified worker closure/runtime/error gates fail')
  require(actual['verified_worker_starts']==1 and actual['uncertain_start'] is False and execution.get('status')=='WORKER_COMPLETED' and execution.get('exit_code')==0 and execution.get('source_plan_unchanged') is True and isinstance(execution.get('raw_closure_invariants'),dict) and bool(execution['raw_closure_invariants']) and all(value is True for value in execution['raw_closure_invariants'].values()),'Qualified captured worker completion invariants fail')
 for key in ('paid_calls','paid_API_calls','GPU_calls','confirmation_calls','CONF_worker_attempts','CONF_annotation_choices','training_steps','optimizer_steps','calibration_calls','generation_calls','NLI_model_initializations','NLI_forward_pairs_attempted','TRAIN_annotation_choices_accessed','DEV_annotation_choices_accessed'):
  if key in actual:require(type(actual[key]) is int and actual[key]==0,'Forbidden action counter: '+key)
 oldobserved,newobserved=pcont.get('execution_observed',{}),cont.get('execution_observed',{})
 require(isinstance(newobserved,dict),'Execution history object required')
 changing={'cumulative_bounded_native_process_attempts_including_qualification','native_qualification_attempts'}
 for key,value in oldobserved.items():
  if key in changing:require(type(value) is int and type(newobserved.get(key)) is int and newobserved[key]==value+n,'Cumulative engineering attempt count differs: '+key)
  else:require(newobserved.get(key)==value,'Historical actual execution changed: '+key)
 require(all(k in oldobserved or k.startswith('epoch29_') for k in newobserved) and newobserved.get('epoch29_actual_execution')==actual,'New actual counters outside E29 or mismatched')
 oldledgerref=pcont.get('rejection_ledger');newledgerref=cont.get('rejection_ledger')
 checked_ref(project,oldledgerref,cp);checked_ref(project,newledgerref,cp,E+'REJECTION_LEDGER.json')
 oldledger,newledger=parse(project/oldledgerref['path']),parse(project/newledgerref['path'])
 require(same_fact(newledger.get('epoch29_data_admission'),cont['epoch29_data_admission']),'Current ledger must retain the exact separate original allocation HOLD')
 require(set(oldledger)<=set(newledger) and all(k in oldledger or k.startswith('epoch29_') for k in newledger),'Rejection ledger historical fields dropped/new key outside E29')
 for key,value in oldledger.items():
  if key=='rejections':require(isinstance(value,list) and isinstance(newledger.get(key),list) and newledger[key][:len(value)]==value,'Historical rejection outcomes changed')
  else:require(newledger.get(key)==value,'Historical rejection ledger changed: '+key)
 check_current_outcome(newledger,oldledger,m,actual);closed_epoch29_allowances(cont.get('cumulative_budget_ledger',{}));closed_epoch29_allowances(cont)
 checked_current_projections(cont,pcont,m,newledger,ref(project,E+'EPOCH_MANIFEST.json'))
 for row in m.get('files',[]):checked_ref(project,row,cp)
 return m

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

def prepare(args):
 project,kit,controls,priorcontrols=map(directory,(args.project,args.kit,args.controls,args.priorcontrols));live_owner(project.parent)
 out=new_output(args.out,(project,kit,controls,priorcontrols))
 for key in ('parent','expected_main','expected_root','expected_bench','expected_scope'):require(re.fullmatch('[0-9a-f]{40}',getattr(args,key) or ''),'Exact Git SHA required: '+key)
 require(args.expected_main==MAIN_COMMIT,'Pinned main required')
 readbackbytes=content(args.parent_readback);check_readback(loads(readbackbytes),args.phase,args.parent,(args.expected_root,args.expected_bench,args.expected_scope))
 mapbytes=content(args.source_filemap);baseline=verify_baseline(kit,loads(mapbytes));current=walk_current(project)
 reviewbytes=content(args.reviewed_files);checked_review(loads(reviewbytes),current)
 bodies,priorb,oldcp,cp,cont,active,plan,freeze,reconstruction=checked_controls(controls,priorcontrols,kit,project,current,args.phase,args.parent)
 if args.prior_expected:
  priorbytes=content(args.prior_expected);prior=tuple_map(loads(priorbytes))
 else:
  require(args.phase=='source','Final requires actual source expected tuples');prior=copy.deepcopy(baseline)
  for name,body in priorb.items():prior[name]=leaf(name,body)
  priorbytes=encoded({'scope':SCOPE,'files':[prior[k] for k in sorted(prior)]})
 for name,body in priorb.items():require(prior.get(name)==leaf(name,body),'Actual prior control tuple differs: '+name)
 for path,row in baseline.items():
  if path not in CONTROLS:require(prior.get(path)==row,'Prior historical tuple differs: '+path)
 expected=copy.deepcopy(baseline)
 for path,body in {**current,**bodies}.items():
  require(path not in baseline or path in CONTROLS,'Historical Git overwrite refused: '+path);expected[path]=leaf(path,body)
 for path,row in prior.items():
  if path not in CONTROLS:require(expected.get(path)==row,'Frozen published source changed/disappeared: '+path)
 check_transport(project,parse(kit/'CONTINUATION.json'),cont,cp_rows(cp),set(expected),kit=kit)
 if args.phase=='final':checked_final(project,cp_rows(cp),cont,loads(priorb['CONTINUATION.json']),plan)
 changed={path:body for path,body in {**current,**bodies}.items() if prior.get(path)!=expected[path]}
 require(CONTROLS<=set(changed),'Three actual control changes required');blobs,groups=transport_groups(changed)
 metadata={'schema_version':1,'stage':args.phase,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'publication_parent':args.parent,
 'CAS_guards':{'expected_main':args.expected_main,'expected_root_tree':args.expected_root,'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,'expected_branch_sha':args.parent,'force':False},
 'source_filemap_sha256':sha(mapbytes),'prior_expected_sha256':sha(priorbytes),'reviewed_files_sha256':sha(reviewbytes),'parent_readback_sha256':sha(readbackbytes),
 'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(prior),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(cp_rows(cp)),'new_epoch29_public_files':len(current),'expected_Git_leaves':len(expected),
 'changed_files':[],'old_noncontrol_tuples_preserved':True,'old_CP_metadata_preserved':True,'frozen_source_tuples_preserved':True,'inherited_archive_transport_unchanged':reconstruction,
 'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[],
 'transport_limits':{'large_file_bytes':LARGE_FILE_BYTES,'blob_JSON_exclusive_bytes':MAX_BLOB_JSON,'tree_JSON_exclusive_bytes':MAX_TREE_JSON,'tool_metadata_reserve_bytes':4096}}
 out.mkdir(mode=0o700);(out/'transport').mkdir(mode=0o700)
 for path,body in sorted(changed.items()):metadata['changed_files'].append({'path':path,'bytes':len(body),'sha256':sha(body),'git_blob_sha1':gitsha(body)})
 for number,(path,body,payload) in enumerate(blobs):
  filename='transport/blob-%03d.json'%number;data=encoded(payload);write(out/filename,data)
  metadata['large_blob_requests'].append({'path':path,'file':filename,'bytes':len(data),'sha256':sha(data),'expected_blob_sha1':gitsha(body),'must_verify_before_tree':True})
 for number,group in enumerate(groups):
  filename='transport/tree-%03d.json'%number;data=encoded({'tree_elements':group});require(len(data)<MAX_TREE_JSON,'Serialized tree strict cap exceeded');write(out/filename,data)
  metadata['create_tree_groups'].append({'file':filename,'bytes':len(data),'sha256':sha(data),'entries':len(group)})
 leaves=encoded({'schema_version':1,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'files':[expected[p] for p in sorted(expected)]});write(out/'expected-leaves.json',leaves)
 metadata['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':sha(leaves),'count':len(expected)};write(out/'metadata.json',encoded(metadata,pretty=True))
 return {k:metadata[k] for k in ('stage','publication_parent','old_CP_rows','new_CP_rows','new_epoch29_public_files','expected_Git_leaves','expected_leaves','Git_mutations')}

def main():
 cli=argparse.ArgumentParser(description=__doc__)
 for name in ('project','kit','controls','priorcontrols','source-filemap','reviewed-files','parent-readback','out'):cli.add_argument('--'+name,type=Path,required=True)
 cli.add_argument('--prior-expected',type=Path)
 cli.add_argument('--phase',choices=('source','final'),required=True)
 for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):cli.add_argument('--'+name,required=True)
 print(__import__('json').dumps(prepare(cli.parse_args()),sort_keys=True))

if __name__=='__main__':main()
