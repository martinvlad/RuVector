"""Independent native/context/resource/feed-proof checks; stdlib only."""
from common import *
from model_checks import forward_replay
from sentence_checks import catalog as sentence_catalog, exact as context_exact
from sentence_checks import POLICY, QUALIFIER, BULLET, token_proof_replay as context_token_proof_replay

def reference(vectors, queries):
    demand(type(vectors) is list and vectors and type(queries) is list and len(queries) == 3, 'complete source vectors and three query vectors required')
    for v in vectors+queries:
        demand(type(v) is list and len(v) == 384 and all(type(x) in (int,float) and math.isfinite(x) for x in v), 'finite actual384-dimensional vectors required')
        demand(math.fsum(x*x for x in v) > 0, 'zero vector has no cosine reference')
    out = []
    for q in queries:
        qn = math.sqrt(math.fsum(x*x for x in q))
        scores = [math.fsum(x*y for x,y in zip(v,q))/(math.sqrt(math.fsum(x*x for x in v))*qn) for v in vectors]
        out.append({'cosine_similarities':scores,'full_cosine_order':sorted(range(len(vectors)),key=lambda i:(-scores[i],i))})
    return out


def native_replay(trace, vectors, queries):
    demand(trace['bundle'] == {'vectors':vectors,'query_vectors':queries}, 'native bundle does not contain the supplied source vectors')
    bundle_bytes = (json.dumps(trace['bundle'],ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    demand(trace['bundle_sha256'] == digest(bundle_bytes), 'actual native bundle byte hash mismatch')
    actual = trace['raw_native_output']; depth = min(40,len(vectors))
    demand(actual['native'] is True and actual['native_binary_sha256'] == BINARY_SHA and actual['package_version'] == '0.1.33', 'actual pinned native RuVector backend required')
    demand(integer(actual['vectors'],1) == len(vectors) and actual['bundle_sha256'] == trace['bundle_sha256'], 'native insertion/bundle count mismatch')
    demand(integer(trace['initial_length']) == 0 and integer(trace['final_length'],1) == len(vectors) and trace['source_script_sha256'] == NATIVE_SCRIPT_SHA, 'native isolated index/source closure changed')
    demand(integer(trace['helper_exit_code']) == 0 and trace['helper_exited'] is True and integer(trace['candidate_depth'],1) == depth, 'actual native helper must exit successfully')
    demand(integer(trace['native_helper_pid'],1) > 0 and integer(trace['native_helper_pgid'],1) > 0, 'actual native process IDs required')
    demand(trace['native_order_used_without_replacement'] is True and trace['raw_scores_available'] is False, 'observed native ranking must not be replaced by reference')
    expected = reference(vectors,queries); demand(len(trace['reference']) == len(actual['queries']) == 3, 'three native queries/reference rows required')
    agreements, times = [], []
    for row, saved, ref in zip(actual['queries'],trace['reference'],expected):
        demand(type(row['ids']) is list and len(row['ids']) == depth and len(set(row['ids'])) == depth
               and all(type(x) is int and 0 <= x < len(vectors) for x in row['ids']), 'native candidate IDs invalid')
        demand(type(saved['full_cosine_order'])is list and all(type(x)is int for x in saved['full_cosine_order']) and saved['full_cosine_order'] == ref['full_cosine_order'] and len(saved['cosine_similarities']) == len(vectors)
               and all(abs(M.real(x)-y) <= 1e-10 for x,y in zip(saved['cosine_similarities'],ref['cosine_similarities'])), 'independent saved-vector cosine reference mismatch')
        agreements.append(row['ids'] == ref['full_cosine_order'][:depth]); times.append(duration(row['latency_ms']))
    return {'queries':3,'native_order_matches_saved_vector_reference':agreements,'latency_ms':times,
            'scope':'Agreement is reported, not used to substitute reference rankings or prove semantic retrieval efficacy.'}


def engineering_replay(raw,protocol,state_sha,instance):
    fixtures=protocol['engineering']['fixtures']; forwards=raw['canary_forwards']
    demand(type(forwards) is list and len(forwards)==3, 'exact three already-exposed engineering canary forwards required')
    timings=[]; correct=0
    for row,fixture in zip(forwards,fixtures):
        demand(row['fixture_id']==fixture['id'] and row['expected_typed_label']==fixture['expected_typed_label'], 'engineering fixture identity changed')
        timings.append(forward_replay(row['forward'],fixture['premise'],fixture['hypothesis'],state_sha,instance))
        correct+=int(row['forward']['typed_prediction']==fixture['expected_typed_label'])
    vocab=('lamp','on','not','box','blue')
    def vector(text):
        c=Counter(re.findall('[a-z]+',text.lower()));return[c[x]for x in vocab]+[0]*379
    trace=raw['engineering_native_trace'];demand(trace['native_selection_affects_NLI']is False,'engineering native retrieval must not change literal NLI pairs')
    native=native_replay(trace,[vector(f['premise'])for f in fixtures],[vector(f['hypothesis'])for f in fixtures])
    ready=raw['semantic_readiness'];demand(integer(ready['correct'])==correct and integer(ready['n'])==3 and ready['passed']is(correct==3),'semantic readiness decision inconsistent')
    demand(ready['plan_sha256']==raw['plan_sha256'] and ready['phase']==raw['phase']
           and ready['canary_forward_receipt_sha256']==digest(canonical(forwards))
           and ready['fp32_state_sha256']==state_sha and ready['tokenizer_backend_sha256']==raw['tokenizer']['backend_sha256'],'actual readiness process/source/feed identity inconsistent')
    demand(raw['FP32_state_after_canaries_sha256']==state_sha,'reader state changed during semantic qualification')
    demand(raw['tokenizer_backend_after_canaries_sha256']==raw['tokenizer']['backend_sha256'], 'tokenizer backend changed during semantic qualification')
    return {'correct':correct,'n':3,'passed':correct==3,'predictions':[r['forward']['typed_prediction']for r in forwards],
            'latency_seconds':timings,'native':native,'scope':'Exposed engineering canaries only; not a benchmark score.'}


def coverage_replay(state,units,hypothesis,arm,ranking):
    c=arm['coverage']; selected=c['selected_chunk_ids_source_order']
    demand(type(selected)is list and selected and selected==sorted(set(selected)) and all(type(i)is int and 0<=i<len(units)for i in selected),'source selected unit IDs invalid')
    spans=[]
    for i in selected:
        a,b=units[i]['start'],units[i]['end']
        if spans and spans[-1][1]==a:spans[-1][1]=b
        else:spans.append([a,b])
    premise='\n\n'.join(state[a:b]for a,b in spans)
    demand(arm['premise']==premise and c['selected_source_spans']==spans,'literal selected source coverage/premise mismatch')
    demand(c['premise_sha256']==digest(premise.encode())and c['hypothesis_sha256']==digest(hypothesis.encode()),'coverage text hash mismatch')
    demand(c['ranking_ids_considered']==ranking and c['ranked_anchor_candidate_cap']==min(40,len(units))and c['ranking_depth']==len(ranking),'saved exact selector ranking mismatch')
    demand(c['joint_pair_token_cap']==512 and type(c['joint_pair_tokens'])is int and c['joint_pair_tokens']==arm['forward']['actual_tokens']<=512,'complete final pair capacity mismatch')
    demand(c['selected_evidence_truncated']is False and c['claim_truncated']is False,'silent evidence/claim truncation forbidden')
    groups = sentence_catalog(state, units)
    context_exact(c['source_sentence_groups'], groups, 'complete exact source sentence/qualifier group catalog required')
    demand(c['policy'] == POLICY and c['qualifier_regex'] == QUALIFIER.pattern
           and c['bullet_regex'] == BULLET.pattern and c['all_selected_groups_complete'] is True,
           'frozen atomic source-group policy required')
    expected_order, anchors = [], {}
    for i in ranking:
        gid = units[i]['group_id']
        if gid not in anchors: expected_order.append(gid); anchors[gid] = i
    context_exact(c['group_ranking_ids'], expected_order, 'source groups must retain first observed member order')
    context_exact(c['group_ranking_anchor_unit_ids'], [anchors[g] for g in expected_order], 'source-group anchor IDs changed')
    selected_groups = c['selected_group_ids_admission_order']
    demand(type(selected_groups) is list and len(set(selected_groups)) == len(selected_groups)
           and all(type(g) is int and 0 <= g < len(groups) for g in selected_groups), 'unique literal selected groups required')
    context_exact(c['selected_chunk_ids_rank_order'], [i for g in selected_groups for i in groups[g]['unit_ids']],
                  'every selected source group must be atomic and retain exact admission order')
    context_exact(selected, sorted(c['selected_chunk_ids_rank_order']), 'complete source groups selected inconsistently')
    omitted=[i for i in range(len(units))if i not in selected]
    demand(c['omitted_chunk_ids']==omitted and c['omitted_source_spans']==[[units[i]['start'],units[i]['end']]for i in omitted],'omitted source coverage mismatch')
    numbers=[{'span':[m.start(),m.end()],'text':m.group(),'retained':any(a<=m.start()and m.end()<=b for a,b in spans)}for m in NUMBER.finditer(state)]
    demand(c['numeric_mentions']==numbers and c['numeric_mentions_retained']==sum(x['retained']for x in numbers)
           and c['numeric_mentions_omitted']==sum(not x['retained']for x in numbers),'mechanical numeric source coverage mismatch')
    covered=sum(b-a for a,b in spans)
    demand(c['retained_source_characters']==covered and c['document_characters']==len(state)and abs(M.real(c['document_character_coverage'])-covered/len(state))<=1e-10,'source character coverage mismatch')
    return {'premise_sha256':digest(premise.encode()),'selected_units':len(selected),'retained_source_characters':covered,'numeric_retained':sum(x['retained']for x in numbers),'numeric_omitted':sum(not x['retained']for x in numbers)}


def resources_replay(raw,execution,raw_path,phase,complete):
    demand(execution['schema_version']==1 and execution['epoch']==22 and execution['phase']==phase and execution['plan_sha256']==raw['plan_sha256'],'outer execution source identity mismatch')
    demand(integer(execution['worker_attempts'])==1 and integer(execution['verified_worker_starts'])==1 and integer(execution['worker_exit_code'])==0 and execution['error']is None,'one successful nonretryable owned worker required')
    demand(execution['raw_sha256']==identity(raw_path)['sha256'] and execution['observed_worker_status']==raw['status'],'outer sealed raw receipt identity mismatch')
    demand(execution['source_plan_unchanged']is True and execution['automatic_retry']is False
           and integer(execution['allowed_further_attempts_in_this_phase'])==0,'source/slot closure mismatch')
    demand(execution['status']=='COMPLETED_AWAITING_INDEPENDENT_REPLAY' and raw['finished_within_deadline']is True,'full process/cleanup deadline not met')
    demand(duration(execution['elapsed_seconds'])<=600 and duration(raw['wall_seconds_inside_worker'])<=duration(execution['elapsed_seconds'])+1,'CPU2/600-second process budget exceeded')
    ids=execution['CPU_affinity'];demand(type(ids)is list and len(ids)==2 and len(set(ids))==2 and all(type(x)is int and x>=0 for x in ids),'exact two-CPU affinity required')
    for k in ('user_seconds','system_seconds','peak_RSS_bytes'):duration(execution[k])
    demand(type(execution['peak_RSS_bytes'])is int and execution['peak_RSS_bytes']>0,'actual outer resource high-water required')
    demand(execution['benchmark_HTTP_requests']==0 and execution['new_paid_API_GPU_calls']==0,'unplanned HTTP/paid/GPU execution')
    cleanup=execution['cleanup']
    demand(all(cleanup[k]is True for k in ('worker_exited','all_native_helpers_exited','process_group_empty'))and cleanup['owned_live_pids']==[],'owned native/worker cleanup incomplete')
    demand(raw['cleanup']['all_native_helpers_reaped']is True,'worker native helper reap incomplete')
    demand(integer(execution['worker_pid'],1)==integer(execution['worker_pgid'],1),'isolated worker process group required')
    demand(integer(raw['semantic_readiness']['pid'],1)==execution['worker_pid'],'semantic readiness came from another process')
    helpers=execution['native_helper_pids'];expected_helpers=9 if complete else 1
    demand(type(helpers)is list and len(helpers)==expected_helpers and len(set(helpers))==expected_helpers and all(type(x)is int and x>0 for x in helpers),'exact actual native helper count required')
    for pid in [execution['worker_pid'],*helpers]:demand(not Path('/proc/'+str(pid)).exists(),'owned process still present at independent scoring')
    after=raw['resources']['after_runtime'];demand(after['allowed_CPU_ids']==ids,'actual worker affinity changed')
    for k in ('worker_cpu_user_seconds','worker_cpu_system_seconds','worker_peak_RSS_bytes','terminated_children_cpu_user_seconds','terminated_children_cpu_system_seconds','largest_terminated_child_peak_RSS_bytes'):duration(after[k])
    return {'outer':execution,'inside_worker':raw['resources'],'scope':'CPU counters and each process high-water are retained separately; no simultaneous RSS aggregate or primary-only deployment claim.'}


def counters_replay(raw,complete):
    c=raw['counters'];expected={'model_initializations_attempted':1,'model_initializations_completed':1,
      'checkpoint_metadata_loads_attempted':1,'checkpoint_metadata_loads_completed':1,
      'nli_forward_pairs_attempted':75 if complete else 3,'nli_forward_pairs_completed':75 if complete else 3,
      'native_index_initializations_attempted':9 if complete else 1,'native_index_initializations_completed':9 if complete else 1,
      'native_queries_attempted':27 if complete else 3,'native_queries_completed':27 if complete else 3,
      'BGE_initializations_attempted':1 if complete else 0,'BGE_initializations_completed':1 if complete else 0,
      'ORT_sessions_attempted':1 if complete else 0,'ORT_sessions_completed':1 if complete else 0,
      'quantization_initializations':0,'paid_API_calls':0,'GPU_calls':0,'native104_calls':0,'previous_reader_forwards':0,
      'training_calibration_fits':0,'benchmark_HTTP_requests':0,'benchmark_documents_completed':8 if complete else 0,'benchmark_questions_completed':24 if complete else 0}
    for k,v in expected.items():demand(type(c.get(k))is int and c[k]==v,'actual scientific count mismatch: '+k)
    for k in ('BGE_forwards','BGE_texts'):
        attempted,done=c[k+'_attempted'],c[k+'_completed']
        demand(type(attempted)is int and type(done)is int and attempted==done
               and (done>0 if complete else done==0),'actual BGE count mismatch: '+k)
    if complete:
        counts=[len(document['source_units'])for document in raw['documents']]
        demand(len(counts)==8 and all(n>0 for n in counts),'complete eight-document BGE source-unit inventory required')
        demand(c['BGE_texts_completed']==sum(counts)+24,'actual BGE text count must equal every source unit plus exactly24 prefixed claims')
        demand(c['BGE_forwards_completed']==sum((n+7)//8+1 for n in counts),'actual BGE forward count must equal exact batch8 source chunks plus one3-query batch each document')
    duration(c['BGE_forward_seconds'])


def tokenizer_report_replay(raw,raw_path,plan_sha,execution_path):
    path=member(PREFIX+'audit/epoch22/tokenizer-feed-replay.'+raw['phase']+'.json');v=read(path)
    demand(v['checks_passed']is True and v['epoch']==22 and v['phase']==raw['phase']
           and v['kind']=='INDEPENDENT_POSTRUN_SOURCE_TOKENIZER_JSON_FEED_REPLAY'
           and v['plan_sha256']==plan_sha and v['raw_receipt_sha256']==identity(raw_path)['sha256'],
           'exact completed independent tokenizer/feed replay required before labels/scoring')
    count=75 if raw['status']=='COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'else 3
    demand(integer(v['actual_feed_pairs_replayed'])==count and len(v['feeds'])==count
           and integer(v['model_native_forwards'])==0 and integer(v['gold_labels_read'])==0
           and v['neural_framework_imports']==[]and v['actual_worker_backend_sha256']==raw['tokenizer']['backend_sha256'],
           'tokenizer replay completeness/source scope invalid')
    demand(v['tokenizers_version']=='0.21.4'and v['independent_reconstructed_backend_sha256']==read(PROTOCOL)['tokenizer']['operational_backend_sha256']==raw['tokenizer']['backend_sha256'],
           'independent source tokenizer version/backend identity required')
    demand(v['execution_receipt']==identity(execution_path,str(Path(execution_path).relative_to(ROOT))),
           'tokenizer replay used a different sealed outer execution receipt')
    pairs=[r['forward']for r in raw['canary_forwards']]
    if count==75:
        for document in raw['documents']:
            for question in document['questions']:
                pairs.extend(question['arms'][arm]['forward']for arm in M.ARMS)
    demand(len(pairs)==count,'actual saved tokenizer forward count mismatch')
    expected=[]
    for i,row in enumerate(pairs):
        expected.append({'forward_index':i,'input_text_sha256':row['input_text_sha256'],
                         'feed_sha256':row['feed_sha256'],'tokens':row['actual_tokens']})
    demand(v['feeds']==expected and all(type(r.get('forward_index'))is int and type(r.get('tokens'))is int
             and type(r.get('input_text_sha256'))is str and SHA.fullmatch(r['input_text_sha256'])
             and type(r.get('feed_sha256'))is str and SHA.fullmatch(r['feed_sha256'])for r in v['feeds']),
           'every independent tokenizer proof row must match exact actual saved feed/text/length/order')
    assets={r['remote_path']:r for r in read(PROTOCOL)['model']['assets']}
    want=[{k:assets[name][k]for k in('path','bytes','sha256')}for name in read(PROTOCOL)['tokenizer']['source_asset_names']]
    demand(v['assets']==want,'independent tokenizer source assets changed')
    context_token_proof_replay(raw, v.get('source_sentence_context_replay'))
    return identity(path,str(path.relative_to(ROOT)))


def corpus_replay(raw,protocol,state_sha,instance,gold_rows):
    phase=raw['phase'];docs=raw['documents'];expected=protocol['data']['DEV_document_ids'if phase=='dev'else'CONF_document_ids']
    demand(type(docs)is list and[d['id']for d in docs]==expected and all(type(d['id'])is int for d in docs),'exact ordered frozen corpus document IDs required')
    gold={r['id']:r for r in gold_rows};demand(len(gold)==len(gold_rows)==24,'exact unique sealed gold rows required')
    flat=[];native=[];coverage=[];requests=[];doc_seconds=[];pair_seconds=[];max_units=0
    for doc in docs:
        state=doc['state'];demand(type(state)is str and state and doc['state_sha256']==digest(state.encode()),'exact source state identity required')
        units=doc['source_units'];demand(type(units)is list and 1<=len(units)<=192,'complete bounded source partition required');max_units=max(max_units,len(units))
        cursor=0
        for i,u in enumerate(units):
            demand(type(u['id'])is int and u['id']==i and type(u['start'])is int and type(u['end'])is int and u['start']==cursor<u['end']<=len(state),'complete contiguous source partition spans required');cursor=u['end']
            demand(type(u['nli_tokens'])is int and 0<=u['nli_tokens']<=160 and type(u['bge_tokens'])is int and 0<=u['bge_tokens']<=256,'source unit tokenizer capacity invalid')
            demand(type(u['paragraph_id'])is int and type(u['token_fallback'])is bool,'source partition metadata invalid')
        demand(cursor==len(state),'source tail omitted from complete partition')
        chunks=[state[u['start']:u['end']]for u in units]
        demand(doc['embedding']['exact_document_texts']==chunks,'document embedding used altered or external text')
        vectors,queries=doc['document_vectors'],doc['query_vectors'];demand(len(vectors)==len(units),'one actual embedding per source unit required')
        native.append(native_replay(doc['native_trace'],vectors,queries))
        questions=doc['questions'];demand(type(questions)is list and len(questions)==3,'three exact source claims per document required')
        demand(doc['embedding']['exact_query_texts']==['Represent this sentence for searching relevant passages: '+q['hypothesis']for q in questions],'retrieval query text/prefix altered')
        for qi,(question,hid)in enumerate(zip(questions,protocol['data']['hypothesis_ids'])):
            qid=f'original-contractnli:train:epoch22:{phase}:{doc["id"]}:{hid}'
            demand(type(question['id'])is str and question['id']==qid and qid in gold,'exact frozen claim identity required')
            g=gold[qid];demand(type(g['document_id'])is int and g['document_id']==doc['id']and g['hypothesis_id']==hid,'gold source group/hypothesis identity mismatch')
            demand(question['input_sha256']==g['input_sha256'],'prediction/gold exact source input hash mismatch')
            hypothesis=question['hypothesis'];depth=min(40,len(units))
            query=set(re.findall(r'\w+',hypothesis.casefold()));scores=[len(query&set(re.findall(r'\w+',text.casefold())))/max(1,len(query|set(re.findall(r'\w+',text.casefold()))))for text in chunks]
            rankings={M.ARMS[0]:doc['native_trace']['raw_native_output']['queries'][qi]['ids'],M.ARMS[1]:sorted(range(len(units)),key=lambda i:(-scores[i],i))[:depth],M.ARMS[2]:list(range(depth))}
            demand(question['rankings']==rankings and set(question['arms'])==set(M.ARMS),'matched actual selector ranking/arms mismatch')
            arms={}
            for arm in M.ARMS:
                value=question['arms'][arm];pair_seconds.append(forward_replay(value['forward'],value['premise'],hypothesis,state_sha,instance))
                coverage.append(coverage_replay(state,units,hypothesis,value,rankings[arm]));arms[arm]=value['forward']
            requests.append(duration(question['all_arm_request_elapsed_seconds']))
            flat.append({'question_id':qid,'document_id':doc['id'],'typed_gold':g['original_threeway_label'],'arms':arms})
        doc_seconds.append(duration(doc['document_elapsed_seconds']))
    ids=[f'original-contractnli:train:epoch22:{phase}:{d}:{h}'for d in expected for h in protocol['data']['hypothesis_ids']]
    M.validate_identities(flat,ids,expected)
    demand(raw['FP32_state_after_sha256']==state_sha,'loaded reader parameters/buffers changed during phase')
    demand(raw['tokenizer_backend_after_sha256']==raw['tokenizer']['backend_sha256'], 'tokenizer backend changed during corpus phase')
    return flat,{'native':native,'coverage':coverage,'max_source_units':max_units,'document_elapsed_seconds':doc_seconds,'direct_all_arm_request_seconds':requests,'direct_pair_seconds':pair_seconds}


