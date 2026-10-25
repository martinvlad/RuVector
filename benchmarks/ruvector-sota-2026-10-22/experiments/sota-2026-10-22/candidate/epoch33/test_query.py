"""Pure prospective query-policy fixtures; no source documents/model/native use."""
from pathlib import Path
import importlib.util
import inspect
import sys
import unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('tested_query',Path(__file__).with_name('query.py'))
Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)


class QueryPolicy(unittest.TestCase):
    def test_only_hypothesis_argument(self):
        self.assertEqual(list(inspect.signature(Q.expand).parameters),['hypothesis'])

    def test_positive_modal_action_types(self):
        fixtures=[
            ('The licensee may copy a confidential document.','copy_permission'),
            ('An employee may duplicate an internal report.','copy_permission'),
            ('The receiver may create a copy of a schedule.','copy_permission'),
            ('The client may disclose information to an adviser.','disclosure_permission'),
            ('A member may share reports with a consultant.','disclosure_permission'),
            ('The protected material may include orally delivered information.','oral_information_scope'),
            ('A policy may encompass spoken statements.','oral_information_scope')]
        for claim,expected in fixtures:
            result=Q.expand(claim)
            self.assertEqual(result['recognized_predicate'],expected)
            self.assertEqual(result['original_query'],claim)
            self.assertEqual(result['expanded_query'],claim+'\nRetrieval terms: '+' '.join(Q.TERMS[expected]))
            self.assertEqual(result['expanded_query_sha256'],Q.sha(result['expanded_query']))
            self.assertEqual(result['original_hypothesis_sha256'],Q.sha(claim))

    def test_case_and_punctuation_preserve_original(self):
        claim='RECEIVER MAY SHARE SOME REPORTS WITH THIRD-PARTIES (INCLUDING AGENTS AND ADVISERS).'
        result=Q.expand(claim)
        self.assertEqual(result['recognized_predicate'],'disclosure_permission')
        self.assertTrue(result['expanded_query'].startswith(claim+'\n'))
        self.assertNotEqual(result['original_query'],claim.lower())

    def test_no_negated_conditional_or_multiple_may_expansion(self):
        for claim in ['A receiver may not copy a report.','A receiver may copy a report if authorized.',
                'A receiver may copy a report unless prohibited.','A receiver may share a report without consent.',
                'A receiver may copy a report and may share it with a consultant.']:
            result=Q.expand(claim)
            self.assertFalse(result['expansion_applied'])
            self.assertEqual(result['expanded_query'],claim)

    def test_unicode_or_unknown_action_falls_back_without_normalization(self):
        for claim in ['A receiver ma\u017f copy a report.','The receiver may copy a r\u00e9sum\u00e9.',
                'A receiver may destroy a report.','A receiver must copy a report.',
                'A receiver might share a report with an adviser.']:
            result=Q.expand(claim)
            self.assertIsNone(result['recognized_predicate'])
            self.assertEqual(result['expanded_query'],claim)
            self.assertEqual(result['appended_terms'],[])

    def test_recognition_cannot_remove_numbers_or_conditions(self):
        claim='A receiver may create a copy of exactly 47 reports in some circumstances.'
        out=Q.expand(claim)
        self.assertEqual(out['original_query'],claim)
        self.assertIn('47',out['expanded_query'])
        self.assertIn('in some circumstances.',out['expanded_query'])

    def test_fixed_augmentation_cap_and_determinism(self):
        claim='A receiver may disclose information to an external agent.'
        first=Q.expand(claim);second=Q.expand(claim)
        self.assertEqual(first,second)
        self.assertLessEqual(len(first['expanded_query'])-len(claim),Q.MAX_ADDED_CHARACTERS)
        self.assertEqual(len(first['query_source_sha256']),64)
        self.assertEqual(len(first['query_policy_sha256']),64)


if __name__=='__main__':
    unittest.main(verbosity=2)
