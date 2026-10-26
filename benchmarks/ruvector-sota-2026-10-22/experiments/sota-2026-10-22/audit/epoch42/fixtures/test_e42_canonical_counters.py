"""Actual SOURCE counter document; fabricated observed resource/timing metadata."""
import json,unittest
from pathlib import Path
import e42_qualification as Q
F=Q.F;M=Q.M
class CanonicalCounter(unittest.TestCase):
 def test_exact_actual_table_and_nonexistent_variable_field_regression(self):
  path=Path(__file__).with_name('test_fixtures')/'EXPECTED_COUNTERS.canonical.json';ref=F.ref(path);self.assertEqual(ref['sha256'],'519fa2681201729c28d58249650e605bbe244077acfe9b1c4dd9693c38aa734d');v=json.loads(path.read_bytes());self.assertEqual(len(v['dev']),68);self.assertNotIn('variable_observed_counters',v);self.assertEqual(set(v['observed_variable_counter_keys']),Q.VARIABLE_KEYS);model={'model_class':'DebertaV2ForSequenceClassification','learned_parameters':435064835,'weights_sha256':'534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc','CPU_FP32':True,'meta_tensors_remaining':0,'source_parameter_dtype':'F32','compute_dtype':'F32','all_source_values_preserved_exactly':True,'loading_missing_keys':[],'loading_unexpected_keys':[],'no_training_or_classifier_reinitialization':True,'actual_model_warmup_forwards':0,'tokenizer_class':'DebertaV2TokenizerFast','pair_special_tokens':3,'attention':'eager','classifier_manifest':{'unrelated':'fixture'}};life=[]
  for i,event in enumerate(['MODEL_PHASE_START','MODEL_INITIALIZATION_COMPLETED','MODEL_READOUTS_COMPLETED','MODEL_UNLOAD_BEFORE','MODEL_UNLOAD_AFTER_GC']):
   count=0 if i<2 else 72;r={'model_tag':'tasksource','event':event,'global_readouts_completed':count,'profile_readouts_completed':count,'monotonic_seconds':i+1.}
   if i==2:r['model_state_unchanged']={'unchanged':True,'classifier_manifest':model['classifier_manifest']}
   if i==4:r.update(reader_weakref_dead=True,model_weakref_dead=True,tokenizer_weakref_dead=True)
   life.append(r)
  cases=[]
  for _ in range(12):cases.append({'context_windows':{a:{'packing_pair_tokenizer_calls':4,'packing_seconds':.001}for a in M.ARMS},'window_readouts':{a:[{'timing':{'pair_tokenization_seconds':.01,'NNI_forward_seconds':.02,'reader_total_seconds':.04}}for _ in range(2)]for a in M.ARMS},'readouts':{a:{'timing':{'two_window_reader_total_seconds':.08,'two_window_NNI_forward_seconds':.04}}for a in M.ARMS},'pipeline_timing':{'source_preparation_started_monotonic_seconds':1.,'all_readouts_completed_monotonic_seconds':3.,'batch_case_span_seconds':2.}})
  raw={'reader_lifecycle':life,'model_runtime_receipts':{'tasksource':model},'cases':cases,'counters':dict(v['dev'],BGE_forward_calls_attempted=35,BGE_forward_calls_completed=35,packing_pair_tokenizer_calls_attempted=144,packing_pair_tokenizer_calls_completed=144,Python_literal_loopback_capability_binds_allowed=0),'wall_seconds':10.,'resources':{'cpu_affinity':[0,1],'torch_num_threads':2,'torch_num_interop_threads':1,'user_seconds':1.,'system_seconds':.1,'max_rss_kib':1234}};plan={'expected_counters_source':ref,'expected_operation_counters':{'dev':v['dev']},'source_units_total':175,'expected_BGE_forward_calls':35};r=Q.execution_audit(raw,plan,'.');self.assertEqual(r['fixed_counters_checked'],68);self.assertEqual(r['latency_by_arm'][M.PRIMARY]['two_window_reader_total_seconds']['N'],12);raw['counters']['undeclared_extra']=0
  with self.assertRaises(ValueError):Q.execution_audit(raw,plan,'.')
if __name__=='__main__':unittest.main()
