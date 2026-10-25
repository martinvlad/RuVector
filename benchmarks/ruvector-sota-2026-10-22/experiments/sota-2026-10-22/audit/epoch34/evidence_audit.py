"""Independent exact-source context and actual native f32 receipt replay."""
import base64
import math
import re
import struct
from data_common import require,identity,digest,expected,TRAIN_IDS,DEV_IDS,HYPOTHESES,finite
from phase_audit import checked,read,KIND
from query_audit import query_check,hybrid_check
from group_audit import source_groups,prelude_check,context_check

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
    phase='dev';require(bank['epoch']==34 and bank['role']==role,'Wrong role bank')
    require(raw['role']==role and raw['input_bank']['path']==plan[role+'_inputs_path']
            and raw['input_bank']['sha256']==plan[role+'_inputs_sha256']
            and raw['input_bank']=={**identity(root/plan[role+'_inputs_path']),'path':plan[role+'_inputs_path']},
            'Actual role input receipt differs from frozen bank')
    cases,records=raw['cases'],bank['records'];triples=lambda rows:[(r['id'],r['document_id'],r['hypothesis_id'])for r in rows]
    expected_rows=expected('dev')if role=='dev'else[(f'epoch32:cc0:engineering:{i}',-32000-i,f'eng-{i}')for i in range(1,7)]
    require(triples(cases)==triples(records)==expected_rows,'Exact fixed source role case identities/order required')
    bundle=read(checked(root,raw['vector_bundle']));native=read(checked(root,raw['native_result']))
    require(bundle['schema_version']==3 and bundle['epoch']==34 and bundle['kind']==KIND and bundle['phase']==phase and bundle['role']==role
            and bundle['vector_encoding']=='base64_float32le_c_order'and bundle['metadata_policy']=='insert id and vector only; metadata absent','Wrong actual bundle scope')
    require(native['epoch']==34 and native['phase']==phase and native['role']==role and native['kind']==KIND and native['native']is True
            and native['bundle_sha256']==raw['vector_bundle']['sha256']and native['errors']==[]
            and native['compact_schema']=='epoch34-native-context-f32le-v1','Actual native artifact incomplete')
    require(native['package_version']=='0.1.33'and native['platform_package_version']=='0.1.31'and native['binary_version']=='2.3.0'
            and native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','Wrong actual original native binary/version')
    require(native['source_sha256']==identity(root/plan['native_worker_path'])['sha256']and native['stage']=='HELPER_COMPLETED',
            'Complete source-bound final native receipt required')
    dids=list(dict.fromkeys(str(r['document_id'])for r in records))
    require([d['document_id']for d in bundle['documents']]==[d['document_id']for d in native['documents']]==dids,'Exact native role documents required')
    prep=raw['documents'];require(set(prep)==set(dids),'Source preparation document set changed')
    bankmap={r['id']:r for r in records};casemap={r['id']:r for r in cases};vectors=hits=queries_seen=0;hybrid_rows=[];group_rows=[]
    for matrix,observed in zip(bundle['documents'],native['documents']):
        did=matrix['document_id'];source=next(r['document']for r in records if str(r['document_id'])==did)
        preparation=prep[did];units=preparation['units'];catalogue=source_groups(source,units)
        prelude_check(source,units,catalogue,preparation['prelude'])
        chunks=[source[u['start']:u['end']]for u in units];digests=block_digests(matrix['vectors']);vectors+=len(digests)
        require(len(digests)==len(units)==observed['initialized_vectors'],'Native/source vector-unit count mismatch')
        qids=[r['id']for r in records if str(r['document_id'])==did];query_digests=block_digests(matrix['query_vectors'])
        query_ids=[q+'::retrieval:original'for q in qids]
        require(len(query_digests)==len(qids)and matrix['queries']==[{'id':q}for q in query_ids]
                and[q['case_id']for q in observed['queries']]==query_ids,'One original native query per case required')
        require(set(preparation['retrieval_queries'])==set(qids),'Query preparation case set changed')
        text_queries=[]
        for q in qids:
            case,inp=casemap[q],bankmap[q]
            require(case['retrieval_query']==preparation['retrieval_queries'][q],'Case/preparation query receipt differs')
            replay=query_check(root,plan,inp['hypothesis'],case['retrieval_query']);text_queries.append(PREFIX+replay['query'])
        emb=preparation['embedding'];require(emb['source_sha256s']==[digest(c.encode())for c in chunks]and emb['exact_query_texts']==text_queries,
            'BGE exact source/original hypothesis query input differs')
        for j,q in enumerate(qids):
            case,inp=casemap[q],bankmap[q];query=observed['queries'][j]
            expected_native=dict(query,document_id=did,initialization_ms=observed['initialization_ms'],initialized_vectors=observed['initialized_vectors'])
            require(case['native']==case['native_original']==expected_native,'Hybrid/native-only must reuse the same original native result')
            hits+=native_query_check(query,digests,units);queries_seen+=1
            require(case['document_preparation_ref']==did and case['input_sha256']==inp['input_sha256']and case['document']==inp['document']
                    and case['document_sha256']==digest(inp['document'].encode())and case['hypothesis']==inp['hypothesis']
                    and case['hypothesis_sha256']==digest(inp['hypothesis'].encode()),'Case/source literal identity mismatch')
            k=min(40,len(units));words=[set(re.findall(r'\w+',c.casefold()))for c in chunks];qw=set(re.findall(r'\w+',inp['hypothesis'].casefold()))
            scores=[len(qw&w)/max(1,len(qw|w))for w in words];lexical=sorted(range(len(units)),key=lambda i:(-scores[i],i))
            require(case['lexical_jaccard_scores']==scores,'Original-hypothesis lexical Jaccard changed')
            hybrid,hybrid_receipt=hybrid_check(lexical,query['ids'],units,case['hybrid_selection'])
            hybrid_rows.append({'id':q,'original_query_vector_sha256':query_digests[j],**hybrid_receipt,
                'hybrid_ranking_differs_native_only':hybrid!=query['ids'],'hybrid_ranking_differs_lexical_only':hybrid!=lexical[:40]})
            rankings={'actual_native':hybrid,'native_original':query['ids'],'lexical':lexical[:40],'positional':list(range(k))}
            require(set(case['arms'])==set(rankings),'Fixed four matched arms missing')
            for name,ranking in rankings.items():
                arm=case['arms'][name];context=arm['context'];selected=context['selected_chunk_ids_source_order']
                seconds=query['query_ms']/1000 if name in('actual_native','native_original')else None
                require(arm['native_query_seconds']==seconds,'Shared original query timing attribution differs')
                require(arm['observed_ranking']==context['ranking_ids_considered']==ranking,'Arm evidence ranking differs')
                group_observation=context_check(source,units,catalogue,ranking,context,preparation['prelude'])
                group_rows.append({'id':q,'arm':name,**group_observation})
                require(selected==sorted(set(selected))and all(type(i)is int and 0<=i<len(units)for i in selected),'Selected source units invalid')
                spans=[]
                for i in selected:
                    start,end=units[i]['start'],units[i]['end']
                    if spans and start==spans[-1][1]:spans[-1][1]=end
                    else:spans.append([start,end])
                premise='\n\n'.join(source[a:b]for a,b in spans)
                require(context['selected_source_spans']==spans and arm['premise']==premise and context['premise_sha256']==digest(premise.encode())
                        and context['hypothesis_sha256']==digest(inp['hypothesis'].encode()),'Exact source context reconstruction failed')
                provenance=[{'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode())}for a,b in spans]
                require(context['source_provenance']['selected_source_provenance']==provenance,'Exact UTF8 source offsets changed')
                literals=[]
                for match in NUMBER.finditer(source):
                    a,b=match.start(),match.end();literals.append({'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode()),'retained':any(x<=a and b<=y for x,y in spans),'lexical_year_candidate':bool(re.fullmatch(r'\d{4}',match.group())and 1000<=int(match.group())<=2999)})
                numeric=context['source_provenance'];require(numeric['numeric_literals']==literals and numeric['numeric_literal_pattern']==NUMBER.pattern
                    and numeric['numeric_literals_retained']==sum(r['retained']for r in literals)and numeric['numeric_literals_omitted']==sum(not r['retained']for r in literals)
                    and numeric['source_text_normalized']is False and numeric['semantic_decision_override']is False,'Literal numeric/year source provenance differs')
                require(context['selected_evidence_truncated']is False and context['claim_truncated']is False and arm['semantic_decision_override']is False
                        and 0<arm['joint_pair_tokens']==context['joint_pair_tokens']<=512,'Source clipping/claim mutation/true pair cap changed')
    counters={'native_index_initializations_attempted':len(dids),'native_index_initializations_completed':len(dids),'native_queries_attempted':queries_seen,'native_queries_completed':queries_seen,'native_len_calls_attempted':2*len(dids),'native_len_calls_completed':2*len(dids),'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_insertions_attempted':vectors,'native_insertions_completed':vectors,'native_hit_source_validations':hits}
    require(all(type(native.get(k))is int and native[k]==v for k,v in counters.items()),'Actual final native API counter totals do not close to source/vector/query/hit records')
    return {'status':'PASS_FIXED_HYBRID_EXACT_SOURCE_GROUPS_AND_NATIVE_F32_REPLAY','documents':len(dids),'cases':len(records),'role':role,
            'source_index_vectors':vectors,'source_query_vectors':queries_seen,'native_hits_verified':hits,'original_unchanged_query_cases':queries_seen,
            'query_expansions':0,'hybrid_selection_observations':hybrid_rows,'group_context_observations':group_rows,
            'native_final_counters_replayed':counters,'raw_to_metric_arms':{'actual_native':'native','native_original':'native_original','lexical':'lexical','positional':'positional'},
            'source_choices_or_evidence_labels_read':0,'model_tokenizer_native_calls':0,
            'context_token_scope':'Recorded true-token observations and readout receipt bounds; auditor replays exact source grouping/selection without tokenizer or NLI execution. Coverage is descriptive, never sufficient evidence/absence proof.'}
