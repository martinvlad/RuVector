"""Independent E46 runtime diagnostics only. Never imports scientific code.

Reads exact public partial execution receipts and the explicitly authorized
private runtime metadata journals. No HTTP request/response bodies, feature,
vault, Gold, model decisions or probabilities are inspected or published.
"""
import hashlib
import json
import math
import os
import stat
from collections import Counter, defaultdict
from pathlib import Path

OWN = Path('/workspace/ruvector-e46-core/runtime-diagnostics-v1')
W = Path('/tmp/ruvector-sota-2026-10-22/epoch46-d3aa1b569848')
R = W / 'project'
P = 'experiments/sota-2026-10-22/epoch46/'
T = 'experiments/sota-2026-10-22/runtime/epoch46/'
ARMS = ['qwen_native_joint_context', 'qwen_lexical_joint_context',
        'qwen_source_order_joint_context']
INPUTS = []


def read(path, size, digest, visibility):
    path = Path(path)
    assert path.is_absolute() and path == path.resolve()
    assert not any(p.is_symlink() for p in (path, *path.parents))
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and before.st_size == size
        raw = stream.read(size + 1)
        after = os.fstat(stream.fileno())
    sig = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    assert sig(before) == sig(after)
    assert len(raw) == size and hashlib.sha256(raw).hexdigest() == digest
    ref = {'path': str(path.relative_to(R)) if path.is_relative_to(R) else str(path),
           'bytes': size, 'sha256': digest, 'visibility': visibility}
    INPUTS.append(ref)
    return raw


def load(path, size, digest, visibility='PUBLIC_RECEIPT'):
    return json.loads(read(path, size, digest, visibility))


def stats(values):
    values = sorted(values)
    assert values and all(type(v) in (float, int) and math.isfinite(v) for v in values)
    return {'N': len(values), 'sum': math.fsum(values),
            'mean': math.fsum(values) / len(values), 'min': values[0],
            'p50': values[math.ceil(0.50 * len(values)) - 1],
            'p95': values[math.ceil(0.95 * len(values)) - 1], 'max': values[-1]}


