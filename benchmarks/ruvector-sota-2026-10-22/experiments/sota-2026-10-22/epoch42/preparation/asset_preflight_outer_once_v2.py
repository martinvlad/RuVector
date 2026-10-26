"""Root-owned once-only 180-second stdlib asset admission outer process V2."""
import time
STARTED = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import signal
import subprocess

W = Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b')
R = W / 'project'
SOURCE_DIR = Path('/workspace/ruvector-e42-engineering-impl/asset-preflight-source-v2')
READY_SHA = '77b5558ad392f0c9a75bd79ad83f9d019dbe0c25b2beed533288ac398deebb53'
PLAN_REL = 'experiments/sota-2026-10-22/epoch42/preparation/ASSET_PREFLIGHT_PLAN.v2.json'
PLAN_SHA = '79867501c06c7e26ba99b33dc77fe304ef60faa67756366dc8792784c2a35de9'
ENTRY_REL = 'experiments/sota-2026-10-22/epoch42/preparation/asset_preflight.py'
SOURCE_APPROVAL = Path('/workspace/ruvector-e42-acceptance-audit/ASSET_PREFLIGHT_SOURCE_APPROVAL.v2.json')
SOURCE_APPROVAL_SHA = 'e2f58e915822267a66fddfa6c829d45b9185865ce71f647f5bd3b71e4428b8e8'
PYTHON = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/bin/python')
DEADLINE = STARTED + 180.0


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate metadata key')
        out[key] = value
    return out


def checked(path, expected_sha, expected_bytes=None):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Regular nonsymlink metadata required')
    raw = path.read_bytes()
    if digest(raw) != expected_sha or (expected_bytes is not None and len(raw) != expected_bytes):
        raise ValueError('Exact metadata identity changed')
    return raw


def put(name, value):
    path = W / name
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(W, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}


def process_identity(pid):
    fields = Path('/proc/%s/stat' % pid).read_text().split(') ', 1)[1].split()
    if len(fields) < 50:
        raise ValueError('Malformed owned process identity')
    return {'pid': pid, 'startticks': int(fields[19]), 'state': fields[0],
            'PGID': int(fields[2]), 'SID': int(fields[3])}


def signal_owned(process, identity, kind):
    if process.poll() is not None:
        return False
    try:
        now = process_identity(process.pid)
    except FileNotFoundError:
        return False
    if (now['startticks'] != identity['startticks'] or now['PGID'] != process.pid
            or now['SID'] != process.pid):
        raise ValueError('Uncertain ownership; no signal or retry')
    if now['state'] == 'Z':
        return False
    os.killpg(process.pid, kind)
    return True


