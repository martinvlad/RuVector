"""Independent stdlib probability, proper-score and paired-document replay.

This module imports no candidate, model, tokenizer, tensor, native or dataset code.
Synthetic unit tests exercise arithmetic only and are never benchmark evidence.
"""
from __future__ import annotations
import math
import random

ORDER = ('Entailment', 'Contradiction', 'NotMentioned')
ARMS = ('ruvector_top2', 'same_nli_lexical_top2', 'same_nli_positional_first2')
RAW_INDEX = {'Entailment': 0, 'Contradiction': 2, 'NotMentioned': 1}


class InvalidReceipt(ValueError):
    pass


def demand(value, message):
    if not value:
        raise InvalidReceipt(message)


def real(value):
    demand(type(value) in (int, float) and math.isfinite(value), 'finite literal real required')
    return float(value)


def softmax(logits):
    demand(isinstance(logits, list) and len(logits) == 3, 'exactly three E/N/C raw logits required')
    z = [real(x) for x in logits]
    peak = max(z)
    e = [math.exp(x - peak) for x in z]
    total = math.fsum(e)
    return {label: e[index] / total for label, index in RAW_INDEX.items()}


def probabilities(p):
    demand(type(p) is dict and set(p) == set(ORDER), 'exact canonical E/C/N probabilities required')
    v = {label: real(p[label]) for label in ORDER}
    demand(all(0 <= x <= 1 for x in v.values()), 'probability outside unit interval')
    demand(abs(math.fsum(v.values()) - 1) <= 1e-10, 'raw typed mass outside frozen tolerance')
    return v


def prediction(p):
    return max(ORDER, key=lambda label: p[label])


def replay_forward(row):
    demand(type(row) is dict, 'forward receipt must be object')
    p = probabilities(row['typed_probabilities'])
    replay = softmax(row['raw_logits'])
    demand(all(abs(p[k] - replay[k]) <= 1e-10 for k in ORDER), 'raw-logit softmax/source-label mismatch')
    demand(row['typed_prediction'] == prediction(p), 'typed argmax mismatch')
    # Binary mass is literal E versus C+N. Never repair or renormalize it.
    yes, no = p['Entailment'], p['Contradiction'] + p['NotMentioned']
    demand(abs((yes + no) - 1) <= 1e-10, 'binary probability mass outside frozen tolerance')
    demand(type(row['binary_probabilities']) is dict and set(row['binary_probabilities']) == {'Yes', 'No'}, 'exact binary keys required')
    for label, expected in [('Yes', yes), ('No', no)]:
        demand(abs(real(row['binary_probabilities'][label]) - expected) <= 1e-10, 'binary marginal mismatch')
    demand(row['binary_prediction'] == ('Yes' if yes >= .5 else 'No'), 'binary threshold mismatch')
    return p


def proper_loss(p, target):
    demand(target in p, 'gold outside class order')
    brier = math.fsum((p[k] - int(k == target)) ** 2 for k in p)
    nll = -math.log(p[target]) if p[target] > 0 else math.inf
    return brier, nll


def mean(values):
    demand(bool(values), 'nonempty metric sample required')
    return math.fsum(values) / len(values)


def percentile(values, p):
    demand(bool(values) and 0 <= p <= 1, 'nonempty percentile sample required')
    values = sorted(values)
    i = (len(values) - 1) * p
    low, high = math.floor(i), math.ceil(i)
    if values[low] == values[high]:
        return values[low]
    return values[low] + (values[high] - values[low]) * (i - low)


def metrics(rows, arm, typed=True):
    demand(arm in ARMS, 'unknown matched arm')
    losses, correct, by_class = [], [], {label: {'n': 0, 'correct': 0} for label in ORDER}
    for row in rows:
        gold = row['typed_gold']
        demand(gold in ORDER, 'unknown typed gold')
        f = row['arms'][arm]
        p = replay_forward(f)
        if typed:
            target, distribution, output = gold, p, f['typed_prediction']
            by_class[gold]['n'] += 1
            by_class[gold]['correct'] += int(output == gold)
        else:
            target = 'Yes' if gold == 'Entailment' else 'No'
            distribution = {'Yes': p['Entailment'], 'No': p['Contradiction'] + p['NotMentioned']}
            output = f['binary_prediction']
        losses.append(proper_loss(distribution, target))
        correct.append(int(output == target))
    return {'n': len(rows), 'correct': sum(correct), 'accuracy': mean(correct),
            'Brier': mean([x[0] for x in losses]), 'NLL': mean([x[1] for x in losses]),
            **({'by_class': by_class} if typed else {})}


def validate_identities(rows, expected_questions, expected_documents):
    demand(isinstance(rows, list) and len(rows) == 24, 'exactly24 complete corpus rows required')
    demand(type(expected_questions) is list and len(expected_questions) == 24 and all(type(x) is str and x for x in expected_questions), 'expected question identities must be24 literal nonempty strings')
    demand(type(expected_documents) is list and len(expected_documents) == 8 and all(type(x) is int and x >= 0 for x in expected_documents), 'expected document identities must be8 literal nonnegative integers')
    expected_doc_keys = [(type(x).__name__, x) for x in expected_documents]
    demand(len(set(expected_questions)) == 24 and len(set(expected_doc_keys)) == 8, 'expected identities must be unique')
    actual = [r['question_id'] for r in rows]
    demand(all(type(x) is str and x for x in actual) and actual == expected_questions and len(set(actual)) == 24, 'exact ordered unique literal string question identities required')
    groups = [r['document_id'] for r in rows]
    demand(all(type(x) is int and x >= 0 for x in groups), 'literal nonnegative integer document identities required; no bool/float/string substitutions')
    group_keys = [(type(x).__name__, x) for x in groups]
    demand(set(group_keys) == set(expected_doc_keys) and len(set(group_keys)) == 8, 'exact typed eight document groups required')
    demand(all(group_keys.count(x) == 3 for x in expected_doc_keys), 'exact three queries per document required')
    demand(group_keys == [key for key in expected_doc_keys for _ in range(3)], 'every ordered question must retain its exact frozen document identity')
    demand(all(set(r['arms']) == set(ARMS) for r in rows), 'exact same-model matched arms required')
    return True


