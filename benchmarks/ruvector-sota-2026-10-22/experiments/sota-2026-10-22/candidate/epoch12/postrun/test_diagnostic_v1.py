import copy,importlib.util,unittest
from pathlib import Path
p=Path(__file__).with_name('build_diagnostic_v1.py');s=importlib.util.spec_from_file_location('postrun',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def trace(self,logits,precision):
  probs=m.softmax(logits)
  return {'input_ids':[1,2,3],'attention_mask':[1,1,1],'token_type_ids':[0,1,1],'input_text_sha256':'same','raw_label_indices':{'entailment':0,'neutral':1,'contradiction':2},'precision':precision,'canonical_logits_E_C_N':logits,'raw_threeway_probabilities':dict(zip(m.TYPED,probs))}
 def test_offset_is_not_posterior_drift(self):
  x=m.pair(self.trace([1,2,3],'FP32'),self.trace([11,12,13],'INT8_TRAIN_DIAGNOSTIC'))
  self.assertEqual(x['raw_logits_max_absolute_difference'],10);self.assertEqual(x['centered_logits_max_absolute_difference'],0);self.assertEqual(x['posterior_total_variation'],0)
 def test_direction_and_half_ties(self):
  self.assertEqual(m.decision({'Yes':.5,'No':.5}),'No')
  x=m.pair(self.trace([5,-5,-5],'FP32'),self.trace([-5,5,-5],'INT8_TRAIN_DIAGNOSTIC'))
  self.assertFalse(x['binary_decision_agrees']);self.assertFalse(x['typed_decision_agrees']);self.assertGreater(x['posterior_total_variation'],.99)
 def test_different_feed_rejected(self):
  a=self.trace([1,2,3],'FP32');b=self.trace([1,2,3],'INT8_TRAIN_DIAGNOSTIC')
  for field in ('input_ids','attention_mask','token_type_ids','input_text_sha256','raw_label_indices'):
   c=copy.deepcopy(b);c[field]='different'
   with self.subTest(field=field),self.assertRaises(ValueError):m.pair(a,c)
 def test_wrong_precision_rejected(self):
  with self.assertRaises(ValueError):m.pair(self.trace([1,2,3],'FP32'),self.trace([1,2,3],'FP32'))
 def test_proper_scores_and_invalid_distribution(self):
  x=m.scores({'Yes':.8,'No':.2},'No');self.assertAlmostEqual(x['brier'],1.28);self.assertFalse(x['correct'])
  for p in ({'Yes':float('nan'),'No':0},{'Yes':-.1,'No':1.1},{'Yes':.2,'No':.2}):
   with self.assertRaises(ValueError):m.normalized(p)
 def test_input_role_completeness(self):
  with self.assertRaises(ValueError):m.analyze([])
if __name__=='__main__':unittest.main()
