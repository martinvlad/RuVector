"""Pure epoch20 identities, bounded protocol and owned-lock admission."""
from __future__ import annotations
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'experiments/sota-2026-10-22/'
STUDY = ROOT / PREFIX / 'epoch20'
SOURCE = '01c42365b8d79c968ea4f49120a5c1d71b9e0687'
STUDY_ID = 'native-anli-roberta-fp32-typed-e20'
MODEL = 'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli'
REVISION = '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed'
ARMS = ('ruvector_top2', 'same_nli_lexical_top2', 'same_nli_positional_first2')
ORDER = ('Entailment', 'Contradiction', 'NotMentioned')
LIMITS = {'threads': 2, 'interop_threads': 1, 'seconds_per_batch': 600,
          'worker_attempts': 2, 'native_batches': 2, 'candidate_configs': 1,
          'paid_calls': 0, 'GPU_calls': 0}
NATIVE_SCRIPT = 'retrieval/native-candidates.cjs'
NATIVE_SCRIPT_SHA = '45efc7fecd2d249aea7bd1f5e7d36bf26cfe57cd6f91de51ffd15adc039ec4a3'
NATIVE_BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def checked(relative, root=ROOT):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(x in ('', '.', '..') for x in relative.split('/'))):
        raise ValueError('Unsafe frozen member path')
    p = Path(root) / relative
    if any(x.is_symlink() for x in [p, *p.parents]) or not p.is_file():
        raise ValueError('Missing or nonregular frozen member: ' + relative)
    return p


def read(path): return json.loads(Path(path).read_text())


def write_new(path, value):
    p = Path(path)
    if any(x.is_symlink() for x in [p, *p.parents]): raise ValueError('Symlink output')
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())


def replace_report(path, value):
    p = Path(path); tmp = Path(str(p) + '.tmp')
    if any(x.is_symlink() for x in [p, tmp, *p.parents]): raise ValueError('Symlink output')
    with tmp.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


def load_module(name, relative, expected=None):
    p = checked(relative)
    if expected is not None and sha(p) != expected: raise ValueError('Module identity changed')
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def distribution(logits):
    if len(logits) != 3 or any(not math.isfinite(float(x)) for x in logits):
        raise ValueError('Exactly three finite raw logits required')
    e = [math.exp(float(x) - max(logits)) for x in logits]; mass = math.fsum(e)
    raw = [x / mass for x in e]
    typed = dict(zip(ORDER, (raw[0], raw[2], raw[1])))
    return raw, typed


def prediction(typed): return max(ORDER, key=lambda label: typed[label])


def canaries(plan):
    value = read(checked(plan['canaries_path']))
    rows = value['fixtures']
    expected = [('semantic-e-v1', 'The lamp is on.', 'The lamp is on.', 'Entailment'),
                ('semantic-c-v1', 'The lamp is not on.', 'The lamp is on.', 'Contradiction'),
                ('semantic-n-v1', 'The box is blue.', 'The lamp is on.', 'NotMentioned')]
    if [(r['id'], r['premise'], r['hypothesis'], r['expected_typed_label']) for r in rows] != expected:
        raise ValueError('Exactly the three already exposed engineering examples required')
    return rows


