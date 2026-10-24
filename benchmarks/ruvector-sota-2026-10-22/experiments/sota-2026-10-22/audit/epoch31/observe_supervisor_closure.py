"""Independent E31 physical closure, using metadata and Linux proc only.

Run the SOURCE-pinned public copy once after the detached supervisor has stopped,
before gold/scoring. The output must be outside the project; root copies it once
to epoch31/SUPERVISOR_OBSERVED_CLOSURE.json. A Z/X process with zero memory and
no FDs is closed but is not absent. No detached supervisor exit status is
observed here: SUPERVISOR_ABOUT_TO_EXIT records an intention only.

This module never imports runtime/model/native code, decodes tensors or raw
predictions, opens dataset/gold contents, starts a process, or sends a signal.
Plan pins (including opaque data/artifact pins) are streamed only for hashes.
Fixtures call evaluate() with in-memory proc records, never the live observer.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

KIND = 'REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
BASE = 'b27d0c39ed3102cd16ba616b1225b7684b76851b'
BOOT = '4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS = 4026532200
STUDY = 'experiments/sota-2026-10-22/epoch31/'
SELF = 'experiments/sota-2026-10-22/audit/epoch31/observe_supervisor_closure.py'
LAUNCH = 'experiments/sota-2026-10-22/candidate/epoch31/runtime/launch.py'
PRE_POPEN_LAUNCH_SHA = '88afc677eb9e5a946c24de71a6066ece0df03eb66a35e0ee4aa8e6d0716c9160'
PATHS = {'dispatch_reservation': STUDY + 'DISPATCH_RESERVATION.json',
         'dispatch_attempt': STUDY + 'DISPATCH_ATTEMPT.json',
         'supervisor_completion': STUDY + 'SUPERVISOR_COMPLETION.json',
         'execution': STUDY + 'runs/dev/execution.json'}
KEYS = {'schema_version', 'epoch', 'kind', 'phase', 'source_plan_sha256',
        'kernel_boot_id', 'pid_namespace_inode', *PATHS, 'supervisor_identity',
        'physical_supervisor_absent', 'observed_supervisor_state',
        'physical_supervisor_closed', 'owned_worker_group_members',
        'unknown_physical_ownership', 'physical_closure_passed'}
SUP_KEYS = {'pid', 'startticks', 'pgid', 'sid'}
PROC_KEYS = {'pid', 'state', 'ppid', 'pgid', 'sid', 'ticks'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return len(a) == len(b) and all(k in b and same(v, b[k]) for k, v in a.items())
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def unique(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def parse(payload):
    def bad(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    value = json.loads(payload.decode('utf-8'), object_pairs_hook=unique,
                       parse_constant=bad)
    def finite(item):
        if isinstance(item, float):
            require(math.isfinite(item), 'Nonfinite JSON number')
        elif isinstance(item, dict):
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)
    finite(value)
    require(isinstance(value, dict), 'Metadata must be a JSON object')
    return value


def canonical_relative(relative):
    require(isinstance(relative, str) and relative and '\\' not in relative,
            'Noncanonical relative path')
    path = PurePosixPath(relative)
    require(not path.is_absolute() and str(path) == relative
            and all(part not in ('', '.', '..') for part in path.parts),
            'Unsafe relative path')
    return path.parts


def directory_fd(path):
    path = Path(path)
    require(path.is_absolute(), 'Absolute directory required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_regular(root, relative):
    """Walk every component with O_NOFOLLOW, retaining dirfd authority."""
    parts = canonical_relative(relative)
    fd = directory_fd(root)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(child).st_mode):
            os.close(child)
            raise ValueError('Expected regular file')
        return child
    finally:
        os.close(fd)


def file_ref(root, relative, metadata=False):
    fd = open_regular(root, relative)
    try:
        before = os.fstat(fd)
        if metadata:
            require(before.st_size <= 8 * 1024 * 1024, 'Metadata exceeds 8MiB')
        digest, count, chunks = hashlib.sha256(), 0, []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            count += len(chunk)
            if metadata:
                require(count <= 8 * 1024 * 1024, 'Metadata grew beyond 8MiB')
                chunks.append(chunk)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and count == after.st_size, 'File changed during hash')
        row = {'path': relative, 'bytes': count, 'sha256': digest.hexdigest()}
        return (row, parse(b''.join(chunks))) if metadata else row
    finally:
        os.close(fd)


def reference(root, row):
    require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'}
            and type(row['bytes']) is int and row['bytes'] >= 0
            and isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']),
            'Invalid exact ref3')
    require(same(file_ref(root, row['path']), row), 'Actual file differs from ref3')
    return row


def check_root(root):
    root = Path(os.path.abspath(root))
    require(root == root.resolve(strict=True) and root.is_dir(), 'Project path has symlink')
    return root


def verify_source(root):
    plan_ref, plan = file_ref(root, STUDY + 'plan.json', True)
    require(plan.get('epoch') == 31 and plan.get('kind') == KIND
            and plan.get('source_checkpoint') == BASE and plan.get('actual_project') == str(root),
            'Wrong current E31 source plan')
    require(same(plan.get('data_roles'), {'train': [], 'dev': [145, 597, 191, 620, 254, 160, 384, 571],
                                        'calibration': [], 'confirmation': []}), 'Wrong fixed roles')
    pins = plan.get('pins')
    require(isinstance(pins, list), 'Plan pins required')
    by_path = {}
    for row in pins:
        reference(root, row)
        require(row['path'] not in by_path, 'Duplicate plan pin')
        by_path[row['path']] = row
    require(Path(__file__).absolute() == root / SELF, 'Run only canonical SOURCE-pinned observer')
    require(SELF in by_path and same(file_ref(root, SELF), by_path[SELF]), 'Observer not source-pinned')
    freeze_path = STUDY + 'source-freeze.json'
    require(plan.get('source_freeze_path') == freeze_path and freeze_path in by_path
            and plan.get('source_freeze_sha256') == by_path[freeze_path]['sha256'], 'Wrong freeze pin')
    _, freeze = file_ref(root, freeze_path, True)
    require(freeze.get('epoch') == 31 and freeze.get('kind') == KIND
            and freeze.get('source_checkpoint') == BASE, 'Wrong freeze identity')
    entries = freeze.get('entries')
    require(isinstance(entries, list) and len({r['path'] for r in entries}) == len(entries),
            'Duplicate/invalid freeze entries')
    require(all(same(by_path.get(r['path']), r) for r in entries)
            and any(r['path'] == SELF for r in entries), 'Observer/freeze not exactly plan-pinned')
    archive = STUDY + 'ARCHIVED_MODEL_SEAL.json'
    require(plan.get('archived_model_seal_path') == archive and archive in by_path
            and same(plan.get('archived_model_seal'), by_path[archive])
            and plan.get('archived_model_seal_sha256') == by_path[archive]['sha256'], 'Wrong archive seal pin')
    admission_ref, admission = file_ref(root, STUDY + 'SOURCE_ADMISSION.json', True)
    require(admission.get('epoch') == 31 and admission.get('kind') == KIND
            and admission.get('phase') == 'dev' and admission.get('scope') == 'benchmarks/ruvector-sota-2026-10-22/'
            and admission.get('verified_actual_remote_readback') is True
            and admission.get('plan_sha256') == plan_ref['sha256']
            and admission.get('source_freeze_sha256') == plan['source_freeze_sha256']
            and re.fullmatch('[0-9a-f]{40}', admission.get('published_source_commit', ''))
            and same(admission.get('archived_model_seal'), by_path[archive]), 'Actual source admission required')
    for key, expected in {'kernel_boot_id': BOOT, 'pid_namespace_inode': PIDNS}.items():
        require(same(admission.get(key), expected), 'Admission namespace mismatch')
    expected = {'schema_version': 1, 'epoch': 31, 'kind': KIND, 'phase': 'dev',
                'plan_sha256': plan_ref['sha256'], 'source_freeze_sha256': plan['source_freeze_sha256'],
                'archived_model_seal_sha256': plan['archived_model_seal_sha256'],
                'admission_sha256': admission_ref['sha256'], 'kernel_boot_id': BOOT,
                'pid_namespace_inode': PIDNS, 'logical_native_budget_reserved': 1,
                'allowed_further_dispatches': 0}
    return plan_ref, plan, by_path, admission_ref, expected


def supervisor(value):
    require(isinstance(value, dict) and set(value) == SUP_KEYS
            and all(type(v) is int and v > 0 for v in value.values())
            and value['pid'] == value['pgid'] == value['sid'], 'Invalid supervisor identity')
    return value


def process(value):
    require(isinstance(value, dict) and set(value) == PROC_KEYS
            and all(type(value[k]) is int and value[k] > 0 for k in ('pid', 'pgid', 'sid', 'ticks'))
            and type(value['ppid']) is int and value['ppid'] >= 0
            and isinstance(value['state'], str) and len(value['state']) == 1,
            'Invalid process identity')
    return value


def identity_key(row):
    return row['pid'], row['ticks'], row['pgid'], row['sid']


def known_before_popen(execution, approved, identities):
    error = execution.get('launcher_error') if execution else None
    return bool(execution is not None and approved and not identities
        and execution.get('status') == 'WORKER_FAILED_OR_TIMEOUT'
        and execution.get('worker_popen_attempted') is False
        and type(execution.get('worker_popen_attempts')) is int and execution['worker_popen_attempts'] == 0
        and execution.get('worker_start_boundary') == 'KNOWN_FAILURE_BEFORE_WORKER_POPEN'
        and isinstance(error, dict) and isinstance(error.get('type'), str) and error['type']
        and isinstance(error.get('message'), str) and error['message']
        and execution.get('uncertain_start') is False
        and type(execution.get('verified_worker_starts')) is int and execution['verified_worker_starts'] == 0
        and execution.get('worker_identity') is None and execution.get('recovered_preexec_child_identity') is None)


def load_evidence(root, expected, by_path):
    refs, docs = {}, {}
    for key, relative in PATHS.items():
        try:
            refs[key], docs[key] = file_ref(root, relative, True)
        except FileNotFoundError:
            refs[key], docs[key] = None, None
    require(refs['dispatch_reservation'] is not None, 'No durable dispatch claim: no closure report')
    claim, attempt = docs['dispatch_reservation'], docs['dispatch_attempt']
    execution, completion = docs['execution'], docs['supervisor_completion']
    require(all(same(claim.get(k), v) for k, v in expected.items()), 'Dispatch source/budget mismatch')
    for key in ('dispatch_monotonic_seconds', 'dispatch_unix_seconds'):
        require(type(claim.get(key)) in (int, float) and math.isfinite(claim[key]) and claim[key] > 0,
                'Invalid dispatch clocks')
    known_supervisors = []
    if attempt is not None:
        require(all(same(attempt.get(k), v) for k, v in expected.items())
                and all(same(attempt.get(k), claim[k]) for k in ('dispatch_monotonic_seconds', 'dispatch_unix_seconds'))
                and attempt.get('verified_launcher_start') is True
                and attempt.get('uncertain_launcher_start') is False, 'Dispatch attempt mismatch')
        known_supervisors.append(supervisor({k: attempt.get(k) for k in SUP_KEYS}))
    extra_refs, identities = [], []
    pre_popen_approved = by_path.get(LAUNCH, {}).get('sha256') == PRE_POPEN_LAUNCH_SHA
    if execution is not None:
        require(all(same(execution.get(k), expected[k]) for k in
                    ('schema_version', 'epoch', 'kind', 'phase', 'plan_sha256', 'kernel_boot_id', 'pid_namespace_inode'))
                and all(same(execution.get(k), refs[k]) for k in ('dispatch_reservation', 'dispatch_attempt'))
                and same(execution.get('logical_native_budget_reserved'), 1)
                and execution.get('status') in ('WORKER_COMPLETED', 'WORKER_FAILED_OR_TIMEOUT')
                and execution.get('source_plan_unchanged') is True, 'Execution binding mismatch')
        known_supervisors.append(supervisor(execution.get('supervisor_identity')))
        for key in ('worker_identity', 'recovered_preexec_child_identity'):
            if execution.get(key) is not None:
                identities.append(process(execution[key]))
        cpu_ref = execution.get('worker_cpu_guard_preexec_artifact')
        if cpu_ref is not None:
            require(cpu_ref.get('path') == STUDY + 'runs/dev/worker-cpu-preexec.json', 'Wrong CPU proof path')
            reference(root, cpu_ref)
            # O_EXCL reserves an empty receipt before pre-Popen setup. Only the
            # exact frozen captured failure may retain that empty file + null
            # embedded receipt. Never parse it or infer a worker identity.
            if cpu_ref['bytes'] == 0:
                require(execution.get('worker_cpu_guard_preexec') is None
                        and known_before_popen(execution, pre_popen_approved, identities),
                        'Empty CPU receipt lacks exact approved pre-Popen failure provenance')
                extra_refs.append(cpu_ref)
            else:
                actual_ref, cpu = file_ref(root, cpu_ref['path'], True)
                require(same(cpu, execution.get('worker_cpu_guard_preexec')), 'CPU proof differs from embedded metadata')
                extra_refs.append(actual_ref)
                if cpu.get('process_identity') is not None:
                    identities.append(process(cpu['process_identity']))
        try:
            native_ref, native = file_ref(root, STUDY + 'runs/dev/native-attempt.json', True)
        except FileNotFoundError:
            native_ref, native = None, None
        if native is not None:
            native_id = process(native.get('identity'))
            require(native.get('pid') == native_id['pid'], 'Native identity PID mismatch')
            helper_path = 'experiments/sota-2026-10-22/candidate/epoch31/native_helper.cjs'
            require(helper_path in by_path and native.get('source_sha256') == by_path[helper_path]['sha256'],
                    'Native attempt source mismatch')
            extra_refs.append(native_ref)
            identities.append(native_id)
    if completion is not None:
        require(execution is not None and all(same(completion.get(k), expected[k]) for k in
                ('schema_version', 'epoch', 'kind', 'phase', 'kernel_boot_id', 'pid_namespace_inode'))
                and completion.get('status') == 'SUPERVISOR_ABOUT_TO_EXIT'
                and completion.get('execution_sha256') == refs['execution']['sha256']
                and completion.get('execution_status') == execution.get('status')
                and same(completion.get('intended_exit_code'), 0 if execution.get('status') == 'WORKER_COMPLETED' else 2)
                and completion.get('exit_code_observed_by_root') is False
                and completion.get('requires_external_physical_supervisor_closure') is True,
                'Completion intention/execution chain mismatch')
        known_supervisors.append(supervisor(completion.get('supervisor_identity')))
    identity = known_supervisors[0] if known_supervisors else None
    require(all(same(item, identity) for item in known_supervisors), 'Conflicting supervisor identities')
    if identity is not None:
        worker_leaders = [r for r in identities if r['pid'] == r['pgid'] == r['sid']]
        if identities:
            require(worker_leaders and len({identity_key(r) for r in worker_leaders}) == 1,
                    'Unknown/conflicting owned worker session')
            leader = worker_leaders[0]
            require(leader['ppid'] == identity['pid'] and leader['pid'] != identity['pid'], 'Wrong worker parent')
            require(all(r['pgid'] == leader['pgid'] and r['sid'] == leader['sid'] for r in identities),
                    'Native/preexec process escaped known worker session')
            require(all(r['pid'] == leader['pid'] or r['ppid'] == leader['pid'] for r in identities),
                    'Native identity is not a direct owned-worker child')
    return refs, docs, identity, identities, extra_refs, pre_popen_approved


def proc_row(text):
    head, tail = text.rsplit(')', 1)
    values = tail.split()
    return process({'pid': int(head.split('(', 1)[0]), 'state': values[0], 'ppid': int(values[1]),
                    'pgid': int(values[2]), 'sid': int(values[3]), 'ticks': int(values[19])})


def read_proc(pid):
    try:
        return proc_row(Path('/proc', str(pid), 'stat').read_text())
    except FileNotFoundError:
        return None


def observed_process(pid):
    try:
        before = read_proc(pid)
        if before is None:
            return {'absent': True, 'row': None, 'closed': True}
        closed = False
        if before['state'] in ('Z', 'X'):
            memory = [int(v) for v in Path('/proc', str(pid), 'statm').read_text().split()]
            fds = list(Path('/proc', str(pid), 'fd').iterdir())
            closed = terminal_closed(before['state'], memory, len(fds))
        after = read_proc(pid)
        if after is None:
            return {'absent': True, 'row': None, 'closed': True}
        require(identity_key(before) == identity_key(after) and before['state'] == after['state'],
                'Process changed during observation')
        return {'absent': False, 'row': after, 'closed': closed}
    except (OSError, ValueError, IndexError):
        return {'absent': None, 'row': None, 'closed': None}


def terminal_closed(state, memory, fd_count):
    return state in ('Z', 'X') and bool(memory) and all(type(v) is int and v == 0 for v in memory) and fd_count == 0


def snapshot(identity, identities):
    """A coherent point-in-time fence around one /proc group enumeration."""
    pids = {r['pid'] for r in identities}
    if identity is not None:
        pids.add(identity['pid'])
    before = {pid: observed_process(pid) for pid in pids}
    rows, error = [], False
    try:
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    row = read_proc(int(entry.name))
                    if row is not None:
                        rows.append(row)
                except (OSError, ValueError, IndexError):
                    error = True
    except OSError:
        error = True
    after = {pid: observed_process(pid) for pid in pids}
    return {'processes': after, 'rows': rows, 'scan_error': error or not same(before, after)}


def evaluate(plan_sha, refs, docs, identity, identities, proc_snapshot, pre_popen_approved=False):
    """Pure reducer; an empty group never establishes an unrecorded worker start."""
    execution, attempt = docs.get('execution'), docs.get('dispatch_attempt')
    unknown = identity is None or attempt is None or proc_snapshot.get('scan_error') is not False
    known_before = known_before_popen(execution, pre_popen_approved, identities)
    known_worker = bool(execution is not None and identities
        and execution.get('uncertain_start') is False
        and execution.get('worker_popen_attempted') is True
        and type(execution.get('worker_popen_attempts')) is int and execution['worker_popen_attempts'] == 1
        and execution.get('worker_start_boundary') == 'WORKER_POPEN_ATTEMPTED'
        and type(execution.get('verified_worker_starts')) is int and execution['verified_worker_starts'] == 1
        and execution.get('worker_identity') is not None)
    recovered = execution.get('recovered_preexec_child_identity') if execution else None
    cpu = execution.get('worker_cpu_guard_preexec') if execution else None
    known_recovered = bool(execution is not None and pre_popen_approved and identities
        and execution.get('uncertain_start') is True
        and type(execution.get('verified_worker_starts')) is int and execution['verified_worker_starts'] == 0
        and execution.get('exit_code') is None
        and execution.get('worker_popen_attempted') is True
        and type(execution.get('worker_popen_attempts')) is int and execution['worker_popen_attempts'] == 1
        and execution.get('worker_start_boundary') == 'WORKER_POPEN_ATTEMPTED'
        and execution.get('worker_identity_source') == 'durable_preexec_only'
        and isinstance(recovered, dict) and same(execution.get('worker_identity'), recovered)
        and isinstance(cpu, dict) and same(cpu.get('process_identity'), recovered)
        and cpu.get('status') in ('CPU_GUARD_INSTALLED_BEFORE_EXEC', 'CPU_GUARD_FAILED_BEFORE_EXEC')
        and isinstance(execution.get('worker_cpu_guard_preexec_artifact'), dict)
        and execution['worker_cpu_guard_preexec_artifact'].get('path') == STUDY + 'runs/dev/worker-cpu-preexec.json'
        and identity is not None and recovered.get('ppid') == identity['pid']
        and recovered.get('pid') == recovered.get('pgid') == recovered.get('sid'))
    captured_closed = bool(execution is not None and execution.get('owned_live_processes_closed') is True
        and same(execution.get('owned_live_group_members'), [])
        and execution.get('owned_process_closure_observation') == 'OBSERVED')
    unknown = unknown or not captured_closed or not (known_before or known_worker or known_recovered)
    absent, state, closed = None, None, None
    expected_rows = list(identities)
    if identity is not None:
        expected_rows.append({'pid': identity['pid'], 'ticks': identity['startticks'],
                              'pgid': identity['pgid'], 'sid': identity['sid']})
        observation = proc_snapshot.get('processes', {}).get(identity['pid'], {})
        absent, closed = observation.get('absent'), observation.get('closed')
        state = observation.get('row', {}).get('state') if observation.get('row') else None
    for row in expected_rows:
        observed = proc_snapshot.get('processes', {}).get(row['pid'], {})
        current = observed.get('row')
        if observed.get('absent') is None or (current is not None and identity_key(current) != identity_key(row)):
            unknown = True
        if current is not None and current['state'] in ('Z', 'X') and observed.get('closed') is not True:
            unknown = True
    if identity is not None:
        current = proc_snapshot.get('processes', {}).get(identity['pid'], {}).get('row')
        if current is not None and identity_key(current) != (identity['pid'], identity['startticks'], identity['pgid'], identity['sid']):
            absent, state, closed = None, None, None
    groups = {r['pgid'] for r in expected_rows}
    sessions = {r['sid'] for r in expected_rows}
    members = [r for r in proc_snapshot.get('rows', [])
               if r['state'] not in ('Z', 'X') and (r['pgid'] in groups or r['sid'] in sessions)]
    members.sort(key=lambda r: (r['pid'], r['ticks']))
    if unknown:
        members = None
    terminal = (absent is True and state is None) or (absent is False and state in ('Z', 'X'))
    passed = bool(not unknown and captured_closed and identity is not None and closed is True
                  and terminal and members == [])
    result = {'schema_version': 1, 'epoch': 31, 'kind': KIND, 'phase': 'dev',
              'source_plan_sha256': plan_sha, 'kernel_boot_id': BOOT, 'pid_namespace_inode': PIDNS,
              **refs, 'supervisor_identity': identity, 'physical_supervisor_absent': absent,
              'observed_supervisor_state': state, 'physical_supervisor_closed': closed,
              'owned_worker_group_members': members, 'unknown_physical_ownership': bool(unknown),
              'physical_closure_passed': passed}
    require(set(result) == KEYS, 'Closure schema drift')
    return result


def write_outside(root, output, value):
    output = Path(os.path.abspath(output))
    parent = output.parent
    require(parent == parent.resolve(strict=True), 'Output parent symlink')
    require(not output.is_relative_to(root), 'Output must be outside project')
    require(output.name == 'SUPERVISOR_OBSERVED_CLOSURE.json', 'Use canonical closure basename')
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    directory = directory_fd(parent)
    try:
        fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                require(count > 0, 'Output write stalled')
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'path': str(output), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strict-snapshot', action='store_true',
                        help='Require two identical closure results from coherent proc scans; never retries')
    args = parser.parse_args()
    root = check_root(args.project)
    plan_ref, plan, pins, admission_ref, expected = verify_source(root)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
            and os.stat('/proc/self/ns/pid').st_ino == PIDNS, 'Current boot/PID namespace mismatch')
    refs, docs, identity, identities, extras, pre_popen = load_evidence(root, expected, pins)
    result = evaluate(plan_ref['sha256'], refs, docs, identity, identities,
                      snapshot(identity, identities), pre_popen)
    if args.strict_snapshot:
        second = evaluate(plan_ref['sha256'], refs, docs, identity, identities,
                          snapshot(identity, identities), pre_popen)
        require(same(result, second), 'Closure snapshots disagree; no output/no retry')
    # Fence all inputs again, including opaque pins, without decoding raw/data.
    for row in [plan_ref, admission_ref, *pins.values(), *extras, *[r for r in refs.values() if r]]:
        reference(root, row)
    # A previously absent optional metadata file appearing is also a changed snapshot.
    for key, relative in PATHS.items():
        if refs[key] is None:
            try:
                file_ref(root, relative)
            except FileNotFoundError:
                continue
            raise ValueError('Optional execution metadata appeared during observation')
    print(json.dumps(write_outside(root, args.output, result), sort_keys=True))
    return 0 if result['physical_closure_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
