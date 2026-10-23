"""Independent source-sentence/group replay; no candidate or parser imports.

The postrun tokenizer caller supplies the two pinned tokenizer objects. Pure
source checks and tests use this module without importing any model/runtime.
"""
from common import *

POLICY = 'source-sentence-qualifier-groups-ranked-before-neighbors-v1'
PARAGRAPH = re.compile(r'(?:\r?\n)[ \t]*(?:\r?\n)+')
SENTENCE = re.compile(r'[.!?;][\"\'\)\]]*(?:\s+|$)')
BULLET = re.compile(r'^\s*(?:(?:\([a-zA-Z0-9]+\)|[a-zA-Z0-9]+[.)])\s+)?')
QUALIFIER = re.compile(
    r'^(?:provided\b|however\b|except\b|unless\b|notwithstanding\b|subject\s+to\b|'
    r'in\s+(?:such|that)\s+(?:case|event)\b|in\s+(?:the\s+)?event\b|'
    r'such\s+(?:disclosure|information|copies|copy)\b|any\s+such\b|'
    r'only\b|to\s+the\s+extent\b|upon\b|at\s+(?:the\s+|a\s+)?request\b|'
    r'and\s+(?:only|provided)\b|but\b)', re.IGNORECASE)
DEFINITION = re.compile(r'(?:\bhereinafter\b|\breferred\s+to\s+as\b|\bdefined\s+as\b|["“][^"”\r\n]{1,80}["”]\s*(?:shall\s+)?(?:means?|includes?)\b)', re.IGNORECASE)
NAMED = re.compile(r'''\([^()\r\n]{0,96}["“‘']\s*(?:(?:confidential|proprietary|non[\s\-\u2010-\u2015]*public)[\s\-\u2010-\u2015]+information|data[\s\-\u2010-\u2015]+recipient|receiving[\s\-\u2010-\u2015]+party|disclosing[\s\-\u2010-\u2015]+party|vendor|recipient)\s*["”’'][^()\r\n]{0,32}\)''', re.IGNORECASE)
BETWEEN = re.compile(r'\bbetween\b', re.IGNORECASE)
PARTY = re.compile(r'\b(?:agreement|parties|party|recipient|disclosing|receiving)\b', re.IGNORECASE)


def exact(left, right, message):
    demand(canonical(left) == canonical(right), message)


def atoms(state):
    demand(type(state) is str and bool(state), 'nonempty exact source required')
    paragraph_ends = [m.end() for m in PARAGRAPH.finditer(state)]
    if not paragraph_ends or paragraph_ends[-1] != len(state): paragraph_ends.append(len(state))
    rows, begin, group = [], 0, -1
    for paragraph, end in enumerate(paragraph_ends):
        stops = [begin + m.end() for m in SENTENCE.finditer(state[begin:end])]
        if not stops or stops[-1] != end: stops.append(end)
        cursor = begin
        for stop in stops:
            if stop <= cursor: continue
            attached = bool(rows and rows[-1]['paragraph_id'] == paragraph
                            and QUALIFIER.search(BULLET.sub('', state[cursor:stop], count=1)))
            if not attached: group += 1
            rows.append({'sentence_id': len(rows), 'start': cursor, 'end': stop,
                         'paragraph_id': paragraph, 'group_id': group,
                         'qualifier_attached': attached})
            cursor = stop
        begin = end
    return rows


def token_count(tokenizer, text, special=False):
    return len(tokenizer.encode(text, add_special_tokens=special).ids)


def partition(state, nli, bge):
    """Reproduce every bounded source unit from independent original tokens."""
    units = []
    for atom in atoms(state):
        begin, end = atom['start'], atom['end']
        def fits(a, b, cap):
            return token_count(nli, state[a:b]) <= cap and token_count(bge, state[a:b], True) <= 256
        if fits(begin, end, 160):
            parts = [{'start': begin, 'end': end, 'token_fallback': False}]
        else:
            points = sorted({begin + b for a, b in nli.encode(state[begin:end], add_special_tokens=False).offsets if b > 0} | {end})
            parts, cursor = [], begin
            while cursor < end:
                accepted = None
                for point in points:
                    if point <= cursor: continue
                    if not fits(cursor, point, 128): break
                    accepted = point
                demand(accepted is not None, 'indivisible original token exceeds source-unit budget')
                parts.append({'start': cursor, 'end': accepted, 'token_fallback': True,
                              'fallback_origin': [begin, end],
                              'fallback_boundary': 'Exact NLI tokenizer offset; full atom remains partitioned'})
                cursor = accepted
        for part in parts:
            part.update(id=len(units), paragraph_id=atom['paragraph_id'], sentence_id=atom['sentence_id'],
                        sentence_span=[begin, end], group_id=atom['group_id'],
                        qualifier_attached=atom['qualifier_attached'],
                        nli_tokens=token_count(nli, state[part['start']:part['end']]),
                        bge_tokens=token_count(bge, state[part['start']:part['end']], True))
            units.append(part)
    demand(1 <= len(units) <= 192, 'complete source partition exceeds fixed192 units')
    return units


