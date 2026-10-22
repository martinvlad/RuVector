"""Pure typed answer construction; this suite never instantiates a model."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tested_cycle3_engine',Path(__file__).with_name('engine.py'));engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
Q={'type':'choice','criteria':{'a':'first','b':'second','z':'third'},'instructions':'Choose'}

class AnswerContract(unittest.TestCase):
    def test_full_empirical_distribution_preserved(self):
        proof={'rule':'synthetic','probabilities':{'a':2/3,'b':1/3,'z':0.0}}
        out=engine.apply_proof({},Q,proof);self.assertEqual(out['probabilities'],proof['probabilities']);self.assertEqual(out['choice'],'a');self.assertFalse(out['calibrated'])
    def test_equal_probability_tie_uses_official_lexical_policy(self):
        out=engine.apply_proof({},Q,{'probabilities':{'z':0,'b':.5,'a':.5}});self.assertEqual(out['choice'],'a')
    def test_malformed_distribution_rejected(self):
        for probabilities in [{'a':1.0},{'a':1.0,'b':float('nan'),'z':0},{'a':True,'b':0,'z':0},{'a':.2,'b':.2,'z':.2}]:
            with self.subTest(probabilities=probabilities),self.assertRaises(ValueError):engine.apply_proof({},Q,{'probabilities':probabilities})
    def test_original_fallback_is_copied_without_mutation(self):
        native={'type':'noul','noul':.3,'usage_note':{'a':1}};original=copy.deepcopy(native);out=engine.apply_proof(native,{'type':'noul','instructions':'x'},None);out['usage_note']['a']=2;self.assertEqual(native,original)

if __name__=='__main__':unittest.main()
