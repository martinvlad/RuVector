"""Pure positive/negative tests of the independent frozen measurement gates."""
import copy
import math
import unittest
import math_v1 as M


class ProbabilityTests(unittest.TestCase):
    def test_probability_and_pool_semantics(self):
        p = {'Entailment': .6, 'Contradiction': .1, 'NotMentioned': .3}
        q = {'Entailment': .2, 'Contradiction': .5, 'NotMentioned': .3}
        pooled = M.mirrored_pool(p, q)
        for key, value in {'Entailment': .55, 'Contradiction': .15, 'NotMentioned': .3}.items():
            M.close(pooled[key], value)
        swapped = M.mirrored_pool(q, p)
        M.close(swapped['Entailment'], pooled['Contradiction'])
        M.close(swapped['Contradiction'], pooled['Entailment'])
        M.close(swapped['NotMentioned'], pooled['NotMentioned'])
        M.close(sum(pooled.values()), 1)
        M.close(M.binary(pooled)['Yes'], .55)

    def test_neutral_is_not_contradiction(self):
        p = {'Entailment': 0., 'Contradiction': 0., 'NotMentioned': 1.}
        self.assertEqual(M.mirrored_pool(p, p), p)

    def test_opposing_assertions_keep_probability_conflict(self):
        p = {'Entailment': 1., 'Contradiction': 0., 'NotMentioned': 0.}
        pooled = M.mirrored_pool(p, p)
        self.assertEqual(pooled, {'Entailment': .5, 'Contradiction': .5, 'NotMentioned': 0.})
        self.assertEqual(M.prediction(M.binary(pooled)), 'No')

    def test_proper_scores_and_ties(self):
        s = M.row_score({'Yes': .5, 'No': .5}, 'Yes', ['Yes', 'No'])
        M.close(s['brier'], .5); M.close(s['nll'], math.log(2))
        self.assertFalse(s['correct'])
        p = {'Entailment': .5, 'Contradiction': .25, 'NotMentioned': .25}
        M.close(M.row_score(p, 'Entailment', M.LABELS)['brier'], .375)
        self.assertEqual(M.prediction(dict.fromkeys(M.LABELS, 1/3)), 'Entailment')

    def test_invalid_probability_is_rejected(self):
        for p in [{'Yes': float('nan'), 'No': 0.}, {'Yes': True, 'No': False},
                  {'Yes': .4, 'No': .4}, {'Yes': 1.1, 'No': -.1}]:
            with self.assertRaises(AssertionError): M.distribution(p, ['Yes', 'No'])

    def test_stable_softmax_actual_raw_mapping(self):
        p = M.softmax([1000., 1001., 999.], {'contradiction': 0, 'entailment': 1, 'neutral': 2})
        M.close(sum(p.values()), 1)
        self.assertGreater(p['Entailment'], p['Contradiction'])
        self.assertGreater(p['Contradiction'], p['NotMentioned'])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.binary = {arm: {'n': 24, 'correct': 12, 'brier': .6, 'nll': 1.,
                             'strict_valid': 24, 'errors': 0} for arm in M.BINARY_ARMS}
        self.binary['ruvector_top2'].update(correct=16, brier=.3, nll=.5)
        self.typed = {arm: {'n': 24, 'correct': 10, 'brier': .8, 'nll': 1.2,
                            'strict_valid': 24, 'errors': 0} for arm in M.TYPED_ARMS}
        self.typed['ruvector_top2'].update(correct=14, brier=.4, nll=.6)
        self.classes = {'Entailment': 12, 'Contradiction': 4, 'NotMentioned': 8}
        self.confusion = {'Contradiction->Contradiction': 1}

    def gate(self):
        return M.point_gate(self.binary, self.typed, self.classes, self.confusion, True)[0]

    def test_meaningful_fixture_passes(self): self.assertTrue(self.gate())
    def test_no_contradiction_competence_fails(self):
        self.confusion = {}; self.assertFalse(self.gate())
    def test_absent_gold_class_fails_without_redraw(self):
        self.classes = {'Entailment': 16, 'Contradiction': 0, 'NotMentioned': 8}
        self.assertFalse(self.gate())
    def test_raw_H_binary_gain_one_fails(self):
        self.binary['same_nli_native_raw_h']['correct'] = 15; self.assertFalse(self.gate())
    def test_raw_H_typed_gain_one_fails(self):
        self.typed['same_nli_native_raw_h']['correct'] = 13; self.assertFalse(self.gate())
    def test_confidence_only_gain_fails(self):
        self.binary['same_nli_native_raw_h']['correct'] = 16; self.assertFalse(self.gate())
    def test_binary_proper_worse_than104_fails(self):
        self.binary['ruvector_top2']['nll'] = 1.1; self.assertFalse(self.gate())
    def test_typed_proper_worse_fails(self):
        self.typed['ruvector_top2']['brier'] = .81; self.assertFalse(self.gate())
    def test_incomplete_metrics_fail(self):
        self.binary['ruvector_top2']['n'] = 23; self.assertFalse(self.gate())
    def test_nonfinite_metrics_fail(self):
        self.binary['ruvector_top2']['nll'] = float('nan'); self.assertFalse(self.gate())
    def test_empty_partial_report_cannot_qualify(self):
        self.assertFalse(M.valid({arm: M.summary([]) for arm in M.BINARY_ARMS}, M.BINARY_ARMS))
    def test_bootstrap_is_document_clustered_and_reproducible(self):
        a = M.interval([1/3] * 8)
        self.assertEqual(a, M.interval([1/3] * 8))
        self.assertEqual(a['ci95'], [1/3, 1/3])
    def test_confirmation_requires_every_binary_and_typed_CI(self):
        def ci(arms): return {arm: {metric: {'ci95': [.01, .2]} for metric in ('accuracy', 'brier', 'nll')}
                              for arm in arms if arm != 'ruvector_top2'}
        binary_ci, typed_ci = ci(M.BINARY_ARMS), ci(M.TYPED_ARMS)
        self.assertTrue(M.confirmation_gate(self.binary, self.typed, self.classes,
                                           self.confusion, binary_ci, typed_ci)[0])
        binary_ci['native104_on_ruvector_evidence']['accuracy']['ci95'][0] = 0
        self.assertFalse(M.confirmation_gate(self.binary, self.typed, self.classes,
                                            self.confusion, binary_ci, typed_ci)[0])
        binary_ci['native104_on_ruvector_evidence']['accuracy']['ci95'][0] = .01
        typed_ci['same_nli_native_raw_h']['accuracy']['ci95'][0] = 0
        self.assertFalse(M.confirmation_gate(self.binary, self.typed, self.classes,
                                            self.confusion, binary_ci, typed_ci)[0])


if __name__ == '__main__': unittest.main()
