"""Offline materialization of the pinned core8 + TypeSafe14 runtime closure.

No download, install, package import, subprocess, model initialization or forward.
Only exact regular files from explicitly supplied cache roots are accepted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

HERE = Path(__file__).resolve().parent
SPEC_PINS = {
    'official-package-closure.json': '3efc9666b549da8f70a22b0fca285dca68112f6835c767d08fd7f5946fc31726',
    'typesafe-runtime-closure.json': '363bb39e63fd6fb212a0aed25974443f5a286ca5eaff867314f3daad5fbe0718',
    'runtime-manifest.json': 'fc507f1f04a067112415d548f32aac5c24ee02c7d81ae79768ffaea1ccd3fbb7',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parts(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid relative path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('Path traversal or alias refused')
    return path.parts


def open_directory(path):
    """Walk every absolute ancestor with directory handles and O_NOFOLLOW."""
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('Parent traversal refused')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(root_fd, item):
    path_parts = parts(item['path'])
    fd = os.dup(root_fd)
    try:
        for part in path_parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        file_fd = os.open(path_parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != item['bytes']:
                raise ValueError('Expected exact regular-file length: ' + item['path'])
            raw = stream.read(item['bytes'] + 1)
        if len(raw) != item['bytes'] or digest(raw) != item['sha256']:
            raise ValueError('File SHA256 mismatch: ' + item['path'])
        return raw
    finally:
        os.close(fd)


def load_specs(directory=HERE):
    values = {}
    directory_fd = open_directory(directory)
    try:
        for name, expected in SPEC_PINS.items():
            file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            with os.fdopen(file_fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('Specification must be regular')
                raw = stream.read(100_001)
            if digest(raw) != expected:
                raise ValueError('Pinned specification changed: ' + name)
            values[name] = json.loads(raw)
    finally:
        os.close(directory_fd)
    core = values['official-package-closure.json']
    typesafe = values['typesafe-runtime-closure.json']
    runtime = values['runtime-manifest.json']
    core_files = [item for package in core['packages'] for item in package['files']]
    type_files = typesafe['files']
    if len(core_files) != 8 or len(type_files) != 14:
        raise ValueError('Expected exact core8 and TypeSafe14 closures')
    if [(p['package'], p['version']) for p in core['packages']] != [('@ruvector/core', '0.1.33'), ('ruvector-core-linux-x64-gnu', '0.1.31')]:
        raise ValueError('Unexpected core package identities')
    if runtime['package'] != '@ruvector/typesafe' or runtime['package_version'] != '0.2.0':
        raise ValueError('Unexpected TypeSafe package identity')
    seen = set()
    for group, rows in (('core', core_files), ('typesafe', type_files)):
        for item in rows:
            parts(item['path'])
            prefix = 'retrieval/node_modules/' if group == 'core' else 'node_modules/@ruvector/typesafe/'
            if not item['path'].startswith(prefix) or item['path'] in seen:
                raise ValueError('Unexpected closure path')
            seen.add(item['path'])
            if type(item['bytes']) is not int or item['bytes'] < 1 or len(item['sha256']) != 64:
                raise ValueError('Invalid closure identity')
    binary_path = 'node_modules/@ruvector/typesafe/native/linux-x64-gnu/typesafe.linux-x64-gnu.node'
    binary = next(item for item in type_files if item['path'] == binary_path)
    if binary['sha256'] != runtime['native_binary_sha256'] or binary['sha256'] != typesafe['binary_receipt_required']:
        raise ValueError('TypeSafe binary and runtime receipt disagree')
    return {'core': core_files, 'typesafe': type_files}


def target_status(root_fd, item):
    """Return exact-existing or missing; links/nonregular/mismatches fail closed."""
    try:
        read_file(root_fd, item)
    except FileNotFoundError:
        return 'missing'
    return 'exact-existing'


def write_new(root_fd, item, raw):
    path_parts = parts(item['path'])
    fd = os.dup(root_fd)
    try:
        for part in path_parts[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        out_fd = os.open(path_parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        with os.fdopen(out_fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def materialize(project_root, groups, cache_roots=None, verify_only=False):
    """Generic tested file transaction. Specifications are pinned by the CLI."""
    root = Path(project_root).absolute()
    root_fd = open_directory(root)
    cache_fds = {}
    payloads, statuses = {}, {}
    try:
        # Verify the entire destination and source closure before any write.
        for group, rows in groups.items():
            if not verify_only:
                if not cache_roots or group not in cache_roots:
                    raise ValueError('An explicit cache root is required for each closure')
                cache_fds[group] = open_directory(cache_roots[group])
            for item in rows:
                parts(item['path'])
                if item['path'] in statuses:
                    raise ValueError('Duplicate target path')
                statuses[item['path']] = target_status(root_fd, item)
                if verify_only and statuses[item['path']] != 'exact-existing':
                    raise ValueError('Missing destination file: ' + item['path'])
                if not verify_only:
                    payloads[item['path']] = read_file(cache_fds[group], item)
        for rows in groups.values():
            for item in rows:
                if statuses[item['path']] == 'missing':
                    write_new(root_fd, item, payloads[item['path']])
        for rows in groups.values():
            for item in rows:
                read_file(root_fd, item)
    finally:
        os.close(root_fd)
        for fd in cache_fds.values():
            os.close(fd)
    return {'schema_version': 1, 'status': 'EXACT_RUNTIME_CLOSURE_VERIFIED',
            'project_root': str(root), 'verify_only': verify_only,
            'counts': {name: len(rows) for name, rows in groups.items()},
            'created': sum(value == 'missing' for value in statuses.values()),
            'reused_exact': sum(value == 'exact-existing' for value in statuses.values()),
            'files': [dict(item) for rows in groups.values() for item in rows],
            'specification_sha256': SPEC_PINS,
            'native_addon_loads': 0, 'model_initializations': 0, 'forwards': 0,
            'downloads': 0, 'installs': 0,
            'scope': 'Exact regular-file identity and isolated materialization only; no execution or ABI-compatibility claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--core-cache-root', type=Path)
    parser.add_argument('--typesafe-cache-root', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    groups = load_specs()
    if args.verify_only:
        if args.core_cache_root or args.typesafe_cache_root:
            parser.error('Verify-only takes no cache roots')
        caches = None
    else:
        if not args.core_cache_root or not args.typesafe_cache_root:
            parser.error('Materialization requires both explicit cache roots')
        caches = {'core': args.core_cache_root, 'typesafe': args.typesafe_cache_root}
    result = materialize(args.project_root, groups, caches, args.verify_only)
    encoded = (json.dumps(result, indent=2) + '\n').encode()
    if args.receipt:
        with args.receipt.open('xb') as stream:
            stream.write(encoded)
    print(json.dumps({'status': result['status'], 'counts': result['counts'],
                      'created': result['created'], 'reused_exact': result['reused_exact'],
                      'receipt_sha256': digest(encoded), 'native_model_calls': 0}))


if __name__ == '__main__':
    main()
