"""Independent label-free capacity and saved source/vector/token replay.

No neural/model/native sessions, inference, fitting or new annotation reads.
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
import process_v1 as P

TOKENIZER_SHA = '5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964'
MODEL_SHA = '821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
MODEL_REV = 'bab4bc7178836f731dcfd18c06ca9def0a137712'
NEW_SPM = '5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17'
NEW_REV = '2b65bccdedcead4bc685988bcc30153d4922a789'
NEW_WEIGHT = 'cc41eeb065c6ab3f7e88f8dab756334abb1f77a1136fec8cf02442143934c253'
PARTITION_SHA = '28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def obj(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x]
def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


class JointBudgetTokenizer:
    """Independent max of two exact tokenizer encodings; model feeds separate."""
    def __init__(self, new, previous): self.new, self.previous = new, previous
    def encode(self, text, pair=None, add_special_tokens=True):
        a = self.new.encode(text,pair,add_special_tokens=add_special_tokens)
        b = self.previous.encode(text,pair,add_special_tokens=add_special_tokens)
        return a if len(a.ids) >= len(b.ids) else b


def check_priority(actual, expected, state, units, new, previous):
    M.check_priority(actual,expected)
    text,_ = M.text_for(state,units,expected['selected_unit_ids'])
    assert actual['new_reader_priority_tokens'] == len(new.encode(text,add_special_tokens=False).ids)
    assert actual['previous_reader_priority_tokens'] == len(previous.encode(text,add_special_tokens=False).ids)
    assert expected['priority_tokens'] == max(actual['new_reader_priority_tokens'],actual['previous_reader_priority_tokens']) <= 160


def lexical(units, state, hypothesis):
    terms = set(re.findall(r'\w+', hypothesis.casefold()))
    scores = []
    for i, unit in enumerate(units):
        words = set(re.findall(r'\w+', state[unit['start']:unit['end']].casefold()))
        scores.append((-len(terms & words)/max(1,len(terms | words)), i))
    return [i for _,i in sorted(scores)[:40]]


def verify_pack(arm,state,units,order,h,new,previous,priority):
    budget = JointBudgetTokenizer(new,previous)
    result = M.pack(state,units,order,h,budget,priority['selected_unit_ids'])
    cov = arm['coverage']
    assert arm['hypothesis'] == h and 'counterclaim' not in arm
    assert arm['premise'] == result['premise'] and arm['ranking_ids'] == order
    assert arm['chunk_ids'] == result['selected']
    assert arm['chunk_spans'] == [[units[i]['start'],units[i]['end']] for i in result['selected']]
    check_priority(cov['definition_priority'],priority,state,units,new,previous)
    assert cov['selected_chunk_ids_rank_order'] == result['selected']
    assert cov['selected_chunk_ids_source_order'] == sorted(result['selected'])
    assert cov['selected_source_spans'] == result['spans']
    assert cov['ranking_ids_considered'] == order and cov['ranking_depth'] == len(order)
    assert cov['ranked_anchor_candidate_cap'] == min(40,len(units))
    trace = cov['packing_attempts']; assert len(trace) == len(result['trace'])
    selected = list(priority['selected_unit_ids'])
    for actual,expected in zip(trace,result['trace']):
        assert {key:actual[key] for key in expected} == expected
        text,_ = M.text_for(state,units,selected+[actual['unit_id']])
        a = len(new.encode(text,h).ids); b = len(previous.encode(text,h).ids)
        assert actual['candidate_new_reader_pair_tokens'] == a
        assert actual['candidate_previous_reader_pair_tokens'] == b
        assert actual['candidate_pair_tokens'] == max(a,b)
        if actual['accepted']: selected.append(actual['unit_id'])
    assert selected == result['selected']
    assert cov['additional_neighbor_unit_ids_inspected'] == result['neighbors']
    omitted = [i for i in range(len(units)) if i not in selected]
    assert cov['omitted_chunk_ids'] == omitted
    assert cov['omitted_source_spans'] == [[units[i]['start'],units[i]['end']] for i in omitted]
    assert cov['retained_source_characters'] == result['chars'] and cov['document_characters'] == len(state)
    assert abs(cov['document_character_coverage']-result['chars']/len(state)) < 1e-12
    assert cov['numeric_mentions'] == result['numbers']
    assert cov['numeric_mentions_retained'] == sum(x['retained'] for x in result['numbers'])
    assert cov['numeric_mentions_omitted'] == sum(not x['retained'] for x in result['numbers'])
    assert cov['selected_evidence_truncated'] is False and cov['claim_truncated'] is False
    assert cov['previous_reader_same_exact_premise'] is True and cov['no_not_pairing'] is True
    for field,text in [('premise',result['premise']),('hypothesis',h)]:
        assert cov[field+'_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    a = new.encode(result['premise'],h); b = previous.encode(result['premise'],h)
    assert cov['new_reader_joint_pair_tokens'] == len(a.ids) <= 512
    assert cov['previous_reader_joint_pair_tokens'] == len(b.ids) <= 512
    assert cov['joint_pair_tokens'] == result['tokens'] == max(len(a.ids),len(b.ids)) <= 512
    assert cov['joint_pair_token_cap'] == 512 and len(result['premise'].encode()) <= 16*1024
    counter = cov['no_priority_counterfactual']; old = M.pack(state,units,order,h,budget,[])
    assert counter['status'] == 'TOKENIZATION_ONLY' and counter['model_forwards'] == 0
    expected = {'selected_chunk_ids_source_order':sorted(old['selected']),
        'selected_source_spans':old['spans'],'joint_pair_tokens':old['tokens'],
        'retained_source_characters':old['chars'],'numeric_mentions_retained':sum(x['retained'] for x in old['numbers']),
        'displaced_unit_ids':sorted(set(old['selected'])-set(result['selected'])),
        'introduced_unit_ids':sorted(set(result['selected'])-set(old['selected'])),
        'source_characters_delta':result['chars']-old['chars'],'pair_tokens_delta':old['tokens']*-1+result['tokens'],
        'numeric_retained_delta':sum(x['retained'] for x in result['numbers'])-sum(x['retained'] for x in old['numbers'])}
    for key,value in expected.items(): assert counter[key] == value,('counterfactual',key)
    return result,a,b


def setup(root):
    s = root/'experiments/sota-2026-10-22'
    base = s/'candidate/epoch6/context.py'; assert sha(base) == PARTITION_SHA
    partition = module(base,'independent18_reviewed_partition').partition
    previous_asset = s/'candidate/epoch15/assets/official-deberta-v3-large'
    assert sha(previous_asset/'tokenizer.json') == TOKENIZER_SHA
    previous = Tokenizer.from_file(str(previous_asset/'tokenizer.json'))
    asset = s/'candidate/epoch17/assets/official-deberta-v2-xlarge-mnli'
    assert sha(asset/'spm.model') == NEW_SPM
    assert sha(asset/'config.json') == '617f9d0b46fe934497a5aab5b44b1b343a751c0c43fec3e56e26b21e76b77c60'
    assert sha(asset/'tokenizer_config.json') == '0704f75eb3defe60aab06311d14756aa2f48c9aae758c8e5f78aa02dd92cc757'
    import importlib.metadata
    assert importlib.metadata.version('transformers') == '4.52.4'
    assert importlib.metadata.version('tokenizers') == '0.21.4'
    assert importlib.metadata.version('sentencepiece') == '0.2.0'
    from transformers import DebertaV2TokenizerFast
    high = DebertaV2TokenizerFast.from_pretrained(str(asset),local_files_only=True,trust_remote_code=False)
    new = high.backend_tokenizer
    bge = Tokenizer.from_file(str(root/'models/bge-small-en-v1.5/tokenizer.json'))
    for t in (new,previous,bge): t.no_padding(); t.no_truncation()
    return s,partition,new,previous,bge


def capacity(root):
    s, partition, new, previous, bge = setup(root)
    joint = JointBudgetTokenizer(new,previous)
    candidate = module(s/'candidate/epoch17/context.py','capacity17_candidate_pure_context')
    data = s/'legal-transfer/epoch18'; phases = {}; cache = {}; total = 0
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
            state = row['input']['state']; h = row['input']['questions']['decision']['criteria']['Yes']
            fingerprint = hashlib.sha256(state.encode()).hexdigest()
            if fingerprint not in cache:
                units = partition(state,joint,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
                assert ''.join(state[u['start']:u['end']] for u in units) == state
                priority = M.priority(state,units,joint)
                check_priority(candidate.select_prelude(state,units,new,previous),priority,state,units,new,previous)
                cache[fingerprint] = (units,priority)
            units,priority = cache[fingerprint]
            assert len(bge.encode('Represent this sentence for searching relevant passages: '+h).ids) <= 256
            for u in units:
                text = state[u['start']:u['end']]
                assert len(joint.encode(text,add_special_tokens=False).ids) == u['nli_tokens'] <= 160
                assert len(bge.encode(text).ids) == u['bge_tokens'] <= 256
            orders = [list(range(min(40,len(units)))),lexical(units,state,h),
                      list(reversed(range(len(units))))[:40],
                      sorted(range(len(units)),key=lambda i:(i%2,i))[:40],
                      sorted(range(len(units)),key=lambda i:(-(i%2),i))[:40]]
            orders += [[i] for i in range(len(units))]
            maximum = 0
            for order in orders:
                premise,cov = candidate.pack(state,units,order,h,new,previous,
                    rank_depth=min(40,len(units)),prelude=candidate.select_prelude(state,units,new,previous))
                pseudo = {'coverage':cov,'chunk_ids':cov['selected_chunk_ids_rank_order'],
                    'chunk_spans':[[units[i]['start'],units[i]['end']] for i in cov['selected_chunk_ids_rank_order']],
                    'premise':premise,'hypothesis':h,'ranking_ids':order}
                _,positive,counter = verify_pack(pseudo,state,units,order,h,new,previous,priority)
                maximum = max(maximum,len(positive.ids),len(counter.ids)); total += 1
            observations.append({'id':row['id'],'input_sha256':row['input_sha256'],
                'source_state_SHA256':fingerprint,'source_units':len(units),
                'priority_unit_ids':priority['selected_unit_ids'],'orders_checked':len(orders),
                'maximum_checked_pair_tokens':maximum})
        phases[phase] = {'n':24,'unique_documents':len({x['source_state_SHA256'] for x in observations}),
                        'max_units':max(x['source_units'] for x in observations),'rows':observations}
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'status':'INDEPENDENT_LABEL_FREE_BOTH_READER_CAPACITY_PASS','phases':phases,
        'actual_tokenization_pack_checks':total,'context_SHA256':sha(s/'candidate/epoch17/context.py'),
        'independent_source_math_SHA256':sha(Path(__file__).parent/'source_math_v1.py'),
        'scope':'Fixed48label-freeinputs, allsingleanchor+neighbors and5fullorders; not all40! orders. Tokenization/source checks only, no generalization/semantic/arithmetic truth claim.',
        'CONF_annotation_choices_read':0,'auditor_model_native_session_fit_paid_GPU_calls':0,
        'model_native_fit_paid_GPU_calls':0}


def replay(root, plan_path, plan_sha):
    assert sha(plan_path) == plan_sha; plan = obj(plan_path)
    for pin in plan['pins']: assert sha(root/pin['path']) == pin['sha256'],pin['path']
    s, partition, new, previous, bge = setup(root)
    joint = JointBudgetTokenizer(new,previous)
    study = s/'epoch18'; proofs = []; phases = {}; counts = {}; priorities = {}
    agreements = {'full_order':0,'candidate_set':0,'top2_set':0}
    for phase in ('development','confirmation'):
        run = study/'runs'/phase
        if not (run/'popen-attempt.json').exists(): continue
        records = rows(run/'records.jsonl') if (run/'records.jsonl').exists() else []
        runtime = obj(run/'runtime.json') if (run/'runtime.json').exists() else None
        pc = {'requests':0,'NLI_pairs':0,'new_reader_pairs':0,'previous_reader_pairs':0,'NLI_tokens':0,'BGE_texts':0,'BGE_batches':0}
        if runtime:
            receipt = runtime['receipt']
            assert receipt['previous_reader'] == receipt['nli']
            assert receipt['previous_reader']['model_sha256'] == MODEL_SHA
            assert receipt['previous_reader']['revision'] == MODEL_REV
            assert receipt['previous_reader']['tokenizer_sha256'] == TOKENIZER_SHA
            assert receipt['new_reader']['revision'] == NEW_REV
            assert receipt['new_reader']['original_checkpoint_sha256'] == NEW_WEIGHT
            assert receipt['new_reader']['tokenizer_sha256'] == NEW_SPM
            backend_sha = hashlib.sha256(new.to_str().encode()).hexdigest()
            assert backend_sha == receipt['new_reader']['tokenizer']['converted_backend_sha256']
            assert receipt['new_reader']['tokenizer']['cls_id'] == new.token_to_id('[CLS]')
            assert receipt['new_reader']['tokenizer']['sep_id'] == new.token_to_id('[SEP]')
            assert receipt['old_base_NLI_session_initialized'] and receipt['no_initialization_model_forwards']
            assert receipt['previous_reader_actual_same_premise'] and receipt['no_not_pairing']
        for row in records:
            state = row['input']['state']; h = row['input']['questions']['decision']['criteria']['Yes']
            d = row['response']['diagnostics']['decision']; assert d['source_state'] == state
            assert d['source_state_sha256'] == hashlib.sha256(state.encode()).hexdigest()
            units = partition(state,joint,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
            assert d['source_units'] == units and d['full_source_partition'] and not d['source_partition_has_overlap']
            assert ''.join(state[u['start']:u['end']] for u in units) == state
            assert d['chunk_spans'] == [[u['start'],u['end']] for u in units]
            assert d['total_chunks'] == len(units) and d['ranking_candidate_depth'] == min(40,len(units))
            priority = M.priority(state,units,joint); check_priority(d['definition_priority'],priority,state,units,new,previous)
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
                arm = d['arms'][name]
                result,new_encoding,previous_encoding = verify_pack(arm,state,units,order,h,new,previous,priority)
                feeds = [('new_decoding',new_encoding,new)]
                if name == 'ruvector_top2': feeds.append(('previous_decoding',previous_encoding,previous))
                for field,encoding,tokenizer in feeds:
                    dec = arm[field]
                    assert dec['input_ids'] == encoding.ids and dec['attention_mask'] == encoding.attention_mask
                    assert dec['token_type_ids'] == encoding.type_ids and all(v==1 for v in encoding.attention_mask)
                    assert encoding.ids[0] == tokenizer.token_to_id('[CLS]')
                    assert encoding.ids[-1] == tokenizer.token_to_id('[SEP]')
                    assert encoding.type_ids[0] == 0 and encoding.type_ids[-1] == 1
                    assert dec['actual_model_pair_tokens'] == len(encoding.ids) <= 512
                    assert dec['truncated'] is False and dec['padding_tokens'] == 0
                    if field == 'new_decoding':
                        assert dec['actual_model_inputs'] == ['input_ids','attention_mask','token_type_ids']
                        assert dec['model_revision'] == NEW_REV and dec['original_checkpoint_sha256'] == NEW_WEIGHT
                        assert dec['converted_tokenizer_backend_sha256'] == backend_sha
                        pc['new_reader_pairs'] += 1
                    else:
                        assert dec['actual_graph_inputs'] == ['attention_mask','input_ids']
                        assert dec['active_Unigram_policy_pair_tokens'] == len(encoding.ids)
                        assert dec['model_revision'] == MODEL_REV and dec['onnx_sha256'] == MODEL_SHA
                        pc['previous_reader_pairs'] += 1
                    pc['NLI_pairs'] += 1; pc['NLI_tokens'] += len(encoding.ids)
                proof['arms'][name] = {'selected_unit_ids':result['selected'],'source_spans':result['spans'],
                    'new_reader_tokens':len(new_encoding.ids),'previous_reader_tokens':len(previous_encoding.ids),
                    'numeric_retained':sum(x['retained'] for x in result['numbers'])}
            primary = d['arms']['ruvector_top2']
            control = {'state':primary['premise'],'questions':row['input']['questions']}
            assert d['baseline_control_input'] == control and d['baseline_control_source_chunk_ids'] == primary['chunk_ids']
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
            P.counters_evidence(counters,pc,complete)
        phases[phase] = {'complete':complete,'scored_request_counts':pc,
                         'actual_terminal_counters':terminal['execution_after_close']['counters'] if terminal else None}
        for key,value in pc.items(): counts[key] = counts.get(key,0)+value
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'scope':'Independent actual saved source/priority/BOTH-reader-tokenfeeds/matchedselector/native-vector/counter replay. No semantic sufficiency, arithmetic truth or absence inference from retrieval misses.',
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