def catalog(state, units):
    source_atoms = {a['sentence_id']: a for a in atoms(state)}
    result, cursor = [], 0
    for i, unit in enumerate(units):
        demand(type(unit) is dict and type(unit.get('sentence_id')) is int,
               'literal source sentence ID required')
        a = source_atoms.get(unit['sentence_id'])
        demand(a is not None, 'unknown source sentence')
        for k in ('id', 'start', 'end', 'paragraph_id', 'group_id', 'nli_tokens', 'bge_tokens'):
            demand(type(unit.get(k)) is int, 'literal source unit integer required: ' + k)
        demand(type(unit.get('qualifier_attached')) is bool and type(unit.get('token_fallback')) is bool,
               'literal source qualifier/fallback flags required')
        demand(unit['id'] == i and unit['start'] == cursor < unit['end'] <= a['end']
               and unit['start'] >= a['start'], 'complete contiguous original source units required')
        exact(unit['sentence_span'], [a['start'], a['end']], 'exact whole sentence span required')
        demand(all(unit[k] == a[k] for k in ('paragraph_id', 'group_id', 'qualifier_attached')),
               'source qualifier/group metadata changed')
        if not result or result[-1]['group_id'] != a['group_id']:
            demand(a['group_id'] == len(result), 'dense source-order groups required')
            result.append({'group_id': a['group_id'], 'start': unit['start'], 'end': unit['end'],
                           'paragraph_id': a['paragraph_id'], 'unit_ids': [], 'sentence_ids': [],
                           'qualifier_sentence_ids': [], 'token_fallback': False})
        g = result[-1]; g['end'] = unit['end']; g['unit_ids'].append(i)
        if a['sentence_id'] not in g['sentence_ids']: g['sentence_ids'].append(a['sentence_id'])
        if a['qualifier_attached'] and a['sentence_id'] not in g['qualifier_sentence_ids']:
            g['qualifier_sentence_ids'].append(a['sentence_id'])
        g['token_fallback'] |= unit['token_fallback']; cursor = unit['end']
    demand(bool(units) and cursor == len(state), 'complete source tail required')
    return result


def joined(state, units, selected):
    ids = sorted(selected)
    demand(len(ids) == len(set(ids)) and all(type(i) is int and 0 <= i < len(units) for i in ids),
           'unique literal selected source IDs required')
    spans = []
    for i in ids:
        start, end = units[i]['start'], units[i]['end']
        if spans and spans[-1][1] == start: spans[-1][1] = end
        else: spans.append([start, end])
    return '\n\n'.join(state[a:b] for a, b in spans), spans


def priority(state, units, nli):
    selected, chosen_groups, attempts = [], [], []
    for group in catalog(state, units):
        start, end = group['start'], group['end']; text = state[start:end]; triggers = []
        if DEFINITION.search(text): triggers.append('explicit-definition-marker')
        if NAMED.search(text): triggers.append('explicit-quoted-named-term-parenthetical')
        first = state[start:min(end, 2048)]
        if start < 2048 and BETWEEN.search(first) and PARTY.search(first): triggers.append('initial-party-declaration')
        if not triggers: continue
        candidate, _ = joined(state, units, selected + group['unit_ids']); count = token_count(nli, candidate)
        accept = not group['token_fallback'] and count <= 160
        attempts.append({'group_id': group['group_id'], 'unit_ids': group['unit_ids'],
                         'span': [start, end], 'source_sha256': digest(text.encode()), 'triggers': triggers,
                         'candidate_priority_tokens': count, 'accepted': accept,
                         'reason': 'admitted-whole-source-group' if accept else 'fallback-or-whole-group-exceeds160'})
        if accept: selected.extend(group['unit_ids']); chosen_groups.append(group['group_id'])
    text, spans = joined(state, units, selected)
    return {'policy': POLICY + ':claim-independent-whole-group-definition-priority',
            'selected_unit_ids': selected, 'selected_group_ids': chosen_groups, 'selected_source_spans': spans,
            'priority_tokens': token_count(nli, text), 'priority_token_cap': 160,
            'priority_text_sha256': digest(text.encode()), 'candidate_attempts': attempts,
            'whole_groups_only': True, 'token_fallback_admitted': False,
            'claim_dependent': False, 'literal_first_text_guaranteed': False}


