"""Once-only native helper; full features/logs private, public process/counter facts."""
from pathlib import Path
import os
import subprocess
import time


def run(C,plan,bundle,counters,progress,out,external,deadline,state):
 node_guard=C.load_module('future_native_pinned_node',C.CANDIDATE/'node_runtime_guard.py')
 state['node_executable_admission']=node_guard.verify(C,plan)
 bundle['role']='dev';source=external/'dev-native-bundle.json';target=external/'dev-native-result.json'
 C.put(source,bundle)
 if source.stat().st_size>67108864:raise ValueError('NATIVE_SOURCE_FRAME_EXCEEDS64MIB')
 state.update(helper_popen_attempted=False,returned_handle=False,child_closed=None,capture_complete=False)
 C.put(out/'DEV_CORPUS_ATTEMPT_RESERVATION.json',{'schema_version':1,'epoch':47,'kind':C.KIND,'phase':'dev','role':'dev',
  'plan_sha256':plan['_plan_sha'],'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False,'at_unix':time.time()})
 counters['corpus_batches_attempted']+=1;counters['native_helper_starts_attempted']+=1
 command=node_guard.build_native_command(C,plan,source,target)
 env=C.child_env(plan);process=identity=None;stdout=stderr=b'';started=time.perf_counter();baseline=dict(counters)
 progress({'event':'NATIVE_HELPER_POPEN_BEFORE'})
 try:
  state['helper_popen_attempted']=True
  process=subprocess.Popen(command,cwd=external,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  state['returned_handle']=True;counters['native_helper_starts_completed']+=1;identity=C.proc(process.pid)
  if not identity or identity['pgid']!=os.getpgrp()or identity['sid']!=os.getsid(0):raise RuntimeError('NATIVE_SESSION_IDENTITY_FAILED')
  state['identity']=identity
  C.put(out/'dev-native-attempt.json',{'pid':process.pid,'identity':identity,'role':'dev','source_sha256':C.sha(C.CANDIDATE/'native_helper.cjs'),
   'bundle_sha256':C.sha(source),'private_io':True})
  stdout,stderr=process.communicate(timeout=min(60,C.remaining(deadline)))
 finally:
  if process is not None and process.poll()is None:
   current=C.proc(process.pid)
   if not identity or not current or current['ticks']!=identity['ticks']:raise RuntimeError('NATIVE_CLEANUP_IDENTITY_UNKNOWN')
   process.terminate()
   try:stdout,stderr=process.communicate(timeout=3)
   except subprocess.TimeoutExpired:process.kill();stdout,stderr=process.communicate(timeout=1)
  (external/'native.stdout').write_bytes(stdout);(external/'native.stderr').write_bytes(stderr)
  state['child_closed']=process.poll()is not None if process is not None else None
  state['exit_code']=process.returncode if process is not None else None
  state['wall_seconds']=time.perf_counter()-started
  for name in ['dev-native-progress.jsonl','dev-node-progress.jsonl']:
   p=external/name
   if p.exists():
    lines=[C.read_json_line(v)for v in p.read_text().splitlines()]
    if lines:
     for k,v in lines[-1].items():
      if (k.startswith('native_')or k=='Node_network_operations_attempted')and type(v)is int:counters[k]=baseline.get(k,0)+v
 if process is None or process.returncode!=0:raise RuntimeError('NATIVE_HELPER_FAILED_PRIVATE_LOG_RETAINED')
 result=C.read(target)
 expected={'epoch':47,'kind':C.KIND,'phase':'dev','role':'dev','native':True,'bundle_sha256':C.sha(source),
  'source_sha256':C.sha(C.CANDIDATE/'native_helper.cjs'),'native_binary_sha256':C.BINARY_SHA,
  'package_version':'0.1.33','platform_package_version':'0.1.31','binary_version':'2.3.0','stage':'HELPER_COMPLETED'}
 if any(result.get(k)!=v for k,v in expected.items())or result.get('errors')!=[]or len(result.get('documents',[]))!=4:raise ValueError('NATIVE_COMPLETE_RECEIPT_FAILED')
 insertions=hits=0
 for original,actual in zip(bundle['documents'],result['documents']):
  n=original['vectors']['shape'][0]
  if actual['document_id']!=original['document_id']or actual['initialized_vectors']!=n or len(actual['queries'])!=3:raise ValueError('NATIVE_DOCUMENT_RECEIPT_FAILED')
  for original_query,q in zip(original['queries'],actual['queries']):
   if (q['case_id']!=original_query['id']or q['requested_k']!=n or len(q['ids'])!=n
       or any(type(i)is not int for i in q['ids'])or set(q['ids'])!=set(range(n))or len(q['raw_hits'])!=n):raise ValueError('NATIVE_ALL_N_RECEIPT_FAILED')
   hits+=n
  insertions+=n
 fixed={'native_index_initializations_attempted':4,'native_index_initializations_completed':4,
  'native_insertions_attempted':insertions,'native_insertions_completed':insertions,'native_queries_attempted':12,'native_queries_completed':12,
  'native_len_calls_attempted':8,'native_len_calls_completed':8,'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_hit_source_validations':hits}
 if insertions!=plan['source_units_total']or any(result.get(k)!=v for k,v in fixed.items()):raise ValueError('NATIVE_EXACT_OPERATION_CAPTURE_FAILED')
 for k,v in fixed.items():counters[k]=v
 guards=[C.read_json_line(v)for v in (external/'dev-node-progress.jsonl').read_text().splitlines()]
 if not guards or guards[-1].get('event')!='NATIVE_BINARY_LOAD_AFTER'or any(guards[-1].get(k)!=v for k,v in {'native_binary_loads_attempted':1,'native_binary_loads_completed':1,'Node_network_operations_attempted':0}.items()):raise ValueError('NATIVE_GUARD_COUNTER_CAPTURE_FAILED')
 for k in('native_binary_loads_attempted','native_binary_loads_completed','Node_network_operations_attempted'):counters[k]=guards[-1][k]
 state['capture_complete']=True;counters['corpus_batches_completed']+=1;progress({'event':'NATIVE_CHILD_CLOSED_COMPLETE'})
 return result
