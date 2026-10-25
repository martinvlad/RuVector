"""Fixed physical work and forbidden capabilities; no case/model operations."""
ZERO=('gold_reader_calls','semantic_gold_labels_decoded','TRAIN_input_reads','old_benchmark_DEV_reads','CONF_input_reads',
 'fits','calibration_calls','training_steps','optimizer_initializations','backward_calls','optimizer_steps',
 'paid_calls','GPU_calls','HTTP_requests','generation_calls','full104_requests',
 'Python_network_operations_attempted','Node_network_operations_attempted')

def expected(source_units):
 if type(source_units)is not int or not 4<=source_units<=4096:raise ValueError('FROZEN_SUPPLIED_UNIT_COUNT_REQUIRED')
 out={k:0 for k in ZERO}
 for name,n in [('model_initializations',1),('tokenizer_initializations',1),('model_unloads',1),
  ('BGE_initializations',1),('ORT_sessions',1),('native_helper_starts',1),('native_binary_loads',1),
  ('native_version_calls',1),('native_index_initializations',4),('native_insertions',source_units),('native_queries',12),('native_len_calls',8),
  ('NLI_forward_calls',72),('pair_tokenizations',72),('NLI_full_pair_tokenizer_calls',72),('NLI_claim_fit_tokenizer_calls',72),('NLI_capped_pair_tokenizer_calls',72),('tasksource_forward_calls',72),('BGE_texts',source_units+12)]:
  out[name+'_attempted']=n;out[name+'_completed']=n
 out.update(dev_features_bank_reads=1,selected_cases_validated=12,packed_input_guard_checks=72,
  corpus_batches_attempted=1,corpus_batches_completed=1,native_hit_source_validations=3*source_units,
  NLI_readouts_completed=72,window_decisions_completed=72,primary_decisions_completed=36,canonical_argmax_decisions_completed=36,
  derived_forecasts_completed=36,reader_lifecycles_completed=1)
 return dict(sorted(out.items()))

def initial(source_units):
 out=dict.fromkeys(expected(source_units),0)
 for name in ('BGE_forward_calls_attempted','BGE_forward_calls_completed','packing_pair_tokenizer_calls_attempted','packing_pair_tokenizer_calls_completed'):out[name]=0
 out['Python_literal_loopback_capability_binds_allowed']=0
 return out
