"""Canonical single-engineering captured-receipt projection; no model imports."""
from __future__ import annotations
import copy,re
from publication_common_v1 import BASE_COMMIT,encoded,require,parse,ref,cp_rows
from phase_schema_v1 import KIND,ROLES,E,PHASE_RESERVATIONS,DISPATCH_PATHS,BOOT_ID,PID_NAMESPACE,CLOSURE_KEYS,CORPUS_RESERVATION_PATHS

def same_fact(left,right):
 if type(left) is not type(right):return False
 if isinstance(left,dict):return set(left)==set(right) and all(same_fact(left[key],right[key]) for key in left)
 if isinstance(left,list):return len(left)==len(right) and all(same_fact(a,b) for a,b in zip(left,right))
 return left==right

def derive_actual(raw,execution):
 """Canonical factual projection of the captured E35 raw/launcher receipts.

 Error count preserves all raw errors and adds only launcher/cleanup error
 objects not already present by canonical JSON identity. An expected original
 boundary refusal is a request outcome and never added to the raw error list.
 """
 phase=execution.get('phase') if isinstance(execution,dict) else None
 require(phase=='engineering','Only captured current engineering phase allowed')
 require((raw is None or isinstance(raw,dict)) and isinstance(execution,dict),'Captured raw/execution objects required')
 for doc in ((raw,execution) if raw is not None else (execution,)):
  require(doc.get('epoch')==35 and doc.get('kind')==KIND,'Captured evidence must belong to actual E35 qualification')
  require(doc.get('phase')==phase,'Wrong captured current engineering phase')
 if raw is not None:require(raw.get('source_checkpoint')==BASE_COMMIT and same_fact(raw.get('data_roles'),ROLES),'Raw source/current engineering roles differ')
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

