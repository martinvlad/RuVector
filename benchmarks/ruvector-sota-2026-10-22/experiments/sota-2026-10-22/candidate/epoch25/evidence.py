"""Finite source-only evidence qualification; no semantic/legal inference or models.

Each supplied source is one indivisible unit. Extraction records lexical source
literals and exact offsets, without normalizing amounts or resolving references.
"""
from __future__ import annotations
import hashlib
import math
import re

MAX_CASES = 6
MAX_SOURCES = 16
MAX_SOURCE_CHARS = 8192
MAX_HYPOTHESIS_CHARS = 2048
TOP_K = 1
MODEL_TOTAL_TOKENS = 512
ARMS = ('actual_native', 'lexical', 'positional')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z')
_LITERAL_PATTERNS = (
    ('number', re.compile(r'(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])')),
    ('currency', re.compile(r'[$€£¥]|\b(?:USD|EUR|GBP|JPY|CAD|AUD|dollars?|euros?|pounds?|yen)\b', re.I)),
    ('scale', re.compile(r'\b(?:thousand|million|billion|trillion)\b', re.I)),
    ('percent', re.compile(r'%|\b(?:percent|per cent)\b', re.I)),
    ('period', re.compile(r'\b(?:FY\s*\d{4}|Q[1-4](?:\s+\d{4})?|(?:fiscal|calendar)\s+year\s+\d{4})\b', re.I)),
)
# These are explicit source assertions of unresolved structure. Missing evidence,
# missing numbers and missing dates do not independently trigger any guard.
_AMBIGUITY_PATTERNS = (
    ('explicit_unit_ambiguity', re.compile(r'\b(?:units?|currency)\s+(?:is\s+|are\s+)?(?:unspecified|unclear|unknown|ambiguous|not stated)\b|\bwithout\s+(?:a\s+)?stated\s+(?:unit|currency)\b', re.I)),
    ('explicit_period_ambiguity', re.compile(r'\b(?:reporting\s+period|period|year)\s+(?:is\s+|are\s+)?(?:unspecified|unclear|unknown|ambiguous|not stated)\b|\bwithout\s+(?:a\s+)?stated\s+(?:period|year)\b', re.I)),
)


def _text(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\0' in value:
        raise ValueError('Invalid finite input string: ' + name)
    value.encode('utf-8', errors='strict')
    return value


def _id(value, name):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Invalid finite input ID: ' + name)
    return value


def validate_case(case):
    if not isinstance(case, dict) or set(case) != {'id', 'hypothesis', 'query', 'sources'}:
        raise ValueError('Case permits only raw id/hypothesis/query/sources')
    _id(case['id'], 'case.id')
    _text(case['hypothesis'], 'hypothesis', MAX_HYPOTHESIS_CHARS)
    if case['query'] != case['hypothesis']:
        raise ValueError('Query must be verbatim frozen hypothesis')
    if not isinstance(case['sources'], list) or not 1 <= len(case['sources']) <= MAX_SOURCES:
        raise ValueError('Finite nonempty supplied source list required')
    seen = set()
    for source in case['sources']:
        if not isinstance(source, dict) or set(source) != {'source_id', 'text'}:
            raise ValueError('Source permits only raw source_id/text')
        source_id = _id(source['source_id'], 'source_id')
        if source_id in seen:
            raise ValueError('Duplicate source_id within case')
        seen.add(source_id)
        _text(source['text'], 'source.text', MAX_SOURCE_CHARS)
    return case


def validate_bundle(bundle, contract_sha256):
    expected = {'schema_version', 'epoch', 'contract_sha256', 'license', 'authorship', 'scope', 'cases'}
    if not isinstance(bundle, dict) or set(bundle) != expected:
        raise ValueError('Wrong authored input wrapper fields')
    if (type(bundle['schema_version']) is not int or bundle['schema_version'] != 1
            or type(bundle['epoch']) is not int or bundle['epoch'] != 25
            or bundle['contract_sha256'] != contract_sha256 or bundle['license'] != 'CC0-1.0'):
        raise ValueError('Wrong authored input wrapper identity/license')
    for name in ('authorship', 'scope'):
        _text(bundle[name], name, 2048)
    if not isinstance(bundle['cases'], list) or len(bundle['cases']) != MAX_CASES:
        raise ValueError('Exactly six authored cases required')
    seen = set()
    for case in bundle['cases']:
        validate_case(case)
        if case['id'] in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case['id'])
    return bundle


