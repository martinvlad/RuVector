"""Label-free whole-source-unit selection; no model/runtime imports."""
import hashlib
import json
import math
import re
from collections import Counter

KIND = 'REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT'
ARMS = ('native', 'lexical', 'source_order')
LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
SEPARATOR = '\n\n'


def require(value, code):
    if not value:
        raise ValueError(code)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def validate_features(bank, role, expected_documents, expected_cases, archive_sha):
    require(set(bank) == {'schema_version', 'epoch', 'kind', 'role',
                         'source_archive_sha256', 'documents', 'cases'}, 'FEATURE_TOP_KEYS')
    require(bank['schema_version'] == 1 and bank['epoch'] == 48 and bank['kind'] == KIND
            and bank['role'] == role and bank['source_archive_sha256'] == archive_sha,
            'FEATURE_ROLE_AND_SOURCE')
    require(type(bank['documents']) is list and len(bank['documents']) == 4
            and [x['document_id'] for x in bank['documents']] == expected_documents,
            'FEATURE_DOCUMENT_ORDER')
    documents = {}
    for doc in bank['documents']:
        require(set(doc) == {'document_id', 'record_ordinal', 'source_group_sha256',
                            'source_document_sha256', 'normalized_document_sha256',
                            'source_filename_key_sha256', 'evidence'}, 'FEATURE_DOCUMENT_KEYS')
        units = doc['evidence']; require(type(units) is list and 1 <= len(units) <= 1024,
                                         'SOURCE_UNIT_COUNT')
        end = 0
        for number, unit in enumerate(units):
            require(set(unit) == {'unit_id', 'sentence', 'start', 'end'}
                    and type(unit['unit_id']) is int and unit['unit_id'] == number
                    and type(unit['start']) is int and unit['start'] == end
                    and type(unit['end']) is int and type(unit['sentence']) is str
                    and unit['sentence'] and unit['end'] == end + len(unit['sentence']),
                    'SOURCE_CONTIGUOUS_EXACT_UNIT')
            require(len(unit['sentence'].encode('utf-8')) <= 262144, 'SOURCE_UNIT_BYTES_CAP')
            end = unit['end']
        text = ''.join(x['sentence'] for x in units)
        require(len(text.encode('utf-8')) <= 1048576, 'SOURCE_DOCUMENT_BYTES_CAP')
        require(digest(text) == doc['source_document_sha256'], 'FULL_SOURCE_TEXT_HASH')
        require(digest(' '.join(text.casefold().split())) == doc['normalized_document_sha256'],
                'NORMALIZED_SOURCE_TEXT_HASH')
        group = 'ContractNLI|' + archive_sha + '|dev|' + str(doc['document_id'])
        require(digest(group) == doc['source_group_sha256'], 'SOURCE_GROUP_HASH')
        require(type(doc['document_id']) is int and doc['document_id'] not in documents,
                'SOURCE_DOCUMENT_UNIQUE')
        documents[doc['document_id']] = (doc, text)
    require(type(bank['cases']) is list and len(bank['cases']) == 12
            and [x['id'] for x in bank['cases']] == expected_cases, 'FEATURE_CASE_ORDER')
    for case in bank['cases']:
        require(set(case) == {'id', 'document_id', 'hypothesis_id', 'input_sha256', 'claim'},
                'FEATURE_CASE_KEYS')
        require(case['document_id'] in documents and type(case['claim']) is str
                and case['claim'].strip() and len(case['claim'].encode('utf-8')) <= 65536,
                'FEATURE_WHOLE_CLAIM')
        text = documents[case['document_id']][1]
        require(hashlib.sha256(canonical({'claim': case['claim'], 'document': text})).hexdigest()
                == case['input_sha256'], 'FEATURE_CASE_INPUT_HASH')
    require(len(set(expected_cases)) == 12, 'FEATURE_CASE_UNIQUE')
    for doc in expected_documents:
        require([x['hypothesis_id'] for x in bank['cases'] if x['document_id'] == doc]
                == ['nda-1', 'nda-10', 'nda-16'], 'FEATURE_FIXED_HYPOTHESES')
    return documents


