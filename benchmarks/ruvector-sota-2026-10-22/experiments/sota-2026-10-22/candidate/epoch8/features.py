"""Inference-only generic legal/deontic features; no IDs, roles or labels."""
from __future__ import annotations
import math
import re

CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')
FEATURE_NAMES = (
    'bias', 'centered_logit_entailment', 'centered_logit_contradiction', 'centered_logit_notmentioned',
    'claim_content_overlap', 'claim_bigram_overlap', 'premise_length_512', 'hypothesis_length_128',
    'premise_permission', 'claim_permission', 'premise_obligation', 'claim_obligation',
    'premise_negation', 'claim_negation', 'premise_exception', 'claim_exception',
    'premise_condition', 'claim_condition', 'premise_numeric', 'claim_numeric', 'claim_numeric_overlap',
    'permission_interaction', 'obligation_interaction', 'negation_interaction', 'negated_modal_claim',
    'negation_near_claim', 'permission_near_claim', 'obligation_near_claim', 'exception_near_claim',
)
PERMISSION = frozenset(('may', 'can', 'permitted', 'allowed', 'entitled', 'permission'))
OBLIGATION = frozenset(('shall', 'must', 'required', 'obligated', 'obligation', 'undertakes'))
NEGATION = frozenset(('not', 'no', 'never', 'neither', 'nor', 'without', 'cannot', 'prohibited', 'forbidden'))
EXCEPTION = frozenset(('unless', 'except', 'excluding', 'however', 'notwithstanding', 'provided'))
CONDITION = frozenset(('if', 'when', 'where', 'subject', 'condition', 'conditions'))
STOP = frozenset(('a', 'an', 'the', 'some', 'any', 'of', 'to', 'in', 'on', 'with', 'and', 'or', 'by', 'for',
                  'be', 'is', 'are', 'as', 'that', 'this', 'may', 'shall', 'must', 'can', 'not'))
WORDS = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
NUMBERS = re.compile(r'(?<!\w)\d+(?:[.,]\d+)*(?!\w)')


def tokens(text):
    return WORDS.findall(text.casefold())


def content(words):
    return [word[:-3] + 'y' if len(word) > 4 and word.endswith('ies')
            else word[:-1] if len(word) > 4 and word.endswith('s') and not word.endswith('ss')
            else word for word in words if word not in STOP]


def extract(premise, hypothesis, canonical_logits):
    if not isinstance(premise, str) or not isinstance(hypothesis, str):
        raise ValueError('Only source premise and exact textual hypothesis are feature inputs')
    logits = [float(value) for value in canonical_logits]
    if len(logits) != 3 or not all(math.isfinite(value) for value in logits):
        raise ValueError('Three finite canonical E/C/N logits are required')
    center = sum(logits) / 3
    p, h = tokens(premise), tokens(hypothesis)
    pc, hc = content(p), content(h)
    ps, hs = set(pc), set(hc)
    pset, hset = set(p), set(h)
    hpairs = set(zip(hc, hc[1:])); ppairs = set(zip(pc, pc[1:]))
    pnums, hnums = set(NUMBERS.findall(premise)), set(NUMBERS.findall(hypothesis))
    indicators = []
    for vocabulary in (PERMISSION, OBLIGATION, NEGATION, EXCEPTION, CONDITION):
        indicators.extend((float(bool(pset & vocabulary)), float(bool(hset & vocabulary))))
    pp, hp, po, ho, pn, hn, pe, he, pi, hi = indicators
    positions = [index for index, word in enumerate(p) if content([word]) and content([word])[0] in hs]

    def near(vocabulary):
        if not positions:
            return 0.0
        return sum(any(word in vocabulary for word in p[max(0, index - 4):index + 5])
                   for index in positions) / len(positions)

    values = [1.0, *(value - center for value in logits),
              len(ps & hs) / max(1, len(hs)), len(ppairs & hpairs) / max(1, len(hpairs)),
              min(len(p) / 512, 1.0), min(len(h) / 128, 1.0),
              *indicators, float(bool(pnums)), float(bool(hnums)), len(pnums & hnums) / max(1, len(hnums)),
              pp * hp, po * ho, pn * hn, pn * float(bool(hp or ho)),
              near(NEGATION), near(PERMISSION), near(OBLIGATION), near(EXCEPTION)]
    if len(values) != len(FEATURE_NAMES) or not all(math.isfinite(value) for value in values):
        raise ValueError('Invalid feature vector')
    return values
