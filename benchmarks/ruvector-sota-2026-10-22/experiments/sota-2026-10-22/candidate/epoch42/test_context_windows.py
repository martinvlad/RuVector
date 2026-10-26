"""Only invented, disjoint inputs; no model/tokenizer/native/data imports."""
import importlib.util
import math
from pathlib import Path
import unittest


def load(name):
    spec=importlib.util.spec_from_file_location('pure_e42_'+name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


C=load('context_windows');M=load('mixture')


class ContextTests(unittest.TestCase):
    def test_exact_partition_decimal_abbreviation_quotes_unicode(self):
        text='Audit Alloy Inc. owes 12.50 USD.  "A party may act!"\n\nIt may not disclose; provided consent is absent. 尾'
        rows=C.sentence_catalog(text)
        self.assertEqual(''.join(r['sentence']for r in rows),text)
        self.assertEqual(len(rows),4)
        self.assertTrue(rows[0]['sentence'].startswith('Audit Alloy Inc. owes 12.50 USD.'))
        self.assertIn('provided consent is absent.',rows[2]['sentence'])
        self.assertEqual(rows[-1]['end'],len(text))
        self.assertEqual([r['start']for r in rows],[0,*[r['end']for r in rows[:-1]]])

    def test_neighbors_whole_group_budget_and_complement(self):
        rows=C.sentence_catalog('Alpha. Beta. Gamma. Delta. Epsilon.')
        seen=[]
        def count(text,claim):
            seen.append((text,claim));return 3+200*text.count('.')
        result=C.build_windows(rows,[0,1,2,3,4],'Unchanged claim',count)
        self.assertEqual(result['windows'][0]['selected_unit_ids'],[0,1])
        self.assertEqual(result['windows'][1]['selected_unit_ids'],[3,4])
        self.assertEqual(result['union_selected_unit_ids'],[0,1,3,4])
        self.assertEqual(result['packing_pair_tokenizer_calls'],len(seen))
        self.assertTrue(all(claim=='Unchanged claim'for _,claim in seen))
        self.assertTrue(any(x['status']=='WHOLE_GROUP_SKIPPED_TOKEN_OVERFLOW'for x in result['windows'][0]['selection_receipts']))
        for window in result['windows']:
            self.assertLessEqual(window['joint_tokens'],512)
            self.assertEqual(window['span_splits'],0)
            self.assertFalse(window['premise_truncated'])

    def test_duplicate_requires_second_actual_readout(self):
        rows=C.sentence_catalog('Entire short source.')
        result=C.build_windows(rows,[0],'One claim',lambda premise,claim:6)
        self.assertEqual(result['duplicate_window_count'],1)
        self.assertEqual(result['windows'][0]['premise_sha256'],result['windows'][1]['premise_sha256'])
        with self.assertRaisesRegex(ValueError,'TWO_REAL'):
            M.two_window_mixture([[math.log(.3),math.log(.4),math.log(.3)]])

    def test_no_fitting_group_and_claim_overflow_fail(self):
        rows=C.sentence_catalog('Large alpha. Large beta.')
        with self.assertRaisesRegex(ValueError,'NO_COMPLETE_NEIGHBOR_GROUP'):
            C.build_windows(rows,[0,1],'Claim',lambda premise,claim:900 if premise else 4)
        with self.assertRaisesRegex(ValueError,'CLAIM_CANNOT_FIT'):
            C.build_windows(rows,[0,1],'Claim',lambda premise,claim:513)

    def test_bad_offsets_rank_types_caps_and_no_source_split(self):
        rows=C.sentence_catalog('Source one. Source two.')
        for order in [[0,0],[True,1]]:
            with self.assertRaises(ValueError):C.build_windows(rows,order,'Claim',lambda a,b:5)
        bad=[dict(row)for row in rows];bad[1]['start']+=1
        with self.assertRaisesRegex(ValueError,'NONCONTIGUOUS'):C.validate_spans(bad)
        with self.assertRaisesRegex(ValueError,'NO_SPLITTING'):
            C.sentence_catalog('x'*(C.MAX_UNIT_BYTES+1))

    def test_lexical_tie_source_first(self):
        rows=C.sentence_catalog('Alpha prior. Beta prior. Gamma unrelated.')
        self.assertEqual(C.lexical_order(rows,'prior'),[0,1,2])


class MixtureTests(unittest.TestCase):
    def test_linear_pool_conflict_is_not_forced_neutral(self):
        result=M.two_window_mixture([[math.log(.1),math.log(.8),math.log(.1)],
            [math.log(.1),math.log(.1),math.log(.8)]])
        for actual,expected in zip(result['probabilities_N_E_C'],[.1,.45,.45]):self.assertAlmostEqual(actual,expected)
        self.assertEqual(result['primary_label'],'Entailment')
        self.assertFalse(result['retrieval_miss_absence_inference'])

    def test_stable_underflow_and_canonical_first_ties(self):
        result=M.two_window_mixture([[0.,-1000.,-1001.],[0.,-1000.,-1001.]])
        self.assertAlmostEqual(result['log_probabilities_N_E_C'][1],-1000.)
        tie=M.two_window_mixture([[math.log(.5),math.log(.5),-1000.]]*2)
        self.assertEqual(tie['primary_label'],'NotMentioned')

    def test_reject_nonfinite_or_unnormalized(self):
        for rows in [[[0.,0.,0.]]*2,[[math.nan,-1.,-2.]]*2]:
            with self.assertRaises(ValueError):M.two_window_mixture(rows)


if __name__=='__main__':unittest.main()
