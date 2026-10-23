"""Synthetic source/receipt faults; no corpus, real tokenizer or inference."""
import copy
import json
from types import SimpleNamespace
import unittest
import common as C
import sentence_checks as S


class CharacterTokenizer:
    """Authored deterministic counting fixture; never a benchmark tokenizer."""
    def encode(self, text, pair=None, add_special_tokens=True):
        if pair is None:
            count = len(text) + (2 if add_special_tokens else 0)
            return SimpleNamespace(ids=list(range(count)), offsets=[(i, i + 1) for i in range(len(text))])
        return SimpleNamespace(ids=list(range(len(text) + len(pair) + 3)))


def fixture(state='Keep text. Except with consent. Other text.'):
    tokenizer = CharacterTokenizer()
    units = S.partition(state, tokenizer, tokenizer)
    return state, units, tokenizer


def full_proof():
    state, units, tokenizer = fixture('Keep text.')
    raw = {'status': 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE', 'documents': []}
    for d in range(8):
        questions = []
        for q in range(3):
            premise, coverage = S.packed(state, units, [0], 'A claim.', tokenizer)
            questions.append({'id': f'synthetic:{d}:{q}', 'hypothesis': 'A claim.',
                              'rankings': {a: [0] for a in C.M.ARMS},
                              'arms': {a: {'premise': premise, 'coverage': copy.deepcopy(coverage)} for a in C.M.ARMS}})
        raw['documents'].append({'id': d, 'state': state, 'state_sha256': S.digest(state.encode()),
            'source_units': copy.deepcopy(units), 'shared_definition_priority': S.priority(state, units, tokenizer),
            'embedding': {'exact_document_texts': [state]}, 'document_vectors': [[1.0] + [0.0] * 383],
            'query_vectors': [[1.0] + [0.0] * 383 for _ in range(3)],
            'native_trace': {'raw_native_output': {'queries': [{'ids': [0]} for _ in range(3)]}},
            'questions': questions})
    proof = S.replay_documents(raw, {}, tokenizer, tokenizer, lambda *a: {'synthetic_fixture': True})
    return raw, proof


class SourceSentenceTests(unittest.TestCase):
    def test_qualifiers_attach_transitively(self):
        a = S.atoms('No copying. Except with consent. Only upon request. Unrelated.')
        self.assertEqual([x['group_id'] for x in a], [0, 0, 0, 1])
        self.assertEqual([x['qualifier_attached'] for x in a], [False, True, True, False])

    def test_blank_paragraph_break_prevents_attachment(self):
        a = S.atoms('No copying.\n\nExcept with consent.')
        self.assertEqual([x['group_id'] for x in a], [0, 1])
        self.assertFalse(a[1]['qualifier_attached'])

    def test_one_bullet_stripped_before_fixed_marker(self):
        a = S.atoms('No copying; (a) Except with consent.')
        self.assertEqual([x['group_id'] for x in a], [0, 0])
        self.assertTrue(a[1]['qualifier_attached'])

    def test_decimal_period_is_not_sentence_boundary(self):
        a = S.atoms('Pay 10.5% within 30 days. Except upon request.')
        self.assertEqual(len(a), 2)
        self.assertEqual(a[1]['group_id'], 0)

    def test_semicolon_is_literal_boundary(self):
        a = S.atoms('No copies; general notes.')
        self.assertEqual(len(a), 2)
        self.assertEqual([x['group_id'] for x in a], [0, 1])

    def test_exact_whitespace_tail_and_unicode_spans(self):
        state, units, _ = fixture('  Café.\n\nOnly Ω permitted.  ')
        self.assertEqual(''.join(state[u['start']:u['end']] for u in units), state)
        self.assertEqual(units[-1]['end'], len(state))

    def test_oversized_atom_fallback_stays_one_atomic_group(self):
        state, units, _ = fixture('x' * 200 + '. ')
        self.assertGreater(len(units), 1)
        self.assertTrue(all(x['token_fallback'] for x in units))
        groups = S.catalog(state, units)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['unit_ids'], list(range(len(units))))

    def test_source_over192_units_rejected_without_tail_clipping(self):
        with self.assertRaises(C.M.InvalidReceipt): fixture('A. ' * 193)

    def test_boolean_unit_identity_rejected(self):
        state, units, _ = fixture(); units[0]['id'] = False
        with self.assertRaises(C.M.InvalidReceipt): S.catalog(state, units)

    def test_qualifier_metadata_tampering_rejected(self):
        state, units, _ = fixture(); units[1]['qualifier_attached'] = False
        with self.assertRaises(C.M.InvalidReceipt): S.catalog(state, units)

    def test_source_tail_omission_rejected(self):
        state, units, _ = fixture(); units.pop()
        with self.assertRaises(C.M.InvalidReceipt): S.catalog(state, units)


