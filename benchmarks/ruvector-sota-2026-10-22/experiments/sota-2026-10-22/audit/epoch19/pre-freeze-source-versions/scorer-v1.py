"""Independent, stdlib-only replay of frozen engineering qualification receipts.

This module imports no candidate, tokenizer, tensor, native or benchmark code.
The six direct fixture results cannot promote or submit any benchmark system.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / 'protocol.json'
PROTOCOL_REL = 'experiments/sota-2026-10-22/audit/epoch19/protocol.json'
ORDER = ('Entailment', 'Contradiction', 'NotMentioned')
RAW_INDEX = {'contradiction': 0, 'neutral': 1, 'entailment': 2}
SHA = re.compile(r'^[0-9a-f]{64}$')


class InvalidReceipt(ValueError):
    pass


def demand(value, message):
    if not value:
        raise InvalidReceipt(message)


def number(value):
    demand(type(value) in (int, float) and math.isfinite(value), 'finite real number required')
    return float(value)


def count(value):
    demand(type(value) is int and value >= 0, 'nonnegative literal integer count required')
    return value


def close(actual, expected, tolerance=1e-10):
    return abs(number(actual) - number(expected)) <= tolerance


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_identity(path, relative=None):
    raw = Path(path).read_bytes()
    return {'path': relative or str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def probability_replay(logits):
    demand(isinstance(logits, list) and len(logits) == 3, 'three raw C/N/E logits required')
    z = [number(x) for x in logits]
    peak = max(z)
    exp = [math.exp(x - peak) for x in z]
    mass = math.fsum(exp)
    return {name: exp[index] / mass for name, index in zip(ORDER, (2, 0, 1))}


def prediction(p):
    return max(ORDER, key=lambda name: p[name])


def proper_scores(rows, fixtures):
    scores = []
    for row, fixture in zip(rows, fixtures):
        p = row['typed_probabilities']; target = fixture['expected_typed_label']
        loss = -math.log(p[target]) if p[target] > 0 else None
        scores.append({'fixture_id': fixture['id'],
            'Brier_sum_over_three_classes': math.fsum((p[name] - int(name == target)) ** 2 for name in ORDER),
            'NLL': loss, 'NLL_is_positive_infinity': loss is None})
    return {'n': len(scores), 'per_fixture': scores,
        'Brier': math.fsum(row['Brier_sum_over_three_classes'] for row in scores) / len(scores),
        'NLL': None if any(row['NLL'] is None for row in scores) else math.fsum(row['NLL'] for row in scores) / len(scores),
        'NLL_is_positive_infinity': any(row['NLL'] is None for row in scores),
        'scope': 'These three public engineering fixtures only; no benchmark estimate'}


def engineering_reference(fixtures):
    vocab = ('lamp', 'on', 'not', 'box', 'blue')
    def words(text):
        return Counter(re.findall(r'[a-z]+', text.lower()))
    def vector(text):
        w = words(text)
        return [w[token] for token in vocab] + [0] * 379
    documents = [vector(row['premise']) for row in fixtures]
    queries = [vector(row['hypothesis']) for row in fixtures]
    cosines, ordering, lexical = [], [], []
    for row, q in zip(fixtures, queries):
        qnorm = math.fsum(x*x for x in q)
        demand(qnorm > 0, 'nonzero deterministic query required')
        values = []
        for v in documents:
            norm = math.fsum(x*x for x in v)
            demand(norm > 0, 'nonzero deterministic document required')
            values.append(math.fsum(x*y for x, y in zip(v, q)) / math.sqrt(norm*qnorm))
        cosines.append(values)
        ordering.append(sorted(range(3), key=lambda index: (-values[index], index)))
        qw = words(row['hypothesis'])
        overlap = [sum((qw & words(doc['premise'])).values()) for doc in fixtures]
        lexical.append(sorted(range(3), key=lambda index: (-overlap[index], index)))
    return {'vectors': documents, 'query_vectors': queries, 'cosine_similarity': cosines,
        'cosine_distance': [[1-x for x in values] for values in cosines],
        'cosine_order': ordering, 'lexical_order': lexical}


def validate_plan(plan, protocol):
    demand(plan.get('schema_version') == 1 and plan.get('epoch') == 19, 'exact epoch19 plan required')
    demand(plan.get('source_checkpoint') == protocol['source_head'], 'exact current public source head required')
    demand(plan.get('study_id') == 'native-semantic-precision-qualification-e19', 'wrong study scope')
    demand(plan.get('audit_protocol') == file_identity(PROTOCOL_PATH, PROTOCOL_REL), 'exact independent protocol identity required')
    demand(plan.get('spec_sha256') == protocol['parent_spec']['sha256'], 'parent spec identity changed')
    demand(plan.get('native_addendum_sha256') == protocol['native_addendum']['sha256'], 'native addendum identity changed')
    for name in ('train', 'calibration', 'datasets', 'confirmation'):
        demand(not plan.get(name), 'benchmark/training/calibration/confirmation role forbidden: ' + name)
    expected = {'native_batches': 1, 'worker_attempts': 1, 'threads': 2, 'interop_threads': 1,
        'seconds_per_batch': 600, 'seconds_per_decision': 30, 'candidate_configs': 1,
        'paid_calls': 0, 'GPU_calls': 0, 'nli_forwards': 6, 'native_invocations': 1,
        'native_queries': 3, 'other_model_forwards': 0, 'benchmark_corpora': 0}
    for key, value in expected.items():
        demand(type(plan['limits'].get(key)) is int and plan['limits'][key] == value, 'frozen limit changed: ' + key)


def validate_model(raw, protocol):
    model = raw['model_provenance']; expected = protocol['model']
    for key in ('repo', 'revision', 'versions', 'architecture'):
        reference = expected[key]
        if key == 'architecture':
            reference = {k: reference[k] for k in ('layers', 'hidden_size', 'attention_heads', 'classes')}
        demand(model.get(key) == reference, 'model provenance changed: ' + key)
    assets = [{k: row[k] for k in ('path', 'bytes', 'sha256')} for row in expected['assets']]
    demand(model.get('asset_identities') == assets, 'all six original licensed asset identities required')
    by_name = {Path(row['path']).name: row['sha256'] for row in assets}
    demand(model.get('original_checkpoint_sha256') == by_name['pytorch_model.bin'], 'checkpoint hash changed')
    demand(model.get('config_sha256') == by_name['config.json'], 'config hash changed')
    demand(model.get('raw_label_indices') == RAW_INDEX, 'literal C0/N1/E2 source mapping changed')
    demand(model.get('typed_order') == list(ORDER), 'canonical typed order changed')
    loading = model['loading_info']
    for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'):
        demand(key in loading and loading[key] == [], 'strict source checkpoint load coverage failed: ' + key)
    flags = model['loading_flags']
    for key, value in {'local_files_only': True, 'trust_remote_code': False, 'use_safetensors': False,
        'weights_only': True, 'torch_dtype': 'torch.float32', 'output_loading_info': True}.items():
        demand((flags.get(key) is value) if type(value) is bool else flags.get(key) == value, 'fixed CPU loader flag changed: ' + key)
    inventory = model['source_storage_dtype_inventory']
    demand(isinstance(inventory, dict) and inventory, 'actual original checkpoint storage inventory required')
    demand(all(isinstance(k, str) and k.startswith('torch.') and count(v) > 0 for k, v in inventory.items()), 'storage dtype inventory must contain actual positive tensor counts')
    fp = raw['fp32_state']; iq = raw['int8_state']
    demand(SHA.fullmatch(fp['sha256']) and SHA.fullmatch(iq['sha256']), 'actual tensor state hashes required')
    demand(fp['sha256'] != iq['sha256'], 'distinct pre/postquant tensor states required')
    demand(count(fp['parameter_count']) > 0, 'actual loaded parameter count required')
    demand(fp['parameter_dtypes'] == ['torch.float32'] and fp['devices'] == ['cpu'], 'exact FP32 CPU loaded state required')
    demand(isinstance(fp['buffer_dtypes'], list), 'actual buffer dtype inventory required')
    allowed_buffers = {'torch.float32', 'torch.int64', 'torch.int32', 'torch.int16', 'torch.int8', 'torch.uint8', 'torch.bool'}
    demand(set(fp['buffer_dtypes']).issubset(allowed_buffers), 'floating buffer fidelity must remain FP32')
    c = fp['classifier']
    demand(c.get('weight_shape') == [3,1536] and c.get('bias_shape') == [3], 'actual threeclass classifier tensor shapes required')
    demand(c.get('weight_dtype') == c.get('bias_dtype') == 'torch.float32', 'classifier FP32 dtype required')
    for key in ('eval', 'inference_mode', 'deterministic_algorithms'):
        demand(fp.get(key) is True, 'FP32 inference state invalid: ' + key)
    demand(fp.get('autocast') is False and fp.get('threads') == 2 and fp.get('interop_threads') == 1, 'FP32 CPU thread/autocast state invalid')
    names = fp['eligible_linear_modules']
    demand(isinstance(names, list) and names and all(isinstance(v, str) for v in names) and len(set(names)) == len(names), 'unique eligible Linear inventory required')
    demand(iq['eligible_linear_modules'] == names, 'pre/postquant eligible inventory drift')
    converted = iq['quantized_linear_modules']
    demand(count(iq['quantized_linear_count']) == len(names) == len(converted), 'every eligible Linear must be dynamically quantized once')
    demand([row['name'] for row in converted] == names, 'exact named Linear conversion coverage required')
    demand(all(row['weight_dtype'] == 'torch.qint8' and isinstance(row['shape'], list) and len(row['shape']) == 2 for row in converted), 'actual qint8 Linear weight receipts required')
    demand(iq.get('fbgemm') is True and iq.get('same_model_object') is True and iq.get('inplace') is True, 'same loaded model in-place fbgemm conversion required')
    demand(iq.get('eval') is True and iq.get('inference_mode') is True and iq.get('autocast') is False, 'INT8 eval/inference/autocast state invalid')
    demand(iq.get('threads') == 2 and iq.get('interop_threads') == 1 and iq.get('device') == 'cpu', 'INT8 CPU resource state invalid')
    demand(iq.get('quantization_recipe') == expected['quantization'], 'exact fixed quantization recipe required')


def validate_tokenizer(tokenizer, protocol):
    expected = {Path(row['path']).name: row['sha256'] for row in protocol['model']['assets']}
    demand(tokenizer['spm_sha256'] == expected['spm.model'], 'original SentencePiece identity required')
    demand(SHA.fullmatch(tokenizer['converted_backend_sha256']), 'actual converted tokenizer backend hash required')
    demand(tokenizer.get('pair_format') == '[CLS]premise[SEP]hypothesis[SEP]', 'pair serialization format changed')
    for name in ('cls_id', 'sep_id', 'pad_id', 'unk_id'):
        count(tokenizer[name])
    demand(len({tokenizer['cls_id'], tokenizer['sep_id'], tokenizer['pad_id'], tokenizer['unk_id']}) == 4, 'distinct actual special token identities required')


def validate_feed(row, fixture, tokenizer):
    for field in ('premise', 'hypothesis'):
        demand(row[field] == fixture[field], 'direct literal pair changed: ' + field)
    demand(row['fixture_id'] == fixture['id'] and row['fixture_sha256'] == fixture['sha256'], 'frozen canary identity changed')
    ids, mask, types, offsets = (row[k] for k in ('input_ids', 'attention_mask', 'token_type_ids', 'offsets'))
    demand(isinstance(ids, list) and 5 <= len(ids) <= 512, 'full exact singleton token pair required')
    demand(all(type(value) is int and value >= 0 for value in ids), 'nonnegative literal token IDs required')
    demand(mask == [1] * len(ids), 'padding/clipping or invalid attention mask')
    demand(isinstance(types, list) and len(types) == len(ids) and all(type(x) is int for x in types), 'literal token type feed required')
    demand(ids[0] == tokenizer['cls_id'] and ids[-1] == tokenizer['sep_id'] and ids.count(tokenizer['sep_id']) == 2, 'actual CLS/PSEP/HSEP serialization invalid')
    separator = ids.index(tokenizer['sep_id'])
    demand(types == [0] * (separator + 1) + [1] * (len(ids) - separator - 1), 'exact A0/B1 pair segment IDs required')
    demand(tokenizer['pad_id'] not in ids, 'literal pair unexpectedly contains padding')
    demand(isinstance(offsets, list) and len(offsets) == len(ids), 'actual source token offsets required')
    last_start = {0: 0, 1: 0}
    for index, pair in enumerate(offsets):
        demand(isinstance(pair, (list, tuple)) and len(pair) == 2 and all(type(x) is int for x in pair), 'integer offset pair required')
        a, b = pair; segment = types[index]
        text = fixture['premise'] if segment == 0 else fixture['hypothesis']
        demand(0 <= a <= b <= len(text), 'token offset escapes actual original source')
        if index in (0, separator, len(ids)-1):
            demand(list(pair) == [0,0], 'special token source offsets must be zero')
        else:
            demand(a >= last_start[segment], 'source token offsets not monotonic within segment')
            last_start[segment] = a
    demand(row.get('truncated') is False and row.get('padding') is False, 'explicit no truncation or padding receipt required')
    demand(row.get('feed_dtype') == 'torch.int64' and row.get('feed_device') == 'cpu' and row.get('batch_size') == 1, 'actual singleton int64 CPU feed required')
    demand(row.get('raw_logit_dtype') in ('float32','torch.float32') and row.get('raw_logit_shape') == [1,3], 'actual singleton FP32 logits required')
    elapsed = number(row['elapsed_seconds'])
    demand(0 <= elapsed <= 30, 'frozen per-forward30second limit exceeded')
    replay = probability_replay(row['raw_logits'])
    p = row['typed_probabilities']
    demand(isinstance(p, dict) and set(p) == set(ORDER), 'literal three typed probabilities required')
    demand(all(0 <= number(p[name]) <= 1 for name in ORDER), 'probability outside unit interval')
    demand(abs(math.fsum(p[name] for name in ORDER) - 1) <= 1e-6, 'raw probability mass exceeds frozen tolerance; no repair')
    demand(all(close(p[name], replay[name]) for name in ORDER), 'saved raw logit softmax T1 replay disagrees')
    demand(row['prediction'] == prediction(replay), 'saved typed prediction disagrees with fixed canonical argmax')
    return replay


def validate_native(trace, fixtures, protocol):
    reference = engineering_reference(fixtures)
    demand(trace['sourceIDs'] == [row['id'] for row in fixtures], 'native source-ID order changed')
    demand(trace['premises'] == [row['premise'] for row in fixtures] and trace['hypotheses'] == [row['hypothesis'] for row in fixtures], 'native trace borrowed or rewrote source text')
    demand(trace['bundle'] == {k: reference[k] for k in ('vectors','query_vectors')}, 'deterministic literal native vectors changed')
    demand(trace['initial_length'] == 0 and trace['final_length'] == 3, 'fresh threevector native index required')
    demand(trace.get('native_selection_affects_NLI') is False, 'native retrieval must not rewrite direct canary pairs')
    output = trace['raw_native_output']; native = protocol['native']
    binary = next(row for row in native['files'] if row['path'].endswith('/ruvector.node'))
    demand(output['native_binary_sha256'] == binary['sha256'] and output['package_version'] == native['package_version'] and output['native'] is True, 'exact actual RuVector native backend required')
    demand(output['vectors'] == 3 and SHA.fullmatch(output['bundle_sha256']), 'actual complete native index and bundle identity required')
    demand(trace.get('bundle_serialization') == 'UTF8 JSON ensure_ascii=False indent=2 allow_nan=False followed by LF', 'exact native bundle byte serialization required')
    bundle_bytes = (json.dumps(trace['bundle'], ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    demand(output['bundle_sha256'] == hashlib.sha256(bundle_bytes).hexdigest(), 'actual native helper read a different bundle byte identity')
    queries = output['queries']; demand(isinstance(queries,list) and len(queries)==3, 'exactly three actual native search receipts required')
    for index, query in enumerate(queries):
        demand(query['ids'] == reference['cosine_order'][index], 'actual full native order differs from independent cosine reference')
        demand(len(set(query['ids'])) == 3 and set(query['ids']) == {0,1,2}, 'native search candidate IDs incomplete or duplicated')
        demand(number(query['latency_ms']) >= 0, 'native measured search latency required')
    if trace['raw_scores_available']:
        for query in queries:
            demand(len(query['scores']) == 3 and all(math.isfinite(number(value)) for value in query['scores']), 'exposed native scores must be finite; numeric orientation unasserted')
    else:
        demand(trace['raw_scores_available'] is False, 'native score availability must be literal boolean')
    claimed = trace['reference']
    for key in ('cosine_order','lexical_order'):
        demand(claimed[key] == reference[key], 'claimed reference order disagrees with independent replay: ' + key)
    for key in ('cosine_similarity','cosine_distance'):
        demand(isinstance(claimed[key],list) and len(claimed[key]) == 3, 'complete reference cosine rows required')
        for actual, expected in zip(claimed[key],reference[key]):
            demand(len(actual)==3 and all(close(x,y) for x,y in zip(actual,expected)), 'reference cosine arithmetic disagrees')
    return reference


def validate_counters(counters):
    expected = {'model_initializations':1,'quantization_initializations':1,
        'nli_forward_pairs_attempted':6,'nli_forward_pairs_completed':6,
        'fp32_forwards_attempted':3,'fp32_forwards_completed':3,'int8_forwards_attempted':3,'int8_forwards_completed':3,
        'native_invocations':1,'native_queries':3,'other_model_forwards':0,
        'BGE_forwards':0,'ORT_sessions':0,'previous_reader_forwards':0,'native104_calls':0,
        'benchmark_HTTP_requests':0,'benchmark_corpora':0,'paid_API_calls':0,'GPU_calls':0,
        'train_fits':0,'calibration_fits':0,'CONF_calls':0}
    for key, expected_value in expected.items():
        demand(count(counters[key]) == expected_value, 'actual frozen process count violated: ' + key)


def validate_execution(execution):
    demand(isinstance(execution,dict), 'independent outer terminal execution receipt required')
    for key in ('qualification_worker_attempts','verified_worker_starts'):
        demand(count(execution[key]) == 1, 'exactly one actual qualification process required')
    demand(type(execution['worker_exit_code']) is int and execution['worker_exit_code'] == 0, 'successful terminal worker exit required')
    demand(0 <= number(execution['elapsed_seconds']) <= 600, 'actual full execution including cleanup must fit600seconds')
    affinity = execution['CPU_affinity']
    demand(isinstance(affinity,list) and 1 <= len(affinity) <= 2 and len(set(affinity)) == len(affinity) and all(type(x) is int and x>=0 for x in affinity), 'actual CPU affinity must use at most two CPUs')
    demand(count(execution['worker_pid']) > 0 and execution['worker_pgid'] == execution['worker_pid'], 'owned worker process group required')
    demand(count(execution['native_helper_pid']) > 0 and execution['native_helper_pid'] != execution['worker_pid'], 'actual distinct native helper PID required')
    demand(number(execution['user_seconds']) >= 0 and number(execution['system_seconds']) >= 0 and count(execution['peak_RSS_bytes']) > 0, 'actual outer CPU/RSS resource receipts required')
    cleanup = execution['cleanup']
    for key in ('worker_exited','native_helper_exited','process_group_empty'):
        demand(cleanup.get(key) is True, 'terminal owned process cleanup unproven: ' + key)
    demand(cleanup.get('owned_live_pids') == [], 'owned processes still live or unverified')


def evaluate(plan, raw, execution=None):
    """Replay receipts only. Missing receipts never become invented zero counts."""
    protocol = json.loads(PROTOCOL_PATH.read_text())
    report = {'schema_version':1,'epoch':19,'kind':'INDEPENDENT_ENGINEERING_QUALIFICATION_REPLAY',
        'checks_passed':False,'engineering_qualified':False,'accepted':False,
        'status':'INCONCLUSIVE_INVALID_OR_INCOMPLETE_EXECUTION','failures':[],
        'benchmark_promotion_allowed':False,'submission_allowed':False,'CONF_consumed':False,
        'official_score':None,'official_rank':None,'cause_of_epoch18_collapse':'UNPROVEN',
        'interpretation':'Three exposed CC0 engineering fixtures and a deterministic-vector native integration trace; no legal/benchmark generalization or SOTA claim.'}
    try:
        validate_plan(plan,protocol)
        demand(raw.get('schema_version') == 1 and raw.get('epoch') == 19, 'actual epoch19 raw receipts required')
        demand(raw.get('status') == 'COMPLETED', 'complete terminal worker raw receipts required')
        validate_model(raw,protocol); validate_tokenizer(raw['tokenizer'],protocol)
        rows = raw['forwards']; fixtures = protocol['fixtures']
        demand(isinstance(rows,list) and len(rows)==6, 'exactly six actual ordered forward receipts required')
        demanded_order = protocol['procedure']['forward_order']
        demand([[row['precision'],row['fixture_id']] for row in rows] == demanded_order, 'three direct FP32 forwards before three direct INT8 forwards required')
        replay = []
        for row, fixture in zip(rows,fixtures*2):
            replay.append(validate_feed(row,fixture,raw['tokenizer']))
        feed_fields = ('premise','hypothesis','input_ids','attention_mask','token_type_ids','offsets','feed_dtype','feed_device','batch_size')
        for fp, iq in zip(rows[:3],rows[3:]):
            demand(all(fp[k] == iq[k] for k in feed_fields), 'same literal source and exact actual token feed required across precisions')
        validate_native(raw['native_trace'],fixtures,protocol)
        validate_counters(raw['counters'])
        validate_execution(execution if execution is not None else raw.get('execution'))
        fp_correct = sum(row['prediction'] == fixture['expected_typed_label'] for row,fixture in zip(rows[:3],fixtures))
        iq_correct = sum(row['prediction'] == fixture['expected_typed_label'] for row,fixture in zip(rows[3:],fixtures))
        same = sum(fp['prediction'] == iq['prediction'] for fp,iq in zip(rows[:3],rows[3:]))
        deltas = [{name:abs(fp[name]-iq[name]) for name in ORDER} for fp,iq in zip(replay[:3],replay[3:])]
        maximum_delta = max(value for row in deltas for value in row.values())
        gates = {'FP32_3_of_3_correct':fp_correct==3,'INT8_3_of_3_correct':iq_correct==3,
            'all_INT8_labels_match_FP32':same==3,'maximum_probability_drift_le_0_05':maximum_delta<=0.05,
            'all_source_distribution_feed_native_counter_resource_cleanup_replays':True}
        qualified = all(gates.values())
        report.update(checks_passed=True,engineering_qualified=qualified,
            status='ENGINEERING_QUALIFIED_ONLY' if qualified else 'REJECTED_ENGINEERING_QUALIFICATION',
            gates=gates,FP32_correct=fp_correct,INT8_correct=iq_correct,labels_matching=same,
            maximum_absolute_per_class_probability_delta=maximum_delta,per_fixture_probability_deltas=deltas,
            FP32_proper_scores=proper_scores(rows[:3],fixtures),INT8_proper_scores=proper_scores(rows[3:],fixtures),
            FP32_predictions=[row['prediction'] for row in rows[:3]],INT8_predictions=[row['prediction'] for row in rows[3:]],
            actual_qualification_forwards=6,actual_benchmark_HTTP_requests=0,actual_benchmark_corpus_batches=0,
            used_benchmark_confirmation_identities=[],all_unused_epoch_slots_must_close=True)
    except (InvalidReceipt,KeyError,TypeError,ValueError,OverflowError) as error:
        report['failures'].append({'type':type(error).__name__,'message':str(error)})
    return report


def read_json(path):
    def reject(value):
        raise ValueError('Nonfinite JSON literal forbidden: '+value)
    return json.loads(Path(path).read_text(),parse_constant=reject)


def main():
    parser=argparse.ArgumentParser()
    for key in ('plan','raw','out'):
        parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--execution',type=Path)
    args=parser.parse_args()
    plan=read_json(args.plan);raw=read_json(args.raw)
    execution=read_json(args.execution) if args.execution else None
    report=evaluate(plan,raw,execution)
    report['plan_sha256']=file_identity(args.plan)['sha256']
    report['raw_receipt_identity']=file_identity(args.raw)
    report['outer_execution_identity']=file_identity(args.execution) if args.execution else None
    report['audit_protocol']=file_identity(PROTOCOL_PATH,PROTOCOL_REL)
    report['scorer_source_sha256']=file_identity(Path(__file__))['sha256']
    if raw.get('plan_sha256') != report['plan_sha256']:
        report.update(checks_passed=False,engineering_qualified=False,status='INCONCLUSIVE_INVALID_OR_INCOMPLETE_EXECUTION')
        report['failures'].append({'type':'InvalidReceipt','message':'raw receipt does not bind exact actual plan bytes'})
    with args.out.open('x') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'checks_passed':report['checks_passed'],'engineering_qualified':report['engineering_qualified'],'status':report['status'],'out':str(args.out)}))


if __name__=='__main__':
    main()
