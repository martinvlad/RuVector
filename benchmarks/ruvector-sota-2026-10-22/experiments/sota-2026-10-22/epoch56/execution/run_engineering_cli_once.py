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

W = Path(__file__).resolve().parent

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

config_path = Path(sys.argv[1])
raw_config = config_path.read_bytes()
assert hashlib.sha256(raw_config).hexdigest() == sys.argv[2]
config = json.loads(raw_config)
assert config['epoch'] == 56 and config['CPU_affinity'] == [0, 1]
assert sorted(os.sched_getaffinity(0)) == [0, 1]
argv = config['argv']
assert argv[1:3] == ['-I', '-B'] and argv[3].endswith('/runtime/epoch56/supervisor.py')
assert argv[0] == '/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/bin/python'
write(W / 'ROOT_ENGINEERING_CLI_LAUNCH.actual.v1.json', {
    'epoch': 56, 'started_monotonic': START, 'argv': argv,
    'launch_config_sha256': sys.argv[2], 'automatic_retry': False})
env = os.environ.copy(); env.update(config['environment'])
timed_out = False
with (W / 'ENGINEERING_SUPERVISOR.stdout').open('xb') as stdout, \
        (W / 'ENGINEERING_SUPERVISOR.stderr').open('xb') as stderr:
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout,
                             stderr=stderr, env=env, close_fds=True)
    identity = snap(child.pid)
    write(W / 'ROOT_ENGINEERING_CLI_STARTED.actual.v1.json',
          {'epoch': 56, 'supervisor_identity': identity})
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
write(W / 'ROOT_ENGINEERING_CLI_WALL.actual.v1.json', {
    'epoch': 56, 'exit_code': code, 'supervisor_identity': identity,
    'supervisor_after_wait': snap(child.pid), 'timed_out': timed_out,
    'actual_CLI_wall_seconds_including_interpreter_bootstrap_capture': wall,
    'within_600_seconds': wall < 600,
    'requires_independent_worker_native_physical_closure': True,
    'automatic_retry': False})
print(json.dumps({'exit_code': code, 'CLI_wall_seconds': wall, 'timed_out': timed_out}))
raise SystemExit(code if not timed_out and wall < 600 else 19)
