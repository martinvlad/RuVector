"""Generic engineering fixtures only: no benchmark inputs or gold are read."""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import random
import struct
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path, sha256=None):
    if sha256 is not None:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('epoch18_math_under_test', HERE / 'math_v1.py')
SOURCE_SHA256 = '6aa17d212ea20a3eeb6876149367842e8462c11dcb54d73df062fb406368331e'
source = load('epoch18_pinned_source_scorer',
              ROOT / 'benchmark' / 'sources' / 'jevbench_scoring.py', SOURCE_SHA256)


def source_score(values, expected='Yes'):
    task = SimpleNamespace(labels=['Yes', 'No'], expected=expected,
                           question={'type': 'binary'})
    return source.score_task(values, task)


def metrics(arms, primary_correct=20, other_correct=18):
    return {arm: {'n': 24, 'correct': primary_correct if arm == 'ruvector_top2'
                 else other_correct, 'brier': .2 if arm == 'ruvector_top2' else .3,
                 'nll': .4 if arm == 'ruvector_top2' else .5,
                 'strict_valid': 24, 'errors': 0} for arm in arms}


def gate_inputs():
    return (metrics(m.BINARY_ARMS), metrics(m.TYPED_ARMS),
            {'Entailment': 8, 'Contradiction': 8, 'NotMentioned': 8},
            {'Contradiction->Contradiction': 1})


def cis(arms):
    return {arm: {key: {'mean_improvement': .2, 'ci95': [.1, .3],
                       'draws': 2000, 'seed': 20261022}
                  for key in ('accuracy', 'brier', 'nll')}
            for arm in arms if arm != 'ruvector_top2'}


