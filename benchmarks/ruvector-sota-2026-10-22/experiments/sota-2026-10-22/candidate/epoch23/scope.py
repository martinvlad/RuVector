"""Exact supplied-range dependency closure; no legal or entailment decisions."""
from __future__ import annotations

import hashlib
import re


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_graph(case):
    """Validate the whole annotated graph before any source is retrieved."""
    errors = []
    excerpts = {}
    units = {}
    if not isinstance(case, dict) or set(case) != {
            'id', 'query', 'excerpts', 'units', 'budget', 'seed_limit'}:
        return {'valid': False, 'errors': [{'reason': 'CASE_SCHEMA'}],
                'excerpts': {}, 'units': {}}
    if not isinstance(case['id'], str) or not case['id']:
        errors.append({'reason': 'CASE_ID'})
    if not isinstance(case['query'], str) or not case['query'].strip():
        errors.append({'reason': 'QUERY_TEXT'})
    budget = case['budget']
    if (not isinstance(budget, dict) or set(budget) != {'max_utf8_bytes', 'max_nodes'}
            or any(type(budget[k]) is not int or budget[k] < 0 for k in budget)):
        errors.append({'reason': 'BUDGET_SCHEMA'})
    if type(case['seed_limit']) is not int or not 0 <= case['seed_limit'] <= 256:
        errors.append({'reason': 'SEED_LIMIT'})
    if not isinstance(case['excerpts'], list) or not 1 <= len(case['excerpts']) <= 64:
        errors.append({'reason': 'EXCERPT_LIST'})
    else:
        for index, row in enumerate(case['excerpts']):
            if (not isinstance(row, dict) or set(row) != {'id', 'text'}
                    or not isinstance(row['id'], str) or not row['id']
                    or not isinstance(row['text'], str)):
                errors.append({'reason': 'EXCERPT_SCHEMA', 'index': index})
                continue
            if row['id'] in excerpts:
                errors.append({'reason': 'DUPLICATE_EXCERPT_ID', 'id': row['id']})
                continue
            try:
                row['text'].encode('utf-8')
            except UnicodeEncodeError:
                errors.append({'reason': 'INVALID_SOURCE_UTF8', 'id': row['id']})
                continue
            excerpts[row['id']] = dict(row, source_order=index,
                source_sha256=sha_text(row['text']))
    if not isinstance(case['units'], list) or len(case['units']) > 256:
        errors.append({'reason': 'UNIT_LIST'})
    else:
        for index, row in enumerate(case['units']):
            if (not isinstance(row, dict) or set(row) != {
                    'id', 'excerpt_id', 'start', 'end', 'requires'}
                    or not isinstance(row['id'], str) or not row['id']
                    or not isinstance(row['excerpt_id'], str)
                    or type(row['start']) is not int or type(row['end']) is not int
                    or not isinstance(row['requires'], list)
                    or any(not isinstance(x, str) or not x for x in row['requires'])):
                errors.append({'reason': 'UNIT_SCHEMA', 'index': index})
                continue
            if row['id'] in units:
                errors.append({'reason': 'DUPLICATE_UNIT_ID', 'id': row['id']})
                continue
            units[row['id']] = row
            source = excerpts.get(row['excerpt_id'])
            if source is None:
                errors.append({'reason': 'UNKNOWN_EXCERPT', 'id': row['id']})
            elif not 0 <= row['start'] < row['end'] <= len(source['text']):
                errors.append({'reason': 'INVALID_SOURCE_RANGE', 'id': row['id']})
            if len(set(row['requires'])) != len(row['requires']):
                errors.append({'reason': 'DUPLICATE_DEPENDENCY', 'id': row['id']})
    for row in units.values():
        for parent in row['requires']:
            if parent not in units:
                errors.append({'reason': 'UNKNOWN_DEPENDENCY', 'id': row['id'],
                               'dependency': parent})
            elif units[parent]['excerpt_id'] != row['excerpt_id']:
                errors.append({'reason': 'CROSS_EXCERPT_DEPENDENCY', 'id': row['id'],
                               'dependency': parent})
    colors = {}

    def visit(uid):
        if colors.get(uid) == 1:
            errors.append({'reason': 'DEPENDENCY_CYCLE', 'id': uid})
            return
        if colors.get(uid) == 2:
            return
        colors[uid] = 1
        for parent in units[uid]['requires']:
            if parent in units:
                visit(parent)
        colors[uid] = 2

    for uid in units:
        visit(uid)
    return {'valid': not errors, 'errors': errors, 'excerpts': excerpts, 'units': units}


def _ordered(ids, graph):
    return sorted(ids, key=lambda uid: (
        graph['excerpts'][graph['units'][uid]['excerpt_id']]['source_order'],
        graph['units'][uid]['start'], graph['units'][uid]['end'], uid))


