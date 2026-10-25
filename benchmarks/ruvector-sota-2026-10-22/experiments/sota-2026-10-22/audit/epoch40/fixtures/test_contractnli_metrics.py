import json,math,unittest
import contractnli_metrics as M
class Metrics(unittest.TestCase):
 def row(self,i,pred):
  r={'id':'unrelated-fixture-'+str(i),'readouts':{}}
  logits={'NotMentioned':[0.,3.,0.],'Entailment':[3.,0.,0.],'Contradiction':[0.,0.,3.]}[pred]
  for arm in M.ARMS:
   tag='b354'if arm==M.REFERENCE else'tasksource';f=M.source_forecast(logits,tag);r['readouts'][arm]={'readout_id':r['id']+'::'+arm,'model_tag':tag,'raw_native_logits':logits,'raw_native_probabilities':f['native_probabilities'],'probabilities_N_E_C':f['probabilities'],'log_probabilities_N_E_C':f['log_probabilities'],'primary_label':f['primary_label'],'canonical_argmax_index':f['canonical_argmax_index']}
  return r
 def test_official_NEC_ties_no_threshold(self):
  self.assertEqual(M.source_forecast([0.,0.,0.],'tasksource')['primary_label'],'NotMentioned');self.assertEqual(M.source_forecast([3.,3.,0.],'b354')['primary_label'],'NotMentioned');self.assertEqual(M.source_forecast([.1,0.,0.],'tasksource')['primary_label'],'Entailment')
 def test_author_nan_is_null_and_gate_fails_notzero(self):
  rows=[self.row(i,'NotMentioned')for i in range(12)];labels={r['id']:'NotMentioned'for r in rows};m=M.metrics(rows,M.PRIMARY,labels);self.assertEqual(m['accuracy'],1);self.assertIsNone(m['author_EC_F1_mean']);self.assertIsNone(m['author_EC_F1_hmean']);self.assertEqual(m['author_helper_metrics']['precision_mean'],0);self.assertEqual(m['author_undefined_metrics']['f1_mean']['status'],'UNDEFINED_AUTHOR_NAN');json.dumps(m,allow_nan=False);results={a:m for a in M.ARMS};self.assertFalse(all(M.gates(results).values()))
 def test_nontrivial_EC_mean_distinct_three_class_macro(self):
  pairs=[('Entailment','Entailment')]*3+[('Entailment','Contradiction')]+[('Contradiction','Entailment')]*2+[('Contradiction','Contradiction'),('Contradiction','NotMentioned')]+[('NotMentioned','Contradiction')]*2+[('NotMentioned','NotMentioned')]*2;rows=[self.row(i,p)for i,(_,p)in enumerate(pairs)];labels={r['id']:pairs[i][0]for i,r in enumerate(rows)};m=M.metrics(rows,M.PRIMARY,labels);self.assertEqual(m['correct'],6);self.assertAlmostEqual(m['author_EC_F1_mean'],(2/3+1/4)/2);self.assertAlmostEqual(m['author_EC_F1_hmean'],2*(2/3)*(1/4)/(2/3+1/4))
 def test_stable_unclipped_NLL_underflow(self):
  f=M.source_forecast([0.,-1000.,-2000.],'tasksource');self.assertEqual(f['probabilities'][2],0);self.assertEqual(-f['log_probabilities'][2],2000)
  for v in [[1e20]*3,[1e38,0.,-1e38]]:self.assertTrue(all(math.isfinite(x)for x in M.source_forecast(v,'tasksource')['log_probabilities']))
 def test_full12_no_unknown_label_remap(self):
  rows=[self.row(i,'Entailment')for i in range(12)];labels={r['id']:'Entailment'for r in rows}
  with self.assertRaises(ValueError):M.metrics(rows[:-1],M.PRIMARY,labels)
  labels[rows[0]['id']]='entailment'
  with self.assertRaisesRegex(ValueError,'NO_REMAP'):M.metrics(rows,M.PRIMARY,labels)
 def test_wrong_p_or_decision_cannot_replay(self):
  row=self.row(0,'Entailment');r=row['readouts'][M.PRIMARY];r['probabilities_N_E_C'][0]+=.01
  with self.assertRaisesRegex(ValueError,'REPLAY'):M.readout_check(r,row['id'],M.PRIMARY)
 def test_gates_require_all_controls_and_gain2(self):
  base={a:{'N':12,'correct':8,'accuracy':8/12,'author_EC_F1_mean':.4,'Brier':.5,'NLL':1.}for a in M.ARMS};base[M.PRIMARY].update(correct=10,accuracy=10/12,author_EC_F1_mean=.5,Brier=.4,NLL=.9);self.assertTrue(all(M.gates(base).values()));base['tasksource_lexical']['NLL']=.8;self.assertFalse(all(M.gates(base).values()))
if __name__=='__main__':unittest.main()
