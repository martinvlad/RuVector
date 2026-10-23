"""Independent epoch17 arithmetic; no inference, data access, or fitting.

Binary transport follows the pinned source scorer's strict SUM_TOL, without
normalization. Internal three-way probabilities retain the tighter invariant.
This new policy does not change or rescue any epoch16 artifact.
"""
import math
import random
import statistics

BINARY_ARMS = ('ruvector_top2', 'same_nli_lexical_top2',
               'same_nli_positional_first2', 'native104_on_ruvector_evidence',
               'previous_reader_native_same_premise')
TYPED_ARMS = tuple(x for x in BINARY_ARMS
                   if x != 'native104_on_ruvector_evidence')
LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
BINARY_LABELS = ('Yes', 'No')
EPS = 1e-12
INTERNAL_TOL = 1e-10
SUM_TOL = 1e-3
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261022


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def close(a, b, tolerance=INTERNAL_TOL):
    assert _number(a) and _number(b)
    assert _number(tolerance) and tolerance >= 0
    assert math.isclose(a, b, rel_tol=0, abs_tol=tolerance), (a, b)


def distribution(values, labels, tolerance=None):
    """Validate and return the same literal mapping, never a repaired copy."""
    assert isinstance(values, dict) and set(values) == set(labels)
    assert len(tuple(labels)) == len(set(labels))
    assert all(_number(v) and 0 <= v <= 1 for v in values.values())
    if tolerance is None:
        tolerance = SUM_TOL if set(labels) == set(BINARY_LABELS) else INTERNAL_TOL
    assert _number(tolerance) and tolerance >= 0
    assert abs(sum(values.values()) - 1) <= tolerance
    return values


def binary_wire(values, source_result=None):
    """Require strict source-compatible binary transport and literal identity.

    The legacy scorer can accept and renormalize a wider 2e-2 range. That path
    is deliberately rejected here, even when its headline ``valid`` is true.
    """
    distribution(values, BINARY_LABELS, SUM_TOL)
    if source_result is not None:
        assert isinstance(source_result, dict)
        assert source_result.get('valid') is True
        assert source_result.get('strict_valid') is True
        assert source_result.get('renormalized') is False
        clean = source_result.get('probs')
        distribution(clean, BINARY_LABELS, SUM_TOL)
        assert clean == values, (clean, values)
    return values


def softmax(logits, indices):
    """Stable three-logit softmax with explicit revision-specific label map."""
    assert isinstance(logits, (list, tuple)) and len(logits) == 3
    assert all(_number(v) for v in logits)
    assert isinstance(indices, dict)
    assert set(indices) == {'entailment', 'contradiction', 'neutral'}
    assert all(type(v) is int for v in indices.values())
    assert set(indices.values()) == {0, 1, 2}
    numbers = [math.exp(v - max(logits)) for v in logits]
    total = sum(numbers)
    result = {'Entailment': numbers[indices['entailment']] / total,
              'Contradiction': numbers[indices['contradiction']] / total,
              'NotMentioned': numbers[indices['neutral']] / total}
    return distribution(result, LABELS, INTERNAL_TOL)


def binary(typed):
    """Collapse E versus C+N; binary No is not a contradiction prediction."""
    distribution(typed, LABELS, INTERNAL_TOL)
    return distribution({'Yes': typed['Entailment'],
                         'No': typed['Contradiction'] + typed['NotMentioned']},
                        BINARY_LABELS, INTERNAL_TOL)


def prediction(values):
    if set(values) == set(LABELS):
        distribution(values, LABELS, INTERNAL_TOL)
        return max(LABELS, key=lambda label: values[label])
    binary_wire(values)
    return max(('No', 'Yes'), key=lambda label: values[label])


def row_score(values, gold, labels):
    distribution(values, labels)
    assert gold in labels
    return {'correct': prediction(values) == gold,
            'brier': sum((v - int(k == gold)) ** 2 for k, v in values.items()),
            'nll': -math.log(max(values[gold], 1e-15))}


def _observation(value):
    return (isinstance(value, dict) and type(value.get('correct')) is bool and
            all(_number(value.get(k)) and value[k] >= 0
                for k in ('brier', 'nll')))


def summary(observations):
    assert all(_observation(x) for x in observations)
    n = len(observations)
    return {'n': n, 'correct': sum(int(x['correct']) for x in observations),
            'brier': statistics.mean(x['brier'] for x in observations) if n else None,
            'nll': statistics.mean(x['nll'] for x in observations) if n else None,
            'strict_valid': n, 'errors': 0}


