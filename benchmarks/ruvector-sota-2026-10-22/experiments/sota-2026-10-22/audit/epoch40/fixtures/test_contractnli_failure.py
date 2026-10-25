import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import contractnli_io as I
import contractnli_failure as F
import contractnli_scorer as S
class Failure(unittest.TestCase):
 def test_absent_report_never_means_zero(self):
  r=F.custody_from_report(None);self.assertIsNone(r['semantic_label_decodes']);self.assertIsNone(r['decode_attempted_tokens']);self.assertTrue(r['semantic_decode_count_uncertain'])
 def test_partial_report_retains_exact_counts_and_undefined_quality(self):
  report={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','semantic_labels_decoded':2,'decode_attempted_tokens':2,'semantic_decode_count_uncertain':False,'label_reader_calls':1,'status':'GOLD_JOIN_FAILED_FINAL_NO_RETRY'};c=F.custody_from_report(report);self.assertEqual(c['semantic_label_decodes'],2);self.assertFalse(c['semantic_decode_count_uncertain']);plan={'data_roles':{'train':[],'dev':['toy-'+str(i)for i in range(12)],'calibration':[],'confirmation':[]}};r=F.replay(plan,'1'*64,{'worker_attempts':1,'owned_live_processes_closed':True},{},c,[{'code':'SYNTHETIC_PARTIAL'}]);self.assertFalse(r['evaluation_executed']);self.assertIsNone(r['metrics']);self.assertTrue(all(x=='NOT_EVALUATED'for x in r['gate_checks'].values()));json.dumps(r,allow_nan=False)
 def test_missing_join_routes_without_calling_evaluate_or_gold(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);admission=root/'failure-admission.json';I.put(admission,{'unrelated':'metadata fixture'});ref=I.raw_ref(admission);fake={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','checks_passed':False,'dev_passed':False,'evaluation_executed':False,'status':'REJECTED_DEV_INTEGRITY'};out=root/'result.json';argv=['scorer','--mode','EVALUATE','--project',str(root),'--out',str(out),'--failure-admission',str(admission),'--expected-failure-admission-sha256',ref['sha256']]
   with patch('sys.argv',argv),patch.object(S,'evaluate')as evaluate,patch.object(F,'capture_failure',return_value=fake)as capture:S.main();evaluate.assert_not_called();capture.assert_called_once()
 def test_unknown_partial_count_stays_unknown(self):
  r={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','semantic_labels_decoded':None,'decode_attempted_tokens':3,'semantic_decode_count_uncertain':True,'label_reader_calls':1,'status':'GOLD_PROCESS_INCOMPLETE'};c=F.custody_from_report(r);self.assertIsNone(c['semantic_label_decodes']);self.assertEqual(c['decode_attempted_tokens'],3);self.assertTrue(c['semantic_decode_count_uncertain'])
if __name__=='__main__':unittest.main()
