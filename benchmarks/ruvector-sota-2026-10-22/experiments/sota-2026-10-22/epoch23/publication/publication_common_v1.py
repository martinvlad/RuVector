"""Pure local publication guards shared by the epoch23 control/stage CLIs.

This module never installs packages, contacts services, starts workers, reads
benchmark annotations, or changes project files. Only the four public epoch23
roots are collected. Historical checkpoint bytes and the inherited archive
exception remain mandatory; neither an allowlist nor a new control can erase
published history.
"""
from __future__ import annotations
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

P = 'experiments/sota-2026-10-22/'
SCOPE = 'benchmarks/ruvector-sota-2026-10-22/'
ROOTS = tuple(P + p for p in ('candidate/epoch23', 'audit/epoch23',
                              'legal-transfer/epoch23', 'epoch23'))
CONTROLS = {'ACTIVE_RUN.json', 'CHECKPOINT_MANIFEST.json', 'CONTINUATION.json'}
TRANSPORT_KEYS = {'format', 'archive', 'extractor', 'restored_artifact',
                  'publication_helper', 'required_before_bootstrap',
                  'standalone_Git_leaf_omitted'}
EXTENSIONS = {'.py', '.js', '.mjs', '.cjs', '.json', '.jsonl', '.md', '.txt',
              '.log', '.csv', '.tsv', '.yaml', '.yml', '.stdout', '.stderr'}
BANNED = {'assets', '__pycache__', '.git', '.cache', 'cache', 'venv', '.venv',
          'node_modules', 'site-packages', 'credentials', 'secrets', 'private',
          'raw-pages', 'raw-email', 'inbox', 'mailbox', 'messages'}
PRIVATE_PATTERNS = tuple(re.compile(p, re.I | re.M) for p in (
    r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
    r'\bgithub_pat_[A-Za-z0-9_]{30,}\b', r'\bAKIA[0-9A-Z]{16}\b',
    r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b',
    r'\b(?:authorization|proxy-authorization)\s*[:=]\s*[\x22\x27]?(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]{20,}',
    r'^[ \t]*(?:Received:|DKIM-Signature:|Return-Path:|MIME-Version:)',
    r'<(?:!DOCTYPE\s+html|html|head|body)(?:\s|>)'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value, pretty=False):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       **({'indent': 2} if pretty else {'separators': (',', ':')}))
            + ('\n' if pretty else '')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gitsha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value
            and not PurePosixPath(value).is_absolute()
            and not any(p in ('', '.', '..') for p in value.split('/')),
            'Unsafe relative publication path')
    return value


def canonical(path):
    path = Path(path).absolute()
    require(path == path.resolve() and not any(p.is_symlink() for p in
            (path, *path.parents)), 'Noncanonical/symlink path refused: ' + str(path))
    return path


def directory(path):
    path = canonical(path)
    require(path.is_dir(), 'Required directory absent: ' + str(path))
    return path


def content(path):
    path = canonical(path)
    require(stat.S_ISREG(path.lstat().st_mode), 'Nonregular source: ' + str(path))
    return path.read_bytes()


def parse(path):
    return json.loads(content(path).decode('utf-8'))


def public_path(path):
    parts = PurePosixPath(relative(path)).parts
    require(not any(p.lower() in BANNED or '.private' in p.lower()
                    or p.lower().startswith('.env') for p in parts),
            'Private/model/cache directory refused: ' + path)
    require(Path(path).suffix in EXTENSIONS, 'Unreviewed public extension: ' + path)


def public_text(path, data):
    public_path(path)
    text = data.decode('utf-8', errors='strict')
    require('\0' not in text and not any(ord(c) < 32 and c not in '\t\r\n'
            for c in text), 'Binary/control payload refused: ' + path)
    require(not any(p.search(text) for p in PRIVATE_PATTERNS),
            'Credential/raw mail/raw page refused: ' + path)
    return text


def walk_current(project):
    found = {}
    for rel in ROOTS:
        root = canonical(project / rel)
        if not root.exists():
            continue
        directory(root)
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs.sort(); files.sort()
            for name in dirs:
                d = directory(Path(base) / name)
                require(not any(p.lower() in BANNED or p.lower().startswith('.env')
                                for p in d.relative_to(project).parts),
                        'Excluded runtime/private directory in public root')
            for name in files:
                file = Path(base) / name
                name = file.relative_to(project).as_posix()
                public_path(name)
                data = content(file); public_text(name, data)
                require(name not in found, 'Duplicate current path')
                found[name] = data
    require(found, 'No public epoch23 files selected')
    return found


def ref(project, path):
    path = relative(path); data = content(project / path)
    return {'path': path, 'bytes': len(data), 'sha256': sha(data)}


def cp_rows(value):
    require(isinstance(value, dict) and isinstance(value.get('project_files'), list),
            'Checkpoint project_files required')
    rows = {}
    for row in value['project_files']:
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
                'Checkpoint row must be canonical path/bytes/SHA256')
        path = relative(row['path'])
        require(type(row['bytes']) is int and row['bytes'] >= 0
                and re.fullmatch('[0-9a-f]{64}', row['sha256'] or '')
                and path not in rows, 'Invalid/duplicate checkpoint identity')
        rows[path] = copy.deepcopy(row)
    return rows


