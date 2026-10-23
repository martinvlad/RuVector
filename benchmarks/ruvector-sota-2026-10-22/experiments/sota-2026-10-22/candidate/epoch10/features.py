"""Generic inference-only clause bindings. No identities, selectors or gold inputs."""
from __future__ import annotations
import math
import re

CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')
WORDS = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
NUMBERS = re.compile(r'(?<!\w)\d+(?:[.,]\d+)*(?!\w)')
STOP = frozenset('a an the some any of to in on with and or by for be is are as that this may shall must can not party information confidential circumstances'.split())
PERMISSION = frozenset('may can permitted allowed entitled permission permit allows'.split())
OBLIGATION = frozenset('shall must required obligated obligation undertakes'.split())
NEGATION = frozenset('not no never neither nor without cannot prohibited forbidden'.split())
CONDITION = frozenset('if when where subject condition conditions unless provided'.split())
EXCEPTION = frozenset('unless except excluding however notwithstanding provided only'.split())
ROLE_RECEIVE = frozenset('receiving receiver recipient recipients receive receives received'.split())
ROLE_DISCLOSE = frozenset('disclosing discloser provider providing owner furnishing'.split())
FAMILIES = {
    'copy': frozenset('copy copies copied copying reproduce reproduces reproduced reproduction duplicate duplicates duplication'.split()),
    'disclosure': frozenset('share shares shared sharing disclose discloses disclosed disclosing disclosure reveal reveals revealed communicate communicates communication convey conveyed furnish furnished'.split()),
    'oral': frozenset('oral orally verbal verbally spoken speech'.split()),
}
BASE_NAMES = ('bias', 'centered_logit_entailment', 'centered_logit_contradiction', 'centered_logit_notmentioned',
              'claim_content_overlap', 'claim_bigram_overlap', 'premise_length_512', 'claim_length_128',
              'clause_count_32', 'claim_receiving_actor', 'claim_disclosing_actor',
              'claim_copy_action', 'claim_disclosure_action', 'claim_oral_action',
              'premise_numeric', 'claim_numeric', 'claim_numeric_overlap')
BINDING_NAMES = ('action_clause_fraction', 'role_match_fraction', 'role_mismatch_fraction', 'actor_unspecified_fraction',
                 'receiving_actor_fraction', 'disclosing_actor_fraction', 'permission_fraction', 'obligation_fraction',
                 'negation_before_action_fraction', 'negated_permission_fraction', 'negated_obligation_fraction',
                 'condition_fraction', 'exception_fraction', 'matching_role_permission_fraction',
                 'matching_role_negation_fraction', 'matching_role_obligation_fraction',
                 'mismatching_role_permission_fraction', 'mismatching_role_negation_fraction',
                 'conditional_permission_fraction', 'exception_negation_fraction',
                 'only_without_fraction', 'actor_action_proximity', 'negation_action_proximity')
FEATURE_NAMES = BASE_NAMES + BINDING_NAMES + ('best_clause_overlap', 'best_clause_role_match',
                 'best_clause_role_mismatch', 'best_clause_negation', 'best_clause_permission',
                 'best_clause_obligation', 'best_clause_condition', 'best_clause_exception')


def tokens(text):
    return WORDS.findall(text.casefold())


def content(words):
    return [w[:-3] + 'y' if len(w) > 4 and w.endswith('ies') else
            w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w
            for w in words if w not in STOP]


def role_at(words, end):
    """Closest explicit actor cue before action, within twelve tokens; no alias oracle."""
    found = [(i, 1 if w in ROLE_RECEIVE else -1) for i, w in enumerate(words[:end + 1])
             if i >= end - 12 and w in ROLE_RECEIVE | ROLE_DISCLOSE]
    return found[-1] if found else (None, 0)


