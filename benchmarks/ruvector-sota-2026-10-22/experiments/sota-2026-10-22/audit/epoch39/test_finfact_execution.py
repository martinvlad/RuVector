import copy,json,tempfile,unittest
from pathlib import Path
import finfact_io as I
import finfact_metrics as M
import finfact_execution as X
class Execution(unittest.TestCase):
 def runtime(self):
  expected={'b354':(435064835,'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'),'xxlarge':(1566915075,'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db')};out={}
  for tag,(count,sha)in expected.items():
   r={'model_class':'DebertaV2ForSequenceClassification','learned_parameters':count,'weights_sha256':sha,'CPU_FP32':True,'meta_tensors_remaining':0,'source_parameter_dtype':'F16','compute_dtype':'F32','all_source_values_losslessly_converted_F16_to_F32':True,'loading_missing_keys':[],'loading_unexpected_keys':[],'no_training_or_classifier_reinitialization':True,'actual_model_warmup_forwards':0,'tokenizer_class':'DebertaV2TokenizerFast','pair_special_tokens':3,'attention':'eager','classifier_manifest':{}}
   if tag=='xxlarge':r.update(weights_only=True,mmap=False,strict_assign=True,unrestricted_pickle_allowed=False,extra_pickle_safe_globals_added=0,map_location='cpu',source_storage_offsets_verified_before_F32=True,native_label_order=['Contradiction','NotMentioned','Entailment'],canonical_E_C_N_from_raw=[2,0,1])
   out[tag]=r
  return out
 def life(self):
  rows=[]
  for tag,j,g,p in [('xxlarge',0,[0,0,12,12,12],[0,0,12,12,12]),('b354',1,[12,12,48,48,48],[0,0,36,36,36])]:
   for i,event in enumerate(['MODEL_PHASE_START','MODEL_INITIALIZATION_COMPLETED','MODEL_READOUTS_COMPLETED','MODEL_UNLOAD_BEFORE','MODEL_UNLOAD_AFTER_GC']):
    r={'model_tag':tag,'event':event,'monotonic_seconds':j*5+i,'global_readouts_completed':g[i],'profile_readouts_completed':p[i]}
    if event=='MODEL_READOUTS_COMPLETED':r['model_state_unchanged']={'unchanged':True,'classifier_manifest':{}}
    if event.endswith('AFTER_GC'):r.update(reader_weakref_dead=True,model_weakref_dead=True,tokenizer_weakref_dead=True)
    rows.append(r)
  return rows
 def test_sequential_disposal_required(self):
  raw={'reader_lifecycle':self.life(),'model_runtime_receipts':self.runtime()};self.assertTrue(X.lifecycle_audit(raw)['checks_passed']);raw['reader_lifecycle'][4]['model_weakref_dead']=False
  with self.assertRaisesRegex(ValueError,'DISPOSAL'):X.lifecycle_audit(raw)
 def test_count_resource_timing_gate(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);expected={'epoch':39,'kind':I.KIND,'dev':{'unrelated_counter':12},'variable_observed_counters':['BGE_forward_calls_attempted','BGE_forward_calls_completed','Python_literal_loopback_capability_binds_allowed']};er=I.put(root/'pure-expected.json',expected);plan={'expected_operation_counters':{'dev':expected['dev']}};raw={'reader_lifecycle':self.life(),'model_runtime_receipts':self.runtime(),'counters':{'unrelated_counter':12,'BGE_forward_calls_attempted':24,'BGE_forward_calls_completed':24,'Python_literal_loopback_capability_binds_allowed':1},'wall_seconds':5,'resources':{'cpu_affinity':[0,1],'torch_num_threads':2,'torch_num_interop_threads':1,'user_seconds':2.,'system_seconds':.1,'max_rss_kib':123},'cases':[{'source_unit_ids':[0],'context_order_seconds':.001,'native_query_seconds':.0001,'readouts':{a:{'timing':{'pair_tokenization_seconds':.01,'NNI_forward_seconds':.02,'reader_total_seconds':.04,'context_order_seconds':.001,'native_query_seconds':.0001,'scope':'unrelatedtoyfixture'}}for a in M.ARMS}}for i in range(12)]};self.assertTrue(X.execution_audit(raw,plan,er,root)['checks_passed']);bad=copy.deepcopy(raw);bad['wall_seconds']=601
   with self.assertRaisesRegex(ValueError,'600'):X.execution_audit(bad,plan,er,root)
   bad=copy.deepcopy(raw);bad['counters']['unrelated_counter']=True
   with self.assertRaisesRegex(ValueError,'COUNTER'):X.execution_audit(bad,plan,er,root)
 def test_exact_canonical_counter_document_without_invented_variable_field(self):
  import hashlib
  p=Path(__file__).with_name('EXPECTED_COUNTERS.canonical.v2.json');body=p.read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),'837a3ac8cfde2eddefb968ab46d09e4847887b1a1e84facc5dd6c46b2f5f195b');expected=json.loads(body);self.assertEqual(set(expected),{'schema_version','epoch','kind','dev'});self.assertEqual(len(expected['dev']),68);self.assertNotIn('variable_observed_counters',expected)
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);er=I.put(root/'canonical-expected.json',expected);plan={'expected_operation_counters':{'dev':expected['dev']}};c=dict(expected['dev'],BGE_forward_calls_attempted=24,BGE_forward_calls_completed=24,Python_literal_loopback_capability_binds_allowed=1);cases=[]
   for i in range(12):cases.append({'source_unit_ids':list(range(5 if i<5 else 4)),'context_order_seconds':.001,'native_query_seconds':.0001,'readouts':{a:{'timing':{'pair_tokenization_seconds':.01,'NNI_forward_seconds':.02,'reader_total_seconds':.04,'context_order_seconds':.001,'native_query_seconds':.0001,'scope':'unrelatedtoyfixture'}}for a in M.ARMS}})
   raw={'reader_lifecycle':self.life(),'model_runtime_receipts':self.runtime(),'counters':c,'wall_seconds':5,'resources':{'cpu_affinity':[0,1],'torch_num_threads':2,'torch_num_interop_threads':1,'user_seconds':2.,'system_seconds':.1,'max_rss_kib':123},'cases':cases};report=X.execution_audit(raw,plan,er,root);self.assertTrue(report['checks_passed']);self.assertEqual(report['fixed_counters_checked'],68);self.assertEqual(sum(len(r['source_unit_ids'])for r in cases),53)
if __name__=='__main__':unittest.main()
