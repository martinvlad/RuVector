"""Independent two-reader sequential lifecycle observations; no model imports."""
from data_common import require,finite
from model_audit import XXL_METADATA_SHA,XXL_DERIVED
PROFILES=[('b354',18),('xxlarge',36)]
EVENTS=['MODEL_PHASE_START','MODEL_INITIALIZATION_COMPLETED','MODEL_READOUTS_COMPLETED','MODEL_UNLOAD_BEFORE','MODEL_UNLOAD_AFTER_GC']
def audit_lifecycle(raw):
 init=raw['model_initializations']['xxlarge']
 require(init['source_state_tensor_count']==init['source_learned_tensor_count']==782
  and init['original_archive_metadata']['sha256']==XXL_METADATA_SHA
  and init['nonpersistent_buffers']==['deberta.embeddings.position_ids']and init['position_ids_buffer_source']==XXL_DERIVED,
  'Sequential xxlarge initialization must bind original782 F16 tensors with no source I64/position_ids and sole derived buffer')
 rows=raw['reader_lifecycle'];require(type(rows)is list and len(rows)==13,'Exactly two five-event model lifecycles plus three oracle fences required')
 require(all(type(r)is dict and finite(r['monotonic_seconds'])and r['monotonic_seconds']>=0 for r in rows),'Invalid lifecycle clock observations')
 require(all(a['monotonic_seconds']<=b['monotonic_seconds']for a,b in zip(rows,rows[1:])),'Lifecycle event time order changed')
 completed=0;observations=[]
 for index,(tag,n)in enumerate(PROFILES):
  rr=rows[index*5:index*5+5]
  require([r['event']for r in rr]==EVENTS and all(r['model_tag']==tag for r in rr),'Reader lifecycle order/profile changed')
  require([r['global_readouts_completed']for r in rr]==[completed,completed,completed+n,completed+n,completed+n]
   and[r['profile_readouts_completed']for r in rr]==[0,0,n,n,n],'Profile/global lifecycle readout counts differ')
  require(rr[2]['expected_readouts']==n and rr[2]['model_state_unchanged']==raw['model_states_unchanged'][tag],'State proof/readout count not retained before unload')
  after=rr[-1]
  require(all(after[k]is True for k in ['reader_weakref_dead','model_weakref_dead','tokenizer_weakref_dead'])
   and type(after['gc_collected_objects'])is int and after['gc_collected_objects']>=0,'Reader/module/tokenizer references remain before next model')
  status=[]
  for row in rr:
   s=row['process_status'];require(s['Cpus_allowed_list']=='0-1','Reader lifecycle escaped CPU0,1')
   require(type(s['VmRSS_bytes'])is int and s['VmRSS_bytes']>=0,'Missing observed lifecycle RSS')
   for t in s.get('observed_thread_affinities',[]):require(t['observed_affinity_within_CPU0_1']is True,'Lifecycle thread escaped CPU0,1')
   status.append({'event':row['event'],'monotonic_seconds':row['monotonic_seconds'],'process_status':s})
  observations.append({'model_tag':tag,'readouts_completed':n,'all_three_weakrefs_dead':True,'events':status})
  if index:require(rows[index*5]['monotonic_seconds']>rows[index*5-1]['monotonic_seconds'],'Next reader initialization did not follow observed previous unload')
  completed+=n
 tail=rows[10:];require([r['event']for r in tail]==['ALL_MODEL_PHASES_CLOSED_BEFORE_ORACLE','ENGINEERING_ORACLE_JOIN_BEFORE','ENGINEERING_ORACLE_JOIN_AFTER']
  and all(r['model_tag']is None and r['global_readouts_completed']==54 for r in tail),'Oracle fence order/global count changed')
 require(tail[1]['unloaded_profiles']==['b354','xxlarge']and tail[2]['joined_labels']==9,'Oracle joined before both readers unloaded or wrong label count')
 require(tail[1]['monotonic_seconds']>rows[9]['monotonic_seconds'],'Oracle join did not follow final reader cleanup')
 return {'status':'PASS_TWO_SEQUENTIAL_READERS_BEFORE_ONCE_ORACLE_JOIN','profiles':observations,'oracle_fences':tail,
  'NLI_initializations':2,'NLI_readouts':54,'oracle_joined_labels':9,
  'xxlarge_source_I64_tensors':0,'xxlarge_source_position_ids_present':False,'sole_nonpersistent_buffer':'Config-derived stock position_ids',
  'scope':'Exact primitive event/order/readout/weakref/CPU/RSS observations replayed, bound to root-approved original782-F16/no-I64 metadata. Dead Python references do not prove allocator, shared library or page-cache release; no claim that RSS must decrease.'}
