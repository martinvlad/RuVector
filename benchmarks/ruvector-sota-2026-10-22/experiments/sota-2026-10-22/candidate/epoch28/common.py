"""Standard-library source/remote admission for one authored qualification."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch28'
SOURCE = '585c476cec6011b1db9c79147e3b0ff80124a6a3'
KIND = 'REAL_ENGINEERING_FULL104_QUALIFICATION'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 77846, 16105893, 13626
BINARY_SHA = 'e4db4b945a91b5cb8937765236e180763e8a3f4866b791e0f71a98d0018c289d'
SOURCE_MAP = 'experiments/sota-2026-10-22/audit/epoch27/full104-source-map.json'
SOURCE_MAP_SHA = 'a429bc7faa5658be89dca31c3bd8122e0d4c96758321e39f2105c24bbd21f127'
ENGINE = 'experiments/submission-2026-10-22/jevbench/engine.py'
RULES = 'experiments/submission-2026-10-22/jevbench/round2-v2/rules.py'
NATIVE_WORKER = 'experiments/swarm/jevbench-adapter/native-worker.cjs'
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'DEV_reads', 'CONF_reads', 'benchmark_label_reads', 'fits', 'calibration_calls',
        'training_steps', 'generation_calls', 'paid_calls', 'GPU_calls', 'HTTP_requests')


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


def read(path):
    return json.loads(Path(path).read_text())


def put(path, value):
    path = Path(path)
    no_symlink(path)
    with path.open('x') as target:
        json.dump(value, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def proc(pid):
    try:
        f = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': f[0], 'ppid': int(f[1]), 'pgid': int(f[2]),
                'sid': int(f[3]), 'ticks': int(f[19])}
    except (OSError, ValueError, IndexError):
        return None


def remaining(deadline):
    value = deadline - time.time()
    if not 0 < value <= 600:
        raise TimeoutError('Invalid or expired bounded qualification deadline')
    return value


def owner_lock(admission=None):
    if admission is not None and (admission.get('owner_pid') != OWNER_PID
            or admission.get('owner_startticks') != OWNER_TICKS):
        raise ValueError('Wrong exact guardian admission identity')
    owner = read(ROOT.parent / 'owner.json')
    row = proc(OWNER_PID)
    if (owner.get('pid') != OWNER_PID or owner.get('startticks') != OWNER_TICKS
            or owner.get('lock_inode') != LOCK_INODE or not row or row['ticks'] != OWNER_TICKS
            or row['state'] in ('Z', 'X') or time.time() >= owner['expires_unix']
            or (ROOT.parent / 'release.request').exists()):
        raise ValueError('Guardian dead, reused, released or expired')
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
    if path.absolute() != STUDY / 'NATIVE_ADMISSION.json':
        raise ValueError('Wrong external source admission path')
    value = read(path)
    if (value.get('epoch') != 28 or value.get('kind') != KIND
            or value.get('scope') != 'benchmarks/ruvector-sota-2026-10-22/'
            or value.get('verified_actual_remote_readback') is not True
            or value.get('plan_sha256') != plan_sha
            or value.get('source_freeze_sha256') != provisional['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}', value.get('published_source_commit', ''))):
        raise ValueError('Actual immutable remote source admission required')
    return value, owner_lock(value)


def verify_plan(path, expected):
    if path.absolute() != STUDY / 'plan.json' or sha(path) != expected:
        raise ValueError('Wrong exact plan identity')
    plan = read(path)
    if (plan.get('epoch') != 28 or plan.get('kind') != KIND
            or plan.get('source_checkpoint') != SOURCE or plan.get('actual_project') != str(ROOT)
            or plan.get('data_roles') != {'train': [], 'dev': [], 'calibration': [], 'confirmation': []}):
        raise ValueError('Only isolated authored engineering qualification admitted')
    exact = {'owned_workers': 1, 'CPU_threads': 2, 'CPU_affinity': [0, 1],
        'seconds_per_batch': 600, 'native_corpus_batches': 1, 'paid_calls': 0, 'GPU_calls': 0,
        'native_process_initializations': 1, 'native_systemOne_requests': 8}
    for key, value in exact.items():
        if plan['limits'].get(key) != value or type(plan['limits'][key]) is not type(value):
            raise ValueError('Wrong fixed budget: ' + key)
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate frozen source identity')
    for row in pins:
        target = checked(row['path'])
        if target.stat().st_size != row['bytes'] or sha(target) != row['sha256']:
            raise ValueError('Frozen source changed: ' + row['path'])
    for name in ('common.py', 'worker.py', 'launch_engineering.py', 'network_guard.py',
                 'node_guard.cjs', 'cpu_guard.py', 'RUNTIME_ASSETS.json', 'RAW_SCHEMA.json'):
        if str((HERE / name).relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned owned source: ' + name)
    for key in ('engineering_inputs', 'runtime_assets_lock', 'source_freeze'):
        if by_path.get(plan[key + '_path'], {}).get('sha256') != plan[key + '_sha256']:
            raise ValueError('Missing exact source/bank/runtime pin: ' + key)
    if by_path.get(SOURCE_MAP, {}).get('sha256') != SOURCE_MAP_SHA:
        raise ValueError('Wrong immutable original source map')
    mapped = read(checked(SOURCE_MAP))
    for row in mapped['source_files']:
        if by_path.get(row['path'], {}).get('sha256') != row['sha256']:
            raise ValueError('Original submitted dependency is not exactly pinned')
    return plan


def verify_runtime(plan):
    lock = read(checked(plan['runtime_assets_lock_path']))
    if len(lock['files']) != 17 or len({r['path'] for r in lock['files']}) != 17:
        raise ValueError('Exact14 native closure plus2 BGE assets plus original manifest required')
    for row in lock['files']:
        target = checked(row['path'])
        if target.stat().st_size != row['bytes'] or sha(target) != row['sha256']:
            raise ValueError('Exact original runtime asset changed: ' + row['path'])
    return lock