def extract(premise, hypothesis, canonical_logits):
    if not isinstance(premise, str) or not isinstance(hypothesis, str):
        raise ValueError('Only premise/hypothesis text and raw logits are feature inputs')
    logits = [float(v) for v in canonical_logits]
    if len(logits) != 3 or not all(math.isfinite(v) for v in logits):
        raise ValueError('Finite canonical E/C/N required')
    p, h = tokens(premise), tokens(hypothesis)
    ps, hs = set(content(p)), set(content(h))
    family_flags = [bool(set(h) & FAMILIES[k]) for k in ('copy', 'disclosure', 'oral')]
    action_terms = set().union(*(FAMILIES[k] for k, active in zip(('copy', 'disclosure', 'oral'), family_flags) if active))
    # For an arbitrary claim without one of the generic verb families, use its
    # content terms. These are feature observations, never predicted answers.
    action_terms = action_terms or set(hs)
    claim_role = 1 if set(h) & ROLE_RECEIVE else -1 if set(h) & ROLE_DISCLOSE else 0
    clauses = [tokens(c) for c in re.split(r'[;\n]+|(?<=[.!?])\s+', premise) if tokens(c)]
    bindings = []; best = (0., [0.] * 7)
    for words in clauses:
        positions = [i for i, w in enumerate(words) if w in action_terms or content([w]) and content([w])[0] in action_terms]
        overlap = len(set(content(words)) & hs) / max(1, len(hs))
        observations = []
        for i in positions:
            actor_position, actor = role_at(words, i)
            before = set(words[max(0, i - 6):i + 1]); around = set(words[max(0, i - 6):i + 7]); whole = set(words)
            match = float(bool(claim_role) and actor == claim_role)
            mismatch = float(bool(claim_role) and actor != 0 and actor != claim_role)
            permission = float(bool(before & PERMISSION)); obligation = float(bool(before & OBLIGATION))
            negation = float(bool(before & NEGATION)); condition = float(bool(whole & CONDITION)); exception = float(bool(whole & EXCEPTION))
            negative_positions = [j for j in range(max(0, i - 6), i + 1) if words[j] in NEGATION]
            observations.append([1., match, mismatch, float(actor == 0), float(actor == 1), float(actor == -1),
                                 permission, obligation, negation, permission * negation, obligation * negation,
                                 condition, exception, match * permission, match * negation, match * obligation,
                                 mismatch * permission, mismatch * negation, condition * permission, exception * negation,
                                 float(bool(around & {'only', 'without'})),
                                 0. if actor_position is None else 1. / (1 + i - actor_position),
                                 0. if not negative_positions else 1. / (1 + i - max(negative_positions))])
        if observations:
            means = [sum(v[j] for v in observations) / len(observations) for j in range(len(BINDING_NAMES))]
            bindings.append(means)
            local = [means[j] for j in (1, 2, 8, 6, 7, 11, 12)]
        else:
            local = [0.] * 7
        if overlap > best[0]:
            best = (overlap, local)
    aggregate = [sum(v[j] for v in bindings) / max(1, len(bindings)) for j in range(len(BINDING_NAMES))]
    aggregate[0] = len(bindings) / max(1, len(clauses))
    hpairs, ppairs = set(zip(content(h), content(h)[1:])), set(zip(content(p), content(p)[1:]))
    pn, hn = set(NUMBERS.findall(premise)), set(NUMBERS.findall(hypothesis))
    center = sum(logits) / 3
    values = [1., *(v - center for v in logits), len(ps & hs) / max(1, len(hs)),
              len(ppairs & hpairs) / max(1, len(hpairs)), min(len(p) / 512, 1.), min(len(h) / 128, 1.),
              min(len(clauses) / 32, 1.), float(claim_role == 1), float(claim_role == -1),
              *(float(v) for v in family_flags), float(bool(pn)), float(bool(hn)), len(pn & hn) / max(1, len(hn)),
              *aggregate, best[0], *best[1]]
    if len(values) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid clause-binding feature vector')
    return values
