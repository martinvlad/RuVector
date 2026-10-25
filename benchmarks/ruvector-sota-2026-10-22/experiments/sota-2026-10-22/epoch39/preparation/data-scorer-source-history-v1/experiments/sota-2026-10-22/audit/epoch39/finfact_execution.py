"""Independent counters, actual resource and latency checks. No inference."""
import math
import finfact_io as I
import finfact_metrics as M

def execution_audit(raw,plan,expected_source,project):
 lifecycle=lifecycle_audit(raw);model_audit=model_runtime_audit(raw);expected=I.load_ref(expected_source,project);I.require(expected['epoch']==39 and expected['kind']==I.KIND,'FROZEN_E39_COUNTER_SOURCE_REQUIRED');fixed=expected['dev'];I.require(plan['expected_operation_counters']['dev']==fixed,'PLAN_COUNTERS_DIFFER_FROM_REVIEWED_SOURCE');c=raw['counters']
 for key,want in fixed.items():I.require(type(c[key])is int and c[key]==want,'ACTUAL_COUNTER_MISMATCH:'+key)
 I.require(c['BGE_forward_calls_attempted']==c['BGE_forward_calls_completed']and type(c['BGE_forward_calls_completed'])is int and c['BGE_forward_calls_completed']>0,'REAL_COMPLETED_BGE_FORWARDS_REQUIRED');I.require(c['BGE_forward_calls_completed']==sum((len(r['source_unit_ids'])+7)//8+1 for r in raw['cases']),'EXACT_REAL_BGE_BATCH_COUNT_REQUIRED');I.require(type(c['Python_literal_loopback_capability_binds_allowed'])is int and c['Python_literal_loopback_capability_binds_allowed']in[0,1],'BOUNDED_LITERAL_LOOPBACK_ONLY');I.require(set(c)==set(fixed)|set(expected['variable_observed_counters']),'UNDECLARED_OR_MISSING_OPERATION_COUNTERS')
 wall=raw['wall_seconds'];I.require(M.finite(wall)and 0<wall<=600,'ACTUAL_WHOLE_BATCH_MAX600_SECONDS_REQUIRED');resources=raw['resources'];I.require(resources['cpu_affinity']==[0,1]and resources['torch_num_threads']==2 and resources['torch_num_interop_threads']==1,'ACTUAL_TWO_CPU_THREAD_RESOURCE_LIMIT_REQUIRED')
 for name in ['user_seconds','system_seconds','max_rss_kib']:I.require(M.finite(resources[name])and resources[name]>=0,'ACTUAL_RESOURCE_OBSERVATION_REQUIRED:'+name)
 by_arm={}
 for arm in M.ARMS:
  timings=[r['readouts'][arm]['timing']for r in raw['cases']];I.require(len(timings)==12,'FULL_TIMING_DENOMINATOR_REQUIRED');keys={'pair_tokenization_seconds','NNI_forward_seconds','reader_total_seconds'};extras={'context_order_seconds','native_query_seconds','scope'};I.require(all(set(v)==keys|extras for v in timings),'FROZEN_READOUT_LATENCY_COMPONENTS_REQUIRED');out={}
  for case,v in zip(raw['cases'],timings):I.require(v['context_order_seconds']==case['context_order_seconds']and v['native_query_seconds']==case['native_query_seconds']and type(v['scope'])is str,'SHARED_CONTEXT_QUERY_LATENCY_BINDING_REQUIRED')
  for key in sorted(keys):
   vals=[v[key]for v in timings];I.require(all(M.finite(x)and x>=0 for x in vals),'FINITE_ACTUAL_TIMING_REQUIRED');out[key]={'N':12,'p50':M.quantile(vals,.5),'p95':M.quantile(vals,.95),'sum':math.fsum(vals),'scope':'Per actual measured readout component. Shared BGE/native/model initialization and whole batch are separate; not publisher end-to-end latency.'}
  for v in timings:I.require(v['reader_total_seconds']+1e-6>=v['pair_tokenization_seconds']+v['NNI_forward_seconds'],'READOUT_TOTAL_COMPONENT_INTEGRITY')
  by_arm[arm]=out
 return {'checks_passed':True,'reader_lifecycle_audit':lifecycle,'model_runtime_audit':model_audit,'fixed_counters_checked':len(fixed),'actual_counters':c,'wall_seconds_including_initialization_and_cleanup':wall,'actual_resources':resources,'latency_by_arm':by_arm,'no_total_or_parallel_memory_inferred_from_summed_RSS':True}
def lifecycle_audit(raw):
 rows=raw['reader_lifecycle'];I.require(type(rows)is list and len(rows)==10,'TEN_OBSERVED_READER_LIFECYCLE_EVENTS_REQUIRED');events=['MODEL_PHASE_START','MODEL_INITIALIZATION_COMPLETED','MODEL_READOUTS_COMPLETED','MODEL_UNLOAD_BEFORE','MODEL_UNLOAD_AFTER_GC'];last=-math.inf
 for j,tag in enumerate(['xxlarge','b354']):
  global_counts=[0,0,12,12,12]if tag=='xxlarge'else[12,12,48,48,48];profile_counts=[0,0,12,12,12]if tag=='xxlarge'else[0,0,36,36,36]
  for i,event in enumerate(events):
   r=rows[j*5+i];I.require(r['model_tag']==tag and r['event']==event and type(r['global_readouts_completed'])is int and r['global_readouts_completed']==global_counts[i]and type(r['profile_readouts_completed'])is int and r['profile_readouts_completed']==profile_counts[i],'ACTUAL_SEQUENTIAL_MODEL_LIFECYCLE_MISMATCH');stamp=r['monotonic_seconds'];I.require(M.finite(stamp)and stamp>=last,'ACTUAL_ORDERED_LIFECYCLE_TIMESTAMPS_REQUIRED');last=stamp
   if event=='MODEL_READOUTS_COMPLETED':I.require(r['model_state_unchanged']['unchanged']is True and r['model_state_unchanged']['classifier_manifest']==raw['model_runtime_receipts'][tag]['classifier_manifest'],'FROZEN_MODEL_STATE_CHANGED')
   if event=='MODEL_UNLOAD_AFTER_GC':I.require(all(r[k]is True for k in ['reader_weakref_dead','model_weakref_dead','tokenizer_weakref_dead']),'OBSERVED_MODEL_TOKENIZER_DISPOSAL_REQUIRED')
 return {'checks_passed':True,'events_observed':10,'model_profiles_disposed':['xxlarge','b354'],'no_model_coexistence_in_observed_lifecycle':True}

def model_runtime_audit(raw):
 expected={'b354':(435064835,'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'),'xxlarge':(1566915075,'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db')};receipts=raw['model_runtime_receipts'];I.require(set(receipts)==set(expected),'BOTH_ACTUAL_MODEL_RUNTIME_RECEIPTS_REQUIRED')
 for tag,(count,weight_sha)in expected.items():
  r=receipts[tag];I.require(r['model_class']=='DebertaV2ForSequenceClassification'and r['learned_parameters']==count and type(r['learned_parameters'])is int and r['weights_sha256']==weight_sha and r['CPU_FP32']is True and r['meta_tensors_remaining']==0 and r['source_parameter_dtype']=='F16'and r['compute_dtype']=='F32'and r['all_source_values_losslessly_converted_F16_to_F32']is True and r['loading_missing_keys']==r['loading_unexpected_keys']==[]and r['no_training_or_classifier_reinitialization']is True and r['actual_model_warmup_forwards']==0 and r['tokenizer_class']=='DebertaV2TokenizerFast'and r['pair_special_tokens']==3 and r['attention']=='eager','EXACT_FROZEN_CPU_MODEL_RUNTIME_REQUIRED:'+tag)
  if tag=='xxlarge':I.require(r['weights_only']is True and r['mmap']is False and r['strict_assign']is True and r['unrestricted_pickle_allowed']is False and r['extra_pickle_safe_globals_added']==0 and r['map_location']=='cpu'and r['source_storage_offsets_verified_before_F32']is True and r['native_label_order']==['Contradiction','NotMentioned','Entailment']and r['canonical_E_C_N_from_raw']==[2,0,1],'EXACT_ORIGINAL_XXL_SAFE_LOAD_MAPPING_REQUIRED')
 return {'checks_passed':True,'actual_model_profiles':['xxlarge','b354'],'new_weight_or_model_strength_claim':False,'lineage_and_eligibility':'HOLD'}
