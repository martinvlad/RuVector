"""Pure tokenizer fixtures: no corpus, labels, runtime sessions or forwards."""
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch6_test_context', HERE / 'context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class Tokenizer:
    def __init__(self, multiplier=1):
        self.multiplier = multiplier

    def encode(self, text, pair=None, add_special_tokens=True):
        offsets = [match.span() for match in re.finditer(r'\w+|[^\w\s]', text)]
        count = len(offsets) * self.multiplier
        if pair is not None:
            count += len(re.findall(r'\w+|[^\w\s]', pair)) * self.multiplier + 3
        elif add_special_tokens:
            count += 2
        return SimpleNamespace(ids=list(range(count)), offsets=offsets)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.nli = Tokenizer()
        self.bge = Tokenizer()

    def test_complete_exact_partition_preserves_whitespace_and_unicode(self):
        state = '§1. Alpha shall retain records.\n\n  βeta may copy material; Gamma must return copies.\n'
        units = context.partition(state, self.nli, self.bge, target=6, nli_cap=10)
        self.assertEqual(''.join(state[u['start']:u['end']] for u in units), state)
        self.assertEqual(units[0]['start'], 0)
        self.assertEqual(units[-1]['end'], len(state))
        self.assertTrue(all(u['nli_tokens'] <= 10 and u['bge_tokens'] <= 256 for u in units))
        self.assertTrue(any(u['paragraph_id'] == 1 for u in units))

    def test_oversize_atom_is_explicit_full_partition(self):
        state = ' '.join('word' + str(i) for i in range(35)) + ' trailing'
        units = context.partition(state, self.nli, self.bge, target=7, nli_cap=10)
        self.assertTrue(all(u['token_fallback'] for u in units))
        self.assertEqual(''.join(state[u['start']:u['end']] for u in units), state)
        self.assertTrue(all(u['fallback_origin'] == [0, len(state)] for u in units))

    def test_bge_budget_can_force_explicit_fallback(self):
        state = ' '.join('word' + str(i) for i in range(15))
        units = context.partition(state, self.nli, Tokenizer(4), target=8, nli_cap=20, bge_cap=22)
        self.assertTrue(all(u['bge_tokens'] <= 22 for u in units))
        self.assertTrue(all(u['token_fallback'] for u in units))
        self.assertEqual(sum(u['end'] - u['start'] for u in units), len(state))

    def test_unit_cap_rejects_instead_of_dropping_tail(self):
        state = 'Alpha one.\n\nBeta two.\n\nGamma three.'
        with self.assertRaises(ValueError):
            context.partition(state, self.nli, self.bge, max_units=2)

    def test_anchor_expansion_precedes_next_anchor_and_keeps_source_order(self):
        state = 'Zero facts. One duty. Two copies. Three dates.'
        units = context.partition(state, self.nli, self.bge, target=1, nli_cap=5)
        premise, audit = context.pack(state, units, [1, 3, 0, 2], 'Copies allowed.', self.nli, pair_cap=14)
        self.assertEqual(audit['selected_chunk_ids_rank_order'], [1, 0])
        self.assertEqual(audit['selected_chunk_ids_source_order'], [0, 1])
        self.assertEqual(premise, state[units[0]['start']:units[1]['end']])
        self.assertLessEqual(audit['joint_pair_tokens'], 14)
        self.assertEqual(audit['packing_attempts'][1]['role'], 'same-paragraph-neighbor')

    def test_neighbor_expansion_never_crosses_paragraph(self):
        state = 'First rule.\n\nSecond rule.'
        units = context.partition(state, self.nli, self.bge, target=1, nli_cap=5)
        premise, audit = context.pack(state, units, [1], 'Rule.', self.nli, pair_cap=50)
        self.assertEqual(audit['selected_chunk_ids_rank_order'], [1])
        self.assertNotIn('First', premise)

    def test_exact_pair_budget_preserves_whole_hypothesis(self):
        state = 'Alpha duty. Beta exception. Gamma remedy.'
        units = context.partition(state, self.nli, self.bge, target=1, nli_cap=5)
        hypothesis = ' '.join(['hypothesis'] * 495)
        premise, audit = context.pack(state, units, [0, 1, 2], hypothesis, self.nli)
        self.assertLessEqual(len(self.nli.encode(premise, hypothesis).ids), 512)
        self.assertFalse(audit['claim_truncated'])
        self.assertFalse(audit['selected_evidence_truncated'])
        with self.assertRaises(ValueError):
            context.pack(state, units, [0], ' '.join(['claim'] * 510), self.nli)

    def test_shared_ranking_depth40_is_explicit(self):
        state = '\n\n'.join('Clause' + str(i) + '.' for i in range(45))
        units = context.partition(state, self.nli, self.bge)
        premise, audit = context.pack(state, units, list(range(45)), 'Hypothesis.', self.nli, pair_cap=5000)
        self.assertEqual(audit['ranking_ids_considered'], list(range(40)))
        self.assertNotIn('Clause44', premise)
        self.assertEqual(audit['omitted_chunk_ids'], list(range(40, 45)))

    def test_neighbor_outside_anchor_ranking_is_explicitly_audited(self):
        state = 'First unit. Second unit. Third unit.'
        units = context.partition(state, self.nli, self.bge, target=1, nli_cap=5)
        premise, audit = context.pack(state, units, [1], 'Hypothesis.', self.nli)
        self.assertEqual(audit['ranking_ids_considered'], [1])
        self.assertEqual(audit['additional_neighbor_unit_ids_inspected'], [0, 2])
        self.assertEqual(premise, state)

    def test_numeric_audit_reports_omission_without_semantic_inference(self):
        state = 'Term is 30 days.\n\nDuty lasts 24 months.'
        units = context.partition(state, self.nli, self.bge)
        premise, audit = context.pack(state, units, [0], 'Term.', self.nli)
        self.assertEqual([n['retained'] for n in audit['numeric_mentions']], [True, False])
        self.assertEqual(audit['numeric_mentions_omitted'], 1)
        self.assertNotIn('insufficient_evidence', audit)

    def test_invalid_rankings_fail(self):
        state = 'A duty.'
        units = context.partition(state, self.nli, self.bge)
        for ranking in ([], [0, 0], [-1], [True], [1]):
            with self.subTest(ranking=ranking), self.assertRaises(ValueError):
                context.pack(state, units, ranking, 'Duty.', self.nli)


if __name__ == '__main__':
    unittest.main()
