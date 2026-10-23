"""Actual-tokenizer synthetic source tests; zero model/native/session calls."""
from pathlib import Path
import copy
import unittest
import replay_context_v1 as R
import source_math_v1 as M


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[4]
        cls.source, cls.partition, cls.nli, cls.bge = R.setup(cls.root)
        cls.candidate = R.module(cls.source/'candidate/epoch16/context.py','auditor_context_synthetic_fixture')
        cls.h = 'Confidential Information may include verbally conveyed information.'
        cls.q = R.PREFIX+cls.h
        cls.state = ('AGREEMENT between Alpha ("Receiving Party") and Beta ("Disclosing Party"). '
            '"Confidential Information" means the listed proprietary data.\n\n' +
            '\n\n'.join('Section '+str(i)+'. Receiving Party handles oral and written material, '
                'protects source records, pays '+str(100+i)+'.25 dollars and preserves '+str(i+2)+
                '% of the relevant numbered records. This paragraph is synthetic validator text only. '
                'No legal benchmark or arithmetic truth is claimed.' for i in range(18)))
        cls.units = cls.partition(cls.state,cls.nli,cls.bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
        cls.priority = M.priority(cls.state,cls.units,cls.nli)

    def packed(self, order):
        premise,cov = self.candidate.pack(self.state,self.units,order,self.h,self.q,self.nli,
            rank_depth=min(40,len(self.units)),prelude=self.candidate.select_prelude(self.state,self.units,self.nli))
        return {'premise':premise,'coverage':cov,'hypothesis':self.h,'counterclaim':self.q,
            'ranking_ids':order,'chunk_ids':cov['selected_chunk_ids_rank_order'],
            'chunk_spans':[[self.units[i]['start'],self.units[i]['end']] for i in cov['selected_chunk_ids_rank_order']]}

    def test_joint_budget_reconstructs_multiple_rankings(self):
        orders = [list(range(min(40,len(self.units)))),
                  list(reversed(range(len(self.units))))[:40],
                  R.lexical(self.units,self.state,self.h)]
        rejected = 0
        for order in orders:
            arm = self.packed(order)
            _,positive,counter = R.verify_pack(arm,self.state,self.units,order,self.h,self.nli,self.priority)
            self.assertLessEqual(max(len(positive.ids),len(counter.ids)),512)
            self.assertEqual(arm['coverage']['joint_pair_tokens'],max(len(positive.ids),len(counter.ids)))
            rejected += sum(not x['accepted'] for x in arm['coverage']['packing_attempts'])
        self.assertGreater(rejected,0)

    def test_counterclaim_scope_drift_is_rejected(self):
        order = list(range(min(40,len(self.units))));arm = self.packed(order)
        arm['counterclaim'] = 'may not '+self.h
        with self.assertRaises(AssertionError):R.verify_pack(arm,self.state,self.units,order,self.h,self.nli,self.priority)

    def test_source_fabrication_is_rejected(self):
        order = list(range(min(40,len(self.units))));arm = self.packed(order)
        arm['premise'] += ' Fabricated assertion.'
        with self.assertRaises(AssertionError):R.verify_pack(arm,self.state,self.units,order,self.h,self.nli,self.priority)

    def test_one_pair_token_trace_tamper_is_rejected(self):
        order = list(range(min(40,len(self.units))));arm = self.packed(order)
        arm['coverage']['counterclaim_joint_pair_tokens'] += 1
        with self.assertRaises(AssertionError):R.verify_pack(arm,self.state,self.units,order,self.h,self.nli,self.priority)

    def test_numeric_surface_trace_tamper_is_rejected(self):
        order = list(range(min(40,len(self.units))));arm = self.packed(order)
        arm['coverage']['numeric_mentions'][0]['retained'] = not arm['coverage']['numeric_mentions'][0]['retained']
        with self.assertRaises(AssertionError):R.verify_pack(arm,self.state,self.units,order,self.h,self.nli,self.priority)


if __name__ == '__main__':unittest.main()