def preexec():
    os.sched_setaffinity(0, {0, 1})
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--outer-approval', type=Path, required=True)
    parser.add_argument('--expected-outer-approval-sha256', required=True)
    args = parser.parse_args()
    self_sha = digest(Path(__file__).read_bytes())
    source_approval = json.loads(checked(SOURCE_APPROVAL, SOURCE_APPROVAL_SHA, 23645),
                                 object_pairs_hook=unique)
    if source_approval.get('checks_passed') is not True:
        raise ValueError('Independent source approval required')
    authority = json.loads(checked(args.outer_approval, args.expected_outer_approval_sha256),
                           object_pairs_hook=unique)
    required = {'checks_passed': True, 'asset_preflight_outer_execution_allowed': True,
                'root_outer_source_sha256': self_sha,
                'source_approval_sha256': SOURCE_APPROVAL_SHA,
                'preflight_ready_sha256': READY_SHA, 'preflight_plan_sha256': PLAN_SHA}
    if any(type(authority.get(k)) is not type(v) or authority.get(k) != v
           for k, v in required.items()):
        raise ValueError('Exact separately reviewed outer activation required')
    ready = json.loads(checked(SOURCE_DIR / 'PREFLIGHT_READY.v2.json', READY_SHA, 5220),
                       object_pairs_hook=unique)
    for item in ready['files'] + ready['required_existing_restored_inherited_files']:
        checked(R / item['path'], item['sha256'], item['bytes'])
    checked(R / PLAN_REL, PLAN_SHA, 6711)
    checked(W / 'mutation_guard.py',
            '868a68b35345ca53b5381aa61325d8ec97e7670a7cdb827f265b6f7b48e1850b', 3552)
    owner = runpy.run_path(str(W / 'mutation_guard.py'))['guard']()
    checked(Path('/workspace/ruvector-e42-independent-audit/planning-actual-readback-independent-v1.json'),
            'c286f2d9cba5525b895cd90974c8855593cc3a2455d36c3d923d045126949050', 3826)
    if owner['expires_unix'] - time.time() < 185:
        raise ValueError('Insufficient live lease')
    forbidden = ['ASSET_PREFLIGHT_ATTEMPT.json', 'ASSET_PREFLIGHT_RESULT.json',
                 'asset-preflight-exact-error.txt', 'ASSET_PREFLIGHT_OUTER_RESULT.json']
    if any((W / name).exists() for name in forbidden):
        raise ValueError('Consumed or uncertain old asset attempt; no retry')
    argv = ['/usr/bin/taskset', '-c', '0,1', str(PYTHON), '-I', '-B',
            str(R / ENTRY_REL), '--plan', str(R / PLAN_REL), '--expected-plan-sha', PLAN_SHA]
    put('ASSET_PREFLIGHT_OUTER_ATTEMPT.json', {
        'epoch': 42, 'kind': 'STDLIB_ASSET_HASH_PREFLIGHT_ONLY', 'argv': argv,
        'owner': owner, 'outer_source_sha256': self_sha,
        'outer_approval_sha256': args.expected_outer_approval_sha256,
        'source_approval_sha256': SOURCE_APPROVAL_SHA,
        'work_seconds_max': 175, 'whole_seconds_max': 180, 'cleanup_reserve': 5,
        'automatic_retry': False, 'ML_tokenizer_native_or_case_calls': 0,
        'at_unix': time.time()})
    if DEADLINE - time.monotonic() <= 5.0:
        raise ValueError('Bound exhausted before one child; no retry')
    process = None
    identity = None
    stdout, stderr = b'', b''
    signals = []
    lifecycle_errors = []
    ownership_uncertain = False
    work_deadline = None

    def record_error(error, scope):
        lifecycle_errors.append({'scope': scope, 'type': type(error).__name__,
                                 'message_sha256': digest(str(error).encode())})

    def collect(seconds):
        nonlocal stdout, stderr
        stdout, stderr = process.communicate(timeout=max(.001, seconds))

    try:
        popen_started = time.monotonic()
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, preexec_fn=preexec)
        work_deadline = min(popen_started + 175.0, DEADLINE - 5.0)
        identity = process_identity(process.pid)
        if identity['PGID'] != process.pid or identity['SID'] != process.pid:
            ownership_uncertain = True
            raise ValueError('Owned process group required')
        put('ASSET_PREFLIGHT_OUTER_CHILD.json', identity)
        # Identity capture and its durable receipt consume the work allowance.
        available_work = work_deadline - time.monotonic()
        if available_work <= 0:
            raise TimeoutError('Work bound consumed during child setup')
        collect(available_work)
    except BaseException as error:
        record_error(error, 'POST_POPEN_LIFECYCLE' if process is not None else 'POPEN')
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    if identity is None or ownership_uncertain:
                        ownership_uncertain = True
                        # Do not signal a PID/group whose identity was not authenticated.
                        collect(max(.001, DEADLINE - time.monotonic() - 1.5))
                    else:
                        if signal_owned(process, identity, signal.SIGTERM):
                            signals.append('TERM')
                        try:
                            collect(max(.001, min(3., DEADLINE-time.monotonic()-1.5)))
                        except BaseException as error:
                            record_error(error, 'TERM_CAPTURE')
                if process.poll() is None and identity is not None and not ownership_uncertain:
                    if signal_owned(process, identity, signal.SIGKILL):
                        signals.append('KILL')
                    collect(max(.001, min(1., DEADLINE-time.monotonic()-.5)))
                elif process.poll() is not None:
                    # Also capture a child that completed during receipt/error handling.
                    collect(max(.001, min(1., DEADLINE-time.monotonic()-.5)))
            except BaseException as error:
                record_error(error, 'FINAL_IDENTITY_BOUND_CLEANUP')
                ownership_uncertain = True
            finally:
                # A failed capture must still reap a known terminal child.
                if process.poll() is not None:
                    process.wait(timeout=.001)
    known_reaped = process is not None and process.poll() is not None
    for name, raw in [('asset-preflight-outer.stdout', stdout), ('asset-preflight-outer.stderr', stderr)]:
        fd = os.open(W / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    through_capture = time.monotonic() - STARTED
    result = {'epoch': 42, 'kind': 'STDLIB_ASSET_HASH_PREFLIGHT_ONLY',
              'exit_code': None if process is None else process.returncode, 'known_child_reaped': known_reaped,
              'child_identity': identity, 'signals': signals, 'lifecycle_errors': lifecycle_errors,
              'ownership_uncertain': ownership_uncertain, 'child_work_deadline': work_deadline,
              'wall_seconds_through_output_capture': through_capture,
              'whole_bound_passed': through_capture <= 180, 'automatic_retry': False,
              'stdout_bytes': len(stdout), 'stdout_sha256': digest(stdout),
              'stderr_bytes': len(stderr), 'stderr_sha256': digest(stderr),
              'peak_child_RSS_KiB': usage.ru_maxrss, 'user_seconds': usage.ru_utime,
              'system_seconds': usage.ru_stime,
              'resource_scope': 'One owned metadata child, RUSAGE_CHILDREN largest-child high-water',
              'ML_tokenizer_native_or_case_calls': 0,
              'outer_source_sha256': self_sha, 'actual_inner_result': 'ASSET_PREFLIGHT_RESULT.json'}
    receipt = put('ASSET_PREFLIGHT_OUTER_RESULT.json', result)
    print(json.dumps(receipt))
    if (not known_reaped or process.returncode != 0 or signals or lifecycle_errors
            or ownership_uncertain or time.monotonic() > DEADLINE):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
