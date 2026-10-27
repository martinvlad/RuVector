"""Root-only one-shot CLI wall capture, including interpreter bootstrap.

The independently reviewed supervisor owns worker/native cleanup. This parent
adds TERM at 590s, then bounded wait/KILL, leaving time to retain a receipt.
Any timeout or absent closure proof is a rejection, never retry authority.
"""
import time
START = time.monotonic()
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

W = Path('/dev/shm/ruvector-sota-2026-10-22/epoch56-ffdd0699f325')
KIND = 'REAL_NATIVE_SCIFACT_RETRIEVAL_DEV_PILOT'

def write(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with path.open('xb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())

def snap(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'startticks': int(fields[19]), 'state': fields[0]}
    except (FileNotFoundError, ProcessLookupError):
        return None

if sys.flags.optimize != 0:
    raise ValueError('NONOPTIMIZED_PYTHON_REQUIRED')
config_path = Path(sys.argv[1])
raw_config = config_path.read_bytes()
assert hashlib.sha256(raw_config).hexdigest() == sys.argv[2]
config = json.loads(raw_config)
assert config['epoch'] == 56 and config['kind'] == KIND and config['CPU_affinity'] == [0, 1]
assert sorted(os.sched_getaffinity(0)) == [0, 1]
argv = config['argv']
assert len(argv) == 16 and argv[1:3] == ['-I', '-B']
assert argv[3] == str(W / 'project/experiments/sota-2026-10-22/runtime/epoch56/retrieval/retrieval_supervisor.py')
assert argv[4::2] == ['--plan', '--expected-plan-sha256', '--admission', '--expected-admission-sha256', '--approval', '--expected-approval-sha256']
plan_bytes = Path(argv[5]).read_bytes()
assert hashlib.sha256(plan_bytes).hexdigest() == argv[7]
plan = json.loads(plan_bytes)
assert plan['epoch'] == 56 and plan['kind'] == KIND
assert plan['supervisor_source']['path'] == argv[3] and config['environment'] == plan['launch_environment']
assert hashlib.sha256(Path(argv[3]).read_bytes()).hexdigest() == plan['supervisor_source']['sha256']
assert argv[0] == '/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/bin/python'
write(W / 'ROOT_RETRIEVAL_CLI_LAUNCH.actual.v1.json', {
    'epoch': 56, 'kind': KIND, 'started_monotonic': START, 'argv': argv,
    'launch_config_sha256': sys.argv[2], 'automatic_retry': False})
env = os.environ.copy(); env.update(config['environment'])
timed_out = False
with (W / 'RETRIEVAL_SUPERVISOR.stdout').open('xb') as stdout, \
        (W / 'RETRIEVAL_SUPERVISOR.stderr').open('xb') as stderr:
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout,
                             stderr=stderr, env=env, close_fds=True)
    identity = snap(child.pid)
    write(W / 'ROOT_RETRIEVAL_CLI_STARTED.actual.v1.json',
          {'epoch': 56, 'kind': KIND, 'supervisor_identity': identity})
    try:
        code = child.wait(timeout=max(.1, 590 - (time.monotonic() - START)))
    except subprocess.TimeoutExpired:
        timed_out = True
        child.send_signal(signal.SIGTERM)
        try:
            code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill(); code = child.wait(timeout=2)
    stdout.flush(); stderr.flush(); os.fsync(stdout.fileno()); os.fsync(stderr.fileno())
wall = time.monotonic() - START
write(W / 'ROOT_RETRIEVAL_CLI_WALL.actual.v1.json', {
    'epoch': 56, 'kind': KIND, 'exit_code': code, 'supervisor_identity': identity,
    'supervisor_after_wait': snap(child.pid), 'timed_out': timed_out,
    'actual_CLI_wall_seconds_including_interpreter_bootstrap_capture': wall,
    'within_600_seconds': wall < 600,
    'requires_independent_worker_native_physical_closure': True,
    'automatic_retry': False})
print(json.dumps({'exit_code': code, 'CLI_wall_seconds': wall, 'timed_out': timed_out}))
raise SystemExit(code if not timed_out and wall < 600 else 19)
