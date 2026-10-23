"""Reviewed exact-source policy, admitted against BOTH actual reader tokenizers.

No claim negation, rewrite, clipping or semantic absence inference. A wrapper
returns the longer actual encoding for each source token budget; actual model
feeds always use each reader's own tokenizer on the same whole text.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent / 'epoch15/context.py'
BASE_SHA256 = '9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'
if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
    raise ValueError('Reviewed epoch15 exact-source definition policy changed')
_spec = importlib.util.spec_from_file_location('epoch17_frozen_context15', BASE_PATH)
BASE15 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BASE15)
_premise = BASE15._premise


class JointTokenizer:
    """Longer exact tokenization; tie deterministically favors new tokenizer."""
    def __init__(self, new, previous):
        self.new, self.previous = new, previous

    def encode(self, text, pair=None, add_special_tokens=True):
        kwargs = {'add_special_tokens': add_special_tokens}
        new = self.new.encode(text, pair, **kwargs)
        previous = self.previous.encode(text, pair, **kwargs)
        return new if len(new.ids) >= len(previous.ids) else previous


def pair_counts(new, previous, premise, hypothesis):
    return {'new_reader_joint_pair_tokens': len(new.encode(premise, hypothesis).ids),
            'previous_reader_joint_pair_tokens': len(previous.encode(premise, hypothesis).ids)}


def partition(state, new, previous, bge, **limits):
    return BASE15.partition(state, JointTokenizer(new, previous), bge, **limits)


def select_prelude(state, units, new, previous):
    result = BASE15.select_prelude(state, units, JointTokenizer(new, previous))
    premise, _ = _premise(state, units, result['selected_unit_ids'])
    result['new_reader_priority_tokens'] = len(new.encode(premise, add_special_tokens=False).ids)
    result['previous_reader_priority_tokens'] = len(previous.encode(premise, add_special_tokens=False).ids)
    result['priority_token_budget_scope'] = 'Maximum of both actual no-special token counts; same whole source IDs'
    return result


def pack(state, units, ranking, hypothesis, new, previous, *, pair_cap=512,
         rank_depth=40, prelude=None):
    expected = select_prelude(state, units, new, previous)
    if prelude is not None and prelude != expected:
        raise ValueError('Shared whole-source priority changed')
    # BASE15 checks its original priority receipt; extra dual-reader facts are
    # attached after its exact unchanged algorithm finishes.
    base_priority = BASE15.select_prelude(state, units, JointTokenizer(new, previous))
    premise, coverage = BASE15.pack(state, units, ranking, hypothesis,
                                    JointTokenizer(new, previous), pair_cap=pair_cap,
                                    rank_depth=rank_depth, prelude=base_priority)
    selected = list(base_priority['selected_unit_ids'])
    for attempt in coverage['packing_attempts']:
        candidate, _ = _premise(state, units, selected + [attempt['unit_id']])
        tokens = pair_counts(new, previous, candidate, hypothesis)
        attempt['candidate_new_reader_pair_tokens'] = tokens['new_reader_joint_pair_tokens']
        attempt['candidate_previous_reader_pair_tokens'] = tokens['previous_reader_joint_pair_tokens']
        if attempt['accepted']:
            selected.append(attempt['unit_id'])
    counts = pair_counts(new, previous, premise, hypothesis)
    if max(counts.values()) > pair_cap:
        raise ValueError('Whole same-premise source exceeds either actual reader token budget')
    coverage.update(counts)
    coverage.update(definition_priority=expected, joint_pair_tokens=max(counts.values()),
                    policy='Reviewed15 source partition/priority160/anchors/neighbors/global order; maximum BOTH reader token counts, whole unchanged H only',
                    previous_reader_same_exact_premise=True,
                    no_not_pairing=True,
                    scope='Mechanical source/token/number retention only; no arithmetic truth, semantic sufficiency or absence proof')
    return premise, coverage
