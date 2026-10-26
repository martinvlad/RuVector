"""Root-only outer monitor for the independently approved fixed DEV intent."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

W = Path('/dev/shm/ruvector-sota-2026-10-22/epoch48-37b29244dcf5')
KIND = 'REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT'


def ref(path):
    path = Path(path)
    b = path.read_bytes()
    return dict(path=str(path), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def put(path, value):
    path = Path(path)
    b = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    f = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(f, 'wb') as stream:
        stream.write(b)
        stream.flush()
        os.fsync(stream.fileno())
    return ref(path)


def snap(pid):
    try:
        p = Path('/proc') / str(pid)
        f = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        status = (p / 'status').read_text()
        return dict(pid=pid, startticks=int(f[19]), ppid=int(f[1]), pgid=int(f[2]),
                    sid=int(f[3]), state=f[0], wait_status=int(f[49]),
                    FDSize=next(int(x.split(':')[1]) for x in status.splitlines() if x.startswith('FDSize:')),
                    statm=[int(x) for x in (p / 'statm').read_text().split()])
    except (FileNotFoundError, ProcessLookupError):
        return None


def main():
    ip = W / 'DEV_LAUNCH_INTENT.v2.json'
    ir = ref(ip)
    assert ir['bytes'] == 3515 and ir['sha256'] == '0a56e084a7a70e2153ee00f82e6b652abbdc23dfde55bd78b70c08a7d70cf8ea'
    intent = json.loads(ip.read_bytes())
    ap = Path('/dev/shm/ruvector-e48-audit/POST_DATA_AND_DEV_DISPATCH_APPROVAL.v1.json')
    ar = ref(ap)
    assert ar['bytes'] == 6133 and ar['sha256'] == 'a6769974cdb1aae98c8deec30e6b0ff985dc5c7da7a93f1d66bd91d5feb740a3'
    approval = json.loads(ap.read_bytes())
    assert approval['checks_passed'] is True and approval['dispatch_allowed'] is True
    assert approval['launch_intent_sha256'] == ir['sha256']
    adref = intent['SCI_admission_ref']
    assert ref(adref['path']) == adref and adref['sha256'] == approval['SCI_admission_sha256']
    ad = json.loads(Path(adref['path']).read_bytes())
    plan = json.loads(Path(intent['plan_ref']['path']).read_bytes())
    assert intent['nonsecret_environment_overrides'] == plan['launch_environment']
    assert approval['worker_slot_token'] == ad['worker_slot_token'] == plan['phase_slots']['dev']['token']
    assert not (W / 'runs/dev').exists() and not (W / 'private-run/dev').exists()
    owner = json.loads((W / 'owner.json').read_bytes())
    assert time.time() + 600 < owner['expires_unix'] and not (W / 'release.request').exists()
    current = snap(owner['pid'])
    assert current and current['state'] not in ('Z', 'X') and current['startticks'] == owner['startticks']
    st = os.stat('/proc/' + str(owner['pid']) + '/fd/3')
    assert (st.st_dev, st.st_ino) == (33, 13626)
    attempt = put(W / 'DEV_OUTER_LAUNCH_ATTEMPT.v1.json', dict(
        schema_version=1, epoch=48, kind=KIND, phase='dev', intent=ir,
        independent_post_DATA_review=ar, SCI_admission_ref=adref, Popen_attempts=1,
        native_batch_ordinal=1, automatic_retry=False,
        nonsecret_environment_overrides=intent['nonsecret_environment_overrides'],
        prelaunch_syntax_failure_scope='An earlier stdin command failed parse before any marker, process or target call; it did not execute this worker slot.'))
    env = os.environ.copy()
    env.update(intent['nonsecret_environment_overrides'])
    started = time.monotonic()
    with Path(intent['supervisor_stdout_path']).open('xb') as out, Path(intent['supervisor_stderr_path']).open('xb') as err:
        child = subprocess.Popen(intent['argv'], env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, start_new_session=True)
    first = snap(child.pid)
    assert first is not None
    observed = {(first['pid'], first['startticks']): first}
    groups, known = {child.pid}, {child.pid}
    reason, term_at, killed = None, None, False
    put(W / 'DEV_SUPERVISOR_STARTED.actual.v1.json', dict(
        schema_version=1, epoch=48, kind=KIND, phase='dev', supervisor=first,
        outer_launch_attempt=attempt, intent=ir, actual_supervisor_starts=1,
        nonsecret_environment_overrides=intent['nonsecret_environment_overrides'],
        absolute_monotonic_start=started, maximum_total_seconds=600))

    def observe():
        allp = []
        for p in Path('/proc').iterdir():
            if p.name.isdigit():
                s = snap(int(p.name))
                if s:
                    allp.append(s)
        changed = True
        while changed:
            changed = False
            for s in allp:
                if s['pid'] in known or s['ppid'] in known or s['pgid'] in groups or s['sid'] in groups:
                    observed[(s['pid'], s['startticks'])] = s
                    if s['pid'] not in known:
                        known.add(s['pid'])
                        groups.update((s['pgid'], s['sid']))
                        changed = True
        return [s for s in allp if (s['pid'], s['startticks']) in observed and s['state'] not in ('Z', 'X')]

    def kill_owned(sig, live):
        for group in sorted({s['pgid'] for s in live}):
            assert group in groups
            try:
                os.killpg(group, sig)
            except ProcessLookupError:
                pass

    while True:
        live, rc = observe(), child.poll()
        elapsed = time.monotonic() - started
        if rc is not None and not live:
            break
        s = snap(owner['pid'])
        held = s and s['startticks'] == owner['startticks'] and s['state'] not in ('Z', 'X') and time.time() < owner['expires_unix'] and not (W / 'release.request').exists()
        if not held:
            reason = reason or 'OWNER_LOSS'
        if rc is not None and live:
            reason = reason or 'STRAGGLER_AFTER_SUPERVISOR_EXIT'
        if elapsed >= 590:
            reason = reason or 'ROOT_590_SECOND_BACKSTOP'
        if reason and term_at is None:
            kill_owned(signal.SIGTERM, live)
            term_at = time.monotonic()
        if term_at is not None and not killed and (time.monotonic() - term_at >= 5 or elapsed >= 595):
            kill_owned(signal.SIGKILL, live)
            killed = True
        if elapsed >= 600:
            break
        time.sleep(.1)
    rc, live, wall = child.poll(), observe(), time.monotonic() - started
    identities = [{k: s[k] for k in ('pid', 'startticks', 'pgid', 'sid')} for _, s in sorted(observed.items())]
    final = [dict(identity=s, current=snap(s['pid'])) for s in identities]
    closed = not live and rc is not None
    zero = all(x['current'] is None or (
        x['current']['startticks'] == x['identity']['startticks'] and x['current']['state'] == 'Z'
        and x['current']['wait_status'] == 0 and x['current']['FDSize'] == 0
        and not any(x['current']['statm'])) for x in final)
    physical = dict(schema_version=1, epoch=48, kind=KIND, phase='dev',
        checks_passed=closed and zero and rc == 0 and reason is None and wall < 600,
        kernel_boot_id=owner['kernel_boot_id'], PID_namespace=owner['PID_namespace'],
        owned_process_identities=identities, final_process_snapshots=final,
        all_owned_experiment_processes_physically_closed=closed, live_owned_processes=live,
        outer_wall_seconds=wall, supervisor_exit_code=rc, forced_reason=reason,
        scope='Only experiment supervisor/worker/native descendants; the work-lock guardian remains outside these groups.')
    pr = put(W / 'DEV_PHYSICAL_CLOSURE.actual.v1.json', physical)
    execution = dict(schema_version=1, epoch=48, kind=KIND, phase='dev',
        actual_supervisor_starts=1, supervisor_pid=child.pid, supervisor_initial_identity=first,
        supervisor_exit_code=rc, wall_seconds_including_capture_and_physical_cleanup=wall,
        within_600_seconds=wall < 600, forced_reason=reason, intent_ref=ir,
        independent_launch_review=ar, outer_launch_attempt=attempt, physical_closure_ref=pr,
        nonsecret_environment_overrides=intent['nonsecret_environment_overrides'],
        Gold_EVAL_calls=0, automatic_retry=False)
    for name in ('execution.json', 'raw.json', 'raw-seal.json'):
        p = W / 'runs/dev' / name
        if p.exists():
            execution[name] = ref(p)
    er = put(W / 'DEV_OUTER_EXECUTION.actual.v1.json', execution)
    print(json.dumps(dict(execution=er, physical_closure=pr, supervisor_exit_code=rc,
                         wall_seconds=wall, within600=wall < 600,
                         physical_checks_passed=physical['checks_passed'],
                         forced_reason=reason, live_owned=len(live))))
    sys.exit(0 if physical['checks_passed'] else 17)


if __name__ == '__main__':
    main()
