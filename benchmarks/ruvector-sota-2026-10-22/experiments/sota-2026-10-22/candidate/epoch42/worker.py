"""One private-input DEV forecast batch:72 real windows/36 derived forecasts, no gold capability invoked."""
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
sp=importlib.util.spec_from_file_location('e42_worker_common',HERE/'runtime/common.py');C=importlib.util.module_from_spec(sp);sp.loader.exec_module(C)
A=C.load_module('e42_science_constants',HERE/'algorithm.py');K=C.load_module('e42_counter_definitions',HERE/'counters.py')


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
 if not C.SOURCE_BINDINGS_READY:raise RuntimeError('E42_TEMPLATE_PENDING_BINDINGS_NO_ACTUAL_MODES')
 if args.out.absolute()!=C.STUDY/'runs/dev':raise ValueError('EXACT_PUBLIC_DEV_OUT_REQUIRED')
 started=time.monotonic();declared_plan=C.read(args.plan);source_units=declared_plan['source_units_total'];counters=K.initial(source_units);raw={'schema_version':1,'epoch':42,'kind':A.KIND,'phase':'dev','source_checkpoint':A.SOURCE,
  'plan_sha256':args.expected_plan_sha,'status':'INITIALIZING','cases':[],'counters':counters,'model_runtime_receipts':{},
  'reader_lifecycle':[],'resources':{},'wall_seconds':None,'errors':[],'required_readout_ids':[],'completed_readout_ids':[],'required_forecast_ids':[],'completed_forecast_ids':[],
  'closure_facts':{'derived_forecasts_completed':0,'physical_readouts_completed':0,'model_profiles_disposed':[],'native_child_closed':None,'all_forecasts_closed_before_gold':False},
  'external_evidence':{},'native_state':{},'offline_policy':{}}
 external=C.external_path(C.SCOPE/'run-external');external.mkdir(exist_ok=True);torch_observed={};audit_file=None;packing_file=None;audit_count=0;disposed=[]
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
 guard=C.load_module('e42_whole_worker_network_guard',HERE/'runtime/network_guard.py').OfflineGuard(counters,progress).install()
 def stop(sig,frame):raise TimeoutError('E42_BOUNDED_WORKER_STOP')
 signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGTERM,stop);code=0
 try:
  signal.setitimer(signal.ITIMER_REAL,max(.001,C.remaining(args.deadline)-7))
  cpu=process_status()
  if cpu['cpu_affinity']!=[0,1]or cpu.get('NoNewPrivs')!='1'or cpu.get('Seccomp')!='2':raise ValueError('WHOLE_WORKER_CPU_PREEXEC_REQUIRED')
  provisional=C.read(args.plan);C.admission(args.admission,provisional,args.expected_plan_sha,'dev');plan=C.verify_plan(args.plan,args.expected_plan_sha,'dev')
  raw['runtime_asset_verification']=C.verify_runtime(plan);C.owner_lock();plan['_plan_sha']=args.expected_plan_sha
  if plan['expected_operation_counters']['dev']!=K.expected(source_units):raise ValueError('FROZEN_PHYSICAL_COUNTERS_CHANGED')
  while not(args.out/'attempt.json').exists():C.remaining(args.deadline);time.sleep(.01)
  own=C.proc(os.getpid());attempt=C.read(args.out/'attempt.json')
  if not own or own['pgid']!=os.getpid()or own['sid']!=os.getpid()or attempt.get('pid')!=os.getpid()or attempt.get('startticks')!=own['ticks']:raise ValueError('WORKER_PROCESS_IDENTITY_CHANGED')
  data=C.load_module('e42_whitelist_data_loader',C.checked(plan['features_source_path']))
  source=next(row for row in plan['external_data_assets']if row['role']=='dev_features');counters['dev_features_bank_reads']+=1
  records=data.load_private_features(source['path'],source['sha256'],plan['data_roles']['dev']);counters['selected_cases_validated']=len(records)
  documents={r['document_id']:r['evidence']for r in records}
  if (len(documents)!=4 or {r['id']:len(r['evidence'])for r in records}!=plan['source_units_per_case']
      or sum(len(rows)for rows in documents.values())!=source_units):raise ValueError('FROZEN_UNIQUE_FOUR_DOC_SOURCE_UNIT_COUNT_CHANGED')
  raw['required_readout_ids']=[r['id']+'::'+arm+'::window:'+str(w)for r in records for arm in A.ARMS for w in range(2)]
  raw['required_forecast_ids']=[r['id']+'::'+arm for r in records for arm in A.ARMS];raw['completed_forecast_ids']=[]
  codec=C.load_module('e42_lossless_vector_codec',HERE/'vector_codec.py');context=C.load_module('e42_supplied_source_context',HERE/'context.py')
  native=C.load_module('e42_private_native_io',HERE/'native_io.py')
  bundle,prepared,bge_receipt=context.prepare_bundle(C,records,counters,progress,codec);raw['BGE_runtime_receipt']=bge_receipt
  native_result=native.run(C,plan,bundle,counters,progress,args.out,external,args.deadline,raw['native_state'])
  raw['external_evidence']['native_output']=C.ref(external/'dev-native-result.json',True)
  private,cases=context.orders_and_premises(C,records,native_result,prepared);raw['cases']=cases
  gc.collect();guard.assert_clean()
  audit_path=external/'nli-input-audits.json';audit_file=audit_path.open('x',encoding='utf-8')
  audit_file.write(json.dumps({'schema_version':1,'epoch':42,'kind':A.KIND,'phase':'dev','source_plan_sha256':args.expected_plan_sha})[:-1]+',"readouts":[')
  score=C.load_module('e42_512_private_nli',HERE/'nli.py');profiles=C.model_profiles(plan)
  windows=C.load_module('e42_frozen_context_windows',HERE/'context_windows.py');mixture=C.load_module('e42_fixed_mixture',HERE/'mixture.py');coverage=C.load_module('e42_span_coverage_audit',HERE/'coverage_audit.py')
  packing_path=external/'packing-input-audits.jsonl';packing_file=packing_path.open('x',encoding='utf-8')
  for tag in A.MODEL_ORDER:
   C.owner_lock();C.remaining(args.deadline);lifecycle(tag,'MODEL_PHASE_START')
   profile=profiles[tag];module=C.load_module('e42_original_'+tag+'_reader',C.checked(profile['reader_path']))
   reader=module.FrozenTasksourceReader(C.MODEL_DIRS[tag],counters,progress)
   torch_observed={'threads':reader.torch.get_num_threads(),'interop':reader.torch.get_num_interop_threads()}
   if torch_observed!={'threads':2,'interop':1}:raise ValueError('ACTUAL_TORCH_THREAD_POLICY_FAILED')
   raw['model_runtime_receipts'][tag]=reader.runtime_checks;lifecycle(tag,'MODEL_INITIALIZATION_COMPLETED')
   for case in cases:
    item=private[case['id']];record=item['record'];item['packed']={}
    for arm in A.ARMS:
     packing_started=time.perf_counter();before=counters['packing_pair_tokenizer_calls_completed'];packing_lookup={}
     def pair_count(premise,claim):
      C.remaining(args.deadline);counters['packing_pair_tokenizer_calls_attempted']+=1
      features=reader.tokenizer(premise,text_pair=claim,add_special_tokens=True,padding=False,truncation=False,
       return_attention_mask=True,return_token_type_ids=False)
      counters['packing_pair_tokenizer_calls_completed']+=1
      saved={'case_id':record['id'],'arm':arm,'ordinal':counters['packing_pair_tokenizer_calls_completed'],
       'premise_sha256':C.text_sha(premise),'claim_sha256':C.text_sha(claim),
       'features':{k:list(features[k])for k in('input_ids','attention_mask')}}
      saved['joint_tokens']=len(saved['features']['input_ids']);saved['features_sha256']=score.digest(saved['features'])
      saved['tokenization_policy']='FULL_UNTRUNCATED_PAIR_COMPLETE_CLAIM_ADD_SPECIAL_TOKENS_NO_PADDING_NO_TOKEN_TYPE_IDS'
      key=(saved['premise_sha256'],saved['claim_sha256']);receipt={'joint_tokens':saved['joint_tokens'],'features_sha256':saved['features_sha256']}
      if key in packing_lookup and packing_lookup[key]!=receipt:raise ValueError('REPEATED_PACKING_INPUT_FEATURES_CHANGED')
      packing_lookup[key]=receipt
      packing_file.write(json.dumps(saved,separators=(',',':'))+'\n');packing_file.flush();os.fsync(packing_file.fileno())
      return len(features['input_ids'])
     packed=windows.build_windows(record['evidence'],item['orders'][arm],record['claim'],pair_count)
     if packed['packing_pair_tokenizer_calls']!=counters['packing_pair_tokenizer_calls_completed']-before:raise ValueError('PACKING_TOKENIZER_RECEIPT_COUNT_FAILED')
     for window in packed['windows']:
      lookup=packing_lookup[(window['premise_sha256'],C.text_sha(record['claim']))]
      if lookup['joint_tokens']!=window['joint_tokens']:raise ValueError('PACKING_FINAL_EXACT_TOKEN_RECEIPT_MISSING_OR_CHANGED')
      window['packing_features_sha256']=lookup['features_sha256']
      data.assert_packed_input(record['claim'],window['premise']);counters['packed_input_guard_checks']+=1
      window['coverage_audit']=coverage.audit(record['evidence'],window['selected_unit_ids'])
     packed['union_coverage_audit']=coverage.audit(record['evidence'],packed['union_selected_unit_ids'])
     packed['packing_seconds']=time.perf_counter()-packing_started;item['packed'][arm]=packed
     case['context_windows'][arm]={k:([{a:b for a,b in w.items()if a!='premise'}for w in v]if k=='windows'else v)for k,v in packed.items()}
   progress({'event':'ALL72_PACKED_INPUT_GUARDS_COMPLETE_BEFORE_ANY_NLI'})
   for case in cases:
    item=private[case['id']];record=item['record']
    for arm in A.ARMS:
     results=[]
     for window in item['packed'][arm]['windows']:
      C.remaining(args.deadline);guard.assert_clean();readout_id=case['id']+'::'+arm+'::window:'+str(window['window_index'])
      result=score.score(reader,window['premise'],record['claim'],window['selected_unit_ids'],tag,readout_id,counters,progress,write_audit)
      if (result['input_audit']['premise_truncated']or result['input_audit']['joint_tokens']!=window['joint_tokens']
          or result['input_audit']['consumed_input_features_sha256']!=window['packing_features_sha256']):raise ValueError('PACKED_WHOLE_SPAN_TOKEN_FEATURE_INTEGRITY_FAILED')
      results.append(result);raw['completed_readout_ids'].append(readout_id);case['window_readouts'][arm]=results
      progress({'event':'PUBLIC_WINDOW_FORECAST_STORED','readout_id':readout_id})
     derived=mixture.two_window_mixture([row['log_probabilities_N_E_C']for row in results])
     derived.update(forecast_id=case['id']+'::'+arm,model_tag=tag,window_readout_ids=[row['readout_id']for row in results],
      timing={'two_window_reader_total_seconds':sum(row['timing']['reader_total_seconds']for row in results),
       'two_window_NNI_forward_seconds':sum(row['timing']['NNI_forward_seconds']for row in results),
       'packing_seconds':item['packed'][arm]['packing_seconds'],'context_order_seconds':case['context_order_seconds'],
       'native_query_seconds':case['native_query_seconds'],'scope':'Actual two-window reader component sum plus separate packing/order/query; excludes shared init/BGE/index/queue, not isolated end-to-end or publisher timing.'})
     case['readouts'][arm]=derived;counters['derived_forecasts_completed']+=1;counters['primary_decisions_completed']+=1;counters['canonical_argmax_decisions_completed']+=1
     raw['completed_forecast_ids'].append(derived['forecast_id']);progress({'event':'PUBLIC_DERIVED_FORECAST_STORED','forecast_id':derived['forecast_id']})
    ended=time.perf_counter();case['pipeline_timing']['all_readouts_completed_monotonic_seconds']=ended;case['pipeline_timing']['batch_case_span_seconds']=ended-case['pipeline_timing']['source_preparation_started_monotonic_seconds']
   unchanged=reader.unchanged();lifecycle(tag,'MODEL_READOUTS_COMPLETED',model_state_unchanged=unchanged)
   counters['model_unloads_attempted']+=1;references={'reader':weakref.ref(reader),'model':weakref.ref(reader.model),'tokenizer':weakref.ref(reader.tokenizer)}
   lifecycle(tag,'MODEL_UNLOAD_BEFORE');del reader;del module;gc.collect();dead={k+'_weakref_dead':v()is None for k,v in references.items()}
   lifecycle(tag,'MODEL_UNLOAD_AFTER_GC',**dead)
   if not all(dead.values()):raise ValueError('MODEL_OR_TOKENIZER_REMAINS_LIVE')
   counters['model_unloads_completed']+=1;counters['reader_lifecycles_completed']+=1;disposed.append(tag)
  if any(counters[k]!=v for k,v in K.expected(source_units).items())or set(raw['completed_readout_ids'])!=set(raw['required_readout_ids']):raise ValueError('FULL72_WINDOW36_DERIVED_COUNTER_INTEGRITY_FAILED')
  if counters['BGE_forward_calls_attempted']!=plan['expected_BGE_forward_calls']or counters['BGE_forward_calls_completed']!=plan['expected_BGE_forward_calls']:raise ValueError('EXACT_DECLARED_BGE_BATCH_COUNT_FAILED')
  if (audit_count!=72 or disposed!=['tasksource']or counters['packing_pair_tokenizer_calls_attempted']!=counters['packing_pair_tokenizer_calls_completed']
      or set(raw['completed_forecast_ids'])!=set(raw['required_forecast_ids']))or raw['native_state'].get('capture_complete')is not True:raise ValueError('FORECAST_PRIVATE_AUDIT_OR_LIFECYCLE_NOT_CLOSED')
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
  if packing_file is not None:packing_file.flush();os.fsync(packing_file.fileno());packing_file.close()
  for key,name in [('packing_input_audits','packing-input-audits.jsonl'),('nli_input_audits','nli-input-audits.json'),('native_output','dev-native-result.json'),('native_bundle','dev-native-bundle.json'),('exact_worker_error','worker-exact-error.txt')]:
   path=external/name
   if path.is_file():raw['external_evidence'][key]=C.ref(path,True)
  raw['closure_facts'].update(derived_forecasts_completed=counters['derived_forecasts_completed'],required_forecast_ids=raw.get('required_forecast_ids',[]),completed_forecast_ids=raw.get('completed_forecast_ids',[]),physical_readouts_completed=counters['NLI_readouts_completed'],required_readout_ids=raw['required_readout_ids'],completed_readout_ids=raw['completed_readout_ids'],
   model_profiles_disposed=disposed,native_child_closed=raw['native_state'].get('child_closed'),all_forecasts_closed_before_gold=raw['status']=='DEV_FORECASTS_COMPLETE_NO_GOLD',source_plan_sha256=args.expected_plan_sha)
  raw['offline_policy']={'clean':not guard.violations and counters['Python_network_operations_attempted']==0,'literal_capability_bind_closed':all(row.get('close_outcome')=='SUCCESS' and row.get('file_descriptor_after_close')==-1 for row in guard.allowed_sockets.values()),'allowed_capability_count':len(guard.allowed_sockets),'violations_count':len(guard.violations)}
  raw.update(resources=resources(torch_observed),wall_seconds=time.monotonic()-started)
  progress({'event':'WORKER_FINAL_PUBLIC_STATUS','status':raw['status']});progress_file.close()
  capture_known=(not raw['native_state'].get('helper_popen_attempted')or raw['native_state'].get('capture_complete')is True)
  if capture_known:C.put(args.out/'raw.json',raw)
  else:checkpoint(raw,args.out)
 return code
if __name__=='__main__':raise SystemExit(main())
