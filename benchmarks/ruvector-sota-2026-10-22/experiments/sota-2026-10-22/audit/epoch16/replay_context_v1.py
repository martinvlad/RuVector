"""Independent label-free capacity and saved source/vector/token replay.

No ONNX/model/native sessions, inference, fitting or new annotation reads.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import re
import numpy as np
from tokenizers import Tokenizer
import source_math_v1 as M

PREFIX = 'It is not the case that '
TOKENIZER_SHA = '5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964'
MODEL_SHA = '821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
MODEL_REV = 'bab4bc7178836f731dcfd18c06ca9def0a137712'
PARTITION_SHA = '28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def obj(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x]
def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


class JointBudgetTokenizer:
    """Count BOTH real pair encodings; returned encoding is only a count proxy.

    This adapter is used by independent packing arithmetic, never model feeds.
    Actual positive/counterclaim feed IDs are separately reconstructed below.
    """
    def __init__(self, tokenizer, hypothesis):
        self.tokenizer, self.hypothesis = tokenizer, hypothesis

    def encode(self, text, pair=None, **kwargs):
        if pair is None: return self.tokenizer.encode(text, **kwargs)
        assert pair == self.hypothesis
        positive = self.tokenizer.encode(text, pair, **kwargs)
        negative = self.tokenizer.encode(text, PREFIX+pair, **kwargs)
        return positive if len(positive.ids) >= len(negative.ids) else negative


def lexical(units, state, hypothesis):
    terms = set(re.findall(r'\w+', hypothesis.casefold()))
    scores = []
    for i, unit in enumerate(units):
        words = set(re.findall(r'\w+', state[unit['start']:unit['end']].casefold()))
        scores.append((-len(terms & words)/max(1,len(terms | words)), i))
    return [i for _,i in sorted(scores)[:40]]


def verify_pack(arm, state, units, order, h, tokenizer, priority):
    q = PREFIX+h; budget = JointBudgetTokenizer(tokenizer, h)
    result = M.pack(state, units, order, h, budget, priority['selected_unit_ids'])
    cov = arm['coverage']
    assert arm['hypothesis'] == h and arm['counterclaim'] == q
    assert arm['premise'] == result['premise'] and arm['ranking_ids'] == order
    assert arm['chunk_ids'] == result['selected']
    assert arm['chunk_spans'] == [[units[i]['start'],units[i]['end']] for i in result['selected']]
    M.check_priority(cov['definition_priority'], priority)
    assert cov['selected_chunk_ids_rank_order'] == result['selected']
    assert cov['selected_chunk_ids_source_order'] == sorted(result['selected'])
    assert cov['selected_source_spans'] == result['spans']
    assert cov['ranking_ids_considered'] == order and cov['ranking_depth'] == len(order)
    assert cov['ranked_anchor_candidate_cap'] == min(40,len(units))
    trace = cov['packing_attempts']; assert len(trace) == len(result['trace'])
    selected = list(priority['selected_unit_ids'])
    for actual, expected in zip(trace,result['trace']):
        assert {key:actual[key] for key in expected} == expected
        text,_ = M.text_for(state,units,selected+[actual['unit_id']])
        positive = len(tokenizer.encode(text,h).ids); counter = len(tokenizer.encode(text,q).ids)
        assert actual['candidate_positive_pair_tokens'] == positive
        assert actual['candidate_counterclaim_pair_tokens'] == counter
        assert actual['candidate_pair_tokens'] == max(positive,counter)
        if actual['accepted']: selected.append(actual['unit_id'])
    assert selected == result['selected']
    assert cov['additional_neighbor_unit_ids_inspected'] == result['neighbors']
    omitted = [i for i in range(len(units)) if i not in selected]
    assert cov['omitted_chunk_ids'] == omitted
    assert cov['omitted_source_spans'] == [[units[i]['start'],units[i]['end']] for i in omitted]
    assert cov['retained_source_characters'] == result['chars']
    assert cov['document_characters'] == len(state)
    assert abs(cov['document_character_coverage']-result['chars']/len(state)) < 1e-12
    assert cov['numeric_mentions'] == result['numbers']
    assert cov['numeric_mentions_retained'] == sum(x['retained'] for x in result['numbers'])
    assert cov['numeric_mentions_omitted'] == sum(not x['retained'] for x in result['numbers'])
    assert not cov['selected_evidence_truncated'] and not cov['claim_truncated'] and not cov['counterclaim_truncated']
    for field,text in [('premise',result['premise']),('hypothesis',h),('counterclaim',q)]:
        assert cov[field+'_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    positive = tokenizer.encode(result['premise'],h); counter = tokenizer.encode(result['premise'],q)
    assert cov['positive_joint_pair_tokens'] == len(positive.ids)
    assert cov['counterclaim_joint_pair_tokens'] == len(counter.ids)
    assert cov['joint_pair_tokens'] == result['tokens'] == max(len(positive.ids),len(counter.ids)) <= 512
    assert cov['joint_pair_token_cap'] == 512 and len(result['premise'].encode()) <= 16*1024
    return result, positive, counter


def setup(root):
    s = root/'experiments/sota-2026-10-22'
    base = s/'candidate/epoch6/context.py'; assert sha(base) == PARTITION_SHA
    partition = module(base,'independent16_reviewed_partition').partition
    asset = s/'candidate/epoch15/assets/official-deberta-v3-large'
    assert sha(asset/'tokenizer.json') == TOKENIZER_SHA
    nli = Tokenizer.from_file(str(asset/'tokenizer.json'))
    bge = Tokenizer.from_file(str(root/'models/bge-small-en-v1.5/tokenizer.json'))
    for t in (nli,bge): t.no_padding(); t.no_truncation()
    return s, partition, nli, bge


def capacity(root):
    s, partition, nli, bge = setup(root)
    candidate = module(s/'candidate/epoch16/context.py','capacity16_candidate_pure_context')
    data = s/'legal-transfer/epoch16'; phases = {}; cache = {}; total = 0
    for phase,role in [('development','dev'),('confirmation','confirmation')]:
        inputs_path = data/(role+'-inputs-only.json'); inputs = obj(inputs_path)['records']
        allow = obj(data/(role+'-input-allowlist.json'))['records']
        assert len(inputs) == len(allow) == 24
        observations = []
        for row, identity in zip(inputs,allow):
            assert set(row) == {'id','input','input_sha256'} and set(row['input']) == {'state','questions'}
            assert row['id'] == identity['id'] and row['input_sha256'] == identity['input_sha256']
            raw = json.dumps(row['input'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            assert hashlib.sha256(raw).hexdigest() == row['input_sha256']
            state = row['input']['state']; h = row['input']['questions']['decision']['criteria']['Yes']; q = PREFIX+h
            fingerprint = hashlib.sha256(state.encode()).hexdigest()
            if fingerprint not in cache:
                units = partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
                assert ''.join(state[u['start']:u['end']] for u in units) == state
                priority = M.priority(state,units,nli)
                M.check_priority(candidate.select_prelude(state,units,nli),priority)
                cache[fingerprint] = (units,priority)
            units,priority = cache[fingerprint]
            assert len(bge.encode('Represent this sentence for searching relevant passages: '+h).ids) <= 256
            for u in units:
                text = state[u['start']:u['end']]
                assert len(nli.encode(text,add_special_tokens=False).ids) == u['nli_tokens'] <= 160
                assert len(bge.encode(text).ids) == u['bge_tokens'] <= 256
            orders = [list(range(min(40,len(units)))),lexical(units,state,h),
                      list(reversed(range(len(units))))[:40],
                      sorted(range(len(units)),key=lambda i:(i%2,i))[:40],
                      sorted(range(len(units)),key=lambda i:(-(i%2),i))[:40]]
            orders += [[i] for i in range(len(units))]
            maximum = 0
            for order in orders:
                premise,cov = candidate.pack(state,units,order,h,q,nli,
                    rank_depth=min(40,len(units)),prelude=candidate.select_prelude(state,units,nli))
                pseudo = {'coverage':cov,'chunk_ids':cov['selected_chunk_ids_rank_order'],
                    'chunk_spans':[[units[i]['start'],units[i]['end']] for i in cov['selected_chunk_ids_rank_order']],
                    'premise':premise,'hypothesis':h,'counterclaim':q,'ranking_ids':order}
                _,positive,counter = verify_pack(pseudo,state,units,order,h,nli,priority)
                maximum = max(maximum,len(positive.ids),len(counter.ids)); total += 1
            observations.append({'id':row['id'],'input_sha256':row['input_sha256'],
                'source_state_SHA256':fingerprint,'source_units':len(units),
                'priority_unit_ids':priority['selected_unit_ids'],'orders_checked':len(orders),
                'maximum_checked_pair_tokens':maximum})
        phases[phase] = {'n':24,'unique_documents':len({x['source_state_SHA256'] for x in observations}),
                        'max_units':max(x['source_units'] for x in observations),'rows':observations}
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'status':'INDEPENDENT_LABEL_FREE_BOTH_PAIR_CAPACITY_PASS','phases':phases,
        'actual_tokenization_pack_checks':total,'context_SHA256':sha(s/'candidate/epoch16/context.py'),
        'independent_source_math_SHA256':sha(Path(__file__).parent/'source_math_v1.py'),
        'scope':'Fixed48label-freeinputs, allsingleanchor+neighbors and5fullorders; not all40! orders. Tokenization/source checks only, no generalization/semantic/arithmetic truth claim.',
        'CONF_annotation_choices_read':0,'auditor_model_native_session_fit_paid_GPU_calls':0}


def replay(root, plan_path, plan_sha):
    assert sha(plan_path) == plan_sha; plan = obj(plan_path)
    for pin in plan['pins']: assert sha(root/pin['path']) == pin['sha256'],pin['path']
    s, partition, nli, bge = setup(root)
    study = s/'epoch16'; proofs = []; phases = {}; counts = {}; priorities = {}
    agreements = {'full_order':0,'candidate_set':0,'top2_set':0}
    for phase in ('development','confirmation'):
        run = study/'runs'/phase
        if not (run/'popen-attempt.json').exists(): continue
        records = rows(run/'records.jsonl') if (run/'records.jsonl').exists() else []
        runtime = obj(run/'runtime.json') if (run/'runtime.json').exists() else None
        pc = {'requests':0,'NLI_pairs':0,'NLI_tokens':0,'BGE_texts':0,'BGE_batches':0}
        if runtime:
            receipt = runtime['receipt']
            assert receipt['nli']['model_sha256'] == MODEL_SHA
            assert receipt['nli']['revision'] == MODEL_REV and receipt['old_base_NLI_session_initialized'] is False
            assert receipt['nli']['label_indices'] == {'contradiction':0,'entailment':1,'neutral':2}
            assert receipt['nli']['tokenizer_sha256'] == receipt['nli']['policy_tokenizer_sha256'] == TOKENIZER_SHA
            assert receipt['counterclaim_prefix'] == PREFIX
        for row in records:
            state = row['input']['state']; h = row['input']['questions']['decision']['criteria']['Yes']; q = PREFIX+h
            d = row['response']['diagnostics']['decision']; assert d['source_state'] == state
            assert d['source_state_sha256'] == hashlib.sha256(state.encode()).hexdigest()
            units = partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
            assert d['source_units'] == units and d['full_source_partition'] and not d['source_partition_has_overlap']
            assert ''.join(state[u['start']:u['end']] for u in units) == state
            assert d['chunk_spans'] == [[u['start'],u['end']] for u in units]
            assert d['total_chunks'] == len(units) and d['ranking_candidate_depth'] == min(40,len(units))
            priority = M.priority(state,units,nli); M.check_priority(d['definition_priority'],priority)
            fingerprint = d['source_state_sha256']
            if fingerprint in priorities: assert priorities[fingerprint] == priority
            else: priorities[fingerprint] = priority
            retrieval = d['retrieval']; evidence = retrieval['bundle_evidence']
            bundle_path = run/'bundles'/evidence['relativefilename']
            assert bundle_path.resolve().is_relative_to((run/'bundles').resolve()) and not bundle_path.is_symlink()
            assert bundle_path.name == evidence['sha256']+'.json' and bundle_path.stat().st_size == evidence['bytes']
            assert sha(bundle_path) == evidence['sha256'] == retrieval['native']['bundle_sha256']
            bundle = obj(bundle_path); vectors = np.asarray(bundle['vectors'],dtype=np.float64)
            query = np.asarray(bundle['query_vectors'],dtype=np.float64)
            assert vectors.shape == (len(units),384) and query.shape == (1,384)
            assert np.isfinite(vectors).all() and np.isfinite(query).all()
            assert np.max(np.abs(np.linalg.norm(vectors,axis=1)-1)) < 1e-5
            assert abs(np.linalg.norm(query)-1) < 1e-5
            native = retrieval['native']; assert native['native'] and native['package_version'] == '0.1.33'
            assert native['native_binary_sha256'] == receipt['native_core_binary_sha256']
            assert native['vectors'] == len(units)
            ids = native['queries'][0]['ids']
            assert len(ids) == len(set(ids)) == min(40,len(units)) and all(type(i) is int and 0<=i<len(units) for i in ids)
            assert retrieval['ranking_scope']['actual_returned_ids'] == ids
            assert retrieval['ranking_scope']['requested'] == min(40,len(units))
            cosine = vectors@query[0]/(np.linalg.norm(vectors,axis=1)*np.linalg.norm(query[0]))
            exact = sorted(range(len(units)),key=lambda i:(-cosine[i],i))[:min(40,len(units))]
            agreements['full_order'] += ids == exact; agreements['candidate_set'] += set(ids) == set(exact)
            agreements['top2_set'] += set(ids[:2]) == set(exact[:2])
            embedding = retrieval['embedding']; chunks = [state[u['start']:u['end']] for u in units]
            texts = ([] if embedding['chunks']['cache_hit'] else chunks)+['Represent this sentence for searching relevant passages: '+h]
            examples = embedding['chunks']['examples']+embedding['query']['examples']
            assert len(examples) == len(texts) == embedding['actual_embedded_texts']
            for text,observed in zip(texts,examples):
                n = len(bge.encode(text).ids); assert n<=256 and observed == {'raw_tokens':n,'used_tokens':n,'truncated':False}
            orders = {'ruvector_top2':ids,'lexical_top2':lexical(units,state,h),
                      'positional_first2':list(range(min(40,len(units))))}
            proof = {'id':row['id'],'phase':phase,'priority_ids':priority['selected_unit_ids'],
                     'native_ranking_ids':ids,'exact_cosine_order':exact,'arms':{}}
            for name,order in orders.items():
                arm = d['arms'][name]; result,pos,neg = verify_pack(arm,state,units,order,h,nli,priority)
                for field,encoding in [('positive_decoding',pos),('counterclaim_decoding',neg)]:
                    dec = arm[field]
                    assert dec['input_ids'] == encoding.ids and dec['attention_mask'] == encoding.attention_mask
                    assert dec['token_type_ids'] == encoding.type_ids and all(v==1 for v in encoding.attention_mask)
                    assert encoding.ids[0] == 1 and encoding.ids[-1] == 2 and encoding.type_ids[0] == 0 and encoding.type_ids[-1] == 1
                    assert dec['actual_graph_inputs'] == ['attention_mask','input_ids']
                    assert dec['active_Unigram_policy_pair_tokens'] == dec['actual_model_pair_tokens'] == len(encoding.ids) <= 512
                    assert dec['model_revision'] == MODEL_REV and dec['onnx_sha256'] == MODEL_SHA
                    assert not dec['truncated'] and dec['padding_tokens'] == 0
                    pc['NLI_pairs'] += 1; pc['NLI_tokens'] += len(encoding.ids)
                proof['arms'][name] = {'selected_unit_ids':result['selected'],'source_spans':result['spans'],
                    'positive_tokens':len(pos.ids),'counterclaim_tokens':len(neg.ids),
                    'numeric_retained':sum(x['retained'] for x in result['numbers'])}
            primary = d['arms']['ruvector_top2']
            control = {'state':primary['premise'],'questions':row['input']['questions']}
            assert d['baseline_control_input'] == control and d['baseline_control_source_chunk_ids'] == primary['chunk_ids']
            assert d['semantic_control_label'] == 'same_nli_native_raw_h'
            raw = json.dumps(control,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            assert hashlib.sha256(raw).hexdigest() == d['baseline_control_input_sha256']
            pc['requests'] += 1; pc['BGE_texts'] += len(texts)
            pc['BGE_batches'] += embedding['chunks']['model_batches']+embedding['query']['model_batches']
            proofs.append(proof)
        terminal = obj(run/'final-engine.json') if (run/'final-engine.json').exists() else None
        complete = (run/'completion.json').exists() and obj(run/'completion.json')['exit_code'] == 0
        if complete: assert pc['requests'] == 24
        if terminal:
            counters = terminal['execution_after_close']['counters']
            for key in ('requests','native104_requests','native_core_searches','context_partitions'):
                assert counters[key+'_completed'] >= pc['requests']
                if complete: assert counters[key+'_attempted'] == counters[key+'_completed'] == pc['requests']
            for key,expected in [('context_packs',pc['requests']*3),('bge_texts',pc['BGE_texts']),
                                 ('bge_forward_batches',pc['BGE_batches']),('nli_forward_pairs',pc['NLI_pairs']),
                                 ('nli_input_tokens',pc['NLI_tokens']),('nli_positive_pairs',pc['NLI_pairs']//2),
                                 ('nli_counterclaim_pairs',pc['NLI_pairs']//2)]:
                assert counters[key+'_completed'] >= expected
                if complete: assert counters[key+'_attempted'] == counters[key+'_completed'] == expected
        phases[phase] = {'complete':complete,'scored_request_counts':pc,
                         'actual_terminal_counters':terminal['execution_after_close']['counters'] if terminal else None}
        for key,value in pc.items(): counts[key] = counts.get(key,0)+value
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'scope':'Independent actual saved source/priority/BOTH-tokenfeeds/pairedselector/native-vector/counter replay. No semantic sufficiency, arithmetic truth or absence inference from retrieval misses.',
        'plan_SHA256':plan_sha,'counts':counts,'phase_counts':phases,
        'native_exact_agreement_counts':agreements,'shared_priority_documents':len(priorities),
        'rows':proofs,'auditor_model_native_session_fit_paid_GPU_calls':0,
        'official_score':None,'official_rank':None,'SOTA_established':False}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--capacity',action='store_true')
    ap.add_argument('--plan-path',type=Path); ap.add_argument('--expected-plan-sha'); a = ap.parse_args()
    if a.capacity: result = capacity(a.project.resolve())
    else:
        assert a.plan_path and a.expected_plan_sha
        plan_path = a.plan_path if a.plan_path.is_absolute() else a.project/a.plan_path
        result = replay(a.project.resolve(),plan_path,a.expected_plan_sha)
    raw = (json.dumps(result,indent=2)+chr(10)).encode()
    with a.out.open('xb') as f: f.write(raw)
    print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(raw).hexdigest(),
                     'status':result.get('status'),'counts':result.get('counts'),
                     'capacity':{k:{x:v for x,v in p.items() if x!='rows'} for k,p in result.get('phases',{}).items()}}))


if __name__ == '__main__': main()
