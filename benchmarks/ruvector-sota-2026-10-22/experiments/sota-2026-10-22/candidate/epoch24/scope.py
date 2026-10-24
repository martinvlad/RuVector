"""CC0-1.0: bounded raw-source structural parser and matched scope packing.

No supplied annotations are accepted. Structural unknown is never a legal label.
"""
from __future__ import annotations

import hashlib
import re

POLICY = 'epoch24-raw-structure-v1'
MAX_BYTES, MAX_UNITS, MAX_REFS = 65536, 512, 2048
NUM = r'\d+(?:\.\d+)*'
TOKEN = NUM + r'(?:\([a-z]\))?'
MARKER = re.compile(r'^(?P<indent>[ \t]*)(?:(?P<section>Section)[ \t]+)?'
    r'(?:(?P<number>\d+(?:\.\d+)*)(?P<delimiter>[.)]?)(?=[ \t]|$)|'
    r'(?P<letter>\([a-z]\))(?=[ \t]|$))', re.I)
SUSPECT = re.compile(r'^[ \t]*(?:\([A-Za-z]+\)|[A-Za-z]+[.)])(?=[ \t]|$)')
TRIGGER = re.compile(r'\b(subject\s+to|except\s+as\s+provided\s+in|'
    r'except\s+as\s+set\s+forth\s+in|provided\s+that\s+the\s+requirements\s+of|'
    r'on\s+condition\s+that\s+the\s+requirements\s+of)\b', re.I)
TARGET = re.compile(TOKEN + r'(?![\w(]|\.\d)')
RELATIVE = re.compile(r'\([a-z]\)')
PREFIX = re.compile(r'(Sections?|Clauses?)[ \t]+', re.I)
SEPARATOR = re.compile(r'[ \t]*(?:,[ \t]*(?:and[ \t]+)?|and[ \t]+)', re.I)


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def span(text, start, end):
    return {'start': start, 'end': end, 'text': text[start:end],
        'source_byte_start': len(text[:start].encode('utf-8')),
        'source_byte_end': len(text[:end].encode('utf-8'))}


def _trim_end(text, start, end):
    while end > start and text[end-1].isspace():
        end -= 1
    return end


