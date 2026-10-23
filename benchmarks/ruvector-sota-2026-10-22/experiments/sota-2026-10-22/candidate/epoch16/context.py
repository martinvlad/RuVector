"""Exact epoch15 source policy with one premise fitting BOTH whole propositions.

Only joint-pair admission changes. Partition, definition priority, ranked
anchors, neighbors, exact source spans and global source order remain shared.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent / 'epoch15/context.py'
BASE_SHA256 = '9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'
if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
    raise ValueError('Frozen epoch15 definition/source policy changed')
_spec = importlib.util.spec_from_file_location('epoch16_frozen_definition_context15', BASE_PATH)
BASE15 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BASE15)
partition = BASE15.partition
select_prelude = BASE15.select_prelude
_premise = BASE15._premise


def pair_counts(nli, premise, hypothesis, counterclaim):
    return {'positive': len(nli.encode(premise, hypothesis).ids),
            'counterclaim': len(nli.encode(premise, counterclaim).ids)}


def pack(state, units, ranking, hypothesis, counterclaim, nli, *, pair_cap=512,
         rank_depth=40, prelude=None):
    if not all(isinstance(x, str) and x.strip() for x in (hypothesis, counterclaim)):
        raise ValueError('Both exact whole propositions are required')
    ranking = list(ranking)
    if (not ranking or len(ranking) != len(set(ranking)) or
            any(type(i) is not int or not 0 <= i < len(units) for i in ranking)):
        raise ValueError('Invalid observed ranking')
    if max(pair_counts(nli, '', hypothesis, counterclaim).values()) > pair_cap:
        raise ValueError('Whole positive/counterclaim exceeds pair budget; no clipping')
    expected = select_prelude(state, units, nli)
    if prelude is not None and prelude != expected:
        raise ValueError('Shared claim-independent priority changed')
    prelude = expected
    selected = list(prelude['selected_unit_ids'])
    priority_text, _ = _premise(state, units, selected)
    if max(pair_counts(nli, priority_text, hypothesis, counterclaim).values()) > pair_cap:
        raise ValueError('Whole priority and whole propositions cannot jointly fit; no silent drop')
    trace = []
    ranking = ranking[:rank_depth]

    def attempt(index, role, anchor):
        if index in selected:
            return True
        premise, _ = _premise(state, units, selected + [index])
        counts = pair_counts(nli, premise, hypothesis, counterclaim)
        accepted = max(counts.values()) <= pair_cap
        trace.append({'unit_id': index, 'role': role, 'anchor': anchor,
                      'candidate_positive_pair_tokens': counts['positive'],
                      'candidate_counterclaim_pair_tokens': counts['counterclaim'],
                      'candidate_pair_tokens': max(counts.values()), 'accepted': accepted})
        if accepted:
            selected.append(index)
        return accepted

    for anchor in ranking:
        if anchor in selected:
            continue
        if not attempt(anchor, 'ranked-anchor', anchor):
            continue
        for neighbor in (anchor - 1, anchor + 1):
            if (0 <= neighbor < len(units) and
                    units[neighbor]['paragraph_id'] == units[anchor]['paragraph_id']):
                attempt(neighbor, 'same-paragraph-neighbor', anchor)
    if not selected:
        raise ValueError('No complete source unit fits both propositions; no clipping')
    premise, spans = _premise(state, units, selected)
    counts = pair_counts(nli, premise, hypothesis, counterclaim)
    if max(counts.values()) > pair_cap:
        raise ValueError('Packed context exceeds exact BOTH-pair cap')
    selected_set = set(selected)
    omitted = [u['id'] for u in units if u['id'] not in selected_set]
    numbers = [{'span': [m.start(), m.end()], 'text': m.group(),
                'retained': any(a <= m.start() and m.end() <= b for a, b in spans)}
               for m in BASE15.BASE.NUMBER.finditer(state)]
    covered = sum(b - a for a, b in spans)
    audit = {
        'policy': 'Unchanged15 whole-unit priority/anchors/neighbors/global source order; BOTH exact H/Q pair admission',
        'definition_priority': prelude, 'ranking_ids_considered': ranking,
        'ranking_depth': len(ranking), 'ranked_anchor_candidate_cap': rank_depth,
        'joint_pair_token_cap': pair_cap,
        'additional_neighbor_unit_ids_inspected': sorted({x['unit_id'] for x in trace
            if x['role'] == 'same-paragraph-neighbor' and x['unit_id'] not in ranking}),
        'selected_chunk_ids_rank_order': selected,
        'selected_chunk_ids_source_order': sorted(selected),
        'selected_source_spans': [list(x) for x in spans], 'omitted_chunk_ids': omitted,
        'omitted_source_spans': [[units[i]['start'], units[i]['end']] for i in omitted],
        'total_document_chunks': len(units), 'retained_source_characters': covered,
        'document_characters': len(state), 'document_character_coverage': covered / len(state),
        'positive_joint_pair_tokens': counts['positive'],
        'counterclaim_joint_pair_tokens': counts['counterclaim'],
        'joint_pair_tokens': max(counts.values()),
        'selected_evidence_truncated': False, 'claim_truncated': False,
        'counterclaim_truncated': False, 'premise_sha256': hashlib.sha256(premise.encode()).hexdigest(),
        'hypothesis_sha256': hashlib.sha256(hypothesis.encode()).hexdigest(),
        'counterclaim_sha256': hashlib.sha256(counterclaim.encode()).hexdigest(),
        'packing_attempts': trace,
        'selected_token_fallback_unit_ids': [i for i in selected if units[i]['token_fallback']],
        'numeric_mentions': numbers, 'numeric_mentions_retained': sum(x['retained'] for x in numbers),
        'numeric_mentions_omitted': sum(not x['retained'] for x in numbers),
        'semantic_ablation': 'RawH model pass uses this SAME premise; no extra forward and no old15-context equivalence claim.',
        'scope': 'Mechanical source/token/number retention only; no arithmetic truth or semantic sufficiency/absence proof.',
    }
    return premise, audit
