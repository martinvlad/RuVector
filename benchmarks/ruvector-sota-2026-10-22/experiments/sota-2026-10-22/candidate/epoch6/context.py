"""Complete source partition and deterministic coherent-context packing.

This module performs tokenization only, never model inference or label lookup.
"""
from __future__ import annotations
import hashlib
import re

PARAGRAPH_BREAK = re.compile(r'(?:\r?\n)[ \t]*(?:\r?\n)+')
SENTENCE_BREAK = re.compile(r'[.!?;][\"\'\)\]]*(?:\s+|$)')
NUMBER = re.compile(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)')


def _count(tokenizer, text, special=False):
    return len(tokenizer.encode(text, add_special_tokens=special).ids)


def _fits_unit(text, nli, bge, nli_cap, bge_cap):
    return _count(nli, text) <= nli_cap and _count(bge, text, True) <= bge_cap


def _split_atom(state, start, end, nli, bge, target, nli_cap, bge_cap):
    """Keep whole legal atoms when possible; explicitly split oversized atoms."""
    if _fits_unit(state[start:end], nli, bge, nli_cap, bge_cap):
        return [{'start': start, 'end': end, 'token_fallback': False}]
    result = []
    cursor = start
    # Every chosen boundary is an observed NLI token end or the exact atom end.
    endpoints = sorted({start + b for a, b in nli.encode(state[start:end], add_special_tokens=False).offsets
                        if b > 0} | {end})
    while cursor < end:
        candidates = [point for point in endpoints if point > cursor]
        selected = None
        for point in candidates:
            text = state[cursor:point]
            if _fits_unit(text, nli, bge, target, bge_cap):
                selected = point
            else:
                break
        if selected is None:
            raise ValueError('One indivisible token span exceeds the declared unit budget; no clipping')
        result.append({'start': cursor, 'end': selected, 'token_fallback': True,
                       'fallback_origin': [start, end],
                       'fallback_boundary': 'Exact NLI tokenizer offset; full atom remains partitioned'})
        cursor = selected
    return result


def partition(state, nli, bge, *, target=128, nli_cap=160, bge_cap=256, max_units=192):
    if not isinstance(state, str) or not state:
        raise ValueError('A nonempty exact source string is required')
    if not (1 <= target <= nli_cap and bge_cap >= 2 and max_units >= 1):
        raise ValueError('Invalid fixed partition limits')
    paragraph_ends = [match.end() for match in PARAGRAPH_BREAK.finditer(state)]
    if not paragraph_ends or paragraph_ends[-1] != len(state):
        paragraph_ends.append(len(state))
    units = []
    paragraph_start = 0
    for paragraph_id, paragraph_end in enumerate(paragraph_ends):
        text = state[paragraph_start:paragraph_end]
        atom_ends = [paragraph_start + match.end() for match in SENTENCE_BREAK.finditer(text)]
        if not atom_ends or atom_ends[-1] != paragraph_end:
            atom_ends.append(paragraph_end)
        atom_start = paragraph_start
        fragments = []
        for atom_end in atom_ends:
            if atom_end > atom_start:
                fragments.extend(_split_atom(state, atom_start, atom_end, nli, bge, target, nli_cap, bge_cap))
            atom_start = atom_end
        grouped = []
        for fragment in fragments:
            if (grouped and not grouped[-1]['token_fallback'] and not fragment['token_fallback']
                    and _count(nli, state[grouped[-1]['start']:grouped[-1]['end']]) < target
                    and _fits_unit(state[grouped[-1]['start']:fragment['end']], nli, bge, nli_cap, bge_cap)):
                grouped[-1]['end'] = fragment['end']
            else:
                grouped.append(dict(fragment))
        for unit in grouped:
            unit.update(id=len(units), paragraph_id=paragraph_id,
                        nli_tokens=_count(nli, state[unit['start']:unit['end']]),
                        bge_tokens=_count(bge, state[unit['start']:unit['end']], True))
            units.append(unit)
        paragraph_start = paragraph_end
    if len(units) > max_units:
        raise ValueError(f'Source exceeds fixed{max_units}-unit budget; full partition rejected before any forward')
    if (not units or units[0]['start'] != 0 or units[-1]['end'] != len(state)
            or any(a['end'] != b['start'] for a, b in zip(units, units[1:]))
            or any(u['start'] >= u['end'] or u['nli_tokens'] > nli_cap or u['bge_tokens'] > bge_cap for u in units)):
        raise ValueError('Incomplete or invalid source partition')
    return units


