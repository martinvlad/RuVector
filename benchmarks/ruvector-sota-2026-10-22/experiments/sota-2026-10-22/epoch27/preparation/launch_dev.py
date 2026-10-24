"""One reserved DEV diagnostic, isolated CPU2 worker, ≤585s +15s cleanup."""
import time
INVOCATION_UNIX = time.time()
INVOCATION_MONOTONIC = time.monotonic()
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import re
import resource
import signal
import stat
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def put(path, value):
    assert path.resolve() == path and not path.is_symlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def proc(pid):
    try:
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'sid': int(fields[3]), 'ticks': int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def group(pgid):
    rows = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            row = proc(int(path.name))
            if row and row['pgid'] == pgid and row['sid'] == pgid and row['state'] not in ('Z', 'X'):
                rows.append(row)
    return rows


def guard(scope):
    owner = json.loads((scope / 'owner.json').read_text())
    assert owner['pid'] == 75591 and owner['startticks'] == 15190845
    assert time.time() < owner['expires_unix'] and not (scope / 'release.request').exists()
    row = proc(owner['pid'])
    assert row and row['ticks'] == owner['startticks'] and row['state'] not in ('Z', 'X')
    lock = Path(owner['lock'])
    assert lock == scope.parent / 'exclusive.work.lock' and lock.resolve() == lock
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        assert stat.S_ISREG(info.st_mode) and info.st_ino == 13626
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        found = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) >= 8 and words[1:5] == ['FLOCK', 'ADVISORY', 'WRITE', '75591']:
                a, b, c = words[5].split(':')
                found |= (int(a, 16), int(b, 16), int(c)) == target
        assert found
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise RuntimeError('Contender unexpectedly acquired scoped guardian lock')
    finally:
        os.close(fd)
    return owner


def reserve(study, plan_sha):
    out = study / 'runs/dev'
    assert not out.exists(), 'Existing run closes the one attempt slot'
    # Exclusive file creation is the single atomic reservation point. It survives
    # Popen failures, process crashes and repeated launcher invocations.
    put(study / 'ATTEMPT_RESERVATION.json', {'epoch': 27, 'phase': 'dev', 'reserved_workers': 1,
        'allowed_further_workers': 0, 'permanently_closed_unspent_slot': True,
        'before_Popen': True, 'plan_sha256': plan_sha, 'at_unix': time.time()})
    out.mkdir(parents=True, exist_ok=False)
    return out


def completion_invariants(raw):
    counts = raw.get('counters', {})
    expected = {'NLI_model_initializations': 1, 'NLI_model_initializations_completed': 1,
        'NLI_forward_pairs_attempted': 72, 'NLI_forward_pairs_completed': 72,
        'NLI_forward_calls_attempted': 72, 'NLI_forward_calls_completed': 72,
        'NLI_forwards': 72, 'DEV_pairs_completed': 72, 'DEV_cases_completed': 24,
        'native_helper_starts': 1, 'native_index_initializations_attempted': 8,
        'native_index_initializations_completed': 8, 'native_queries_attempted': 24,
        'native_queries_completed': 24, 'BGE_initializations_attempted': 1,
        'BGE_initializations_completed': 1, 'ORT_sessions_attempted': 1, 'ORT_sessions_completed': 1}
    zero = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'benchmark_HTTP_requests', 'benchmark_label_reads', 'TRAIN_calibration_fits',
        'CONF_worker_attempts', 'CONF_annotation_choices', 'CONF_NLI_pairs',
        'paid_API_calls', 'GPU_calls', 'fits', 'paid_calls', 'confirmation_calls',
        'generation_calls', 'generated_tokens', 'training_steps', 'optimizer_steps',
        'external_API_calls', 'train_calls', 'calibration_calls')
    return {'raw_completed': raw.get('status') == 'COMPLETED_DEV_DIAGNOSTIC_AWAITING_INDEPENDENT_SCORER',
        'all24cases_3arms_complete': len(raw.get('cases', [])) == 24 and all(
            set(row.get('arms', {})) == {'actual_native', 'lexical', 'positional'}
            and all(arm.get('reader') is not None for arm in row['arms'].values()) for row in raw.get('cases', [])),
        'exact_operation_counts': all(type(counts.get(k)) is int and counts[k] == v for k, v in expected.items()),
        'forbidden_counts_zero': all(type(counts.get(k)) is int and counts[k] == 0 for k in zero),
        'errors_empty': raw.get('errors') == [],
        'persistent_network_violations_empty': raw.get('Python_network_violations') == [],
        'every_allowed_bind_has_outcome': all(event.get('bind_outcome') in ('SUCCESS', 'ERROR')
            for event in raw.get('allowed_local_bind_events', []))}


