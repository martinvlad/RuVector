"""E38 label-free native/lexical source-constraint coverage; no neural import at module load."""
import hashlib
import math
import time
from pathlib import Path
BGE_SOURCE='experiments/sota-2026-10-22/candidate/epoch3/models.py'
BGE_SHA='c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
QUERY_PREFIX='Represent this sentence for searching relevant passages: '
RAW_CONTEXTS=('full_source','native_coverage','lexical_coverage')
ARMS=('full_raw','native_raw','native_verified','lexical_verified','full_verified')
MAP={'full_raw':'full_source','full_verified':'full_source','native_raw':'native_coverage','native_verified':'native_coverage','lexical_verified':'lexical_coverage'}
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
    if C.sha(C.checked(BGE_SOURCE))!=BGE_SHA:raise ValueError('Original source BGE hash changed')
    context=C.load_module('e38_source_context',Path(__file__).with_name('source_context.py'))
    quantitative=C.load_module('e38_quantitative_catalog',Path(__file__).with_name('quantitative.py'))
    models=C.load_module('e38_original_BGE3',C.checked(BGE_SOURCE))
    counters['BGE_initializations_attempted']+=1;counters['ORT_sessions_attempted']+=1
    progress({'event':'BGE_INITIALIZATION_BEFORE'});started=time.perf_counter();bge=models.BgeEncoder(C.ROOT)
    counters['BGE_initializations_completed']+=1;counters['ORT_sessions_completed']+=1
    bge.session=CountedSession(bge.session,counters,progress)
    receipt={**bge.receipt,'initialization_seconds':time.perf_counter()-started,'source_path':BGE_SOURCE,
        'source_sha256':BGE_SHA,'one_session':True,'no_warmup':True,'no_truncated_model_input':True,'query_prefix':QUERY_PREFIX}
    progress({'event':'BGE_INITIALIZATION_AFTER'});return context,quantitative,bge,receipt

def prepare(C,records,tokenizer,counters,progress,codec,runtime,role):
    if role!='engineering':raise ValueError('Only independently authored engineering role')
    context,quantitative,bge,receipt=runtime
    query_policy=C.load_module('e38_original_query',Path(__file__).with_name('query.py'))
    documents={};bundle={'schema_version':3,'epoch':38,'kind':'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES',
        'vector_encoding':'base64_float32le_c_order','metadata_policy':'insert id and vector only; metadata absent','documents':[],'role':role}
    for record in records:
        document=record['document'];did=str(record['document_id']);started=time.perf_counter()
        units=context.partition(document,tokenizer,bge.raw_tokenizer,target=128,nli_cap=160,bge_cap=256,max_units=40)
        chunks=[document[u['start']:u['end']]for u in units];query=query_policy.query(record['hypothesis']);q=QUERY_PREFIX+query['query']
        if len(bge.raw_tokenizer.encode(q).ids)>256:raise ValueError('Whole original BGE query exceeds256; no clipping')
        if len(tokenizer.encode('',record['hypothesis']).ids)>512:raise ValueError('Whole original hypothesis exceeds512')
        counters['source_analysis_calls_attempted']+=1;analysis=quantitative.analyze(document,record['hypothesis']);counters['source_analysis_calls_completed']+=1
        counters['automatically_extracted_units']+=len(units)
        vectors,dd=bge.encode(chunks);qv,qd=bge.encode([q])
        if vectors.shape!=(len(chunks),384)or qv.shape!=(1,384):raise ValueError('BGE physical matrices differ')
        norms=[math.sqrt(math.fsum(float(x)*float(x)for x in row))for row in [*vectors,*qv]]
        if any(not math.isfinite(v)or abs(v-1)>1e-5 for v in norms):raise ValueError('Actual BGE vectors not normalized384')
        documents[did]={'units':units,'partition_model_tag':'xxlarge','partition_seconds':time.perf_counter()-started,
            'retrieval_queries':{record['id']:query},'source_analysis':analysis,
            'embedding':{'document':dd,'queries':qd,'exact_query_texts':[q],'source_sha256s':[hashlib.sha256(t.encode()).hexdigest()for t in chunks],
                'norm_min':min(norms),'norm_max':max(norms)}}
        bundle['documents'].append({'document_id':did,'vectors':_block(vectors,codec),'query_vectors':_block(qv,codec),
            'queries':[{'id':record['id']+'::retrieval:original'}]})
        progress({'event':'DOCUMENT_LABEL_FREE_EMBEDDING_COMPLETED','document_id':did,'units':len(units)})
    return context,documents,bundle,receipt

