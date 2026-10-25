"""Independent exact-arithmetic/witness fixtures; no tokenizer, model or native calls."""
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent

def load(name,file):
    s=importlib.util.spec_from_file_location(name,file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class AuthoredOracleFixtures(unittest.TestCase):
    def test_exact_numeric_and_deontic_full_source_conclusions(self):
        # Oracle witnesses are independent of retrieval rankings and reader outputs.
        conclusions=[D('2.75')>=D('2.50'),F(18,72)==F(1,4),D('.075')*1000<=75,
            10<=11<=11 and 2<=2,D('1.80')==D('2.00'),F(210-335)==F(125),
            F(30,50)<F(3,5),2>=3]
        self.assertEqual(conclusions,[True]*4+[False]*4)
        oracle=json.loads((HERE/'engineering.oracle.json').read_text())['expected_labels']
        self.assertEqual(list(oracle.values()),['Entailment']*4+['Contradiction']*4+['NotMentioned']*4)

    def test_open_world_two_compatible_assignments_have_opposite_claim_truth(self):
        # Every world preserves all numeric facts in its full supplied excerpt.
        witnesses=[(D('11.3')>D('11.2'),D('11.1')>D('11.2')),
            (F(8,400)==F(2,100),F(8,800)==F(2,100)),
            (2==2,0==2),((240+0)==240,(240+60)==240)]
        self.assertEqual(witnesses,[(True,False)]*4)

    def test_exact_proposal_to_separate_label_free_inputs_and_oracle(self):
        proposal=json.loads((HERE/'CASE_PROPOSAL.json').read_text());bundle=json.loads((HERE/'engineering.inputs.json').read_text())
        E=load('e35_case_admission',HERE/'evidence.py');rows=E.validate_inputs(bundle,'engineering')
        self.assertEqual(len(rows),12)
        for original,row in zip(proposal['cases'],rows):
            self.assertEqual(row['document'],'\n\n'.join(original['paragraphs']))
            self.assertEqual(row['hypothesis'],original['hypothesis'])
            self.assertEqual(row['id'],original['id']);self.assertNotIn('expected_label',row)
        with self.assertRaises(ValueError):E.validate_inputs(bundle,'dev')
        mutated=json.loads(json.dumps(bundle));mutated['records'][0]['expected_label']='Entailment'
        with self.assertRaises(ValueError):E.validate_inputs(mutated,'engineering')
        mutated=json.loads(json.dumps(bundle));mutated['records'][0]['document']+=' Omitted source.'
        with self.assertRaises(ValueError):E.validate_inputs(mutated,'engineering')

if __name__=='__main__':unittest.main(verbosity=2)
