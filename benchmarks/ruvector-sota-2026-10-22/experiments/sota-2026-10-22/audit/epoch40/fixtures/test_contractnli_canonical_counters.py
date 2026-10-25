"""Exact canonical E40 expected-counter document, unrelated observed metadata."""
import json,unittest
from pathlib import Path
from unittest.mock import patch
import contractnli_io as I
import contractnli_metrics as M
import contractnli_execution as X
class CanonicalCounters(unittest.TestCase):
 def test_exact_canonical_document_and_undeclared_counter(self):
  p=Path(__file__).with_name('EXPECTED_COUNTERS.canonical-fixture.json');ref=I.raw_ref(p);self.assertEqual(ref['sha256'],'a4b1cbf22160f8b9b447a3836bfbd85fd68412ccb183f18c594c58526f601e99');v=json.loads(p.read_bytes());self.assertEqual(set(v),{'schema_version','epoch','kind','dev'});self.assertEqual(len(v['dev']),68)
  timing={'pair_tokenization_seconds':.01,'NNI_forward_seconds':.02,'reader_total_seconds':.04,'context_order_seconds':.1,'native_query_seconds':.01,'scope':'unrelated fixture'};sizes=[62,122,61,82,53,72,133,78,91,99,32,241];rows=[{'source_unit_ids':list(range(n)),'context_order_seconds':.1,'native_query_seconds':.01,'readouts':{a:{'timing':dict(timing)}for a in M.ARMS},'pipeline_timing':{'source_preparation_started_monotonic_seconds':1.,'all_readouts_completed_monotonic_seconds':3.,'batch_case_span_seconds':2.,'evidence_preparation_component_sum_seconds':.2,'scope':'unrelated fixture'}}for n in sizes];raw={'cases':rows,'counters':dict(v['dev'],BGE_forward_calls_attempted=158,BGE_forward_calls_completed=158,Python_literal_loopback_capability_binds_allowed=0),'wall_seconds':10.,'resources':{'cpu_affinity':[0,1],'torch_num_threads':2,'torch_num_interop_threads':1,'user_seconds':2.,'system_seconds':1.,'max_rss_kib':1234}};plan={'expected_operation_counters':{'dev':v['dev']}}
  with patch.object(X,'lifecycle_audit',return_value={'fixture':True}),patch.object(X,'model_runtime_audit',return_value={'fixture':True}):
   r=X.execution_audit(raw,plan,ref,'.');self.assertEqual(r['fixed_counters_checked'],68);raw['counters']['invented']=0
   with self.assertRaises(ValueError):X.execution_audit(raw,plan,ref,'.')
if __name__=='__main__':unittest.main()
