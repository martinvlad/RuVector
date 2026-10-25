"""Fixed physical work and forbidden capabilities; no case/model operations."""
ZERO=('gold_reader_calls','semantic_gold_labels_decoded','TRAIN_input_reads','old_benchmark_DEV_reads','CONF_input_reads',
 'fits','calibration_calls','training_steps','optimizer_initializations','backward_calls','optimizer_steps',
 'paid_calls','GPU_calls','HTTP_requests','generation_calls','full104_requests',
 'Python_network_operations_attempted','Node_network_operations_attempted')

def expected():
 out={k:0 for k in ZERO}
 for name,n in [('model_initializations',2),('tokenizer_initializations',2),('model_unloads',2),
  ('BGE_initializations',1),('ORT_sessions',1),('native_helper_starts',1),('native_binary_loads',1),
  ('native_version_calls',1),('native_index_initializations',12),('native_insertions',53),('native_queries',12),('native_len_calls',24),
  ('NLI_forward_calls',48),('pair_tokenizations',48),('NLI_full_pair_tokenizer_calls',48),('NLI_claim_fit_tokenizer_calls',48),('NLI_capped_pair_tokenizer_calls',48),('xxlarge_forward_calls',12),('b354_forward_calls',36),('BGE_texts',65)]:
  out[name+'_attempted']=n;out[name+'_completed']=n
 out.update(dev_features_bank_reads=1,selected_cases_validated=12,packed_input_guard_checks=48,
  corpus_batches_attempted=1,corpus_batches_completed=1,native_hit_source_validations=53,
  NLI_readouts_completed=48,primary_decisions_completed=48,argmax_diagnostic_decisions_completed=48,
  reader_lifecycles_completed=2)
 return dict(sorted(out.items()))

def initial():
 out=dict.fromkeys(expected(),0)
 for name in ('BGE_forward_calls_attempted','BGE_forward_calls_completed'):out[name]=0
 out['Python_literal_loopback_capability_binds_allowed']=0
 return out
