"""Synthetic engineering checks only, never benchmark generalization."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch15_context_engineering', HERE / 'context.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


class CharacterTokenizer:
    def encode(self, text, pair=None, add_special_tokens=True):
        n = len(text) + (len(pair) if pair is not None else 0) + ((3 if pair is not None else 2) if add_special_tokens else 0)
        return SimpleNamespace(ids=list(range(n)), offsets=[(i, i + 1) for i in range(len(text))])


def document(parts):
    state = ''.join(parts)
    units, start = [], 0
    for i, part in enumerate(parts):
        units.append({'id': i, 'start': start, 'end': start + len(part),
                      'paragraph_id': i, 'token_fallback': False})
        start += len(part)
    return state, units


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.t = CharacterTokenizer()

    def test_whole_definition_priority_and_source_exactness(self):
        state, units = document(['First clause.\n\n', '"Recipient" means Acme.\n\n', 'Keep all records.'])
        prelude = C.select_prelude(state, units, self.t)
        self.assertEqual(prelude['selected_unit_ids'], [1])
        premise, cov = C.pack(state, units, [2, 0, 1], 'A whole claim.', self.t, prelude=prelude)
        self.assertEqual(premise, state)
        self.assertEqual(cov['selected_source_spans'], [[0, len(state)]])
        self.assertFalse(cov['definition_priority']['literal_first_text_guaranteed'])

    def test_over160_unit_skipped_whole(self):
        text = '"Recipient" means ' + 'x' * 170
        state, units = document([text, 'Other source.'])
        prelude = C.select_prelude(state, units, self.t)
        self.assertEqual(prelude['selected_unit_ids'], [])
        self.assertEqual(prelude['candidate_attempts'][0]['span'], [0, len(text)])
        self.assertFalse(prelude['candidate_attempts'][0]['accepted'])

    def test_explicit_named_parentheses_curly_quote_hyphen(self):
        state, units = document(['The parties protect material (“Non–Public Information”).'])
        prelude = C.select_prelude(state, units, self.t)
        self.assertEqual(prelude['selected_unit_ids'], [0])
        self.assertIn('explicit-quoted-named-term-parenthetical', prelude['candidate_attempts'][0]['triggers'])

    def test_quoted_shall_include_is_explicit_source_marker(self):
        state, units = document(['"Protected Material" shall include all listed records.'])
        self.assertEqual(C.select_prelude(state, units, self.t)['selected_unit_ids'], [0])

    def test_role_name_outside_parenthesis_does_not_infer_alias(self):
        state, units = document(['Vendor may inspect the archive.'])
        self.assertEqual(C.select_prelude(state, units, self.t)['selected_unit_ids'], [])

    def test_initial_marker_after2048_not_admitted(self):
        state, units = document(['x' * 2048, 'Agreement between Acme and Beta.'])
        self.assertEqual(C.select_prelude(state, units, self.t)['selected_unit_ids'], [])

    def test_initial_marker_must_itself_be_in_window(self):
        state, units = document(['x' * 2040, 'x' * 16 + ' Agreement between Acme and Beta.'])
        self.assertEqual(C.select_prelude(state, units, self.t)['selected_unit_ids'], [])

    def test_priority_claim_budget_conflict_fails_closed(self):
        state, units = document(['"Recipient" means Acme.'])
        with self.assertRaisesRegex(ValueError, 'priority'):
            C.pack(state, units, [0], 'x' * 80, self.t, pair_cap=90)

    def test_priority_shared_across_retrieval_rankings(self):
        state, units = document(['"Recipient" means Acme.\n\n', 'Rule one.\n\n', 'Rule two.'])
        p = C.select_prelude(state, units, self.t)
        results = [C.pack(state, units, rank, 'claim', self.t, prelude=p)[1]
                   for rank in ([0, 1, 2], [2, 1, 0], [1, 0, 2])]
        self.assertTrue(all(x['definition_priority'] == p for x in results))

    def test_altered_shared_priority_rejected(self):
        state, units = document(['"Recipient" means Acme.'])
        p = C.select_prelude(state, units, self.t)
        p['selected_unit_ids'] = []
        with self.assertRaisesRegex(ValueError, 'differs'):
            C.pack(state, units, [0], 'claim', self.t, prelude=p)

    def test_fallback_fragment_never_promoted_to_definition(self):
        state, units = document(['"Recipient" means Acme.'])
        units[0]['token_fallback'] = True
        self.assertEqual(C.select_prelude(state, units, self.t)['selected_unit_ids'], [])

    def test_tokenization_only_displacement_and_numbers(self):
        state, units = document(['"Recipient" means Acme Co.\n\n',
                                 'Use only for Project Orion at $5 per day.\n\n',
                                 'Destroy all copies after 20 days.\n\n'])
        _, cov = C.pack(state, units, [1, 2, 0], 'the claim', self.t, pair_cap=80)
        base = cov['no_priority_counterfactual']
        self.assertEqual(base['status'], 'TOKENIZATION_ONLY')
        self.assertEqual(base['model_forwards'], 0)
        self.assertIn(1, base['displaced_unit_ids'])
        self.assertIn(0, base['introduced_unit_ids'])
        self.assertEqual(cov['numeric_mentions_retained'], 1)
        self.assertEqual(cov['numeric_mentions_omitted'], 1)

    def test_no_definition_reproduces_exact_plain_packing(self):
        state, units = document(['First rule.\n\n', 'Second rule.'])
        got, audit = C.pack(state, units, [1, 0], 'claim', self.t)
        expected, old = C.BASE.pack(state, units, [1, 0], 'claim', self.t)
        self.assertEqual(got, expected)
        self.assertEqual(audit['selected_source_spans'], old['selected_source_spans'])
        self.assertEqual(audit['no_priority_counterfactual']['displaced_unit_ids'], [])

    def test_unicode_whitespace_partition_conserves_every_character(self):
        state = 'α\t“秘密” shall remain protected.\r\n\r\nSecond; third.  '
        units = C.partition(state, self.t, self.t, target=32, nli_cap=64, bge_cap=128)
        self.assertEqual(''.join(state[u['start']:u['end']] for u in units), state)
        self.assertEqual(units[0]['start'], 0)
        self.assertEqual(units[-1]['end'], len(state))


if __name__ == '__main__':
    unittest.main()
