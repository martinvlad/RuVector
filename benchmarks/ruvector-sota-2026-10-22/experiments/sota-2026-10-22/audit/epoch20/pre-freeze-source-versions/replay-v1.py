"""Stdlib-only independent replay of immutable epoch20 worker evidence.

No candidate, tokenizer, framework, native module or dataset code is imported.
Gold is optional and may only be joined after a complete sealed corpus process.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import metrics as M

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'experiments/sota-2026-10-22/'
PROTOCOL = HERE / 'protocol.json'
SOURCE = '01c42365b8d79c968ea4f49120a5c1d71b9e0687'
MODEL = 'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli'
REVISION = '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
NATIVE_SCRIPT_SHA = '45efc7fecd2d249aea7bd1f5e7d36bf26cfe57cd6f91de51ffd15adc039ec4a3'
SHA = re.compile(r'^[0-9a-f]{64}$')
NUMBER = re.compile(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)')
demand = M.demand


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()


def identity(path, relative=None):
    p = Path(path); b = p.read_bytes()
    return {'path': relative or str(p), 'bytes': len(b), 'sha256': digest(b)}


def read(path): return json.loads(Path(path).read_bytes())


def member(relative, root=ROOT):
    demand(type(relative) is str and relative and '\\' not in relative and not PurePosixPath(relative).is_absolute()
           and all(x not in ('', '.', '..') for x in relative.split('/')), 'safe relative source path required')
    p = Path(root) / relative
    demand(not any(x.is_symlink() for x in [p, *p.parents]) and p.is_file(), 'regular nonsymlink source required: ' + relative)
    return p


def integer(value, minimum=0):
    demand(type(value) is int and value >= minimum, 'literal integer required')
    return value


def duration(value):
    n = M.real(value); demand(n >= 0, 'nonnegative measured duration/resource required'); return n


def sha_value(value):
    demand(type(value) is str and SHA.fullmatch(value), 'actual SHA256 identity required'); return value


def plan_replay(plan_path):
    p = read(plan_path); protocol = read(PROTOCOL)
    demand(p.get('schema_version') == 1 and p.get('epoch') == 20 and p.get('source_checkpoint') == SOURCE,
           'exact epoch20 source plan required')
    demand(p.get('study_id') == 'native-anli-roberta-fp32-typed-e20' and p.get('actual_project') == str(ROOT), 'exact isolated study required')
    demand(p.get('train') == [] and p.get('calibration') == [], 'explicit empty train/calibration required')
    limits = {'threads': 2, 'interop_threads': 1, 'seconds_per_batch': 600, 'worker_attempts': 2,
              'native_batches': 2, 'candidate_configs': 1, 'paid_calls': 0, 'GPU_calls': 0}
    for k, value in limits.items(): demand(type(p['limits'].get(k)) is int and p['limits'][k] == value, 'frozen limit changed: ' + k)
    pins = p['pins']; demand(type(pins) is list and bool(pins), 'source pins required')
    by_path = {r['path']: r for r in pins}; demand(len(by_path) == len(pins), 'duplicate source pins')
    for row in pins:
        path = member(row['path']); actual = identity(path, row['path'])
        demand(actual['sha256'] == row['sha256'] and ('bytes' not in row or actual['bytes'] == row['bytes']), 'source pin changed: ' + row['path'])
    for path in HERE.glob('*.py'):
        rel = str(path.relative_to(ROOT)); demand(rel in by_path, 'independent checker source unpinned: ' + rel)
    rel = str(PROTOCOL.relative_to(ROOT)); demand(by_path.get(rel, {}).get('sha256') == identity(PROTOCOL)['sha256'], 'independent protocol unpinned')
    lock = protocol['model']['asset_lock']; demand(by_path.get(lock['path'], {}).get('sha256') == lock['sha256'], 'independent model lock changed')
    demand(identity(member(lock['path']))['sha256'] == lock['sha256'], 'actual independent model lock changed')
    demand(protocol['source_head'] == SOURCE and protocol['model']['repository'] == MODEL
           and protocol['model']['revision'] == REVISION, 'independent scientific contract changed')
    return p, protocol


def model_replay(raw, protocol):
    p, state, token = raw['model_provenance'], raw['fp32_state'], raw['tokenizer']
    demand(p['repo'] == MODEL and p['revision'] == REVISION, 'selected pretrained reader revision changed')
    demand(p['raw_id2label'] == {'0': 'Entailment', '1': 'NotMentioned', '2': 'Contradiction'}
           and p['canonical_order'] == list(M.ORDER) and p['canonical_permutation'] == [0, 2, 1], 'source label mapping changed')
    for k, value in {'local_files_only': True, 'trust_remote_code': False, 'weights_only': True,
                     'use_safetensors': False, 'torch_dtype': 'torch.float32', 'output_loading_info': True,
                     'attn_implementation': 'eager'}.items():
        actual = p['load_flags'].get(k)
        demand((actual is value) if type(value) is bool else actual == value, 'fixed loader flag changed: ' + k)
    demand(p['actual_attention_implementation'] == 'eager', 'actual CPU attention implementation changed')
    for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'):
        demand(k in p['loading_info'] and p['loading_info'][k] == [], 'source tensor load mismatch: ' + k)
    demand(p['precision'] == 'ORIGINAL_CHECKPOINT_EXPLICIT_FP32_CPU_NO_QUANTIZATION', 'fixed inference precision changed')
    demand(integer(p['initialization_model_forwards']) == 0 and integer(p['quantization_initializations']) == 0, 'unplanned model/precision probes')
    for k, v in protocol['model']['versions'].items(): demand(p['versions'].get(k) == v, 'exact runtime version changed: ' + k)
    demand(integer(p['pair_token_cap']) == 512 and integer(p['batch_size']) == 1 and M.real(p['temperature']) == 1, 'fixed reader/feed budget changed')
    inventory = p['source_checkpoint_dtype_elements']
    demand(type(inventory) is dict and inventory and all(type(k) is str and k.startswith('torch.') and type(v) is int and v > 0 for k,v in inventory.items()), 'actual original checkpoint dtype inventory required')
    demand(integer(p['source_checkpoint_tensors'], 1) > 0 and integer(p['source_checkpoint_elements'], 1) == sum(inventory.values()), 'original checkpoint element inventory invalid')
    state_sha = sha_value(state['state_sha256']); demand(state_sha == p['state_sha256'], 'actual loaded state identities differ')
    demand(state['devices'] == ['cpu'] and state['all_floating_parameters_buffers_FP32'] is True
           and state['eval'] is True and state['deterministic_algorithms'] is True, 'FP32 CPU eval state required')
    parameters = state['parameter_dtype_element_counts']; demand(set(parameters) == {'torch.float32'}, 'all parameters must remain FP32')
    demand(integer(state['parameter_count'], 1) == integer(parameters['torch.float32'], 1), 'loaded parameter count invalid')
    buffers = state['buffer_dtype_element_counts']; demand(type(buffers) is dict and all(type(k) is str and k in ('torch.float32','torch.int64','torch.int32','torch.int16','torch.int8','torch.uint8','torch.bool') and type(v) is int and v >= 0 for k,v in buffers.items()), 'floating buffers must remain FP32')
    for k, expected in [('classifier_dense_shape',[1024,1024]),('classifier_out_proj_shape',[3,1024]),
                        ('classifier_dense_bias_shape',[1024]),('classifier_out_proj_bias_shape',[3])]:
        demand(state[k] == expected and all(type(x) is int for x in state[k]), 'classifier tensor shape mismatch')
    demand(integer(state['quantized_modules']) == 0 and integer(state['threads']) == 2 and integer(state['interop_threads']) == 1, 'precision/thread count changed')
    demand(type(state['model_instance_token']) is str and state['model_instance_token'], 'actual singleton model instance token required')
    for k, expected in [('type','RobertaTokenizerFast'),('backend_model','BPE'),('pair_format','<s>P</s></s>H</s>'),('bos_id',0),('eos_id',2),('pad_id',1),('all_token_type_ids',0)]:
        demand(token[k] == expected and (type(expected) is not int or type(token[k]) is int), 'actual source tokenizer changed: ' + k)
    demand(token['padding'] is False and token['truncation'] is False and token == p['tokenizer'], 'complete tokenizer provenance required')
    sha_value(token['backend_sha256'])
    assets = {row['path']: row for row in raw['asset_identities']}
    demand(len(assets) == len(raw['asset_identities']), 'duplicate actual asset receipts')
    for row in protocol['model']['assets']:
        want = {k: row[k] for k in ('path','bytes','sha256')}
        demand(assets.get(row['path']) == want, 'actual selected model asset mismatch')
    return state_sha, state['model_instance_token']


def assets_replay(raw,plan):
    model=read(member(plan['model_assets_lock_path']))['assets']
    bge=read(member(plan['bge_assets_lock_path']));bge=bge['assets']if'assets'in bge else bge['files']
    native=read(member(plan['native_closure_path']))
    native=[r for package in native['packages']for r in package['files']]if'packages'in native else native['files']
    native=[r for r in native if r['path'].startswith('retrieval/node_modules/')]
    demand(len(model)==7 and len(native)==8,'exact selected model/native closures required')
    expected=[{k:r[k]for k in('path','bytes','sha256')}for r in model+bge+native]
    demand(raw['asset_identities']==expected,'actual full reader/BGE/native asset table differs from frozen locks')
    wheels=read(member(plan['wheel_lock_path']))['wheels'];demand(len(wheels)==31,'exact31-wheelCPU runtime required')
    versions={r['filename'].split('-',2)[0]:r['filename'].split('-',2)[1]for r in wheels}
    demand(raw['versions']==versions,'actual31 installed runtime versions changed')
    return {'asset_records':len(expected),'installed_distributions':31}


def forward_replay(row, premise, hypothesis, state_sha, instance):
    demand(row['premise'] == premise and row['hypothesis'] == hypothesis, 'literal actual model pair changed')
    demand(row['input_text_sha256'] == digest(canonical([premise,hypothesis])), 'model input text hash mismatch')
    p = M.replay_forward(row)
    raw = [p['Entailment'],p['NotMentioned'],p['Contradiction']]
    demand(type(row['raw_probabilities']) is list and len(row['raw_probabilities']) == 3
           and all(abs(M.real(x)-y) <= 1e-10 for x,y in zip(row['raw_probabilities'],raw)), 'raw E/N/C probability permutation mismatch')
    feed = row['feed']; demand(type(feed) is dict and set(feed) == {'input_ids','attention_mask'}, 'exact input IDs and attention mask feed required')
    ids, mask = feed['input_ids'], feed['attention_mask']
    demand(type(ids) is list and len(ids) == 1 and type(ids[0]) is list and 4 <= len(ids[0]) <= 512, 'singleton complete pair token budget required')
    demand(type(mask) is list and len(mask) == 1 and type(mask[0]) is list and len(mask[0]) == len(ids[0]), 'exact mask shape required')
    demand(all(type(x) is int and 0 <= x < 50265 for x in ids[0]) and ids[0][0] == 0 and ids[0][-1] == 2, 'literal source vocabulary/BOS/EOS token IDs required')
    demand(all(type(x) is int and x == 1 for x in mask[0]), 'unmasked unpadded complete pair required')
    demand(row['token_type_ids_not_fed'] == [[0]*len(ids[0])] and all(type(x) is int for x in row['token_type_ids_not_fed'][0]), 'literal all-zero token types must not be fed')
    demand(type(row['actual_tokens']) is int and row['actual_tokens'] == len(ids[0]), 'actual pair length mismatch')
    demand(row['feed_sha256'] == digest(canonical(feed)), 'actual tensor feed hash mismatch')
    demand(row['padding'] is False and row['truncation'] is False and row['inference_mode'] is True and row['cpu_autocast'] is False, 'inference/feed flags changed')
    demand(row['model_state_sha256'] == state_sha and row['model_instance_token'] == instance, 'matched reader identity changed')
    return duration(row['elapsed_seconds'])


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
    omitted=[i for i in range(len(units))if i not in selected]
    demand(c['omitted_chunk_ids']==omitted and c['omitted_source_spans']==[[units[i]['start'],units[i]['end']]for i in omitted],'omitted source coverage mismatch')
    numbers=[{'span':[m.start(),m.end()],'text':m.group(),'retained':any(a<=m.start()and m.end()<=b for a,b in spans)}for m in NUMBER.finditer(state)]
    demand(c['numeric_mentions']==numbers and c['numeric_mentions_retained']==sum(x['retained']for x in numbers)
           and c['numeric_mentions_omitted']==sum(not x['retained']for x in numbers),'mechanical numeric source coverage mismatch')
    covered=sum(b-a for a,b in spans)
    demand(c['retained_source_characters']==covered and c['document_characters']==len(state)and abs(M.real(c['document_character_coverage'])-covered/len(state))<=1e-10,'source character coverage mismatch')
    return {'premise_sha256':digest(premise.encode()),'selected_units':len(selected),'retained_source_characters':covered,'numeric_retained':sum(x['retained']for x in numbers),'numeric_omitted':sum(not x['retained']for x in numbers)}


def resources_replay(raw,execution,raw_path,phase,complete):
    demand(execution['schema_version']==1 and execution['epoch']==20 and execution['phase']==phase and execution['plan_sha256']==raw['plan_sha256'],'outer execution source identity mismatch')
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
      'quantization_initializations':0,'paid_API_calls':0,'GPU_calls':0,'native104_calls':0,'previous_reader_forwards':0,
      'training_calibration_fits':0,'benchmark_HTTP_requests':0,'benchmark_documents_completed':8 if complete else 0,'benchmark_questions_completed':24 if complete else 0}
    for k,v in expected.items():demand(type(c.get(k))is int and c[k]==v,'actual scientific count mismatch: '+k)
    for k in ('BGE_forwards','BGE_texts'):
        attempted,done=c[k+'_attempted'],c[k+'_completed'];demand(type(attempted)is int and attempted==done and done>0 if complete else type(attempted)is int and attempted==done==0,'actual BGE count mismatch: '+k)
    duration(c['BGE_forward_seconds'])


def tokenizer_report_replay(raw,raw_path,plan_sha):
    path=member(PREFIX+'audit/epoch20/tokenizer-feed-replay.'+raw['phase']+'.json');v=read(path)
    demand(v['checks_passed']is True and v['epoch']==20 and v['phase']==raw['phase']
           and v['kind']=='INDEPENDENT_POSTRUN_SOURCE_BPE_FEED_REPLAY'
           and v['plan_sha256']==plan_sha and v['raw_receipt_sha256']==identity(raw_path)['sha256'],
           'exact completed independent tokenizer/feed replay required before labels/scoring')
    count=75 if raw['status']=='COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'else 3
    demand(integer(v['actual_feed_pairs_replayed'])==count and len(v['feeds'])==count
           and integer(v['model_native_forwards'])==0 and integer(v['gold_labels_read'])==0
           and v['neural_framework_imports']==[]and v['actual_worker_backend_sha256']==raw['tokenizer']['backend_sha256'],
           'tokenizer replay completeness/source scope invalid')
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
            qid=f'original-contractnli:train:epoch20:{phase}:{doc["id"]}:{hid}'
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
    ids=[f'original-contractnli:train:epoch20:{phase}:{d}:{h}'for d in expected for h in protocol['data']['hypothesis_ids']]
    M.validate_identities(flat,ids,expected)
    demand(raw['FP32_state_after_sha256']==state_sha,'loaded reader parameters/buffers changed during phase')
    return flat,{'native':native,'coverage':coverage,'max_source_units':max_units,'document_elapsed_seconds':doc_seconds,'direct_all_arm_request_seconds':requests,'direct_pair_seconds':pair_seconds}


def latency(values,scope):
    return {'n':len(values),'p50_seconds':M.percentile(values,.5),'p95_seconds':M.percentile(values,.95),'max_seconds':max(values),'scope':scope}


def runtime_replay(raw,plan,mechanical):
    capacity=raw['confirmation_capacity']; expected=read(PROTOCOL)['data']['CONF_document_ids']
    demand(capacity['scope']=='INPUT_ONLY_TOKENIZATION_CAPACITY'and capacity['source_path']==plan['confirmation_capacity_inputs_path']
           and capacity['source_sha256']==plan['confirmation_capacity_inputs_sha256'],'actual input-only confirmation capacity bank changed')
    path=member(capacity['source_path']);demand(identity(path)['sha256']==capacity['source_sha256'],'input-only capacity source bytes changed')
    rows=capacity['document_units'];demand(type(rows)is list and[r['document_id']for r in rows]==expected
        and all(type(r['document_id'])is int and type(r['units'])is int and 1<=r['units']<=192 for r in rows),'exact8 current-tokenizer confirmation unit counts required')
    demand(type(capacity['max_units'])is int and capacity['max_units']==max(r['units']for r in rows),'capacity maximum source units mismatch')
    demand(integer(capacity['model_forwards'])==0 and integer(capacity['annotation_choices_accessed'])==0
           and integer(capacity['confirmation_NLI_predictions'])==0 and capacity['text_previously_published']is True
           and capacity['training_selection_on_confirmation_labels']is False,'capacity scan may only tokenize already-published inputs')
    bank=read(path);allow=read(member(plan['phases']['confirmation']['input_allowlist_path']))
    demand(bank['role']=='confirmation'and len(bank['records'])==len(allow['records'])==24,'exact24 input-only capacity records required')
    expected_hashes={r['input_sha256']for r in allow['records']};actual_hashes=set()
    for row in bank['records']:
        demand(set(row)=={'id','input','input_sha256'}and type(row['id'])is str
               and row['input_sha256']==digest(canonical(row['input'])),'capacity bank must contain only exact source inputs, no choices')
        actual_hashes.add(row['input_sha256'])
    demand(len(actual_hashes)==24 and actual_hashes==expected_hashes,'capacity scan used a different reserved input identity')
    initialization=duration(raw['whole_pipeline_initialization_seconds'])
    demand(initialization>=duration(raw['initialization_elapsed_seconds']),'whole initialization cannot omit reader setup')
    max_document_third=max(mechanical['document_elapsed_seconds'])/3
    dev_units=integer(mechanical['max_source_units'],1);conf_units=capacity['max_units']
    ratio=max(1,conf_units/dev_units)
    forecast=24*max_document_third*ratio+2*initialization+60
    return {'formula_id':'24xDEVmaxDocumentThirdxmax1UnitRatio+2xWholeInit+60-v1',
            'max_DEV_document_seconds_divided_by3':max_document_third,'max_DEV_source_units':dev_units,
            'max_CONFIRMATION_source_units':conf_units,'source_unit_ratio':ratio,
            'whole_pipeline_initialization_seconds':initialization,'projected_confirmation_seconds':forecast,
            'limit_seconds':600,'allowed':forecast<=600,'capacity_receipt':capacity,
            'scope':'Conservative complete-document amortized forecast; no confirmation labels/predictions used and no guarantee of future completion.'}


def replay(plan_path,raw_path,execution_path,gold_path=None):
    plan,protocol=plan_replay(plan_path);raw=read(raw_path);execution=read(execution_path);phase=raw['phase']
    demand(phase in ('dev','confirmation')and raw['schema_version']==1 and raw['epoch']==20 and raw['plan_sha256']==identity(plan_path)['sha256'],'raw scientific/source identity mismatch')
    demand(raw['errors']==[],'actual worker errors prevent acceptance')
    state,instance=model_replay(raw,protocol);assets=assets_replay(raw,plan);engineering=engineering_replay(raw,protocol,state,instance)
    complete=raw['status']=='COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'
    if complete:demand(engineering['passed'],'legal corpus followed failed engineering readiness')
    else:
        demand(raw['status']=='REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'and not engineering['passed']and raw['documents']==[],'only completed corpus or valid prelegal engineering rejection can be scored')
        demand(gold_path is None,'engineering failure must not project or join any legal labels')
    resources=resources_replay(raw,execution,raw_path,phase,complete);counters_replay(raw,complete)
    token_proof=tokenizer_report_replay(raw,raw_path,identity(plan_path)['sha256'])
    report={'schema_version':1,'epoch':20,'phase':phase,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
            'engineering_qualified':engineering['passed'],'accepted_for_confirmation':False,'DEV_gate_passed':None,'CONF_gate_passed':None,
            'accepted':False,'runtime_gate_passed':False,'plan_sha256':identity(plan_path)['sha256'],
            'raw_receipt':identity(raw_path,str(Path(raw_path).relative_to(ROOT))),
            'execution_receipt':identity(execution_path,str(Path(execution_path).relative_to(ROOT))),
            'engineering':engineering,'model_state_sha256':state,'tokenizer_backend_sha256':raw['tokenizer']['backend_sha256'],
            'asset_runtime_replay':assets,
            'independent_tokenizer_feed_replay':token_proof,
            'actual_counters':raw['counters'],'actual_resources':resources,'champion_promoted':False,'submission_allowed':False,
            'official_score':None,'official_rank':None,'official_SOTA_goal_verified':False,'used_confirmation_identities':[]}
    if not complete:
        report['status']='REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS';report['metrics']=None
        report['all_remaining_epoch20_slots_must_close']=True;return report
    demand(gold_path is not None,'complete sealed corpus needs independent postprediction gold projection')
    gold=read(gold_path);demand(gold['phase']==phase and gold['raw_receipt_sha256']==report['raw_receipt']['sha256'],'postprediction gold projection is stale/different phase')
    demand(gold['status']=='FIXED_ROLE_GOLD_PROJECTED_AFTER_COMPLETE_SEALED_PREDICTIONS_AND_CLEANUP'
           and gold['plan_sha256'] == raw['plan_sha256'] and integer(gold['annotation_choices_accessed']) == 24
           and integer(gold['other_role_annotation_choices_accessed']) == 0 and integer(gold['old_reserved48_choices_accessed']) == 0
           and gold['labels_used_for_model_fit_calibration_selection'] is False and integer(gold['model_native_paid_GPU_calls']) == 0,
           'exact role-specific postprediction-only gold provenance required')
    rows,mechanical=corpus_replay(raw,protocol,state,instance,gold['records'])
    result=M.gate(rows,phase=='confirmation');report['metrics']=result
    report['mechanical_replays']=mechanical
    report['latency']={'direct_pair':latency(mechanical['direct_pair_seconds'],'72corpus matched-arm direct pair forwards; no engineering cases.'),
                       'direct_all_arm_request':latency(mechanical['direct_all_arm_request_seconds'],'Three matched NLIarms perquestion; document preparation is reported separately.'),
                       'document_amortized':latency([x/3 for x in mechanical['document_elapsed_seconds']],'Complete source partition/embedding/native and3questionsx3NLIarms perdocument, dividedby3; amortized full-document unit, not serving latency.')}
    report['gold_receipt']=identity(gold_path,str(Path(gold_path).relative_to(ROOT)))
    if phase=='dev':
        forecast=runtime_replay(raw,plan,mechanical);report['runtime_forecast']=forecast
        report['DEV_gate_passed']=result['passed'];report['runtime_gate_passed']=forecast['allowed']
        report['accepted_for_confirmation']=result['passed']and forecast['allowed']
        report['status']=('DEV_ACCEPTED_FOR_CONDITIONAL_CONFIRMATION'if report['accepted_for_confirmation']else
                          'REJECTED_DEV_GATE'if not result['passed']else'BLOCKED_CONFIRMATION_RUNTIME_FORECAST')
        report['all_remaining_epoch20_slots_must_close']=not report['accepted_for_confirmation']
    else:
        report['CONF_gate_passed']=result['passed'];report['accepted']=result['passed'];report['status']='LOCAL_MATCHED_RETRIEVAL_RESEARCH_ACCEPTED_ONLY'if result['passed']else'REJECTED_CONFIRMATION_GATE'
        report['used_confirmation_identities']=[r['question_id']for r in rows];report['all_remaining_epoch20_slots_must_close']=True
    return report


def write_new(path,value):
    p=Path(path);demand(not any(x.is_symlink()for x in[p,*p.parents]),'nonsymlink output required')
    with p.open('x')as f:json.dump(M.json_safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    ap=argparse.ArgumentParser()
    for key in ('plan','raw','execution','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--gold',type=Path)
    args=ap.parse_args()
    try:
        report=replay(args.plan,args.raw,args.execution,args.gold)
    except (M.InvalidReceipt,KeyError,TypeError,ValueError,OSError)as exc:
        report={'schema_version':1,'epoch':20,'at':datetime.now(timezone.utc).isoformat(),
                'status':'INCONCLUSIVE_INVALID_OR_INCOMPLETE_EXECUTION','checks_passed':False,
                'engineering_qualified':None,'accepted_for_confirmation':False,'accepted':False,
                'champion_promoted':False,'submission_allowed':False,'official_score':None,'official_rank':None,
                'failures':[{'type':type(exc).__name__,'message':str(exc)}],
                'model_native_calls_by_checker':0,'all_remaining_epoch20_slots_must_close':True,
                'scope':'Retain actual partial/invalid evidence and uncertainty; do not fabricate missing scores/counters or retry.'}
        for label,path in(('plan',args.plan),('raw',args.raw),('execution',args.execution)):
            try:report[label+'_receipt']=identity(path,str(path.relative_to(ROOT)))
            except (OSError,ValueError):report[label+'_receipt']=None
        try:
            actual=read(args.raw);report['phase']=actual.get('phase');report['actual_counters_unverified']=actual.get('counters');report['actual_worker_errors_unverified']=actual.get('errors')
        except (OSError,ValueError):report['phase']=None
    write_new(args.out,report)
    print(json.dumps({k:report[k]for k in('status','checks_passed','engineering_qualified','accepted_for_confirmation','accepted')}))


if __name__=='__main__':main()