def require_plan(path, expected=None):
    if expected is not None and sha(path) != expected: raise ValueError('Plan bytes changed')
    p = read(path)
    if (p.get('epoch') != 20 or p.get('schema_version') != 1
            or p.get('source_checkpoint') != SOURCE or p.get('study_id') != STUDY_ID
            or p.get('actual_project') != str(ROOT)):
        raise ValueError('Wrong isolated epoch20 source/plan')
    if any(type(p['limits'].get(k)) is not int or p['limits'][k] != v for k, v in LIMITS.items()):
        raise ValueError('Exact CPU2/two-process/600s/zero-spend budget required')
    if p.get('train') or p.get('calibration'): raise ValueError('No fitting/calibration role')
    pins = p['pins']; by_path = {r['path']: r for r in pins}
    if len(by_path) != len(pins): raise ValueError('Duplicate source pin')
    for r in pins:
        f = checked(r['path'])
        if sha(f) != r['sha256'] or ('bytes' in r and f.stat().st_size != r['bytes']):
            raise ValueError('Source pin changed: ' + r['path'])
    for f in HERE.glob('*.py'):
        r = str(f.relative_to(ROOT))
        if r not in by_path: raise ValueError('Unpinned candidate source: ' + r)
    for key in ('model_assets_lock', 'bge_assets_lock', 'native_closure', 'canaries', 'wheel_lock', 'source_freeze', 'audit_protocol'):
        rel = p[key + '_path']; want = p[key + '_sha256']
        if rel not in by_path or by_path[rel]['sha256'] != want or sha(checked(rel)) != want:
            raise ValueError('Unpinned scientific protocol: ' + key)
    snapshot = read(checked(p['source_freeze_path']))
    if snapshot.get('source_checkpoint') != SOURCE: raise ValueError('Wrong source snapshot')
    for r in snapshot['files']:
        f = checked(r['path'])
        if r['path'] not in by_path or sha(f) != r['sha256'] or f.stat().st_size != r['bytes']:
            raise ValueError('Source snapshot member changed')
    if by_path.get(NATIVE_SCRIPT, {}).get('sha256') != NATIVE_SCRIPT_SHA:
        raise ValueError('Exact actual native helper required')
    for phase in ('dev', 'confirmation'):
        entry = p['phases'][phase]
        for key in ('input_recipe', 'input_allowlist'):
            rel = entry[key + '_path']; want = entry[key + '_sha256']
            if by_path.get(rel, {}).get('sha256') != want or sha(checked(rel)) != want:
                raise ValueError('Unpinned phase recipe/identity')
    cap_path = p['confirmation_capacity_inputs_path']; cap_sha = p['confirmation_capacity_inputs_sha256']
    if by_path.get(cap_path, {}).get('sha256') != cap_sha or sha(checked(cap_path)) != cap_sha:
        raise ValueError('Unpinned previously published input-only confirmation capacity bank')
    if not math.isfinite(p['lease_expires_unix']): raise ValueError('Finite lease required')
    canaries(p)
    return p


def verify_owner_lock(value):
    owner, ticks, inode = (value[k] for k in ('owner_pid', 'owner_start_ticks', 'lock_inode'))
    if any(type(x) is not int or x < 1 for x in (owner, ticks, inode)): raise ValueError('Bad owner identity')
    state = Path('/proc/' + str(owner) + '/stat').read_text().rsplit(')', 1)[1].split()
    if state[0] in ('Z', 'X') or int(state[19]) != ticks: raise ValueError('Owner exited/PID reused')
    lock = Path(value['lock_path'])
    if lock != ROOT.parent.parent / 'exclusive.work.lock' or any(x.is_symlink() for x in [lock, *lock.parents]):
        raise ValueError('Wrong physical work lock')
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_ino != inode: raise ValueError('Work-lock inode changed')
        identity = (os.major(st.st_dev), os.minor(st.st_dev), inode); active = False
        for line in Path('/proc/locks').read_text().splitlines():
            parts = line.split()
            if len(parts) < 8 or parts[1:4] != ['FLOCK', 'ADVISORY', 'WRITE'] or parts[4] != str(owner): continue
            major, minor, ino = parts[5].split(':')
            if (int(major, 16), int(minor, 16), int(ino)) == identity: active = True
        if not active: raise ValueError('Exact owner lacks kernel FLOCK')
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        fcntl.flock(fd, fcntl.LOCK_UN); raise ValueError('Exclusive lock contender acquired')
    finally: os.close(fd)


def verify_admission(path, plan_sha, phase):
    path = Path(path).absolute()
    if path != STUDY / 'NATIVE_ADMISSION.json' or path.is_symlink(): raise ValueError('Exact late admission required')
    value = read(path)
    if (any(value.get(k) is not True for k in ('checks_passed', 'independent_remote_readback_passed', 'exclusive_lock_held'))
            or value.get('plan_sha256') != plan_sha): raise ValueError('Late source/lock admission failed')
    proof = checked(value['readback_path'])
    if sha(proof) != value['independent_readback_sha256']: raise ValueError('Readback proof changed')
    remote = read(proof)
    if remote.get('independent_remote_readback_passed') is not True or remote.get('commit') != value['source_commit']:
        raise ValueError('Exact actual published source required')
    verify_owner_lock(value)
    if phase == 'confirmation':
        adm = read(STUDY / 'CONFIRMATION_ADMISSION.json')
        if (adm.get('checks_passed') is not True or adm.get('independent_DEV_accepted') is not True
                or adm.get('runtime_gate_passed') is not True or adm.get('plan_sha256') != plan_sha):
            raise ValueError('Independent DEV/runtime confirmation gate required')
        report = checked(adm['independent_DEV_report_path'])
        if sha(report) != adm['independent_DEV_report_sha256']: raise ValueError('DEV gate receipt changed')
    elif phase != 'dev': raise ValueError('Unknown phase')
    return value
