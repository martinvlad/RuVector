import copy,math,unittest
import finfact_metrics as M
class MetricsTest(unittest.TestCase):
 def row(self,i,logits=None):
  r={'id':'unrelated-toy-'+str(i),'readouts':{}}
  for a in M.ARMS:
   tag='xxlarge'if a=='xxlarge_source_order'else'b354';lg=(logits or [0.,0.,0.]);f=M.source_forecast(lg,tag);r['readouts'][a]={'readout_id':r['id']+'::'+a,'model_tag':tag,'raw_native_logits':lg,'raw_native_probabilities':f['native_probabilities'],'probabilities_E_C_N':f['probabilities'],'log_probabilities_E_C_N':f['log_probabilities'],'primary_label':f['primary_label'],'argmax_label':f['argmax_label'],'native_argmax_index':f['native_argmax_index']}
  return r
 def test_threshold_strict_order(self):
  self.assertEqual(M.ordered_label([.5,.2,.3]),'false');self.assertEqual(M.ordered_label([.50001,.2,.29999]),'true');self.assertEqual(M.ordered_label([.2,.2,.6]),'neutral');self.assertEqual(M.ordered_label([.25,.25,.5]),'false')
 def test_native_maps_and_ties(self):
  self.assertEqual(M.source_forecast([1.,1.,1.],'b354')['argmax_label'],'true');self.assertEqual(M.source_forecast([1.,1.,1.],'xxlarge')['argmax_label'],'false');self.assertEqual(M.source_forecast([0.,5.,0.],'b354')['primary_label'],'neutral');self.assertEqual(M.source_forecast([5.,0.,0.],'xxlarge')['primary_label'],'false')
 def test_stable_log_unclipped(self):
  for x in [[1e20]*3,[1e38,0.,-1e38],[0.,-1000.,-2000.]]:
   for tag in M.MAPS:
    f=M.source_forecast(x,tag);self.assertTrue(all(math.isfinite(y)for y in f['log_probabilities']));self.assertAlmostEqual(sum(f['probabilities']),1)
  f=M.source_forecast([0.,-1000.,-2000.],'b354');self.assertEqual(f['probabilities'][1],0);self.assertEqual(-f['log_probabilities'][1],2000)
 def test_observed_union_not_fixed_three(self):
  rows=[self.row(i)for i in range(12)];labels={r['id']:'false'for r in rows};m=M.metrics(rows,'b354_native',labels);self.assertEqual(m['correct'],12);self.assertEqual(m['macro_F1'],1);self.assertAlmostEqual(m['fixed_three_class_macro_F1_diagnostic'],1/3);self.assertEqual(m['official_observed_union_labels'],['false'])
 def test_confusion_zero_division(self):
  rows=[self.row(i)for i in range(12)];labels={r['id']:('true'if i<6 else'neutral')for i,r in enumerate(rows)};m=M.metrics(rows,'b354_native',labels);self.assertEqual(m['official_observed_union_labels'],['false','neutral','true']);self.assertEqual(m['macro_F1'],0);self.assertEqual(m['N'],12)
 def test_no_silent_missing_drop(self):
  rows=[self.row(i)for i in range(12)];labels={r['id']:'true'for r in rows}
  with self.assertRaises(ValueError):M.metrics(rows[:-1],'b354_native',labels)
  rows[0]['readouts']['b354_native']['primary_label']='neutral'
  with self.assertRaises(ValueError):M.metrics(rows,'b354_native',labels)
 def test_forecast_tamper(self):
  r=self.row(0);r['readouts']['b354_native']['probabilities_E_C_N'][0]+=1e-7
  with self.assertRaises(ValueError):M.readout_check(r['readouts']['b354_native'],r['id'],'b354_native')
 def test_nontrivial_official_macro_manual(self):
  pairs=[('true','true')]*3+[('true','false')]+[('false','true')]*2+[('false','false'),('false','neutral')]+[('neutral','false')]*2+[('neutral','neutral')]*2;rows=[];labels={}
  for i,(gold,pred)in enumerate(pairs):
   lg={'true':[3.,0.,0.],'false':[0.,0.,3.],'neutral':[0.,3.,0.]}[pred];r=self.row(i,lg);rows.append(r);labels[r['id']]=gold
  m=M.metrics(rows,'b354_native',labels);self.assertEqual(m['correct'],6);self.assertEqual(m['accuracy'],.5);self.assertAlmostEqual(m['macro_precision'],(3/5+1/4+2/3)/3);self.assertAlmostEqual(m['macro_recall'],.5);self.assertAlmostEqual(m['macro_F1'],(2/3+1/4+4/7)/3)
 def test_fixed_gates(self):
  base={a:{'N':12,'correct':8,'accuracy':8/12,'macro_F1':.5,'Brier':.5,'NLL':1.}for a in M.ARMS};base[M.PRIMARY].update(correct=10,accuracy=10/12,macro_F1=.6,Brier=.4,NLL=.9);self.assertTrue(all(M.gates(base).values()));base[M.PRIMARY]['NLL']=1.001;self.assertFalse(all(M.gates(base).values()))
 def test_timing_quantile(self):self.assertEqual(M.quantile([4,1,2,3],.5),2.5);self.assertAlmostEqual(M.quantile([1,2,3,4],.95),3.85)
if __name__=='__main__':unittest.main()
