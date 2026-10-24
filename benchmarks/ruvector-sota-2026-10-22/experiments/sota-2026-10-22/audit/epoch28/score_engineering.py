"""Pure-stdlib saved-output engineering replay and later RESULTS binding.

No candidate imports, annotation source, ML/native initialization or proper scores.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

KIND = 'REAL_ENGINEERING_FULL104_QUALIFICATION'
PINS = {
    'protocol.json': '10e33b6a673e640142f63316d8fff923c8558852e65d132e450a4b8272182408',
    'engineering-inputs.json': 'c3a83ae2a834ecfe534ec421eea21e7414586cc9858e400d105ce5657ad1cc45',
    'engineering-identities.json': '62056f9c8d8ebf7d2c91f57c6896de86cc4c860d81b34d58d85362c5454b29d3',
    'full104-closure-audit.json': '2069213fac27e5bb8a5a83785e1617b0240a9e139317b4508fbd77507e9a398d',
    'cpu-affinity-policy-v1.json': '98310d2468e8e81f95cae17b95b97a7eb572b20fe18bbc6f3aad337909bd9602',
}
BINARY = 'node_modules/@ruvector/typesafe/native/linux-x64-gnu/typesafe.linux-x64-gnu.node'
BINARY_SHA = 'e4db4b945a91b5cb8937765236e180763e8a3f4866b791e0f71a98d0018c289d'
PUBLICATION_HELPER_SHA = '5b7d569902b5df3aeb4b4af45104c90807f97203a4ed78356bd4ab3bcb99511c'
ORT = 'node_modules/@ruvector/typesafe/native/linux-x64-gnu/libonnxruntime.so.1'
ZERO = ['Python_network_operations_attempted', 'Node_network_operations_attempted',
        'DEV_reads', 'CONF_reads', 'benchmark_label_reads', 'fits', 'calibration_calls',
        'training_steps', 'generation_calls', 'paid_calls', 'GPU_calls', 'HTTP_requests']
COUNTS = dict.fromkeys(['native_process_starts_attempted', 'native_process_starts_completed',
    'composite_initializations_attempted', 'composite_initializations_completed',
    'native_ready_receipts', 'native_binary_loads_attempted', 'native_binary_loads_completed'], 1)
COUNTS.update(dict.fromkeys(['composite_predict_attempted', 'native_systemOne_requests',
                           'native_questions_written', 'native_response_lines'], 8))
COUNTS.update(composite_predict_completed=7, native_successful_responses=7, native_refusal_responses=1)
COUNTS.update(native_stdin_write_calls_attempted=8, native_request_reply_pairs_closed=8,
              native_stdout_read_calls_attempted=9, native_stdout_lines_read=9)


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key: ' + key)
        out[key] = value
    return out


def loads(value):
    def invalid(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(value, object_pairs_hook=unique, parse_constant=invalid)


def read(path):
    return loads(Path(path).read_bytes())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def identity(path, root=None):
    path = Path(path)
    return {'path': str(path.relative_to(root)) if root else str(path),
            'bytes': path.stat().st_size, 'sha256': sha(path)}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def quantile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    rank = (len(values)-1)*fraction
    low, high = math.floor(rank), math.ceil(rank)
    return values[low] + (rank-low)*(values[high]-values[low])


def metric_na():
    return {'benchmark_accuracy': None, 'NLL': None, 'Brier': None,
        'proper_score_metric_computations': 0,
        'reason': 'Authored engineering transport/source/proof checks only. No benchmark labels or semantic accuracy gate. Original zero-label noul is an uncalibrated similarity score; no invented probability model.'}


def safe_relative(root, value):
    path = root/value
    if Path(value).is_absolute() or path != path.resolve() or not path.is_relative_to(root):
        raise ValueError('Noncanonical/outside project artifact path')
    return path


def answer_valid(answer, question):
    if type(answer) is not dict or answer.get('type') != question['type']:
        return False
    if type(answer.get('calibrated')) is not bool:
        return False
    for key in ['confidence', 'temperature', 'abstain']:
        if key in answer and not finite(answer[key]):
            return False
    p = answer.get('probabilities')
    if question['type'] == 'choice':
        if type(p) is not dict or set(p) != set(question['criteria']) or answer.get('choice') not in p:
            return False
    elif question['type'] == 'noul':
        if not finite(answer.get('noul')) or not 0 <= answer['noul'] <= 1:
            return False
        if p is not None:
            if type(p) is not dict or set(p) != {'yes', 'no'} or not all(finite(v) for v in p.values()):
                return False
            if abs(p['yes']-answer['noul']) > 1e-6:
                return False
    if p is not None:
        if any(not finite(v) or not 0 <= v <= 1 for v in p.values()) or abs(math.fsum(p.values())-1) > 1e-6:
            return False
    return True


def physically_closed(raw, execution):
    identities = [raw.get('worker_identity'), raw.get('initialization', {}).get('actual_child')]
    for row in identities:
        if row and Path('/proc/' + str(row['pid'])).exists():
            return False
    group = execution.get('worker_identity', {}).get('pgid')
    if group:
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
                if int(fields[2]) == group or int(fields[3]) == group:
                    return False
            except (OSError, ValueError, IndexError):
                pass
    return True


def partial_source_evidence(root, partial_path, execution):
    """Bind an absent or truly unparsable final; never hide a parseable final."""
    final = partial_path.with_name('raw.json')
    if not final.exists():
        return (execution.get('raw_sha256') is None and execution.get('raw_bytes') is None), None
    observed = identity(final, root)
    bound = observed['sha256'] == execution.get('raw_sha256') and observed['bytes'] == execution.get('raw_bytes')
    try:
        read(final)
    except (ValueError, TypeError):
        return bound, observed
    return False, observed


def evaluate(args):
    root = Path(args.project).resolve()
    directory = root/'experiments/sota-2026-10-22/audit/epoch28'
    raw, execution, plan = read(args.raw), read(args.execution), read(args.plan)
    integrity, gates = [], []

    def check(name, value, qualification=False):
        target = gates if qualification else integrity
        target.append({'name': name, 'passed': bool(value)})

    for name, expected in PINS.items():
        check('fixed_oracle:' + name, sha(directory/name) == expected)
    bank = read(directory/'engineering-inputs.json')
    oracle = read(directory/'engineering-identities.json')
    closure = read(directory/'full104-closure-audit.json')
    check('fixed_eight_oracle_rows', len(bank['records']) == len(oracle['records']) == 8)
    check('oracle_metadata_matches_fixed_bank', oracle['records'] == [
        {key: row[key] for key in ['id', 'purpose', 'input_utf8_json_sha256',
         'state_utf8_bytes', 'state_utf8_sha256', 'engineering_expectation']}
        for row in bank['records']])
    check('engineering_only_roles', raw.get('epoch') == plan.get('epoch') == 28 and raw.get('kind') == plan.get('kind') == KIND
          and raw.get('data_roles') == {'train': [], 'dev': [], 'calibration': [], 'confirmation': []})
    check('no_raw_benchmark_or_promotion_claim', raw.get('benchmark_generalization_claim') is False
          and raw.get('champion_promoted') is False)
    fixed_limits = {'owned_workers': 1, 'CPU_threads': 2, 'CPU_affinity': [0, 1],
        'seconds_per_batch': 600, 'native_corpus_batches': 1, 'paid_calls': 0, 'GPU_calls': 0,
        'native_process_initializations': 1, 'native_systemOne_requests': 8}
    check('fixed_bounded_plan', all(plan['limits'].get(k) == v for k, v in fixed_limits.items()))
    check('exact_raw_plan_binding', raw.get('plan_sha256') == sha(args.plan))
    check('exact_raw_source_freeze_binding', raw.get('source_freeze_sha256') == plan.get('source_freeze_sha256')
          and sha(safe_relative(root, plan['source_freeze_path'])) == plan['source_freeze_sha256'])
    check('exact_outer_raw_identity', execution.get('raw_sha256') == sha(args.raw)
          and execution.get('raw_bytes') == Path(args.raw).stat().st_size)
    for row in plan['pins']:
        path = safe_relative(root, row['path'])
        check('frozen_source:' + row['path'], path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
    own = Path(__file__).resolve()
    if own.is_relative_to(root):
        own_relative = str(own.relative_to(root))
        check('published_scorer_source_pinned', any(row['path'] == own_relative
              and row['sha256'] == sha(own) for row in plan['pins']))
    runtime = raw.get('runtime_assets', {})
    by_runtime = {row['path']: row for row in runtime.get('files', [])}
    required = closure['required_runtime16'] + [{'path': 'models/manifest.json', 'bytes': 577,
        'sha256': 'fdca50d372d5993f347db244678f77c0c8fef5698d5fd479ddf1a060f77838a5'}]
    check('exact17_runtime_metadata', len(by_runtime) == 17 and all(by_runtime.get(row['path']) == row for row in required))
    receipt = raw.get('initialization', {}).get('receipt', {})
    check('original_native_receipt', receipt.get('backend') == 'native' and receipt.get('binary_version') == '2.4.0'
          and receipt.get('package_version') == '0.2.0' and receipt.get('package') == '@ruvector/typesafe'
          and receipt.get('binary_sha256') == BINARY_SHA
          and receipt.get('model_manifest_sha256') == by_runtime.get('models/manifest.json', {}).get('sha256'), True)
    events = raw.get('Node_guard_events', [])
    before = [x for x in events if x.get('event') == 'NATIVE_BINARY_LOAD_BEFORE']
    after = [x for x in events if x.get('event') == 'NATIVE_BINARY_LOAD_AFTER']
    check('one_actual_isolated_native_addon_load', len(before) == len(after) == 1
          and before[0].get('path') == after[0].get('path') == str(root/BINARY)
          and before[0].get('sha256') == BINARY_SHA, True)
    for key, rows in [('initial', raw.get('initialization', {}).get('actual_mapped_native_runtime', [])),
                      ('after_requests', raw.get('actual_mapped_native_runtime_after_requests', []))]:
        check('actual_mapped_addon_and_ORT:' + key, {BINARY, ORT} <= {r['path'] for r in rows}
              and all(by_runtime.get(row['path']) == row for row in rows), True)
    init = raw.get('initialization', {})
    cpu = raw.get('cpu_guard_preexec', {})
    check('CPU_guard_installed_before_exec_without_model_options', cpu.get('status') == 'CPU_GUARD_INSTALLED_BEFORE_EXEC'
          and cpu.get('platform') == 'linux-x86_64' and cpu.get('CPU_affinity') == [0, 1]
          and cpu.get('denied_syscalls') == [203, 1073742027] and cpu.get('denial_errno') == 1
          and cpu.get('inherited_by_all_future_threads_and_exec') is True
          and cpu.get('global_kernel_configuration_changed') is False, True)
    cpu_artifact = raw.get('cpu_guard_preexec_artifact', {})
    cpu_path = safe_relative(root, cpu_artifact['path'])
    check('CPU_guard_original_artifact_bound', identity(cpu_path, root) == cpu_artifact and read(cpu_path) == cpu)
    admission_events = [e for e in events if e.get('event') == 'NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT']
    node_cpu = admission_events[0].get('CPU_guard_actual_proc_status', {}) if len(admission_events) == 1 else {}
    check('CPU_guard_independently_seen_before_native_import', len(admission_events) == 1
          and str(node_cpu.get('NoNewPrivs')) == '1' and str(node_cpu.get('Seccomp')) == '2'
          and node_cpu.get('Cpus_allowed_list') in ['0-1', '0,1'], True)
    check('opaque_internals_remain_unknown', all(init.get(key) is None for key in
          ['opaque_internal_BGE_forwards', 'NLI_calls', 'ANN_queries']))
    counters = raw.get('counters', {})
    for key, expected in COUNTS.items():
        check('API_counter:' + key, type(counters.get(key)) is int and counters[key] == expected, True)
    for key in ZERO:
        check('forbidden_zero:' + key, type(counters.get(key)) is int and counters[key] == 0, True)
    check('network_violation_lists_empty', raw.get('Python_network_violations') == []
          and not any(x.get('event') == 'OFFLINE_FATAL_VIOLATION' for x in events), True)
    rows = raw.get('requests', [])
    check('fixed_ordered_requests', [x.get('id') for x in rows] == [x['id'] for x in bank['records']], True)
    all_times, success_times, refusal_details = [], [], []
    source_inferred_mappings = []
    for record, observed in zip(bank['records'], rows):
        cid, inp = record['id'], record['input']
        check(cid + ':oracle_metadata', observed.get('engineering_expectation') == record['engineering_expectation'])
        expected_literal = canonical(inp)
        check(cid + ':literal_full_input', observed.get('literal_input_json') == expected_literal
              and digest(expected_literal.encode()) == record['input_utf8_json_sha256'])
        state, questions = observed.get('normalized_state'), observed.get('normalized_questions')
        check(cid + ':normalization_preserves_full_state_order', state == inp['state'] and canonical(questions) == canonical(inp['questions'])
              and observed.get('state_utf8_bytes') == len(inp['state'].encode()) == record['state_utf8_bytes']
              and observed.get('state_utf8_sha256') == record['state_utf8_sha256'])
        sent, replied = observed.get('native_stdin_literal', ''), observed.get('native_stdout_literal', '')
        wire, native = loads(sent), loads(replied)
        check(cid + ':actual_pipe_frames_hash_and_full_outer_body', sent.endswith('\n') and replied.endswith('\n')
              and digest(sent.encode()) == observed.get('native_stdin_sha256')
              and digest(replied.encode()) == observed.get('native_stdout_sha256')
              and canonical(wire) == canonical({'state': state, 'questions': questions}))
        check(cid + ':observed_write_read_completion', observed.get('native_stdin_write_intended') == sent
              and observed.get('native_stdin_literal_written') == sent
              and observed.get('native_stdin_write_outcome') == 'COMPLETE_FRAME_ACCEPTED'
              and observed.get('native_stdout_literal_received') == replied
              and observed.get('native_backend_execution_observation') == 'ORIGINAL_RESPONSE_OBSERVED', True)
        mapping = {'state': state, 'questions': {}}
        for key, q in questions.items():
            if q['type'] == 'choice':
                mapping['questions'][key] = {'type': q['type'], 'criteria': q['criteria'], 'instructions': q['instructions']}
            else:
                mapping['questions'][key] = {'type': q['type'], 'instructions': q['instructions']}
        source_inferred_mappings.append({'id': cid, 'mapping_basis': 'Inferred from pinned original client.js jevToWireQuestion; not separately observed FFI traffic',
            'internal_FFI_request_observed': False, 'inferred_request_utf8_sha256': digest(canonical(mapping).encode())})
        seconds = observed.get('seconds')
        check(cid + ':finite_request_interval', finite(seconds) and seconds >= 0)
        if finite(seconds) and seconds >= 0:
            all_times.append(seconds)
        expectation = record['engineering_expectation']
        if expectation['outcome'] == 'success':
            response = observed.get('response')
            successful = native.get('ok') is True and observed.get('error') is None and type(response) is dict
            check(cid + ':original_success_preserved', successful, True)
            if not successful:
                continue
            success_times.append(seconds)
            check(cid + ':question_identity', set(response.get('answers', {})) == set(questions))
            for key, question in questions.items():
                answer = response['answers'][key]
                original = native['response']['answers'][key]
                check(cid + ':actual_native_original_preserved', answer.get('native_original_answer') == original)
                check(cid + ':all_original_answer_versions_valid', all(answer_valid(v, question) for v in
                      [answer, answer.get('native_original_answer'), answer.get('baseline100_answer')]), True)
                check(cid + ':original_fallback_route', answer.get('native_fallback_used') is expectation['expected_native_fallback_used'], True)
                if expectation['expected_native_fallback_used']:
                    stripped = {k: v for k, v in answer.items() if k not in
                                ['native_original_answer', 'baseline100_answer', 'native_fallback_used']}
                    check(cid + ':no_new_fallback_override', stripped == original
                          and answer.get('baseline100_answer') == original, True)
                if 'expected_proof_rule' in expectation:
                    proof = answer.get('symbolic_proof', {})
                    stripped = {k: v for k, v in answer.items() if k not in
                                ['native_original_answer', 'baseline100_answer', 'native_fallback_used']}
                    check(cid + ':exact_original_word_count_function', proof.get('rule') == expectation['expected_proof_rule']
                          and proof.get('required') == 3
                          and proof.get('actual') == len(loads(state)['response'].split())
                          and answer.get('noul') == expectation['expected_final_noul']
                          and answer.get('calibrated') is False
                          and answer.get('baseline100_answer') == stripped, True)
                if question['type'] == 'noul' and expectation['expected_native_fallback_used']:
                    check(cid + ':uncalibrated_noul_stays_score', original.get('calibrated') is False, True)
        else:
            error = observed.get('error') or {}
            message = native.get('error', '')
            supported = type(message) is str and ('state' in message.lower() or 'input' in message.lower())
            supported = supported and any(x in message.lower() for x in ['limit', 'large', 'long', 'max', '16384', 'bytes'])
            check(cid + ':original_oversize_refusal_retained', native.get('ok') is False and bool(message)
                  and observed.get('response') is None and error.get('message') == message
                  and error.get('original_error_kind') is None, True)
            check(cid + ':limit_cause_supported_not_invented', supported, True)
            refusal_details.append({'id': cid, 'state_utf8_bytes': record['state_utf8_bytes'],
                'original_error_message': message, 'original_error_kind': None,
                'original_message_supports_predetermined_limit': supported,
                'cause_when_unsupported': None if supported else 'UNKNOWN'})
    for key, literals in [('stdin', [x.get('native_stdin_literal', '') for x in rows]),
                          ('stdout', [x.get('native_stdout_literal', '') for x in rows])]:
        entry = raw.get('pipe_artifacts', {}).get(key, {})
        path = safe_relative(root, entry['path'])
        content = path.read_bytes()
        check('complete_pipe_artifact:' + key, len(content) == entry.get('bytes') and digest(content) == entry.get('sha256'))
        if key == 'stdin':
            check('stdin_is_exact_all_captured_requests', content == ''.join(literals).encode())
        else:
            lines = content.decode().splitlines(keepends=True)
            check('stdout_has_one_ready_plus_eight_original_responses', len(lines) == 9 and ''.join(lines[1:]) == ''.join(literals))
            ready = loads(lines[0])
            check('actual_ready_frame_matches_original_receipt', ready.get('status') == 'ready'
                  and all(receipt.get(k) == value for k, value in ready.items())
                  and raw.get('native_startup_stdout_literal') == lines[0])
    stderr = raw.get('pipe_artifacts', {}).get('stderr', {})
    stderr_path = safe_relative(root, stderr['path'])
    check('complete_stderr_retained', stderr_path.stat().st_size == stderr.get('bytes') and sha(stderr_path) == stderr.get('sha256'))
    check('exact_outer_counter_copy', execution.get('raw_operation_counters') == counters)
    check('final_raw_counters_not_checkpoint_counts', execution.get('raw_operation_counters_source') == 'raw.json'
          and execution.get('operation_counts_complete') is True
          and execution.get('backend_execution_since_checkpoint') == 'NOT_APPLICABLE_FINAL_RAW', True)
    check('successful_closed_single_CPU2_execution', execution.get('status') == 'WORKER_COMPLETED'
          and execution.get('exit_code') == 0 and execution.get('worker_attempts_reserved') == execution.get('verified_worker_starts') == 1
          and execution.get('CPU_affinity') == [0, 1] and execution.get('owned_live_processes_closed') is True
          and execution.get('owned_live_group_members') == [] and finite(execution.get('wall_seconds_including_init_cleanup'))
          and 0 < execution['wall_seconds_including_init_cleanup'] <= 600
          and execution.get('launcher_error') is None and execution.get('cleanup_errors') == [], True)
    check('worker_helper_physically_absent', physically_closed(raw, execution), True)
    check('raw_completed_no_unexpected_errors', raw.get('status') == 'COMPLETED_AUTHORED_QUALIFICATION_AWAITING_INDEPENDENT_REPLAY'
          and raw.get('errors') == [] and raw.get('native_child_closed') is True
          and type(raw.get('native_child_exit_code')) is int, True)
    check('all_future_slots_closed', execution.get('allowed_further_epoch28_workers') == 0, True)
    check('CPU_affinity_observation', raw.get('resources', {}).get('CPU_affinity') == [0, 1], True)
    child_status = init.get('native_process_status', {})
    check('native_child_kernel_CPU_filter_observed', str(child_status.get('NoNewPrivs')) == '1'
          and str(child_status.get('Seccomp')) == '2'
          and str(child_status.get('Seccomp_filters', '')).isdigit()
          and int(child_status.get('Seccomp_filters', 0)) > 0, True)
    snapshots = [child_status, raw.get('resources', {}).get('worker', {})]
    progress_path = Path(args.raw).parent/'progress.jsonl'
    check('saved_progress_trace_available', progress_path.is_file())
    if progress_path.is_file():
        for line in progress_path.read_text().splitlines():
            event = loads(line)
            snapshots.append(event.get('process', {}))
            detail = event.get('event', {})
            if type(detail) is dict and type(detail.get('native_process')) is dict:
                snapshots.append(detail['native_process'])
    observed_tasks = [task for snapshot in snapshots for task in snapshot.get('observed_thread_affinities', [])]
    check('all_observed_thread_affinities_within_CPU0_1', bool(observed_tasks)
          and all(task.get('observed_affinity_within_CPU0_1') is True for task in observed_tasks), True)
    integrity_pass = all(c['passed'] for c in integrity)
    qualified = integrity_pass and all(c['passed'] for c in gates)
    status = 'ENGINEERING_QUALIFIED' if qualified else ('FAILED_ENGINEERING_EXECUTION'
              if execution.get('status') != 'WORKER_COMPLETED' else 'REJECTED_ENGINEERING_QUALIFICATION')
    return {'schema_version': 1, 'epoch': 28, 'kind': KIND, 'status': status,
        'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': integrity_pass,
        'integrity_checks': integrity, 'qualification_checks': gates,
        'engineering_qualified': qualified, 'comparator_transport_ready': qualified,
        'parsed_raw_available': True,
        'failed_integrity_checks': [x['name'] for x in integrity if not x['passed']],
        'failed_qualification_checks': [x['name'] for x in gates if not x['passed']],
        'metrics': metric_na(), 'request_timing': {
            key: {'n': len(values), 'p50_seconds': quantile(values, .5), 'p95_seconds': quantile(values, .95)}
            for key, values in [('all_attempts_including_refusal', all_times), ('successful_requests', success_times)]},
        'timing_scope': 'Harness interval around original CompositeEngine.predict plus response retention/JSON and structural validation; includes private pipe/native work and proof routing. Not isolated ONNX/ANN/kernel. Initialization and full outer wall retained separately.',
        'resources': raw.get('resources'), 'outer_execution': execution,
        'actual_API_counters': counters, 'opaque_internal_observations': {
            'BGE_forward_count': None, 'NLI_call_count': None, 'ANN_query_count': None,
            'reason': 'Observed API constructor/request/addon-load counters are not opaque compiled internal forward/thread counts.',
            'native_process_status': init.get('native_process_status')},
        'CPU_enforcement_observations': {'native_NoNewPrivs': child_status.get('NoNewPrivs'),
            'native_Seccomp': child_status.get('Seccomp'), 'native_Seccomp_filters': child_status.get('Seccomp_filters'),
            'observed_task_snapshots': len(observed_tasks),
            'preexec_filter_receipt': cpu, 'actual_affinity_syscall_attempt_count': None,
            'scope': 'Process-local preexec affinity/seccomp source policy plus actual status and observed task snapshots; no continuous observation of every short-lived task and no OS network-isolation claim.'},
        'refusals': refusal_details, 'source_inferred_internal_mappings': source_inferred_mappings,
        'errors_preserved': {'raw_errors': raw.get('errors'), 'request_errors': [x.get('error') for x in rows],
            'launcher_error': execution.get('launcher_error'), 'cleanup_errors': execution.get('cleanup_errors')},
        'counter_scope': 'One bounded native engineering batch, zero benchmark corpora;8actual original API requests if complete. OS thread samples and internal unknowns remain distinct from CPU affinity/computational budget.',
        'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []},
        'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
        'official_SOTA_established': False, 'confirmation': [], 'benchmark_annotation_choices_accessed': 0,
        'model_tokenizer_native_calls_by_auditor': 0,
        'scope': 'Authored CC0 source/proof/transport engineering only. Readiness is not semantic generalization, future CONF admission, benchmark improvement or promotion.',
        'evidence': {'raw': identity(args.raw, root), 'execution': identity(args.execution, root),
            'plan': identity(args.plan, root), 'protocol': identity(directory/'protocol.json', root),
            'bank': identity(directory/'engineering-inputs.json', root),
            'oracle': identity(directory/'engineering-identities.json', root),
            'CPU_guard_preexec': cpu_artifact,
            'progress': identity(progress_path, root) if progress_path.is_file() else None,
            'scorer_source': identity(Path(__file__).resolve(), root if Path(__file__).resolve().is_relative_to(root) else None)}}


def derive_actual_with_frozen_helper(root, replay, raw, execution):
    relative = 'experiments/sota-2026-10-22/epoch28/publication/stage_publication_v1.py'
    path = safe_relative(root, relative)
    plan = read(safe_relative(root, replay['evidence']['plan']['path']))
    pin = next((row for row in plan['pins'] if row['path'] == relative), None)
    if pin is None or path.stat().st_size != pin['bytes'] or sha(path) != pin['sha256'] or pin['sha256'] != PUBLICATION_HELPER_SHA:
        raise ValueError('Unpinned publication derive_actual helper')
    dependency = path.parent/'publication_common_v1.py'
    dependency_pin = next((row for row in plan['pins'] if row['path'] == str(dependency.relative_to(root))), None)
    if dependency_pin is None or dependency.stat().st_size != dependency_pin['bytes'] or sha(dependency) != dependency_pin['sha256']:
        raise ValueError('Unpinned publication helper dependency')
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location('epoch28_frozen_publication_binding_helper', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.derive_actual(raw, execution), identity(path, root)
    finally:
        sys.path[:] = old_path


def bind(args):
    root = Path(args.project).resolve()
    replay, results = read(args.replay), read(args.results)
    failures = []
    for key in ['raw', 'execution', 'plan', 'protocol', 'bank', 'oracle', 'progress', 'CPU_guard_preexec', 'unparsed_final_raw']:
        row = replay['evidence'].get(key)
        if row is not None and identity(safe_relative(root, row['path']), root) != row:
            failures.append('replay_artifact_changed:' + key)
    if results.get('epoch') != 28 or results.get('kind') != KIND:
        failures.append('canonical_results_epoch_kind')
    if results.get('engineering_qualified') is not replay['engineering_qualified']:
        failures.append('canonical_engineering_verdict')
    if results.get('metrics') != replay['metrics']:
        failures.append('canonical_metrics_NA')
    for key in ['benchmark_accepted', 'champion_promoted', 'new_submission']:
        if results.get(key) is not False:
            failures.append('permanent_false:' + key)
    execution = replay['outer_execution']
    row = replay['evidence']['raw']
    raw = read(safe_relative(root, row['path'])) if row and replay.get('parsed_raw_available', True) else None
    if row is not None and Path(row['path']).name == 'raw.partial.json':
        valid_partial_source, final_evidence = partial_source_evidence(root, safe_relative(root, row['path']), execution)
        if (execution.get('status') == 'WORKER_COMPLETED' or replay['engineering_qualified'] is not False
                or row['sha256'] != execution.get('partial_raw_sha256')
                or row['bytes'] != execution.get('partial_raw_bytes')
                or (raw or {}).get('counters') != execution.get('raw_operation_counters')
                or execution.get('raw_operation_counters_source') != 'raw.partial.json'
                or execution.get('operation_counts_complete') is not False
                or execution.get('backend_execution_since_checkpoint') != 'UNKNOWN'
                or replay.get('operation_counts_complete') is not False
                or replay.get('backend_execution_since_checkpoint') != 'UNKNOWN'
                or not valid_partial_source
                or replay['evidence'].get('unparsed_final_raw') != final_evidence):
            failures.append('partial_raw_not_explicitly_failed_and_byte_counter_bound')
    if row is None and (execution.get('status') == 'WORKER_COMPLETED'
            or execution.get('raw_sha256') is not None or execution.get('raw_bytes') is not None
            or execution.get('raw_operation_counters') is not None
            or execution.get('partial_raw_sha256') is not None or execution.get('partial_raw_bytes') is not None
            or safe_relative(root, replay['expected_raw_path']).exists()):
        failures.append('null_raw_not_a_captured_early_failure')
    actual, helper = derive_actual_with_frozen_helper(root, replay, raw, execution)
    if results.get('actual_execution') != actual:
        failures.append('canonical_actual_execution_exact_derive_actual')
    if row is not None and Path(row['path']).name == 'raw.partial.json' and (
            actual.get('operation_counts_complete') is not False
            or actual.get('backend_execution_since_checkpoint') != 'UNKNOWN'):
        failures.append('canonical_partial_execution_scope_not_explicitly_unknown')
    if failures:
        raise ValueError('RESULTS binding failures: ' + ','.join(failures))
    return {**replay, 'binding_at': datetime.now(timezone.utc).isoformat(),
        'evaluated_integrity_checks_passed': replay['checks_passed'],
        'publication_binding_checks_passed': True, 'checks_passed': True,
        'checks_passed_scope': 'Publication artifact provenance/RESULTS consistency only. The unchanged evaluation replay and evaluated_integrity_checks_passed retain every original functional/integrity failure; publication binding never qualifies a failed execution.',
        'canonical_RESULTS_binding_passed': True,
        'evidence': {**replay['evidence'], 'qualification_replay': identity(args.replay, root),
            'results': identity(args.results, root), 'derive_actual_helper': helper}}


def preserved_failure(args, error):
    """Retain an incomplete/early-failure receipt without inventing missing counts."""
    root = args.project.resolve()
    execution, plan = read(args.execution), read(args.plan)
    raw_identity, raw = None, None
    is_partial = args.raw.name == 'raw.partial.json'
    if args.raw.is_file():
        raw_identity = identity(args.raw, root)
        try:
            raw = read(args.raw)
        except (ValueError, TypeError):
            pass
    source_checks = []
    for row in plan['pins']:
        path = safe_relative(root, row['path'])
        source_checks.append(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
    if raw_identity:
        prefix = 'partial_raw_' if is_partial else 'raw_'
        raw_bound = (raw_identity['sha256'] == execution.get(prefix + 'sha256')
                     and raw_identity['bytes'] == execution.get(prefix + 'bytes'))
        if is_partial:
            raw_bound = raw_bound and (raw or {}).get('counters') == execution.get('raw_operation_counters')
            valid_partial_source, final_evidence = partial_source_evidence(root, args.raw, execution)
            raw_bound = raw_bound and valid_partial_source
            if final_evidence is not None:
                args.unparsed_final_raw_identity = final_evidence
    else:
        raw_bound = execution.get('raw_sha256') is None and execution.get('raw_bytes') is None
        raw_bound = raw_bound and execution.get('raw_operation_counters') is None
        raw_bound = raw_bound and execution.get('partial_raw_sha256') is None and execution.get('partial_raw_bytes') is None
    closed = execution.get('owned_live_processes_closed') is True and execution.get('owned_live_group_members') == []
    closed = closed and physically_closed(raw or {}, execution)
    failed_outer = execution.get('status') != 'WORKER_COMPLETED' or execution.get('exit_code') != 0
    integrity = all(source_checks) and raw_bound and closed and failed_outer
    return {'schema_version': 1, 'epoch': 28, 'kind': KIND,
        'status': 'FAILED_ENGINEERING_EXECUTION' if failed_outer else 'REJECTED_ENGINEERING_QUALIFICATION',
        'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': False,
        'failure_provenance_checks_passed': integrity,
        'engineering_qualified': False, 'comparator_transport_ready': False,
        'parsed_raw_available': raw is not None, 'raw_available': raw_identity is not None,
        'expected_raw_path': str((args.raw.parent/'raw.json').relative_to(root)),
        'raw_is_partial_checkpoint': is_partial,
        'operation_counts_complete': False if is_partial or raw is None else None,
        'backend_execution_since_checkpoint': 'UNKNOWN' if is_partial else None,
        'integrity_checks': {'frozen_source_pins_preserved': all(source_checks),
            'raw_or_partial_or_absence_matches_execution': raw_bound,
            'worker_group_closed': closed, 'outer_failure_explicit': failed_outer},
        'qualification_checks': [], 'failed_qualification_checks': ['Incomplete/invalid saved engineering outputs'],
        'audit_error_preserved': {'type': type(error).__name__, 'message': str(error)},
        'metrics': metric_na(), 'request_timing': None, 'resources': (raw or {}).get('resources'),
        'outer_execution': execution, 'actual_API_counters': (raw or {}).get('counters'),
        'opaque_internal_observations': {'BGE_forward_count': None, 'NLI_call_count': None, 'ANN_query_count': None},
        'errors_preserved': {'raw_errors': (raw or {}).get('errors'),
            'request_errors': [x.get('error') for x in (raw or {}).get('requests', [])],
            'launcher_error': execution.get('launcher_error'), 'cleanup_errors': execution.get('cleanup_errors')},
        'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []},
        'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
        'official_SOTA_established': False, 'confirmation': [], 'benchmark_annotation_choices_accessed': 0,
        'model_tokenizer_native_calls_by_auditor': 0,
        'scope': 'Captured early/partial execution failure only; no completed qualification, invented operation counts, metrics, labels or retries.',
        'evidence': {'raw': raw_identity, 'execution': identity(args.execution, root),
            'plan': identity(args.plan, root),
            'unparsed_final_raw': getattr(args, 'unparsed_final_raw_identity', None),
            'scorer_source': identity(Path(__file__).resolve(), root if Path(__file__).resolve().is_relative_to(root) else None)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    evaluate_parser = sub.add_parser('evaluate')
    for name in ['project', 'raw', 'execution', 'plan', 'output']:
        evaluate_parser.add_argument('--' + name, required=True, type=Path)
    bind_parser = sub.add_parser('bind')
    for name in ['project', 'replay', 'results', 'output']:
        bind_parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.project.resolve()):
        raise ValueError('Auditor output must stay outside the frozen project until canonical copy')
    if args.mode == 'evaluate':
        if not args.raw.exists() and (args.raw.parent/'raw.partial.json').is_file():
            args.raw = args.raw.parent/'raw.partial.json'
        elif args.raw.is_file() and args.raw.name == 'raw.json' and (args.raw.parent/'raw.partial.json').is_file():
            try:
                read(args.raw)
            except (ValueError, TypeError):
                args.unparsed_final_raw_identity = identity(args.raw, args.project.resolve())
                args.raw = args.raw.parent/'raw.partial.json'
        try:
            if args.raw.name == 'raw.partial.json':
                result = preserved_failure(args, ValueError('Captured checkpoint is not a final completed worker output'))
            else:
                result = evaluate(args)
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            result = preserved_failure(args, error)
    else:
        result = bind(args)
    with args.output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'mode': args.mode, 'status': result['status'], 'checks_passed': result['checks_passed'],
        'engineering_qualified': result['engineering_qualified'], 'output': identity(args.output)}, sort_keys=True))
