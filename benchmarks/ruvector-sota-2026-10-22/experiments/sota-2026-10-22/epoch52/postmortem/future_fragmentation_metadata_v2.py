"""Future-study engineering prototype; never an E52 execution path.

Pure source-span planning with an externally supplied capacity oracle. The actual
tokenizer/model is deliberately absent. Inert fixtures use invented strings and
oracles only. Exact character coverage does not prove semantic context preservation.
The bounded greedy planner does not backtrack; failure is not proof that no
alternative complete partition could fit under a nonmonotonic capacity oracle.
"""
import hashlib
import re
import unicodedata

PROTECTED = re.compile(
    r'[$€£¥]?\b\d+(?:[.,:/-]\d+)*(?:\s?(?:%|USD|EUR|GBP|days?|years?))?'
    r'|\b(?:not|no|never|unless|except|without)\b', re.IGNORECASE)


def safe_cuts(text):
    """No rewrite; propose exact codepoint boundaries outside protected occurrences."""
    if type(text) is not str or not text.strip():
        raise ValueError('NONEMPTY_SOURCE_REQUIRED')
    protected = [(m.start(), m.end()) for m in PROTECTED.finditer(text)]
    cuts = []
    for at in range(1, len(text)):
        if not (text[at - 1].isspace() or text[at - 1] in ';,:.!?'):
            continue
        if unicodedata.combining(text[at]) or '\u200d' in text[at - 1:at + 1]:
            continue
        if any(start < at < end for start, end in protected):
            continue
        cuts.append(at)
    return [*cuts, len(text)]


def partition_offsets(text, pair_token_count, max_tokens=512, max_pieces=16,
                      max_checks=4096, cuts=None):
    """Select furthest admissible exact span; never assumes monotonic token counts.

    A future actual oracle must compute the maximum original genuine-pair length
    over every frozen hypothesis for this document, without a model forward. Every
    check counts against the same bounded experiment clock. If this greedy path or
    bounded budget fails, reject the entire batch; never return a partial partition.
    Furthest-admissible greedy choices do not establish global partition feasibility:
    an alternative earlier cut can admit a later tail that this path cannot cover.
    Failure means only this frozen bounded planner did not produce a fullpartition.
    """
    if type(text) is not str or not text.strip():
        raise ValueError('NONEMPTY_SOURCE_REQUIRED')
    if not all(type(x) is int and x > 0 for x in (max_tokens, max_pieces, max_checks)):
        raise ValueError('POSITIVE_FROZEN_INTEGER_LIMITS_REQUIRED')
    candidates = safe_cuts(text) if cuts is None else cuts
    if (type(candidates) is not list or not candidates
            or any(type(x) is not int for x in candidates)
            or candidates != sorted(set(candidates)) or candidates[-1] != len(text)
            or candidates[0] <= 0):
        raise ValueError('EXACT_ORDERED_CUT_BOUNDARIES_REQUIRED')
    allowed = set(safe_cuts(text))
    if not set(candidates) <= allowed:
        raise ValueError('PROTECTED_OR_NONAUTHORITATIVE_CUT')
    start = 0; pieces = []; checks = 0
    while start < len(text):
        chosen = None
        for end in reversed(candidates):
            if end <= start:
                continue
            if checks == max_checks:
                raise ValueError('FROZEN_CAPACITY_CHECK_BUDGET_EXHAUSTED')
            checks += 1
            count = pair_token_count(start, end)
            if type(count) is not int or count <= 0:
                raise ValueError('EXACT_POSITIVE_GENUINE_PAIR_TOKEN_COUNT_REQUIRED')
            if count <= max_tokens:
                chosen = (end, count); break
        if chosen is None:
            raise ValueError('NO_SAFE_COMPLETE_CAPACITY_PARTITION_NO_FALLBACK')
        if len(pieces) == max_pieces:
            raise ValueError('FROZEN_FRAGMENT_COUNT_EXCEEDED')
        end, count = chosen
        value = text[start:end]
        pieces.append(dict(start=start, end=end, checked_pair_tokens=count,
                           exact_source_slice_sha256=hashlib.sha256(value.encode()).hexdigest()))
        start = end
    assert ''.join(text[p['start']:p['end']] for p in pieces) == text
    assert pieces[0]['start'] == 0 and pieces[-1]['end'] == len(text)
    assert all(a['end'] == b['start'] for a, b in zip(pieces, pieces[1:]))
    return dict(pieces=pieces, capacity_checks=checks,
                source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                exact_all_source_characters_once=True,
                protected_occurrences_not_split=True,
                semantic_context_preservation_guaranteed=False,
                benchmark_accuracy_or_generalization_measured=False,
                original_source_not_rewritten=True)
