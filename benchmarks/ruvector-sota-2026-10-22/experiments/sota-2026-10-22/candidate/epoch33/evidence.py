"""Mechanical exact-source provenance; never alters NLI semantic predictions."""
from __future__ import annotations
import hashlib
import json
import math
import re

TRAIN_DOCUMENT_IDS = ()
DEV_DOCUMENT_IDS = (91,427,299,439,513,268,583,402)
HYPOTHESIS_IDS = ('nda-17', 'nda-7', 'nda-3')
# Literal signed decimals, thousands groups, leading decimals, years
# adjacent to punctuation. No amount/year normalization or arithmetic is used.
NUMBER = re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_inputs(bundle, role):
    if role not in ('engineering','dev'):raise ValueError('Only authored ENG and conditional DEV inputs')
    n=6 if role=='engineering' else 24
    if not isinstance(bundle,dict) or set(bundle)!={'schema_version','epoch','role','records'} or bundle['schema_version']!=1 or bundle['epoch']!=33 or bundle['role']!=role or not isinstance(bundle['records'],list) or len(bundle['records'])!=n:raise ValueError('Wrong fixed inputs-only role bank')
    expected=[(-32000-i,f'eng-{i}',f'epoch32:cc0:engineering:{i}') for i in range(1,7)] if role=='engineering' else [(d,h,f'original-contractnli:train:epoch33:dev:{d}:{h}') for d in DEV_DOCUMENT_IDS for h in HYPOTHESIS_IDS]
    documents,hypotheses={},{}
    for row,(d,h,case) in zip(bundle['records'],expected):
        if set(row)!={'id','document_id','hypothesis_id','document','hypothesis','input_sha256'} or row['id']!=case or row['document_id']!=d or row['hypothesis_id']!=h:raise ValueError('Exact input identity/order/keys required; oracle fields prohibited')
        for key,cap in (('document',1000000),('hypothesis',8192)):
            value=row[key]
            if not isinstance(value,str) or not value.strip() or '\0' in value or len(value)>cap:raise ValueError('Invalid full source string')
            value.encode('utf-8',errors='strict')
        payload=json.dumps({k:row[k] for k in ('document','hypothesis')},sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        if hashlib.sha256(payload).hexdigest()!=row['input_sha256']:raise ValueError('Changed full source text')
        if d in documents and documents[d]!=row['document'] or h in hypotheses and hypotheses[h]!=row['hypothesis']:raise ValueError('Conflicting source strings')
        documents[d],hypotheses[h]=row['document'],row['hypothesis']
    return bundle['records']


def span(text, start, end):
    if not 0 <= start < end <= len(text):
        raise ValueError('Invalid source character span')
    literal = text[start:end]
    first, last = len(text[:start].encode('utf-8')), len(text[:end].encode('utf-8'))
    if text.encode('utf-8')[first:last].decode('utf-8') != literal:
        raise ValueError('Exact UTF8 byte provenance failed')
    return {'source_char_start': start, 'source_char_end': end,
            'source_byte_start': first, 'source_byte_end': last,
            'text': literal, 'text_sha256': text_sha(literal)}


def provenance(document, premise, context):
    spans = context['selected_source_spans']
    selected = [span(document, a, b) for a, b in spans]
    if '\n\n'.join(s['text'] for s in selected) != premise:
        raise ValueError('Packed premise must be exact source slices plus fixed separators')
    if spans != sorted(spans) or any(x[1] > y[0] for x, y in zip(spans, spans[1:])):
        raise ValueError('Source spans must be ordered without overlap')
    literals = []
    for match in NUMBER.finditer(document):
        row = span(document, match.start(), match.end())
        row['retained'] = any(a <= match.start() and match.end() <= b for a, b in spans)
        row['lexical_year_candidate'] = bool(re.fullmatch(r'\d{4}', match.group())
                                             and 1000 <= int(match.group()) <= 2999)
        literals.append(row)
    return {'selected_source_provenance': selected, 'numeric_literals': literals,
            'numeric_literals_retained': sum(row['retained'] for row in literals),
            'numeric_literals_omitted': sum(not row['retained'] for row in literals),
            'numeric_literal_pattern': NUMBER.pattern, 'source_text_normalized': False,
            'semantic_decision_override': False,
            'scope': 'Literal source offsets/retention only; omissions never prove global NotMentioned.'}


def lexical_order(chunks, hypothesis):
    query = set(re.findall(r'\w+', hypothesis.casefold()))
    words = [set(re.findall(r'\w+', text.casefold())) for text in chunks]
    scores = [len(query & w) / max(1, len(query | w)) for w in words]
    if not all(math.isfinite(x) for x in scores):
        raise ValueError('Nonfinite lexical Jaccard')
    return sorted(range(len(chunks)), key=lambda i: (-scores[i], i)), scores


class PairTokenizer:
    """Preserve old source-group API while using exact admitted HF pair encoding."""
    def __init__(self, tokenizer, counters=None):
        self.tokenizer,self.counters = tokenizer,counters

    def encode(self, text, pair=None, add_special_tokens=True):
        kind='context_pair_tokenizer_calls' if pair is not None else 'context_single_tokenizer_calls'
        if self.counters is not None:
            self.counters['context_tokenizer_calls_attempted']+=1;self.counters[kind+'_attempted']+=1
        output = self.tokenizer(text, text_pair=pair, add_special_tokens=add_special_tokens,
                                padding=False, truncation=False,
                                return_attention_mask=False, return_token_type_ids=False,
                                return_offsets_mapping=True)
        if self.counters is not None:
            self.counters['context_tokenizer_calls_completed']+=1;self.counters[kind+'_completed']+=1
        class Encoded:
            pass
        result = Encoded()
        result.ids = output['input_ids']
        result.offsets = output['offset_mapping']
        return result