def dispatch_evidence(root,plan_ref,rows,execution_ref):
 """A dispatch burns the sole logical slot; ABOUT_TO_EXIT is never closure."""
 pins={};values={}
 for key,path in DISPATCH_PATHS.items():
  if (root/path).exists():pins[key]=ref(root,path);checked_ref(root,pins[key],rows,path);values[key]=parse(root/path)
  else:pins[key]=None;values[key]=None
 require(pins['reservation'] is not None,'A current engineering attempt requires its durable dispatch reservation')
 claim=values['reservation']
 require(isinstance(claim,dict) and claim.get('epoch')==35 and claim.get('kind')==KIND and claim.get('phase')=='engineering'
  and claim.get('plan_sha256')==plan_ref['sha256'] and claim.get('kernel_boot_id')==BOOT_ID and claim.get('pid_namespace_inode')==PID_NAMESPACE
  and type(claim.get('logical_native_budget_reserved'))is int and claim['logical_native_budget_reserved']==1
  and type(claim.get('allowed_further_dispatches'))is int and claim['allowed_further_dispatches']==0,'Wrong current source-bound logical dispatch reservation')
 require(pins['closure'] is not None,'Independent actual supervisor closure proof required before GOLD/FINAL')
 proof=values['closure'];require(isinstance(proof,dict) and set(proof)==CLOSURE_KEYS,'Exact independent observed-closure schema required')
 require(same_fact(proof.get('schema_version'),1) and proof.get('epoch')==35 and proof.get('kind')==KIND and proof.get('phase')=='engineering'
  and proof.get('source_plan_sha256')==plan_ref['sha256'] and proof.get('kernel_boot_id')==BOOT_ID and proof.get('pid_namespace_inode')==PID_NAMESPACE,'Independent closure source/boot/namespace differs')
 expected={'dispatch_reservation':pins['reservation'],'dispatch_attempt':pins['attempt'],'supervisor_completion':pins['completion'],'execution':execution_ref}
 require(all(same_fact(proof.get(k),v)for k,v in expected.items()),'Independent closure refs differ from actual dispatch/execution bytes')
 identity=proof.get('supervisor_identity');identity_keys={'pid','startticks','pgid','sid'}
 require(identity is None or(isinstance(identity,dict) and set(identity)==identity_keys and all(type(v)is int and v>0 for v in identity.values())),'Exact known supervisor identity or null required')
 known=[]
 if values['attempt'] is not None:
  attempt=values['attempt'];require(attempt.get('epoch')==35 and attempt.get('kind')==KIND and attempt.get('phase')=='engineering' and attempt.get('plan_sha256')==plan_ref['sha256'],'Wrong current dispatch attempt')
  if all(type(attempt.get(k))is int and attempt[k]>0 for k in identity_keys):known.append({k:attempt[k]for k in identity_keys})
 for doc in ([parse(root/execution_ref['path'])]if execution_ref else [])+([values['completion']]if values['completion']else[]):
  if isinstance(doc.get('supervisor_identity'),dict):known.append(doc['supervisor_identity'])
 require(all(same_fact(x,identity)for x in known),'Known supervisor identities conflict with closure proof')
 for key in ('physical_supervisor_absent','physical_supervisor_closed'):require(proof[key] is None or type(proof[key])is bool,'Closure physical facts must be bool/null')
 require(proof['observed_supervisor_state'] is None or isinstance(proof['observed_supervisor_state'],str),'Observed supervisor state must be str/null')
 require(proof['owned_worker_group_members'] is None or isinstance(proof['owned_worker_group_members'],list),'Known worker groups must be list/null')
 require(type(proof['unknown_physical_ownership'])is bool and type(proof['physical_closure_passed'])is bool,'Closure unknown/pass booleans required')
 if execution_ref is None:require(proof['unknown_physical_ownership']is True and proof['owned_worker_group_members']is None and proof['physical_closure_passed']is False,'Missing captured execution keeps worker ownership/closure UNKNOWN; no inferred no-Popen exception')
 terminal=(proof['physical_supervisor_absent'] is True and proof['observed_supervisor_state'] in (None,'ABSENT'))or(proof['physical_supervisor_absent'] is False and proof['observed_supervisor_state']in ('Z','X'))
 closed=bool(execution_ref is not None and identity is not None and known and proof['physical_supervisor_closed']is True and terminal
  and proof['owned_worker_group_members']==[] and proof['unknown_physical_ownership']is False)
 require(proof['physical_closure_passed']is closed,'Observed physical closure contradicts captured identity/state/ownership')
 return {'dispatch_reservation':pins['reservation'],'dispatch_attempt':pins['attempt'],'supervisor_completion':pins['completion'],
  'supervisor_observed_closure':pins['closure'],'supervisor_closure_value':proof,'dispatch_attempt_value':values['attempt']}

def corpus_reservation_evidence(root,plan_ref,rows=None):
 pins={}
 for role,path in CORPUS_RESERVATION_PATHS.items():
  if not(root/path).exists():pins[role]=None;continue
  pin=ref(root,path);checked_ref(root,pin,rows,path);value=parse(root/path)
  require(value.get('epoch')==35 and value.get('kind')==KIND and value.get('phase')=='engineering' and value.get('role')==role
   and value.get('plan_sha256')==plan_ref['sha256'] and same_fact(value.get('corpus_batches_reserved'),1)
   and same_fact(value.get('allowed_further_role_helpers'),0) and value.get('before_Popen')is True and value.get('automatic_retry')is False,'Wrong durable native corpus reservation')
  pins[role]=pin
 require(set(pins)=={'engineering'},'Exactly one engineering corpus role required')
 return {'corpus_reservations':pins,'corpus_reservation_count':sum(row is not None for row in pins.values())}

