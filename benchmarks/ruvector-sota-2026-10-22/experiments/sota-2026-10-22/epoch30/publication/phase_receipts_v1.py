"""Canonical TRAIN/DEV captured-receipt projection; no model imports."""
from __future__ import annotations
import copy,re
from publication_common_v1 import BASE_COMMIT,encoded,require,parse,ref,cp_rows
from phase_schema_v1 import KIND,ROLES,E,PHASE_RESERVATIONS

def same_fact(left,right):
 if type(left) is not type(right):return False
 if isinstance(left,dict):return set(left)==set(right) and all(same_fact(left[key],right[key]) for key in left)
 if isinstance(left,list):return len(left)==len(right) and all(same_fact(a,b) for a,b in zip(left,right))
 return left==right

def derive_actual(raw,execution):
 """Canonical factual projection of the captured E30 raw/launcher receipts.

 Error count preserves all raw errors and adds only launcher/cleanup error
 objects not already present by canonical JSON identity. An expected original
 boundary refusal is a request outcome and never added to the raw error list.
 """
 phase=execution.get('phase') if isinstance(execution,dict) else None
 require(phase in ('train','dev'),'Captured train/dev phase required')
 require((raw is None or isinstance(raw,dict)) and isinstance(execution,dict),'Captured raw/execution objects required')
 for doc in ((raw,execution) if raw is not None else (execution,)):
  require(doc.get('epoch')==30 and doc.get('kind')==KIND,'Captured evidence must belong to actual E30 qualification')
  require(doc.get('phase')==phase,'Wrong captured TRAIN/DEV phase')
 if raw is not None:require(raw.get('source_checkpoint')==BASE_COMMIT and same_fact(raw.get('data_roles'),ROLES),'Raw source/empty benchmark roles differ')
 counters=raw.get('counters') if raw is not None else {}
 require(isinstance(counters,dict) and (execution.get('raw_operation_counters')==counters if raw is not None else execution.get('raw_operation_counters') in (None,{})),'Captured raw/launcher counters differ')
 require(all(isinstance(key,str) and type(value) in (int,float) and value>=0 for key,value in counters.items()),'Invalid raw operation counters')
 n=execution.get('worker_attempts_reserved');starts=execution.get('verified_worker_starts')
 require(type(n) is int and 0<=n<=1 and type(starts) is int and 0<=starts<=n,'Captured reservation/start count invalid')
 require(type(execution.get('uncertain_start')) is bool,'Captured start uncertainty required')
 closed=execution.get('owned_live_processes_closed');groups=execution.get('owned_live_group_members')
 observation=execution.get('owned_process_closure_observation','OBSERVED')
 unknown_closure=(closed is None and groups is None and observation=='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF'
  and execution.get('status')=='WORKER_FAILED_OR_TIMEOUT' and execution['uncertain_start'] is True and starts==0
  and execution.get('exit_code') is None and execution.get('worker_identity_source')=='UNKNOWN'
  and execution.get('worker_identity') is None and execution.get('recovered_preexec_child_identity') is None
  and execution.get('raw_operation_counters_source')=='UNKNOWN')
 require((closed is True and groups==[] and observation=='OBSERVED') or unknown_closure,'Captured physical closure must be observed or exact failed uncertain UNKNOWN')
 for key in ('wall_seconds_including_init_cleanup','children_user_seconds','children_system_seconds','largest_child_peak_RSS_bytes'):
  require(type(execution.get(key)) in (int,float) and execution[key]>=0,'Captured resource missing/invalid: '+key)
 require(type(execution['largest_child_peak_RSS_bytes']) is int,'Captured RSS must be bytes integer')
 require(execution.get('CPU_affinity')==[0,1] and all(type(x) is int for x in execution['CPU_affinity']),'Captured CPU affinity differs')
 require(execution.get('allowed_further_phase_workers')==0,'Captured remaining worker allowance is open')
 errors=raw.get('errors') if raw is not None else [];cleanup=execution.get('cleanup_errors')
 require(isinstance(errors,list) and isinstance(cleanup,list),'Captured error lists required')
 identities={encoded(error) for error in errors};error_count=len(errors)
 extra=([execution['launcher_error']] if execution.get('launcher_error') is not None else [])+cleanup
 for error in extra:
  identity=encoded(error)
  if identity not in identities:error_count+=1;identities.add(identity)
 overlay={'phase':phase,'worker_attempts':n,'verified_worker_starts':starts,'uncertain_start':execution['uncertain_start'],
  'wall_seconds_including_init_cleanup':execution['wall_seconds_including_init_cleanup'],
  'CPU_affinity':copy.deepcopy(execution['CPU_affinity']),'owned_live_processes_closed':closed,
  'owned_live_group_members':copy.deepcopy(groups),'owned_process_closure_observation':observation,
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

def checked_ref(root,row,rows=None,path=None):
 require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Canonical phase reference required')
 require(path is None or row['path']==path,'Wrong phase evidence path')
 require(ref(root,row['path'])==row,'Actual phase reference mismatch')
 if rows is not None:require(rows.get(row['path'])==row,'Phase reference absent/different in checkpoint')
 return row['path']

def not_started(phase):
 return {'phase':phase,'status':'NOT_STARTED','worker_attempts':0,'verified_worker_starts':0,
  'raw_operation_counters_source':'NOT_STARTED','operation_counts_complete':False,
  'backend_execution_since_checkpoint':'NOT_STARTED','errors':None,'resources':None}

def phase_evidence(root,phase,plan_ref,rows=None,required=False):
 """Bind captured bytes to the selected current full/partial/unknown receipt."""
 require(phase in ('train','dev'),'Unknown phase')
 directory=root/(E+'runs/'+phase);execution_path=directory/'execution.json';reservation=root/PHASE_RESERVATIONS[phase]
 if not execution_path.exists():
  require(not required and not reservation.exists() and not directory.exists(),'A reserved/partial phase cannot be relabelled unstarted')
  return {'raw':None,'execution':None,'reservation':None,'actual':not_started(phase),'raw_value':None,'execution_value':None}
 require(reservation.is_file(),'Captured phase missing its durable reservation')
 rr=ref(root,PHASE_RESERVATIONS[phase]);checked_ref(root,rr,rows,PHASE_RESERVATIONS[phase])
 reserve=parse(reservation)
 require(reserve.get('phase')==phase and reserve.get('plan_sha256')==plan_ref['sha256'],'Phase reservation/source-plan identity differs')
 ep=E+'runs/'+phase+'/execution.json';er=ref(root,ep);checked_ref(root,er,rows,ep);execution=parse(execution_path)
 require(execution.get('phase')==phase,'Captured execution belongs to different phase')
 full=directory/'raw.json';partial=directory/'raw.partial.json';fv=pv=None;fp=pp=None
 if full.exists():
  fp=ref(root,E+'runs/'+phase+'/raw.json');checked_ref(root,fp,rows)
  require(execution.get('raw_bytes')==fp['bytes'] and execution.get('raw_sha256')==fp['sha256'],'Captured full raw seal differs')
  try:fv=parse(full)
  except (ValueError,UnicodeError):pass
 else:require(execution.get('raw_bytes') is None and execution.get('raw_sha256') is None,'Captured full raw disappeared')
 if partial.exists():
  pp=ref(root,E+'runs/'+phase+'/raw.partial.json');checked_ref(root,pp,rows)
  require(execution.get('partial_raw_bytes')==pp['bytes'] and execution.get('partial_raw_sha256')==pp['sha256'],'Captured partial raw seal differs')
  try:pv=parse(partial)
  except (ValueError,UnicodeError):pass
 else:require(execution.get('partial_raw_bytes') is None and execution.get('partial_raw_sha256') is None,'Captured partial raw disappeared')
 source=execution.get('raw_operation_counters_source')
 if isinstance(fv,dict) and isinstance(fv.get('counters'),dict):
  require(source=='raw.json','Known final counters cannot be relabelled partial/UNKNOWN');selected,value=fp,fv
 elif isinstance(pv,dict) and isinstance(pv.get('counters'),dict):
  require(source=='raw.partial.json' and execution.get('status')=='WORKER_FAILED_OR_TIMEOUT','Known checkpoint counters cannot be hidden or called complete');selected,value=pp,pv
 else:
  require(source=='UNKNOWN' and execution.get('status')=='WORKER_FAILED_OR_TIMEOUT','Absent/unparseable counters require explicit failed UNKNOWN');selected,value=fp or pp,None
 actual=derive_actual(value,execution)
 require(actual['worker_attempts']==1,'A captured phase must burn its reservation')
 if value is not None:require(value.get('plan_sha256')==plan_ref['sha256'],'Raw phase/source-plan identity differs')
 return {'raw':selected,'execution':er,'reservation':rr,'actual':actual,'raw_value':value,'execution_value':execution}

def phase_completed(evidence):
 e=evidence['execution_value'];a=evidence['actual']
 return bool(e and e.get('status')=='WORKER_COMPLETED' and e.get('exit_code')==0
  and a.get('verified_worker_starts')==1 and a.get('uncertain_start') is False
  and a.get('owned_live_processes_closed') is True and a.get('operation_counts_complete') is True and a.get('errors')==0
  and a.get('wall_seconds_including_init_cleanup',601)<=600
  and e.get('source_plan_unchanged') is True and isinstance(e.get('raw_closure_invariants'),dict)
  and bool(e['raw_closure_invariants']) and all(v is True for v in e['raw_closure_invariants'].values()))

def aggregate_actual(train,dev):
 phases=[train,dev];known=[p['actual'] for p in phases if p['execution_value'] is not None]
 return {'train':copy.deepcopy(train['actual']),'dev':copy.deepcopy(dev['actual']),
  'worker_attempts':sum(a['worker_attempts'] for a in (train['actual'],dev['actual'])),
  'verified_worker_starts':sum(a['verified_worker_starts'] for a in (train['actual'],dev['actual'])),
  'completed_corpus_batches':sum(phase_completed(p) for p in phases),
  'wall_seconds_including_init_cleanup':sum(a['wall_seconds_including_init_cleanup'] for a in known) if known else None,
  'peak_RSS_bytes':max(a['peak_RSS_bytes'] for a in known) if known else None,
  'owned_live_processes_closed':None if any(a['owned_live_processes_closed'] is None for a in known) else all(a['owned_live_processes_closed'] for a in known),
  'errors':sum(a['errors'] for a in known) if known and all(a['errors'] is not None for a in known) else None,
  'resource_scope':'Sum of observed whole-phase wall times; maximum largest-child high-water RSS across phases, not simultaneous aggregate RSS. Unstarted phase internal operations/resources unmeasured.'}

def cumulative_counts(actual):
 return {'corpus_attempts':24+actual['worker_attempts'],
  'completed_corpus_batches':22+actual['completed_corpus_batches'],
  'bounded_native_process_attempts':30+actual['worker_attempts'],
  'qualification_attempts':6,'benchmark_HTTP_successes':885,'benchmark_HTTP_failures':2}

def require_final_physical_closure(actual):
 require(actual.get('owned_live_processes_closed') is True,'FINAL must not close/release work while physical closure remains UNKNOWN; separate independent physical resolution required')
