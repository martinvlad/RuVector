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
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('epoch39_launcher_stdlib_common', HERE / 'common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def supervisor_identity():
    row = C.proc(os.getpid())
    if not row or row['pgid'] != os.getpid() or row['sid'] != os.getpid():
        raise RuntimeError('Detached supervisor session identity is not exact')
    return {'pid':row['pid'],'startticks':row['ticks'],'pgid':row['pgid'],'sid':row['sid']}


def group(pgid):
    rows = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            row = C.proc(int(path.name))
            if row and row['pgid'] == pgid and row['sid'] == pgid and row['state'] not in ('Z', 'X'):
                rows.append(row)
    return rows


def signal_owned_session(worker, identity, sig, signals):
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


def recover_preexec_identity(path):
    """Recover only the just-reserved direct child's preexec session proof.

    This never upgrades an uncertain exec to a verified worker start.
    """
    until = time.monotonic() + 1
    record, last_error = None, None
    while record is None:
        if path.is_file() and path.stat().st_size:
            try:
                record = C.read(path)
            except (ValueError, OSError) as error:
                last_error = error
        if record is not None:
            break
        if time.monotonic() >= until:
            if last_error is not None:
                raise RuntimeError('Incomplete durable preexec proof after bounded observation') from last_error
            return None
        time.sleep(.01)
    identity = record.get('process_identity')
    if (record.get('status') not in ('CPU_GUARD_INSTALLED_BEFORE_EXEC', 'CPU_GUARD_FAILED_BEFORE_EXEC')
            or not isinstance(identity, dict) or type(identity.get('pid')) is not int
            or identity['pid'] <= 0 or identity['pid'] in (os.getpid(), C.OWNER_PID)
            or identity.get('ppid') != os.getpid() or identity.get('pgid') != identity['pid']
            or identity.get('sid') != identity['pid'] or type(identity.get('ticks')) is not int
            or identity['ticks'] <= 0):
        raise RuntimeError('Uncertain Popen lacks exact direct-child preexec session proof')
    return identity


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    C.put(path, value)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reserve(study, plan_sha, phase):
    if phase not in C.PHASES:
        raise ValueError('Only the real FinFact DEV phase may reserve a worker')
    out = study / ('runs/' + phase)
    if out.exists():
        raise RuntimeError('Existing run closes the one worker slot')
    put(study / (phase.upper() + '_ATTEMPT_RESERVATION.json'), {'epoch': 39, 'kind': C.KIND,
        'phase': phase, 'owned_workers_reserved': 1, 'allowed_further_phase_workers': 0, 'before_Popen': True,
        'plan_sha256': plan_sha, 'at_unix': time.time(), 'automatic_retry': False})
    out.mkdir(parents=True, exist_ok=False)
    return out


def completion_invariants(raw,plan,phase):
    counters=raw.get('counters');valid=isinstance(counters,dict)
    if not valid:counters={}
    expected=plan['expected_operation_counters']['dev'];facts=raw.get('closure_facts',{})
    ids=plan['data_roles']['dev'];arms=plan['arms'];required={i+'::'+a for i in ids for a in arms}
    offline=raw.get('offline_policy',{})
    return {'raw_forecasts_complete_without_gold':raw.get('phase')=='dev' and raw.get('status')=='DEV_FORECASTS_COMPLETE_NO_GOLD',
        'exact_frozen_operation_counts':valid and all(type(counters.get(k))is int and counters[k]==v for k,v in expected.items()),
        'forbidden_operation_counts_zero':all(type(counters.get(k))is int and counters[k]==0 for k in C.phase_zero(phase)),
        'worker_errors_empty':raw.get('errors')==[],
        'offline_policy_closed':offline.get('clean')is True and offline.get('literal_capability_bind_closed')is True,
        'all48_unique_forecasts':len(raw.get('completed_readout_ids',[]))==48 and set(raw.get('completed_readout_ids',[]))==required,
        'all48_required':len(raw.get('required_readout_ids',[]))==48 and set(raw.get('required_readout_ids',[]))==required,
        'native_child_closed':facts.get('native_child_closed')is True,
        'both_readers_disposed_in_order':facts.get('model_profiles_disposed')==['xxlarge','b354'],
        'all_forecasts_closed_before_gold':facts.get('all_forecasts_closed_before_gold')is True,
        'gold_not_decoded':counters.get('gold_reader_calls')==0 and counters.get('semantic_gold_labels_decoded')==0}


def safe_error(error,stage=None):
    row={'type':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()}
    if stage is not None:row['stage']=stage
    return row


def load_raw_preserving_failure(path, errors):
    C.no_symlink(path)
    if not path.is_file():
        return {}
    try:
        value = C.read(path)
        if not isinstance(value, dict):
            raise ValueError('Raw output must be a JSON object')
        return value
    except BaseException as error:
        errors.append(safe_error(error,'raw_read_or_parse'))
        return {}


def select_operation_counters(raw, partial):
    """Preserve observed final/checkpoint counters; absence never becomes zero."""
    if isinstance(raw.get('counters'), dict):
        return raw['counters'], 'raw.json'
    if isinstance(partial.get('counters'), dict):
        return partial['counters'], 'raw.partial.json'
    return None, 'UNKNOWN'


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'admission', 'scope'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--phase', choices=C.PHASES, required=True)
    args = parser.parse_args()
    started, startwall = INVOCATION_MONOTONIC, INVOCATION_UNIX
    def interrupted(signum, frame):
        raise InterruptedError('Launcher received ' + signal.Signals(signum).name)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    os.sched_setaffinity(0, {0, 1})
    if os.sched_getaffinity(0) != {0, 1}:
        raise RuntimeError('Launcher CPU0,1 mask missing')
    if args.scope.absolute() != C.SCOPE:
        raise ValueError('Wrong fresh executor scope')
    C.owner_lock()
    if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
        raise ValueError('Unknown exact source plan')
    provisional = C.read(args.plan)
    dispatch, dispatch_attempt = C.dispatch_proof(provisional, args.expected_plan_sha, args.admission)
    started, startwall = dispatch['dispatch_monotonic_seconds'], dispatch['dispatch_unix_seconds']
    out = reserve(C.STUDY, args.expected_plan_sha, args.phase)
    external=C.external_path(C.SCOPE/'run-external');external.mkdir(exist_ok=True)
    plan=provisional;admission=owner=None
    worker = identity = error = None
    recovered_identity, recovered_exit_code = None, None
    cpu_fd, cpu_path = None, out / 'worker-cpu-preexec.json'
    signals, cleanup_errors, stdout, stderr = [], [], b'', b''
    communicated, uncertain, popen_attempted = False, False, False


    try:
        # This alarm also bounds source/asset checks before worker Popen.
        signal.signal(signal.SIGALRM, interrupted)
        signal.setitimer(signal.ITIMER_REAL, max(.001, started + 600 - time.monotonic()))
        admission, owner = C.admission(args.admission, provisional, args.expected_plan_sha, args.phase)
        plan = C.verify_plan(args.plan, args.expected_plan_sha, args.phase)
        C.verify_runtime(plan)
        if plan['worker_path'] != str((C.CANDIDATE / 'worker.py').relative_to(C.ROOT)):
            raise ValueError('Wrong exact worker')
        if str(Path(plan['inference_python']).resolve()) != str(Path(sys.executable).resolve()):
            raise ValueError('Expected current standard-library Python interpreter')
        deadline = min(startwall + 585, C.read(args.scope / 'owner.json')['expires_unix'] - 15)
        if min(deadline - time.time(), started + 585 - time.monotonic()) < 60:
            raise RuntimeError('Insufficient unexpired lease before reservation')
        cpu = C.load_module('epoch39_whole_worker_cpu_guard', HERE / 'cpu_guard.py')
        cpu_fd = os.open(cpu_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        preexec = cpu.make_preexec(cpu_fd)
        directory_fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        env = dict(os.environ)
        for name in ('NODE_OPTIONS', 'E39_GUARD_SYNTHETIC'):
            env.pop(name, None)
        env.update({key: '2' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'RAYON_NUM_THREADS', 'TOKIO_WORKER_THREADS', 'ORT_NUM_THREADS', 'ORT_INTRA_OP_NUM_THREADS')})
        env.update(ORT_INTER_OP_NUM_THREADS='1', UV_THREADPOOL_SIZE='1', TOKENIZERS_PARALLELISM='false',
            PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', LC_ALL='C.UTF-8', HF_HUB_OFFLINE='1',
            TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
        temporary=C.ROOT.parent/'runtime39-tmp';temporary.mkdir(exist_ok=True)
        C.no_symlink(temporary)
        env.update(TMPDIR=str(temporary),HF_HOME=str(temporary/'hf'),TORCH_HOME=str(temporary/'torch'))
        env.update(E39_PHASE=args.phase, E39_PROJECT=str(C.ROOT), E39_OUT=str(out), E39_PLAN=str(args.plan),
            E39_EXTERNAL_RUN=str(external), E39_NATIVE_ROOT=plan['native_asset_root'],
            E39_PLAN_SHA=args.expected_plan_sha, E39_ADMISSION=str(args.admission))
        command = [plan['inference_python'], '-I', '-B', str(C.CANDIDATE / 'worker.py'), '--phase', args.phase, '--plan', str(args.plan),
            '--expected-plan-sha', args.expected_plan_sha, '--admission', str(args.admission),
            '--out', str(out), '--deadline', str(deadline)]
        put(out / 'launch-intent.json', {'argv': command, 'start_new_session': True,
            'outer_total_seconds_cap': 600, 'worker_deadline_unix': deadline,
            'cleanup_deadline_unix': startwall + 600, 'CPU_affinity': [0, 1],
            'computational_thread_environment_budget': 2, 'total_OS_thread_count_is_not_asserted2': True,
            'automatic_retry': False, 'secret_values_recorded': False,
            'CPU_guard_before_entire_Python_worker_exec': True,
            'descendant_Node_must_inherit_without_repeat_setaffinity': True})
        C.owner_lock(admission)
        popen_attempted = True  # Irreversible boundary BEFORE the actual Popen API call.
        uncertain = True  # An attempted Popen without a returned identity remains uncertain.
        worker = subprocess.Popen(command, cwd=C.ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, preexec_fn=preexec, pass_fds=(cpu_fd,))
        identity = C.proc(worker.pid)
        uncertain = identity is None or identity['pgid'] != worker.pid or identity['sid'] != worker.pid
        put(out / 'attempt.json', {'pid': worker.pid, 'pgid': identity['pgid'] if identity else None,
            'sid': identity['sid'] if identity else None, 'startticks': identity['ticks'] if identity else None,
            'verified_process_start': not uncertain, 'uncertain_start': uncertain,
            'at_unix': time.time(), 'deadline_unix': deadline})
        if uncertain:
            raise RuntimeError('Exact returned worker identity uncertain; no retry')
        # Also cap by monotonic time; a backwards wall-clock jump cannot
        # extend the single worker beyond the original585s work allowance.
        timeout = min(deadline - time.time(), started + 585 - time.monotonic())
        if timeout <= 0:
            raise TimeoutError('Whole invocation worker deadline expired')
        while True:
            C.owner_lock(admission)
            timeout = min(deadline - time.time(), started + 585 - time.monotonic())
            if timeout <= 0:
                raise TimeoutError('Dispatch-bound work deadline expired')
            try:
                stdout, stderr = worker.communicate(timeout=min(.5, timeout))
                communicated = True
                break
            except subprocess.TimeoutExpired as pending:
                # communicate returns cumulative buffers on a timeout. Never
                # append/replay them across polls, which would duplicate bytes.
                stdout, stderr = pending.output or b'', pending.stderr or b''
    except BaseException as exc:
        error = safe_error(exc)
        import traceback
        (external/'launcher-exact-error.txt').write_text(traceback.format_exc())
        if isinstance(exc, subprocess.TimeoutExpired):
            stdout, stderr = exc.output or b'', exc.stderr or b''
    finally:
        # Complete the owned cleanup once even if cancellation signals repeat.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if cpu_fd is not None:
            os.close(cpu_fd)
        cleanup_target = worker
        if worker is None and uncertain:
            try:
                recovered_identity = recover_preexec_identity(cpu_path)
                if recovered_identity is not None:
                    identity = recovered_identity
                    cleanup_target = SimpleNamespace(pid=identity['pid'])
            except BaseException as exc:
                cleanup_errors.append(safe_error(exc,'uncertain_preexec_identity_recovery'))
        if cleanup_target is not None:
            try:
                if group(cleanup_target.pid):
                    signal_owned_session(cleanup_target, identity, signal.SIGTERM, signals)
                    until = min(time.monotonic() + 3, started + 594)
                    while group(cleanup_target.pid) and time.monotonic() < until:
                        time.sleep(.05)
                if group(cleanup_target.pid):
                    signal_owned_session(cleanup_target, identity, signal.SIGKILL, signals)
                if worker is not None and worker.poll() is None:
                    worker.wait(timeout=max(.001, min(3, started + 597 - time.monotonic())))
                elif worker is None:
                    current = C.proc(cleanup_target.pid)
                    if current is None or current['ticks'] == identity['ticks']:
                        try:
                            waited, status = os.waitpid(cleanup_target.pid, os.WNOHANG)
                            if waited == cleanup_target.pid:
                                recovered_exit_code = os.waitstatus_to_exitcode(status)
                        except ChildProcessError:
                            pass
            except BaseException as exc:
                cleanup_errors.append(safe_error(exc,'owned_group_cleanup'))
            if worker is not None and not communicated:
                try:
                    stdout, stderr = worker.communicate(timeout=1)
                    communicated = True
                except BaseException as exc:
                    cleanup_errors.append(safe_error(exc,'final_output_capture'))
        (external / 'worker.stdout').write_bytes(stdout)
        (external / 'worker.stderr').write_bytes(stderr)
        living = group(cleanup_target.pid) if cleanup_target is not None else []
        closure_known = not (worker is None and uncertain and cleanup_target is None)
        raw_path = out / 'raw.json'
        raw = load_raw_preserving_failure(raw_path, cleanup_errors)
        partial_path = out / 'raw.partial.json'
        partial = load_raw_preserving_failure(partial_path, cleanup_errors)
        checkpoint_tmp = out / 'raw.partial.pending.json'
        operation_counters, counter_source = select_operation_counters(raw, partial)
        invariants = completion_invariants(raw, plan, args.phase)
        cpu_receipt = load_raw_preserving_failure(cpu_path, cleanup_errors)
        invariants['whole_worker_CPU_guard_before_exec'] = (
            cpu_receipt.get('status') == 'CPU_GUARD_INSTALLED_BEFORE_EXEC'
            and cpu_receipt.get('CPU_affinity') == [0, 1]
            and cpu_receipt.get('actual_proc_status', {}).get('NoNewPrivs') == '1'
            and cpu_receipt.get('actual_proc_status', {}).get('Seccomp') == '2')
        elapsed = time.monotonic() - started
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        closed_integrity = (worker is not None and worker.returncode in (0,2) and error is None and not cleanup_errors
            and not uncertain and not living and communicated and all(invariants.values()) and elapsed <= 600
            and C.sha(args.plan) == args.expected_plan_sha)
        good=closed_integrity and worker.returncode==0 and raw.get('status') in ('DEV_FORECASTS_COMPLETE_NO_GOLD',)
        engineering_rejected=False  # Semantic refusal is a completed engineering capture, not an execution error.
        corpus_reservations={}
        for role in ('dev',):
            path=out/(role.upper()+'_CORPUS_ATTEMPT_RESERVATION.json');C.no_symlink(path)
            corpus_reservations[role]=({'path':str(path.relative_to(C.ROOT)),'bytes':path.stat().st_size,'sha256':C.sha(path)} if path.is_file() else None)
        report = {'schema_version': 1, 'epoch': 39, 'kind': C.KIND,
            'phase': args.phase, 'plan_sha256': args.expected_plan_sha,
            'supervisor_identity': supervisor_identity(), 'kernel_boot_id': C.BOOT_ID, 'pid_namespace_inode': C.PIDNS_INODE,
            'dispatch_reservation': {'path': str((C.STUDY/'DISPATCH_RESERVATION.json').relative_to(C.ROOT)), 'bytes': (C.STUDY/'DISPATCH_RESERVATION.json').stat().st_size, 'sha256': C.sha(C.STUDY/'DISPATCH_RESERVATION.json')},
            'dispatch_attempt': {'path': str((C.STUDY/'DISPATCH_ATTEMPT.json').relative_to(C.ROOT)), 'bytes': (C.STUDY/'DISPATCH_ATTEMPT.json').stat().st_size, 'sha256': C.sha(C.STUDY/'DISPATCH_ATTEMPT.json')},
            'logical_native_budget_reserved': 1, 'budget_count_scope': 'max(dispatch claim,DEV reservation)=1 logical worker; exactlyone DEV corpus reservation',
            'status': 'WORKER_COMPLETED' if good else ('WORKER_DEV_REJECTED' if engineering_rejected else 'WORKER_FAILED_OR_TIMEOUT'),
            'corpus_reservations':corpus_reservations,'corpus_reservation_count':sum(v is not None for v in corpus_reservations.values()),
            'worker_popen_attempted': popen_attempted, 'worker_popen_attempts': int(popen_attempted),
            'worker_start_boundary': ('WORKER_POPEN_ATTEMPTED' if popen_attempted else
                ('KNOWN_FAILURE_BEFORE_WORKER_POPEN' if error else 'UNKNOWN')),
            'worker_attempts_reserved': 1, 'verified_worker_starts': int(identity is not None and not uncertain),
            'worker_identity': identity, 'uncertain_start': uncertain, 'exit_code': worker.returncode if worker else None,
            'worker_identity_source': 'returned_Popen' if worker is not None else ('durable_preexec_only' if recovered_identity else 'UNKNOWN'),
            'recovered_preexec_child_identity': recovered_identity,
            'recovered_preexec_exit_code': recovered_exit_code,
            'launcher_error': error, 'cleanup_signals': signals, 'cleanup_errors': cleanup_errors,
            'stdout_stderr_capture_completed': communicated,
            'owned_live_group_members': living if closure_known else None,
            'owned_live_processes_closed': (not living) if closure_known else None,
            'owned_process_closure_observation': 'OBSERVED' if closure_known else 'UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF',
            'wall_seconds_including_init_cleanup': elapsed,
            'CPU_affinity': sorted(os.sched_getaffinity(0)), 'children_user_seconds': usage.ru_utime,
            'children_system_seconds': usage.ru_stime, 'largest_child_peak_RSS_bytes': usage.ru_maxrss * 1024,
            'raw':C.ref(raw_path) if raw_path.exists() else None,
            'external_evidence':{p.name:C.ref(p,True) for p in (external/'worker.stdout',external/'worker.stderr',external/'launcher-exact-error.txt')if p.is_file()},
            'raw_bytes': raw_path.stat().st_size if raw_path.exists() else None,
            'raw_sha256': C.sha(raw_path) if raw_path.exists() else None,
            'raw_operation_counters': operation_counters, 'raw_operation_counters_source': counter_source,
            'operation_counts_complete': counter_source == 'raw.json',
            'backend_execution_since_checkpoint': 'NOT_APPLICABLE_FINAL_RAW' if counter_source == 'raw.json' else 'UNKNOWN',
            'raw_closure_invariants': invariants,
            'worker_cpu_guard_preexec_artifact': ({'path': str(cpu_path.relative_to(C.ROOT)),
                'bytes': cpu_path.stat().st_size, 'sha256': C.sha(cpu_path)} if cpu_path.is_file() else None),
            'worker_cpu_guard_preexec': cpu_receipt or None,
            'actual_denied_affinity_syscalls': None,
            'partial_raw_bytes': partial_path.stat().st_size if partial_path.exists() else None,
            'partial_raw_sha256': C.sha(partial_path) if partial_path.exists() else None,
            'leftover_checkpoint_tmp_bytes': checkpoint_tmp.stat().st_size if checkpoint_tmp.exists() else None,
            'leftover_checkpoint_tmp_sha256': C.sha(checkpoint_tmp) if checkpoint_tmp.exists() else None,
            'source_plan_unchanged': C.sha(args.plan) == args.expected_plan_sha,
            'stdout_sha256': hashlib.sha256(stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
            'allowed_further_phase_workers': 0,
            'CONF_calls': (0 if counter_source=='raw.json'and all(operation_counters.get(k)==0 for k in C.phase_zero(args.phase)if k.startswith('CONF_'))else None),
            'paid_calls': operation_counters.get('paid_calls')if counter_source=='raw.json'else None,
            'GPU_calls': operation_counters.get('GPU_calls')if counter_source=='raw.json'else None,
            'benchmark_generalization_claim': False}
        put(out / 'execution.json', report)
        put(out / 'raw-seal.json', {'epoch': 39, 'kind': C.KIND, 'phase': args.phase, 'raw_sha256': report['raw_sha256'],
            'raw_bytes': report['raw_bytes'], 'execution_sha256': C.sha(out / 'execution.json'),
            'owned_group_closed': (not living) if closure_known else None, 'raw_closure_invariants': invariants,
            'benchmark_annotation_choices_accessed': 0, 'plan_sha256': args.expected_plan_sha})
        put(C.STUDY/'SUPERVISOR_COMPLETION.json', {'schema_version':1,'epoch':39,'kind':C.KIND,'phase':'dev',
            'status':'SUPERVISOR_ABOUT_TO_EXIT', 'supervisor_identity':supervisor_identity(),
            'kernel_boot_id':C.BOOT_ID,'pid_namespace_inode':C.PIDNS_INODE,
            'execution_sha256':C.sha(out/'execution.json'),'execution_status':report['status'],
            'intended_exit_code':0 if report['status']=='WORKER_COMPLETED' else 2,
            'exit_code_observed_by_root':False,'requires_external_physical_supervisor_closure':True})
        signal.setitimer(signal.ITIMER_REAL,0)
        print(json.dumps(report))
    if time.monotonic() - started > 600:
        raise RuntimeError('Whole process bound exceeded; no retry')
    return 0 if report['status'] == 'WORKER_COMPLETED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