def emit(name, value):
    path = OWN / name
    body = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(OWN, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def main():
    raw = load(R / P / 'runs/dev/raw.json', 433392,
               '4f7fb57f0dd33dfe8b4367587af27047b915440b7023b110c8e919a917a99712')
    execution = load(R / P / 'runs/dev/execution.json', 3622,
                     '47926f6f1ad4bb3e2a7438b2c493992552125e7fb049fe9702afca51743c76f5')
    freeze = load(R / P / 'SOURCE_FREEZE.json', 22325,
                  '6b854126b849fce27def51ed1ddb7bddd5d90d4e8d4f1f3b033ac2cfdfb61e98')
    table = {row['path']: row for row in freeze['files']}
    source_refs = []
    for name in ['worker.py', 'reader.py', 'http_transport.py', 'packing.py', 'RAW_SCHEMA.json']:
        row = table[T + name]
        read(R / row['path'], row['bytes'], row['sha256'], 'PUBLIC_SOURCE_STATIC_ONLY')
        source_refs.append(row)
    private = W / 'private/run'
    http = load(private / 'HTTP_CAPTURE_INDEX.json', 1192339,
                '158e616a5b0e1ef5f503f696d9e3b74b475129a8c9dc81d26b0b5351659f5c2b',
                'PRIVATE_RUNTIME_METADATA_INPUT_NOT_PUBLISHED')
    packing = load(private / 'PACKING_JOURNAL.json', 6564925,
                   '4212037e81cbba47d400c36e96825ea3473dd4af2b9ff758cc346e9b2db97562',
                   'PRIVATE_RUNTIME_METADATA_INPUT_NOT_PUBLISHED')['proposals']
    progress_bytes = read(private / 'worker-progress.jsonl', 7008625,
                          '3679c23fbe07baa7cedbee0d383f60e8b5e636450d860d96d52674d03dd0f01d',
                          'PRIVATE_RUNTIME_METADATA_INPUT_NOT_PUBLISHED')
    progress = [json.loads(line) for line in progress_bytes.splitlines()]
    exception = read(private / 'worker.exception.txt', 931,
                     'da1bbbbc2664ff11ea8e19c952f9a0fb533641901f911d255e29b495155b57a5',
                     'PRIVATE_RUNTIME_METADATA_INPUT_NOT_PUBLISHED')
    closure = load('/workspace/ruvector-e46-audit/FAILURE_PHYSICAL_CLOSURE_INDEPENDENT.v1.json',
                   21177, 'a7713e0660f180e2e65fdf70124802486949f5350eb2b7edd9236d8d1dd76a2a')
    assert raw['epoch'] == execution['epoch'] == 46
    assert raw['plan_sha256'] == execution['plan_sha256'] == '287309e0bfc966f18f3dc8836b9e0aac781e599d5cf00f5311c887e24bd6985d'
    assert raw['counters'] == execution['operation_counters']
    assert raw['counters']['semantic_gold_decodes'] == 0
    assert raw['status'] == 'DEV_PARTIAL_NO_GOLD' and execution['status'] == 'FAILED'
    assert execution['worker_exit_code'] == 1 and raw['errors'][0]['type'] == 'TimeoutError'
    assert b'block = sock.recv(65536)' in exception and exception.endswith(b'TimeoutError: timed out\n')
    assert raw['closure_facts']['all_forecasts_closed_before_gold'] is False
    assert raw['native_state']['child_closed'] is True and raw['native_state']['exit_code'] == 0
    assert raw['reader_state']['child_closed'] is True and raw['reader_state']['exit_code'] == 0

    # Only the timing, arm, ID, token-count and server-timing fields are accessed.
    observed = []
    by_arm = defaultdict(list)
    for case in raw['cases']:
        for arm, value in case['forecasts'].items():
            assert arm in ARMS
            item = {'case_id': case['id'], 'arm': arm,
                    'forecast_id': value['forecast_id'],
                    'completion_request_ordinal': value['http_exchange']['request_ordinal'],
                    'timings_seconds': {k: value['timings'][k] for k in
                        ['request_wall_seconds', 'context_packing_seconds',
                         'model_readout_HTTP_seconds', 'packing_and_readout_seconds']},
                    'full_prompt_tokens': value['fullprompttoken_count'],
                    'server_prompt_seconds': value['server_timing']['prompt_ms'] / 1000,
                    'server_prompt_tokens': value['server_timing']['prompt_n'],
                    'server_predicted_seconds': value['server_timing']['predicted_ms'] / 1000}
            observed.append(item)
            by_arm[arm].append(item)
    assert len(observed) == raw['counters']['forecasts_completed'] == 19
    per_arm = {}
    for arm in ARMS:
        rows = by_arm[arm]
        per_arm[arm] = {'completed_forecasts': len(rows),
                       'timings_seconds': {k: stats([r['timings_seconds'][k] for r in rows])
                           for k in observed[0]['timings_seconds']},
                       'full_prompt_tokens': stats([r['full_prompt_tokens'] for r in rows]),
                       'server_reported_prompt_seconds': stats([r['server_prompt_seconds'] for r in rows])}
    all_totals = {k: math.fsum(r['timings_seconds'][k] for r in observed)
                  for k in observed[0]['timings_seconds']}
    categories = {}
    for category in sorted({row['category'] for row in http}):
        rows = [row for row in http if row['category'] == category]
        categories[category] = {'attempted': len(rows),
            'completed': sum(row['parsed_response_canonical_sha256'] is not None for row in rows),
            'observed_HTTP_wall_seconds_all_attempts': stats([row['wall_seconds'] for row in rows]),
            'request_wire_bytes_sum': sum(row['request']['bytes'] for row in rows),
            'response_wire_bytes_sum': sum(row['response']['bytes'] for row in rows)}
    completions = [row for row in http if row['category'] == 'completion']
    complete = [row for row in completions if row['parsed_response_canonical_sha256'] is not None]
    failed = [row for row in completions if row['parsed_response_canonical_sha256'] is None]
    assert len(completions) == 20 and len(complete) == 19 and len(failed) == 1
    assert len(http) == 1497 and len(packing) == 1448
    assert categories['prompt_tokenize']['completed'] == 1448
    assert {r['completion_request_ordinal'] for r in observed} == {r['request_ordinal'] for r in complete}
    assert all(row['status'] == 200 for row in complete)
    assert math.isclose(all_totals['request_wall_seconds'], math.fsum(r['wall_seconds'] for r in complete), abs_tol=1e-8)
    groups = defaultdict(list)
    for row in packing:
        groups[(row['case_id'], row['arm'])].append(row)
    assert len(groups) == 20
    assert all(sum(r['stage'] == 'FINAL_COMBINED_PROMPT' for r in rows) == 1 for rows in groups.values())
    assert sum(r['stage'] == 'WHOLE_GROUP_PROPOSAL' for r in packing) == 1408
    packed_uncompleted = [key for key in groups if key not in {(r['case_id'], r['arm']) for r in observed}]
    assert len(packed_uncompleted) == 1
    last = failed[0]
    assert last['request_ordinal'] == 1497 and last['status'] is None and last['response']['bytes'] == 0
    events = Counter(row['event'] for row in progress)
    assert events['FORECAST_COMPLETE'] == 19 and events['LOCAL_HTTP_BEFORE'] == 1497
    def event_time(name):
        values = [r['monotonic_seconds'] for r in progress if r['event'] == name]
        assert len(values) == 1
        return values[0]
    bge_duration = event_time('BGE_ALL_UNIT_AND_QUERY_FEATURES_COMPLETE') - event_time('BGE_INITIALIZATION_BEFORE')
    reader_load = event_time('SERVER_READY') - event_time('SERVER_POPEN_BEFORE')
    reader_reap = event_time('SERVER_REAPED') - event_time('SERVER_STOP_BEFORE')
    prompt_sum = math.fsum(r['server_prompt_seconds'] for r in observed)
    completion_sum = categories['completion']['observed_HTTP_wall_seconds_all_attempts']['sum']
    worker_wall = raw['wall_seconds']
    resources = raw['resources']
    memory = raw['reader_state']['memory_before_stop']
    paired_cases = [case['id'] for case in raw['cases'] if set(case['forecasts']) == set(ARMS)]
    assert len(paired_cases) == 6
    report = {'schema_version': 1, 'epoch': 46,
        'kind': 'REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT', 'phase': 'dev',
        'status': 'REJECTED_DEV_INTEGRITY_RUNTIME_DIAGNOSTICS_ONLY',
        'source_commit': 'c74ecd93ce3a16d489fe794a91ff8c8d160383dc',
        'source_plan_sha256': raw['plan_sha256'],
        'source_freeze_sha256': '6b854126b849fce27def51ed1ddb7bddd5d90d4e8d4f1f3b033ac2cfdfb61e98',
        'runtime_acceptance_passed': False, 'scientific_acceptance_passed': False,
        'accuracy': None, 'brier': None, 'nll': None, 'benchmark_rank': None,
        'semantic_gold_decodes': 0, 'protected_confirmation_decodes': 0,
        'used_confirmation_identities': [], 'EVALUATE_calls': 0,
        'new_worker_or_model_or_native_or_Node_calls_by_this_analysis': 0,
        'R_writes_by_this_analysis': 0, 'request_or_response_body_reads_by_this_analysis': 0,
        'feature_or_vault_reads_by_this_analysis': 0,
        'model_decision_or_probability_fields_inspected': 0,
        'quantile_definition': 'Nearest rank: sort x ascending; Q(p)=x[ceil(p*N)-1], p=0.50 or0.95; no interpolation.',
        'sample_limits': 'Only19 completed forecasts from a fixed sequential failed batch. Arms have N7/6/6 and only6 complete matched cases from documents357/227; case46:nda-1 native completed and lexical was censored. These timings cannot establish full-batch arm performance, quality or generalization.',
        'completed_forecasts': 19, 'required_forecasts': 36, 'completion_attempts': 20,
        'fully_paired_completed_case_ids': paired_cases,
        'per_arm_completed_latency': per_arm,
        'successful_forecast_timing_rows': observed,
        'successful_forecast_component_sums_seconds': all_totals,
        'HTTP_categories': categories,
        'successful_completion_HTTP_wall_seconds': stats([row['wall_seconds'] for row in complete]),
        'censored_completion': {'ordinal': 1497, 'case_id': packed_uncompleted[0][0],
            'arm': packed_uncompleted[0][1], 'observed_wait_seconds': last['wall_seconds'],
            'request_wire_bytes': last['request']['bytes'], 'response_wire_bytes': 0,
            'HTTP_status': None, 'completion_achieved': False,
            'not_in_completed_latency_quantiles': True,
            'interpretation': 'Right-censored at global work deadline;18.387s is observed incomplete wait, never a successful completion latency.'},
        'packing_metadata': {'sequences_started_and_finally_packed': 20,
            'prompt_tokenize_calls_attempted': 1448, 'prompt_tokenize_calls_completed': 1448,
            'empty_base_probes': 20, 'whole_group_proposals': 1408, 'final_combined_probes': 20,
            'prompt_tokenize_HTTP_wall_seconds_sum': categories['prompt_tokenize']['observed_HTTP_wall_seconds_all_attempts']['sum'],
            'packing_of20th_sequence_not_in19_successful_forecast_packing_sum': True},
        'actual_operation_counters': raw['counters'],
        'actual_native': {'corpus_batches_completed': 1, 'indexes': 4, 'insertions': 176,
            'queries': 12, 'hit_source_validations': 528,
            'native_helper_wall_seconds': raw['native_state']['wall_seconds'],
            'child_closed': True, 'exit_code': 0},
        'actual_BGE': {'texts': 188, 'forward_calls': 36, 'query_encodings': 12,
            'initialization_seconds': raw['BGE_runtime_receipt']['initialization_seconds'],
            'all_features_stage_elapsed_seconds': bge_duration},
        'wall_clock_scopes_seconds': {'worker_capture_including_cleanup': worker_wall,
            'supervisor_execution_receipt': execution['wall_seconds'],
            'root_outer_before_capture': closure['outer_before_capture_wall_seconds'],
            'reader_start_to_ready': reader_load, 'reader_stop_to_reaped': reader_reap,
            'independent_later_failure_fence_minus_dispatch': closure['current_audit_fence_minus_dispatch_seconds']},
        'closure': {'worker_exit_code': 1, 'reader_exit_code': 0, 'native_exit_code': 0,
            'physical_failure_closure_review_passed': closure['physical_closure_passed'],
            'runtime_qualification_passed': False,
            'frozen600_success_bound_claimed': False,
            'scope': 'Successful frozen physical<=600 qualification absent. Later independent failure closure is not the frozen success observer.'},
        'resource_scopes': {
            'worker_self': {'user_CPU_seconds': resources['user_seconds'],
                'system_CPU_seconds': resources['system_seconds'], 'max_RSS_KiB': resources['max_rss_kib'],
                'max_RSS_GiB': resources['max_rss_kib'] / 1048576,
                'scope': 'RUSAGE_SELF only; excludes reader/native child CPU and RSS.'},
            'children': {'max_RSS_KiB': resources['children_max_rss_kib'],
                'max_RSS_GiB': resources['children_max_rss_kib'] / 1048576,
                'CPU_seconds': None,
                'scope': 'RUSAGE_CHILDREN ru_maxrss peak child high-water value; not sum or independent CPU utilization measurement.'},
            'reader_before_stop': {'observed_metadata': memory,
                'scope': '/proc reader VmHWM/VmRSS just before stop;7 total threads includes support threads despite configured compute2 and HTTP1.'},
            'shared_cgroup': {'current_bytes': resources['cgroup_memory_current'],
                'peak_bytes': resources['cgroup_memory_peak'],
                'current_GiB': resources['cgroup_memory_current'] / 1073741824,
                'peak_GiB': resources['cgroup_memory_peak'] / 1073741824,
                'scope': 'Shared execution cgroup; includes other processes/cache and prior peak. Not reader or per-candidate incremental memory.'},
            'configured_limits': {'worker_CPU_affinity': resources['cpu_affinity'],
                'reader_compute_threads': 2, 'reader_batch_threads': 2, 'HTTP_threads': 1,
                'paid_API_calls': 0, 'GPU_calls': 0}},
        'attribution': {'completed_readout_seconds': all_totals['model_readout_HTTP_seconds'],
            'completed_packing_seconds': all_totals['context_packing_seconds'],
            'completed_readout_share_of_packing_plus_readout_percent': 100 * all_totals['model_readout_HTTP_seconds'] / all_totals['packing_and_readout_seconds'],
            'all_completion_HTTP_share_of_worker_capture_percent': 100 * completion_sum / worker_wall,
            'all_prompt_tokenize_HTTP_share_of_worker_capture_percent': 100 * categories['prompt_tokenize']['observed_HTTP_wall_seconds_all_attempts']['sum'] / worker_wall,
            'server_reported_prompt_evaluation_seconds_completed19': prompt_sum,
            'server_reported_prompt_share_of_successful_completion_HTTP_percent': 100 * prompt_sum / all_totals['request_wall_seconds'],
            'server_predicted_ms_is_server_reported_not_independent_compute_measurement': True,
            'conclusion': 'Observed timeout is dominated by reader prompt evaluation, not packing/tokenize HTTP overhead.19 completed readouts consumed529.109s versus3.323s packing; server prompt timings account for512.095s. All20 completion waits consumed546.106s of570.506s worker capture. Native and BGE stages completed. This single partial trace is descriptive, not a causal optimization experiment.',
            'future_direction_only': 'An independently frozen future design must reduce reader prompt-evaluation work or use a faster eligible CPU reader while retaining matched retrieval arms and evidence/decision checks. Packing RPC reduction alone cannot recover the observed time deficit. No configuration change, new run or spend is authorized by this diagnostic.'},
        'source_timing_definitions_verified_statically': source_refs,
        'private_metadata_publication_rule': 'Publish only this derived diagnostic, analysis source and exact input descriptors; never full private journals, wire bodies, exception text or corpus/token payloads.',
        'private_metadata_fields_used': ['HTTP category/ordinal/status/wall/size/ref hashes',
            'packing case/arm/stage only', 'progress event names and monotonic timestamps',
            'exception type and receive stack location'],
        'inputs': INPUTS,
        'analysis_source': {'path': str(Path(__file__)), 'bytes': Path(__file__).stat().st_size,
                            'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    input_ref = emit('EXACT_INPUT_REFS.v1.json', {'schema_version': 1, 'epoch': 46, 'inputs': INPUTS})
    report['exact_input_refs'] = input_ref
    result_ref = emit('RUNTIME_DIAGNOSTICS.v1.json', report)
    print(json.dumps({'diagnostics': result_ref, 'input_refs': input_ref, 'analysis_source': report['analysis_source']}, sort_keys=True))


if __name__ == '__main__':
    main()
