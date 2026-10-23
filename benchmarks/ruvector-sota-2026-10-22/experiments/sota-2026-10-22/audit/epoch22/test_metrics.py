"""Pure arithmetic and receipt-fault tests, not corpus measurements."""
import copy
import json
import math
import unittest
import metrics as m


def forward(p):
    logits = [math.log(p['Entailment']) if p['Entailment'] else -1000,
              math.log(p['NotMentioned']) if p['NotMentioned'] else -1000,
              math.log(p['Contradiction']) if p['Contradiction'] else -1000]
    p = m.softmax(logits)
    return {'raw_logits': logits, 'typed_probabilities': p, 'typed_prediction': m.prediction(p),
            'binary_probabilities': {'Yes': p['Entailment'], 'No': p['Contradiction'] + p['NotMentioned']},
            'binary_prediction': 'Yes' if p['Entailment'] >= .5 else 'No'}


def rows():
    out = []
    for d in range(8):
        for i, gold in enumerate(m.ORDER):
            primary = forward({x: .98 if x == gold else .01 for x in m.ORDER})
            control = forward({x: 1/3 for x in m.ORDER})
            out.append({'question_id': f'{d}:{i}', 'document_id': d, 'typed_gold': gold,
                        'arms': {m.ARMS[0]: primary, m.ARMS[1]: copy.deepcopy(control), m.ARMS[2]: copy.deepcopy(control)}})
    return out


class ProbabilityTests(unittest.TestCase):
    def test_source_label_mapping(self):
        self.assertEqual(m.prediction(m.softmax([20, 0, 0])), 'Entailment')
        self.assertEqual(m.prediction(m.softmax([0, 20, 0])), 'NotMentioned')
        self.assertEqual(m.prediction(m.softmax([0, 0, 20])), 'Contradiction')

    def test_stable_large_logits(self):
        p = m.softmax([1000, 999, 998])
        self.assertAlmostEqual(sum(p.values()), 1)
        self.assertGreater(p['Entailment'], p['NotMentioned'])

    def test_tie_order_canonical_not_raw(self):
        self.assertEqual(m.prediction(m.softmax([0, 0, 0])), 'Entailment')
        self.assertEqual(m.prediction(m.softmax([-10, 0, 0])), 'Contradiction')

    def test_binary_threshold_separate_from_argmax(self):
        f = forward({'Entailment': .4, 'Contradiction': .3, 'NotMentioned': .3})
        self.assertEqual(f['typed_prediction'], 'Entailment')
        self.assertEqual(f['binary_prediction'], 'No')
        self.assertEqual(m.replay_forward(f), f['typed_probabilities'])

    def test_binary_half_tie_yes(self):
        f = forward({'Entailment': .5, 'Contradiction': .25, 'NotMentioned': .25})
        self.assertEqual(f['binary_prediction'], 'Yes')

    def test_unknown_class_rejected(self):
        with self.assertRaises(m.InvalidReceipt): m.probabilities({'E': 1, 'C': 0, 'N': 0})

    def test_mass_outside_tolerance_rejected(self):
        with self.assertRaises(m.InvalidReceipt): m.probabilities({'Entailment': .4, 'Contradiction': .3, 'NotMentioned': .3000001})

    def test_negative_probability_rejected(self):
        with self.assertRaises(m.InvalidReceipt): m.probabilities({'Entailment': 1.01, 'Contradiction': -.01, 'NotMentioned': 0})

    def test_nonfinite_rejected(self):
        for value in [math.nan, math.inf, -math.inf, True, '0.5']:
            with self.subTest(value=value):
                with self.assertRaises(m.InvalidReceipt): m.softmax([value, 0, 0])

    def test_raw_cardinality_rejected(self):
        for value in [[], [0, 0], [0, 0, 0, 0], {'0': 0}]:
            with self.subTest(value=value):
                with self.assertRaises(m.InvalidReceipt): m.softmax(value)

    def test_logit_mismatch_rejected(self):
        f = forward({'Entailment': .8, 'Contradiction': .1, 'NotMentioned': .1}); f['raw_logits'] = [0, 0, 0]
        with self.assertRaises(m.InvalidReceipt): m.replay_forward(f)

    def test_typed_decision_mismatch_rejected(self):
        f = forward({'Entailment': .8, 'Contradiction': .1, 'NotMentioned': .1}); f['typed_prediction'] = 'Contradiction'
        with self.assertRaises(m.InvalidReceipt): m.replay_forward(f)

    def test_wrong_binary_marginal_rejected(self):
        f = forward({'Entailment': .8, 'Contradiction': .1, 'NotMentioned': .1}); f['binary_probabilities']['No'] = .1
        with self.assertRaises(m.InvalidReceipt): m.replay_forward(f)

    def test_binary_decision_mismatch_rejected(self):
        f = forward({'Entailment': .8, 'Contradiction': .1, 'NotMentioned': .1}); f['binary_prediction'] = 'No'
        with self.assertRaises(m.InvalidReceipt): m.replay_forward(f)


