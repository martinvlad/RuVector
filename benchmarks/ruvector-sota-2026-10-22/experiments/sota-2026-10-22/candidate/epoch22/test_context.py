"""Pure authored source/packing fault tests, never a benchmark qualification."""
import copy
import hashlib
import re
import sys
from types import SimpleNamespace
import unittest
import context as X


class Words:
    """Deliberately simple synthetic capacity oracle; not a model tokenizer."""
    def encode(self, text, pair=None, add_special_tokens=True):
        spans = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
        n = len(spans)
        if pair is not None: n += len(pair.split()) + 3
        elif add_special_tokens: n += 2
        return SimpleNamespace(ids=list(range(n)), offsets=spans)


class Context(unittest.TestCase):
    def setUp(self): self.nli = self.bge = Words()

    def partition(self, text): return X.partition(text, self.nli, self.bge)

    def pack(self, text, ranking=None):
        units = self.partition(text)
        ranking = list(range(len(units))) if ranking is None else ranking
        return units, X.pack(text, units, ranking, 'The recipient may disclose.', self.nli,
                             rank_depth=min(40, len(units)))

    def test_no_model_parser_runtime_imports(self):
        for name in ('torch', 'transformers', 'tokenizers', 'numpy', 'onnxruntime', 'sentencepiece'):
            self.assertNotIn(name, sys.modules)

    def test_source_full_partition_including_whitespace_tail(self):
        text = '  Opening.\n\nReceiver shall not copy; however, prior written consent permits copies.  '\
               '\n\nA 12.5% fee is due in 30 days.\n'
        units = self.partition(text)
        self.assertEqual(''.join(text[u['start']:u['end']] for u in units), text)
        self.assertEqual([u['id'] for u in units], list(range(len(units))))
        self.assertTrue(all(u['nli_tokens'] <= 160 and u['bge_tokens'] <= 256 for u in units))

    def test_adjacent_nonqualifier_sentences_not_greedily_merged(self):
        units = self.partition('First source sentence. Second source sentence. Third source sentence.')
        self.assertEqual(len(units), 3)
        self.assertEqual([u['group_id'] for u in units], [0, 1, 2])

    def test_qualifier_attaches_whole_same_paragraph_group(self):
        text = 'Recipient shall not copy. However, prior written consent permits copying. '\
               'Such copies shall be returned upon request. Separate topic.'
        units = self.partition(text); groups = X.groups(text, units)
        self.assertEqual(groups[0]['unit_ids'], [0, 1, 2])
        self.assertEqual(groups[0]['qualifier_sentence_ids'], [1, 2])
        self.assertEqual(groups[1]['unit_ids'], [3])

    def test_qualifier_never_attaches_across_paragraph(self):
        text = 'Recipient shall not copy.\n\nHowever, independent source paragraph.'
        units = self.partition(text)
        self.assertEqual([u['group_id'] for u in units], [0, 1])
        self.assertFalse(units[1]['qualifier_attached'])

    def test_authored_scope_markers_remain_literal(self):
        for marker in ['Provided that', 'Except with prior consent', 'Unless requested',
                       'Notwithstanding', 'Subject to', 'In such event', 'Only that portion',
                       'Upon request', 'At the request', '(b) However']:
            text = 'Source predicate holds. ' + marker + ' the qualification applies.'
            units = self.partition(text)
            self.assertEqual(len(X.groups(text, units)), 1, marker)
            _, (premise, _) = self.pack(text)
            self.assertEqual(premise, text)

    def test_decimal_number_not_sentence_boundary(self):
        text = 'Pay 12.5% within 30 days. Return 1,000 copies.'
        units = self.partition(text)
        self.assertEqual(len(units), 2)

    def test_long_atom_fallback_is_one_atomic_group(self):
        text = ' '.join(['word'] * 200) + '.'
        units = self.partition(text)
        self.assertGreater(len(units), 1)
        self.assertTrue(all(u['token_fallback'] for u in units))
        self.assertEqual(len(X.groups(text, units)), 1)
        _, (premise, receipt) = self.pack(text)
        self.assertEqual(premise, text)
        self.assertEqual(receipt['selected_chunk_ids_source_order'], list(range(len(units))))

    def test_oversized_group_rejected_without_partial_predicate(self):
        text = ' '.join(['large'] * 510) + '. Small fallback topic.'
        units = self.partition(text); group = X.groups(text, units)[0]
        _, (premise, receipt) = self.pack(text)
        self.assertEqual(premise, 'Small fallback topic.')
        self.assertTrue(set(group['unit_ids']).isdisjoint(receipt['selected_chunk_ids_source_order']))
        self.assertFalse(receipt['packing_attempts'][0]['accepted'])
        self.assertFalse(receipt['packing_attempts'][0]['all_group_units_admitted_together'])

    def test_ranking_maps_first_observed_member_without_scores(self):
        text = 'Main rule. However, this qualifies. Last rule.'
        units = self.partition(text)
        _, (_, r) = self.pack(text, [1, 2, 0])
        self.assertEqual(r['ranking_ids_considered'], [1, 2, 0])
        self.assertEqual(r['group_ranking_ids'], [0, 1])
        self.assertEqual(r['group_ranking_anchor_unit_ids'], [1, 2])

    def test_all_ranked_groups_before_optional_neighbor_filler(self):
        text = ' '.join(['First'] * 200) + '. ' + ' '.join(['Neighbor'] * 200) + '. '\
             + ' '.join(['Ranked'] * 200) + '.'
        units = self.partition(text)
        self.assertEqual(len(units), 6)  # 200-word atoms explicitly split at128 offsets.
        _, (premise, r) = self.pack(text, [0, 4])
        roles = [a['role'] for a in r['packing_attempts']]
        self.assertEqual(roles[:2], ['ranked-sentence-group'] * 2)
        self.assertTrue(all(a == 'optional-neighbor-group-after-all-ranked' for a in roles[2:]))
        self.assertIn('Ranked', premise)
        self.assertNotIn('Neighbor', premise)

    def test_same_exact_ranking_same_receipt_for_all_arm_names(self):
        text = 'Disclosure is limited. Except by consent, no copies are made. Another topic.'
        outcomes = [self.pack(text)[1] for arm in ('native', 'lexical', 'positional')]
        self.assertTrue(all(x == outcomes[0] for x in outcomes))

    def test_numeric_literal_spans_and_counts_retained(self):
        text = 'Pay 12.5% within 30 days. Copies number 1,000.'
        units, (premise, r) = self.pack(text)
        self.assertEqual(premise, text)
        self.assertEqual([n['text'] for n in r['numeric_mentions']], ['12.5%', '30', '1,000'])
        self.assertEqual(r['numeric_mentions_retained'], 3)
        self.assertEqual(r['numeric_mentions_omitted'], 0)
        for n in r['numeric_mentions']:
            self.assertEqual(text[slice(*n['span'])], n['text'])

    def test_group_metadata_tampering_refused(self):
        text = 'Main rule. However, exception applies.'; units = self.partition(text)
        for key, value in [('group_id', 2), ('sentence_id', 9), ('sentence_span', [0, 1]),
                           ('qualifier_attached', False), ('start', 1)]:
            bad = copy.deepcopy(units); bad[1][key] = value
            with self.assertRaises(ValueError): X.groups(text, bad)

    def test_changed_preselection_refused(self):
        text = 'Main rule. However, exception applies.'; units = self.partition(text)
        with self.assertRaises(ValueError):
            X.pack(text, units, [0, 1], 'Claim.', self.nli, rank_depth=2, prelude={})

    def test_shared_definition_admits_whole_group_only(self):
        text = '"Recipient" means the named receiver. However, only written consent modifies that term. Other topic.'
        units = self.partition(text); p = X.select_prelude(text, units, self.nli)
        self.assertEqual(p['selected_unit_ids'], [0, 1])
        self.assertEqual(p['selected_group_ids'], [0])
        self.assertLessEqual(p['priority_tokens'], 160)

    def test_overbudget_definition_group_not_partially_preselected(self):
        text = '"Recipient" means ' + ' '.join(['definition'] * 150) + '. However, '\
               + ' '.join(['qualification'] * 30) + '.'
        units = self.partition(text); p = X.select_prelude(text, units, self.nli)
        self.assertEqual(p['selected_unit_ids'], [])
        self.assertFalse(p['candidate_attempts'][0]['accepted'])

    def test_invalid_ranking_and_hypothesis_rejected(self):
        text = 'Main rule.'; units = self.partition(text)
        for ranking in ([], [0, 0], [True], [-1], [1]):
            with self.assertRaises(ValueError): X.pack(text, units, ranking, 'Claim.', self.nli, rank_depth=1)
        for h in ('', ' ', ' '.join(['claim'] * 512)):
            with self.assertRaises(ValueError): X.pack(text, units, [0], h, self.nli, rank_depth=1)

    def test_fixed_partition_budget_and_no_source_tail_clip(self):
        for limits in ({'max_units': 191}, {'target': 127}, {'nli_cap': 159}, {'bge_cap': 255}):
            with self.assertRaises(ValueError): X.partition('Text.', self.nli, self.bge, **limits)
        with self.assertRaises(ValueError): self.partition('Sentence. ' * 193)

    def test_exact_final_hashes_source_order_and_omissions(self):
        text = 'One source. Two source. Three source.'
        units, (premise, r) = self.pack(text, [2, 0])
        self.assertEqual(r['premise_sha256'], hashlib.sha256(premise.encode()).hexdigest())
        self.assertEqual(r['selected_chunk_ids_source_order'], sorted(set(r['selected_chunk_ids_source_order'])))
        self.assertEqual(sorted(r['selected_chunk_ids_source_order'] + r['omitted_chunk_ids']), list(range(len(units))))
        self.assertFalse(r['selected_evidence_truncated']); self.assertFalse(r['claim_truncated'])


if __name__ == '__main__': unittest.main()