def check_history(project, cp):
    rows = cp_rows(cp)
    for path, row in rows.items():
        require(ref(project, path) == row, 'Historical project bytes changed: ' + path)
    return rows


def check_transport(project, old_cont, new_cont, rows, git_paths=None):
    transport = old_cont.get('artifact_transport')
    require(isinstance(transport, dict) and set(transport) == TRANSPORT_KEYS
            and new_cont.get('artifact_transport') == transport,
            'Inherited exact seven-key artifact transport changed')
    require(transport['format'] == 'gzip+base64'
            and transport['required_before_bootstrap'] is True,
            'Inherited archive must precede bootstrap')
    raw = transport['restored_artifact']
    require(transport['standalone_Git_leaf_omitted'] == raw['path'],
            'Only the inherited raw artifact may lack a Git leaf')
    for key in ('archive', 'extractor', 'publication_helper', 'restored_artifact'):
        row = transport[key]
        require(set(row) == {'path', 'bytes', 'sha256'} and rows.get(row['path']) == row
                and ref(project, row['path']) == row, 'Archive/CP identity changed: ' + key)
    if git_paths is not None:
        require(raw['path'] not in git_paths, 'Archived raw must never be a Git payload')
        require(all(transport[k]['path'] in git_paths for k in
                    ('archive', 'extractor', 'publication_helper')),
                'Published reconstruction sources missing')
    return copy.deepcopy(transport)


def new_output(path, forbidden):
    out = canonical(path)
    directory(out.parent)
    require(not os.path.lexists(out), 'Output must be an exclusive new path')
    require(not any(out.is_relative_to(p) or p.is_relative_to(out) for p in forbidden),
            'Output must be outside project/kit/input control trees')
    return out


def write(path, data):
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def live_owner(scope):
    owner = parse(scope / 'owner.json')
    pid = owner['pid']; ticks = owner['startticks']
    require(type(pid) is int and pid > 0 and type(ticks) is int
            and time.time() < owner['expires_unix']
            and not (scope / 'release.request').exists(), 'Expired/released owner')
    status = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
    require(status[0] not in ('Z', 'X') and int(status[19]) == ticks,
            'Owner PID/startticks not live')
    require(owner['CPU_affinity'] == [0, 1]
            and os.sched_getaffinity(pid) == {0, 1}, 'Owner CPU2 affinity changed')
    path = canonical(owner['lock']); fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_ino == owner['lock_inode'],
                'Scoped lock inode changed')
        identity = (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)
        held = False
        for line in Path('/proc/locks').read_text().splitlines():
            parts = line.split()
            if (len(parts) >= 8 and parts[1:4] == ['FLOCK', 'ADVISORY', 'WRITE']
                    and parts[4] == str(pid)):
                a, b, c = parts[5].split(':')
                held |= (int(a, 16), int(b, 16), int(c)) == identity
        require(held, 'Exact owned FLOCK absent')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            raise ValueError('Independent contender acquired lock; STOP')
    finally:
        os.close(fd)
    return owner


ZERO_COUNTERS = ('NLI_model_initializations', 'NLI_forward_pairs_attempted',
    'NLI_forward_pairs_completed', 'benchmark_corpora', 'benchmark_questions',
    'benchmark_HTTP_requests', 'TRAIN_calibration_fits', 'CONF_worker_attempts',
    'CONF_annotation_choices', 'CONF_NLI_pairs', 'paid_API_calls', 'GPU_calls',
    'NLI_forwards', 'fits', 'paid_calls', 'Python_network_operations_attempted',
    'confirmation_calls')
COUNT_COUNTERS = ('worker_attempts', 'verified_worker_starts', 'BGE_initializations',
    'BGE_forwards', 'BGE_texts', 'native_index_initializations',
    'native_searches_completed', 'native_engineering_batches', 'errors')
FINAL_ZERO_ALLOWANCES = ('publication_period_native_calls_allowed',
    'new_study_attempts_remaining', 'new_study_unspent_phase_slots',
    'allowed_further_attempts_in_closed_study',
    'conditional_DEV_after_exact_remote_readback',
    'conditional_CONF_after_independent_DEV_runtime_gates')