def parse_raw_source(source_text):
    """One excerpt only. Offsets are Unicode codepoints; bytes are also recorded."""
    if not isinstance(source_text, str):
        raise ValueError('RAW_TEXT_REQUIRED')
    source_text.encode('utf-8')
    if len(source_text.encode('utf-8')) > MAX_BYTES:
        return {'units': [], 'references': [], 'unknowns': [
            {'reason': 'budget_exceeded', 'owner_id': None, 'span': span(source_text, 0, 0)}]}
    text = source_text
    boundaries, cursor = [], 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\r\n')
        match = MARKER.match(body)
        valid = False
        if match:
            num, letter = match.group('number'), match.group('letter')
            valid = bool((letter and re.fullmatch(r'\([a-z]\)', letter)) or
                (num and (match.group('section') or '.' in num or match.group('delimiter'))))
        suspect = SUSPECT.match(body)
        if valid:
            boundaries.append({'line_start': cursor, 'start': cursor+len(match.group('indent')),
                'marker_end': cursor+match.end(), 'after': cursor+match.end(),
                'number': num, 'letter': letter})
        elif match or suspect:
            end = cursor + (match.end() if match else suspect.end())
            boundaries.append({'line_start': cursor, 'start': cursor+len(body)-len(body.lstrip(' \t')),
                'marker_end': end, 'unsupported': True})
        cursor += len(line)
    units, unknowns, occurrences = [], [], {}
    active = None
    for index, item in enumerate(boundaries):
        segment_end = boundaries[index+1]['line_start'] if index+1 < len(boundaries) else len(text)
        end = _trim_end(text, item['start'], segment_end)
        if item.get('unsupported'):
            unknowns.append({'reason': 'unsupported_marker_syntax', 'owner_id': None,
                'span': span(text, item['start'], max(item['marker_end'], end))})
            active = None
            continue
        num, letter = item.get('number'), item.get('letter')
        if letter and active is None:
            unknowns.append({'reason': 'ambiguous_scope', 'detail': 'letter_without_numeric_parent',
                'owner_id': None, 'span': span(text, item['start'], end)})
            continue
        label = num if num else active['clause_id'] + letter
        occurrences[label] = occurrences.get(label, 0)+1
        local_id = label + (('#'+str(occurrences[label])) if occurrences[label] > 1 else '')
        start_content = item['after']
        while start_content < end and text[start_content] in ' \t':
            start_content += 1
        start_content = min(start_content, end)
        parent = None
        if num and '.' in num:
            parent_label = num.rsplit('.', 1)[0]
            parents = [u for u in units if u['clause_id'] == parent_label]
            if len(parents) == 1:
                parent = parents[0]
            else:
                unknowns.append({'reason': 'ambiguous_scope', 'detail': 'missing_or_duplicate_numeric_ancestor',
                    'owner_id': local_id, 'span': span(text, item['start'], item['marker_end'])})
        elif letter:
            parent = active
        heading_spans = []
        if parent:
            heading_spans.extend(parent['heading_spans'])
            content = text[parent['content_start']:parent['content_end']]
            if content.rstrip().endswith(':'):
                last_start = max(content.rfind('\n'), content.rfind('\r'))+1
                a = parent['content_start']+last_start
                while a < parent['content_end'] and text[a] in ' \t':
                    a += 1
                heading_spans.append(span(text, a, parent['content_end']))
        row = {'id': local_id, 'clause_id': label, 'start': item['start'], 'end': end,
            'marker_start': item['start'], 'marker_end': item['marker_end'],
            'content_start': start_content, 'content_end': end,
            'parent_id': parent['id'] if parent else None,
            'requires': [parent['id']] if parent else [], 'heading_spans': heading_spans,
            'numeric_scope': num if num else active['clause_id']}
        row.update(marker_span=span(text, item['start'], item['marker_end']),
            content_span=span(text, start_content, end), whole_span=span(text, item['start'], end))
        units.append(row)
        if num:
            active = row
    if len(units) > MAX_UNITS:
        return {'units': [], 'references': [], 'unknowns': [
            {'reason': 'budget_exceeded', 'owner_id': None, 'span': span(text, 0, 0)}]}
    # Preamble remains source, never an invented graph node. A colon has no guessed scope.
    preamble_end = boundaries[0]['line_start'] if boundaries else len(text)
    for match in re.finditer(r'(?m)^[^\r\n]*:[ \t]*$', text[:preamble_end]):
        unknowns.append({'reason': 'ambiguous_scope', 'detail': 'unnumbered_heading',
            'owner_id': None, 'span': span(text, match.start(), match.end())})
    by_label = {}
    for unit in units:
        by_label.setdefault(unit['clause_id'], []).append(unit)
    for label, values in by_label.items():
        if len(values) > 1:
            for unit in values:
                unknowns.append({'reason': 'ambiguous_scope', 'detail': 'duplicate_clause_id',
                    'owner_id': unit['id'], 'span': span(text, unit['marker_start'], unit['marker_end'])})
    if not units:
        unknowns.append({'reason': 'no_supported_units', 'owner_id': None, 'span': span(text, 0, len(text))})
    refs = []
    for unit in units:
        content = text[unit['content_start']:unit['content_end']]
        for trigger in TRIGGER.finditer(content):
            trigger_start = unit['content_start']+trigger.start()
            trigger_end = unit['content_start']+trigger.end()
            at = trigger_end
            while at < unit['end'] and text[at] in ' \t': at += 1
            pref = PREFIX.match(text, at)
            absolute = pref is not None
            if pref: at = pref.end()
            target = TARGET.match(text, at) if absolute else RELATIVE.match(text, at)
            targets = []
            if target:
                targets.append(target)
                at = target.end()
                while True:
                    sep = SEPARATOR.match(text, at)
                    if not sep: break
                    following = TARGET.match(text, sep.end()) if absolute else RELATIVE.match(text, sep.end())
                    if not following: break
                    targets.append(following); at = following.end()
            tail = text[at:unit['end']]
            bad_tail = bool(re.match(r'[ \t]*(?:[-–—]|through\b|to[ \t]+\d|or[ \t]+(?:\d|\())', tail, re.I)
                or re.match(r'[ \t]*(?:,[ \t]*|and[ \t]+)\(', tail, re.I))
            if not targets or bad_tail:
                stop = at if targets else min(unit['end'], trigger_end+80)
                unknowns.append({'reason': 'unsupported_reference_syntax', 'owner_id': unit['id'],
                    'span': span(text, trigger_start, max(trigger_end, stop))})
                continue
            kind = ('subject_to' if trigger.group().casefold().startswith('subject') else
                'exception_reference' if trigger.group().casefold().startswith('except') else 'condition_reference')
            for target in targets:
                literal = target.group()
                label = literal if absolute else unit['numeric_scope']+literal
                candidates = by_label.get(label, [])
                status = ('resolved' if len(candidates) == 1 else
                    'ambiguous_reference' if len(candidates) > 1 else 'unresolved_reference')
                ref = {'owner_id': unit['id'], 'trigger_kind': kind,
                    'trigger_span': span(text, trigger_start, trigger_end),
                    'target_span': span(text, target.start(), target.end()),
                    'target_literal': literal, 'target_clause_id': label,
                    'resolved_target_id': candidates[0]['id'] if status == 'resolved' else None,
                    'inherited': False, 'status': status}
                refs.append(ref)
                if status == 'resolved':
                    if candidates[0]['id'] not in unit['requires']: unit['requires'].append(candidates[0]['id'])
                else:
                    unknowns.append({'reason': status, 'owner_id': unit['id'],
                        'span': ref['target_span'], 'candidate_ids': [u['id'] for u in candidates]})
    if len(refs) > MAX_REFS:
        return {'units': [], 'references': [], 'unknowns': [
            {'reason': 'budget_exceeded', 'owner_id': None, 'span': span(text, 0, 0)}]}
    order = {u['id']: i for i, u in enumerate(units)}
    for unit in units: unit['requires'].sort(key=lambda uid: order[uid])
    return {'units': units, 'references': refs, 'unknowns': sorted(unknowns,
        key=lambda r: (r['span']['start'], r['span']['end'], r['reason'], r.get('owner_id') or ''))}