def per_document_deltas(rows, control, typed):
    grouped = {}
    for row in rows:
        grouped.setdefault(row['document_id'], []).append(row)
    out = []
    for group in sorted(grouped, key=str):
        a, b = metrics(grouped[group], ARMS[0], typed), metrics(grouped[group], control, typed)
        out.append((a['accuracy'] - b['accuracy'], b['Brier'] - a['Brier'], b['NLL'] - a['NLL']))
    return out


def paired_bootstrap(rows, control, typed=True, draws=2000, seed=20261022):
    demand(type(draws) is int and draws == 2000 and type(seed) is int and seed == 20261022, 'exact frozen bootstrap recipe required')
    deltas = per_document_deltas(rows, control, typed)
    demand(len(deltas) == 8, 'exact eight paired document groups required')
    demand(all(math.isfinite(x) for row in deltas for x in row), 'infinite proper scores cannot support confirmation intervals')
    rng, samples = random.Random(seed), [[], [], []]
    for _ in range(draws):
        indices = [rng.randrange(8) for _ in range(8)]
        for i in range(3):
            samples[i].append(mean([deltas[j][i] for j in indices]))
    return {name: {'mean_improvement': mean([x[i] for x in deltas]),
                   'ci95': [percentile(samples[i], .025), percentile(samples[i], .975)],
                   'draws': draws, 'seed': seed}
            for i, name in enumerate(('accuracy', 'Brier', 'NLL'))}


def gate(rows, confirmation=False):
    """Research acceptance only; never champion promotion or publisher eligibility."""
    demand(isinstance(rows, list) and len(rows) == 24, 'complete24-query phase required for gate')
    demand(all(type(r['question_id']) is str and r['question_id'] for r in rows) and len({r['question_id'] for r in rows}) == 24, 'unique literal string gate question identities required')
    documents = [r['document_id'] for r in rows]
    demand(all(type(x) is int and x >= 0 for x in documents), 'literal nonnegative integer gate document identities required; bool/float/string not allowed')
    documents = [(type(x).__name__, x) for x in documents]
    demand(len(set(documents)) == 8 and all(documents.count(x) == 3 for x in set(documents)), 'complete8x3 document phase required for gate')
    typed = {arm: metrics(rows, arm, True) for arm in ARMS}
    binary = {arm: metrics(rows, arm, False) for arm in ARMS}
    checks, intervals = {}, {}
    primary = typed[ARMS[0]]
    checks['all_gold_classes_present'] = all(primary['by_class'][label]['n'] >= 1 for label in ORDER)
    checks['all_three_classes_correct_at_least_once'] = all(primary['by_class'][label]['correct'] >= 1 for label in ORDER)
    for kind, table in [('typed', typed), ('binary', binary)]:
        a = table[ARMS[0]]
        for control in ARMS[1:]:
            b, key = table[control], kind + ':' + control
            checks[key + ':accuracy_gain_at_least_two_correct'] = a['correct'] - b['correct'] >= 2
            checks[key + ':Brier_nonincrease'] = a['Brier'] <= b['Brier']
            checks[key + ':NLL_nonincrease'] = a['NLL'] <= b['NLL']
            checks[key + ':strict_proper_gain'] = b['Brier'] - a['Brier'] >= 1e-6 or b['NLL'] - a['NLL'] >= 1e-6
            finite = all(math.isfinite(x) for x in [a['Brier'], a['NLL'], b['Brier'], b['NLL']])
            checks[key + ':finite_proper_scores'] = finite
            if confirmation and finite:
                ci = paired_bootstrap(rows, control, kind == 'typed')
                intervals[key] = ci
                checks[key + ':accuracy_CI_lower_positive'] = ci['accuracy']['ci95'][0] > 0
                checks[key + ':Brier_CI_lower_nonnegative'] = ci['Brier']['ci95'][0] >= 0
                checks[key + ':NLL_CI_lower_nonnegative'] = ci['NLL']['ci95'][0] >= 0
            elif confirmation:
                checks[key + ':finite_confirmation_intervals'] = False
    return {'passed': all(checks.values()), 'checks': checks, 'typed_metrics': typed,
            'binary_metrics': binary, 'confirmation_intervals': intervals if confirmation else None,
            'champion_promotion_allowed': False, 'publisher_submission_allowed': False,
            'scope': 'Frozen matched-reader retrieval research; nominal paired8-document intervals, not official benchmark placement or a direct full-input native104 comparison.'}


def json_safe(value):
    """Represent infinite losses explicitly, never silently clip or fabricate them."""
    if type(value) is float and not math.isfinite(value):
        return {'nonfinite': '+Infinity' if value > 0 else '-Infinity' if value < 0 else 'NaN'}
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value
