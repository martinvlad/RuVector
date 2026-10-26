"""Independent arithmetic/source fixtures, never real DEV cases or model calls."""
import math,unittest
import e42_metrics as M
class Metrics(unittest.TestCase):
 def record(self,cid,arm,logitpair):
  physical=[]
  for i,logits in enumerate(logitpair):
   v=M.forecast(logits);physical.append({'readout_id':cid+'::'+arm+'::window:'+str(i),'model_tag':'tasksource','raw_native_logits':logits,'raw_native_probabilities':v['native_probabilities'],**{k:v[k]for k in ['probabilities_N_E_C','log_probabilities_N_E_C','canonical_argmax_index','primary_label']},'argmax_label':v['primary_label']})
  m=M.mixture([M.forecast(x)for x in logitpair]);return physical,dict(m,model_tag='tasksource',aggregation='EQUAL_WEIGHT_ARITHMETIC_PROBABILITY_MIXTURE_TWO_REAL_WINDOWS',real_window_outputs_required=2,retrieval_miss_absence_inference=False,forecast_id=cid+'::'+arm,window_readout_ids=[r['readout_id']for r in physical])
 def cohort(self):
  rows=[];labels={}
  for i in range(12):
   cid='unrelated:'+str(i);label=M.LABELS[i%3];labels[cid]=label;row={'id':cid,'document_id':i//3,'hypothesis_id':'h'+str(i%3),'window_readouts':{},'readouts':{}}
   for a in M.ARMS:
    target=label if a==M.PRIMARY or i>=3 else M.LABELS[(i+1)%3];canonical=[-3.,-3.,-3.];canonical[M.LABELS.index(target)]=3.;native=[canonical[1],canonical[0],canonical[2]];p,m=self.record(cid,a,[native,native]);row['window_readouts'][a]=p;row['readouts'][a]=m
   rows.append(row)
  return rows,labels
 def test_source_mapping_ties_and_mixture_hand_arithmetic(self):
  self.assertEqual(M.forecast([0.,0.,0.])['primary_label'],'NotMentioned');v=M.mixture([M.forecast([math.log(9),0.,0.]),M.forecast([0.,0.,math.log(9)])]);self.assertAlmostEqual(v['probabilities_N_E_C'][0],1/11);self.assertAlmostEqual(v['probabilities_N_E_C'][1],5/11);self.assertAlmostEqual(v['probabilities_N_E_C'][2],5/11);self.assertEqual(v['primary_label'],'Entailment')
 def test_stable_unclipped_underflow_no_false_clipped_NLL(self):
  v=M.mixture([M.forecast([-1000.,0.,-1000.])]*2);self.assertEqual(v['probabilities_N_E_C'][1],0);self.assertAlmostEqual(-v['log_probabilities_N_E_C'][1],1000);self.assertEqual(v['primary_label'],'NotMentioned')
 def test_actual_seventy_two_refs_and_no_mixture_tamper(self):
  rows,labels=self.cohort();out={a:M.metrics(rows,a,labels)for a in M.ARMS};self.assertEqual(out[M.PRIMARY]['correct'],12);self.assertTrue(all(M.gates(out,True).values()));self.assertEqual(len({x for a in M.ARMS for r in out[a]['scores']for x in r['window_readout_ids']}),72);rows[0]['readouts'][M.PRIMARY]['probabilities_N_E_C'][0]+=.01
  with self.assertRaises(ValueError):M.metrics(rows,M.PRIMARY,labels)
 def test_author_undefined_descriptive_only_not_class_gate(self):
  rows,labels=self.cohort();labels={r['id']:'Entailment'for r in rows};out={a:M.metrics(rows,a,labels)for a in M.ARMS};self.assertIsNone(out[M.PRIMARY]['author_EC_F1_mean']);self.assertTrue(out[M.PRIMARY]['author_undefined_metrics']);self.assertTrue(all('F1'not in k and'F1'not in k.upper()for k in M.gate_names()));self.assertEqual(out[M.PRIMARY]['N'],12)
 def test_per_hyp_macro_document_and_disagreements(self):
  rows,labels=self.cohort();v=M.descriptive(rows,labels);self.assertEqual(len(v['per_document']),4);self.assertEqual(len(v['per_hypothesis']),3);self.assertEqual(v['macro_document'][M.PRIMARY]['accuracy'],1.);self.assertEqual(v['paired_control_disagreements'][M.CONTROLS[0]]['native_only_correct'],3)
 def test_fixed_denominator_raw_enum_no_remap(self):
  rows,labels=self.cohort()
  with self.assertRaises(ValueError):M.metrics(rows[:-1],M.PRIMARY,{r['id']:labels[r['id']]for r in rows[:-1]})
  labels[rows[0]['id']]='entailment'
  with self.assertRaises(ValueError):M.metrics(rows,M.PRIMARY,labels)
if __name__=='__main__':unittest.main()