def interval(differences):
    """Nominal paired document bootstrap; empirical floor-index percentiles."""
    assert differences and all(_number(v) for v in differences)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(differences)
    samples = sorted(statistics.mean(differences[rng.randrange(n)]
                                     for _ in range(n))
                     for _ in range(BOOTSTRAP_DRAWS))
    return {'mean_improvement': statistics.mean(differences),
            'ci95': [samples[int(.025 * 1999)], samples[int(.975 * 1999)]],
            'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED}


def grouped_differences(primary, controls, source_groups):
    """Equal document weighting, with proper gain oriented control-primary."""
    assert len(primary) == len(controls) == len(source_groups) > 0
    assert all(_observation(x) for x in list(primary) + list(controls))
    assert all(type(g) in (int, str) for g in source_groups)
    groups = sorted(set(source_groups), key=lambda g: (type(g).__name__, str(g)))
    differences = {'accuracy': [], 'brier': [], 'nll': []}
    for group in groups:
        ix = [i for i, g in enumerate(source_groups) if g == group]
        differences['accuracy'].append(statistics.mean(
            int(primary[i]['correct']) - int(controls[i]['correct']) for i in ix))
        for metric in ('brier', 'nll'):
            differences[metric].append(statistics.mean(
                controls[i][metric] - primary[i][metric] for i in ix))
    return differences


def paired_intervals(per_arm, source_groups):
    assert set(per_arm) in (set(BINARY_ARMS), set(TYPED_ARMS))
    assert len(source_groups) == 24 and len(set(source_groups)) == 8
    assert all(source_groups.count(g) == 3 for g in set(source_groups))
    assert all(len(rows) == 24 for rows in per_arm.values())
    return {name: {metric: interval(values) for metric, values in
                   grouped_differences(per_arm['ruvector_top2'], controls,
                                       source_groups).items()}
            for name, controls in per_arm.items() if name != 'ruvector_top2'}


def valid(metrics, expected_arms, n=24):
    if not isinstance(metrics, dict) or set(metrics) != set(expected_arms):
        return False
    for m in metrics.values():
        if not isinstance(m, dict):
            return False
        if not all(type(m.get(k)) is int for k in
                   ('n', 'strict_valid', 'errors', 'correct')):
            return False
        if not (m['n'] == m['strict_valid'] == n and m['errors'] == 0 and
                0 <= m['correct'] <= n):
            return False
        if not all(_number(m.get(k)) and m[k] >= 0 for k in ('brier', 'nll')):
            return False
    return True


def comparison(primary, other, accuracy_gain):
    return {'accuracy_gain': primary['correct'] >= other['correct'] + accuracy_gain,
            'brier_nonincrease': primary['brier'] <= other['brier'] + EPS,
            'nll_nonincrease': primary['nll'] <= other['nll'] + EPS,
            'strict_proper_gain': (primary['brier'] < other['brier'] - EPS or
                                   primary['nll'] < other['nll'] - EPS)}


def point_gate(binary_metrics, typed_metrics, class_counts,
               primary_typed_confusion, development):
    assert type(development) is bool
    if not (valid(binary_metrics, BINARY_ARMS) and valid(typed_metrics, TYPED_ARMS)):
        return False, {'validity': False}
    classes = (isinstance(class_counts, dict) and set(class_counts) == set(LABELS)
               and all(type(class_counts[x]) is int and class_counts[x] >= 1
                       for x in LABELS) and sum(class_counts.values()) == 24)
    correct_c = (primary_typed_confusion.get('Contradiction->Contradiction', 0)
                 if isinstance(primary_typed_confusion, dict) else None)
    contradiction = (type(correct_c) is int and correct_c >= 1 and classes and
                     correct_c <= class_counts['Contradiction'])
    gain = 2 if development else 0
    checks = {'validity': True, 'all_gold_classes_present': classes,
              'primary_contradiction_correct_at_least_one': bool(contradiction),
              'binary': {}, 'typed': {}}
    for name in BINARY_ARMS:
        if name == 'ruvector_top2':
            continue
        c = comparison(binary_metrics['ruvector_top2'], binary_metrics[name], gain)
        if name == 'native104_on_ruvector_evidence':
            c.pop('strict_proper_gain')
        checks['binary'][name] = c
    for name in TYPED_ARMS:
        if name != 'ruvector_top2':
            checks['typed'][name] = comparison(typed_metrics['ruvector_top2'],
                                               typed_metrics[name], gain)
    passed = bool(classes and contradiction and all(
        all(c.values()) for kind in ('binary', 'typed')
        for c in checks[kind].values()))
    return passed, checks


def _interval_valid(value):
    if not isinstance(value, dict) or set(value) != {
            'mean_improvement', 'ci95', 'draws', 'seed'}:
        return False
    bounds = value['ci95']
    return (type(value['draws']) is int and value['draws'] == BOOTSTRAP_DRAWS and
            type(value['seed']) is int and value['seed'] == BOOTSTRAP_SEED and
            _number(value['mean_improvement']) and
            isinstance(bounds, (list, tuple)) and len(bounds) == 2 and
            all(_number(x) for x in bounds) and bounds[0] <= bounds[1])


def confirmation_gate(binary_metrics, typed_metrics, class_counts,
                      primary_typed_confusion, binary_intervals, typed_intervals):
    passed, checks = point_gate(binary_metrics, typed_metrics, class_counts,
                                primary_typed_confusion, False)
    if not passed:
        return False, {'point_gate': checks, 'uncertainty_gate': False}
    ci = {}
    for kind, expected, intervals in (
            ('binary', BINARY_ARMS, binary_intervals),
            ('typed', TYPED_ARMS, typed_intervals)):
        if not isinstance(intervals, dict) or set(intervals) != set(expected) - {
                'ruvector_top2'}:
            return False, {'point_gate': checks, 'uncertainty_gate': False,
                           'invalid_intervals': kind}
        ci[kind] = {}
        for name, value in intervals.items():
            if (not isinstance(value, dict) or set(value) != {'accuracy', 'brier', 'nll'}
                    or not all(_interval_valid(v) for v in value.values())):
                return False, {'point_gate': checks, 'uncertainty_gate': False,
                               'invalid_intervals': kind + ':' + name}
            ci[kind][name] = {
                'accuracy_lower_positive': value['accuracy']['ci95'][0] > 0,
                'brier_lower_nonnegative': value['brier']['ci95'][0] >= -EPS,
                'nll_lower_nonnegative': value['nll']['ci95'][0] >= -EPS}
    result = all(all(v.values()) for kind in ci.values() for v in kind.values())
    return result, {'point_gate': checks, 'uncertainty_gate': ci}


def latency_percentile(values, q):
    assert values and all(_number(v) and v >= 0 for v in values)
    assert _number(q) and 0 <= q <= 1
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
