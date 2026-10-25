"""Frozen E36 shared native corpus, exact full sources and unchanged two-group controls.

All imports here are standard-library-only. BGE is loaded after admission by
prepare(); no NLI forward or label/evidence annotation is used in selection.
"""
import hashlib
import importlib.util
import math
import time
from pathlib import Path

BGE_SOURCE = 'experiments/sota-2026-10-22/candidate/epoch3/models.py'
BGE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
CONTEXT_SOURCE = 'experiments/sota-2026-10-22/candidate/epoch36/source_context.py'
CONTEXT_SHA = 'e847c2d3819a3b469bb6a601a9633f4c8a1279d2b3a2a3e2c2d02cd82eb5c517'
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
FULL_POLICY = 'native-complete-source-when-pair-fits512-v1'
ARMS = ('xxlarge_full_source','xxlarge_native_two','xxlarge_lexical_two','xxlarge_positional_two','b354_full_source','b354_native_two')


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
    context = C.load_module('e36_unchanged_source_context22', C.checked(CONTEXT_SOURCE))
    models = C.load_module('e36_unchanged_BGE3', C.checked(BGE_SOURCE))
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
    query_policy=C.load_module('e36_unchanged_query_hybrid_policy',Path(__file__).with_name('query.py'))
    documents, bundle = {}, {'schema_version': 3, 'epoch': 36,
        'kind': 'ENGINEERING_PAIRED_READER_SOURCE_COVERAGE',
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
        query_receipts={row['id']:query_policy.query(row['hypothesis']) for row in rows}
        queries=[QUERY_PREFIX+query_receipts[row['id']]['query'] for row in rows]
        if any(len(bge.raw_tokenizer.encode(query).ids) > 256 for query in queries):
            raise ValueError('Whole BGE query exceeds256; no clipping/fallback')
        if any(len(tokenizer.encode('', row['hypothesis']).ids) > 512 for row in rows):
            raise ValueError('Whole unchanged hypothesis exceeds pair budget')
        partition_seconds = time.perf_counter() - started
        counters['automatically_extracted_units'] += len(units)
        vectors, document_diagnostics = bge.encode(chunks)
        query_vectors, query_diagnostics = bge.encode(queries)
        if vectors.shape != (len(chunks), 384) or query_vectors.shape != (len(rows), 384):
            raise ValueError('Actual BGE vector matrix shape differs')
        norms = [math.sqrt(math.fsum(float(x) * float(x) for x in row)) for row in [*vectors, *query_vectors]]
        if any(not math.isfinite(value) or abs(value - 1) > 1e-5 for value in norms):
            raise ValueError('Actual BGE vectors are not finite normalized384')
        documents[document_id] = {'retrieval_queries':query_receipts,'units': units, 'prelude': prelude, 'preludes_by_model': {'b354': prelude}, 'partition_model_tag': 'b354', 'partition_seconds': partition_seconds,
            'embedding': {'document': document_diagnostics, 'queries': query_diagnostics,
                'exact_query_texts': queries, 'source_sha256s': [hashlib.sha256(text.encode('utf-8')).hexdigest() for text in chunks],
                'norm_min': min(norms), 'norm_max': max(norms)}}
        bundle['documents'].append({'document_id': document_id, 'vectors': _block(vectors, codec),
            'query_vectors': _block(query_vectors, codec), 'queries': [{'id':row['id']+'::retrieval:original'} for row in rows]})
        progress({'event': 'DOCUMENT_LABEL_FREE_EMBEDDING_COMPLETED', 'document_id': document_id, 'units': len(units)})
    return context, documents, bundle, receipt



def initialize_cases(records,documents,native_result,evidence,counters):
    """Authenticate one actual full native unit set before any full-source arm."""
    observed={}
    for document in native_result['documents']:
        for query in document['queries']:
            if query['case_id']in observed:raise ValueError('Duplicate actual shared native query')
            observed[query['case_id']]={**query,'document_id':document['document_id'],
                'initialization_ms':document['initialization_ms'],'initialized_vectors':document['initialized_vectors']}
    if set(observed)!={r['id']+'::retrieval:original'for r in records}:raise ValueError('Shared native identities differ')
    cases=[]
    for source in records:
        did=str(source['document_id']);prepared=documents[did];native=observed[source['id']+'::retrieval:original'];n=len(prepared['units'])
        if (native['document_id']!=did or n>40 or native.get('requested_k')!=n
                or native.get('initialized_vectors')!=n or len(native['ids'])!=n
                or any(type(v)is not int for v in native['ids']) or set(native['ids'])!=set(range(n))):
            raise ValueError('Actual complete unique native unit set required; no absence inference or fallback')
        chunks=[source['document'][u['start']:u['end']]for u in prepared['units']]
        query=prepared['retrieval_queries'][source['id']];lexical,scores=evidence.lexical_order(chunks,query['query'])
        row={k:source[k]for k in('id','document_id','hypothesis_id','input_sha256')}
        row.update(document=source['document'],document_sha256=evidence.text_sha(source['document']),
            hypothesis=source['hypothesis'],hypothesis_sha256=evidence.text_sha(source['hypothesis']),
            native=native,retrieval_query=query,lexical_jaccard_scores=scores,lexical_ranking=lexical,
            document_preparation_ref=did,native_complete_unique_unitset_verified=True,arms={arm:None for arm in ARMS})
        counters['native_complete_unitset_cases_verified']+=1;cases.append(row)
    return cases


def pack_full(source,prepared,native,context,evidence,tokenizer):
    """Full supplied bytes are admitted only with complete native source coverage."""
    state,hypothesis=source['document'],source['hypothesis'];units=prepared['units'];n=len(units)
    if n>40 or len(native['ids'])!=n or set(native['ids'])!=set(range(n)):
        raise ValueError('Complete native source units required before full-source readout')
    catalog=context.groups(state,units);count=len(tokenizer.encode(state,hypothesis).ids)
    if not 0<count<=512:raise ValueError('Complete supplied source does not fit512; no clipping/fallback')
    audit={'policy':FULL_POLICY,'source_sentence_groups':catalog,
        'full_supplied_source_in_original_order':True,'native_complete_unique_unitset_verified':True,
        'group_ranking_policy':'All actual native source units must be present; full original source order, no ranked-unit omission',
        'selected_group_ids_admission_order':[g['group_id']for g in catalog],
        'all_selected_groups_complete':True,'ranking_ids_considered':list(native['ids']),
        'ranking_depth':n,'ranked_anchor_candidate_cap':n,
        'selected_chunk_ids_rank_order':list(native['ids']),'selected_chunk_ids_source_order':list(range(n)),
        'selected_source_spans':[[0,len(state)]],'omitted_chunk_ids':[],'omitted_source_spans':[],
        'total_document_chunks':n,'retained_source_characters':len(state),'document_characters':len(state),
        'document_character_coverage':1.0,'joint_pair_tokens':count,'joint_pair_token_cap':512,
        'selected_evidence_truncated':False,'claim_truncated':False,
        'premise_sha256':evidence.text_sha(state),'hypothesis_sha256':evidence.text_sha(hypothesis),
        'selected_token_fallback_unit_ids':[u['id']for u in units if u['token_fallback']],
        'scope':'Exact complete supplied source after actual complete native unitset verification. No source rewrite, arithmetic override, global absence or benchmark generalization.'}
    audit['source_provenance']=evidence.provenance(state,state,audit)
    return state,audit


def pack_for_model(cases,records,documents,role,context,evidence,tokenizer,counters,progress,model_tag):
    if role!='engineering'or model_tag not in('b354','xxlarge'):raise ValueError('Only fixed paired engineering profiles')
    names=('b354_full_source','b354_native_two')if model_tag=='b354'else ARMS[:4]
    for row,source in zip(cases,records):
        prepared=documents[str(source['document_id'])];native=row['native'];n=len(prepared['units'])
        prelude=context.select_prelude(source['document'],prepared['units'],tokenizer)
        if model_tag=='b354'and prepared['prelude']!=prelude:raise ValueError('Shared b354 source partition/prelude changed')
        prepared['preludes_by_model'][model_tag]=prelude
        rankings={'native_two':native['ids'],'lexical_two':row['lexical_ranking'][:40],
            'positional_two':list(range(min(40,n)))}
        for arm in names:
            if row['arms'][arm]is not None:raise ValueError('Repeated arm context/model phase forbidden')
            started=time.perf_counter();suffix=arm.removeprefix(model_tag+'_')
            if suffix=='full_source':
                premise,audit=pack_full(source,prepared,native,context,evidence,tokenizer);ranking=list(native['ids'])
                counters['full_source_contexts_completed']+=1
            else:
                ranking=rankings[suffix]
                premise,audit=context.pack(source['document'],prepared['units'],ranking,source['hypothesis'],
                    tokenizer,pair_cap=512,rank_depth=min(40,n),prelude=prelude)
                audit['legacy_numeric_mentions']=audit.pop('numeric_mentions')
                audit['legacy_numeric_mentions_retained']=audit.pop('numeric_mentions_retained')
                audit['legacy_numeric_mentions_omitted']=audit.pop('numeric_mentions_omitted')
                audit['source_provenance']=evidence.provenance(source['document'],premise,audit)
                counters['two_group_contexts_completed']+=1
            pair_tokens=len(tokenizer.encode(premise,source['hypothesis']).ids)
            if pair_tokens!=audit['joint_pair_tokens']or not 0<pair_tokens<=512:raise ValueError('Complete true-pair tokenizer budget differs')
            candidate={'model_tag':model_tag,'observed_ranking':list(ranking),'premise':premise,'context':audit,
                'joint_pair_tokens':pair_tokens,'context_seconds':time.perf_counter()-started,
                'native_query_seconds':native['query_ms']/1000 if suffix in('full_source','native_two')else None,
                'reader':None,'decision':None,'decision_seconds':None,'semantic_decision_override':False}
            if model_tag=='xxlarge':
                baseline=row['arms']['b354_'+suffix]if suffix in('full_source','native_two')else None
                if baseline is not None and (candidate['premise']!=baseline['premise']
                        or candidate['context']['selected_source_spans']!=baseline['context']['selected_source_spans']):
                    raise ValueError('Cross-model full/native-two source bytes or spans differ; no drift allowed')
            row['arms'][arm]=candidate;counters['ENGINEERING_contexts_completed']+=1
        progress({'event':'MODEL_CASE_CONTEXTS_COMPLETED','case_id':source['id'],'phase':role,'model_tag':model_tag})
    return cases
