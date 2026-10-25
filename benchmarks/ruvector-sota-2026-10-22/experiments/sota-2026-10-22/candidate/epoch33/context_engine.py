"""Frozen E27 legal source contexts with genuine BGE/native evidence once/phase.

All imports here are standard-library-only. BGE is loaded after admission by
prepare(); no NLI forward or label/evidence annotation is used in selection.
"""
import hashlib
import math
import time
from pathlib import Path

BGE_SOURCE = 'experiments/sota-2026-10-22/candidate/epoch3/models.py'
BGE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
CONTEXT_SOURCE = 'experiments/sota-2026-10-22/candidate/epoch22/context.py'
CONTEXT_SHA = '9ca2968ed800443bc75fac452daf2cbf17bf27cf1b3b75cbfb220bfa23a9e727'
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
ARMS = ('actual_native', 'native_original', 'lexical', 'positional')


class CountedSession:
    def __init__(self, session, counters, progress):
        self.session, self.counters, self.progress = session, counters, progress

    def run(self, names, feed):
        count = len(feed['input_ids'])
        self.counters['BGE_forward_calls_attempted'] += 1
        self.counters['BGE_texts_attempted'] += count
        self.progress({'event': 'BGE_FORWARD_BEFORE', 'texts': count})
        started = time.perf_counter()
        value = self.session.run(names, feed)
        self.counters['BGE_forward_calls_completed'] += 1
        self.counters['BGE_texts_completed'] += count
        self.counters['BGE_forward_seconds'] += time.perf_counter() - started
        self.progress({'event': 'BGE_FORWARD_AFTER', 'texts': count})
        return value


def _block(matrix, codec):
    if str(matrix.dtype) != 'float32' or len(matrix.shape) != 2 or matrix.shape[1] != 384:
        raise ValueError('Actual BGE float32 matrix required')
    block = codec.encode(matrix.astype('<f4', copy=False).tobytes(order='C'), int(matrix.shape[0]))
    codec.decode(block)
    return block


def initialize(C,counters,progress):
    if C.sha(C.checked(BGE_SOURCE)) != BGE_SHA or C.sha(C.checked(CONTEXT_SOURCE)) != CONTEXT_SHA:
        raise ValueError('Original BGE/context source changed')
    context = C.load_module('e33_unchanged_source_context22', C.checked(CONTEXT_SOURCE))
    models = C.load_module('e33_unchanged_BGE3', C.checked(BGE_SOURCE))
    counters['BGE_initializations_attempted'] += 1
    counters['ORT_sessions_attempted'] += 1
    progress({'event': 'BGE_INITIALIZATION_BEFORE'})
    started = time.perf_counter()
    bge = models.BgeEncoder(C.ROOT)
    counters['BGE_initializations_completed'] += 1
    counters['ORT_sessions_completed'] += 1
    bge.session = CountedSession(bge.session, counters, progress)
    receipt = {**bge.receipt, 'initialization_seconds': time.perf_counter() - started,
        'source_path': BGE_SOURCE, 'source_sha256': BGE_SHA, 'query_prefix': QUERY_PREFIX,
        'one_session': True, 'no_warmup': True, 'no_truncated_model_input': True}
    progress({'event': 'BGE_INITIALIZATION_AFTER'})
    return context,bge,receipt


def prepare(C,records,tokenizer,counters,progress,codec,runtime,role):
    context,bge,receipt=runtime
    query_policy=C.load_module('e33_typed_modal_query',Path(__file__).with_name('query.py'))
    documents, bundle = {}, {'schema_version': 3, 'epoch': 33,
        'kind': 'REAL_NATIVE_TYPED_MODAL_RETRIEVAL_NLI_DIAGNOSTIC',
        'vector_encoding': 'base64_float32le_c_order', 'metadata_policy': 'insert id and vector only; metadata absent',
        'documents': [],'role':role}
    groups=[]
    for record in records:
        if not groups or groups[-1][0]['document_id']!=record['document_id']:groups.append([])
        groups[-1].append(record)
    for rows in groups:
        document, document_id = rows[0]['document'], str(rows[0]['document_id'])
        started = time.perf_counter()
        units = context.partition(document, tokenizer, bge.raw_tokenizer,
            target=128, nli_cap=160, bge_cap=256, max_units=192)
        prelude = context.select_prelude(document, units, tokenizer)
        chunks = [document[unit['start']:unit['end']] for unit in units]
        query_receipts={row['id']:query_policy.expand(row['hypothesis']) for row in rows}
        queries=[QUERY_PREFIX+query_receipts[row['id']][variant+'_query'] for row in rows for variant in ('original','expanded')]
        if any(len(bge.raw_tokenizer.encode(query).ids) > 256 for query in queries):
            raise ValueError('Whole BGE query exceeds256; no clipping/fallback')
        if any(len(tokenizer.encode('', row['hypothesis']).ids) > 512 for row in rows):
            raise ValueError('Whole unchanged hypothesis exceeds pair budget')
        partition_seconds = time.perf_counter() - started
        counters['automatically_extracted_units'] += len(units)
        vectors, document_diagnostics = bge.encode(chunks)
        query_vectors, query_diagnostics = bge.encode(queries)
        if vectors.shape != (len(chunks), 384) or query_vectors.shape != (2*len(rows), 384):
            raise ValueError('Actual BGE vector matrix shape differs')
        norms = [math.sqrt(math.fsum(float(x) * float(x) for x in row)) for row in [*vectors, *query_vectors]]
        if any(not math.isfinite(value) or abs(value - 1) > 1e-5 for value in norms):
            raise ValueError('Actual BGE vectors are not finite normalized384')
        documents[document_id] = {'retrieval_queries':query_receipts,'units': units, 'prelude': prelude, 'partition_seconds': partition_seconds,
            'embedding': {'document': document_diagnostics, 'queries': query_diagnostics,
                'exact_query_texts': queries, 'source_sha256s': [hashlib.sha256(text.encode('utf-8')).hexdigest() for text in chunks],
                'norm_min': min(norms), 'norm_max': max(norms)}}
        bundle['documents'].append({'document_id': document_id, 'vectors': _block(vectors, codec),
            'query_vectors': _block(query_vectors, codec), 'queries': [{'id':row['id']+'::retrieval:'+variant} for row in rows for variant in ('original','expanded')]})
        progress({'event': 'DOCUMENT_LABEL_FREE_EMBEDDING_COMPLETED', 'document_id': document_id, 'units': len(units)})
    return context, documents, bundle, receipt