def packed(state, units, ranking, hypothesis, nli):
    """Independently replay every admission from actual unmodified unit order."""
    demand(type(ranking) is list and len(ranking) == min(40, len(units))
           and len(set(ranking)) == len(ranking)
           and all(type(i) is int and 0 <= i < len(units) for i in ranking),
           'exact observed top40 source unit ranking required')
    demand(type(hypothesis) is str and bool(hypothesis.strip()), 'whole hypothesis required')
    demand(len(nli.encode('', hypothesis).ids) <= 512, 'whole hypothesis cannot fit frozen pair cap')
    groups = catalog(state, units); prelude = priority(state, units, nli)
    selected, selected_groups = list(prelude['selected_unit_ids']), list(prelude['selected_group_ids'])
    text, _ = joined(state, units, selected)
    demand(len(nli.encode(text, hypothesis).ids) <= 512, 'whole shared priority and claim exceed pair cap')
    order, anchor = [], {}
    for unit in ranking:
        gid = units[unit]['group_id']
        if gid not in anchor: order.append(gid); anchor[gid] = unit
    attempts, admitted = [], []
    def consider(gid, role, ranked_anchor):
        if gid in selected_groups: return True
        group = groups[gid]; candidate, _ = joined(state, units, selected + group['unit_ids'])
        count = len(nli.encode(candidate, hypothesis).ids); accept = count <= 512
        attempts.append({'group_id': gid, 'unit_ids': group['unit_ids'], 'role': role, 'anchor': ranked_anchor,
                         'source_span': [group['start'], group['end']], 'candidate_pair_tokens': count,
                         'accepted': accept, 'all_group_units_admitted_together': accept})
        if accept: selected.extend(group['unit_ids']); selected_groups.append(gid)
        return accept
    for gid in order:
        if gid in selected_groups: continue
        if consider(gid, 'ranked-sentence-group', anchor[gid]): admitted.append(gid)
    inspected = set(order) | set(selected_groups)
    for gid in admitted:
        for neighbor in (gid - 1, gid + 1):
            if 0 <= neighbor < len(groups) and neighbor not in inspected and groups[neighbor]['paragraph_id'] == groups[gid]['paragraph_id']:
                inspected.add(neighbor)
                consider(neighbor, 'optional-neighbor-group-after-all-ranked', anchor[gid])
    demand(bool(selected), 'no complete source group fits frozen pair cap')
    premise, spans = joined(state, units, selected); count = len(nli.encode(premise, hypothesis).ids)
    demand(count <= 512, 'final complete pair exceeds frozen cap')
    chosen = set(selected); omitted = [u['id'] for u in units if u['id'] not in chosen]
    numbers = [{'span': [m.start(), m.end()], 'text': m.group(),
                'retained': any(a <= m.start() and m.end() <= b for a, b in spans)} for m in NUMBER.finditer(state)]
    covered = sum(b - a for a, b in spans)
    coverage = {'policy': POLICY, 'definition_priority': prelude, 'source_sentence_groups': groups,
        'qualifier_regex': QUALIFIER.pattern, 'bullet_regex': BULLET.pattern,
        'group_ranking_policy': 'First observed member unit in unchanged observed top40 ranking; no new scores or reordering',
        'group_ranking_ids': order, 'group_ranking_anchor_unit_ids': [anchor[g] for g in order],
        'selected_group_ids_admission_order': selected_groups, 'all_selected_groups_complete': True,
        'ranking_ids_considered': ranking, 'ranking_depth': len(ranking),
        'ranked_anchor_candidate_cap': min(40, len(units)), 'joint_pair_token_cap': 512,
        'additional_neighbor_unit_ids_inspected': sorted({i for a in attempts if a['role'].startswith('optional-neighbor') for i in a['unit_ids'] if i not in ranking}),
        'selected_chunk_ids_rank_order': selected, 'selected_chunk_ids_source_order': sorted(selected),
        'selected_source_spans': spans, 'omitted_chunk_ids': omitted,
        'omitted_source_spans': [[units[i]['start'], units[i]['end']] for i in omitted],
        'total_document_chunks': len(units), 'retained_source_characters': covered,
        'document_characters': len(state), 'document_character_coverage': covered / len(state),
        'joint_pair_tokens': count, 'selected_evidence_truncated': False, 'claim_truncated': False,
        'premise_sha256': digest(premise.encode()), 'hypothesis_sha256': digest(hypothesis.encode()),
        'packing_attempts': attempts, 'selected_token_fallback_unit_ids': [i for i in selected if units[i]['token_fallback']],
        'numeric_mentions': numbers, 'numeric_mentions_retained': sum(n['retained'] for n in numbers),
        'numeric_mentions_omitted': sum(not n['retained'] for n in numbers),
        'scope': 'Exact mechanical atom/group/qualifier/number retention only. Neither retention nor omission proves evidence sufficiency or a typed decision.'}
    return premise, coverage