def bm25_order(units, claim):
    """Fixed BM25 k1=1.2,b=.75, query-term multiplicity ignored; unit-ID ties."""
    terms = [Counter(re.findall(r'\w+', u['sentence'].casefold())) for u in units]
    query = set(re.findall(r'\w+', claim.casefold()))
    n = len(terms); lengths = [sum(t.values()) for t in terms]
    avg = sum(lengths) / n if sum(lengths) else 1.0
    df = {word: sum(word in t for t in terms) for word in query}
    scores = []
    for i, counts in enumerate(terms):
        value = math.fsum(math.log(1 + (n - df[word] + .5) / (df[word] + .5))
                          * (counts[word] * 2.2)
                          / (counts[word] + 1.2 * (.25 + .75 * lengths[i] / avg))
                          for word in sorted(query) if counts[word])
        scores.append(value)
    return sorted(range(n), key=lambda i: (-scores[i], i))


def pack(units, claim, order, tokenize):
    require(len(order) == len(units) and all(type(i) is int for i in order)
            and sorted(order) == list(range(len(units))), 'PACK_FULL_RANKED_PERMUTATION')
    base = tokenize('', claim)
    require(len(base['input_ids']) <= 512, 'WHOLE_HYPOTHESIS_EXCEEDS_PAIR_CAP')
    selected = []; proposals = []
    for index in order:
        if len(selected) == 4:
            break
        candidate = sorted([*selected, index])
        chosen = [units[i] for i in candidate]
        require(all(a['end'] <= b['start'] for a, b in zip(chosen, chosen[1:])),
                'PACK_SOURCE_OVERLAP')
        premise = SEPARATOR.join(x['sentence'] for x in chosen)
        tokens = tokenize(premise, claim)
        count = len(tokens['input_ids']); admissible = count <= 512
        proposals.append({'unit_id': index, 'candidate_unit_ids': candidate,
                          'pair_tokens': count, 'accepted': admissible})
        if admissible:
            selected = candidate
    require(selected, 'NO_WHOLE_SOURCE_UNIT_FITS_NO_NEUTRAL_FALLBACK')
    chosen = [units[i] for i in selected]
    premise = SEPARATOR.join(x['sentence'] for x in chosen)
    tokens = tokenize(premise, claim)
    require(0 < len(tokens['input_ids']) <= 512 and len(selected) <= 4,
            'FINAL_PAIR_CAP')
    occurrences = numeric_occurrences(chosen, premise)
    evidence = {'selected_unit_ids': selected,
                'units': [{'unit_id': x['unit_id'], 'start': x['start'], 'end': x['end'],
                           'sha256': digest(x['sentence'])} for x in chosen],
                'premise_sha256': digest(premise), 'claim_sha256': digest(claim),
                'pair_input_sha256': hashlib.sha256(canonical({'premise': premise,
                                                              'claim': claim})).hexdigest(),
                'token_ids_sha256': hashlib.sha256(canonical(tokens['input_ids'])).hexdigest(),
                'pair_token_count': len(tokens['input_ids']),
                'source_units_total': len(units), 'selected_source_characters': sum(
                    len(x['sentence']) for x in chosen),
                'source_characters_total': sum(len(x['sentence']) for x in units),
                'whole_units_unchanged': True, 'claim_unchanged': True,
                'coverage_is_not_evidence_sufficiency': True,
                'numeric_date_currency_negation_audit': occurrences,
                'packing_proposals': proposals}
    return tokens, evidence


def numeric_occurrences(units, premise):
    """Exact substring/count preservation only, never semantic numerical verification."""
    pattern = re.compile(r'[$€£¥]?\b\d+(?:[.,:/-]\d+)*(?:\s?(?:%|USD|EUR|GBP|days?|years?))?'
                         r'|\b(?:not|no|never|unless|except|without)\b', re.IGNORECASE)
    intended = Counter(m.group() for x in units for m in pattern.finditer(x['sentence']))
    observed = Counter(m.group() for m in pattern.finditer(premise))
    require(intended == observed, 'NUMERIC_SUBSTRING_PRESERVATION_FAILED')
    return {'source_and_premise_occurrence_counts_match': True,
            'occurrence_count': sum(intended.values()),
            'multiset_sha256': hashlib.sha256(canonical(sorted(intended.items()))).hexdigest(),
            'semantic_arithmetic_or_date_verification': False,
            'confidence_or_label_override': False}
