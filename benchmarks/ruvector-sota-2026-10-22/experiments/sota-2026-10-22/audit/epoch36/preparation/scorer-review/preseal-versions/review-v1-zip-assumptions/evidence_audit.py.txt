"""Independent exact-source context and actual native f32 receipt replay."""
import base64
import math
import re
import struct
from data_common import require,identity,digest,expected,finite,canonical
from phase_audit import checked,read,KIND
from query_audit import query_check
from group_audit import source_groups,prelude_check,context_check
from source_coverage_audit import numeric_check,full_context_check
from nli_metrics import ARMS,model_for_arm

PREFIX='Represent this sentence for searching relevant passages: '
ABSENT='{"present":false}'
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')

def block_digests(block):
    require(block['encoding']=='base64'and block['dtype']=='float32le','Wrong numeric vector encoding')
    shape=block['shape'];require(type(shape)is list and len(shape)==2 and type(shape[0])is int
        and 0<shape[0]<=192 and shape[1]==384,'Wrong numeric vector dimensions')
    b=base64.b64decode(block['data_base64'],validate=True)
    require(base64.b64encode(b).decode()==block['data_base64']and len(b)==block['bytes']==shape[0]*1536
            and digest(b)==block['sha256'],'Lossless vector bytes/hash mismatch')
    result=[]
    for i in range(shape[0]):
        row=b[i*1536:(i+1)*1536];v=struct.unpack('<384f',row)
        require(all(math.isfinite(x)for x in v)and abs(math.sqrt(math.fsum(x*x for x in v))-1)<=1e-5,
                'Source BGE output must be finite normalized float32')
        result.append(digest(row))
    return result

def native_query_check(query,digests,units):
    k=min(40,len(units))
    require(type(query['requested_k'])is int and query['requested_k']==len(query['ids'])==len(query['raw_hits'])==k
            and all(type(i)is int for i in query['ids'])
            and len(set(query['ids']))==k and query['ids']==[int(h['id'])for h in query['raw_hits']]
            and query['native_order_used_without_replacement']is True,'Actual complete native hit list changed')
    require(finite(query['query_ms'])and query['query_ms']>=0,'Native query timing invalid')
    for hit in query['raw_hits']:
        index=int(hit['id']);require(type(hit['id'])is str and str(index)==hit['id']and 0<=index<len(units),
                'Native hit outside source index')
        require(finite(hit['score'])and {'id','score','vector'}<=set(hit['raw_keys'])and 'metadata'not in hit['raw_keys'],
                'Original native hit fields lost/nonfinite')
        require(hit['vector_receipt']=={'source_vector_index':index,'dimensions':384,'dtype':'float32le',
            'sha256':digests[index],'source_sha256':digests[index],'source_equal_before_stripping':True},
            'Native/source f32 bits mismatch')
        require(hit['metadata_receipt']=={'present':False,'canonical_json':ABSENT,'sha256':digest(ABSENT.encode()),
            'source_equal_before_stripping':True},'Native metadata absence receipt mismatch')
    return len(query['raw_hits'])