def load_raw_preserving_failure(path, errors):
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError('Raw output must be a JSON object')
        return raw
    except BaseException as exc:
        errors.append({'stage': 'raw_read_or_parse', 'type': type(exc).__name__, 'message': str(exc)})
        return {}


def main():
    parser = argparse.ArgumentParser()
    for key in ('plan', 'admission', 'scope'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    args = parser.parse_args()
    started, startwall = INVOCATION_MONOTONIC, INVOCATION_UNIX
    os.sched_setaffinity(0, {0, 1})
    owner = guard(args.scope)
    assert digest(args.plan) == args.expected_plan_sha
    plan = json.loads(args.plan.read_text())
    project = Path(plan['actual_project'])
    study = project / 'experiments/sota-2026-10-22/epoch27'
    assert project == args.scope / 'project' and args.plan == study / 'plan.json'
    assert args.admission == study / 'NATIVE_ADMISSION.json'
    assert plan['source_checkpoint'] == '6e4ad4ab0b6a09a6a1083335ed0401637227d17f'
    assert plan['epoch'] == 27 and plan['phase'] == 'dev' and plan['diagnostic_only'] is True
    assert plan['champion_promotion_allowed'] is False and plan['confirmation_execution_allowed'] is False
    admission = json.loads(args.admission.read_text())
    assert admission['verified_actual_remote_readback'] is True and admission['epoch'] == 27 and admission['phase'] == 'dev'
    assert admission['plan_sha256'] == args.expected_plan_sha and admission['source_freeze_sha256'] == plan['source_freeze_sha256']
    assert admission['scope'] == 'benchmarks/ruvector-sota-2026-10-22/'
    assert admission['owner_pid'] == 75591 and admission['owner_startticks'] == 15190845
    assert re.fullmatch('[0-9a-f]{40}', admission['published_source_commit'])
    assert all(plan['benchmark_roles'][k] == [] for k in ('train', 'calibration', 'confirmation'))
    assert len(plan['benchmark_roles']['dev']) == 24
    # Remote admission is already verified before the first pinned DEV-byte hash.
    for row in plan['pins']:
        path = project / row['path']
        assert path.resolve() == path and path.is_file()
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    pins = {row['path']: row for row in plan['pins']}
    assert len(pins) == len(plan['pins'])
    exactworker = 'experiments/sota-2026-10-22/candidate/epoch27/worker.py'
    assert plan['worker_path'] == exactworker and exactworker in pins
    own = Path(__file__).resolve().relative_to(project).as_posix()
    assert pins[own]['sha256'] == digest(Path(__file__).resolve())
    assert plan['inference_python'] == str(project / 'retrieval/.venv/bin/python')
    assert Path(plan['inference_python']).is_file()
    assert pins[plan['source_freeze_path']]['sha256'] == plan['source_freeze_sha256']
    for key, value in {'worker_attempts': 1, 'native_corpus_batches': 1, 'seconds_per_batch': 600,
            'cpu_threads': 2, 'paid_calls': 0, 'GPU_calls': 0, 'NLI_model_initializations': 1, 'NLI_forward_pairs': 72}.items():
        assert type(plan['limits'][key]) is int and plan['limits'][key] == value
    deadline = min(startwall + 585, owner['expires_unix'] - 15)
    if deadline - time.time() < 60:
        raise RuntimeError('Insufficient bounded lease before reserving worker')
    out = reserve(study, args.expected_plan_sha)
    env = dict(os.environ)
    env.update({key: '2' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
        'NUMEXPR_NUM_THREADS', 'RAYON_NUM_THREADS', 'TOKIO_WORKER_THREADS')})
    env.update(UV_THREADPOOL_SIZE='1', TOKENIZERS_PARALLELISM='false', PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    command = [plan['inference_python'], '-I', '-B', str(project / plan['worker_path']),
        '--plan', str(args.plan), '--expected-plan-sha', args.expected_plan_sha,
        '--admission', str(args.admission), '--out', str(out), '--deadline', str(deadline)]
    put(out / 'launch-intent.json', {'argv': command, 'start_new_session': True, 'outer_total_seconds_cap': 600,
        'worker_deadline_unix': deadline, 'cleanup_deadline_unix': startwall + 600, 'CPU_affinity': [0, 1],
        'secret_values_recorded': False, 'automatic_retry': False})
    worker = identity = error = None
    signals, cleanup_errors = [], []
    stdout = stderr = b''
    uncertain = False
    communicated = False

    def signal_owned(sig):
        members = group(worker.pid)
        if not members:
            return
        if identity is None or identity['pgid'] != worker.pid or identity['sid'] != worker.pid:
            raise RuntimeError('Cannot prove exact original process/session; refuse signal')
        leader = proc(worker.pid)
        if leader is not None:
            assert leader['ticks'] == identity['ticks'] and leader['pgid'] == worker.pid and leader['sid'] == worker.pid
        for row in members:
            current = proc(row['pid'])
            if current is not None:
                assert current['ticks'] == row['ticks'] and current['pgid'] == worker.pid and current['sid'] == worker.pid
        try:
            os.killpg(worker.pid, sig)
            signals.append(signal.Signals(sig).name)
        except ProcessLookupError:
            pass

    try:
        guard(args.scope)
        worker = subprocess.Popen(command, cwd=project, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True)
        identity = proc(worker.pid)
        uncertain = identity is None or identity['pgid'] != worker.pid or identity['sid'] != worker.pid
        put(out / 'attempt.json', {'pid': worker.pid, 'pgid': identity['pgid'] if identity else None,
            'sid': identity['sid'] if identity else None, 'startticks': identity['ticks'] if identity else None,
            'verified_process_start': not uncertain, 'uncertain_start': uncertain, 'Popen_returned_pid': worker.pid,
            'at_unix': time.time(), 'deadline_unix': deadline})
        if uncertain:
            raise RuntimeError('Worker returned PID but exact session identity not sealed; no retry')
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
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        rawpath = out / 'raw.json'
        raw = load_raw_preserving_failure(rawpath, cleanup_errors)
        invariants = completion_invariants(raw)
        elapsed = time.monotonic() - started
        good = (worker is not None and worker.returncode == 0 and error is None and not cleanup_errors
            and not uncertain and not living and communicated and all(invariants.values())
            and elapsed <= 600 and digest(args.plan) == args.expected_plan_sha)
        report = {'epoch': 27, 'phase': 'dev', 'diagnostic_only': True,
            'status': 'WORKER_COMPLETED' if good else 'WORKER_FAILED_OR_TIMEOUT',
            'worker_attempts_reserved': 1, 'verified_worker_starts': int(identity is not None and not uncertain),
            'Popen_returned_pid': worker.pid if worker else None, 'uncertain_start': uncertain,
            'worker_identity': identity, 'exit_code': worker.returncode if worker else None,
            'launcher_error': error, 'cleanup_signals': signals, 'cleanup_errors': cleanup_errors,
            'stdout_stderr_capture_completed': communicated, 'owned_live_group_members': living,
            'owned_live_processes_closed': not living, 'wall_seconds_including_init_cleanup': elapsed,
            'CPU_affinity': sorted(os.sched_getaffinity(0)), 'largest_child_peak_RSS_bytes': usage.ru_maxrss * 1024,
            'children_user_seconds': usage.ru_utime, 'children_system_seconds': usage.ru_stime,
            'memory_scope': 'RUSAGE_CHILDREN largest-child high-water, not simultaneous aggregate RSS',
            'raw_bytes': rawpath.stat().st_size if rawpath.exists() else None,
            'raw_sha256': digest(rawpath) if rawpath.exists() else None,
            'raw_operation_counters': raw.get('counters'), 'raw_closure_invariants': invariants,
            'source_plan_unchanged': digest(args.plan) == args.expected_plan_sha,
            'stdout_sha256': hashlib.sha256(stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
            'allowed_further_epoch27_workers': 0, 'confirmation_calls': 0, 'paid_calls': 0, 'GPU_calls': 0}
        put(study / 'execution.json', report)
        put(out / 'raw-seal.json', {'epoch': 27, 'phase': 'dev', 'raw_sha256': report['raw_sha256'],
            'raw_bytes': report['raw_bytes'], 'execution_sha256': digest(study / 'execution.json'),
            'owned_group_closed': not living, 'all24cases_complete': invariants['all24cases_3arms_complete'],
            'annotation_choices_accessed_before_seal': 0, 'plan_sha256': args.expected_plan_sha})
        print(json.dumps(report))
    if time.monotonic() - started > 600:
        raise RuntimeError('Whole process bound exceeded; no retry')
    return 0 if report['status'] == 'WORKER_COMPLETED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
