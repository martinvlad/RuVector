"""One source-admitted authored full-input original-comparator qualification."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
import traceback

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('epoch28_stdlib_common', HERE / 'common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
BANK_SHA = 'c3a83ae2a834ecfe534ec421eea21e7414586cc9858e400d105ce5657ad1cc45'
IDS = ['e28-full104-engineering-' + str(i).zfill(2) for i in range(1, 9)]


def status(pid):
    result = {}
    try:
        for line in Path('/proc/' + str(pid) + '/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, unit = line.split()
                result[key.rstrip(':') + '_bytes'] = int(value) * 1024
            elif line.startswith(('Threads:', 'Cpus_allowed_list:', 'NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:')):
                key, value = line.split(':', 1)
                result[key] = value.strip()
    except OSError:
        pass
    observed, races = [], []
    try:
        tasks = sorted((Path('/proc') / str(pid) / 'task').iterdir(), key=lambda path: int(path.name))
    except OSError:
        tasks = []
    for task in tasks:
        try:
            for line in (task / 'status').read_text().splitlines():
                if line.startswith('Cpus_allowed_list:'):
                    literal = line.split(':', 1)[1].strip()
                    cpus = set()
                    for item in literal.split(','):
                        ends = item.split('-')
                        cpus.update(range(int(ends[0]), int(ends[-1]) + 1))
                    observed.append({'tid': int(task.name), 'Cpus_allowed_list': literal,
                        'observed_affinity_within_CPU0_1': bool(cpus) and cpus <= {0, 1}})
                    break
        except FileNotFoundError:
            races.append(int(task.name))
    result['observed_thread_affinities'] = observed
    result['thread_status_disappearance_races'] = races
    result['observability_scope'] = 'Read-only current task snapshots; unobserved thread lifetimes remain unknown.'
    if any(not row['observed_affinity_within_CPU0_1'] for row in observed):
        # Preserve the complete observed snapshot on the exception for raw failure
        # reporting; never rewrite native thread affinities or model settings.
        error = RuntimeError('Observed process thread affinity outside fixed CPU0,1 budget')
        error.observed_process_status = result
        raise error
    return result


def mapped_runtime(pid, runtime):
    """Observe the actual loaded addon/ORT paths, without invoking either API."""
    paths = {line.split()[-1] for line in Path('/proc/' + str(pid) + '/maps').read_text().splitlines()
             if line.split() and line.split()[-1].startswith('/')}
    expected = {str(C.ROOT / row['path']): row for row in runtime['files']
                if row['path'].endswith('.node') or '.so' in row['path']}
    observed = []
    for path in paths:
        if 'typesafe' not in path and 'libonnxruntime' not in path:
            continue
        if path not in expected or C.sha(Path(path)) != expected[path]['sha256']:
            raise ValueError('Actual loaded native/ORT path or hash differs from exact closure')
        observed.append(expected[path])
    names = {row['path'].split('/')[-1] for row in observed}
    if not {'typesafe.linux-x64-gnu.node', 'libonnxruntime.so.1'} <= names:
        raise ValueError('Actual addon and its required ONNX runtime were not observed mapped')
    return sorted(observed, key=lambda row: row['path'])


class Tee:
    """Transparent synchronous TextIO facade; no readers/listeners added."""
    def __init__(self, target, sink, observed, direction, notify=None):
        self.target, self.sink, self.observed, self.direction = target, sink, observed, direction
        self.notify = notify

    def write(self, value):
        if self.notify is not None:
            self.notify('attempt', value, None)
        count = self.target.write(value)
        actual = value[:count]
        if self.notify is not None:
            self.notify('accepted', actual, count == len(value))
        self.sink.write(actual.encode('utf-8'))
        self.sink.flush()
        os.fsync(self.sink.fileno())
        self.observed.append(actual)
        return count

    def readline(self, *args):
        if self.notify is not None:
            self.notify('read_attempt', None, None)
        value = self.target.readline(*args)
        if value:
            if self.notify is not None:
                self.notify('read_line', value, None)
            self.sink.write(value.encode('utf-8'))
            self.sink.flush()
            os.fsync(self.sink.fileno())
            self.observed.append(value)
        return value

    def __getattr__(self, name):
        return getattr(self.target, name)


def atomic_checkpoint(raw, out):
    """Stop signals may fire after a complete replacement, never mid-write."""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
    try:
        temporary, partial = out / 'raw.partial.pending.json', out / 'raw.partial.json'
        with temporary.open('x') as target:
            json.dump(raw, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, partial)
        directory = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


class ProcessFacade:
    def __init__(self, process, stdin, stdout):
        self.process, self.stdin, self.stdout = process, stdin, stdout

    def __getattr__(self, name):
        return getattr(self.process, name)


def node_events(out, counters, *, fatal=True):
    path = out / 'node-progress.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if rows:
        for key in ('Node_network_operations_attempted', 'native_binary_loads_attempted', 'native_binary_loads_completed'):
            counters[key] = rows[-1][key]
    if fatal and counters['Node_network_operations_attempted']:
        raise RuntimeError('Persistent native public-network-API violation')
    return rows


def validate_outputs(response, questions):
    if not isinstance(response, dict) or set(response.get('answers', {})) != set(questions):
        raise ValueError('Exact original response question identity closure failed')
    for key, answer in response['answers'].items():
        if not isinstance(answer, dict) or answer.get('type') != questions[key]['type']:
            raise ValueError('Original answer type changed')
        for version in (answer, answer.get('native_original_answer'), answer.get('baseline100_answer')):
            if not isinstance(version, dict):
                raise ValueError('Full original native/baseline100 answers must remain present')
            if 'calibrated' in version and type(version['calibrated']) is not bool:
                raise ValueError('Malformed actual calibration flag')
            for field in ('noul', 'confidence', 'score'):
                if field in version and (type(version[field]) not in (int, float)
                        or not math.isfinite(version[field]) or not 0 <= version[field] <= 1):
                    raise ValueError('Nonfinite or out-of-range actual native numeric field')
            if 'probabilities' in version:
                probabilities = version['probabilities']
                values = list(probabilities.values()) if isinstance(probabilities, dict) else probabilities
                if (not isinstance(values, list) or not values or any(type(x) not in (int, float)
                        or not math.isfinite(x) or not 0 <= x <= 1 for x in values)
                        or abs(math.fsum(values) - 1) > 1e-6):
                    raise ValueError('Malformed actual probability field')


def run(raw, plan, args, progress, offline):
    counters = raw['counters']
    bank_path = C.checked(plan['engineering_inputs_path'])
    if plan['engineering_inputs_sha256'] != BANK_SHA or C.sha(bank_path) != BANK_SHA:
        raise ValueError('Wrong fixed independently authored engineering bank')
    bank = C.read(bank_path)
    records = bank['records']
    if (bank['epoch'] != 28 or bank['license'] != 'CC0-1.0' or bank['DEV'] != [] or bank['CONF'] != []
            or [row['id'] for row in records] != IDS or plan['engineering_ids'] != IDS):
        raise ValueError('Only fixed eight authored requests allowed')
    engine_module = C.load_module('epoch28_original_composite', C.checked(C.ENGINE))
    server = engine_module.server
    if Path(server.__file__).resolve() != C.checked('experiments/swarm/jevbench-adapter/server.py'):
        raise ValueError('Original submitted server dependency resolved outside exact source closure')
    captures = {'stdin': [], 'stdout': []}
    sinks = {name: (args.out / ('native.' + name + '.jsonl')).open('xb') for name in captures}
    stderr = (args.out / 'native.stderr').open('xb')
    original_popen = subprocess.Popen
    cpu_guard = C.load_module('epoch28_child_cpu_guard', HERE / 'cpu_guard.py')
    process = identity = engine = None
    init_started = time.perf_counter()

    def written(phase, value, complete):
        row = raw['requests'][-1]
        if phase == 'attempt':
            counters['native_stdin_write_calls_attempted'] += 1
            row['native_stdin_write_intended'] = value
            row['native_backend_execution_observation'] = 'UNKNOWN_PENDING_OR_ABSENT_REPLY'
            row['native_stdin_write_outcome'] = 'UNKNOWN_UNTIL_WRITE_RETURNS'
            progress({'event': 'NATIVE_STDIN_WRITE_ATTEMPT', 'id': row['id'], 'intended_utf8_bytes': len(value.encode('utf-8'))})
        else:
            row['native_stdin_literal_written'] = value
            row['native_stdin_write_outcome'] = 'COMPLETE_FRAME_ACCEPTED' if complete else 'PARTIAL_WRITE_ACCEPTED'
            if complete:
                wire = json.loads(value)
                counters['native_systemOne_requests'] += 1
                counters['native_questions_written'] += len(wire['questions'])
            progress({'event': 'NATIVE_STDIN_WRITE_RETURNED', 'id': row['id'], 'complete_frame': complete})

    def received(phase, value, complete):
        if phase == 'read_attempt':
            counters['native_stdout_read_calls_attempted'] += 1
            progress({'event': 'NATIVE_STDOUT_READ_ATTEMPT'})
        else:
            counters['native_stdout_lines_read'] += 1
            if counters['native_stdout_lines_read'] == 1:
                raw['native_startup_stdout_literal'] = value
            else:
                counters['native_response_lines'] += 1
                raw['requests'][-1]['native_stdout_literal_received'] = value
                raw['requests'][-1]['native_backend_execution_observation'] = 'ORIGINAL_RESPONSE_LINE_OBSERVED_UNVALIDATED'
            progress({'event': 'NATIVE_STDOUT_LINE_OBSERVED'})

    def popen(command, *positional, **kwargs):
        nonlocal process, identity
        if (process is not None or command != ['node', str(C.ROOT / C.NATIVE_WORKER)]
                or kwargs.get('cwd') != C.ROOT or kwargs.get('stdin') != subprocess.PIPE
                or kwargs.get('stdout') != subprocess.PIPE or kwargs.get('text') is not True
                or kwargs.get('bufsize') != 1):
            raise ValueError('Only exact original single NativeEngine Popen invocation allowed')
        C.remaining(args.deadline)
        receipt_path = args.out / 'native-preexec.json'
        receipt_fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            preexec = cpu_guard.make_preexec(receipt_fd)
        except BaseException:
            os.close(receipt_fd)
            raise
        counters['native_process_starts_attempted'] += 1
        progress({'event': 'ORIGINAL_NATIVE_POPEN_BEFORE', 'argv': command})
        env = dict(os.environ)
        env.pop('E28_GUARD_SYNTHETIC', None)
        env.pop('TYPESAFE_BACKEND', None)
        env.update(E28_PROJECT=str(C.ROOT), E28_OUT=str(args.out), E28_PLAN=str(args.plan),
            E28_PLAN_SHA=args.expected_plan_sha, E28_ADMISSION=str(args.admission),
            NODE_OPTIONS='--require=' + str(HERE / 'node_guard.cjs'), TMPDIR=raw['scratch_directory'])
        kwargs.update(env=env, stderr=stderr, preexec_fn=preexec, pass_fds=(receipt_fd,))
        try:
            process = original_popen(command, *positional, **kwargs)
        finally:
            os.close(receipt_fd)
        counters['native_process_starts_completed'] += 1
        identity = C.proc(process.pid)
        if not identity or identity['pgid'] != os.getpgrp() or identity['sid'] != os.getsid(0):
            raise ValueError('Original native child escaped owned worker session')
        raw['cpu_guard_preexec'] = C.read(receipt_path)
        if (raw['cpu_guard_preexec'].get('status') != 'CPU_GUARD_INSTALLED_BEFORE_EXEC'
                or raw['cpu_guard_preexec'].get('CPU_affinity') != [0, 1]
                or raw['cpu_guard_preexec'].get('actual_proc_status', {}).get('NoNewPrivs') != '1'
                or raw['cpu_guard_preexec'].get('actual_proc_status', {}).get('Seccomp') != '2'):
            raise ValueError('Actual before-exec CPU guard receipt failed')
        C.put(args.out / 'native-attempt.json', {'pid': process.pid, 'identity': identity,
            'argv': command, 'original_cwd_preserved': str(C.ROOT), 'extra_model_options': {},
            'capture': 'transparent synchronous stdin.write/stdout.readline tees, no data listeners',
            'CPU_guard_receipt_sha256': C.sha(receipt_path),
            'source_sha256': C.sha(C.ROOT / C.NATIVE_WORKER)})
        if process.stdin.encoding.lower().replace('-', '') != 'utf8' or process.stdout.encoding.lower().replace('-', '') != 'utf8':
            raise ValueError('Exact UTF8 native pipe encoding required')
        return ProcessFacade(process, Tee(process.stdin, sinks['stdin'], captures['stdin'], 'stdin', written),
            Tee(process.stdout, sinks['stdout'], captures['stdout'], 'stdout', received))

    try:
        subprocess.Popen = popen
        counters['composite_initializations_attempted'] += 1
        engine = engine_module.CompositeEngine(C.checked(C.RULES))
        counters['composite_initializations_completed'] += 1
        receipt = engine.receipt
        if (receipt.get('backend') != 'native' or receipt.get('binary_version') != '2.4.0'
                or receipt.get('package') != '@ruvector/typesafe' or receipt.get('package_version') != '0.2.0'
                or receipt.get('binary_sha256') != C.BINARY_SHA
                or receipt.get('model_manifest_sha256') != C.sha(C.ROOT / 'models/manifest.json')):
            raise ValueError('Wrong actual original native initialization receipt')
        if len(captures['stdout']) != 1 or json.loads(captures['stdout'][0]).get('status') != 'ready':
            raise ValueError('Exactly one original raw startup ready line required')
        counters['native_ready_receipts'] += 1
        raw['initialization'] = {'seconds': time.perf_counter() - init_started, 'receipt': receipt,
            'actual_child': identity,
            'BGE_initialization_basis': 'One exact immutable nativeEngine/createTypesafe ONNX constructor completed before original ready line; internal forward count not exposed.',
            'opaque_internal_BGE_forwards': None, 'NLI_calls': None, 'ANN_queries': None}
        raw['initialization']['native_process_status'] = status(process.pid)
        raw['initialization']['actual_mapped_native_runtime'] = mapped_runtime(process.pid, raw['runtime_assets'])
        progress({'event': 'ORIGINAL_COMPOSITE_NATIVE_INITIALIZED', 'native_process': status(process.pid)})
        for record in records:
            C.remaining(args.deadline)
            literal = json.dumps(record['input'], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            if C.text_sha(literal) != record['input_utf8_json_sha256']:
                raise ValueError('Authored literal input identity changed')
            state, questions = server.validate_request(record['input'])
            if (not isinstance(state, str) or C.text_sha(state) != record['state_utf8_sha256']
                    or len(state.encode('utf-8')) != record['state_utf8_bytes'] or set(questions) != {'decision'}):
                raise ValueError('Complete original authored state/question mapping changed')
            row = {'id': record['id'], 'purpose': record['purpose'], 'literal_input_json': literal,
                'normalized_state': state, 'normalized_questions': questions,
                'state_utf8_bytes': len(state.encode('utf-8')), 'state_utf8_sha256': C.text_sha(state),
                'engineering_expectation': record['engineering_expectation'], 'response': None, 'error': None}
            raw['requests'].append(row)
            sent_before, replies_before = len(captures['stdin']), len(captures['stdout'])
            counters['composite_predict_attempted'] += 1
            progress({'event': 'ORIGINAL_COMPOSITE_PREDICT_BEFORE', 'id': record['id'], 'native_process': status(process.pid)})
            started = time.perf_counter()
            try:
                response = engine.predict(state, questions)
                counters['composite_predict_completed'] += 1
                # Retain the actual returned composite value before validation.
                # A non-JSON Python value has no literal JSON representation;
                # preserve its diagnostic repr and fail rather than dropping it.
                row['response'] = response
                try:
                    json.dumps(response, ensure_ascii=False, allow_nan=False)
                except (TypeError, ValueError, OverflowError) as serialization_error:
                    row['response'] = {'unserializable_original_response': True,
                        'python_type': type(response).__name__, 'diagnostic_repr': repr(response),
                        'serialization_error_type': type(serialization_error).__name__,
                        'serialization_error': str(serialization_error)}
                    raise ValueError('Original composite response is not strict JSON; diagnostic representation retained') from serialization_error
                validate_outputs(response, questions)
            except BaseException as error:
                row['error'] = {'type': type(error).__name__, 'message': str(error),
                    'original_error_kind': None, 'cause': 'UNKNOWN_UNLESS_SUPPORTED_BY_ORIGINAL_ERROR_MESSAGE',
                    'traceback': traceback.format_exc()}
            row['seconds'] = time.perf_counter() - started
            if len(captures['stdin']) != sent_before + 1 or len(captures['stdout']) != replies_before + 1:
                raise ValueError('Exactly one actual native stdin request and stdout response per authored request required')
            sent, replied = captures['stdin'][-1], captures['stdout'][-1]
            row.update(native_stdin_literal=sent, native_stdout_literal=replied,
                native_stdin_sha256=C.text_sha(sent), native_stdout_sha256=C.text_sha(replied))
            wire, native = json.loads(sent), json.loads(replied)
            if (set(wire) != {'state', 'questions'} or wire['state'] != state or wire['questions'] != questions
                    or list(wire['questions']['decision'].get('criteria', {})) != list(questions['decision'].get('criteria', {}))):
                raise ValueError('Actual native wire changed full input or question/criteria order')
            row['native_backend_execution_observation'] = 'ORIGINAL_RESPONSE_OBSERVED'
            counters['native_request_reply_pairs_closed'] += 1
            if native.get('ok') is True:
                counters['native_successful_responses'] += 1
                if row['error'] is not None or row['response'] is None:
                    raise ValueError('Original native success did not preserve full composite output')
            elif native.get('ok') is False:
                counters['native_refusal_responses'] += 1
                if not isinstance(native.get('error'), str) or not native['error'] or row['error'] is None:
                    raise ValueError('Original refusal must retain raw nonempty error line and original exception')
            else:
                raise ValueError('Malformed original native response status')
            if (record['engineering_expectation']['outcome'] == 'success') != (native.get('ok') is True):
                raise ValueError('Predetermined within-limit success/over-limit refusal expectation failed')
            offline.assert_clean()
            node_events(args.out, counters)
            progress({'event': 'ORIGINAL_COMPOSITE_PREDICT_AFTER', 'id': record['id'], 'native_process': status(process.pid)})
        raw['actual_mapped_native_runtime_after_requests'] = mapped_runtime(process.pid, raw['runtime_assets'])
        raw['status'] = 'COMPLETED_AUTHORED_QUALIFICATION_AWAITING_INDEPENDENT_REPLAY'
    finally:
        subprocess.Popen = original_popen
        if engine is not None:
            try:
                engine.close()
            except BaseException as error:
                raw['errors'].append({'stage': 'original_engine_close', 'type': type(error).__name__, 'message': str(error)})
        elif process is not None and process.poll() is None:
            current = C.proc(process.pid)
            if not identity or not current or current['ticks'] != identity['ticks']:
                raise RuntimeError('Cannot prove exact native child for failed-init cleanup')
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        raw['native_child_exit_code'] = process.returncode if process is not None else None
        raw['native_child_closed'] = process is None or process.poll() is not None
        cpu_receipt = args.out / 'native-preexec.json'
        if cpu_receipt.is_file():
            raw['cpu_guard_preexec_artifact'] = {'path': str(cpu_receipt.relative_to(C.ROOT)),
                'bytes': cpu_receipt.stat().st_size, 'sha256': C.sha(cpu_receipt)}
            if 'cpu_guard_preexec' not in raw:
                try:
                    raw['cpu_guard_preexec'] = C.read(cpu_receipt)
                except BaseException as error:
                    raw['errors'].append({'stage': 'CPU_guard_receipt_parse', 'type': type(error).__name__, 'message': str(error)})
        raw['Node_guard_events'] = node_events(args.out, counters, fatal=False)
        for sink in sinks.values():
            sink.close()
        stderr.close()
        raw['pipe_artifacts'] = {name: {'path': str(path.relative_to(C.ROOT)), 'bytes': path.stat().st_size,
            'sha256': C.sha(path)} for name, path in [('stdin', args.out / 'native.stdin.jsonl'),
                ('stdout', args.out / 'native.stdout.jsonl'), ('stderr', args.out / 'native.stderr')]}


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'admission', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    if args.out.absolute() != C.STUDY / 'runs/engineering' or args.out.resolve() != args.out.absolute():
        raise ValueError('Unsafe qualification output directory')
    started = time.monotonic()
    raw = {'schema_version': 1, 'epoch': 28, 'kind': C.KIND, 'source_checkpoint': C.SOURCE,
        'status': 'INITIALIZING', 'started_at': datetime.now(timezone.utc).isoformat(),
        'worker_pid': os.getpid(), 'worker_identity': C.proc(os.getpid()), 'plan_sha256': args.expected_plan_sha,
        'requests': [], 'errors': [], 'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []},
        'benchmark_generalization_claim': False, 'champion_promoted': False,
        'benchmark_accuracy': None, 'benchmark_NLL': None, 'benchmark_Brier': None,
        'proper_metric_computations': 0,
        'counters': {**dict.fromkeys(C.ZERO, 0), **dict.fromkeys(('native_process_starts_attempted',
            'native_process_starts_completed', 'composite_initializations_attempted', 'composite_initializations_completed',
            'native_ready_receipts', 'native_binary_loads_attempted', 'native_binary_loads_completed',
            'native_stdin_write_calls_attempted', 'native_request_reply_pairs_closed',
            'native_stdout_read_calls_attempted', 'native_stdout_lines_read',
            'composite_predict_attempted', 'composite_predict_completed', 'native_systemOne_requests',
            'native_questions_written', 'native_response_lines', 'native_successful_responses', 'native_refusal_responses'), 0)},
        'opaque_internal_forward_counts': None,
        'counter_semantics': {'native_stdin_write_calls_attempted': 'incremented before actual stdin.write; a write exception leaves acceptance and backend execution unknown',
            'native_systemOne_requests': 'complete original JSON request frames accepted by stdin.write; backend execution remains unknown without its original response',
            'native_questions_written': 'question count in complete accepted original stdin frames',
            'native_request_reply_pairs_closed': 'actual accepted request and original response both observed',
            'opaque_backend_execution_without_reply': 'UNKNOWN, never inferred from a missing response or reported as zero'},
        'numeric_semantics': 'Raw engine probabilities preserve their actual field names and calibration flags. Native untrained noul is an uncalibrated similarity score, never rebranded as a probability. No fitted head or calibration.',
        'resource_policy': 'CPU affinity0,1 and computational environment thread budget2; total OS helper/thread count is measured, not asserted2.',
        'network_policy_scope': 'Python/Node public API interposition; not OS syscall isolation or instrumentation inside compiled Rust.'}
    raw['CPU_enforcement_policy'] = 'Before Node exec, child pinned0,1 then no_new_privs+inherited Linuxx86_64 seccomp denies sched_setaffinity203 and x32variant withEPERM. Actual blocked syscall totals UNKNOWN; no model option edits.'
    progress_path = args.out / 'progress.jsonl'
    stream = progress_path.open('xb')
    def progress(event):
        row = {'at_unix': time.time(), 'elapsed_seconds': time.monotonic() - started,
            'event': event, 'counters': dict(raw['counters']), 'process': status(os.getpid())}
        stream.write((json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
        # A killed worker cannot run finally. Retain its most recent complete
        # raw/counter snapshot atomically, independently of the final raw seal.
        atomic_checkpoint(raw, args.out)
    guard = C.load_module('epoch28_offline_guard', HERE / 'network_guard.py').OfflineGuard(raw['counters'], progress).install()
    def bounded_stop(signum, frame):
        raise TimeoutError('Bounded worker stop signal received: ' + str(signum))
    signal.signal(signal.SIGTERM, bounded_stop)
    signal.signal(signal.SIGALRM, bounded_stop)
    code = 0
    try:
        if sorted(os.sched_getaffinity(0)) != [0, 1]:
            raise ValueError('Exact CPU0,1 computational affinity required')
        C.remaining(args.deadline)
        # Leave seven worker-budget seconds for the unchanged NativeEngine.close
        # (up to five seconds) and durable final raw output before outer cleanup.
        signal.setitimer(signal.ITIMER_REAL, max(.001, C.remaining(args.deadline) - 7))
        if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
            raise ValueError('Unknown source plan identity')
        provisional = C.read(args.plan)
        admission, owner = C.admission(args.admission, provisional, args.expected_plan_sha)
        plan = C.verify_plan(args.plan, args.expected_plan_sha)
        runtime = C.verify_runtime(plan)
        attempt_path = args.out / 'attempt.json'
        while not attempt_path.exists():
            C.remaining(args.deadline)
            if time.monotonic() - started > 5:
                raise ValueError('Outer exact worker session identity was not sealed')
            time.sleep(.01)
        attempt, current = C.read(attempt_path), C.proc(os.getpid())
        if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpid()
                or attempt.get('sid') != os.getpid() or attempt.get('startticks') != current['ticks']
                or current['pgid'] != os.getpid() or current['sid'] != os.getpid()):
            raise ValueError('Exact worker PID/ticks/session identity required')
        raw.update(admission=admission, owner_lock=owner, runtime_assets=runtime,
            source_freeze_sha256=plan['source_freeze_sha256'], source_admitted_before_initialization=True)
        scratch = C.ROOT.parent / 'runtime28-tmp'
        C.no_symlink(scratch)
        scratch.mkdir(exist_ok=False)
        raw['scratch_directory'] = str(scratch)
        progress({'event': 'ALL_SOURCE_RUNTIME_REMOTE_AND_OWNER_GATES_VERIFIED_BEFORE_NATIVE'})
        run(raw, plan, args, progress, guard)
        C.verify_plan(args.plan, args.expected_plan_sha)
        C.verify_runtime(plan)
        C.owner_lock(admission)
        C.remaining(args.deadline)
        guard.assert_clean()
        expected = {'native_process_starts_attempted': 1, 'native_process_starts_completed': 1,
            'composite_initializations_attempted': 1, 'composite_initializations_completed': 1,
            'native_ready_receipts': 1, 'native_binary_loads_attempted': 1, 'native_binary_loads_completed': 1,
            'native_stdin_write_calls_attempted': 8, 'native_request_reply_pairs_closed': 8,
            'native_stdout_read_calls_attempted': 9, 'native_stdout_lines_read': 9,
            'composite_predict_attempted': 8, 'composite_predict_completed': 7,
            'native_systemOne_requests': 8, 'native_questions_written': 8, 'native_response_lines': 8,
            'native_successful_responses': 7, 'native_refusal_responses': 1}
        if any(raw['counters'][k] != v for k, v in expected.items()) or any(raw['counters'][k] for k in C.ZERO):
            raise ValueError('Exact one-init/eight-request/seven-success/one-refusal closure failed')
        if raw['errors'] or not raw.get('native_child_closed'):
            raise ValueError('Native cleanup or worker errors remain')
    except BaseException as error:
        raw['status'] = 'FAILED_AUTHORED_QUALIFICATION'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()})
        if hasattr(error, 'observed_process_status'):
            raw['CPU_affinity_violation_snapshot'] = error.observed_process_status
        code = 2
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        raw.update(wall_seconds_including_initialization_cleanup=time.monotonic() - started,
            completed_at=datetime.now(timezone.utc).isoformat(), Python_network_violations=guard.violations,
            resources={'CPU_affinity': sorted(os.sched_getaffinity(0)), 'worker': status(os.getpid()),
                'worker_user_seconds': own.ru_utime, 'worker_system_seconds': own.ru_stime,
                'worker_peak_RSS_bytes': own.ru_maxrss * 1024, 'child_user_seconds': child.ru_utime,
                'child_system_seconds': child.ru_stime, 'largest_child_peak_RSS_bytes': child.ru_maxrss * 1024,
                'memory_scope': 'Separate high-water values, not aggregate simultaneous RSS.'})
        if raw.get('scratch_directory'):
            try:
                scratch = Path(raw['scratch_directory'])
                files = []
                for path in sorted(scratch.rglob('*')):
                    C.no_symlink(path)
                    if path.is_file():
                        files.append({'path': str(path.relative_to(scratch)), 'bytes': path.stat().st_size,
                            'sha256': C.sha(path)})
                raw['scratch_receipt'] = {'directory': str(scratch), 'files': files,
                    'files_retained_outside_public_project': True}
                C.put(args.out / 'scratch-receipt.json', raw['scratch_receipt'])
            except BaseException as error:
                raw['status'] = 'FAILED_AUTHORED_QUALIFICATION'
                raw['errors'].append({'stage': 'scratch_receipt', 'type': type(error).__name__, 'message': str(error)})
                code = 2
        try:
            progress({'event': 'WORKER_FINAL', 'status': raw['status'], 'errors': raw['errors']})
        except BaseException as error:
            raw['status'] = 'FAILED_AUTHORED_QUALIFICATION'
            raw['errors'].append({'stage': 'final_progress_checkpoint', 'type': type(error).__name__, 'message': str(error)})
            code = 2
        leftover = args.out / 'raw.partial.pending.json'
        if leftover.is_file():
            raw['leftover_partial_checkpoint'] = {'bytes': leftover.stat().st_size, 'sha256': C.sha(leftover),
                'path': str(leftover.relative_to(C.ROOT)), 'retained_without_overwrite': True}
        C.put(args.out / 'raw.json', raw)
        stream.close()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
