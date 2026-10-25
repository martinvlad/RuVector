import unittest
import finfact_input_audit as A
class InputAudit(unittest.TestCase):
 def test_merged_literal_scope(self):
  self.assertEqual(A.merged([[0,3],[3,5],[9,10],[0,0]]),[[0,5],[9,10]]);self.assertEqual([m.group()for m in A.NUMBER.finditer('Revenue USD1,200.50 in2024: +12 and −2.5, x3.')],['200.50','+12','−2.5'])
 def test_only_first_rejects_claim_loss(self):
  rec={'claim':'short claim','evidence':[{'unit_id':0,'sentence':'separate source'}]};saved={'readout_id':'toy::b354_native','model_tag':'b354','raw_native_logits':[0,0,0],'premise':'separate source','claim':'short claim','features':{'input_ids':[1,2,3],'attention_mask':[1,1,1]},'full_features':{'input_ids':[1,2,4,3],'attention_mask':[1,1,1,1]},'sequence_ids':[None,0,None],'full_sequence_ids':[None,0,1,None],'offset_mapping':[[0,0],[0,8],[0,0]],'full_offsets':[[0,0],[0,8],[0,5],[0,0]]};r={'readout_id':'toy::b354_native','model_tag':'b354','raw_native_logits':[0,0,0],'input_audit':{'ordered_unit_ids':[0]}}
  with self.assertRaisesRegex(ValueError,'WHOLE_CLAIM'):A.check_saved_input(rec,'b354_native',r,saved)
if __name__=='__main__':unittest.main()

class ReplaySuccess(unittest.TestCase):
 def test_complete_saved_pair_replays_and_offset_tamper_fails(self):
  import copy
  rec={'claim':'test','evidence':[{'unit_id':0,'sentence':'gain 24.'}]};features={'input_ids':[101,7,8,102,9,102],'attention_mask':[1]*6};a={'full_premise_sha256':A.digest('gain 24.'),'claim_sha256':A.digest('test'),'ordered_unit_ids':[0],'full_joint_tokens':6,'joint_tokens':6,'full_premise_tokens':2,'consumed_premise_tokens':2,'full_claim_tokens':1,'consumed_claim_tokens':1,'claim_complete':True,'premise_truncated':False,'full_input_features_sha256':A.digest(features),'consumed_input_features_sha256':A.digest(features),'consumed_premise_tokens_sha256':A.digest([7,8]),'consumed_claim_tokens_sha256':A.digest([9]),'full_numeric_literal_count':1,'retained_numeric_literal_count':1,'omitted_numeric_literal_count':0,'numeric_literal_coverage':1.0};r={'readout_id':'unrelated::b354_native','model_tag':'b354','raw_native_logits':[0.,0.,0.],'input_audit':a};saved={'readout_id':r['readout_id'],'model_tag':'b354','raw_native_logits':[0.,0.,0.],'premise':'gain 24.','claim':'test','features':features,'full_features':features,'sequence_ids':[None,0,0,None,1,None],'full_sequence_ids':[None,0,0,None,1,None],'offset_mapping':[[0,0],[0,4],[5,7],[0,0],[0,4],[0,0]],'full_offsets':[[0,0],[0,4],[5,7],[0,0],[0,4],[0,0]],'input_audit':a}
  self.assertEqual(A.check_saved_input(rec,'b354_native',r,saved),a);bad=copy.deepcopy(saved);bad['offset_mapping'][2]=[5,6]
  with self.assertRaisesRegex(ValueError,'COVERAGE_REPLAY'):A.check_saved_input(rec,'b354_native',r,bad)
