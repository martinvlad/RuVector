"""Standard-library-only epoch27 admission and immutable-source helpers."""
from __future__ import annotations
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'experiments/sota-2026-10-22/'
STUDY = ROOT / PREFIX / 'epoch27'
SOURCE = '6e4ad4ab0b6a09a6a1083335ed0401637227d17f'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 75591, 15190845, 13626
BGE_SOURCE = PREFIX + 'candidate/epoch3/models.py'
BGE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
CONTEXT_SOURCE = PREFIX + 'candidate/epoch22/context.py'
CONTEXT_SHA = '9ca2968ed800443bc75fac452daf2cbf17bf27cf1b3b75cbfb220bfa23a9e727'
CONTEXT_DEPENDENCIES = {
    PREFIX + 'candidate/epoch6/context.py': '28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2',
    PREFIX + 'candidate/epoch15/context.py': '9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb',
}
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
ARMS = ('actual_native', 'lexical', 'positional')
DOCUMENT_IDS = ('609', '380', '592', '454', '559', '515', '349', '223')
HYPOTHESIS_IDS = ('nda-17', 'nda-7', 'nda-3')
LIMITS = {'worker_attempts': 1, 'native_corpus_batches': 1, 'cpu_threads': 2,
    'seconds_per_batch': 600, 'paid_calls': 0, 'GPU_calls': 0,
    'NLI_model_initializations': 1, 'NLI_forward_pairs': 72}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def no_symlink(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink path refused')


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


def put(path, value, *, compact=False):
    path = Path(path)
    no_symlink(path)
    with path.open('x') as target:
        json.dump(value, target, ensure_ascii=False, indent=None if compact else 2,
                  separators=(',', ':') if compact else None, allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def remaining(deadline):
    seconds = deadline - time.time()
    if seconds <= 0:
        raise TimeoutError('Whole DEV-only diagnostic deadline reached')
    return seconds


def proc(pid):
    try:
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'sid': int(fields[3]), 'ticks': int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def owner_lock(admission=None):
    if admission is not None and (admission.get('owner_pid') != OWNER_PID
            or admission.get('owner_startticks') != OWNER_TICKS):
        raise ValueError('Wrong exact epoch27 guardian identity')
    owner = read(ROOT.parent / 'owner.json')
    process = proc(OWNER_PID)
    if (owner.get('pid') != OWNER_PID or owner.get('startticks') != OWNER_TICKS
            or owner.get('lock_inode') != LOCK_INODE or not process
            or process['ticks'] != OWNER_TICKS or process['state'] in ('Z', 'X')
            or time.time() >= owner['expires_unix'] or (ROOT.parent / 'release.request').exists()):
        raise ValueError('Guardian PID reused, dead, released or lease expired')
    lock = ROOT.parent.parent / 'exclusive.work.lock'
    if owner.get('lock') != str(lock):
        raise ValueError('Guardian lock path mismatch')
    no_symlink(lock)
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_ino != LOCK_INODE:
            raise ValueError('Wrong kernel lock inode')
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        active = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) >= 8 and words[1:5] == ['FLOCK', 'ADVISORY', 'WRITE', str(OWNER_PID)]:
                a, b, c = words[5].split(':')
                active |= (int(a, 16), int(b, 16), int(c)) == target
        if not active:
            raise ValueError('Exact guardian lacks kernel FLOCK')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'owner_pid': OWNER_PID, 'owner_startticks': OWNER_TICKS,
                    'lock_inode': LOCK_INODE, 'contender_denied': True}
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise ValueError('Contender unexpectedly acquired guardian lock')
    finally:
        os.close(fd)


