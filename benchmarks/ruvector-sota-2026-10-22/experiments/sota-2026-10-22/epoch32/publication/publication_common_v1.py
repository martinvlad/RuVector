"""Pure local publication guards shared by the epoch32 control/stage CLIs.

This module never installs packages, contacts services, starts workers, reads
benchmark annotations, or changes project files. Only the four public epoch32
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
BASE_COMMIT = 'f8bcbc4ca7ec31c6732159cad60a6e223f93c539'
BASE_CP_SHA256 = '8662d03427f700179d3684f6afed91eb0f3e5c0fcf5a703178b1e20a325cc339'
OLD_CP_ROWS = 4350
OWNER_PIN = (91138, 20058000, 13626)
OWNER_RUN_ID = 'epoch32-f8bcbc4ca7ec'
OWNER_GENERATION = 1
OWNER_EXPIRES_UNIX = 1792887678.0829117
OWNER_SCOPE_DIR = Path('/tmp/ruvector-sota-2026-10-22') / OWNER_RUN_ID
WORK_SCOPE_DIR = Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec')
OWNER_LOCK = OWNER_SCOPE_DIR.parent / 'exclusive.work.lock'
ROOTS = tuple(P + p for p in ('candidate/epoch32', 'audit/epoch32',
                              'legal-transfer/epoch32', 'epoch32'))
CONTROLS = {'ACTIVE_RUN.json', 'CHECKPOINT_MANIFEST.json', 'CONTINUATION.json'}
TRANSPORT_KEYS = {'format', 'archive', 'extractor', 'restored_artifact',
                  'publication_helper', 'required_before_bootstrap',
                  'standalone_Git_leaf_omitted'}
EXTENSIONS = {'.py', '.js', '.mjs', '.cjs', '.json', '.jsonl', '.md', '.txt',
              '.log', '.csv', '.tsv', '.yaml', '.yml', '.stdout', '.stderr'}
FAIRSEQ_LICENSE_PATH = P + 'candidate/epoch32/reader/LICENSE.fairseq'
FAIRSEQ_LICENSE_BYTES = 1086
FAIRSEQ_LICENSE_SHA256 = '52412d7bc7ce4157ea628bbaacb8829e0a9cb3c58f57f99176126bc8cf2bfc85'
BANNED = {'assets', '__pycache__', '.git', '.cache', 'cache', 'venv', '.venv',
          'node_modules', 'site-packages', 'credentials', 'secrets', 'private',
          'raw-pages', 'raw-email', 'inbox', 'mailbox', 'messages', 'models', 'weights'}
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


def loads(data):
    def unique(pairs):
        answer = {}
        for key, value in pairs:
            require(key not in answer, 'Duplicate JSON object key')
            answer[key] = value
        return answer
    def nonfinite(value):
        raise ValueError('Nonfinite JSON number refused')
    value = json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)
    def finite_tree(item):
        if isinstance(item, float): require(math.isfinite(item), 'Nonfinite JSON number refused')
        elif isinstance(item, dict):
            for child in item.values(): finite_tree(child)
        elif isinstance(item, list):
            for child in item: finite_tree(child)
    finite_tree(value)
    return value


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
    return loads(content(path))


def public_path(path):
    parts = PurePosixPath(relative(path)).parts
    require(not any(p.lower() in BANNED or '.private' in p.lower()
                    or p.lower().startswith('.env') for p in parts),
            'Private/model/cache directory refused: ' + path)
    require(Path(path).suffix in EXTENSIONS or path == FAIRSEQ_LICENSE_PATH,
            'Unreviewed public extension: ' + path)


def public_text(path, data):
    public_path(path)
    require(not path.endswith('/trained-parameters.public.json'), 'No new trained parameter or base-weight payload is allowed in E32')
    text = data.decode('utf-8', errors='strict')
    require('\0' not in text and not any(ord(c) < 32 and c not in '\t\r\n'
            for c in text), 'Binary/control payload refused: ' + path)
    require(not any(p.search(text) for p in PRIVATE_PATTERNS),
            'Credential/raw mail/raw page refused: ' + path)
    if path == FAIRSEQ_LICENSE_PATH:
        require(len(data) == FAIRSEQ_LICENSE_BYTES and sha(data) == FAIRSEQ_LICENSE_SHA256,
                'Exact official fairseq MIT licence bytes required')
    return text


def walk_current(project, allow_empty=False):
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
    require(found or allow_empty, 'No public epoch32 files selected')
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


def check_inherited_checkpoint(cp):
    rows = cp_rows(cp)
    require(len(rows) == OLD_CP_ROWS, 'Pinned inherited4350 CP identities required')
    require(not any(any(path == root or path.startswith(root + '/') for root in ROOTS)
                    for path in rows), 'Inherited checkpoint already contains epoch32')
    return rows


def check_transport(project, old_cont, new_cont, rows, git_paths=None, kit=None):
    """Preserve three historical CP-only originals, without a new transport.

    Epoch22's seven-key contract and epoch26's manifest/descriptors are frozen
    inherited evidence. Their original source commit is not this study's source
    commit. Root bootstrap sources are Git/KIT files, not historical CP members.
    """
    def checked(row, label, cp_required=True):
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
                'Canonical inherited transport reference required: ' + label)
        relative(row['path'])
        require(type(row['bytes']) is int and row['bytes'] >= 0
                and isinstance(row['sha256'], str)
                and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                'Invalid inherited transport identity: ' + label)
        base = project if cp_required else kit
        require(base is not None and ref(base, row['path']) == row,
                'Actual inherited transport bytes changed: ' + label)
        if cp_required:
            require(rows.get(row['path']) == row,
                    'Inherited transport/CP identity changed: ' + label)

    def descriptor(item, label, keys):
        require(isinstance(item, dict) and set(item) == keys
                and item.get('format') == 'gzip+base64'
                and item.get('required_before_bootstrap') is True,
                'Inherited transport descriptor changed: ' + label)
        for key in ('archive', 'extractor', 'publication_helper', 'restored_artifact'):
            checked(item[key], label + '/' + key)
        raw = item['restored_artifact']['path']
        require(item['standalone_Git_leaf_omitted'] == raw,
                'Inherited omitted-leaf identity changed: ' + label)
        if git_paths is not None:
            require(raw not in git_paths, 'Archived original must never be a Git payload')
            require(all(item[key]['path'] in git_paths for key in
                        ('archive', 'extractor', 'publication_helper')),
                    'Inherited reconstruction Git sources missing')
        return raw

    transport = old_cont.get('artifact_transport')
    require(isinstance(transport, dict) and set(transport) == TRANSPORT_KEYS
            and new_cont.get('artifact_transport') == transport,
            'Inherited exact seven-key artifact transport changed')
    omitted = [descriptor(transport, 'epoch22', TRANSPORT_KEYS)]
    bundle = old_cont.get('epoch26_artifact_transports')
    require(isinstance(bundle, dict) and set(bundle) == {'manifest', 'descriptors'}
            and new_cont.get('epoch26_artifact_transports') == bundle
            and isinstance(bundle['descriptors'], list) and len(bundle['descriptors']) == 2,
            'Inherited epoch26 manifest/descriptors changed')
    checked(bundle['manifest'], 'epoch26 manifest')
    manifest = parse(project / bundle['manifest']['path'])
    require(isinstance(manifest, dict)
            and set(manifest) == {'schema_version', 'epoch', 'format', 'source_commit', 'descriptors'}
            and type(manifest['schema_version']) is int and manifest['schema_version'] == 1
            and type(manifest['epoch']) is int and manifest['epoch'] == 26
            and manifest['format'] == 'gzip+base64'
            and manifest['source_commit'] == '00d49880e0b6a7dc2aea8cb155d64549f423c782'
            and manifest['descriptors'] == bundle['descriptors'],
            'Inherited epoch26 manifest identity differs from continuation')
    for number, item in enumerate(bundle['descriptors']):
        omitted.append(descriptor(item, 'epoch26/' + str(number), TRANSPORT_KEYS | {'source_commit'}))
        require(item['source_commit'] == manifest['source_commit'],
                'Inherited epoch26 source identity changed')
    expected_omissions = {P+'epoch22/runs/dev/raw.json',
        P+'epoch26/runs/dev/raw.json', P+'epoch26/runs/dev/native-result.json'}
    require(len(omitted) == 3 and set(omitted) == expected_omissions,
            'Exactly the three inherited CP-only originals are required')
    restore = old_cont.get('epoch26_restore')
    require(isinstance(restore, dict) and new_cont.get('epoch26_restore') == restore
            and set(restore) == {'manifest', 'extractor', 'run_after_inherited_epoch22_restore',
                'must_run_before_bootstrap', 'original_bootstrap', 'original_restore', 'instructions'}
            and restore['manifest'] == bundle['manifest']
            and restore['run_after_inherited_epoch22_restore'] is True
            and restore['must_run_before_bootstrap'] is True
            and isinstance(restore['instructions'], str) and bool(restore['instructions'])
            and all(restore['extractor'] == item['extractor'] for item in bundle['descriptors']),
            'Inherited epoch26 restoration contract changed')
    checked(restore['extractor'], 'epoch26 restore extractor')
    for key, path in [('original_bootstrap', 'bootstrap.py'),
                      ('original_restore', 'restore_checkpoint.py')]:
        require(isinstance(restore[key], dict) and restore[key].get('path') == path,
                'Inherited root restore source changed')
        checked(restore[key], key, cp_required=False)
    if git_paths is not None:
        require(bundle['manifest']['path'] in git_paths
                and {'bootstrap.py', 'restore_checkpoint.py'} <= git_paths,
                'Inherited manifest/bootstrap/restore Git sources missing')
    return copy.deepcopy({'artifact_transport': transport,
        'epoch26_artifact_transports': bundle, 'epoch26_restore': restore,
        'CP_only_artifacts': sorted(omitted)})


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


def check_owner_identity(owner, scope):
    require(Path(scope) == OWNER_SCOPE_DIR
            and owner.get('run_id') == OWNER_RUN_ID
            and type(owner.get('generation')) is int
            and owner['generation'] == OWNER_GENERATION
            and owner.get('scope') == 'ruvnet/RuVector:' + SCOPE.rstrip('/')
            and owner.get('lock') == str(OWNER_LOCK)
            and owner.get('expires_unix') == OWNER_EXPIRES_UNIX,
            'Owner scope/generation/original expiry changed')
    require(all(type(owner.get(key)) is int for key in ('pid','startticks','lock_inode'))
            and (owner['pid'],owner['startticks'],owner['lock_inode']) == OWNER_PIN,
            'Owner differs from the pinned epoch32 guardian generation')
    return owner


def live_owner(scope):
    workspace = directory(scope)
    require(workspace == WORK_SCOPE_DIR, 'Exact E32 workspace required')
    scope = directory(OWNER_SCOPE_DIR)
    owner = check_owner_identity(parse(scope / 'owner.json'), scope)
    pid = owner['pid']; ticks = owner['startticks']
    require((pid, ticks, owner.get('lock_inode')) == OWNER_PIN,
            'Owner differs from the pinned epoch32 guardian generation')
    require(type(pid) is int and pid > 0 and type(ticks) is int
            and time.time() < owner['expires_unix']
            and not (scope / 'release.request').exists(), 'Expired/released owner')
    status = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
    require(status[0] not in ('Z', 'X') and int(status[19]) == ticks,
            'Owner PID/startticks not live')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == '4632fb06-b0ef-4df5-b72b-0e875bbad810'
            and os.readlink('/proc/' + str(pid) + '/ns/pid') == 'pid:[4026532200]',
            'Owner boot/PID namespace changed')
    require(owner['CPU_affinity'] in ([0, 1], 2)
            and os.sched_getaffinity(pid) == {0, 1}, 'Owner CPU2 affinity changed')
    path = canonical(owner['lock']); fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_ino == owner['lock_inode'] and st.st_dev == 33,
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

