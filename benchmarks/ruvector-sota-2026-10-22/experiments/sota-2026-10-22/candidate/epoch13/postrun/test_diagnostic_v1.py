"""Engineering boundaries for saved-record math only; no model/native/data reads."""
from pathlib import Path
import importlib.util,unittest,math
HERE=Path(__file__).resolve().parent

def load(name):
 s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
d=load('build_diagnostic_v1');c=load('build_reference_coverage_v1')
class Boundaries(unittest.TestCase):
 def test_python_float_normalization(self):
  p=d.normalized({'Yes':.30000001,'No':.70000005});self.assertAlmostEqual(math.fsum(p.values()),1);self.assertTrue(all(type(x)is float for x in p.values()))
 def test_invalid_mass_rejected(self):
  for p in ({'Yes':float('nan'),'No':0},{'Yes':-.1,'No':1.1},{'Yes':0,'No':0},{'Yes':.1,'No':.1}):
   with self.subTest(p=p),self.assertRaises(ValueError):d.normalized(p)
 def test_tie_and_neutral_mass(self):
  self.assertEqual(d.decision({'Yes':.5,'No':.5}),'No');self.assertFalse(d.score({'Entailment':.01,'Contradiction':.49,'NotMentioned':.5},'Contradiction')['correct']);self.assertTrue(d.score({'Yes':.01,'No':.99},'No')['correct'])
 def test_reference_union_no_double_count(self):
  self.assertEqual(c.length([[0,10],[5,15]]),15);self.assertEqual(c.intersection([[0,10],[5,15]],[[8,12]]),4)
 def test_every_span_overlap_is_not_full_coverage(self):
  self.assertEqual(c.intersection([[0,10],[20,30]],[[5,25]]),10);self.assertEqual(c.length([[0,10],[20,30]]),20)
 def test_empty_and_invalid_spans(self):
  self.assertEqual(c.length([]),0);self.assertEqual(c.intersection([],[[1,2]]),0)
  with self.assertRaises(ValueError):c.length([[3,3]])
if __name__=='__main__':unittest.main()