def load_module(name, path, expected=None):
    if expected is not None and sha(path) != expected:
        raise ValueError('Pinned Python dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_plan(path, expected):
    if Path(path).absolute() != STUDY / 'plan.json' or sha(path) != expected:
        raise ValueError('Plan path/hash mismatch')
    plan = read(path)
    if (plan.get('schema_version') != 1 or plan.get('epoch') != 27
            or plan.get('phase') != 'dev' or plan.get('diagnostic_only') is not True
            or plan.get('source_checkpoint') != SOURCE or plan.get('actual_project') != str(ROOT)
            or plan.get('champion_promotion_allowed') is not False
            or plan.get('confirmation_execution_allowed') is not False):
        raise ValueError('Wrong isolated DEV-only epoch27 plan')
    for key, value in LIMITS.items():
        if type(plan['limits'].get(key)) is not int or plan['limits'][key] != value:
            raise ValueError('Wrong exact budget: ' + key)
    roles = plan['benchmark_roles']
    expected_ids = ['original-contractnli:train:epoch27:dev:' + d + ':' + h
                    for d in DOCUMENT_IDS for h in HYPOTHESIS_IDS]
    if roles != {'train': [], 'dev': expected_ids, 'calibration': [], 'confirmation': []}:
        raise ValueError('Only the prospective exact 24 DEV identities are allowed')
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate source pins')
    for row in pins:
        source = checked(row['path'])
        if source.stat().st_size != row['bytes'] or sha(source) != row['sha256']:
            raise ValueError('Frozen source changed: ' + row['path'])
    required = ['common.py', 'worker.py', 'native.cjs', 'evidence.py', 'network_guard.py', 'reader/bart_reader.py', 'MODEL_ASSETS.json']
    for name in required:
        if str((HERE / name).relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned candidate file: ' + name)
    for relative, digest in {BGE_SOURCE: BGE_SHA, CONTEXT_SOURCE: CONTEXT_SHA, **CONTEXT_DEPENDENCIES}.items():
        if by_path.get(relative, {}).get('sha256') != digest:
            raise ValueError('Wrong exact reused BGE/context dependency: ' + relative)
    for key in ('inputs', 'runtime_assets_lock', 'reader_assets_lock', 'source_freeze'):
        relative = plan[key + '_path']
        if by_path.get(relative, {}).get('sha256') != plan[key + '_sha256']:
            raise ValueError('Missing exact source/runtime/bank pin: ' + key)
    if plan['inputs_path'] != PREFIX + 'epoch27/data/dev.inputs.json':
        raise ValueError('Wrong DEV-only input bank path')
    return plan, by_path


def verify_admission(path, plan, digest):
    if Path(path).absolute() != STUDY / 'NATIVE_ADMISSION.json':
        raise ValueError('Wrong actual source admission path')
    admission = read(path)
    if (admission.get('epoch') != 27 or admission.get('phase') != 'dev'
            or admission.get('scope') != 'benchmarks/ruvector-sota-2026-10-22/'
            or admission.get('verified_actual_remote_readback') is not True
            or admission.get('plan_sha256') != digest
            or admission.get('source_freeze_sha256') != plan['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}', admission.get('published_source_commit', ''))):
        raise ValueError('Late immutable remote source admission missing')
    return admission, owner_lock(admission)


def verify_assets(plan):
    runtime = read(checked(plan['runtime_assets_lock_path']))
    rows = runtime['assets']
    if len(rows) != 10 or len({row['path'] for row in rows}) != 10:
        raise ValueError('Exactly two BGE + eight native closure files required')
    if {row['path'] for row in rows if row['path'].startswith('models/')} != {
            'models/bge-small-en-v1.5/model.onnx', 'models/bge-small-en-v1.5/tokenizer.json'}:
        raise ValueError('Wrong BGE asset closure')
    for row in rows:
        source = checked(row['path'])
        if source.stat().st_size != row['bytes'] or sha(source) != row['sha256']:
            raise ValueError('Runtime asset changed: ' + row['path'])
    versions = {key: importlib.metadata.version(key) for key in plan['python_expected_versions']}
    if versions != plan['python_expected_versions']:
        raise ValueError('Python package versions changed')
    reader = load_module('epoch27_frozen_reader', HERE / 'reader/bart_reader.py')
    model_dir = ROOT / plan['reader_model_dir']
    no_symlink(model_dir)
    if model_dir.resolve() != model_dir or not model_dir.is_dir():
        raise ValueError('Unsafe selected model directory')
    reader_lock = reader.verify_runtime_assets(model_dir, checked(plan['reader_assets_lock_path']))
    external = rows + [{'path': plan['reader_model_dir'] + '/' + r['path'],
                        'bytes': r['bytes'], 'sha256': r['sha256']} for r in reader_lock['files']]
    freeze = read(checked(plan['source_freeze_path']))
    identity = lambda row: (row['path'], row['bytes'], row['sha256'])
    if (len(freeze['external_runtime_assets']) != len(external)
            or set(map(identity, freeze['external_runtime_assets'])) != set(map(identity, external))):
        raise ValueError('Source freeze does not bind exact external runtime identities')
    return rows, versions, reader
