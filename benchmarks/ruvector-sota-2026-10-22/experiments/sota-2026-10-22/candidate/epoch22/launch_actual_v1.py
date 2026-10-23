"""One-shot CPU2/600s phase launcher with durable starts and owned cleanup."""
from __future__ import annotations
import time
INVOCATION_STARTED_UNIX = time.time()
INVOCATION_STARTED_MONOTONIC = time.monotonic()
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import common as C


def now(): return datetime.now(timezone.utc).isoformat()


def process_info(pid):
    try:
        x = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': x[0], 'pgid': int(x[2]), 'sid': int(x[3]), 'start_ticks': int(x[19])}
    except (OSError, ValueError, IndexError): return None


def alive(pid):
    v = process_info(pid)
    return bool(v and v['state'] not in ('Z', 'X'))


def members(pgid):
    result = []
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            v = process_info(int(p.name))
            if v and v['pgid'] == pgid and v['sid'] == pgid and v['state'] not in ('Z', 'X'): result.append(v)
    return sorted(result, key=lambda v: v['pid'])


def close_owned_group(pgid, ticks, deadline):
    result = {'pgid': pgid, 'signals': [], 'owned_live_before': members(pgid), 'owned_live_pids': []}
    leader = process_info(pgid)
    if leader and ticks is not None and leader['start_ticks'] != ticks:
        result.update(error='Original leader PID reused; refused uncertain signal',
                      owned_live_pids=[v['pid'] for v in members(pgid)])
        return result
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not members(pgid): break
        try: os.killpg(pgid, sig); result['signals'].append(signal.Signals(sig).name)
        except ProcessLookupError: break
        until = min(deadline - .05, time.time() + (.6 if sig == signal.SIGTERM else .5))
        while members(pgid) and time.time() < until: time.sleep(.02)
    result['owned_live_pids'] = [v['pid'] for v in members(pgid)]
    result['finished_within_deadline'] = time.time() <= deadline
    return result