def phase_evidence(root,phase,plan_ref,rows=None,required=False):
 """Bind captured bytes to the selected current full/partial/unknown receipt."""
 require(phase=='engineering','Unknown phase')
 directory=root/(E+'runs/'+phase);execution_path=directory/'execution.json';reservation=root/PHASE_RESERVATIONS[phase]
 corpus=corpus_reservation_evidence(root,plan_ref,rows)
 if not execution_path.exists():
  if (root/DISPATCH_PATHS['reservation']).exists():
   outer=dispatch_evidence(root,plan_ref,rows,None)
   rr=ref(root,PHASE_RESERVATIONS[phase])if reservation.exists()else None
   if rr is not None:
    checked_ref(root,rr,rows,PHASE_RESERVATIONS[phase]);reserve=parse(reservation)
    require(reserve.get('phase')==phase and reserve.get('plan_sha256')==plan_ref['sha256'],'Phase reservation/source-plan identity differs')
   actual={'phase':phase,'status':'DISPATCH_RESERVED_NO_CAPTURED_EXECUTION','worker_attempts':1,'verified_worker_starts':0,
    'uncertain_start':True,'actual_worker_start_status':'UNKNOWN_NO_CAPTURED_EXECUTION','raw_operation_counters_source':'UNKNOWN',
    'operation_counts_complete':False,'backend_execution_since_checkpoint':'UNKNOWN','errors':None,'resources':None,
    'owned_live_processes_closed':None,'owned_live_group_members':None}
   retained=[ref(root,E+'runs/engineering/'+n)for n in ('raw.json','raw.partial.json','raw.partial.pending.json')if(root/(E+'runs/engineering/'+n)).exists()]
   return {'raw':None,'execution':None,'reservation':rr,'actual':actual,'raw_value':None,'execution_value':None,'retained_unsealed_raw_files':retained,**outer,**corpus}
  require(not required and not reservation.exists() and not directory.exists() and not any((root/path).exists()for path in DISPATCH_PATHS.values()),'A dispatch/reserved/partial phase cannot be relabelled unstarted')
  return {'raw':None,'execution':None,'reservation':None,'actual':not_started(phase),'raw_value':None,'execution_value':None,'dispatch_reservation':None,'supervisor_closure_value':None,'dispatch_attempt_value':None,**corpus}
 require(reservation.is_file(),'Captured phase missing its durable reservation')
 rr=ref(root,PHASE_RESERVATIONS[phase]);checked_ref(root,rr,rows,PHASE_RESERVATIONS[phase])
 reserve=parse(reservation)
 require(reserve.get('phase')==phase and reserve.get('plan_sha256')==plan_ref['sha256'],'Phase reservation/source-plan identity differs')
 ep=E+'runs/'+phase+'/execution.json';er=ref(root,ep);checked_ref(root,er,rows,ep);execution=parse(execution_path)
 outer=dispatch_evidence(root,plan_ref,rows,er)
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
 require(same_fact(execution.get('corpus_reservations'),corpus['corpus_reservations']) and same_fact(execution.get('corpus_reservation_count'),corpus['corpus_reservation_count']),'Captured corpus reservations differ from retained durable claims')
 if value is not None:require(same_fact(value.get('corpus_reservations'),corpus['corpus_reservations']),'Raw corpus reservation refs differ')
 actual=derive_actual(value,execution)
 if actual['operation_counts_complete']:require(same_fact(actual.get('corpus_batches_attempted'),corpus['corpus_reservation_count']),'Complete raw corpus attempt count differs from durable claims')
 require(actual['worker_attempts']==1,'A captured phase must burn its reservation')
 if value is not None:require(value.get('plan_sha256')==plan_ref['sha256'],'Raw phase/source-plan identity differs')
 return {'raw':selected,'execution':er,'reservation':rr,'actual':actual,'raw_value':value,'execution_value':execution,**outer,**corpus}

def phase_completed(evidence):
 e=evidence['execution_value'];a=evidence['actual']
 return bool(e and evidence.get('supervisor_closure_value',{}).get('physical_closure_passed')is True
  and isinstance(evidence.get('dispatch_attempt_value'),dict) and evidence['dispatch_attempt_value'].get('verified_launcher_start')is True
  and evidence['dispatch_attempt_value'].get('uncertain_launcher_start')is False and e.get('status')=='WORKER_COMPLETED' and e.get('exit_code')==0
  and a.get('verified_worker_starts')==1 and a.get('uncertain_start') is False
  and a.get('owned_live_processes_closed') is True and a.get('operation_counts_complete') is True and a.get('errors')==0
  and a.get('wall_seconds_including_init_cleanup',601)<=600
  and e.get('source_plan_unchanged') is True and isinstance(e.get('raw_closure_invariants'),dict)
  and bool(e['raw_closure_invariants']) and all(v is True for v in e['raw_closure_invariants'].values()))

