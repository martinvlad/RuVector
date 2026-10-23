"""Pure boundary fixtures, not benchmark examples or model execution."""
from pathlib import Path
import hashlib,importlib.util,json,math,tempfile,unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pure_diagnostic_e11',HERE/'build_diagnostic_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Diagnostics(unittest.TestCase):
 def test_neutral_mass_and_nonfinite_rejection(self):
  p=m.typed([0,5,-1],{'entailment':0,'neutral':1,'contradiction':2});self.assertGreater(p['NotMentioned'],.98);self.assertGreater(p['Contradiction']+p['NotMentioned'],.99)
  with self.assertRaises(ValueError):m.typed([0,float('nan'),1],{'entailment':0,'neutral':1,'contradiction':2})
 def test_preserve_native_probability_roundoff_and_tie(self):
  p={'Yes':.50000001,'No':.49999998};v=m.metrics(p,'Yes');self.assertEqual(v['brier'],(.50000001-1)**2+.49999998**2);self.assertEqual(m.metrics({'Yes':.5,'No':.5},'No')['predicted'],'No')
 def test_source_span_guards(self):
  self.assertEqual(m.merge([[1,3],[3,5],[7,8]],10),[[1,5],[7,8]])
  for a in [[[1,11]],[[-1,2]],[[True,2]],[[2,2]]]:
   with self.assertRaises(ValueError):m.merge(a,10)
 def test_percentile_and_empty_incomplete_metrics(self):
  self.assertAlmostEqual(m.percentile([1,2,3,4],.95),3.85);self.assertIsNone(m.summarize([])['accuracy']);self.assertEqual(m.summarize([])['n'],0)
 def test_active_run_refused_before_records_or_other_data_open(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);study=root/(m.PREFIX+'epoch11');study.mkdir(parents=True);(study/'study-completion.json').write_text(json.dumps({'status':'PREPARED','allowed_further_attempts_in_closed_study':0}))
   with self.assertRaisesRegex(ValueError,'closed terminal'):m.build(root)
 def test_extra_or_confirmation_annotation_identity_refused(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'records.jsonl';p.write_text('synthetic fixture\n');base={'saved_DEV_records_sha256':m.digest(p),'confirmation_records_or_labels_included':False,'records':[{'id':'dev'}]};self.assertEqual(set(m.validate_projection(base,[{'id':'dev'}],p)),{'dev'})
   bad=dict(base);bad['records']=[{'id':'dev'},{'id':'unconsumed'}]
   with self.assertRaises(ValueError):m.validate_projection(bad,[{'id':'dev'}],p)
   bad=dict(base);bad['confirmation_records_or_labels_included']=True
   with self.assertRaises(ValueError):m.validate_projection(bad,[{'id':'dev'}],p)
if __name__=='__main__':unittest.main(verbosity=2)
