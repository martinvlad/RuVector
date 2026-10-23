"""Frozen full-proposition counterclaim and polarity-equivariant probability pool.

This is an empirical model-view combination, not a rule for benchmark labels,
semantic evidence sufficiency, or a Bayesian independence claim.
"""
from __future__ import annotations
import math

PREFIX = 'It is not the case that '
HYPOTHESES = {
    'nda-17': 'Receiving Party may create a copy of some Confidential Information in some circumstances.',
    'nda-7': 'Receiving Party may share some Confidential Information with some third-parties (including consultants, agents and professional advisors).',
    'nda-3': 'Confidential Information may include verbally conveyed information.',
}
ORDER = ('Entailment', 'Contradiction', 'NotMentioned')
MIRROR = {'Entailment': 'Contradiction', 'Contradiction': 'Entailment',
          'NotMentioned': 'NotMentioned'}


def counterclaim(hypothesis):
    if not isinstance(hypothesis, str) or hypothesis not in HYPOTHESES.values():
        raise ValueError('Unsupported exact whole hypothesis; no native/model forward permitted')
    return PREFIX + hypothesis


def checked(probabilities):
    if not isinstance(probabilities, dict) or set(probabilities) != set(ORDER):
        raise ValueError('Exactly three typed probabilities required')
    p = {}
    for key in ORDER:
        value = probabilities[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Finite numeric probabilities required')
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Finite probabilities in [0,1] required')
        p[key] = float(value)
    if not math.isclose(sum(p.values()), 1., rel_tol=0, abs_tol=1e-10):
        raise ValueError('Typed probability mass must sum to one')
    return p


def pool(positive, negative):
    p, q = checked(positive), checked(negative)
    mirrored = {key: q[MIRROR[key]] for key in ORDER}
    result = {key: (p[key] + mirrored[key]) / 2. for key in ORDER}
    checked(result)
    return result


def binary(typed):
    p = checked(typed)
    return {'Yes': p['Entailment'], 'No': p['Contradiction'] + p['NotMentioned']}


def prediction(typed):
    p = checked(typed)
    # Explicit canonical-order first maximum; binary .5 ties still use No in
    # the unchanged answer helper. Threeway and binary decisions are distinct.
    return max(ORDER, key=lambda key: p[key])


def receipt(positive, negative):
    p, q = checked(positive), checked(negative)
    mirrored = {key: q[MIRROR[key]] for key in ORDER}
    pos_label, neg_label = prediction(p), prediction(q)
    return {
        'method': 'full-proposition-NOT mirrored arithmetic mean, temperature1',
        'formulas': {'Entailment': '(E_H+C_Q)/2', 'Contradiction': '(C_H+E_Q)/2',
                     'NotMentioned': '(N_H+N_Q)/2'},
        'counterclaim_prefix': PREFIX,
        'positive_threeway_probabilities': p,
        'counterclaim_threeway_probabilities': q,
        'mirrored_counterclaim_threeway_probabilities': mirrored,
        'view_argmax': {'positive': pos_label, 'counterclaim': neg_label,
                        'mirrored_counterclaim': MIRROR[neg_label]},
        'polarity_view_disagreement': pos_label != MIRROR[neg_label],
        'both_views_predict_entailment': pos_label == neg_label == 'Entailment',
        'both_views_predict_contradiction': pos_label == neg_label == 'Contradiction',
        'threeway_tie_policy': 'first maximum in Entailment,Contradiction,NotMentioned order',
        'conflict_scope': 'Conflict stays distributed over E/C and is recorded; it is not relabeled NotMentioned.',
        'neutral_scope': 'Neutral probabilities are averaged directly; missing entailment does not prove contradiction or absence.',
        'training_or_calibration': False,
        'Bayesian_independence_or_annotation_complement_claim': False,
    }