def parse_case(case):
    """Accept input-only engineering sources, never units/graphs/annotations."""
    base = {'valid': False, 'errors': [], 'units': {}, 'references': [], 'unknowns': [],
        'excerpts': {}, 'cycles': [], 'parser_policy_version': POLICY}
    if not isinstance(case, dict) or set(case) != {'id', 'query', 'excerpts', 'budget', 'seed_limit'}:
        base['errors'].append({'reason': 'RAW_CASE_SCHEMA'}); return base
    if not isinstance(case['id'], str) or not case['id'] or not isinstance(case['query'], str) or not case['query'].strip():
        base['errors'].append({'reason': 'CASE_ID_OR_QUERY'}); return base
    if (not isinstance(case['budget'], dict) or set(case['budget']) != {'max_utf8_bytes', 'max_nodes'}
            or any(type(v) is not int or v < 0 for v in case['budget'].values())
            or type(case['seed_limit']) is not int or not 0 <= case['seed_limit'] <= 256):
        base['errors'].append({'reason': 'BUDGET_OR_SEED_SCHEMA'}); return base
    if not isinstance(case['excerpts'], list) or not 1 <= len(case['excerpts']) <= 64:
        base['errors'].append({'reason': 'EXCERPT_LIST'}); return base
    for index, excerpt in enumerate(case['excerpts']):
        if (not isinstance(excerpt, dict) or set(excerpt) != {'id', 'text'} or
                not isinstance(excerpt['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]+', excerpt['id']) or
                not isinstance(excerpt['text'], str) or excerpt['id'] in base['excerpts']):
            base['errors'].append({'reason': 'EXCERPT_SCHEMA_OR_ID'}); continue
        eid, text = excerpt['id'], excerpt['text']
        try: parsed = parse_raw_source(text)
        except UnicodeEncodeError:
            base['errors'].append({'reason': 'INVALID_SOURCE_UTF8', 'excerpt_id': eid}); continue
        base['excerpts'][eid] = dict(excerpt, source_order=index, source_sha256=sha_text(text))
        qualify = lambda uid: eid+'::'+uid if uid is not None else None
        for row in parsed['units']:
            row['id'] = qualify(row['id']); row['parent_id'] = qualify(row['parent_id'])
            row['requires'] = [qualify(x) for x in row['requires']]
            row['excerpt_id'] = eid
            base['units'][row['id']] = row
        for row in parsed['references']:
            row['owner_id'] = qualify(row['owner_id']); row['resolved_target_id'] = qualify(row['resolved_target_id'])
            row['excerpt_id'] = eid; base['references'].append(row)
        for row in parsed['unknowns']:
            row['owner_id'] = qualify(row['owner_id']); row['excerpt_id'] = eid
            if 'candidate_ids' in row: row['candidate_ids'] = [qualify(x) for x in row['candidate_ids']]
            base['unknowns'].append(row)
    if len(base['units']) > MAX_UNITS or len(base['references']) > MAX_REFS:
        base['errors'].append({'reason': 'GLOBAL_UNIT_OR_REFERENCE_BUDGET'}); return base
    # Tarjan SCCs: retain cycles, diagnose them, and traverse them safely later.
    counter, indices, low, stack, onstack = 0, {}, {}, [], set()
    def visit(uid):
        nonlocal counter
        indices[uid] = low[uid] = counter; counter += 1; stack.append(uid); onstack.add(uid)
        for target in base['units'][uid]['requires']:
            if target not in indices: visit(target); low[uid] = min(low[uid], low[target])
            elif target in onstack: low[uid] = min(low[uid], indices[target])
        if low[uid] == indices[uid]:
            component = []
            while True:
                value = stack.pop(); onstack.remove(value); component.append(value)
                if value == uid: break
            if len(component) > 1 or uid in base['units'][uid]['requires']:
                base['cycles'].append(sorted(component))
    for uid in base['units']:
        if uid not in indices: visit(uid)
    base['cycles'].sort()
    base['valid'] = not base['errors']
    return base


def _ordered(ids, graph):
    return sorted(ids, key=lambda uid: (graph['excerpts'][graph['units'][uid]['excerpt_id']]['source_order'],
        graph['units'][uid]['start'], graph['units'][uid]['end'], uid))


def _render(ids, graph):
    spans = []
    for uid in _ordered(ids, graph):
        unit = graph['units'][uid]
        if spans and spans[-1]['excerpt_id'] == unit['excerpt_id'] and unit['start'] <= spans[-1]['end']:
            spans[-1]['end'] = max(spans[-1]['end'], unit['end']); spans[-1]['unit_ids'].append(uid)
        else: spans.append({'excerpt_id': unit['excerpt_id'], 'start': unit['start'], 'end': unit['end'], 'unit_ids': [uid]})
    for value in spans:
        source = graph['excerpts'][value['excerpt_id']]
        value.update(span(source['text'], value['start'], value['end']))
        value.update(source_sha256=source['source_sha256'], quote_sha256=sha_text(value['text']))
    return '\n'.join(s['text'] for s in spans), spans


def _parents(uid, graph):
    found, todo = set(), [uid]
    while todo:
        value = todo.pop()
        if value in found: continue
        found.add(value); todo.extend(reversed(graph['units'][value]['requires']))
    return found


def pack_scope(case, graph, observed_seed_ids, close_dependencies):
    """Internal parser result only; worker obtains graph directly from parse_case."""
    if type(close_dependencies) is not bool: raise ValueError('EXPLICIT_CLOSURE_MODE_REQUIRED')
    result = {'case_id': case.get('id') if isinstance(case, dict) else None, 'close_dependencies': close_dependencies,
        'selected_unit_ids': [], 'spans': [], 'context': '', 'context_sha256': sha_text(''),
        'context_utf8_bytes': 0, 'context_codepoints': 0, 'dropped_seed_ids': [], 'omissions': [],
        'errors': list(graph['errors']), 'unknown': True, 'global_evidence_completeness': 'UNKNOWN',
        'entailment_or_insufficiency_decision': 'NOT_EVALUATED',
        'retrieval_miss_implies_insufficient_evidence': False,
        'scope': 'Automatically parsed explicit structural dependencies only; no legal or NLI conclusion.'}
    if not graph['valid']: return dict(result, status='INVALID_SOURCE_UNKNOWN')
    if not isinstance(observed_seed_ids, list) or any(not isinstance(s, str) for s in observed_seed_ids):
        return dict(result, status='INVALID_SEEDS_UNKNOWN', errors=[{'reason': 'SEED_LIST_SCHEMA'}])
    result['observed_effective_seed_ids'] = list(observed_seed_ids)
    if len(set(observed_seed_ids)) != len(observed_seed_ids) or any(s not in graph['units'] for s in observed_seed_ids):
        return dict(result, status='INVALID_SEEDS_UNKNOWN', errors=[{'reason': 'UNKNOWN_OR_DUPLICATE_SEED'}])
    selected = set()
    for uid in observed_seed_ids:
        component = _parents(uid, graph) if close_dependencies else {uid}
        proposed = selected | component
        context, _ = _render(proposed, graph)
        usage = {'max_utf8_bytes': len(context.encode('utf-8')), 'max_nodes': len(proposed)}
        if any(usage[k] > case['budget'][k] for k in usage):
            result['dropped_seed_ids'].append(uid)
            result['omissions'].append({'seed_id': uid, 'reason': 'COMPONENT_OVER_BUDGET',
                'required_unit_ids': _ordered(component, graph), 'proposed_usage': usage})
        else: selected = proposed
    missing = [{'seed_id': uid, 'missing_unit_ids': _ordered(_parents(uid, graph)-selected, graph)}
        for uid in observed_seed_ids if _parents(uid, graph)-selected]
    unresolved = [u for u in graph['unknowns'] if u['owner_id'] is None or u['owner_id'] in selected]
    context, spans = _render(selected, graph)
    complete = bool(observed_seed_ids) and not result['omissions'] and not missing and not unresolved
    return dict(result, status='COMPLETE_FOR_RETRIEVED_SEEDS' if complete else 'INCOMPLETE_STRUCTURAL_UNKNOWN',
        unknown=not complete, selected_unit_ids=_ordered(selected, graph), spans=spans, context=context,
        context_sha256=sha_text(context), context_utf8_bytes=len(context.encode('utf-8')),
        context_codepoints=len(context), selected_nodes=len(selected), budget=dict(case['budget']),
        missing_dependencies=missing, structural_unknowns=unresolved)