def aggregate_actual(dev):
 proof=dev.get('supervisor_closure_value');physical=(True if proof['physical_closure_passed'] else None if proof['unknown_physical_ownership'] or proof['owned_worker_group_members']is None else False)if proof else True
 actual=copy.deepcopy(dev['actual']);known=dev['execution_value'] is not None
 complete=actual.get('operation_counts_complete')is True
 notstarted=actual.get('status')=='NOT_STARTED'
 attempted=actual.get('corpus_batches_attempted');completed=actual.get('corpus_batches_completed')
 for name,value in [('attempted',attempted),('completed',completed)]:
  require(value is None or(type(value)is int and 0<=value<=1),'Captured corpus batch count invalid: '+name)
 if complete:require(attempted is not None and completed is not None and completed<=attempted,'Complete captured raw requires honest attempted/completed corpus counts')
 # A checkpoint is a known lower bound, never certainty about backend work
 # after that checkpoint. Outer-worker and corpus budgets are different units.
 corpora_attempted=0 if notstarted else attempted if complete else None
 corpora_completed=0 if notstarted else completed if complete else None
 return {'engineering':actual,'worker_attempts':actual['worker_attempts'],'verified_worker_starts':actual['verified_worker_starts'],
  'completed_worker_batches':int(phase_completed(dev)),
  'corpus_batches_attempted':corpora_attempted,'completed_corpus_batches':corpora_completed,
  'known_corpus_reservations':copy.deepcopy(dev.get('corpus_reservations')),
  'known_corpus_reservation_count':dev.get('corpus_reservation_count'),
  'known_corpus_batches_attempted_at_last_capture':attempted,'known_corpus_batches_completed_at_last_capture':completed,
  'wall_seconds_including_init_cleanup':actual.get('wall_seconds_including_init_cleanup') if known else None,
  'peak_RSS_bytes':actual.get('peak_RSS_bytes') if known else None,
  'owned_live_processes_closed':physical,
  'supervisor_observed_closure':copy.deepcopy(dev.get('supervisor_observed_closure')),
  'physical_supervisor_absent':dev.get('supervisor_closure_value',{}).get('physical_supervisor_absent') if dev.get('supervisor_closure_value')else None,
  'observed_supervisor_state':dev.get('supervisor_closure_value',{}).get('observed_supervisor_state') if dev.get('supervisor_closure_value')else None,
  'errors':actual.get('errors'),
  'logical_budget_scope':'One outer-worker slot is max(dispatch reservation, engineering reservation), never their sum. One native corpus batch have separate attempted/completed counters; missing or partial capture leaves actual corpus totals UNKNOWN and retains captured lower bounds.',
  'physical_closure_scope':'Independent observed supervisor/known-worker closure; original captured closure remains unchanged. Terminal Z/X may be closed without absent.',
  'resource_scope':'Observed one whole engineering-only worker including init/cleanup; largest-child high-water RSS, not simultaneous aggregate RSS. Unstarted/internal unobserved operations remain UNKNOWN.'}

def cumulative_counts(actual):
 attempted=actual['corpus_batches_attempted'];completed=actual['completed_corpus_batches']
 return {'corpus_attempts':None if attempted is None else 31+attempted,
  'completed_corpus_batches':None if completed is None else 29+completed,
  'bounded_native_process_attempts':35+actual['worker_attempts'],'qualification_attempts':6,
  'benchmark_HTTP_successes':888,'benchmark_HTTP_failures':2,
  'epoch35_actual_official_benchmark_HTTP_successes':3,'epoch35_actual_official_benchmark_HTTP_failures':0}

def require_final_physical_closure(actual):
 require(actual.get('owned_live_processes_closed') is True,'FINAL must not close/release work while physical closure remains UNKNOWN; separate independent physical resolution required')
