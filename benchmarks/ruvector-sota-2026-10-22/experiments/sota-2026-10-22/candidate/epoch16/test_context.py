"""Exact tokenizer/source packing engineering checks, without inference."""
from pathlib import Path
import importlib.util
import unittest
from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('test_e16_context',HERE/'context.py')
C = importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
spec = importlib.util.spec_from_file_location('test_e16_context_pairing',HERE/'pairing.py')
P = importlib.util.module_from_spec(spec);spec.loader.exec_module(P)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.t = Tokenizer.from_file(str(HERE.parent/'epoch15/assets/official-deberta-v3-large/tokenizer.json'))
        self.t.no_padding();self.t.no_truncation()
        self.h=P.HYPOTHESES['nda-3'];self.q=P.counterclaim(self.h)

    def source(self):
        state='Alpha costs 42.\n\nBeta costs 17.\n\nGamma costs 5.'
        units=[];start=0
        for i,part in enumerate(state.split('\n\n')):
            end=start+len(part)
            units.append({'id':i,'start':start,'end':end,'paragraph_id':i,'token_fallback':False})
            start=end+2
        return state,units

    def test_same_source_fits_both_actual_tokenizer_pairs(self):
        state,units=self.source()
        first=state[units[0]['start']:units[0]['end']]
        cap=len(self.t.encode(first,self.q).ids)
        premise,cov=C.pack(state,units,[0,1,2],self.h,self.q,self.t,pair_cap=cap)
        self.assertLessEqual(len(self.t.encode(premise,self.h).ids),cap)
        self.assertLessEqual(len(self.t.encode(premise,self.q).ids),cap)
        self.assertEqual(cov['positive_joint_pair_tokens'],len(self.t.encode(premise,self.h).ids))
        self.assertEqual(cov['counterclaim_joint_pair_tokens'],len(self.t.encode(premise,self.q).ids))
        self.assertEqual(cov['joint_pair_tokens'],max(cov['positive_joint_pair_tokens'],cov['counterclaim_joint_pair_tokens']))
        self.assertEqual(premise,first)
        self.assertEqual(cov['numeric_mentions_retained'],1)
        self.assertEqual(cov['numeric_mentions_omitted'],2)
        self.assertFalse(cov['claim_truncated']);self.assertFalse(cov['counterclaim_truncated'])

    def test_source_order_and_number_offsets_remain_exact(self):
        state,units=self.source()
        premise,cov=C.pack(state,units,[2,0,1],self.h,self.q,self.t,pair_cap=512)
        self.assertEqual(cov['selected_chunk_ids_source_order'],[0,1,2])
        self.assertEqual(premise,state)
        self.assertEqual(cov['numeric_mentions_retained'],3)
        for m in cov['numeric_mentions']:
            self.assertEqual(state[slice(*m['span'])],m['text'])

    def test_exact_priority_rule_unchanged(self):
        state='This agreement is between Acme and Beta.\n\nThe material (\u201cConfidential Information\u201d) stays protected.\n\nKeep records for 20 days.'
        units=C.partition(state,self.t,self.t,target=32,nli_cap=64,bge_cap=256,max_units=192)
        pre=C.select_prelude(state,units,self.t)
        self.assertEqual(pre,C.BASE15.select_prelude(state,units,self.t))
        premise,cov=C.pack(state,units,list(reversed(range(len(units)))),self.h,self.q,self.t,prelude=pre)
        self.assertEqual(cov['definition_priority'],pre)
        self.assertTrue(all(a<=b for a,b in cov['selected_source_spans']))
        self.assertLessEqual(max(C.pair_counts(self.t,premise,self.h,self.q).values()),512)

    def test_shorter_positive_cannot_admit_overlong_counterclaim(self):
        state,units=self.source()
        with self.assertRaises(ValueError):
            C.pack(state,units,[0,1,2],self.h,self.q,self.t,
                   pair_cap=len(self.t.encode('',self.h).ids))


if __name__=='__main__':unittest.main()
