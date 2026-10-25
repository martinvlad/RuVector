"""Root-only one-shot E33 supervisor dispatch; no model, tokenizer or native import.

The plan SHA is supplied after the master source freeze to avoid a hash cycle.
The immutable plan must itself pin this exact driver. A durable reservation is
written before the sole Popen boundary; any uncertainty consumes the slot.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
W = Path('/workspace/ruvector-epoch33-0522a2c521c9')
G = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9')
R = W / 'project'
E = R / 'experiments/sota-2026-10-22/epoch33'
CANDIDATE = R / 'experiments/sota-2026-10-22/candidate/epoch33'
PYTHON = G / 'runtime/.venv/bin/python'
KIND = 'REAL_NATIVE_TYPED_MODAL_RETRIEVAL_NLI_DIAGNOSTIC'
COMMON_SHA = '08075dac21e62e130ea7bee9ad027317e29981386559b0a4366013cce1423b79'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            digest.update(part)
    return digest.hexdigest()


def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Missing/nonregular/symlink file: ' + str(path))


def put(path, value):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink output refused')
    with path.open('x', encoding='utf-8') as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def host_admission(plan):
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        name, value = line.split(':', 1)
        if name in ('MemTotal', 'MemAvailable'):
            mem[name] = int(value.split()[0]) * 1024
    limits = Path('/sys/fs/cgroup')
    maximum = (limits / 'memory.max').read_text().strip()
    current = int((limits / 'memory.current').read_text().strip())
    maximum = None if maximum == 'max' else int(maximum)
    capacity = min(mem['MemTotal'], maximum) if maximum is not None else mem['MemTotal']
    unallocated = min(mem['MemAvailable'], maximum - current) if maximum is not None else mem['MemAvailable']
    free = shutil.disk_usage(W).free
    policy = plan['host_admission_policy']
    if capacity < 3 * 1024 ** 3 or unallocated < policy['minimum_unallocated_memory_bytes']:
        raise RuntimeError('Insufficient current effective memory capacity/headroom; no dispatch')
    if free < policy['minimum_workspace_free_bytes']:
        raise RuntimeError('Insufficient current workspace free space; no dispatch')
    return {'observed_at_unix': time.time(), 'mem_total_bytes': mem['MemTotal'],
            'mem_available_bytes': mem['MemAvailable'], 'cgroup_memory_max_bytes': maximum,
            'cgroup_memory_current_bytes': current, 'effective_capacity_bytes': capacity,
            'effective_unallocated_bytes': unallocated, 'workspace_free_bytes': free,
            'minimum_effective_capacity_bytes': 3 * 1024 ** 3,
            'frozen_policy': policy, 'passed': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-plan-sha', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}', args.expected_plan_sha):
        raise ValueError('An exact frozen plan SHA256 is required')
    own = Path(__file__).absolute()
    if own != E / 'preparation/dispatch_once.py' or own != own.resolve():
        raise ValueError('Only the exact prospective public driver may dispatch')
    if Path(sys.prefix).absolute() != PYTHON.parent.parent:
        raise ValueError('Use the exact restored E33 external Python environment')
    common_path = CANDIDATE / 'runtime/common.py'
    regular(common_path)
    if sha(common_path) != COMMON_SHA:
        raise ValueError('Changed reviewed standard-library admission source')
    spec = importlib.util.spec_from_file_location('e33_root_dispatch_stdlib_common', common_path)
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    C.owner_lock()
    plan = C.verify_plan(E / 'plan.json', args.expected_plan_sha, 'dev')
    if plan['kind'] != KIND or plan['inference_python'] != str(PYTHON):
        raise ValueError('Wrong exact E33 pretrained diagnostic/interpreter')
    if plan['guardian_scope'] != str(G) or plan['actual_project'] != str(R):
        raise ValueError('Controller and guardian scope must remain distinct')
    own_ref = {'path': own.relative_to(R).as_posix(), 'bytes': own.stat().st_size, 'sha256': sha(own)}
    if own_ref not in plan['pins']:
        raise ValueError('The master source plan does not pin this driver')
    admission_path = E / 'SOURCE_ADMISSION.json'
    admission, _ = C.admission(admission_path, plan, args.expected_plan_sha, 'dev')
    if C.read(G / 'owner.json')['expires_unix'] - time.time() < 615:
        raise RuntimeError('Less than615seconds lease remains; full600second budget unavailable')
    stdout, stderr = W / 'supervisor.stdout', W / 'supervisor.stderr'
    forbidden = [E / name for name in ('DISPATCH_RESERVATION.json', 'DISPATCH_ATTEMPT.json',
        'DEV_ATTEMPT_RESERVATION.json', 'SUPERVISOR_COMPLETION.json',
        'SUPERVISOR_OBSERVED_CLOSURE.json', 'runs/dev')]
    forbidden += [stdout, stderr, W / 'dispatch-observer-receipt.json', W / 'dispatch-error.json',
                  W / 'dispatch-host-admission.json']
    if any(path.exists() or path.is_symlink() for path in forbidden):
        raise RuntimeError('Existing consumed/uncertain E33 dispatch artifact; no retry')
    host = host_admission(plan)
    put(W / 'dispatch-host-admission.json', host)
    with stdout.open('xb') as out, stderr.open('xb') as err:
        C.owner_lock(admission)
        claim = {'schema_version': 1, 'epoch': 33, 'kind': KIND, 'phase': 'dev',
            'plan_sha256': args.expected_plan_sha, 'source_freeze_sha256': plan['source_freeze_sha256'],
            'pretrained_model_source_sha256': plan['pretrained_model_source_sha256'],
            'model_assets_lock_sha256': plan['model_assets_lock_sha256'],
            'admission_sha256': sha(admission_path), 'kernel_boot_id': admission['kernel_boot_id'],
            'pid_namespace_inode': admission['pid_namespace_inode'],
            'dispatch_monotonic_seconds': time.monotonic(), 'dispatch_unix_seconds': time.time(),
            'logical_native_budget_reserved': 1, 'allowed_further_dispatches': 0}
        put(E / 'DISPATCH_RESERVATION.json', claim)
        argv = ['taskset', '-c', '0,1', str(PYTHON), '-I', '-B',
            str(CANDIDATE / 'runtime/launch.py'), '--scope', str(G), '--phase', 'dev',
            '--plan', str(E / 'plan.json'), '--admission', str(admission_path),
            '--expected-plan-sha', args.expected_plan_sha]
        try:
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                start_new_session=True, close_fds=True, cwd=R)
            fields = Path('/proc/' + str(child.pid) + '/stat').read_text().rsplit(')', 1)[1].split()
            pid = child.pid
            if int(fields[2]) != pid or int(fields[3]) != pid or fields[0] in ('Z', 'X'):
                raise RuntimeError('New detached supervisor identity unverified; no retry')
            attempt = {**claim, 'pid': pid, 'startticks': int(fields[19]), 'pgid': pid, 'sid': pid,
                'verified_launcher_start': True, 'uncertain_launcher_start': False}
            put(E / 'DISPATCH_ATTEMPT.json', attempt)
            put(W / 'dispatch-observer-receipt.json', {
                'supervisor_identity': {key: attempt[key] for key in ('pid', 'startticks', 'pgid', 'sid')},
                'stdout': str(stdout), 'stderr': str(stderr), 'argv': argv,
                'detached_supervisor_exit_code_observed': False, 'allowed_further_dispatches': 0,
                'dispatch_controller': own_ref, 'host_admission': {
                    'path': str(W / 'dispatch-host-admission.json'),
                    'sha256': sha(W / 'dispatch-host-admission.json')}})
        except BaseException as error:
            put(W / 'dispatch-error.json', {'error_type': type(error).__name__, 'error': str(error),
                'dispatch_budget_consumed': 1,
                'actual_supervisor_or_model_start': 'UNKNOWN_UNLESS_MATCHING_DURABLE_IDENTITY_PROOF',
                'allowed_further_dispatches': 0})
            raise
    print(json.dumps({'dispatched_once': True, 'supervisor_identity': {
        key: attempt[key] for key in ('pid', 'startticks', 'pgid', 'sid')},
        'budget_reserved': 1, 'MODEL_calls_by_dispatch_driver': 0,
        'supervisor_exit_code_observed': False}, allow_nan=False))


if __name__ == '__main__':
    main()