def pack_all(records, documents, native_result, phase, context, evidence, tokenizer, counters, progress):
    observed = {}
    for document in native_result['documents']:
        for query in document['queries']:
            if query['case_id'] in observed:
                raise ValueError('Duplicate actual native query case')
            observed[query['case_id']] = {**query, 'document_id': document['document_id'],
                'initialization_ms': document['initialization_ms'], 'initialized_vectors': document['initialized_vectors']}
    if set(observed) != {row['id']+'::retrieval:'+variant for row in records for variant in ('original','expanded')}:
        raise ValueError('Actual native case identity closure differs')
    cases = []
    for source in records:
        document_id = str(source['document_id'])
        prepared = documents[document_id]
        chunks = [source['document'][unit['start']:unit['end']] for unit in prepared['units']]
        query_receipt=prepared['retrieval_queries'][source['id']]
        lexical, scores = evidence.lexical_order(chunks, query_receipt['expanded_query'])
        native = observed[source['id']+'::retrieval:expanded']
        native_original=observed[source['id']+'::retrieval:original']
        if native['document_id'] != document_id or native_original['document_id']!=document_id:
            raise ValueError('Native query belongs to another document')
        rankings = {'actual_native': native['ids'], 'native_original':native_original['ids'], 'lexical': lexical[:40],
            'positional': list(range(min(40, len(prepared['units']))))}
        row = {key: source[key] for key in ('id', 'document_id', 'hypothesis_id', 'input_sha256')}
        row.update(document=source['document'],document_sha256=evidence.text_sha(source['document']), hypothesis=source['hypothesis'],
            hypothesis_sha256=evidence.text_sha(source['hypothesis']), native=native,native_original=native_original,retrieval_query=query_receipt,
            lexical_jaccard_scores=scores, document_preparation_ref=document_id, arms={})
        for arm in ARMS:
            started = time.perf_counter()
            premise, audit = context.pack(source['document'], prepared['units'], rankings[arm], source['hypothesis'],
                tokenizer, pair_cap=512, rank_depth=min(40, len(prepared['units'])), prelude=prepared['prelude'])
            audit['legacy_numeric_mentions'] = audit.pop('numeric_mentions')
            audit['legacy_numeric_mentions_retained'] = audit.pop('numeric_mentions_retained')
            audit['legacy_numeric_mentions_omitted'] = audit.pop('numeric_mentions_omitted')
            audit['source_provenance'] = evidence.provenance(source['document'], premise, audit)
            pair_tokens = len(tokenizer.encode(premise, source['hypothesis']).ids)
            if pair_tokens != audit['joint_pair_tokens'] or not 0 < pair_tokens <= 512:
                raise ValueError('Exact source context/true-pair token count differs')
            row['arms'][arm] = {'observed_ranking': rankings[arm], 'premise': premise, 'context': audit,
                'joint_pair_tokens': pair_tokens, 'context_seconds': time.perf_counter() - started,
                'native_query_seconds': (native if arm=='actual_native' else native_original)['query_ms']/1000 if arm in ('actual_native','native_original') else None,
                'reader': None, 'decision': None, 'decision_seconds':None, 'semantic_decision_override': False}
            counters[phase.upper() + '_contexts_completed'] += 1
        cases.append(row)
        progress({'event': 'ALL_LABEL_FREE_CASE_CONTEXTS_COMPLETED', 'case_id': source['id'], 'phase': phase})
    return cases
