"""Invented source strings/capacity oracles only; no tokenizer/model/corpus imports."""
from collections import Counter
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from future_fragmentation_metadata import PROTECTED, partition_offsets, safe_cuts


class FutureSpanEngineeringChecks(unittest.TestCase):
    def oracle(self, text, overhead=3):
        return lambda start, end: len(text[start:end]) + overhead

    def test_long_unit_partitions_exactly_without_text_loss(self):
        text = 'Exact source clause; ' * 45
        self.assertGreater(len(text) + 3, 512)
        out = partition_offsets(text, self.oracle(text), max_tokens=512)
        self.assertGreater(len(out['pieces']), 1)
        self.assertEqual(''.join(text[p['start']:p['end']] for p in out['pieces']), text)
        self.assertTrue(all(p['checked_pair_tokens'] <= 512 for p in out['pieces']))

    def test_numbers_dates_currency_negation_stay_whole(self):
        text = 'Pay $1,234.50 USD on 2026-10-27; not unless 30 days. ' * 5
        out = partition_offsets(text, self.oracle(text), max_tokens=75)
        expected = Counter(m.group() for m in PROTECTED.finditer(text))
        actual = Counter(m.group() for p in out['pieces'] for m in PROTECTED.finditer(text[p['start']:p['end']]))
        self.assertEqual(actual, expected)
        self.assertEqual(sum(p['end'] - p['start'] for p in out['pieces']), len(text))

    def test_impossible_protected_numeric_atom_rejects_entire_partition(self):
        text = 'Before ' + '1' * 80 + ' USD after.'
        with self.assertRaisesRegex(ValueError, 'NO_SAFE_COMPLETE_CAPACITY_PARTITION'):
            partition_offsets(text, self.oracle(text), max_tokens=30)

    def test_no_monotonic_prefix_token_count_assumption(self):
        text = 'a b c d e '
        def count(start, end):
            if start == 0:
                return {10: 99, 8: 4, 6: 99, 4: 3, 2: 2}[end]
            return end - start + 1
        out = partition_offsets(text, count, max_tokens=5)
        self.assertEqual([(p['start'], p['end']) for p in out['pieces']], [(0, 8), (8, 10)])
        self.assertGreater(count(0, 6), count(0, 8))

    def test_capacity_count_covers_every_frozen_hypothesis(self):
        text = 'One clause; second clause; third clause.'
        frozen_hypothesis_overheads = (3, 7, 11)
        count = lambda a,b: max(len(text[a:b]) + h for h in frozen_hypothesis_overheads)
        out = partition_offsets(text, count, max_tokens=35)
        self.assertTrue(all(count(p['start'], p['end']) <= 35 for p in out['pieces']))

    def test_fragment_and_call_limits_fail_without_partial_result(self):
        text = 'word ' * 40
        with self.assertRaisesRegex(ValueError, 'FROZEN_FRAGMENT_COUNT_EXCEEDED'):
            partition_offsets(text, self.oracle(text), max_tokens=15, max_pieces=2)
        with self.assertRaisesRegex(ValueError, 'FROZEN_CAPACITY_CHECK_BUDGET_EXHAUSTED'):
            partition_offsets(text, self.oracle(text), max_tokens=15, max_checks=1)

    def test_external_cuts_cannot_split_protected_atom_or_duplicate(self):
        text = 'Pay 30 days now.'
        with self.assertRaisesRegex(ValueError, 'PROTECTED_OR_NONAUTHORITATIVE_CUT'):
            partition_offsets(text, self.oracle(text), cuts=[6, len(text)])
        with self.assertRaisesRegex(ValueError, 'EXACT_ORDERED_CUT_BOUNDARIES_REQUIRED'):
            partition_offsets(text, self.oracle(text), cuts=[4, 4, len(text)])

    def test_no_cut_before_combining_mark_or_next_to_joiner(self):
        text = 'A;\u0301 B;\u200dC; end.'
        cuts = safe_cuts(text)
        self.assertNotIn(2, cuts)
        self.assertNotIn(6, cuts)
        out = partition_offsets(text, self.oracle(text), max_tokens=30)
        self.assertTrue(out['exact_all_source_characters_once'])

    def test_coverage_never_promises_semantics_or_benchmark_success(self):
        text = 'If one clause holds; then another may apply.'
        out = partition_offsets(text, self.oracle(text), max_tokens=35)
        self.assertFalse(out['semantic_context_preservation_guaranteed'])
        self.assertFalse(out['benchmark_accuracy_or_generalization_measured'])
        self.assertTrue(out['original_source_not_rewritten'])


if __name__ == '__main__':
    unittest.main()