def _render(ids, graph):
    spans = []
    for uid in _ordered(ids, graph):
        row = graph['units'][uid]
        if (spans and spans[-1]['excerpt_id'] == row['excerpt_id']
                and row['start'] <= spans[-1]['end']):
            spans[-1]['end'] = max(spans[-1]['end'], row['end'])
            spans[-1]['unit_ids'].append(uid)
        else:
            spans.append({'excerpt_id': row['excerpt_id'], 'start': row['start'],
                          'end': row['end'], 'unit_ids': [uid]})
    for span in spans:
        source = graph['excerpts'][span['excerpt_id']]
        text = source['text']
        quote = text[span['start']:span['end']]
        span.update(text=quote, source_sha256=source['source_sha256'],
            quote_sha256=sha_text(quote),
            source_byte_start=len(text[:span['start']].encode('utf-8')),
            source_byte_end=len(text[:span['end']].encode('utf-8')))
    return '\n'.join(span['text'] for span in spans), spans


def _parents(uid, graph):
    found = set()

    def add(value):
        if value in found:
            return
        found.add(value)
        for parent in graph['units'][value]['requires']:
            add(parent)
    add(uid)
    return found


def _numeric_literals(spans):
    """Trace literal source strings, never infer numerical equivalence."""
    result = []
    pattern = r'(?<!\w)(?:[$€£]\s*)?[+-]?\d[\d,]*(?:\.\d+)?(?:\s*%)?'
    for span in spans:
        for match in re.finditer(pattern, span['text']):
            literal = match.group()
            result.append({'excerpt_id': span['excerpt_id'],
                'start': span['start'] + match.start(),
                'end': span['start'] + match.end(), 'literal': literal,
                'utf8_hex': literal.encode('utf-8').hex(), 'sha256': sha_text(literal)})
    return result


def pack_scope(case, observed_seed_ids, close_dependencies):
    """Admit complete annotated components atomically under one exact budget."""
    if type(close_dependencies) is not bool:
        raise ValueError('Explicit Boolean closure mode required')
    graph = validate_graph(case)
    base = {'case_id': case.get('id') if isinstance(case, dict) else None,
        'close_dependencies': close_dependencies, 'selected_unit_ids': [],
        'spans': [], 'context': '', 'context_sha256': sha_text(''),
        'context_utf8_bytes': 0, 'context_codepoints': 0,
        'dropped_seed_ids': [], 'omissions': [], 'errors': list(graph['errors']),
        'unknown': True, 'global_evidence_completeness': 'UNKNOWN',
        'entailment_or_insufficiency_decision': 'NOT_EVALUATED',
        'retrieval_miss_implies_insufficient_evidence': False,
        'scope': 'Supplied dependencies only; no automatic legal parsing or NLI.'}
    if not graph['valid']:
        return dict(base, status='INVALID_GRAPH_UNKNOWN')
    if (not isinstance(observed_seed_ids, list)
            or any(not isinstance(uid, str) for uid in observed_seed_ids)):
        return dict(base, status='INVALID_SEEDS_UNKNOWN',
                    errors=[{'reason': 'SEED_LIST_SCHEMA'}])
    base['observed_effective_seed_ids'] = list(observed_seed_ids)
    seed_errors = []
    for uid in observed_seed_ids:
        if uid not in graph['units']:
            seed_errors.append({'reason': 'UNKNOWN_SEED_ID', 'id': uid})
    if len(set(observed_seed_ids)) != len(observed_seed_ids):
        seed_errors.append({'reason': 'DUPLICATE_SEED_ID'})
    if seed_errors:
        return dict(base, status='INVALID_SEEDS_UNKNOWN', errors=seed_errors,
                    dropped_seed_ids=list(observed_seed_ids))
    selected = set()
    seen = set()
    for uid in observed_seed_ids:
        if uid in seen or uid not in graph['units']:
            reason = 'DUPLICATE_SEED_ID' if uid in seen else 'UNKNOWN_SEED_ID'
            base['dropped_seed_ids'].append(uid)
            base['omissions'].append({'seed_id': uid, 'reason': reason})
            base['errors'].append({'reason': reason, 'id': uid})
            continue
        seen.add(uid)
        component = _parents(uid, graph) if close_dependencies else {uid}
        proposed = selected | component
        context, _ = _render(proposed, graph)
        used = {'max_utf8_bytes': len(context.encode('utf-8')), 'max_nodes': len(proposed)}
        if any(used[key] > case['budget'][key] for key in used):
            base['dropped_seed_ids'].append(uid)
            base['omissions'].append({'seed_id': uid, 'reason': 'COMPONENT_OVER_BUDGET',
                'required_unit_ids': _ordered(component, graph), 'proposed_usage': used})
            continue
        selected = proposed
    context, spans = _render(selected, graph)
    missing = []
    for uid in observed_seed_ids:
        if uid in graph['units']:
            absent = _parents(uid, graph) - selected
            if absent:
                missing.append({'seed_id': uid, 'missing_unit_ids': _ordered(absent, graph)})
    complete = bool(observed_seed_ids) and not base['omissions'] and not missing and not base['errors']
    return dict(base, status='COMPLETE_FOR_RETRIEVED_SEEDS' if complete else 'INCOMPLETE_UNKNOWN',
        unknown=not complete, selected_unit_ids=_ordered(selected, graph), context=context,
        spans=spans, context_sha256=sha_text(context), context_utf8_bytes=len(context.encode('utf-8')),
        context_codepoints=len(context), selected_nodes=len(selected), budget=dict(case['budget']),
        missing_dependencies=missing, numeric_source_literals=_numeric_literals(spans))
