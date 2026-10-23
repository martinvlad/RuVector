"""Verify/copy/explicitly download six exact public model assets; never infer."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import urllib.parse
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
REPO = 'microsoft/deberta-v2-xlarge-mnli'
REVISION = '2b65bccdedcead4bc685988bcc30153d4922a789'
PREFIX = 'experiments/sota-2026-10-22/candidate/epoch17/assets/official-deberta-v2-xlarge-mnli/'
MEMBERS = {'.gitattributes', 'README.md', 'config.json', 'tokenizer_config.json', 'spm.model', 'pytorch_model.bin'}
SPEC_SHA256 = '5f3a0538b71cb3691200b88996d56a4800e4b3f81caa43b290c56f6cbeb422f2'


def parts(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or PurePosixPath(value).is_absolute()
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe relative asset path')
    return PurePosixPath(value).parts


def directory(path):
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


def parent(root_fd, relative, create=False):
    names = parts(relative)
    fd = os.dup(root_fd)
    try:
        for name in names[:-1]:
            if create:
                try:
                    os.mkdir(name, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd, names[-1]
    except BaseException:
        os.close(fd)
        raise


def regular(root_fd, relative):
    fd, name = parent(root_fd, relative)
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise ValueError('Asset must be a regular file')
        return os.fdopen(file_fd, 'rb')
    finally:
        os.close(fd)


def identity(stream, item, output=None):
    count = 0
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        count += len(block)
        if count > item['bytes']:
            raise ValueError('Asset exceeds exact pinned length')
        digest.update(block)
        if output is not None:
            output.write(block)
    if count != item['bytes'] or digest.hexdigest() != item['sha256']:
        raise ValueError('Asset length/SHA256 mismatch')


def verify(root_fd, relative, item):
    with regular(root_fd, relative) as stream:
        if os.fstat(stream.fileno()).st_size != item['bytes']:
            raise ValueError('Asset length mismatch')
        identity(stream, item)


def validate_spec(spec):
    if spec.get('repo') != REPO or spec.get('revision') != REVISION or len(spec.get('assets', [])) != 6:
        raise ValueError('Exactly six assets from the selected immutable model are required')
    seen = set()
    for item in spec['assets']:
        name = item['remote_path']
        parts(name)
        if name not in MEMBERS or name in seen or item['path'] != PREFIX + name:
            raise ValueError('Unexpected or duplicate asset path')
        seen.add(name)
        if item['url'] != f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}':
            raise ValueError('Only the immutable official model URLs are permitted')
        if type(item['bytes']) is not int or not 0 < item['bytes'] < 2_000_000_000 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid exact asset identity')


def load_spec(path=HERE / 'model-assets.lock.json'):
    path = Path(path).absolute()
    fd = directory(path.parent)
    try:
        with regular(fd, path.name) as stream:
            raw = stream.read(100_001)
    finally:
        os.close(fd)
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise ValueError('Pinned six-asset specification changed')
    value = json.loads(raw)
    validate_spec(value)
    return value


def admit(root_fd, item, source):
    fd, name = parent(root_fd, item['path'], create=True)
    temporary = '.asset-' + uuid.uuid4().hex
    try:
        out_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        with os.fdopen(out_fd, 'wb') as stream:
            identity(source, item, stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        except FileExistsError:
            # A concurrently created target is never replaced.
            verify(root_fd, item['path'], item)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)


def acquire(destination, spec, cache_dir=None, download=False, verify_only=False):
    validate_spec(spec)
    if sum((cache_dir is not None, bool(download), bool(verify_only))) != 1:
        raise ValueError('Choose exactly one cache copy, explicit download, or verify-only mode')
    root_fd = directory(destination)
    cache_fd = None
    statuses = {}
    try:
        if cache_dir is not None:
            cache_fd = directory(cache_dir)
        # All destination and local-cache checks finish before any write/network.
        for item in spec['assets']:
            try:
                verify(root_fd, item['path'], item)
                statuses[item['path']] = 'VERIFIED_EXISTING'
            except FileNotFoundError:
                if verify_only:
                    raise ValueError('Missing exact asset: ' + item['path'])
                statuses[item['path']] = 'MISSING'
            if cache_fd is not None:
                verify(cache_fd, item['remote_path'], item)
        requests = 0
        copied = 0
        for item in spec['assets']:
            if statuses[item['path']] != 'MISSING':
                continue
            if cache_fd is not None:
                with regular(cache_fd, item['remote_path']) as stream:
                    admit(root_fd, item, stream)
                statuses[item['path']] = 'COPIED_VERIFIED_CACHE'
                copied += 1
            else:
                request = urllib.request.Request(item['url'], headers={'User-Agent': 'RuVector exact public asset restore'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    if urllib.parse.urlsplit(response.url).scheme != 'https':
                        raise ValueError('Official asset download redirected outside HTTPS')
                    admit(root_fd, item, response)
                statuses[item['path']] = 'DOWNLOADED_VERIFIED'
                requests += 1
        for item in spec['assets']:
            verify(root_fd, item['path'], item)
    finally:
        os.close(root_fd)
        if cache_fd is not None:
            os.close(cache_fd)
    return {'status': 'SIX_EXACT_ASSETS_VERIFIED', 'repo': REPO, 'revision': REVISION,
            'files': [{'path': item['path'], 'bytes': item['bytes'], 'sha256': item['sha256'],
                       'status': statuses[item['path']]} for item in spec['assets']],
            'network_requests': requests, 'cache_files_copied': copied,
            'model_initializations': 0, 'model_calls': 0, 'native_calls': 0, 'installs': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, required=True, help='Existing reconstructed project root')
    parser.add_argument('--manifest', type=Path, default=HERE / 'model-assets.lock.json')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--cache-dir', type=Path, help='Regular model directory with config.json and pytorch_model.bin')
    mode.add_argument('--download', action='store_true', help='Opt in to only the six immutable public HTTPS assets')
    mode.add_argument('--verify-only', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    result = acquire(args.dest, load_spec(args.manifest), args.cache_dir, args.download, args.verify_only)
    encoded = (json.dumps(result, indent=2) + '\n').encode()
    if args.receipt:
        with args.receipt.open('xb') as stream:
            stream.write(encoded)
    print(json.dumps({'status': result['status'], 'files': len(result['files']),
                      'network_requests': result['network_requests'],
                      'cache_files_copied': result['cache_files_copied'],
                      'receipt_sha256': hashlib.sha256(encoded).hexdigest(), 'model_native_calls': 0}))


if __name__ == '__main__':
    main()
