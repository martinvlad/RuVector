"""Independent exact-source context and actual native f32 receipt replay."""
import base64
import math
import re
import struct
from data_common import require,identity,digest,expected,TRAIN_IDS,DEV_IDS,HYPOTHESES,finite
from phase_audit import checked,read,KIND
from query_audit import query_check

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
    require(query['requested_k']==len(query['ids'])==len(query['raw_hits'])==k
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
    phase="dev"
    require(bank['epoch']==33 and bank['role']==role,'Wrong role bank')
    require(raw['role']==role and raw['input_bank']['path']==plan[role+'_inputs_path']
            and raw['input_bank']['sha256']==plan[role+'_inputs_sha256']
            and raw['input_bank']=={**identity(root/plan[role+'_inputs_path']),'path':plan[role+'_inputs_path']},
            'Actual role input receipt differs from frozen bank')
    cases=raw['cases'];records=bank['records']
    triples=lambda rows:[(r['id'],r['document_id'],r['hypothesis_id'])for r in rows]
    expected_rows=expected('dev') if role=='dev' else [(f'epoch32:cc0:engineering:{i}',-32000-i,f'eng-{i}')for i in range(1,7)]
    require(triples(cases)==triples(records)==expected_rows,'Exact source role case identities/order required')
    bundle=read(checked(root,raw['vector_bundle']));native=read(checked(root,raw['native_result']))
    require(bundle['schema_version']==3 and bundle['epoch']==33 and bundle['kind']==KIND and bundle['phase']==phase and bundle['role']==role
            and bundle['vector_encoding']=='base64_float32le_c_order'
            and bundle['metadata_policy']=='insert id and vector only; metadata absent','Wrong actual bundle scope')
    require(native['epoch']==33 and native['phase']==phase and native['role']==role and native['kind']==KIND and native['native']is True
            and native['bundle_sha256']==raw['vector_bundle']['sha256']and native['errors']==[]
            and native['compact_schema']=='epoch33-native-context-f32le-v1','Actual native artifact incomplete')
    require(native['package_version']=='0.1.33'and native['platform_package_version']=='0.1.31'
            and native['binary_version']=='2.3.0'
            and native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e',
            'Wrong original actual native binary/version')
    require(native['source_sha256']==identity(root/plan['native_worker_path'])['sha256'],'Native helper source changed')
    require(native['stage']=='HELPER_COMPLETED','A complete source-bound final native receipt is required')
    dids=list(dict.fromkeys(str(r['document_id'])for r in records))
    require([d['document_id']for d in bundle['documents']]==[d['document_id']for d in native['documents']]==dids,
            'Exact role native document identities required')
    prep=raw['documents'];require(set(prep)==set(dids),'Source preparation document set changed')
    bankmap={r['id']:r for r in records};casemap={r['id']:r for r in cases};vectors=hits=queries_seen=query_expansions=0;families={};query_pairs=[]
    for matrix,observed in zip(bundle['documents'],native['documents']):
        did=matrix['document_id'];source=next(r['document']for r in records if str(r['document_id'])==did)
        preparation=prep[did];units=preparation['units'];cursor=0
        for i,u in enumerate(units):
            require(u['id']==i and u['start']==cursor and type(u['end'])is int and cursor<u['end']<=len(source),
                    'Source unit partition has gap/overlap/tail clipping')
            cursor=u['end']
        require(cursor==len(source)and 0<len(units)<=192,'Complete bounded source partition required')
        chunks=[source[u['start']:u['end']]for u in units];digests=block_digests(matrix['vectors']);vectors+=len(digests)
        require(len(digests)==len(units)==observed['initialized_vectors'],'Actual native vector/source unit count mismatch')
        qids=[r['id']for r in records if str(r['document_id'])==did]
        query_digests=block_digests(matrix['query_vectors'])
        query_ids=[q+'::retrieval:'+v for q in qids for v in('original','expanded')]
        require(len(query_digests)==2*len(qids),'Two genuine native query vectors per case required')
        require(matrix['queries']==[{'id':q}for q in query_ids]
                and[q['case_id']for q in observed['queries']]==query_ids,'Original/expanded query identities/order changed')
        require(set(preparation['retrieval_queries'])==set(qids),'Query preparation case set changed')
        expanded={};text_queries=[]
        for q in qids:
            case=casemap[q];inp=bankmap[q]
            require(case['retrieval_query']==preparation['retrieval_queries'][q],'Case/preparation query receipt differs')
            expanded[q]=query_check(root,plan,inp['hypothesis'],case['retrieval_query'])
            text_queries.extend(PREFIX+expanded[q][v]for v in('original','expanded'))
            query_expansions+=int(expanded[q]['expansion_applied'])
            family=expanded[q]['recognized_predicate'];families[str(family)]=families.get(str(family),0)+1
        emb=preparation['embedding'];require(emb['source_sha256s']==[digest(c.encode())for c in chunks]
            and emb['exact_query_texts']==text_queries,'BGE literal original/expanded query input changed')
        for j,q in enumerate(qids):
            case=casemap[q];inp=bankmap[q]
            original_query,query=observed['queries'][2*j:2*j+2]
            require(case['native']==dict(query,document_id=did,initialization_ms=observed['initialization_ms'],
                        initialized_vectors=observed['initialized_vectors'])
                    and case['native_original']==dict(original_query,document_id=did,
                        initialization_ms=observed['initialization_ms'],initialized_vectors=observed['initialized_vectors']),
                    'Per-case expanded/original native ordered result changed')
            query_pairs.append({'id':q,'expansion_applied':expanded[q]['expansion_applied'],
                'original_query_vector_sha256':query_digests[2*j],
                'expanded_query_vector_sha256':query_digests[2*j+1],
                'query_vectors_equal':query_digests[2*j]==query_digests[2*j+1],
                'native_order_changed':original_query['ids']!=query['ids']})
            hits+=native_query_check(original_query,digests,units)+native_query_check(query,digests,units)
            queries_seen+=2
            require(case['document_preparation_ref']==did and case['input_sha256']==inp['input_sha256']
                    and case['document']==inp['document']
                    and case['document_sha256']==digest(inp['document'].encode())
                    and case['hypothesis']==inp['hypothesis']and case['hypothesis_sha256']==digest(inp['hypothesis'].encode()),
                    'Case/source literal identity mismatch')
            k=min(40,len(units))
            words=[set(re.findall(r'\w+',c.casefold()))for c in chunks];query_words=set(re.findall(r'\w+',expanded[case['id']]['expanded'].casefold()))
            scores=[len(query_words&w)/max(1,len(query_words|w))for w in words];lex=sorted(range(len(units)),key=lambda i:(-scores[i],i))[:40]
            require(case['lexical_jaccard_scores']==scores,'Matched lexical scores changed')
            rankings={'actual_native':query['ids'],'native_original':original_query['ids'],'lexical':lex,'positional':list(range(k))}
            arms=['actual_native','native_original','lexical','positional']
            require(set(case['arms'])==set(arms),'Fixed matched arms missing')
            for name in arms:
                arm=case['arms'][name];context=arm['context'];selected=context['selected_chunk_ids_source_order']
                expected_seconds=(query if name=='actual_native'else original_query)['query_ms']/1000 if name in('actual_native','native_original')else None
                require(arm['native_query_seconds']==expected_seconds,'Arm native query timing/control attribution differs')
                require(arm['observed_ranking']==context['ranking_ids_considered']==rankings[name], 'Context selector/rank changed')
                require(selected==sorted(set(selected))and all(type(i)is int and 0<=i<len(units)for i in selected),'Selected units invalid')
                spans=[]
                for i in selected:
                    start,end=units[i]['start'],units[i]['end']
                    if spans and start==spans[-1][1]:spans[-1][1]=end
                    else:spans.append([start,end])
                premise='\n\n'.join(source[a:b]for a,b in spans)
                require(context['selected_source_spans']==spans and arm['premise']==premise
                    and context['premise_sha256']==digest(premise.encode())
                    and context['hypothesis_sha256']==digest(inp['hypothesis'].encode()),'Exact source context reconstruction failed')
                provenance=[{'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),
                    'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode())}for a,b in spans]
                require(context['source_provenance']['selected_source_provenance']==provenance,'Source UTF8 offsets changed')
                literals=[]
                for match in NUMBER.finditer(source):
                    a,b=match.start(),match.end()
                    literals.append({'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),
                        'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode()),
                        'retained':any(x<=a and b<=y for x,y in spans),
                        'lexical_year_candidate':bool(re.fullmatch(r'\d{4}',match.group())and 1000<=int(match.group())<=2999)})
                numeric=context['source_provenance']
                require(numeric['numeric_literals']==literals and numeric['numeric_literal_pattern']==NUMBER.pattern
                        and numeric['numeric_literals_retained']==sum(r['retained']for r in literals)
                        and numeric['numeric_literals_omitted']==sum(not r['retained']for r in literals)
                        and numeric['source_text_normalized']is False,'Literal numeric/year source provenance changed')
                require(context['selected_evidence_truncated']is False and context['claim_truncated']is False
                    and type(arm['semantic_decision_override'])is bool
                    and context['source_provenance']['semantic_decision_override']is False,
                    'Source clipping or context semantic mutation')
                require(0<arm['joint_pair_tokens']==context['joint_pair_tokens']<=512,'True pair budget changed')
    expected_counters={'native_index_initializations_attempted':len(dids),'native_index_initializations_completed':len(dids),
        'native_queries_attempted':queries_seen,'native_queries_completed':queries_seen,
        'native_len_calls_attempted':2*len(dids),'native_len_calls_completed':2*len(dids),
        'native_version_calls_attempted':1,'native_version_calls_completed':1,
        'native_insertions_attempted':vectors,'native_insertions_completed':vectors,'native_hit_source_validations':hits}
    require(all(type(native.get(k))is int and native[k]==v for k,v in expected_counters.items()),
            'Independent actual final native API counter totals do not close to captured source/vector/query/hit records')
    return {'status':'PASS_EXACT_SOURCE_MATCHED_CONTEXT_AND_NATIVE_F32_REPLAY','documents':len(dids),'cases':len(records),'role':role,
            'source_index_vectors':vectors,'source_query_vectors':queries_seen,'native_hits_verified':hits,
            'typed_query_expansion_cases':query_expansions,'typed_query_predicate_counts':families,
            'query_pair_observations':query_pairs,
            'same_text_query_vector_differences':sum(not row['expansion_applied']and not row['query_vectors_equal']for row in query_pairs),
            'native_final_counters_replayed':expected_counters,
            'raw_to_metric_arms':{'actual_native':'native','native_original':'native_original','lexical':'lexical','positional':'positional'},
            'source_choices_or_evidence_labels_read':0,'model_tokenizer_native_calls':0}
