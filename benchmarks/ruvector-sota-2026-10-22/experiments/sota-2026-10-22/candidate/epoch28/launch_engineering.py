"""Single reserved source-admitted worker:585s execution plus15s owned cleanup."""
import time
INVOCATION_UNIX = time.time()
INVOCATION_MONOTONIC = time.monotonic()
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('epoch28_launcher_stdlib_common', HERE / 'common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
EXPECTED = {'native_process_starts_attempted': 1, 'native_process_starts_completed': 1,
    'composite_initializations_attempted': 1, 'composite_initializations_completed': 1,
    'native_ready_receipts': 1, 'native_binary_loads_attempted': 1, 'native_binary_loads_completed': 1,
    'native_stdin_write_calls_attempted': 8, 'native_request_reply_pairs_closed': 8,
    'native_stdout_read_calls_attempted': 9, 'native_stdout_lines_read': 9,
    'composite_predict_attempted': 8, 'composite_predict_completed': 7,
    'native_systemOne_requests': 8, 'native_questions_written': 8, 'native_response_lines': 8,
    'native_successful_responses': 7, 'native_refusal_responses': 1}


def group(pgid):
    rows = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            row = C.proc(int(path.name))
            if row and row['pgid'] == pgid and row['sid'] == pgid and row['state'] not in ('Z', 'X'):
                rows.append(row)
    return rows


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    C.put(path, value)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reserve(study, plan_sha):
    out = study / 'runs/engineering'
    assert not out.exists(), 'Existing run closes the one worker slot'
    put(study / 'ATTEMPT_RESERVATION.json', {'epoch': 28, 'kind': C.KIND,
        'owned_workers_reserved': 1, 'allowed_further_workers': 0, 'before_Popen': True,
        'plan_sha256': plan_sha, 'at_unix': time.time(), 'automatic_retry': False})
    out.mkdir(parents=True, exist_ok=False)
    return out


def completion_invariants(raw):
    counters = raw.get('counters', {})
    requests = raw.get('requests', [])
    return {'raw_completed': raw.get('status') == 'COMPLETED_AUTHORED_QUALIFICATION_AWAITING_INDEPENDENT_REPLAY',
        'all8requests_closed': len(requests) == 8 and all('native_stdout_literal' in row for row in requests),
        'seven_composite_outputs_one_preserved_refusal': sum(row.get('response') is not None for row in requests) == 7
            and sum(row.get('error') is not None for row in requests) == 1,
        'exact_operation_counts': all(type(counters.get(k)) is int and counters[k] == v for k, v in EXPECTED.items()),
        'forbidden_operation_counts_zero': all(type(counters.get(k)) is int and counters[k] == 0 for k in C.ZERO),
        'worker_errors_empty': raw.get('errors') == [],
        'Python_network_violations_empty': raw.get('Python_network_violations') == [],
        'original_native_child_closed': raw.get('native_child_closed') is True}


def load_raw_preserving_failure(path, errors):
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('Raw output must be a JSON object')
        return value
    except BaseException as error:
        errors.append({'stage': 'raw_read_or_parse', 'type': type(error).__name__, 'message': str(error)})
        return {}


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'admission', 'scope'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    args = parser.parse_args()
    started, startwall = INVOCATION_MONOTONIC, INVOCATION_UNIX
    os.sched_setaffinity(0, {0, 1})
    if args.scope.absolute() != C.ROOT.parent or C.ROOT != args.scope / 'project':
        raise ValueError('Wrong fresh executor scope')
    C.owner_lock()
    if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
        raise ValueError('Unknown exact source plan')
    provisional = C.read(args.plan)
    admission, owner = C.admission(args.admission, provisional, args.expected_plan_sha)
    plan = C.verify_plan(args.plan, args.expected_plan_sha)
    C.verify_runtime(plan)
    if plan['worker_path'] != str((HERE / 'worker.py').relative_to(C.ROOT)):
        raise ValueError('Wrong exact worker')
    if str(Path(plan['inference_python']).resolve()) != str(Path(sys.executable).resolve()):
        raise ValueError('Expected current standard-library Python interpreter')
    deadline = min(startwall + 585, C.read(args.scope / 'owner.json')['expires_unix'] - 15)
    if deadline - time.time() < 60:
        raise RuntimeError('Insufficient unexpired lease before reservation')
    out = reserve(C.STUDY, args.expected_plan_sha)
    env = dict(os.environ)
    for name in ('NODE_OPTIONS', 'TYPESAFE_BACKEND', 'E28_GUARD_SYNTHETIC'):
        env.pop(name, None)
    env.update({key: '2' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
        'NUMEXPR_NUM_THREADS', 'RAYON_NUM_THREADS', 'TOKIO_WORKER_THREADS', 'ORT_NUM_THREADS', 'ORT_INTRA_OP_NUM_THREADS')})
    env.update(ORT_INTER_OP_NUM_THREADS='1', UV_THREADPOOL_SIZE='1', TOKENIZERS_PARALLELISM='false',
        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', LC_ALL='C.UTF-8', HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    command = [plan['inference_python'], '-I', '-B', str(HERE / 'worker.py'), '--plan', str(args.plan),
        '--expected-plan-sha', args.expected_plan_sha, '--admission', str(args.admission),
        '--out', str(out), '--deadline', str(deadline)]
    put(out / 'launch-intent.json', {'argv': command, 'start_new_session': True,
        'outer_total_seconds_cap': 600, 'worker_deadline_unix': deadline,
        'cleanup_deadline_unix': startwall + 600, 'CPU_affinity': [0, 1],
        'computational_thread_environment_budget': 2, 'total_OS_thread_count_is_not_asserted2': True,
        'automatic_retry': False, 'secret_values_recorded': False})
    worker = identity = error = None
    signals, cleanup_errors, stdout, stderr = [], [], b'', b''
    communicated, uncertain = False, False

    def signal_owned(sig):
        members = group(worker.pid)
        if not members:
            return
        if identity is None or identity['pgid'] != worker.pid or identity['sid'] != worker.pid:
            raise RuntimeError('Cannot prove original owned process session; refuse signal')
        leader = C.proc(worker.pid)
        if leader is not None:
            if leader['ticks'] != identity['ticks'] or leader['pgid'] != worker.pid or leader['sid'] != worker.pid:
                raise RuntimeError('Exact worker leader identity changed; refuse signal')
        for row in members:
            current = C.proc(row['pid'])
            if current is not None:
                if current['ticks'] != row['ticks'] or current['pgid'] != worker.pid or current['sid'] != worker.pid:
                    raise RuntimeError('Exact owned process/session member identity changed; refuse signal')
        try:
            os.killpg(worker.pid, sig)
            signals.append(signal.Signals(sig).name)
        except ProcessLookupError:
            pass

    try:
        C.owner_lock(admission)
        worker = subprocess.Popen(command, cwd=C.ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True)
        identity = C.proc(worker.pid)
        uncertain = identity is None or identity['pgid'] != worker.pid or identity['sid'] != worker.pid
        put(out / 'attempt.json', {'pid': worker.pid, 'pgid': identity['pgid'] if identity else None,
            'sid': identity['sid'] if identity else None, 'startticks': identity['ticks'] if identity else None,
            'verified_process_start': not uncertain, 'uncertain_start': uncertain,
            'at_unix': time.time(), 'deadline_unix': deadline})
        if uncertain:
            raise RuntimeError('Exact returned worker identity uncertain; no retry')
        stdout, stderr = worker.communicate(timeout=max(.001, deadline - time.time()))
        communicated = True
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        if isinstance(exc, subprocess.TimeoutExpired):
            stdout, stderr = exc.output or b'', exc.stderr or b''
    finally:
        if worker is not None:
            try:
                if group(worker.pid):
                    signal_owned(signal.SIGTERM)
                    until = min(time.monotonic() + 3, started + 594)
                    while group(worker.pid) and time.monotonic() < until:
                        time.sleep(.05)
                if group(worker.pid):
                    signal_owned(signal.SIGKILL)
                if worker.poll() is None:
                    worker.wait(timeout=max(.001, min(3, started + 597 - time.monotonic())))
            except BaseException as exc:
                cleanup_errors.append({'stage': 'owned_group_cleanup', 'type': type(exc).__name__, 'message': str(exc)})
            if not communicated:
                try:
                    stdout, stderr = worker.communicate(timeout=1)
                    communicated = True
                except BaseException as exc:
                    cleanup_errors.append({'stage': 'final_output_capture', 'type': type(exc).__name__, 'message': str(exc)})
        (out / 'worker.stdout').write_bytes(stdout)
        (out / 'worker.stderr').write_bytes(stderr)
        living = group(worker.pid) if worker is not None else []
        raw_path = out / 'raw.json'
        raw = load_raw_preserving_failure(raw_path, cleanup_errors)
        partial_path = out / 'raw.partial.json'
        partial = load_raw_preserving_failure(partial_path, cleanup_errors)
        checkpoint_tmp = out / 'raw.partial.pending.json'
        if isinstance(raw.get('counters'), dict):
            operation_counters, counter_source = raw['counters'], 'raw.json'
        elif isinstance(partial.get('counters'), dict):
            operation_counters, counter_source = partial['counters'], 'raw.partial.json'
        else:
            operation_counters, counter_source = None, 'UNKNOWN'
        invariants = completion_invariants(raw)
        elapsed = time.monotonic() - started
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        good = (worker is not None and worker.returncode == 0 and error is None and not cleanup_errors
            and not uncertain and not living and communicated and all(invariants.values()) and elapsed <= 600
            and C.sha(args.plan) == args.expected_plan_sha)
        report = {'schema_version': 1, 'epoch': 28, 'kind': C.KIND,
            'status': 'WORKER_COMPLETED' if good else 'WORKER_FAILED_OR_TIMEOUT',
            'worker_attempts_reserved': 1, 'verified_worker_starts': int(identity is not None and not uncertain),
            'worker_identity': identity, 'uncertain_start': uncertain, 'exit_code': worker.returncode if worker else None,
            'launcher_error': error, 'cleanup_signals': signals, 'cleanup_errors': cleanup_errors,
            'stdout_stderr_capture_completed': communicated, 'owned_live_group_members': living,
            'owned_live_processes_closed': not living, 'wall_seconds_including_init_cleanup': elapsed,
            'CPU_affinity': sorted(os.sched_getaffinity(0)), 'children_user_seconds': usage.ru_utime,
            'children_system_seconds': usage.ru_stime, 'largest_child_peak_RSS_bytes': usage.ru_maxrss * 1024,
            'raw_bytes': raw_path.stat().st_size if raw_path.exists() else None,
            'raw_sha256': C.sha(raw_path) if raw_path.exists() else None,
            'raw_operation_counters': operation_counters, 'raw_operation_counters_source': counter_source,
            'operation_counts_complete': counter_source == 'raw.json',
            'backend_execution_since_checkpoint': 'NOT_APPLICABLE_FINAL_RAW' if counter_source == 'raw.json' else 'UNKNOWN',
            'raw_closure_invariants': invariants,
            'partial_raw_bytes': partial_path.stat().st_size if partial_path.exists() else None,
            'partial_raw_sha256': C.sha(partial_path) if partial_path.exists() else None,
            'leftover_checkpoint_tmp_bytes': checkpoint_tmp.stat().st_size if checkpoint_tmp.exists() else None,
            'leftover_checkpoint_tmp_sha256': C.sha(checkpoint_tmp) if checkpoint_tmp.exists() else None,
            'source_plan_unchanged': C.sha(args.plan) == args.expected_plan_sha,
            'stdout_sha256': hashlib.sha256(stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
            'allowed_further_epoch28_workers': 0, 'CONF_calls': 0, 'DEV_calls': 0, 'paid_calls': 0, 'GPU_calls': 0,
            'benchmark_generalization_claim': False}
        put(C.STUDY / 'execution.json', report)
        put(out / 'raw-seal.json', {'epoch': 28, 'kind': C.KIND, 'raw_sha256': report['raw_sha256'],
            'raw_bytes': report['raw_bytes'], 'execution_sha256': C.sha(C.STUDY / 'execution.json'),
            'owned_group_closed': not living, 'all8requests_closed': invariants['all8requests_closed'],
            'benchmark_annotation_choices_accessed': 0, 'plan_sha256': args.expected_plan_sha})
        print(json.dumps(report))
    if time.monotonic() - started > 600:
        raise RuntimeError('Whole process bound exceeded; no retry')
    return 0 if report['status'] == 'WORKER_COMPLETED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
