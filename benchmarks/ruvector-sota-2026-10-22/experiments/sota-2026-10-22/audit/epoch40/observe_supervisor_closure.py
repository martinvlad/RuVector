"""SOURCE-pinned metadata/proc closure; no model/native/data/gold capabilities."""
from pathlib import Path
import importlib.util
import time
_spec=importlib.util.spec_from_file_location('e40_closure_metadata',Path(__file__).with_name('closure_metadata.py'))
M=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(M)
for _name in dir(M):
 if not _name.startswith('_'):globals()[_name]=getattr(M,_name)
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


def read_terminal_wait_status(pid,expected):
    """Actual Linux stat field52; absence or malformed/redacted identity is UNKNOWN."""
    text=Path('/proc',str(pid),'stat').read_text();row=proc_row(text);values=text.rsplit(')',1)[1].split()
    require(identity_key(row)==identity_key(expected)and row['state']=='Z'and len(values)>=50,'Exact zombie wait status required')
    value=int(values[49]);require(0<=value<2**32,'Invalid kernel wait status')
    return {'wait_status':value,'field':52,'source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE',
        'raw_stat_sha256':hashlib.sha256(text.encode()).hexdigest()}

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
        exit_before=exit_after=None
        if before['state']=='Z':
            try:exit_before=read_terminal_wait_status(pid,expected)
            except(OSError,ValueError,IndexError):pass
        fd_errno, status = None, None
        if before['state'] in ('Z', 'X'):
            memory = [int(v) for v in Path('/proc', str(pid), 'statm').read_text().split()]
            status = Path('/proc', str(pid), 'status').read_text()
            values = status_fields(status)
            # A dead leader with other tasks remains ambiguous even if its FD
            # listing is readable. Prospective E40 requires one remaining task.
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
        if after['state']=='Z':
            try:exit_after=read_terminal_wait_status(pid,expected)
            except(OSError,ValueError,IndexError):pass
        evidence=exit_after if exit_before is not None and same(exit_before,exit_after)else None
        return {'absent': False, 'row': after, 'closed': closed,'exit_status_evidence':evidence}
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
        and execution['worker_cpu_guard_preexec_artifact'].get('path') == STUDY + 'runs/dev/worker-cpu-preexec.json'
        and identity is not None and recovered.get('ppid') == identity['pid']
        and recovered.get('pid') == recovered.get('pgid') == recovered.get('sid'))
    captured_closed = bool(execution is not None and execution.get('owned_live_processes_closed') is True
        and same(execution.get('owned_live_group_members'), [])
        and execution.get('owned_process_closure_observation') == 'OBSERVED')
    unknown = unknown or not captured_closed or not (known_before or known_worker or known_recovered)
    absent, state, closed = None, None, None
    exit_evidence=None
    expected_rows = list(identities)
    if identity is not None:
        expected_rows.append({'pid': identity['pid'], 'ticks': identity['startticks'],
                              'pgid': identity['pgid'], 'sid': identity['sid']})
        observation = proc_snapshot.get('processes', {}).get(identity['pid'], {})
        absent, closed = observation.get('absent'), observation.get('closed')
        exit_evidence=observation.get('exit_status_evidence')
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
            exit_evidence=None
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
    result = {'schema_version': 1, 'epoch': 40, 'kind': KIND, 'phase': 'dev',
              'source_plan_sha256': plan_sha, 'kernel_boot_id': BOOT, 'pid_namespace_inode': PIDNS,
              **refs, 'evidence':{'dispatch_attempt':refs.get('dispatch_attempt'),'execution':refs.get('execution'),'reservation':refs.get('dispatch_reservation'),'completion':refs.get('supervisor_completion')}, 'supervisor_identity': identity, 'physical_supervisor_absent': absent,
              'observed_supervisor_state': state, 'physical_supervisor_closed': closed,
              'owned_worker_group_members': members, 'unknown_physical_ownership': bool(unknown),
              'physical_closure_passed': passed,'observed_closed_by_monotonic_seconds':None,
              'observed_supervisor_exit_wait_status':exit_evidence.get('wait_status')if isinstance(exit_evidence,dict)and state=='Z'else None,
              'supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE'if isinstance(exit_evidence,dict)and state=='Z'else 'UNKNOWN_ABSENT_OR_UNREADABLE',
              'observed_supervisor_exit_status_evidence':exit_evidence if state=='Z'else None}
    require(set(result) == KEYS, 'Closure schema drift')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strict-snapshot', action='store_true',
                        help='Compatibility flag; two coherent snapshots are always mandatory, never retries')
    args = parser.parse_args()
    root = check_root(args.project)
    require(Path(__file__).absolute()==root/SELF,'Run canonical SOURCE-pinned observer')
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
    optional_metadata = [STUDY + 'runs/dev/worker-cpu-preexec.json']
    for role in ('dev',):
        optional_metadata += [STUDY + 'runs/dev/' + role + '-native-attempt.json',
            STUDY + 'runs/dev/' + role.upper() + '_CORPUS_ATTEMPT_RESERVATION.json']
    # Missing captured execution remains UNKNOWN even if durable child/role
    # files exist. Never interpret their existence/absence as zero worker start.
    for relative in optional_metadata if docs['execution'] is not None else []:
        if relative not in extra_present:
            try:
                file_ref(root, relative)
            except FileNotFoundError:
                continue
            raise ValueError('Previously unreferenced role/CPU metadata appeared')
    result['observed_closed_by_monotonic_seconds']=time.monotonic()
    print(json.dumps(write_outside(root, args.output, result), sort_keys=True))
    return 0 if result['physical_closure_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
