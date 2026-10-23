"""Frozen five-arm binary/four-arm typed scoring and predeclared DEV gates.

No inference; original benchmark labels remain unchanged.
"""
import math
import importlib
from collections import Counter

ARMS = ('ruvector_top2', 'native104_on_ruvector_evidence',
        'same_nli_lexical_top2', 'same_nli_positional_first2', 'previous_reader_native_same_premise')
TYPED_ARMS = tuple(x for x in ARMS if x != 'native104_on_ruvector_evidence')
CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')
EPSILON = 1e-12
BINARY_PROBABILITY_POLICY = {'SUM_TOL': 1e-3, 'strict_valid': True,
                             'renormalized': False, 'normalization': 'none',
                             'typed_raw_tolerance': 1e-10}


def response_for(record, arm):
    response = record['response']
    if arm == 'native104_on_ruvector_evidence':
        return response['baseline104_response']
    if arm != 'ruvector_top2':
        return response['ablation_responses'][arm]
    return response


def validate_literal_binary(record, evaluator):
    """Use the pinned scorer's strict float32-compatible rule without repair.

    The scorer itself is source/hash checked by evaluate._load_scorer. This
    guard forbids its broader rounded-distribution renormalization route.
    """
    frozen_scorer = evaluator._load_scorer()
    if frozen_scorer.SUM_TOL != BINARY_PROBABILITY_POLICY['SUM_TOL']:
        raise ValueError('Pinned scorer SUM_TOL changed')
    evaluation = record['evaluation']
    if evaluation['type'] != 'choice' or set(evaluation['labels']) != {'Yes', 'No'}:
        raise ValueError('Expected frozen binary choice task')
    if set(record['input']['questions']) != {'decision'}:
        raise ValueError('Exactly one decision question required')
    answer = record['response']['answers']['decision']
    literal = answer['probabilities']
    frozen_scorer.validate_probs(literal, evaluation['labels'])
    scored = evaluator.score_record(record)
    if (scored.get('valid') is not True or scored.get('strict_valid') is not True
            or scored.get('renormalized') is not False or scored.get('probs') != literal):
        raise ValueError('Binary wire is invalid, nonstrict, repaired or changed')
    return scored


def metric_aliases(metrics):
    return {**metrics, 'mean_brier': metrics['brier'], 'mean_nll': metrics['nll'],
            'strict_valid_count': metrics['strict_valid']}


def binary_scores(records, scorer, evaluator=None):
    evaluator = evaluator or importlib.import_module('benchmark.evaluate')
    result = {}
    for arm in ARMS:
        projected = [{**row, 'response': response_for(row, arm)} for row in records]
        for row in projected:
            validate_literal_binary(row, evaluator)
        result[arm] = metric_aliases(scorer(projected))
    return result


def typed_scores(records):
    result, confusions = {}, {}
    for arm in TYPED_ARMS:
        counts = {key: {'n': 0, 'correct': 0} for key in CLASSES}
        confusion = Counter()
        predictions = {key: 0 for key in CLASSES}
        brier, nll, correct = 0., 0., 0
        for row in records:
            keys = list(row['input']['questions'])
            if len(keys) != 1:
                raise ValueError('Exactly one frozen benchmark question required')
            gold = row['evaluation']['original_threeway_label']
            if gold not in CLASSES:
                raise ValueError('Unknown original annotation label')
            answer = response_for(row, arm)['answers'][keys[0]]
            probabilities = answer['typed_probabilities']
            if (set(probabilities) != set(CLASSES) or
                    any(type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1
                        for x in probabilities.values()) or
                    abs(sum(probabilities.values())-1) > 1e-10):
                raise ValueError('Invalid complete threeway distribution')
            predicted = max(CLASSES, key=lambda key: probabilities[key])
            if answer['typed_prediction'] != predicted:
                raise ValueError('Typed prediction/probabilities disagree')
            hit = int(predicted == gold)
            correct += hit
            counts[gold]['n'] += 1
            counts[gold]['correct'] += hit
            predictions[predicted] += 1
            confusion[gold+'->'+predicted] += 1
            brier += sum((probabilities[key]-int(gold == key))**2 for key in CLASSES)
            nll -= math.log(max(probabilities[gold], 1e-15))
        n = len(records)
        if not n:
            raise ValueError('Empty typed measurement')
        result[arm] = metric_aliases({'n': n, 'correct': correct, 'accuracy': correct/n,
                       'brier': brier/n, 'nll': nll/n, 'strict_valid': n, 'errors': 0,
                       'by_class': counts,
                       'gold_counts': {key: counts[key]['n'] for key in CLASSES},
                       'prediction_counts': predictions,
                       'correct_by_gold': {key: counts[key]['correct'] for key in CLASSES},
                       'confusion': {gold: {predicted: confusion[gold+'->'+predicted]
                                            for predicted in CLASSES} for gold in CLASSES}})
        confusions[arm] = dict(confusion)
    return result, confusions


def valid_metrics(metrics, expected_arms, typed=False):
    if set(metrics) != set(expected_arms):
        return False
    cohort = None
    for value in metrics.values():
        if (value.get('n') != 24 or value.get('strict_valid') != 24 or value.get('errors') != 0
                or type(value.get('correct')) is not int or not 0 <= value['correct'] <= 24
                or any(type(value.get(key)) not in (int, float) or not math.isfinite(value[key])
                       or value[key] < 0 for key in ('brier', 'nll'))):
            return False
        if typed:
            classes = value.get('by_class', {})
            if set(classes) != set(CLASSES):
                return False
            if any(type(x.get('n')) is not int or type(x.get('correct')) is not int or
                   not 0 <= x['correct'] <= x['n'] for x in classes.values()):
                return False
            if sum(x['n'] for x in classes.values()) != 24 or sum(x['correct'] for x in classes.values()) != value['correct']:
                return False
            current = {key: classes[key]['n'] for key in CLASSES}
            if cohort is not None and current != cohort:
                return False
            cohort = current
    return True


def compare(primary, control, margin, strict):
    result = {'accuracy_gain': primary['correct'] >= control['correct']+margin,
              'brier_nonincrease': primary['brier'] <= control['brier']+EPSILON,
              'nll_nonincrease': primary['nll'] <= control['nll']+EPSILON}
    if strict:
        result['strict_proper_gain'] = (primary['brier'] < control['brier']-EPSILON
                                       or primary['nll'] < control['nll']-EPSILON)
    return result


def development_gate(metrics, typed):
    if not valid_metrics(metrics, ARMS) or not valid_metrics(typed, TYPED_ARMS, typed=True):
        return False, {'invalid': 'Incomplete, nonfinite or inconsistent binary/typed metrics'}
    classes = typed['ruvector_top2']['by_class']
    guards = {'all_three_gold_classes_present': all(classes[key]['n'] >= 1 for key in CLASSES),
              'primary_correct_contradiction': classes['Contradiction']['correct'] >= 1}
    binary = {name: compare(metrics['ruvector_top2'], metrics[name], 2,
                            name != 'native104_on_ruvector_evidence')
              for name in ARMS if name != 'ruvector_top2'}
    typed_comparisons = {name: compare(typed['ruvector_top2'], typed[name], 2, True)
                         for name in TYPED_ARMS if name != 'ruvector_top2'}
    passed = (all(guards.values()) and all(all(x.values()) for x in binary.values())
              and all(all(x.values()) for x in typed_comparisons.values()))
    return passed, {'class_guards': guards, 'binary': binary, 'typed': typed_comparisons}
