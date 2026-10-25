"""Independent E37 physical closure, using metadata and Linux proc only.

Run the SOURCE-pinned public copy once after the detached supervisor has stopped,
before gold/scoring. The output must be outside the project; root copies it once
to epoch37/SUPERVISOR_OBSERVED_CLOSURE.json. A Z/X process with zero memory and
no FDs is closed but is not absent. No detached supervisor exit status is
observed here: SUPERVISOR_ABOUT_TO_EXIT records an intention only.

The prospective terminal rule also accepts EACCES13 on the FD directory only
with exact stable Z/X identity, seven zero statm values and genuine kernel
FDSize0/Threads1. Unknown FD capacity or ambiguous task ownership never closes.
This module never imports runtime/model/native code, decodes tensors or raw
predictions, opens dataset/gold contents, starts a process, or sends a signal.
Plan pins (including opaque data/artifact pins) are streamed only for hashes.
Fixtures call evaluate() with in-memory proc records, never the live observer.
"""
import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

KIND = 'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
BASE = 'b4e9e4f7a8a40b95b87ed8e418435b2d5757bb0e'
BOOT = '4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS = 4026532200
GUARDIAN_SCOPE = '/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4'
STUDY = 'experiments/sota-2026-10-22/epoch37/'
SELF = 'experiments/sota-2026-10-22/audit/epoch37/observe_supervisor_closure.py'
LAUNCH = 'experiments/sota-2026-10-22/candidate/epoch37/runtime/launch.py'
PRE_POPEN_LAUNCH_SHA = '386f5b4ca72ade320f9020a34aa507c30777de10a9b22f4f178ccb5b5db90d70'
PATHS = {'dispatch_reservation': STUDY + 'DISPATCH_RESERVATION.json',
         'dispatch_attempt': STUDY + 'DISPATCH_ATTEMPT.json',
         'supervisor_completion': STUDY + 'SUPERVISOR_COMPLETION.json',
         'execution': STUDY + 'runs/engineering/execution.json'}
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
    require(plan.get('epoch') == 37 and plan.get('kind') == KIND
            and plan.get('source_checkpoint') == BASE and plan.get('actual_project') == str(root)
            and plan.get('guardian_scope') == GUARDIAN_SCOPE,
            'Wrong current E37 source plan')
    require(same(plan.get('data_roles'), {'train': [], 'dev': [],
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
    require(freeze.get('epoch') == 37 and freeze.get('kind') == KIND
            and freeze.get('source_checkpoint') == BASE, 'Wrong freeze identity')
    entries = freeze.get('entries')
    require(isinstance(entries, list) and len({r['path'] for r in entries}) == len(entries),
            'Duplicate/invalid freeze entries')
    require(all(same(by_path.get(r['path']), r) for r in entries)
            and any(r['path'] == SELF for r in entries), 'Observer/freeze not exactly plan-pinned')
    model_source = 'experiments/sota-2026-10-22/candidate/epoch37/PRETRAINED_MODEL_SOURCE.json'
    require(plan.get('pretrained_model_source_path') == model_source and model_source in by_path
            and same(plan.get('pretrained_model_source'), by_path[model_source])
            and plan.get('pretrained_model_source_sha256') == by_path[model_source]['sha256'], 'Wrong pretrained source pin')
    assets_path = plan.get('model_assets_lock_path')
    require(assets_path == 'experiments/sota-2026-10-22/candidate/epoch37/MODEL_ASSETS.json'
            and assets_path in by_path and plan.get('model_assets_lock_sha256') == by_path[assets_path]['sha256'],
            'Wrong public model-assets metadata pin')
    for key, relative in [('model_profiles','MODEL_PROFILES.json'), ('xxlarge_weight_metadata','research/XXL_ORIGINAL_WEIGHT_METADATA.json'),
            ('legacy_original_load_plan','research/LEGACY_ORIGINAL_LOAD_PLAN.v3.json')]:
        expected_path='experiments/sota-2026-10-22/candidate/epoch37/'+relative
        require(plan.get(key+'_path')==expected_path and expected_path in by_path
                and plan.get(key+'_sha256')==by_path[expected_path]['sha256'], 'Wrong paired source pin: '+key)
    require(isinstance(PRE_POPEN_LAUNCH_SHA, str) and re.fullmatch('[0-9a-f]{64}', PRE_POPEN_LAUNCH_SHA)
            and by_path.get(LAUNCH, {}).get('sha256') == PRE_POPEN_LAUNCH_SHA,
            'Final independently reviewed runtime launch source must be exactly pinned')
    admission_ref, admission = file_ref(root, STUDY + 'SOURCE_ADMISSION.json', True)
    require(admission.get('epoch') == 37 and admission.get('kind') == KIND
            and admission.get('phase') == 'engineering' and admission.get('scope') == 'benchmarks/ruvector-sota-2026-10-22/'
            and admission.get('verified_actual_remote_readback') is True
            and admission.get('plan_sha256') == plan_ref['sha256']
            and admission.get('source_freeze_sha256') == plan['source_freeze_sha256']
            and re.fullmatch('[0-9a-f]{40}', admission.get('published_source_commit', ''))
            and same(admission.get('pretrained_model_source'), by_path[model_source])
            and admission.get('model_assets_lock_sha256') == plan['model_assets_lock_sha256']
            and admission.get('model_profiles_sha256') == plan['model_profiles_sha256']
            and admission.get('xxlarge_weight_metadata_sha256') == plan['xxlarge_weight_metadata_sha256']
            and admission.get('legacy_original_load_plan_sha256') == plan['legacy_original_load_plan_sha256'], 'Actual paired source admission required')
    for key, expected in {'kernel_boot_id': BOOT, 'pid_namespace_inode': PIDNS,
            'owner_pid': 110592, 'owner_startticks': 24921126, 'owner_generation': 1,
            'owner_lock_inode': 13626, 'owner_lock_device': 33, 'owner_lock_fd': 3}.items():
        require(same(admission.get(key), expected), 'Admission namespace mismatch')
    expected = {'schema_version': 1, 'epoch': 37, 'kind': KIND, 'phase': 'engineering',
                'plan_sha256': plan_ref['sha256'], 'source_freeze_sha256': plan['source_freeze_sha256'],
                'pretrained_model_source_sha256': plan['pretrained_model_source_sha256'],
                'model_assets_lock_sha256': plan['model_assets_lock_sha256'],
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
    pre_popen_approved = isinstance(PRE_POPEN_LAUNCH_SHA, str) and by_path.get(LAUNCH, {}).get('sha256') == PRE_POPEN_LAUNCH_SHA
    if execution is not None:
        require(all(same(execution.get(k), expected[k]) for k in
                    ('schema_version', 'epoch', 'kind', 'phase', 'plan_sha256', 'kernel_boot_id', 'pid_namespace_inode'))
                and all(same(execution.get(k), refs[k]) for k in ('dispatch_reservation', 'dispatch_attempt'))
                and same(execution.get('logical_native_budget_reserved'), 1)
                and execution.get('status') in ('WORKER_COMPLETED', 'WORKER_ENGINEERING_REJECTED', 'WORKER_FAILED_OR_TIMEOUT')
                and execution.get('source_plan_unchanged') is True, 'Execution binding mismatch')
        known_supervisors.append(supervisor(execution.get('supervisor_identity')))
        for key in ('worker_identity', 'recovered_preexec_child_identity'):
            if execution.get(key) is not None:
                identities.append(process(execution[key]))
        cpu_ref = execution.get('worker_cpu_guard_preexec_artifact')
        if cpu_ref is not None:
            require(cpu_ref.get('path') == STUDY + 'runs/engineering/worker-cpu-preexec.json', 'Wrong CPU proof path')
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
        corpus_refs = execution.get('corpus_reservations')
        require(isinstance(corpus_refs, dict) and set(corpus_refs) == {'engineering'}
                and same(execution.get('corpus_reservation_count'), sum(r is not None for r in corpus_refs.values())),
                'Exact engineering-only corpus reservation metadata required; no inferred starts')
        for role in ('engineering',):
            reservation_path = STUDY + 'runs/engineering/' + role.upper() + '_CORPUS_ATTEMPT_RESERVATION.json'
            reservation_ref = corpus_refs[role]
            if reservation_ref is not None:
                require(reservation_ref.get('path') == reservation_path, 'Wrong role reservation path')
                reference(root, reservation_ref)
                actual_ref, reservation = file_ref(root, reservation_path, True)
                require(all(same(reservation.get(k), v) for k, v in {
                    'schema_version': 1, 'epoch': 37, 'kind': KIND, 'phase': 'engineering', 'role': role,
                    'plan_sha256': expected['plan_sha256'], 'corpus_batches_reserved': 1,
                    'allowed_further_role_helpers': 0, 'before_Popen': True, 'automatic_retry': False}.items())
                    and type(reservation.get('at_unix')) in (int, float) and math.isfinite(reservation['at_unix']),
                    'Role reservation binding differs')
                extra_refs.append(actual_ref)
            else:
                try:
                    file_ref(root, reservation_path)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError('Unreferenced role reservation exists')
            try:
                native_ref, native = file_ref(root, STUDY + 'runs/engineering/' + role + '-native-attempt.json', True)
            except FileNotFoundError:
                native_ref, native = None, None
            if native is not None:
                native_id = process(native.get('identity'))
                require(reservation_ref is not None and native.get('role') == role
                        and native.get('pid') == native_id['pid'], 'Native role/identity/reservation mismatch')
                helper_path = 'experiments/sota-2026-10-22/candidate/epoch37/native_helper.cjs'
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


def status_fields(text):
    fields = {}
    for line in text.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            require(key not in fields, 'Duplicate kernel status field')
            fields[key] = value.strip()
    return fields


def terminal_capacity(expected, before, after, memory, status, fd_errno,
                      boot_before, boot_after, namespace_before, namespace_after):
    """Pure prospective proof: no FD slots and one remaining terminal task."""
    try:
        values = status_fields(status)
        return bool(type(fd_errno) is int and fd_errno == errno.EACCES
            and boot_before == boot_after == BOOT and namespace_before == namespace_after == PIDNS
            and same(before, after) and identity_key(before) == identity_key(expected)
            and before['state'] in ('Z', 'X') and len(memory) == 7
            and all(type(v) is int and v == 0 for v in memory)
            and values.get('FDSize') == '0' and values.get('Threads') == '1'
            and values.get('Pid') == values.get('Tgid') == str(before['pid'])
            and values.get('State', '').split()[0] == before['state'])
    except (ValueError, KeyError, TypeError, IndexError):
        return False


def observed_process(pid, expected):
    try:
        boot_before = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        namespace_before = os.stat('/proc/self/ns/pid').st_ino
        require(boot_before == BOOT and namespace_before == PIDNS, 'Observation namespace differs')
        before = read_proc(pid)
        if before is None:
            return {'absent': True, 'row': None, 'closed': True}
        require(identity_key(before) == identity_key(expected), 'Observed PID identity differs')
        closed = False
        fd_errno, status = None, None
        if before['state'] in ('Z', 'X'):
            memory = [int(v) for v in Path('/proc', str(pid), 'statm').read_text().split()]
            status = Path('/proc', str(pid), 'status').read_text()
            values = status_fields(status)
            # A dead leader with other tasks remains ambiguous even if its FD
            # listing is readable. Prospective E37 requires one remaining task.
            require(values.get('Threads') == '1' and values.get('Pid') == values.get('Tgid') == str(pid)
                    and values.get('State', '').split()[0] == before['state'], 'Ambiguous terminal task ownership')
            try:
                fds = list(Path('/proc', str(pid), 'fd').iterdir())
                closed = terminal_closed(before['state'], memory, len(fds))
            except PermissionError as error:
                require(error.errno == errno.EACCES, 'Only terminal FD EACCES13 has capacity equivalence')
                fd_errno = error.errno
        after = read_proc(pid)
        if after is None:
            return {'absent': True, 'row': None, 'closed': True}
        boot_after = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        namespace_after = os.stat('/proc/self/ns/pid').st_ino
        require(same(before, after) and boot_before == boot_after == BOOT
                and namespace_before == namespace_after == PIDNS,
                'Process changed during observation')
        if fd_errno is not None:
            require(terminal_capacity(expected, before, after, memory, status, fd_errno,
                    boot_before, boot_after, namespace_before, namespace_after),
                    'Unknown terminal FD capacity or live MM/tasks')
            closed = True
        return {'absent': False, 'row': after, 'closed': closed}
    except (OSError, ValueError, IndexError):
        return {'absent': None, 'row': None, 'closed': None}


def terminal_closed(state, memory, fd_count):
    return state in ('Z', 'X') and len(memory) == 7 and all(type(v) is int and v == 0 for v in memory) and fd_count == 0


def snapshot(identity, identities):
    """A coherent point-in-time fence around one /proc group enumeration."""
    expected = {r['pid']: r for r in identities}
    if identity is not None:
        expected[identity['pid']] = {'pid': identity['pid'], 'ticks': identity['startticks'],
                                    'pgid': identity['pgid'], 'sid': identity['sid']}
    before = {pid: observed_process(pid, row) for pid, row in expected.items()}
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
    after = {pid: observed_process(pid, row) for pid, row in expected.items()}
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
        and execution['worker_cpu_guard_preexec_artifact'].get('path') == STUDY + 'runs/engineering/worker-cpu-preexec.json'
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
    result = {'schema_version': 1, 'epoch': 37, 'kind': KIND, 'phase': 'engineering',
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
                        help='Compatibility flag; two coherent snapshots are always mandatory, never retries')
    args = parser.parse_args()
    root = check_root(args.project)
    plan_ref, plan, pins, admission_ref, expected = verify_source(root)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
            and os.stat('/proc/self/ns/pid').st_ino == PIDNS, 'Current boot/PID namespace mismatch')
    refs, docs, identity, identities, extras, pre_popen = load_evidence(root, expected, pins)
    result = evaluate(plan_ref['sha256'], refs, docs, identity, identities,
                      snapshot(identity, identities), pre_popen)
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
    extra_present = {row['path'] for row in extras}
    optional_metadata = [STUDY + 'runs/engineering/worker-cpu-preexec.json']
    for role in ('engineering',):
        optional_metadata += [STUDY + 'runs/engineering/' + role + '-native-attempt.json',
            STUDY + 'runs/engineering/' + role.upper() + '_CORPUS_ATTEMPT_RESERVATION.json']
    # Missing captured execution remains UNKNOWN even if durable child/role
    # files exist. Never interpret their existence/absence as zero worker start.
    for relative in optional_metadata if docs['execution'] is not None else []:
        if relative not in extra_present:
            try:
                file_ref(root, relative)
            except FileNotFoundError:
                continue
            raise ValueError('Previously unreferenced role/CPU metadata appeared')
    print(json.dumps(write_outside(root, args.output, result), sort_keys=True))
    return 0 if result['physical_closure_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
