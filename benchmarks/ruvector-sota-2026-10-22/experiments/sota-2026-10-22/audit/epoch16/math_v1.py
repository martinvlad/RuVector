"""Independent epoch16 probability, scoring, gate and uncertainty arithmetic.

Pure functions only. No candidate imports, model sessions, inference or fitting.
"""
import math
import random
import statistics

BINARY_ARMS = ('ruvector_top2', 'same_nli_lexical_top2',
               'same_nli_positional_first2', 'native104_on_ruvector_evidence',
               'same_nli_native_raw_h')
TYPED_ARMS = tuple(x for x in BINARY_ARMS if x != 'native104_on_ruvector_evidence')
LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
EPS = 1e-12


def close(a, b, tolerance=1e-10):
    assert math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance), (a, b)


def distribution(values, labels):
    assert set(values) == set(labels)
    assert all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
               for v in values.values())
    assert abs(sum(values.values()) - 1) <= 1e-10
    return values


def softmax(logits, indices):
    assert len(logits) == 3 and all(type(v) in (int, float) and math.isfinite(v)
                                  for v in logits)
    assert set(indices) == {'entailment', 'contradiction', 'neutral'}
    assert set(indices.values()) == {0, 1, 2}
    numbers = [math.exp(v - max(logits)) for v in logits]
    total = sum(numbers)
    return {'Entailment': numbers[indices['entailment']] / total,
            'Contradiction': numbers[indices['contradiction']] / total,
            'NotMentioned': numbers[indices['neutral']] / total}


def mirrored_pool(positive, counterclaim):
    distribution(positive, LABELS); distribution(counterclaim, LABELS)
    return {'Entailment': (positive['Entailment'] + counterclaim['Contradiction']) / 2,
            'Contradiction': (positive['Contradiction'] + counterclaim['Entailment']) / 2,
            'NotMentioned': (positive['NotMentioned'] + counterclaim['NotMentioned']) / 2}


def binary(typed):
    distribution(typed, LABELS)
    return {'Yes': typed['Entailment'],
            'No': typed['Contradiction'] + typed['NotMentioned']}


def prediction(values):
    # Independent explicit policies: binary .5 is No; typed ties use E,C,N.
    if set(values) == set(LABELS):
        return max(LABELS, key=lambda label: values[label])
    assert set(values) == {'Yes', 'No'}
    return max(('No', 'Yes'), key=lambda label: values[label])


def row_score(values, gold, labels):
    distribution(values, labels); assert gold in labels
    return {'correct': prediction(values) == gold,
            'brier': sum((v - int(k == gold)) ** 2 for k, v in values.items()),
            'nll': -math.log(max(values[gold], 1e-15))}


def summary(observations):
    n = len(observations)
    return {'n': n, 'correct': sum(int(x['correct']) for x in observations),
            'brier': statistics.mean(x['brier'] for x in observations) if n else None,
            'nll': statistics.mean(x['nll'] for x in observations) if n else None,
            'strict_valid': n, 'errors': 0}


def interval(differences):
    assert differences and all(math.isfinite(v) for v in differences)
    rng = random.Random(20261022)
    n = len(differences)
    samples = sorted(statistics.mean(differences[rng.randrange(n)] for _ in range(n))
                     for _ in range(2000))
    return {'mean_improvement': statistics.mean(differences),
            'ci95': [samples[int(.025 * 1999)], samples[int(.975 * 1999)]],
            'draws': 2000, 'seed': 20261022}


def paired_intervals(per_arm, source_groups):
    assert len(source_groups) == len(per_arm['ruvector_top2'])
    groups = sorted(set(source_groups))
    result = {}
    for name, controls in per_arm.items():
        if name == 'ruvector_top2':
            continue
        differences = {'accuracy': [], 'brier': [], 'nll': []}
        for group in groups:
            ix = [i for i, g in enumerate(source_groups) if g == group]
            differences['accuracy'].append(statistics.mean(
                int(per_arm['ruvector_top2'][i]['correct']) - int(controls[i]['correct'])
                for i in ix))
            for metric in ('brier', 'nll'):
                differences[metric].append(statistics.mean(
                    controls[i][metric] - per_arm['ruvector_top2'][i][metric] for i in ix))
        result[name] = {metric: interval(values) for metric, values in differences.items()}
    return result


def valid(metrics, expected_arms, n=24):
    return (set(metrics) == set(expected_arms) and all(
        m['n'] == m['strict_valid'] == n and m['errors'] == 0 and
        type(m['correct']) is int and 0 <= m['correct'] <= n and
        all(type(m[key]) in (int, float) and math.isfinite(m[key]) and m[key] >= 0
            for key in ('brier', 'nll')) for m in metrics.values()))


def comparison(primary, other, accuracy_gain):
    return {'accuracy_gain': primary['correct'] >= other['correct'] + accuracy_gain,
            'brier_nonincrease': primary['brier'] <= other['brier'] + EPS,
            'nll_nonincrease': primary['nll'] <= other['nll'] + EPS,
            'strict_proper_gain': (primary['brier'] < other['brier'] - EPS or
                                   primary['nll'] < other['nll'] - EPS)}


def point_gate(binary_metrics, typed_metrics, class_counts, primary_typed_confusion,
               development):
    if not (valid(binary_metrics, BINARY_ARMS) and valid(typed_metrics, TYPED_ARMS)):
        return False, {'validity': False}
    classes = (set(class_counts) == set(LABELS) and
               all(type(class_counts[x]) is int and class_counts[x] >= 1 for x in LABELS) and
               sum(class_counts.values()) == 24)
    contradiction = primary_typed_confusion.get('Contradiction->Contradiction', 0) >= 1
    gain = 2 if development else 0
    checks = {'validity': True, 'all_gold_classes_present': classes,
              'primary_contradiction_correct_at_least_one': contradiction,
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
    passed = classes and contradiction and all(
        all(c.values()) for kind in ('binary', 'typed') for c in checks[kind].values())
    return passed, checks


def confirmation_gate(binary_metrics, typed_metrics, class_counts,
                      primary_typed_confusion, binary_intervals, typed_intervals):
    passed, checks = point_gate(binary_metrics, typed_metrics, class_counts,
                                primary_typed_confusion, False)
    if not passed:
        return False, {'point_gate': checks, 'uncertainty_gate': False}
    ci = {}
    for kind, expected, intervals in (('binary', BINARY_ARMS, binary_intervals),
                                      ('typed', TYPED_ARMS, typed_intervals)):
        assert set(intervals) == set(expected) - {'ruvector_top2'}
        ci[kind] = {name: {'accuracy_lower_positive': value['accuracy']['ci95'][0] > 0,
                           'brier_lower_nonnegative': value['brier']['ci95'][0] >= -EPS,
                           'nll_lower_nonnegative': value['nll']['ci95'][0] >= -EPS}
                    for name, value in intervals.items()}
    result = passed and all(all(v.values()) for kind in ci.values() for v in kind.values())
    return result, {'point_gate': checks, 'uncertainty_gate': ci}


def latency_percentile(values, q):
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index); upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