def merge_selected(units, selected):
    if not selected or len(selected) != len(set(selected)) or any(type(i) is not int or i < 0 or i >= len(units) for i in selected):
        raise ValueError('Invalid source-unit IDs')
    spans = []
    for index in sorted(selected):
        start, end = units[index]['start'], units[index]['end']
        if spans and start == spans[-1][1]:
            spans[-1] = (spans[-1][0], end)
        else:
            spans.append((start, end))
    return spans


def pack(state, units, ranking, hypothesis, nli, *, pair_cap=512, rank_depth=40):
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        raise ValueError('Exact complete hypothesis is required')
    ranking = list(ranking)
    if not ranking or len(ranking) != len(set(ranking)) or any(type(i) is not int or i < 0 or i >= len(units) for i in ranking):
        raise ValueError('Invalid observed ranking')
    if len(nli.encode('', hypothesis).ids) > pair_cap:
        raise ValueError('Whole hypothesis exceeds pair budget; no clipping')
    ranking = ranking[:rank_depth]
    selected, trace = [], []

    def attempt(index, role, anchor):
        if index in selected:
            return True
        spans = merge_selected(units, selected + [index])
        premise = '\n\n'.join(state[start:end] for start, end in spans)
        count = len(nli.encode(premise, hypothesis).ids)
        accepted = count <= pair_cap
        trace.append({'unit_id': index, 'role': role, 'anchor': anchor,
                      'candidate_pair_tokens': count, 'accepted': accepted})
        if accepted:
            selected.append(index)
        return accepted

    for anchor in ranking:
        if anchor in selected:
            continue
        if not attempt(anchor, 'ranked-anchor', anchor):
            continue
        for neighbor in (anchor - 1, anchor + 1):
            if 0 <= neighbor < len(units) and units[neighbor]['paragraph_id'] == units[anchor]['paragraph_id']:
                attempt(neighbor, 'same-paragraph-neighbor', anchor)
    if not selected:
        raise ValueError('No complete source unit fits whole hypothesis budget; no clipping')
    spans = merge_selected(units, selected)
    premise = '\n\n'.join(state[start:end] for start, end in spans)
    pair_tokens = len(nli.encode(premise, hypothesis).ids)
    if pair_tokens > pair_cap:
        raise ValueError('Packed joint context exceeds exact token budget')
    selected_set = set(selected)
    omitted = [unit['id'] for unit in units if unit['id'] not in selected_set]
    numbers = [{'span': [match.start(), match.end()], 'text': match.group(),
                'retained': any(start <= match.start() and match.end() <= end for start, end in spans)}
               for match in NUMBER.finditer(state)]
    covered = sum(end - start for start, end in spans)
    audit = {'policy': 'Scan ranked anchor candidates; previous/next same-paragraph expansion may inspect additional units; all admissions use the exact joint pair budget',
             'ranking_ids_considered': ranking, 'ranking_depth': len(ranking),
             'ranked_anchor_candidate_cap': rank_depth, 'joint_pair_token_cap': pair_cap,
             'additional_neighbor_unit_ids_inspected': sorted({item['unit_id'] for item in trace
                                                               if item['role'] == 'same-paragraph-neighbor'
                                                               and item['unit_id'] not in ranking}),
             'selected_chunk_ids_rank_order': selected, 'selected_chunk_ids_source_order': sorted(selected),
             'selected_source_spans': [list(span) for span in spans], 'omitted_chunk_ids': omitted,
             'omitted_source_spans': [[units[i]['start'], units[i]['end']] for i in omitted],
             'total_document_chunks': len(units), 'retained_source_characters': covered,
             'document_characters': len(state), 'document_character_coverage': covered / len(state),
             'joint_pair_tokens': pair_tokens, 'selected_evidence_truncated': False, 'claim_truncated': False,
             'premise_sha256': hashlib.sha256(premise.encode()).hexdigest(),
             'hypothesis_sha256': hashlib.sha256(hypothesis.encode()).hexdigest(),
             'packing_attempts': trace,
             'selected_token_fallback_unit_ids': [i for i in selected if units[i]['token_fallback']],
             'numeric_mentions': numbers,
             'numeric_mentions_retained': sum(item['retained'] for item in numbers),
             'numeric_mentions_omitted': sum(not item['retained'] for item in numbers),
             'scope': 'Mechanical source coverage only. Omission or retention establishes neither entailment nor insufficient evidence.'}
    return premise, audit