class ProbabilityPolicyTests(unittest.TestCase):
    def test_source_tolerance_is_exactly_frozen(self):
        self.assertEqual(source.SUM_TOL, 1e-3)
        self.assertEqual(source.RENORM_TOL, 2e-2)
        self.assertEqual(m.SUM_TOL, source.SUM_TOL)
        self.assertEqual(m.INTERNAL_TOL, 1e-10)

    def test_generic_float32_wire_is_literal_and_strict_source_valid(self):
        f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
        values = {'Yes': f32(.33333334), 'No': f32(.6666667)}
        before = dict(values)
        deviation = abs(sum(values.values()) - 1)
        self.assertGreater(deviation, 1e-10)
        self.assertLess(deviation, 1e-3)
        scored = source_score(values)
        self.assertIs(m.binary_wire(values, scored), values)
        self.assertEqual(values, before)
        self.assertTrue(scored['strict_valid'])
        self.assertFalse(scored['renormalized'])
        with self.assertRaises(AssertionError):
            m.distribution(values, m.BINARY_LABELS, 1e-10)

    def test_just_inside_source_sum_tolerance_is_not_renormalized(self):
        for mass_delta in (.000999, -.000999):
            values = {'Yes': .5, 'No': .5 + mass_delta}
            scored = source_score(values)
            self.assertTrue(scored['strict_valid'])
            self.assertFalse(scored['renormalized'])
            self.assertIs(m.binary_wire(values, scored), values)
            self.assertEqual(scored['probs'], values)

    def test_float32_mass_near_eight_e_minus_eight_remains_literal(self):
        f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
        values = {'Yes': f32(.9), 'No': f32(.1000001)}
        deviation = abs(sum(values.values()) - 1)
        self.assertGreater(deviation, 7e-8)
        self.assertLess(deviation, 8e-8)
        result = source_score(values)
        self.assertIs(m.binary_wire(values, result), values)
        self.assertEqual(result['probs'], values)
        with self.assertRaises(AssertionError):
            m.distribution(values, m.BINARY_LABELS, 1e-10)

    def test_renorm_only_and_outside_range_are_not_strict_acceptance(self):
        for values in ({'Yes': .5, 'No': .501001},
                       {'Yes': .507, 'No': .507},
                       {'Yes': .5, 'No': .498999}):
            scored = source_score(values)
            self.assertTrue(scored['valid'])
            self.assertFalse(scored['strict_valid'])
            self.assertTrue(scored['renormalized'])
            with self.assertRaises(AssertionError):
                m.binary_wire(values, scored)
        with self.assertRaises(AssertionError):
            m.binary_wire({'Yes': .52, 'No': .52},
                          source_score({'Yes': .52, 'No': .52}))

    def test_invalid_probability_types_keys_and_values_fail(self):
        bad = [None, [], {'Yes': True, 'No': 0},
               {'Yes': .5, 'No': float('nan')},
               {'Yes': .5, 'No': float('inf')},
               {'Yes': -.1, 'No': 1.1}, {'Yes': 1.1, 'No': 0},
               {'Yes': .5}, {'Yes': .5, 'No': .5, 'extra': 0},
               {'Yes': '0.5', 'No': .5}, {'Yes': 0, 'No': 0}]
        for values in bad:
            with self.subTest(values=values), self.assertRaises(AssertionError):
                m.binary_wire(values)

    def test_source_flags_and_literal_copy_cannot_be_repaired(self):
        values = {'Yes': .5004, 'No': .5004}
        original = source_score(values)
        for field, bad in (('valid', False), ('valid', 1),
                           ('strict_valid', False), ('renormalized', True)):
            result = copy.deepcopy(original)
            result[field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(AssertionError):
                m.binary_wire(values, result)
        result = copy.deepcopy(original)
        result['probs'] = {'Yes': .5, 'No': .5}
        with self.assertRaises(AssertionError):
            m.binary_wire(values, result)

    def test_internal_probability_tolerance_is_not_binary_wire_tolerance(self):
        typed = {'Entailment': .3, 'Contradiction': .3, 'NotMentioned': .40000001}
        with self.assertRaises(AssertionError):
            m.distribution(typed, m.LABELS)
        with self.assertRaises(AssertionError):
            m.binary(typed)
        m.binary_wire({'Yes': .3, 'No': .70000001})

    def test_binary_collapse_and_no_semantics(self):
        typed = {'Entailment': .3, 'Contradiction': .1, 'NotMentioned': .6}
        result = m.binary(typed)
        self.assertEqual(result, {'Yes': .3, 'No': .7})
        self.assertEqual(m.prediction(typed), 'NotMentioned')
        self.assertEqual(m.prediction(result), 'No')

    def test_explicit_ties_are_frozen(self):
        self.assertEqual(m.prediction({'Yes': .5, 'No': .5}), 'No')
        self.assertEqual(source_score({'Yes': .5, 'No': .5})['predicted'], 'No')
        self.assertEqual(m.prediction(dict.fromkeys(m.LABELS, 1 / 3)), 'Entailment')
        self.assertEqual(m.prediction({'Entailment': 0, 'Contradiction': .5,
                                      'NotMentioned': .5}), 'Contradiction')

    def test_two_reader_index_maps_are_semantically_equivalent(self):
        new = {'contradiction': 0, 'neutral': 1, 'entailment': 2}
        old = {'contradiction': 0, 'entailment': 1, 'neutral': 2}
        for semantic, canonical in [('contradiction', 'Contradiction'),
                                    ('neutral', 'NotMentioned'),
                                    ('entailment', 'Entailment')]:
            new_logits, old_logits = [-10.] * 3, [-10.] * 3
            new_logits[new[semantic]] = 10.
            old_logits[old[semantic]] = 10.
            new_probs, old_probs = m.softmax(new_logits, new), m.softmax(old_logits, old)
            self.assertEqual(new_probs, old_probs)
            self.assertEqual(m.prediction(new_probs), canonical)

    def test_softmax_extremes_and_invalid_indices(self):
        indices = {'contradiction': 0, 'neutral': 1, 'entailment': 2}
        self.assertEqual(m.softmax([1000., -1000., 0.], indices),
                         {'Entailment': 0., 'Contradiction': 1., 'NotMentioned': 0.})
        bad = [{'contradiction': 0, 'neutral': 0, 'entailment': 2},
               {'contradiction': False, 'neutral': 1, 'entailment': 2},
               {'contradiction': 0., 'neutral': 1, 'entailment': 2},
               {'contradiction': 0, 'neutral': 1, 'other': 2}]
        for mapping in bad:
            with self.assertRaises(AssertionError):
                m.softmax([1., 2., 3.], mapping)
        for logits in ([float('nan'), 0, 0], [True, 0, 0], [1, 2]):
            with self.assertRaises(AssertionError):
                m.softmax(logits, indices)

    def test_literal_proper_scores_and_probability_floor(self):
        values = {'Yes': .5004, 'No': .5004}
        scored = source_score(values, 'Yes')
        actual = m.row_score(values, 'Yes', m.BINARY_LABELS)
        literal_brier = (.5004 - 1) ** 2 + .5004 ** 2
        self.assertEqual(actual['brier'], literal_brier)
        self.assertEqual(actual['nll'], -math.log(scored['probs']['Yes']))
        self.assertNotEqual(actual['brier'], .5)  # normalizing would hide the mass
        self.assertFalse(actual['correct'])  # exact tie is No
        zero = m.row_score({'Yes': 0., 'No': 1.}, 'Yes', m.BINARY_LABELS)
        self.assertEqual(zero['brier'], 2.)
        self.assertEqual(zero['nll'], -math.log(1e-15))


class GateTests(unittest.TestCase):
    def test_positive_development_contract_compares_every_control(self):
        self.assertTrue(m.point_gate(*gate_inputs(), development=True)[0])
        self.assertEqual(m.BINARY_ARMS[-1], 'previous_reader_native_same_premise')
        self.assertNotIn('native104_on_ruvector_evidence', m.TYPED_ARMS)

    def test_development_requires_two_correct_gain_binary_and_typed(self):
        for kind, arms in ((0, m.BINARY_ARMS), (1, m.TYPED_ARMS)):
            for arm in arms:
                if arm == 'ruvector_top2':
                    continue
                args = list(gate_inputs())
                args[kind][arm]['correct'] = 19
                with self.subTest(kind=kind, arm=arm):
                    self.assertFalse(m.point_gate(*args, development=True)[0])

    def test_confidence_only_gain_does_not_pass_dev(self):
        args = list(gate_inputs())
        for collection in args[:2]:
            for value in collection.values():
                value['correct'] = 18
        self.assertFalse(m.point_gate(*args, development=True)[0])
        self.assertTrue(m.point_gate(*args, development=False)[0])

    def test_typed_contradiction_and_all_classes_are_required(self):
        for confusion in ({}, {'Contradiction->Contradiction': 0},
                          {'Contradiction->Contradiction': True},
                          {'Contradiction->Contradiction': 9}, None):
            args = list(gate_inputs())
            args[3] = confusion
            self.assertFalse(m.point_gate(*args, development=True)[0])
        for counts in ({'Entailment': 12, 'Contradiction': 0, 'NotMentioned': 12},
                       {'Entailment': 8, 'Contradiction': 8, 'NotMentioned': 7},
                       {'Entailment': True, 'Contradiction': 11, 'NotMentioned': 12}):
            args = list(gate_inputs())
            args[2] = counts
            self.assertFalse(m.point_gate(*args, development=True)[0])

    def test_both_proper_scores_nonworse_and_each_nli_control_strict(self):
        for kind, arms in ((0, m.BINARY_ARMS), (1, m.TYPED_ARMS)):
            for arm in arms:
                if arm == 'ruvector_top2':
                    continue
                for metric in ('brier', 'nll'):
                    args = list(gate_inputs())
                    args[kind][arm][metric] = args[kind]['ruvector_top2'][metric] - 1e-5
                    self.assertFalse(m.point_gate(*args, development=True)[0])
                args = list(gate_inputs())
                for metric in ('brier', 'nll'):
                    args[kind][arm][metric] = args[kind]['ruvector_top2'][metric]
                expected = arm == 'native104_on_ruvector_evidence'
                with self.subTest(kind=kind, arm=arm):
                    self.assertEqual(m.point_gate(*args, development=True)[0], expected)

    def test_invalid_partial_error_and_nonfinite_metrics_fail_closed(self):
        for key, value in (('n', 23), ('n', 24.), ('strict_valid', 23),
                           ('errors', 1), ('correct', True), ('brier', float('nan')),
                           ('nll', float('inf')), ('nll', -.01)):
            args = list(gate_inputs())
            args[0]['ruvector_top2'][key] = value
            self.assertFalse(m.point_gate(*args, development=True)[0])
        args = list(gate_inputs())
        del args[0][m.BINARY_ARMS[-1]]
        self.assertFalse(m.point_gate(*args, development=True)[0])

    def test_confirm_point_and_ci_contract(self):
        args = gate_inputs()
        bci, tci = cis(m.BINARY_ARMS), cis(m.TYPED_ARMS)
        self.assertTrue(m.confirmation_gate(*args, bci, tci)[0])
        for kind, arms in ((0, m.BINARY_ARMS), (1, m.TYPED_ARMS)):
            for arm in arms:
                if arm == 'ruvector_top2':
                    continue
                for metric, bad in (('accuracy', 0.), ('brier', -2e-12),
                                    ('nll', -2e-12)):
                    intervals = [cis(m.BINARY_ARMS), cis(m.TYPED_ARMS)]
                    intervals[kind][arm][metric]['ci95'][0] = bad
                    with self.subTest(kind=kind, arm=arm, metric=metric):
                        self.assertFalse(m.confirmation_gate(*args, *intervals)[0])

    def test_ci_nonnegative_epsilon_and_wrong_bootstrap_rejected(self):
        args = gate_inputs()
        bci, tci = cis(m.BINARY_ARMS), cis(m.TYPED_ARMS)
        for intervals in (bci, tci):
            for value in intervals.values():
                value['brier']['ci95'][0] = -m.EPS
                value['nll']['ci95'][0] = -m.EPS
        self.assertTrue(m.confirmation_gate(*args, bci, tci)[0])
        for field, bad in (('draws', 1999), ('seed', 0),
                           ('mean_improvement', float('nan')), ('ci95', [.3, .1])):
            changed = cis(m.BINARY_ARMS)
            changed[m.BINARY_ARMS[1]]['accuracy'][field] = bad
            self.assertFalse(m.confirmation_gate(*args, changed, tci)[0])
        del bci[m.BINARY_ARMS[-1]]
        self.assertFalse(m.confirmation_gate(*args, bci, tci)[0])


class AggregationTests(unittest.TestCase):
    def test_summary_is_literal_and_rejects_invalid_rows(self):
        rows = [{'correct': True, 'brier': .2, 'nll': .4},
                {'correct': False, 'brier': .4, 'nll': .6}]
        actual = m.summary(rows)
        self.assertEqual(actual['correct'], 1)
        self.assertAlmostEqual(actual['brier'], .3)
        self.assertEqual(actual['strict_valid'], 2)
        self.assertIsNone(m.summary([])['brier'])
        for bad in ({'correct': 1, 'brier': .2, 'nll': .4},
                    {'correct': True, 'brier': -.2, 'nll': .4}):
            with self.assertRaises(AssertionError):
                m.summary([bad])

    def test_group_weighting_and_gain_orientations(self):
        primary = [{'correct': True, 'brier': .1, 'nll': .2}] * 3
        control = [{'correct': False, 'brier': .3, 'nll': .5},
                   {'correct': True, 'brier': .1, 'nll': .2},
                   {'correct': True, 'brier': .1, 'nll': .2}]
        actual = m.grouped_differences(primary, control, ['a', 'b', 'b'])
        self.assertEqual(actual['accuracy'], [1, 0])
        self.assertAlmostEqual(actual['brier'][0], .2)
        self.assertAlmostEqual(actual['nll'][0], .3)
        self.assertEqual(actual['brier'][1], 0)
        self.assertEqual(m.interval(actual['accuracy'])['mean_improvement'], .5)
        self.assertNotEqual(m.interval(actual['accuracy'])['mean_improvement'], 1 / 3)

    def test_bootstrap_seed_percentiles_and_constant_bounds(self):
        self.assertEqual(m.interval([0.] * 8)['ci95'], [0., 0.])
        self.assertEqual(m.interval([.25] * 8)['ci95'], [.25, .25])
        vector = [0.] * 4 + [1.] * 4
        random.seed(910)
        first = m.interval(vector)
        random.seed(33)
        self.assertEqual(first, m.interval(vector))
        self.assertEqual(first, {'mean_improvement': .5, 'ci95': [.125, .875],
                                 'draws': 2000, 'seed': 20261022})

    def test_exact_eight_document_paired_ci_shape(self):
        good = {'correct': True, 'brier': .1, 'nll': .2}
        worse = {'correct': False, 'brier': .4, 'nll': .6}
        per_arm = {arm: [dict(good if arm == 'ruvector_top2' else worse)
                         for _ in range(24)] for arm in m.BINARY_ARMS}
        groups = [i for i in range(8) for _ in range(3)]
        actual = m.paired_intervals(per_arm, groups)
        self.assertEqual(set(actual), set(m.BINARY_ARMS) - {'ruvector_top2'})
        for value in actual.values():
            self.assertEqual(value['accuracy']['ci95'], [1, 1])
            self.assertAlmostEqual(value['brier']['mean_improvement'], .3)
            self.assertAlmostEqual(value['nll']['mean_improvement'], .4)
        bad_groups = list(groups)
        bad_groups[-1] = 0  # 8 docs remain, but 4/2 query groups are disallowed
        with self.assertRaises(AssertionError):
            m.paired_intervals(per_arm, bad_groups)
        with self.assertRaises(AssertionError):
            m.paired_intervals({k: v for k, v in per_arm.items()
                                if k != m.BINARY_ARMS[-1]}, groups)

    def test_linear_latency_quantiles_and_input_guards(self):
        self.assertEqual(m.latency_percentile([0, 10, 20, 30], .5), 15)
        self.assertAlmostEqual(m.latency_percentile([0, 10, 20, 30], .95), 28.5)
        self.assertEqual(m.latency_percentile([7], .95), 7)
        for values, q in (([], .5), ([1], -1), ([1], 1.1),
                          ([float('nan')], .5), ([-1], .5), ([True], .5)):
            with self.assertRaises(AssertionError):
                m.latency_percentile(values, q)


if __name__ == '__main__':
    unittest.main(verbosity=2)
