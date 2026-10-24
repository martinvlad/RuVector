"""Standard-library-only admission for one native document-identity worker."""
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch29'
CANDIDATE = HERE.parent
SOURCE = '07a2cbe78fdee78a8c9bca2aeb64bc9746481ba0'
KIND = 'REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 80007, 17161777, 13626
OWNER_EXPIRY = 1792858715.860032
BINARY = 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'TRAIN_reads', 'DEV_reads', 'CONF_reads', 'benchmark_label_reads', 'fits',
        'calibration_calls', 'training_steps', 'NLI_calls', 'Torch_imports', 'generation_calls',
        'paid_calls', 'GPU_calls', 'HTTP_requests')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def no_symlink(path):
    if any(p.is_symlink() for p in (Path(path), *Path(path).parents)):
        raise ValueError('Symlink component refused')


def checked(relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(x in ('', '.', '..') for x in relative.split('/'))):
        raise ValueError('Unsafe frozen path')
    path = ROOT / relative
    no_symlink(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Missing/nonregular frozen file: ' + relative)
    return path


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite JSON number')
    return result


def read(path):
    no_symlink(path)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_object,
        parse_float=_float, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def put(path, value):
    path = Path(path)
    no_symlink(path)
    with path.open('x', encoding='utf-8') as target:
        json.dump(value, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def proc(pid):
    try:
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'sid': int(fields[3]), 'ticks': int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def remaining(deadline):
    value = deadline - time.time()
    if not 0 < value <= 600:
        raise TimeoutError('Invalid/expired bounded document-identity deadline')
    return value


def owner_lock(admitted=None):
    if admitted is not None and (admitted.get('owner_pid') != OWNER_PID
            or admitted.get('owner_startticks') != OWNER_TICKS):
        raise ValueError('Wrong exact guardian admission identity')
    owner = read(ROOT.parent / 'owner.json')
    row = proc(OWNER_PID)
    if (owner.get('pid') != OWNER_PID or owner.get('startticks') != OWNER_TICKS
            or owner.get('lock_inode') != LOCK_INODE or owner.get('expires_unix') != OWNER_EXPIRY
            or not row or row['ticks'] != OWNER_TICKS or row['state'] in ('Z', 'X')
            or time.time() >= OWNER_EXPIRY or (ROOT.parent / 'release.request').exists()):
        raise ValueError('Guardian dead/reused/released/expired or lease changed')
    lock = ROOT.parent.parent / 'exclusive.work.lock'
    if owner.get('lock') != str(lock):
        raise ValueError('Wrong scoped lock path')
    no_symlink(lock)
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_ino != LOCK_INODE:
            raise ValueError('Wrong lock inode')
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        active = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) >= 8 and words[1:5] == ['FLOCK', 'ADVISORY', 'WRITE', str(OWNER_PID)]:
                a, b, c = words[5].split(':')
                active |= (int(a, 16), int(b, 16), int(c)) == target
        if not active:
            raise ValueError('Exact guardian kernel lock absent')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'owner_pid': OWNER_PID, 'owner_startticks': OWNER_TICKS,
                    'lock_inode': LOCK_INODE, 'contender_denied': True}
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise ValueError('Contender unexpectedly acquired guardian lock')
    finally:
        os.close(fd)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def admission(path, provisional, plan_sha):
    if Path(path).absolute() != STUDY / 'NATIVE_ADMISSION.json':
        raise ValueError('Wrong external source admission path')
    value = read(path)
    if (value.get('epoch') != 29 or value.get('kind') != KIND
            or value.get('scope') != 'benchmarks/ruvector-sota-2026-10-22/'
            or value.get('verified_actual_remote_readback') is not True
            or value.get('plan_sha256') != plan_sha
            or value.get('source_freeze_sha256') != provisional['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}', value.get('published_source_commit', ''))):
        raise ValueError('Actual immutable remote source admission required')
    return value, owner_lock(value)


def verify_ref(row):
    if not isinstance(row, dict) or type(row.get('bytes')) is not int or row['bytes'] < 0:
        raise ValueError('Invalid exact file reference')
    if not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
        raise ValueError('Invalid exact file digest')
    target = checked(row['path'])
    if target.stat().st_size != row['bytes'] or sha(target) != row['sha256']:
        raise ValueError('Frozen bytes changed: ' + row['path'])
    return target