def audit_evidence(root,raw,bank,role,plan):
    phase='engineering';require(bank['epoch']==36 and bank['role']==role,'Wrong authored role bank')
    require(set(bank)=={'schema_version','epoch','role','records'}and bank['schema_version']==1 and role=='engineering','Only exact unlabeled authored engineering bank permitted')
    for row in bank['records']:
        require(set(row)=={'id','document_id','hypothesis_id','document','hypothesis','input_sha256'},'Input bank contains oracle/foreign fields')
        for key,cap in [('document',1000000),('hypothesis',8192)]:
            require(type(row[key])is str and row[key].strip()and '\0'not in row[key]and len(row[key])<=cap,'Invalid original supplied source/hypothesis');row[key].encode('utf-8',errors='strict')
        require(digest(canonical({k:row[k]for k in ['document','hypothesis']}).encode())==row['input_sha256'],'Independent source input SHA differs')
    require(raw['role']==role and raw['input_bank']['path']==plan['engineering_inputs_path']and raw['input_bank']['sha256']==plan['engineering_inputs_sha256']
        and raw['input_bank']=={**identity(root/plan['engineering_inputs_path']),'path':plan['engineering_inputs_path']},'Actual input receipt differs from frozen bank')
    cases,records=raw['cases'],bank['records'];triples=lambda rr:[(r['id'],r['document_id'],r['hypothesis_id'])for r in rr]
    require(triples(cases)==triples(records)==expected('engineering'),'Exact fixed nine engineering identities/order required')
    bundle=read(checked(root,raw['vector_bundle']));native=read(checked(root,raw['native_result']))
    require(bundle['schema_version']==3 and bundle['epoch']==36 and bundle['kind']==KIND and bundle['phase']==phase and bundle['role']==role
        and bundle['vector_encoding']=='base64_float32le_c_order'and bundle['metadata_policy']=='insert id and vector only; metadata absent','Wrong shared native bundle scope')
    require(native['epoch']==36 and native['phase']==phase and native['role']==role and native['kind']==KIND and native['native']is True
        and native['bundle_sha256']==raw['vector_bundle']['sha256']and native['errors']==[]and native['compact_schema']=='epoch36-native-context-f32le-v1','Actual native result incomplete')
    require(native['package_version']=='0.1.33'and native['platform_package_version']=='0.1.31'and native['binary_version']=='2.3.0'
        and native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','Wrong original native binary/version')
    require(native['source_sha256']==identity(root/plan['native_worker_path'])['sha256']and native['stage']=='HELPER_COMPLETED','Complete exact-source final native receipt required')
    dids=list(dict.fromkeys(str(r['document_id'])for r in records));require(len(dids)==9,'Nine distinct source documents required')
    require([d['document_id']for d in bundle['documents']]==[d['document_id']for d in native['documents']]==dids,'Exact native role documents required')
    prep=raw['documents'];require(set(prep)==set(dids),'Shared source preparation set changed')
    bankmap={r['id']:r for r in records};casemap={r['id']:r for r in cases};vectors=hits=queries_seen=0;group_rows=[];coverage_rows=[]
    for matrix,observed in zip(bundle['documents'],native['documents']):
        did=matrix['document_id'];source=next(r['document']for r in records if str(r['document_id'])==did)
        preparation=prep[did];units=preparation['units'];catalogue=source_groups(source,units)
        require(preparation['partition_model_tag']=='b354','Shared native partition must explicitly identify original b354 tokenizer')
        preludes=preparation['preludes_by_model'];require(set(preludes)=={'b354','xxlarge'}and preparation['prelude']==preludes['b354'],'Both source-bound prelude receipts required')
        for prelude in preludes.values():prelude_check(source,units,catalogue,prelude)
        chunks=[source[u['start']:u['end']]for u in units];digests=block_digests(matrix['vectors']);vectors+=len(digests)
        require(len(digests)==len(units)==observed['initialized_vectors'],'Native/source vector unit count differs')
        qids=[r['id']for r in records if str(r['document_id'])==did];query_digests=block_digests(matrix['query_vectors']);query_ids=[q+'::retrieval:original'for q in qids]
        require(len(query_digests)==len(qids)and matrix['queries']==[{'id':q}for q in query_ids]and[q['case_id']for q in observed['queries']]==query_ids,'One original native query per case required')
        require(set(preparation['retrieval_queries'])==set(qids),'Query preparation identity set changed');text_queries=[]
        for q in qids:
            case,inp=casemap[q],bankmap[q];require(case['retrieval_query']==preparation['retrieval_queries'][q],'Shared original query receipt differs')
            replay=query_check(root,plan,inp['hypothesis'],case['retrieval_query']);text_queries.append(PREFIX+replay['query'])
        emb=preparation['embedding'];require(emb['source_sha256s']==[digest(c.encode())for c in chunks]and emb['exact_query_texts']==text_queries,'BGE original source/query text differs')
        for j,q in enumerate(qids):
            case,inp=casemap[q],bankmap[q];query=observed['queries'][j];expected_native=dict(query,document_id=did,initialization_ms=observed['initialization_ms'],initialized_vectors=observed['initialized_vectors'])
            require(case['native']==expected_native,'All six arms must share original actual native result')
            hits+=native_query_check(query,digests,units);queries_seen+=1
            require(set(query['ids'])==set(range(len(units)))and len(query['ids'])==len(units),'Full-source admission requires every actual native unit, not a retrieval-absence inference')
            require(case['native_complete_unique_unitset_verified']is True
                and case['document_preparation_ref']==did and case['input_sha256']==inp['input_sha256']and case['document']==inp['document']
                and case['document_sha256']==digest(inp['document'].encode())and case['hypothesis']==inp['hypothesis']and case['hypothesis_sha256']==digest(inp['hypothesis'].encode()),'Case original source literal identity changed')
            k=min(40,len(units));words=[set(re.findall(r'\w+',c.casefold()))for c in chunks];qw=set(re.findall(r'\w+',inp['hypothesis'].casefold()))
            scores=[len(qw&w)/max(1,len(qw|w))for w in words];lexical=sorted(range(len(units)),key=lambda i:(-scores[i],i));require(case['lexical_jaccard_scores']==scores,'Original-hypothesis Jaccard ranking changed')
            rankings={name:query['ids']for name in ARMS};rankings['xxlarge_lexical_two']=lexical[:40];rankings['xxlarge_positional_two']=list(range(k))
            require(set(case['arms'])==set(ARMS),'Six fixed arms required')
            for name in ARMS:
                arm=case['arms'][name];context=arm['context'];tag=model_for_arm(name);require(arm['model_tag']==tag,'Arm model profile changed')
                seconds=query['query_ms']/1000 if name.endswith(('_full_source','_native_two'))else None
                require(arm['native_query_seconds']==seconds,'Shared native query timing attribution differs')
                require(arm['observed_ranking']==context['ranking_ids_considered']==rankings[name],'Fixed control/admission ranking differs')
                if name.endswith('_full_source'):
                    observation=full_context_check(source,inp['hypothesis'],units,catalogue,query,arm)
                    spans=[[0,len(source)]]
                else:
                    observation=context_check(source,units,catalogue,rankings[name],context,preludes[tag]);selected=context['selected_chunk_ids_source_order']
                    require(selected==sorted(set(selected))and all(type(i)is int and 0<=i<len(units)for i in selected),'Selected source units invalid')
                    spans=[]
                    for i in selected:
                        a,b=units[i]['start'],units[i]['end']
                        if spans and a==spans[-1][1]:spans[-1][1]=b
                        else:spans.append([a,b])
                    premise='\n\n'.join(source[a:b]for a,b in spans)
                    require(context['selected_source_spans']==spans and arm['premise']==premise and context['premise_sha256']==digest(premise.encode())and context['hypothesis_sha256']==digest(inp['hypothesis'].encode()),'Exact two-group context reconstruction failed')
                    numeric_check(source,spans,context)
                require(context['selected_evidence_truncated']is False and context['claim_truncated']is False and arm['semantic_decision_override']is False
                    and 0<arm['joint_pair_tokens']==context['joint_pair_tokens']<=512,'Source clipping/claim rewrite or pair budget changed')
                group_rows.append({'id':q,'arm':name,'model_tag':tag,**observation})
            a,b=case['arms']['xxlarge_full_source'],case['arms']['b354_full_source']
            require(a['premise']==b['premise']==source and a['context']['selected_source_spans']==b['context']['selected_source_spans']==[[0,len(source)]],'Cross-model full-source premises differ')
            a,b=case['arms']['xxlarge_native_two'],case['arms']['b354_native_two']
            require(a['premise']==b['premise']and a['context']['selected_source_spans']==b['context']['selected_source_spans'],'Cross-model native-two context changed')
            coverage_rows.append({'id':q,'actual_native_unique_unitset_complete':True,'unit_ids':query['ids'],'source_units':len(units),'query_vector_sha256':query_digests[j]})
    counters={'native_index_initializations_attempted':len(dids),'native_index_initializations_completed':len(dids),'native_queries_attempted':queries_seen,'native_queries_completed':queries_seen,'native_len_calls_attempted':2*len(dids),'native_len_calls_completed':2*len(dids),'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_insertions_attempted':vectors,'native_insertions_completed':vectors,'native_hit_source_validations':hits}
    require(all(type(native.get(k))is int and native[k]==v for k,v in counters.items()),'Native final counter totals do not close to actual source/vector/query records')
    return {'status':'PASS_PAIRED_READERS_EXACT_FULL_SOURCE_TWO_GROUP_AND_NATIVE_F32_REPLAY','documents':len(dids),'cases':len(records),'role':role,
        'source_index_vectors':vectors,'source_query_vectors':queries_seen,'native_hits_verified':hits,'original_unchanged_query_cases':queries_seen,'query_expansions':0,
        'complete_native_unitsets':coverage_rows,'group_context_observations':group_rows,'native_final_counters_replayed':counters,
        'source_choices_or_evidence_labels_read':0,'model_tokenizer_native_calls':0,
        'scope':'Actual native is shared provenance/coverage admission for full-source arms; ranking affects two-group controls. Exact source bytes/groups/selection and native float32 records are independently replayed without candidate/tokenizer/model imports. Token counts remain actual source-bound worker observations. No benchmark/generalization or causal native-selection gain for the full-source primary.'}