def launch(plan_path, admission_path, phase):
    started_unix = INVOCATION_STARTED_UNIX; started = INVOCATION_STARTED_MONOTONIC
    plan = C.require_plan(plan_path); digest = C.sha(plan_path)
    C.verify_admission(admission_path, digest, phase)
    if str(Path(sys.executable).absolute()) != plan['inference_python']:
        raise ValueError('Exact fresh reviewed inference Python required')
    # Two extra seconds cover interpreter entry and the final small receipts.
    hard = min(started_unix + 598, plan['lease_expires_unix'] - 30); deadline = hard - 5
    if deadline - time.time() < 60: raise RuntimeError('Insufficient lease; no worker reserved')
    folder = C.STUDY / 'runs' / phase
    folder.mkdir(parents=True, exist_ok=False)
    C.write_new(folder / 'reservation.json', {'at': now(), 'state': 'PREPARED_NOT_ACTUAL_START',
        'phase': phase, 'plan_sha256': digest, 'worker_attempt': 1 if phase == 'dev' else 2})
    env = dict(os.environ)
    for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
              'RAYON_NUM_THREADS', 'UV_THREADPOOL_SIZE'): env[k] = '2'
    env.update(TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    affinity = sorted(os.sched_getaffinity(0))[:2]
    process = None; exit_code = None; error = None; actual_affinity = None; ticks = None
    cleanup = {'owned_live_pids': [], 'scope': 'No PID returned, no process start inferred'}
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with (folder / 'worker.log').open('x') as log:
        C.write_new(folder / 'popen-attempt.json', {'at': now(), 'state': 'DURABLE_IMMEDIATELY_BEFORE_POPEN',
            'phase': phase, 'pid': None, 'pgid': None, 'plan_sha256': digest,
            'worker_attempt': 1 if phase == 'dev' else 2, 'automatic_retry': False,
            'scope': 'Consumes phase slot even if Popen fails; not proof model/native ran'})
        try:
            command = [sys.executable, '-B', str(Path(__file__).with_name('worker_actual_v1.py')),
                '--plan', str(plan_path), '--expected-plan-sha', digest,
                '--admission', str(admission_path), '--phase', phase, '--deadline', str(deadline)]
            process = subprocess.Popen(command, cwd=C.ROOT, env=env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True,
                preexec_fn=lambda: os.sched_setaffinity(0, affinity))
            info = process_info(process.pid); ticks = info['start_ticks'] if info else None
            try: actual_affinity = sorted(os.sched_getaffinity(process.pid))
            except ProcessLookupError: pass
            C.write_new(folder / 'attempt.json', {'at': now(), 'pid': process.pid, 'pgid': process.pid,
                'phase': phase, 'start_ticks': ticks, 'plan_sha256': digest,
                'invocation_started_unix': started_unix, 'deadline_unix': deadline,
                'hard_cleanup_deadline_unix': hard, 'observed_CPU_affinity': actual_affinity,
                'worker_attempt': 1 if phase == 'dev' else 2, 'automatic_retry': False})
            exit_code = process.wait(timeout=max(.001, deadline - time.time()))
        except BaseException as exc: error = type(exc).__name__ + ': ' + str(exc)
        finally:
            if process is not None:
                cleanup = close_owned_group(process.pid, ticks, hard)
                if process.returncode is None:
                    try: exit_code = process.wait(timeout=max(.001, hard - time.time()))
                    except subprocess.TimeoutExpired: error = (error or '') + '; worker not reaped by hard deadline'
                else: exit_code = process.returncode
    native_attempts = [C.read(p) for p in sorted(folder.glob('native-attempt-*.json'))]
    raw = C.read(folder / 'raw.json') if (folder / 'raw.json').exists() else None
    after = resource.getrusage(resource.RUSAGE_CHILDREN); elapsed = time.monotonic() - started
    execution = {'schema_version': 1, 'epoch': 22, 'phase': phase, 'at': now(), 'plan_sha256': digest,
        'worker_attempts': 1, 'verified_worker_starts': int(process is not None),
        'worker_pid': process.pid if process else None, 'worker_pgid': process.pid if process else None,
        'native_helper_pids': [r['pid'] for r in native_attempts], 'worker_exit_code': exit_code,
        'error': error, 'elapsed_seconds': elapsed, 'CPU_affinity': actual_affinity,
        'user_seconds': after.ru_utime - before.ru_utime, 'system_seconds': after.ru_stime - before.ru_stime,
        'peak_RSS_bytes': after.ru_maxrss * 1024,
        'resource_scope': 'Outer Linux RUSAGE_CHILDREN for one owned worker plus reaped descendants; maximum is largest child high-water, not simultaneous RSS sum.',
        'source_plan_unchanged': C.sha(plan_path) == digest,
        'raw_sha256': C.sha(folder / 'raw.json') if raw else None,
        'observed_worker_status': raw.get('status') if raw else None,
        'cleanup': {'worker_exited': bool(process and process.poll() is not None and not alive(process.pid)),
            'all_native_helpers_exited': all(not alive(r['pid']) for r in native_attempts),
            'process_group_empty': not members(process.pid) if process else None,
            'owned_live_pids': cleanup.get('owned_live_pids'), 'details': cleanup},
        'benchmark_HTTP_requests': 0, 'new_paid_API_GPU_calls': 0, 'automatic_retry': False,
        'allowed_further_attempts_in_this_phase': 0}
    good = (exit_code == 0 and not error and elapsed <= 600 and execution['source_plan_unchanged']
        and all(execution['cleanup'].get(k) is True for k in ('worker_exited', 'all_native_helpers_exited', 'process_group_empty')))
    execution['status'] = ('COMPLETED_AWAITING_INDEPENDENT_REPLAY' if good else 'FAILED_OR_INCOMPLETE_PRESERVED_EVIDENCE')
    C.write_new(folder / 'execution.json', execution)
    C.write_new(C.STUDY / ('phase.' + phase + '.completion.json'), {'at': now(), 'phase': phase,
        'status': execution['status'], 'worker_attempts': 1, 'verified_worker_starts': execution['verified_worker_starts'],
        'execution_path': str((folder / 'execution.json').relative_to(C.ROOT)),
        'execution_sha256': C.sha(folder / 'execution.json'), 'engineering_qualified': None,
        'accepted': False, 'champion_promoted': False, 'allowed_further_attempts_in_this_phase': 0,
        'official_score': None, 'official_rank': None})
    if not good: raise RuntimeError('Actual phase failed; preserve evidence and never retry')
    return execution


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--admission', type=Path); ap.add_argument('--phase', choices=('dev', 'confirmation'), default='dev')
    ap.add_argument('--check-plan', action='store_true'); ap.add_argument('--verify-assets', action='store_true')
    args = ap.parse_args()
    if args.check_plan:
        plan = C.require_plan(args.plan); assets = None
        if args.verify_assets:
            import worker_actual_v1
            _, rows, versions = worker_actual_v1.verify_assets(plan)
            assets = {'files': len(rows), 'versions': len(versions), 'model_native_imports': 0}
        print(json.dumps({'status': 'FULL_UNMOCKED_SOURCE_PLAN_PASS', 'pins': len(plan['pins']),
            'plan_sha256': C.sha(args.plan), 'asset_verification': assets, 'native_execution_admitted': False})); return
    if not args.admission: ap.error('Actual launch needs exact late published-source admission')
    print(json.dumps({'status': launch(args.plan, args.admission, args.phase)['status']}))


if __name__ == '__main__': main()