def summary_row(document_id, question, arm):
    value = question['arms'][arm]; coverage = value['coverage']
    return {'document_id': document_id, 'question_id': question['id'], 'arm': arm,
            'premise_sha256': digest(value['premise'].encode()), 'coverage_sha256': digest(canonical(coverage)),
            'source_units_sha256': None, 'joint_pair_tokens': coverage['joint_pair_tokens'],
            'priority_attempts': len(coverage['definition_priority']['candidate_attempts']),
            'packing_attempts': len(coverage['packing_attempts']),
            'selected_group_ids': coverage['selected_group_ids_admission_order']}


def replay_documents(raw, protocol, nli, bge, native_check):
    partitions, arm_rows, native = [], [], []
    for doc in raw['documents']:
        state, units = doc['state'], doc['source_units']
        demand(doc['state_sha256'] == digest(state.encode()), 'exact document text identity required')
        expected = partition(state, nli, bge)
        exact(units, expected, 'source sentence/token-fallback partition differs from exact independent tokens')
        groups = catalog(state, units); prelude = priority(state, units, nli)
        exact(doc['shared_definition_priority'], prelude, 'document shared whole-group priority differs')
        chunks = [state[u['start']:u['end']] for u in units]
        exact(doc['embedding']['exact_document_texts'], chunks, 'altered or external embedding source')
        vectors, queries = doc['document_vectors'], doc['query_vectors']
        demand(len(vectors) == len(units), 'one actual vector per original bounded source unit required')
        native.append(native_check(doc['native_trace'], vectors, queries))
        partitions.append({'document_id': doc['id'], 'units': len(units), 'groups': len(groups),
                           'partition_sha256': digest(canonical(units)), 'group_catalog_sha256': digest(canonical(groups))})
        for qi, question in enumerate(doc['questions']):
            words = set(re.findall(r'\w+', question['hypothesis'].casefold()))
            scores = [len(words & set(re.findall(r'\w+', text.casefold()))) /
                      max(1, len(words | set(re.findall(r'\w+', text.casefold())))) for text in chunks]
            depth = min(40, len(units))
            rankings = {M.ARMS[0]: doc['native_trace']['raw_native_output']['queries'][qi]['ids'],
                        M.ARMS[1]: sorted(range(len(units)), key=lambda i: (-scores[i], i))[:depth],
                        M.ARMS[2]: list(range(depth))}
            exact(question['rankings'], rankings, 'source-only matched unit ranking differs')
            for arm in M.ARMS:
                premise, coverage = packed(state, units, rankings[arm], question['hypothesis'], nli)
                exact(question['arms'][arm]['coverage'], coverage, 'atomic ranked-before-neighbor packing receipt differs')
                demand(question['arms'][arm]['premise'] == premise, 'packed exact source text differs')
                row = summary_row(doc['id'], question, arm); row['source_units_sha256'] = partitions[-1]['partition_sha256']
                arm_rows.append(row)
    demand(len(partitions) == 8 and len(arm_rows) == 72, 'complete eight-document72arm context replay required')
    return {'checks_passed': True, 'policy': POLICY, 'documents': partitions, 'arms': arm_rows,
            'all_actual_native_traces_replayed': True, 'native_trace_reports': native,
            'model_native_forwards': 0, 'gold_labels_read': 0,
            'scope': 'Exact mechanical source/token/group/ranking/admission replay, not semantic evidence sufficiency or benchmark generalization.'}


def token_proof_replay(raw, proof):
    if raw['status'] != 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE':
        demand(proof is None, 'engineering-only rejection cannot have corpus context replay')
        return
    demand(type(proof) is dict and proof.get('checks_passed') is True and proof.get('policy') == POLICY
           and proof.get('all_actual_native_traces_replayed') is True
           and integer(proof['model_native_forwards']) == integer(proof['gold_labels_read']) == 0,
           'exact completed independent source/group replay required')
    documents, arms = [], []
    for doc in raw['documents']:
        groups = catalog(doc['state'], doc['source_units']); units_sha = digest(canonical(doc['source_units']))
        documents.append({'document_id': doc['id'], 'units': len(doc['source_units']), 'groups': len(groups),
                          'partition_sha256': units_sha, 'group_catalog_sha256': digest(canonical(groups))})
        for question in doc['questions']:
            for arm in M.ARMS:
                row = summary_row(doc['id'], question, arm); row['source_units_sha256'] = units_sha; arms.append(row)
    exact(proof['documents'], documents, 'context proof partition/group identities changed')
    exact(proof['arms'], arms, 'every actual context/admission summary must match the sealed source proof')
    demand(len(documents) == 8 and len(arms) == 72 and len(proof['native_trace_reports']) == 8,
           'complete independent source/group/native proof required')
