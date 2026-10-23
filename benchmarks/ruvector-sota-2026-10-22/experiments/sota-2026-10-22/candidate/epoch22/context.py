"""Exact-source sentence/semicolon groups; no labels, parsers or inference.

Ranked groups are admitted atomically before optional neighbor filler. Native,
lexical and positional unit rankings use the same first-member group mapping.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import re


def _load(name, epoch, digest):
    path = Path(__file__).resolve().parent.parent / epoch / 'context.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Pinned pure source-context dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


BASE = _load('epoch22_exact_context6', 'epoch6',
             '28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2')
PRIORITY = _load('epoch22_exact_definition_markers15', 'epoch15',
                 '9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb')
POLICY = 'source-sentence-qualifier-groups-ranked-before-neighbors-v1'
BULLET = re.compile(r'^\s*(?:(?:\([a-zA-Z0-9]+\)|[a-zA-Z0-9]+[.)])\s+)?')
QUALIFIER = re.compile(
    r'^(?:provided\b|however\b|except\b|unless\b|notwithstanding\b|subject\s+to\b|'
    r'in\s+(?:such|that)\s+(?:case|event)\b|in\s+(?:the\s+)?event\b|'
    r'such\s+(?:disclosure|information|copies|copy)\b|any\s+such\b|'
    r'only\b|to\s+the\s+extent\b|upon\b|at\s+(?:the\s+|a\s+)?request\b|'
    r'and\s+(?:only|provided)\b|but\b)', re.IGNORECASE)


def atoms(state):
    if not isinstance(state, str) or not state:
        raise ValueError('A nonempty exact source string is required')
    ends = [m.end() for m in BASE.PARAGRAPH_BREAK.finditer(state)]
    if not ends or ends[-1] != len(state): ends.append(len(state))
    rows = []; start = 0; group_id = -1
    for paragraph_id, end in enumerate(ends):
        atom_ends = [start + m.end() for m in BASE.SENTENCE_BREAK.finditer(state[start:end])]
        if not atom_ends or atom_ends[-1] != end: atom_ends.append(end)
        cursor = start
        for stop in atom_ends:
            if stop <= cursor: continue
            text = state[cursor:stop]
            leading = BULLET.sub('', text, count=1)
            attached = bool(rows and rows[-1]['paragraph_id'] == paragraph_id and QUALIFIER.search(leading))
            if not attached: group_id += 1
            rows.append({'sentence_id': len(rows), 'start': cursor, 'end': stop,
                         'paragraph_id': paragraph_id, 'group_id': group_id,
                         'qualifier_attached': attached})
            cursor = stop
        start = end
    return rows


def partition(state, nli, bge, *, target=128, nli_cap=160, bge_cap=256, max_units=192):
    if (target, nli_cap, bge_cap, max_units) != (128, 160, 256, 192):
        raise ValueError('Exact frozen source partition budgets required')
    units = []
    for atom in atoms(state):
        for part in BASE._split_atom(state, atom['start'], atom['end'], nli, bge, target, nli_cap, bge_cap):
            text = state[part['start']:part['end']]
            part.update(id=len(units), paragraph_id=atom['paragraph_id'],
                sentence_id=atom['sentence_id'], sentence_span=[atom['start'], atom['end']],
                group_id=atom['group_id'], qualifier_attached=atom['qualifier_attached'],
                nli_tokens=BASE._count(nli, text), bge_tokens=BASE._count(bge, text, True))
            units.append(part)
    if len(units) > max_units:
        raise ValueError('Complete source exceeds192 units; no tail clipping or adaptive fallback')
    groups(state, units)
    return units


def groups(state, units):
    expected = atoms(state); by_sentence = {a['sentence_id']: a for a in expected}
    result = []; cursor = 0
    for i, u in enumerate(units):
        a = by_sentence.get(u.get('sentence_id'))
        if (a is None or u['id'] != i or u['start'] != cursor or not cursor < u['end'] <= a['end']
                or u['start'] < a['start'] or u['sentence_span'] != [a['start'], a['end']]
                or any(u[k] != a[k] for k in ('paragraph_id', 'group_id', 'qualifier_attached'))):
            raise ValueError('Exact contiguous atom/unit/group metadata required')
        if not result or result[-1]['group_id'] != a['group_id']:
            if a['group_id'] != len(result): raise ValueError('Dense contiguous source group IDs required')
            result.append({'group_id': a['group_id'], 'start': u['start'], 'end': u['end'],
                'paragraph_id': a['paragraph_id'], 'unit_ids': [], 'sentence_ids': [],
                'qualifier_sentence_ids': [], 'token_fallback': False})
        g = result[-1]; g['end'] = u['end']; g['unit_ids'].append(i)
        if a['sentence_id'] not in g['sentence_ids']: g['sentence_ids'].append(a['sentence_id'])
        if a['qualifier_attached'] and a['sentence_id'] not in g['qualifier_sentence_ids']:
            g['qualifier_sentence_ids'].append(a['sentence_id'])
        g['token_fallback'] |= u['token_fallback']; cursor = u['end']
    if not units or cursor != len(state): raise ValueError('Complete source partition required')
    return result


def _premise(state, units, ids):
    if not ids: return '', []
    spans = BASE.merge_selected(units, ids)
    return '\n\n'.join(state[a:b] for a, b in spans), spans


def select_prelude(state, units, nli):
    selected, selected_groups, attempts = [], [], []
    for group in groups(state, units):
        start, end = group['start'], group['end']; text = state[start:end]; triggers = []
        if PRIORITY.DEFINITION.search(text): triggers.append('explicit-definition-marker')
        if PRIORITY.NAMED_PARENTHETICAL.search(text): triggers.append('explicit-quoted-named-term-parenthetical')
        initial = state[start:min(end, PRIORITY.INITIAL_PARTY_CHARACTER_CAP)]
        if start < PRIORITY.INITIAL_PARTY_CHARACTER_CAP and PRIORITY.BETWEEN.search(initial) and PRIORITY.PARTY.search(initial):
            triggers.append('initial-party-declaration')
        if not triggers: continue
        candidate, _ = _premise(state, units, selected + group['unit_ids'])
        count = BASE._count(nli, candidate)
        accept = not group['token_fallback'] and count <= PRIORITY.PRELUDE_TOKEN_CAP
        attempts.append({'group_id': group['group_id'], 'unit_ids': group['unit_ids'],
            'span': [start, end], 'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'triggers': triggers, 'candidate_priority_tokens': count, 'accepted': accept,
            'reason': 'admitted-whole-source-group' if accept else 'fallback-or-whole-group-exceeds160'})
        if accept: selected.extend(group['unit_ids']); selected_groups.append(group['group_id'])
    text, spans = _premise(state, units, selected)
    return {'policy': POLICY + ':claim-independent-whole-group-definition-priority',
        'selected_unit_ids': selected, 'selected_group_ids': selected_groups,
        'selected_source_spans': [list(s) for s in spans], 'priority_tokens': BASE._count(nli, text),
        'priority_token_cap': 160, 'priority_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'candidate_attempts': attempts, 'whole_groups_only': True, 'token_fallback_admitted': False,
        'claim_dependent': False, 'literal_first_text_guaranteed': False}


def pack(state, units, ranking, hypothesis, nli, *, pair_cap=512, rank_depth=40, prelude=None):
    ranking = list(ranking)
    if (pair_cap != 512 or rank_depth != min(40, len(units)) or not ranking
            or len(ranking) != len(set(ranking)) or any(type(i) is not int or not 0 <= i < len(units) for i in ranking)):
        raise ValueError('Exact observed top40 unit ranking and frozen budgets required')
    if not isinstance(hypothesis, str) or not hypothesis.strip() or len(nli.encode('', hypothesis).ids) > pair_cap:
        raise ValueError('Whole unchanged hypothesis must fit; no clipping')
    catalog = groups(state, units); ranking = ranking[:rank_depth]
    expected = select_prelude(state, units, nli)
    if prelude is not None and prelude != expected: raise ValueError('Shared source-only prelude changed')
    prelude = expected; selected = list(prelude['selected_unit_ids'])
    priority_text, _ = _premise(state, units, selected)
    if len(nli.encode(priority_text, hypothesis).ids) > pair_cap:
        raise ValueError('Complete shared prelude and claim do not fit; no silent drop')
    order, anchors = [], {}
    for unit_id in ranking:
        gid = units[unit_id]['group_id']
        if gid not in anchors: order.append(gid); anchors[gid] = unit_id
    selected_groups = list(prelude['selected_group_ids']); trace = []; admitted = []

    def attempt(gid, role, anchor):
        if gid in selected_groups: return True
        group = catalog[gid]
        premise, _ = _premise(state, units, selected + group['unit_ids'])
        count = len(nli.encode(premise, hypothesis).ids); accept = count <= pair_cap
        trace.append({'group_id': gid, 'unit_ids': group['unit_ids'], 'role': role, 'anchor': anchor,
                      'source_span': [group['start'], group['end']], 'candidate_pair_tokens': count,
                      'accepted': accept, 'all_group_units_admitted_together': accept})
        if accept: selected.extend(group['unit_ids']); selected_groups.append(gid)
        return accept

    for gid in order:
        if gid in selected_groups: continue
        if attempt(gid, 'ranked-sentence-group', anchors[gid]): admitted.append(gid)
    inspected = set(order) | set(selected_groups)
    for gid in admitted:
        for neighbor in (gid - 1, gid + 1):
            if (0 <= neighbor < len(catalog) and neighbor not in inspected
                    and catalog[neighbor]['paragraph_id'] == catalog[gid]['paragraph_id']):
                inspected.add(neighbor); attempt(neighbor, 'optional-neighbor-group-after-all-ranked', anchors[gid])
    if not selected: raise ValueError('No complete source group fits; no fragment fallback or clipping')
    premise, spans = _premise(state, units, selected); count = len(nli.encode(premise, hypothesis).ids)
    if count > pair_cap: raise ValueError('Packed source exceeds512 joint tokens')
    chosen = set(selected); omitted = [u['id'] for u in units if u['id'] not in chosen]
    numbers = [{'span': [m.start(), m.end()], 'text': m.group(),
        'retained': any(a <= m.start() and m.end() <= b for a, b in spans)} for m in BASE.NUMBER.finditer(state)]
    covered = sum(b - a for a, b in spans)
    receipt = {'policy': POLICY, 'definition_priority': prelude, 'source_sentence_groups': catalog,
        'qualifier_regex': QUALIFIER.pattern, 'bullet_regex': BULLET.pattern,
        'group_ranking_policy': 'First observed member unit in unchanged observed top40 ranking; no new scores or reordering',
        'group_ranking_ids': order, 'group_ranking_anchor_unit_ids': [anchors[g] for g in order],
        'selected_group_ids_admission_order': selected_groups, 'all_selected_groups_complete': True,
        'ranking_ids_considered': ranking, 'ranking_depth': len(ranking),
        'ranked_anchor_candidate_cap': rank_depth, 'joint_pair_token_cap': pair_cap,
        'additional_neighbor_unit_ids_inspected': sorted({i for a in trace if a['role'].startswith('optional-neighbor') for i in a['unit_ids'] if i not in ranking}),
        'selected_chunk_ids_rank_order': selected, 'selected_chunk_ids_source_order': sorted(selected),
        'selected_source_spans': [list(s) for s in spans], 'omitted_chunk_ids': omitted,
        'omitted_source_spans': [[units[i]['start'], units[i]['end']] for i in omitted],
        'total_document_chunks': len(units), 'retained_source_characters': covered,
        'document_characters': len(state), 'document_character_coverage': covered / len(state),
        'joint_pair_tokens': count, 'selected_evidence_truncated': False, 'claim_truncated': False,
        'premise_sha256': hashlib.sha256(premise.encode()).hexdigest(),
        'hypothesis_sha256': hashlib.sha256(hypothesis.encode()).hexdigest(), 'packing_attempts': trace,
        'selected_token_fallback_unit_ids': [i for i in selected if units[i]['token_fallback']],
        'numeric_mentions': numbers, 'numeric_mentions_retained': sum(n['retained'] for n in numbers),
        'numeric_mentions_omitted': sum(not n['retained'] for n in numbers),
        'scope': 'Exact mechanical atom/group/qualifier/number retention only. Neither retention nor omission proves evidence sufficiency or a typed decision.'}
    return premise, receipt
