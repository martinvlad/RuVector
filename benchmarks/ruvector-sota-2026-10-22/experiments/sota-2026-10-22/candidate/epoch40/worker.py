"""One private-input DEV forecast batch:48NNI, no gold capability invoked."""
from pathlib import Path
import gc
import hashlib
import importlib.util
import json
import os
import resource
import signal
import sys
import time
import traceback
import weakref
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('e40_worker_common',HERE/'runtime/common.py');C=importlib.util.module_from_spec(sp);sp.loader.exec_module(C)
A=C.load_module('e40_science_constants',HERE/'algorithm.py');K=C.load_module('e40_counter_definitions',HERE/'counters.py')


def checkpoint(raw,out):
 temporary=out/'raw.partial.pending.json'
 with temporary.open('w',encoding='utf-8')as f:json.dump(raw,f,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(temporary,out/'raw.partial.json')

def process_status():
 values={}
 for line in Path('/proc/self/status').read_text().splitlines():
  if line.startswith(('Threads:','NoNewPrivs:','Seccomp:')):key,value=line.split(':',1);values[key]=value.strip()
 values['cpu_affinity']=sorted(os.sched_getaffinity(0));return values

def resources(torch_observed):
 own=resource.getrusage(resource.RUSAGE_SELF);child=resource.getrusage(resource.RUSAGE_CHILDREN)
 result={'cpu_affinity':sorted(os.sched_getaffinity(0)),'torch_num_threads':torch_observed.get('threads'),
  'torch_num_interop_threads':torch_observed.get('interop'),'user_seconds':own.ru_utime,'system_seconds':own.ru_stime,
  'max_rss_kib':own.ru_maxrss,'child_user_seconds':child.ru_utime,'child_system_seconds':child.ru_stime,
  'largest_child_max_rss_kib':child.ru_maxrss,'process':process_status(),'memory_scope':'Separatehighwater observations;not summedsimultaneousRSS.'}
 cg=Path('/sys/fs/cgroup')
 for name in('memory.current','memory.max'):
  if(cg/name).exists():result['cgroup_'+name.replace('.','_')]=(cg/name).read_text().strip()
 if(cg/'memory.stat').exists():result['cgroup_memory_stat']={a:int(b)for a,b in(line.split()for line in(cg/'memory.stat').read_text().splitlines())}
 return result

def main():
 import argparse
 p=argparse.ArgumentParser()
 for name in('plan','admission','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--expected-plan-sha',required=True);p.add_argument('--deadline',type=float,required=True);p.add_argument('--phase',choices=('dev',),required=True);args=p.parse_args()
 if args.out.absolute()!=C.STUDY/'runs/dev':raise ValueError('EXACT_PUBLIC_DEV_OUT_REQUIRED')
 started=time.monotonic();declared_plan=C.read(args.plan);source_units=declared_plan['source_units_total'];counters=K.initial(source_units);raw={'schema_version':1,'epoch':40,'kind':A.KIND,'phase':'dev','source_checkpoint':A.SOURCE,
  'plan_sha256':args.expected_plan_sha,'status':'INITIALIZING','cases':[],'counters':counters,'model_runtime_receipts':{},
  'reader_lifecycle':[],'resources':{},'wall_seconds':None,'errors':[],'required_readout_ids':[],'completed_readout_ids':[],
  'closure_facts':{'physical_readouts_completed':0,'model_profiles_disposed':[],'native_child_closed':None,'all_forecasts_closed_before_gold':False},
  'external_evidence':{},'native_state':{},'offline_policy':{}}
 external=C.external_path(C.SCOPE/'run-external');external.mkdir(exist_ok=True);torch_observed={};audit_file=None;audit_count=0;disposed=[]
 progress_file=(external/'worker-progress-private.jsonl').open('x',encoding='utf-8')
 def progress(event):
  # Events are fixed program names and readout IDs/counts, never private source strings.
  row={'monotonic_seconds':time.monotonic(),'event':event,'counters':dict(counters),'process':process_status()}
  progress_file.write(json.dumps(row,separators=(',',':'))+'\n');progress_file.flush();os.fsync(progress_file.fileno());checkpoint(raw,args.out)
 def lifecycle(tag,event,**extra):
  row={'model_tag':tag,'event':event,'monotonic_seconds':time.monotonic(),'global_readouts_completed':counters['NLI_readouts_completed'],
   'profile_readouts_completed':counters[tag+'_forward_calls_completed'],**extra};raw['reader_lifecycle'].append(row);progress({'event':event,'model_tag':tag})
 def write_audit(private):
  nonlocal audit_count
  if audit_count:audit_file.write(',\n')
  json.dump(private,audit_file,separators=(',',':'),allow_nan=False);audit_file.flush();os.fsync(audit_file.fileno());audit_count+=1
 guard=C.load_module('e40_whole_worker_network_guard',HERE/'runtime/network_guard.py').OfflineGuard(counters,progress).install()
 def stop(sig,frame):raise TimeoutError('E40_BOUNDED_WORKER_STOP')
 signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGTERM,stop);code=0
 try:
  signal.setitimer(signal.ITIMER_REAL,max(.001,C.remaining(args.deadline)-7))
  cpu=process_status()
  if cpu['cpu_affinity']!=[0,1]or cpu.get('NoNewPrivs')!='1'or cpu.get('Seccomp')!='2':raise ValueError('WHOLE_WORKER_CPU_PREEXEC_REQUIRED')
  provisional=C.read(args.plan);C.admission(args.admission,provisional,args.expected_plan_sha,'dev');plan=C.verify_plan(args.plan,args.expected_plan_sha,'dev')
  C.verify_runtime(plan);C.owner_lock();plan['_plan_sha']=args.expected_plan_sha
  if plan['expected_operation_counters']['dev']!=K.expected(source_units):raise ValueError('FROZEN_PHYSICAL_COUNTERS_CHANGED')
  while not(args.out/'attempt.json').exists():C.remaining(args.deadline);time.sleep(.01)
  own=C.proc(os.getpid());attempt=C.read(args.out/'attempt.json')
  if not own or own['pgid']!=os.getpid()or own['sid']!=os.getpid()or attempt.get('pid')!=os.getpid()or attempt.get('startticks')!=own['ticks']:raise ValueError('WORKER_PROCESS_IDENTITY_CHANGED')
  data=C.load_module('e40_whitelist_data_loader',C.checked(plan['contractnli_data_source_path']))
  source=next(row for row in plan['external_data_assets']if row['role']=='dev_features');counters['dev_features_bank_reads']+=1
  records=data.load_private_features(source['path'],source['sha256'],plan['data_roles']['dev']);counters['selected_cases_validated']=len(records)
  if {r['id']:len(r['evidence'])for r in records}!=plan['source_units_per_case']or sum(len(r['evidence'])for r in records)!=source_units:raise ValueError('FROZEN_COMPLETE_SOURCE_UNIT_COUNT_CHANGED')
  raw['required_readout_ids']=[r['id']+'::'+arm for r in records for arm in A.ARMS]
  codec=C.load_module('e40_lossless_vector_codec',HERE/'vector_codec.py');context=C.load_module('e40_supplied_source_context',HERE/'context.py')
  native=C.load_module('e40_private_native_io',HERE/'native_io.py')
  bundle,prepared,bge_receipt=context.prepare_bundle(C,records,counters,progress,codec);raw['BGE_runtime_receipt']=bge_receipt
  native_result=native.run(C,plan,bundle,counters,progress,args.out,external,args.deadline,raw['native_state'])
  raw['external_evidence']['native_output']=C.ref(external/'dev-native-result.json',True)
  private,cases=context.orders_and_premises(records,native_result,prepared,data,counters);raw['cases']=cases
  gc.collect();guard.assert_clean()
  audit_path=external/'nli-input-audits.json';audit_file=audit_path.open('x',encoding='utf-8')
  audit_file.write(json.dumps({'schema_version':1,'epoch':40,'kind':A.KIND,'phase':'dev','source_plan_sha256':args.expected_plan_sha})[:-1]+',"readouts":[')
  score=C.load_module('e40_512_private_nli',HERE/'nli.py');profiles=C.model_profiles(plan)
  for tag in A.MODEL_ORDER:
   C.owner_lock();C.remaining(args.deadline);lifecycle(tag,'MODEL_PHASE_START')
   profile=profiles[tag];module=C.load_module('e40_original_'+tag+'_reader',C.checked(profile['reader_path']))
   reader=(module.FrozenTasksourceReader if tag=='tasksource'else module.FrozenMoritzProofReader)(C.MODEL_DIRS[tag],counters,progress)
   torch_observed={'threads':reader.torch.get_num_threads(),'interop':reader.torch.get_num_interop_threads()}
   if torch_observed!={'threads':2,'interop':1}:raise ValueError('ACTUAL_TORCH_THREAD_POLICY_FAILED')
   raw['model_runtime_receipts'][tag]=reader.runtime_checks;lifecycle(tag,'MODEL_INITIALIZATION_COMPLETED')
   for case in cases:
    item=private[case['id']];record=item['record']
    for arm in A.MODEL_ARMS[tag]:
     C.remaining(args.deadline);guard.assert_clean()
     result=score.score(reader,item['premises'][arm],record['claim'],item['orders'][arm],tag,case['id']+'::'+arm,counters,progress,write_audit)
     result['timing'].update(context_order_seconds=case['context_order_seconds'],native_query_seconds=case['native_query_seconds'],
      scope='Reader actualtokenization+NNI+privateauditwrite;ordering/query terms separate;sharedBGE/index/init excluded,notpublisherendtoend.')
     case['readouts'][arm]=result;raw['completed_readout_ids'].append(result['readout_id']);progress({'event':'PUBLIC_FORECAST_STORED','readout_id':result['readout_id']})
    if tag=='tasksource':
     ended=time.perf_counter();case['pipeline_timing']['all_readouts_completed_monotonic_seconds']=ended;case['pipeline_timing']['batch_case_span_seconds']=ended-case['pipeline_timing']['source_preparation_started_monotonic_seconds']
   unchanged=reader.unchanged();lifecycle(tag,'MODEL_READOUTS_COMPLETED',model_state_unchanged=unchanged)
   counters['model_unloads_attempted']+=1;references={'reader':weakref.ref(reader),'model':weakref.ref(reader.model),'tokenizer':weakref.ref(reader.tokenizer)}
   lifecycle(tag,'MODEL_UNLOAD_BEFORE');del reader;del module;gc.collect();dead={k+'_weakref_dead':v()is None for k,v in references.items()}
   lifecycle(tag,'MODEL_UNLOAD_AFTER_GC',**dead)
   if not all(dead.values()):raise ValueError('MODEL_OR_TOKENIZER_REMAINS_LIVE')
   counters['model_unloads_completed']+=1;counters['reader_lifecycles_completed']+=1;disposed.append(tag)
  if any(counters[k]!=v for k,v in K.expected(source_units).items())or set(raw['completed_readout_ids'])!=set(raw['required_readout_ids']):raise ValueError('FULL48_ACTUAL_FORECAST_COUNTER_INTEGRITY_FAILED')
  if counters['BGE_forward_calls_attempted']!=plan['expected_BGE_forward_calls']or counters['BGE_forward_calls_completed']!=plan['expected_BGE_forward_calls']:raise ValueError('EXACT_DECLARED_BGE_BATCH_COUNT_FAILED')
  if audit_count!=48 or disposed!=['b354','tasksource']or raw['native_state'].get('capture_complete')is not True:raise ValueError('FORECAST_PRIVATE_AUDIT_OR_LIFECYCLE_NOT_CLOSED')
  guard.assert_clean();C.owner_lock();C.remaining(args.deadline)
  raw['status']='DEV_FORECASTS_COMPLETE_NO_GOLD'
 except BaseException as error:
  code=2;raw['status']='FAILED_DEV';message=str(error)
  raw['errors'].append({'type':type(error).__name__,'message_sha256':C.text_sha(message),'code':'WORKER_FAILURE_PRIVATE_LOG_RETAINED'})
  (external/'worker-exact-error.txt').write_text(traceback.format_exc())
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGTERM,signal.SIG_IGN)
  if audit_file is not None:
   audit_file.write(']}\n');audit_file.flush();os.fsync(audit_file.fileno());audit_file.close()
  for key,name in [('nli_input_audits','nli-input-audits.json'),('native_output','dev-native-result.json'),('native_bundle','dev-native-bundle.json'),('exact_worker_error','worker-exact-error.txt')]:
   path=external/name
   if path.is_file():raw['external_evidence'][key]=C.ref(path,True)
  raw['closure_facts'].update(physical_readouts_completed=counters['NLI_readouts_completed'],required_readout_ids=raw['required_readout_ids'],completed_readout_ids=raw['completed_readout_ids'],
   model_profiles_disposed=disposed,native_child_closed=raw['native_state'].get('child_closed'),all_forecasts_closed_before_gold=raw['status']=='DEV_FORECASTS_COMPLETE_NO_GOLD',source_plan_sha256=args.expected_plan_sha)
  raw['offline_policy']={'clean':not guard.violations and counters['Python_network_operations_attempted']==0,'literal_capability_bind_closed':all(row.get('close_outcome')=='SUCCESS' and row.get('file_descriptor_after_close')==-1 for row in guard.allowed_sockets.values()),'allowed_capability_count':len(guard.allowed_sockets),'violations_count':len(guard.violations)}
  raw.update(resources=resources(torch_observed),wall_seconds=time.monotonic()-started)
  progress({'event':'WORKER_FINAL_PUBLIC_STATUS','status':raw['status']});progress_file.close()
  capture_known=(not raw['native_state'].get('helper_popen_attempted')or raw['native_state'].get('capture_complete')is True)
  if capture_known:C.put(args.out/'raw.json',raw)
  else:checkpoint(raw,args.out)
 return code
if __name__=='__main__':raise SystemExit(main())
