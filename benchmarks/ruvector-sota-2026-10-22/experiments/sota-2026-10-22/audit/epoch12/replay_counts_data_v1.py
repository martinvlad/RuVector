"""Independent saved-count, probability, resource and role audit; no inference imports."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import statistics

HERE = Path(__file__).resolve().parent
FP32 = '9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b'
INT8 = 'f28cc7e69eb2834597c5ef2336f2adb7398b7bcb019282fb3f11d0130a3c0010'
NAMES = ['ruvector_top2', 'same_nli_lexical_top2', 'same_nli_positional_first2',
         'native104_on_ruvector_evidence']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def close(first, second):
    assert math.isclose(first, second, rel_tol=0, abs_tol=1e-10), (first, second)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def percentile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def answer(response, name):
    if name == 'native104_on_ruvector_evidence':
        response = response['baseline104_response']
    elif name != 'ruvector_top2':
        response = response['ablation_responses'][name]
    return response['answers']['decision']


def score(answer_object, gold):
    probabilities = answer_object['probabilities']
    assert answer_object['type'] == 'choice' and set(probabilities) == {'Yes', 'No'}
    assert all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities.values())
    # Preserve the frozen scorer's 1e-3 validity tolerance for Native104.
    assert abs(sum(probabilities.values()) - 1) <= 1e-3
    assert answer_object['choice'] == max(sorted(probabilities), key=lambda label: probabilities[label])
    return (int(answer_object['choice'] == gold),
            sum((probabilities[label] - float(label == gold)) ** 2 for label in ('Yes', 'No')),
            -math.log(max(1e-15, probabilities[gold])))


def run(root, frozen_project=None):
    s = root / 'experiments/sota-2026-10-22'
    e = s / 'epoch12'
    actual = e / 'runs/development'
    data = s / 'legal-transfer/epoch12'
    contract, plan = load(data / 'data-contract.json'), load(e / 'plan.json')
    source_by_role = {'train': rows(data / 'train-sanity6.jsonl'),
                      'development': rows(data / 'development24.jsonl')}
    metadata = {'train': load(data / 'train-allowlist.json'),
                'development': load(data / 'dev-allowlist.json')}
    confirmation = load(data / 'confirmation-allowlist.json')
    registry = load(data / 'eligibility-manifest.json')
    assert contract['calibration'] == [] and not contract['fitting']['supervised_fit']
    assert not contract['fitting']['model_precision_or_threshold_selection']
    assert plan['training_feature_questions'] == 0 and plan['training_questions'] == plan['train_sanity_questions'] == 6
    assert len(confirmation['records']) == 48 and len({x['source_group'] for x in confirmation['records']}) == 16
    assert len(registry['excluded_document_ids']) == 173 and len(registry['eligible_document_ids']) == 234
    assert len(registry['training_sanity_reuse_document_ids']) == 24
    old_groups = {'original-contractnli:' + str(i) for i in registry['excluded_document_ids']}
    reserved_groups = {x['source_group'] for x in confirmation['records']}
    train_groups = {x['source_group'] for x in source_by_role['train']}
    dev_groups = {x['source_group'] for x in source_by_role['development']}
    assert len(train_groups) == 2 and train_groups <= old_groups
    assert len(dev_groups) == 8 and not dev_groups & (old_groups | reserved_groups)
    assert not train_groups & reserved_groups
    for role, key in [('train', 'train'), ('development', 'development')]:
        name = 'train-sanity6.jsonl' if role == 'train' else 'development24.jsonl'
        assert sha(data / name) == contract[key]['sha256']
        assert [x['id'] for x in source_by_role[role]] == [x['id'] for x in metadata[role]['records']]
    original = source_by_role['train'] + source_by_role['development']
    start, wire, record, server = [rows(actual / name) for name in
                                  ('started-requests.jsonl', 'wire.jsonl', 'records.jsonl', 'server-audit.jsonl')]
    assert len(start) == len(wire) == len(record) == len(server) == len(original) == 30
    assert [x['id'] for x in original] == [x['id'] for x in start] == [x['id'] for x in wire] == [x['id'] for x in record]
    values = {role: {name: [] for name in NAMES} for role in source_by_role}
    bundles = set()
    bge_texts = bge_batches = fp32_tokens = int8_tokens = 0
    paired_binary_agreements = paired_typed_agreements = 0
    latencies = {'train': [], 'development': []}
    for index, (source, started, transport, measured, served) in enumerate(zip(original, start, wire, record, server)):
        role = 'train' if index < 6 else 'development'
        operation = 'train_sanity' if role == 'train' else 'predict'
        assert measured['measured_phase'] == started['phase'] == transport['phase'] == role
        assert source['split'] == ('train_sanity' if role == 'train' else 'dev')
        envelope = json.loads(transport['request'])
        response = json.loads(transport['response'])
        assert set(envelope) == ({'state', 'questions', 'operation', 'training_example_id'} if role == 'train'
                                 else {'state', 'questions', 'operation'})
        assert envelope['operation'] == started['operation'] == transport['operation'] == served['operation'] == operation
        if role == 'train':
            assert envelope['training_example_id'] == served['training_example_id'] == source['id']
            assert response['training_sanity_example_id'] == source['id']
        else:
            assert served['training_example_id'] is None and 'precision_fidelity' not in response
            assert 'quantized_primary_response' not in response
        inp = {key: envelope[key] for key in ('state', 'questions')}
        assert inp == source['input'] == measured['input'] and envelope == measured['transport_input']
        assert response == measured['response'] and source['evaluation'] == measured['evaluation']
        assert digest(canonical(inp).encode()) == source['input_sha256'] == measured['input_sha256']
        assert started['request'] == transport['request']
        assert digest(transport['request'].encode()) == started['request_sha256'] == transport['request_sha256'] == served['request_sha256']
        assert digest(transport['response'].encode()) == transport['response_sha256'] == served['response_sha256']
        assert transport['status'] == served['status'] == 200 and served['ok'] and served['error'] is None
        assert served['cost_per_decision_usd'] is None and served['usage']['paid_calls'] == 0
        close(transport['elapsed_s'], measured['elapsed_s'])
        latencies[role].append(transport['elapsed_s'])
        before, after = served['usage']['execution_before']['counters'], served['usage']['execution_after']['counters']
        assert before['requests_completed'] == index and after['requests_completed'] == index + 1
        assert after['nli_fp32_forward_pairs_completed'] == 3 * (index + 1)
        assert after['nli_int8_diagnostic_forward_pairs_completed'] == min(index + 1, 6)
        assert after['training_sanity_requests_completed'] == min(index + 1, 6)
        assert served['usage']['nli_singleton_pairs'] == (4 if role == 'train' else 3)
        diagnostic = response['diagnostics']['decision']
        assert diagnostic['source_state'] == inp['state']
        assert digest(inp['state'].encode()) == diagnostic['source_state_sha256']
        descriptor = diagnostic['retrieval']['bundle_evidence']
        path = actual / 'bundles' / descriptor['relativefilename']
        assert path.name == descriptor['sha256'] + '.json' and sha(path) == descriptor['sha256']
        assert path.stat().st_size == descriptor['bytes']
        assert descriptor['sha256'] == diagnostic['retrieval']['native']['bundle_sha256']
        bundles.add(path.name)
        bundle = load(path)
        assert len(bundle['vectors']) == diagnostic['total_chunks'] and len(bundle['query_vectors']) == 1
        assert {len(v) for v in bundle['vectors'] + bundle['query_vectors']} == {384}
        assert all(math.isfinite(value) for vector in bundle['vectors'] + bundle['query_vectors'] for value in vector)
        native = diagnostic['retrieval']['native']
        assert native['native'] and native['native_binary_sha256'] == 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
        embedding = diagnostic['retrieval']['embedding']
        bge_batches += sum(embedding[k]['model_batches'] for k in ('chunks', 'query'))
        bge_texts += len(embedding['query']['examples']) + (0 if embedding['chunks']['cache_hit'] else len(embedding['chunks']['examples']))
        for section in ('chunks', 'query'):
            for example in embedding[section]['examples']:
                assert not example['truncated'] and example['raw_tokens'] == example['used_tokens'] <= 256
        for arm in diagnostic['arms'].values():
            decoding = arm['decoding']
            assert decoding['precision'] == 'FP32' and decoding['onnx_sha256'] == FP32
            assert not decoding['truncated'] and decoding['padding_tokens'] == 0 and decoding['batch_size'] == 1
            assert decoding['used_tokens'] == decoding['raw_tokens'] == decoding['actual_model_pair_tokens'] <= 512
            assert len(decoding['input_ids']) == len(decoding['attention_mask']) == len(decoding['token_type_ids']) == decoding['input_tokens']
            fp32_tokens += decoding['input_tokens']
        if role == 'train':
            pair = diagnostic['TRAIN_only_precision_pair']
            quantized = pair['quantized_decoding']
            primary = diagnostic['arms']['ruvector_top2']['decoding']
            assert pair['same_primary_packed_context'] and pair['primary_precision_always_FP32']
            assert quantized['precision'] == 'INT8_TRAIN_DIAGNOSTIC' and quantized['onnx_sha256'] == INT8
            assert not quantized['truncated'] and quantized['padding_tokens'] == 0 and quantized['batch_size'] == 1
            for key in ('input_ids', 'attention_mask', 'token_type_ids', 'input_text_sha256'):
                assert quantized[key] == primary[key]
            int8_tokens += quantized['input_tokens']
            fidelity = response['precision_fidelity']['decision']
            assert fidelity == pair['fidelity'] and fidelity['identical_feed_tokens']
            assert not fidelity['source_original_fidelity_established']
            paired_binary_agreements += int(fidelity['binary_decision_agrees'])
            paired_typed_agreements += int(fidelity['typed_decision_agrees'])
        else:
            assert 'TRAIN_only_precision_pair' not in diagnostic
        for name in NAMES:
            values[role][name].append(score(answer(response, name), source['evaluation']['gold']))
    assert len(bundles) == len(list((actual / 'bundles').glob('*.json'))) == 30
    metrics = {role: {name: {'n': len(items), 'correct': sum(x[0] for x in items),
                              'brier': statistics.mean(x[1] for x in items),
                              'nll': statistics.mean(x[2] for x in items)}
                      for name, items in arms.items()} for role, arms in values.items()}
    comparison = load(actual / 'development-comparison.json')
    train_comparison = load(actual / 'train-sanity-comparison.json')
    for role, target in [('development', comparison), ('train', train_comparison)]:
        for name, score_object in metrics[role].items():
            saved = target['metrics'][name]
            assert saved['n'] == score_object['n'] and saved['correct'] == score_object['correct']
            assert saved['strict_valid'] == score_object['n'] and saved['errors'] == 0
            close(saved['brier'], score_object['brier'])
            close(saved['nll'], score_object['nll'])
    assert [metrics['development'][name]['correct'] for name in NAMES] == [13, 10, 12, 8]
    summary, completion, resources, runtime, attempt, marker = [load(path) for path in
        (e / 'study-completion.json', actual / 'completion.json', actual / 'resources.json',
         actual / 'runtime.json', actual / 'attempt.json', actual / 'popen-attempt.json')]
    assert summary['status'] == 'REJECTED_DEV_GATE' and not summary['development_gate_passed']
    assert not comparison['frozen_development_gate_passed'] and not (e / 'runs/confirmation').exists()
    assert not summary['confirmation_consumed_or_attempted'] and not summary['confirmation_phase_attempted']
    assert summary['actual_native_attempts'] == summary['native_processes_started'] == 1
    assert summary['lifetime_native_attempts'] == 15 and summary['unspent_phase_slots'] == 1
    assert summary['allowed_further_attempts_in_closed_study'] == 0
    assert sum((e / 'runs' / phase / 'popen-attempt.json').exists() for phase in ('development', 'confirmation')) == 1
    assert completion['native_process_started'] and completion['popen_invocation_reserved']
    assert completion['exit_code'] == 0 and completion['error'] is None and completion['source_plan_unchanged']
    assert completion['wall_seconds_including_model_load'] <= 600 and completion['owned_group_cleanup']['finished_within_deadline']
    assert not completion['owned_group_cleanup']['live_members_after']
    assert marker['source_plan_sha256'] == attempt['source_plan_sha256'] == sha(e / 'plan.json')
    assert marker['at'] <= attempt['at'] and attempt['pid'] == runtime['pid']
    assert marker['lifetime_native_attempt'] == attempt['lifetime_native_attempt'] == 15
    finish = load(e / 'train-sanity-completion-lock.json')
    assert finish['plan_sha256'] == sha(e / 'plan.json') and finish['train_sanity_completed'] == 6
    assert not finish['supervised_fit'] and finish['training_feature_queries'] == 0
    assert finish['receipt']['quantized_session_released'] and not finish['receipt']['precision_selection']
    assert finish['receipt']['optimizer_fits'] == 0 and finish['receipt']['candidate_primary_precision'] == 'FP32'
    assert finish['identities'] == [{'id': x['id'], 'input_sha256': x['input_sha256']} for x in source_by_role['train']]
    assert start[5]['at'] < finish['at'] < start[6]['at']
    final = load(actual / 'final-engine.json')
    counters = final['execution_after_close']['counters']
    assert final['receipt_after_close']['binary_sha256'] == 'e4db4b945a91b5cb8937765236e180763e8a3f4866b791e0f71a98d0018c289d'
    for key in ('requests', 'native104_requests', 'native_core_searches', 'context_partitions'):
        assert counters[key + '_attempted'] == counters[key + '_completed'] == 30
    assert counters['nli_fp32_forward_pairs_completed'] == 90 and counters['nli_int8_diagnostic_forward_pairs_completed'] == 6
    assert counters['nli_forward_pairs_attempted'] == counters['nli_forward_pairs_completed'] == 96
    assert counters['nli_fp32_input_tokens_completed'] == fp32_tokens == 43051
    assert counters['nli_int8_diagnostic_input_tokens_completed'] == int8_tokens == 2783
    assert counters['nli_input_tokens_completed'] == fp32_tokens + int8_tokens == 45834
    assert counters['bge_texts_completed'] == bge_texts == 172 and counters['bge_forward_batches_completed'] == bge_batches == 52
    assert counters['training_sanity_requests_completed'] == 6 and counters['context_packs_completed'] == 90
    assert resources['allowed_CPU_ids'] == [0, 1] and resources['configured_ORT_threads'] == 2
    cpu = sum(resources[k] for k in ('worker_cpu_user_seconds', 'worker_cpu_system_seconds',
                                    'terminated_children_cpu_user_seconds', 'terminated_children_cpu_system_seconds'))
    assert cpu <= 2 * completion['wall_seconds_including_model_load'] + 2
    latency = {role: {'p50': statistics.median(items), 'p95': percentile(items, .95), 'max': max(items)}
               for role, items in latencies.items()}
    frozen = frozen_project or e / 'project'
    for pin in plan['pins']:
        assert (frozen / pin['path']).is_file() and sha(frozen / pin['path']) == pin['sha256'], pin['path']
    assert len(plan['pins']) == 201
    snapshot = load(e / 'actual-snapshot.json')
    assert snapshot['plan_sha256'] == sha(e / 'plan.json') and len(snapshot['files']) == 51
    for pin in snapshot['files']:
        outer = e / pin['path']
        inner = frozen / 'experiments/sota-2026-10-22/epoch12' / pin['path']
        assert outer.stat().st_size == inner.stat().st_size == pin['bytes']
        assert sha(outer) == sha(inner) == pin['sha256']
    admission = load(e / 'runtime-admission.json')
    forecast = 48 * latency['development']['max'] * max(1, admission['max_confirmation_units'] / admission['max_DEV_units']) + 2 * admission['DEV_initialization_seconds'] + 60
    close(forecast, admission['projected_confirmation_seconds'])
    assert not admission['allowed'] and forecast > 600
    base = load(e / 'durable-kit/CONTINUATION.json')['execution_observed']
    totals = {'attempts': base['native_corpus_attempts_including_failed_request'] + 1,
              'completed_batches': base['native_corpus_batches_completed'] + 1,
              'successful_HTTP': base['actual_HTTP_successful_decisions'] + 30,
              'learned_feature_HTTP': base['actual_HTTP_training_feature_requests'],
              'TRAIN_sanity_HTTP': 6, 'evaluation_HTTP': base['actual_HTTP_evaluation_diagnostic_decisions'] + 24,
              'historical_failed_HTTP': base['actual_HTTP_failed_requests']}
    assert totals == {'attempts': 15, 'completed_batches': 13, 'successful_HTTP': 789,
                      'learned_feature_HTTP': 144, 'TRAIN_sanity_HTTP': 6, 'evaluation_HTTP': 639, 'historical_failed_HTTP': 2}
    assert totals['successful_HTTP'] == totals['learned_feature_HTTP'] + totals['TRAIN_sanity_HTTP'] + totals['evaluation_HTTP']
    return {'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': True,
            'audit_source': Path(__file__).name, 'audit_source_sha256': sha(Path(__file__)),
            'scope': 'Independent saved literal wire/server/records/bundle/precision-feed/token/count/role/proper-score/resource arithmetic. All201 frozen pins byte-hashed, including unusedCONF bytes only; no CONF JSON parse or model/native/session/fit execution.',
            'plan_sha256': sha(e / 'plan.json'), 'frozen_source_pins_checked': 201,
            'snapshot_files_both_actual_outer_exact': 51, 'matched_started_wire_records_server': 30,
            'TRAIN_sanity_requests': 6, 'training_feature_requests': 0, 'DEV_requests': 24, 'CONF_requests': 0,
            'errors': 0, 'finite_hash_valid_native_vectorbundles': 30, 'metrics': metrics,
            'latency_whole_HTTP_seconds': latency, 'wall_seconds': completion['wall_seconds_including_model_load'],
            'CPU_seconds_worker_plus_terminated_children': cpu, 'resources': resources, 'execution_counters': counters,
            'TRAIN_pairing': {'same_input_feed_pairs': 6, 'binary_agreements': paired_binary_agreements,
                              'typed_agreements': paired_typed_agreements, 'quantized_session_released_before_DEV': True,
                              'fitting_or_precision_selection': False, 'original_upstream_fidelity_established': False},
            'process_attempts': {'conservative_Popen_invocations': 1, 'PID_confirmed_native_process_starts': 1,
                                 'closed_cap': 2, 'unspent_slots': 1, 'allowed_further': 0},
            'runtime_forecast_seconds_NOT_executed_CONFIRM': forecast, 'cumulative': totals,
            'identities': {'prior_exposed': 173, 'new_DEV_groups_retired': 8, 'reused_TRAIN_groups_new_exposure': 0,
                           'exposed_now': 181, 'unreserved_after_fixed_draw': 226, 'CONF_reserved_groups': 16,
                           'CONF_reserved_queries': 48, 'confirmation_model_unused': True},
            'server_USD_cost_reported': None, 'paid_API_calls_verified': 0,
            'auditor_models_native_fits_paid_calls': 0, 'official_score': None, 'official_rank': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=HERE.parents[3])
    parser.add_argument('--frozen-project', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Use a new proof output path'
    proof = run(args.root, args.frozen_project)
    args.out.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'checks_passed': True, 'out_sha256': sha(args.out),
                      'TRAIN_sanity': proof['TRAIN_sanity_requests'], 'DEV': proof['DEV_requests'],
                      'errors': proof['errors'], 'cumulative': proof['cumulative']}))