class AtomicPackingTests(unittest.TestCase):
    def test_best_member_rank_maps_group_once(self):
        state, units, tokenizer = fixture('No copying. Except with consent. Only upon request. Unrelated.')
        premise, c = S.packed(state, units, [2, 3, 0, 1], 'A claim.', tokenizer)
        self.assertEqual(c['group_ranking_ids'], [0, 1])
        self.assertEqual(c['group_ranking_anchor_unit_ids'], [2, 3])
        self.assertEqual(c['selected_chunk_ids_rank_order'], [0, 1, 2, 3])
        self.assertEqual(premise, state)

    def test_all_ranked_groups_before_any_optional_neighbor(self):
        state, units, tokenizer = fixture(''.join(f'Unit{i:02}. ' for i in range(43)))
        ranking = list(range(39)) + [41]
        _, c = S.packed(state, units, ranking, 'Claim.', tokenizer)
        roles = [x['role'] for x in c['packing_attempts']]
        self.assertEqual(roles[:40], ['ranked-sentence-group'] * 40)
        self.assertTrue(all(x == 'optional-neighbor-group-after-all-ranked' for x in roles[40:]))
        self.assertEqual([x['group_id'] for x in c['packing_attempts'][40:]], [39, 40, 42])

    def test_overbudget_group_rejected_entirely_no_fragment_fallback(self):
        state, units, tokenizer = fixture('x' * 600 + '. Keep 7.')
        _, c = S.packed(state, units, list(range(len(units))), 'A claim.', tokenizer)
        rejected = c['packing_attempts'][0]
        self.assertFalse(rejected['accepted'])
        self.assertFalse(rejected['all_group_units_admitted_together'])
        self.assertGreater(len(rejected['unit_ids']), 1)
        self.assertEqual(c['selected_group_ids_admission_order'], [1])
        self.assertFalse(set(rejected['unit_ids']) & set(c['selected_chunk_ids_source_order']))

    def test_whole_hypothesis_overcap_rejected(self):
        state, units, tokenizer = fixture()
        with self.assertRaises(C.M.InvalidReceipt): S.packed(state, units, list(range(len(units))), 'h' * 600, tokenizer)

    def test_incomplete_ranking_rejected(self):
        state, units, tokenizer = fixture()
        with self.assertRaises(C.M.InvalidReceipt): S.packed(state, units, [0], 'Claim.', tokenizer)

    def test_definition_priority_is_whole_group_and_claim_independent(self):
        state, units, tokenizer = fixture('"Data" means secrets. Except public material. Other text.')
        p = S.priority(state, units, tokenizer)
        self.assertEqual(p['selected_group_ids'], [0]); self.assertEqual(p['selected_unit_ids'], [0, 1])
        self.assertFalse(p['claim_dependent'])
        for claim in ('First claim.', 'Second claim.'):
            _, c = S.packed(state, units, list(range(len(units))), claim, tokenizer)
            self.assertEqual(c['definition_priority'], p)

    def test_fallback_definition_group_not_global_priority(self):
        state, units, tokenizer = fixture('"Data" means ' + 'x' * 190 + '. ')
        p = S.priority(state, units, tokenizer)
        self.assertEqual(p['selected_group_ids'], [])
        self.assertFalse(p['candidate_attempts'][0]['accepted'])

    def test_exact_numeric_retention_only(self):
        state, units, tokenizer = fixture('Pay 1,200 within 30 days. Except upon request.')
        premise, c = S.packed(state, units, list(range(len(units))), 'Claim.', tokenizer)
        self.assertEqual(premise, state)
        self.assertEqual([x['text'] for x in c['numeric_mentions']], ['1,200', '30'])
        self.assertEqual(c['numeric_mentions_retained'], 2)
        self.assertEqual(c['numeric_mentions_omitted'], 0)


class ContextProofFaultTests(unittest.TestCase):
    def test_exact_complete_synthetic_context_proof(self):
        raw, proof = full_proof(); S.token_proof_replay(raw, proof)

    def test_missing_context_proof_rejected(self):
        raw, _ = full_proof()
        with self.assertRaises(C.M.InvalidReceipt): S.token_proof_replay(raw, None)

    def test_reordered_arm_proof_rejected(self):
        raw, proof = full_proof(); proof['arms'][0], proof['arms'][1] = proof['arms'][1], proof['arms'][0]
        with self.assertRaises(C.M.InvalidReceipt): S.token_proof_replay(raw, proof)

    def test_tampered_attempt_proof_rejected(self):
        raw, proof = full_proof(); proof['arms'][0]['packing_attempts'] += 1
        with self.assertRaises(C.M.InvalidReceipt): S.token_proof_replay(raw, proof)

    def test_changed_coverage_after_context_replay_rejected(self):
        raw, proof = full_proof(); raw['documents'][0]['questions'][0]['arms'][C.M.ARMS[0]]['coverage']['packing_attempts'][0]['accepted'] = False
        with self.assertRaises(C.M.InvalidReceipt): S.token_proof_replay(raw, proof)

    def test_native_validation_not_optional(self):
        raw, proof = full_proof(); proof['all_actual_native_traces_replayed'] = False
        with self.assertRaises(C.M.InvalidReceipt): S.token_proof_replay(raw, proof)

    def test_no_context_replay_for_engineering_only(self):
        S.token_proof_replay({'status': 'REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'}, None)

    def test_science_gates_and_metrics_unchanged(self):
        old = C.read(C.ROOT / C.PREFIX / 'audit/epoch21/protocol.json'); new = C.read(C.PROTOCOL)
        for key in ('arms', 'decisions', 'engineering', 'gates', 'limits', 'numerical', 'runtime_confirmation_gate', 'tokenizer'):
            self.assertEqual(new[key], old[key], key)
        self.assertEqual((C.HERE / 'metrics.py').read_bytes(), (C.HERE.parent / 'epoch21/metrics.py').read_bytes())


if __name__ == '__main__': unittest.main()