class MetricsTests(unittest.TestCase):
    def test_uniform_categorical_brier_and_nll(self):
        p = {x: 1/3 for x in m.ORDER}; b, n = m.proper_loss(p, 'Entailment')
        self.assertAlmostEqual(b, 2/3); self.assertAlmostEqual(n, math.log(3))

    def test_zero_gold_probability_not_clipped(self):
        p = {'Entailment': 0, 'Contradiction': .5, 'NotMentioned': .5}
        self.assertEqual(m.proper_loss(p, 'Entailment'), (1.5, math.inf))
        self.assertEqual(m.json_safe({'NLL': math.inf}), {'NLL': {'nonfinite': '+Infinity'}})

    def test_known_strong_metric(self):
        result = m.metrics(rows(), m.ARMS[0], True)
        self.assertEqual(result['correct'], 24)
        self.assertAlmostEqual(result['Brier'], .0006)
        self.assertAlmostEqual(result['NLL'], -math.log(.98))
        self.assertEqual(result['by_class']['NotMentioned'], {'n': 8, 'correct': 8})

    def test_binary_metric_uses_entailment_marginal(self):
        result = m.metrics(rows(), m.ARMS[1], False)
        self.assertEqual(result['correct'], 16)
        self.assertAlmostEqual(result['NLL'], -(math.log(1/3) + 2*math.log(2/3))/3)

    def test_latency_percentile_literal(self):
        self.assertEqual(m.percentile([1, 2, 3], .95), 2.9)
        self.assertEqual(m.percentile([2], .95), 2)

    def test_empty_metric_rejected(self):
        with self.assertRaises(m.InvalidReceipt): m.metrics([], m.ARMS[0])

    def test_exact_identity_success(self):
        r = rows(); self.assertTrue(m.validate_identities(r, [x['question_id'] for x in r], list(range(8))))

    def test_duplicate_question_rejected(self):
        r = rows(); expected = [x['question_id'] for x in r]; r[1]['question_id'] = r[0]['question_id']
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, expected, list(range(8)))

    def test_reordered_question_rejected(self):
        r = rows(); expected = [x['question_id'] for x in r]; r[0], r[1] = r[1], r[0]
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, expected, list(range(8)))

    def test_document_substitution_rejected(self):
        r = rows(); r[0]['document_id'] = 99
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_swapped_document_assignments_rejected(self):
        r = rows(); r[0]['document_id'], r[3]['document_id'] = r[3]['document_id'], r[0]['document_id']
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_extra_arm_rejected(self):
        r = rows(); r[0]['arms']['oracle'] = r[0]['arms'][m.ARMS[0]]
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_bool_document_substitution_rejected(self):
        r = rows()
        for row in r:
            if row['document_id'] == 1: row['document_id'] = True
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_float_document_substitution_rejected(self):
        r = rows()
        for row in r:
            if row['document_id'] == 1: row['document_id'] = 1.0
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_string_document_substitution_rejected(self):
        r = rows()
        for row in r:
            if row['document_id'] == 1: row['document_id'] = '1'
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], list(range(8)))

    def test_duplicate_expected_documents_rejected(self):
        r = rows()
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [x['question_id'] for x in r], [0,1,2,3,4,5,6,6])

    def test_nonstring_question_substitution_rejected(self):
        r = rows(); r[0]['question_id'] = 0
        with self.assertRaises(m.InvalidReceipt): m.validate_identities(r, [str(x['question_id']) for x in r], list(range(8)))


class GateTests(unittest.TestCase):
    def test_meaningful_dev_gain_passes(self):
        g = m.gate(rows()); self.assertTrue(g['passed']); self.assertFalse(g['champion_promotion_allowed'])

    def test_meaningful_confirmation_ci_gain_passes(self):
        g = m.gate(rows(), confirmation=True); self.assertTrue(g['passed'])
        self.assertTrue(all(v['accuracy']['ci95'][0] > 0 for v in g['confirmation_intervals'].values()))

    def test_equal_accuracy_cannot_pass(self):
        r = rows()
        for row in r:
            row['arms'][m.ARMS[1]] = copy.deepcopy(row['arms'][m.ARMS[0]])
        g = m.gate(r); self.assertFalse(g['passed'])
        self.assertFalse(g['checks']['typed:' + m.ARMS[1] + ':accuracy_gain_at_least_two_correct'])

    def test_all_contradiction_cannot_pass_class_guard(self):
        r = rows()
        for row in r: row['arms'][m.ARMS[0]] = forward({'Entailment': .01, 'Contradiction': .98, 'NotMentioned': .01})
        g = m.gate(r); self.assertFalse(g['passed']); self.assertFalse(g['checks']['all_three_classes_correct_at_least_once'])

    def test_missing_gold_class_fails(self):
        r = rows()
        for row in r:
            if row['typed_gold'] == 'NotMentioned': row['typed_gold'] = 'Contradiction'
        g = m.gate(r); self.assertFalse(g['checks']['all_gold_classes_present'])

    def test_partial_phase_rejected(self):
        with self.assertRaises(m.InvalidReceipt): m.gate(rows()[:-1])

    def test_duplicate_phase_rejected(self):
        r = rows(); r[-1]['question_id'] = r[0]['question_id']
        with self.assertRaises(m.InvalidReceipt): m.gate(r)

    def test_bool_document_gate_rejected(self):
        r = rows()
        for row in r:
            if row['document_id'] == 1: row['document_id'] = True
        with self.assertRaises(m.InvalidReceipt): m.gate(r)

    def test_bootstrap_recipe_not_mutable(self):
        for kwargs in [{'draws': 100}, {'seed': 1}, {'draws': True}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(m.InvalidReceipt): m.paired_bootstrap(rows(), m.ARMS[1], **kwargs)

    def test_bootstrap_deterministic_and_per_document(self):
        a = m.paired_bootstrap(rows(), m.ARMS[1]); b = m.paired_bootstrap(rows(), m.ARMS[1])
        self.assertEqual(a, b)
        self.assertAlmostEqual(a['accuracy']['mean_improvement'], 2/3)
        for bound in a['accuracy']['ci95']: self.assertAlmostEqual(bound, 2/3)

    def test_json_never_emits_nonstandard_infinity(self):
        result = m.json_safe({'NLL': math.inf, 'nested': [math.nan, -math.inf]})
        json.dumps(result, allow_nan=False)
        self.assertEqual(result['nested'][0], {'nonfinite': 'NaN'})


if __name__ == '__main__': unittest.main()