def verify_plan(path, expected):
    if Path(path).absolute() != STUDY / 'plan.json' or sha(path) != expected:
        raise ValueError('Wrong exact source plan identity')
    plan = read(path)
    if (plan.get('epoch') != 29 or plan.get('kind') != KIND
            or plan.get('source_checkpoint') != SOURCE or plan.get('actual_project') != str(ROOT)
            or not same(plan.get('data_roles'), {'train': [], 'dev': [], 'calibration': [], 'confirmation': []})):
        raise ValueError('Only isolated native document-identity engineering admitted')
    exact = {'owned_workers': 1, 'CPU_threads': 2, 'CPU_affinity': [0, 1],
        'seconds_per_batch': 600, 'native_corpus_batches': 0, 'engineering_batches': 1,
        'paid_calls': 0, 'GPU_calls': 0}
    for key, value in exact.items():
        if not same(plan['limits'].get(key), value):
            raise ValueError('Wrong fixed budget: ' + key)
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate frozen source identity')
    for row in pins:
        verify_ref(row)
    for name in ('common.py', 'launch.py', 'network_guard.py', 'node_guard.cjs', 'cpu_guard.py'):
        if str((HERE / name).relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned runtime source: ' + name)
    if plan.get('worker_path') != str((CANDIDATE / 'worker.py').relative_to(ROOT)):
        raise ValueError('Wrong core worker path')
    if plan['worker_path'] not in by_path:
        raise ValueError('Unpinned core worker')
    if (plan.get('native_worker_path') != str((CANDIDATE / 'native_identity.cjs').relative_to(ROOT))
            or plan['native_worker_path'] not in by_path):
        raise ValueError('Unpinned exact native identity helper')
    expected_counters = plan.get('expected_operation_counters')
    if (not isinstance(expected_counters, dict) or not expected_counters
            or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in expected_counters.items())):
        raise ValueError('Exact nonnegative integer operation budget required')
    for key in ('engineering_inputs', 'runtime_assets_lock', 'source_freeze'):
        if by_path.get(plan[key + '_path'], {}).get('sha256') != plan[key + '_sha256']:
            raise ValueError('Missing exact input/runtime/source-freeze pin: ' + key)
    if plan['source_freeze_path'] != str((STUDY / 'source-freeze.json').relative_to(ROOT)):
        raise ValueError('Wrong canonical source freeze')
    frozen = read(checked(plan['source_freeze_path']))
    if frozen.get('epoch') != 29 or frozen.get('kind') != KIND or frozen.get('source_checkpoint') != SOURCE:
        raise ValueError('Wrong source-freeze epoch/kind/checkpoint')
    entries = frozen['entries']
    if len({row['path'] for row in entries}) != len(entries):
        raise ValueError('Duplicate source-freeze entry')
    for row in entries:
        if not same(by_path.get(row['path']), row):
            raise ValueError('Source-freeze entry absent/different from exact plan pin')
    return plan


def verify_runtime(plan):
    lock = read(checked(plan['runtime_assets_lock_path']))
    assets = lock['assets']
    if len(assets) != 10 or len({row['path'] for row in assets}) != 10:
        raise ValueError('Exact original10 core/BGE assets required')
    rows = {row['path']: row for row in assets}
    required = {BINARY: BINARY_SHA,
        'models/bge-small-en-v1.5/model.onnx': '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35',
        'models/bge-small-en-v1.5/tokenizer.json': 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'}
    for path, expected in required.items():
        if rows.get(path, {}).get('sha256') != expected:
            raise ValueError('Wrong original core/BGE identity')
    if (lock.get('native_core_runtime_version') != '2.3.0'
            or lock.get('native_NPM_version') != '0.1.33'
            or lock.get('native_platform_NPM_version') != '0.1.31'
            or lock.get('python_expected_versions') != {'numpy': '2.2.6', 'onnxruntime': '1.22.1', 'tokenizers': '0.21.4'}):
        raise ValueError('Wrong frozen original runtime versions')
    for row in assets:
        verify_ref(row)
    pins = {row['path']: row for row in plan.get('pins', [])}
    for key in ('wheel_lock', 'native_closure', 'BGE_source'):
        relative, digest = lock[key + '_path'], lock[key + '_sha256']
        if pins.get(relative, {}).get('sha256') != digest or sha(checked(relative)) != digest:
            raise ValueError('Unpinned original runtime dependency: ' + key)
    reference = lock.get('wheel_members_reference_path')
    digest = lock.get('wheel_members_reference_sha256')
    if (digest != '87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'
            or lock.get('wheel_members_reference_count') != 17498
            or pins.get(reference, {}).get('sha256') != digest or sha(checked(reference)) != digest):
        raise ValueError('Wrong original installed-wheel member reference')
    members = read(checked(reference))
    if len(members) != 17498 or len({row['path'] for row in members}) != 17498:
        raise ValueError('Wrong exact17498 installed-wheel closure')
    for row in members:
        verify_ref({'path': 'retrieval/.venv/' + row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    return lock