def check_final_manifest(manifest, expected_queries=17):
    require(manifest.get('epoch') == 23 and manifest.get('kind') == 'SOURCE_SCOPE_ENGINEERING'
            and manifest.get('all_slots_closed') is True
            and manifest.get('champion_promoted') is False
            and manifest.get('new_submission') is False
            and manifest.get('benchmark_accepted') is False
            and type(manifest.get('engineering_qualified')) is bool,
            'Final engineering status/promotion scope invalid')
    actual = manifest['actual_execution']
    require(type(expected_queries) is int and expected_queries > 0,
            'Frozen native query count required')
    for key in COUNT_COUNTERS:
        require(type(actual.get(key)) is int and actual[key] >= 0,
                'Missing/invalid explicit actual counter: ' + key)
    for key in ZERO_COUNTERS:
        require(type(actual.get(key)) is int and actual[key] == 0,
                'Missing/nonzero forbidden counter: ' + key)
    attempts = actual['worker_attempts']
    require(type(attempts) is int and 0 <= attempts <= 1
            and actual.get('owned_live_processes_closed') is True,
            'Final attempt cap or owned-process closure invalid')
    require(actual['verified_worker_starts'] <= attempts
            and actual['native_index_initializations'] <= expected_queries
            and actual['native_searches_completed'] <= expected_queries
            and actual['native_engineering_batches'] <= 1,
            'Actual execution exceeds the frozen engineering allowance')
    wall = actual.get('wall_seconds_including_init_cleanup')
    require(actual.get('CPU_affinity') == [0, 1]
            and all(type(x) is int for x in actual['CPU_affinity'])
            and type(wall) in (int, float) and math.isfinite(wall) and 0 <= wall <= 600,
            'CPU2/whole-worker600s resource admission differs')
    if manifest['engineering_qualified']:
        require(attempts == actual['verified_worker_starts'] == actual['BGE_initializations'] == 1
                and actual['BGE_forwards'] > 0 and actual['BGE_texts'] > 0
                and actual['native_index_initializations'] == expected_queries
                and actual['native_searches_completed'] == expected_queries
                and actual['native_engineering_batches'] == 1 and actual['errors'] == 0,
                'Qualified run lacks exact frozen native+BGE execution')
    require(manifest.get('data_roles') == {'train': [], 'dev': [], 'calibration': [],
                                         'confirmation': []}, 'No benchmark role may be used')
    for key, value in actual.items():
        forbidden = (key.startswith(('CONF_', 'NLI_')) or any(part in key.lower()
                     for part in ('fit', 'paid', 'gpu', 'benchmark_http')))
        if forbidden and not isinstance(value, str):
            require(type(value) is int and value == 0, 'Forbidden inference/spend: ' + key)
    return attempts


def final_ledger(old, manifest, project):
    updates = manifest.get('cumulative_budget_ledger')
    if updates is None:
        updates = parse(project / (P + 'epoch23/cumulative-ledger.final.json'))
    require(isinstance(updates, dict), 'Explicit cumulative ledger updates required')
    required = set(FINAL_ZERO_ALLOWANCES) | {'current_epoch_closed', 'scope',
                                            'epoch23_closed_qualification'}
    require(required <= set(updates), 'Explicit current closed-ledger fields missing')
    ledger = copy.deepcopy(old)
    for key, value in updates.items():
        historical = (isinstance(old.get(key), (dict, list))
            or re.search(r'(?:^|_)epoch(?:[1-9]|1[0-9]|2[0-2])(?:_|$)', key)
            or key in ('cumulative_native_attempts', 'total_historical_attempts',
                       'cumulative_corpus_attempts_current')
            or key.startswith('cumulative_corpus_attempts_preserved'))
        if historical and key in old:
            require(old[key] == value, 'Historical closed/corpus budget changed: ' + key)
        ledger[key] = copy.deepcopy(value)
    for key in FINAL_ZERO_ALLOWANCES:
        require(type(ledger.get(key)) is int and ledger[key] == 0,
                'Final current allowance not closed: ' + key)
    require(ledger.get('current_epoch_closed') is True
            and ledger.get('scope') == 'ALL_EPOCHS_CLOSED_THROUGH23',
            'Final current epoch ledger scope is not closed')
    q = ledger['epoch23_closed_qualification']; actual = manifest['actual_execution']
    require(isinstance(q, dict) and type(q.get('used')) is int
            and q['used'] == actual['worker_attempts']
            and type(q.get('cap')) is int and q['cap'] == 1
            and type(q.get('allowed_further')) is int and q['allowed_further'] == 0
            and type(q.get('benchmark_corpora')) is int and q['benchmark_corpora'] == 0,
            'Closed qualification usage/cap/allowance differs')
    require(all(actual[key] == value for key, value in q.items() if key in actual),
            'Closed qualification actual counters differ')
    for key in ('cumulative_qualification_attempts',
                'cumulative_native_process_attempts_including_qualification'):
        require(type(old.get(key)) is int and type(ledger.get(key)) is int
                and ledger[key] == old[key] + actual['worker_attempts'],
                'Cumulative qualification/process attempt increment differs: ' + key)
    return ledger


def check_ledger_history(old, new):
    require(isinstance(old, dict) and isinstance(new, dict), 'Rejection ledgers required')
    for key, value in old.items():
        require(key in new, 'Historical ledger key dropped: ' + key)
        if key in ('rejections', 'preparation_blocks'):
            require(isinstance(new[key], list) and new[key][:len(value)] == value,
                    'Historical ledger sequence changed: ' + key)
        elif key not in ('next_research_priority', 'used_identity_manifest'):
            require(new[key] == value, 'Historical ledger record changed: ' + key)