def initialize_cases(records,documents,native_result,evidence,counters):
    observed={}
    for document in native_result['documents']:
        for query in document['queries']:
            if query['case_id']in observed:raise ValueError('Duplicate native query')
            observed[query['case_id']]={**query,'document_id':document['document_id'],'initialization_ms':document['initialization_ms'],'initialized_vectors':document['initialized_vectors']}
    if set(observed)!={r['id']+'::retrieval:original'for r in records}:raise ValueError('Native query source identities differ')
    cases=[]
    for source in records:
        did=str(source['document_id']);prepared=documents[did];native=observed[source['id']+'::retrieval:original'];n=len(prepared['units'])
        if (native['document_id']!=did or n>40 or native.get('requested_k')!=n or native.get('initialized_vectors')!=n
                or len(native['ids'])!=n or any(type(v)is not int for v in native['ids'])or set(native['ids'])!=set(range(n))):
            raise ValueError('Native full unique source unit set required, never absence inference')
        chunks=[source['document'][u['start']:u['end']]for u in prepared['units']]
        query=prepared['retrieval_queries'][source['id']];lexical,scores=evidence.lexical_order(chunks,query['query'])
        row={k:source[k]for k in('id','document_id','hypothesis_id','input_sha256')}
        row.update(document=source['document'],document_sha256=evidence.text_sha(source['document']),hypothesis=source['hypothesis'],
            hypothesis_sha256=evidence.text_sha(source['hypothesis']),native=native,retrieval_query=query,
            lexical_jaccard_scores=scores,lexical_ranking=lexical,document_preparation_ref=did,source_analysis=prepared['source_analysis'],
            native_complete_unique_unitset_verified=True,readouts={name:None for name in RAW_CONTEXTS},arms={arm:None for arm in ARMS})
        counters['native_complete_unitset_cases_verified']+=1;cases.append(row)
    return cases

def pack_for_model(cases,records,documents,role,context,evidence,tokenizer,counters,progress,model_tag):
    if role!='engineering'or model_tag!='xxlarge':raise ValueError('Exactly one original model')
    for row,source in zip(cases,records):
        prepared=documents[str(source['document_id'])];units=prepared['units'];analysis=prepared['source_analysis']
        for name in RAW_CONTEXTS:
            if row['readouts'][name]is not None:raise ValueError('Repeated measured context prohibited')
            started=time.perf_counter();ranking=row['lexical_ranking']if name=='lexical_coverage'else row['native']['ids']
            if name=='full_source':
                premise=source['document'];count=len(tokenizer.encode(premise,source['hypothesis']).ids)
                if not 0<count<=512:raise ValueError('Whole exact source does not fit512; no clipping')
                audit={'policy':'native-complete-source-when-pair-fits512-v1','selected_source_spans':[[0,len(premise)]],
                    'selected_chunk_ids_source_order':list(range(len(units))),'selected_group_ids_admission_order':[g['group_id']for g in context.groups(premise,units)],
                    'joint_pair_tokens':count,'joint_pair_token_cap':512,'full_supplied_source_in_original_order':True,
                    'selected_evidence_truncated':False,'claim_truncated':False,'document_character_coverage':1.0,
                    'all_required_source_quotes_covered':True,'dependency_analysis_sha256':analysis['analysis_sha256']}
                counters['full_source_contexts_completed']+=1
            else:
                premise,audit=context.pack(source['document'],units,ranking,source['hypothesis'],tokenizer,analysis,pair_cap=512)
                counters['coverage_contexts_completed']+=1
            audit['source_provenance']=evidence.provenance(source['document'],premise,audit)
            count=len(tokenizer.encode(premise,source['hypothesis']).ids)
            if count!=audit['joint_pair_tokens']or not 0<count<=512:raise ValueError('True context pair cap differs')
            row['readouts'][name]={'readout_id':source['id']+'::NLI:'+name,'measured_context':name,'model_tag':'xxlarge',
                'premise':premise,'context':audit,'joint_pair_tokens':count,'context_seconds':time.perf_counter()-started,
                'native_query_seconds':row['native']['query_ms']/1000,'reader':None,'observed_ranking':list(ranking)}
            counters['ENGINEERING_contexts_completed']+=1
            progress({'event':'PHYSICAL_CONTEXT_READY','id':row['id'],'measured_context':name,'pair_tokens':count})