def span(text, start, end):
    if not 0 <= start <= end <= len(text):
        raise ValueError('Invalid source character offset')
    literal = text[start:end]
    byte_start = len(text[:start].encode('utf-8'))
    byte_end = len(text[:end].encode('utf-8'))
    if text.encode('utf-8')[byte_start:byte_end].decode('utf-8') != literal:
        raise ValueError('UTF8 source span round-trip failure')
    return {'text': literal, 'start': start, 'end': end,
            'source_byte_start': byte_start, 'source_byte_end': byte_end}


def source_unit(source):
    text = source['text']
    literals = []
    for kind, pattern in _LITERAL_PATTERNS:
        for match in pattern.finditer(text):
            record = dict(kind=kind, **span(text, match.start(), match.end()))
            if kind == 'number' and re.fullmatch(r'\d{4}', match.group()) and 1000 <= int(match.group()) <= 2999:
                record['lexical_year_candidate'] = True
            literals.append(record)
    literals.sort(key=lambda row: (row['start'], row['end'], row['kind']))
    unknowns = []
    for reason, pattern in _AMBIGUITY_PATTERNS:
        for match in pattern.finditer(text):
            unknowns.append(dict(reason=reason, **span(text, match.start(), match.end())))
    return {'source_id': source['source_id'], 'text': text,
            'source_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'whole_span': span(text, 0, len(text)), 'numeric_literals': literals,
            'structural_unknowns': sorted(unknowns, key=lambda row: (row['start'], row['end'], row['reason']))}


def qualify(source):
    unit = source_unit(source)
    return {'status': 'STRUCTURAL_UNKNOWN' if unit['structural_unknowns'] else 'SOURCE_PROVENANCE_VALID',
            'structural_unknown': bool(unit['structural_unknowns']),
            'decision': None, 'unknowns': unit['structural_unknowns'],
            'scope': 'Source-only finite literal/span checks; no legal or semantic sufficiency judgment.'}


def lexical_order(texts, query):
    query_words = set(re.findall(r'\w+', query.casefold()))
    words = [set(re.findall(r'\w+', text.casefold())) for text in texts]
    scores = [len(query_words & current) / max(1, len(query_words | current)) for current in words]
    if not all(math.isfinite(value) for value in scores):
        raise ValueError('Nonfinite lexical overlap score')
    return sorted(range(len(texts)), key=lambda i: (-scores[i], i)), scores


def pack(sources, ranking):
    if (not isinstance(ranking, list) or not ranking or len(set(ranking)) != len(ranking)
            or any(type(i) is not int or not 0 <= i < len(sources) for i in ranking)):
        raise ValueError('Invalid observed ranking; never synthesize native order')
    index = ranking[0]
    unit = source_unit(sources[index])
    return {'top_k': TOP_K, 'selected_indices': [index], 'selected_source_ids': [unit['source_id']],
            'context': unit['text'], 'source_units': [unit], 'guard': qualify(sources[index]),
            'policy': 'First ranked entire supplied source; no splitting, closure expansion or truncation.'}


def owned_source_guards():
    """Author-owned source-only smoke probes, no hypotheses and no NLI forwards."""
    examples = [
        ('utf8_literals', 'In fiscal year 2024, café revenue was €12.5 million, up 8%.'),
        ('explicit_unit', 'For 2024 revenue was 42 million; currency unspecified.'),
        ('explicit_period', 'Revenue was USD 42 million; reporting period is unspecified.'),
        ('no_global_absence', 'The office uses blue folders.'),
    ]
    records = []
    for source_id, text in examples:
        source = {'source_id': source_id, 'text': text}
        unit, guard = source_unit(source), qualify(source)
        records.append({'source': source, 'unit': unit, 'guard': guard})
    expected = [False, True, True, False]
    if [row['guard']['structural_unknown'] for row in records] != expected:
        raise ValueError('Author-owned source-only guard smoke failed')
    for row in records:
        if row['guard']['decision'] is not None:
            raise ValueError('Structural guard must never emit a semantic decision')
    return records
