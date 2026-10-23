"""Encode only the exact sealed DEV raw artifact for the Git blob API limit."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat

PREFIX = 'experiments/sota-2026-10-22/epoch22/'
RAW_PATH = PREFIX + 'runs/dev/raw.json'
ARCHIVE_PATH = PREFIX + 'publication/actualarchive.dev.raw.v1.json'
RAW_BYTES = 21631719
RAW_SHA256 = '2b012e1595bdb9b3bb1e5dacc242e9136a189638704f3a55229fe4d828cd0414'
RAW_GIT_SHA1 = '113b883813afc968e1dd24732f2f70be992d4cfa'
LIMIT = 8 * 1024 * 1024
REQUEST_METADATA_RESERVE = 4096


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encoded_request_sizes(archive):
    request = {'content': base64.b64encode(archive).decode('ascii'), 'encoding': 'base64'}
    body_size = len(json.dumps(request, separators=(',', ':'), allow_nan=False).encode('utf-8'))
    return {'base64_content_encoding_JSON_bytes': body_size,
            'request_metadata_reserve_bytes': REQUEST_METADATA_RESERVE,
            'Git_API_JSON_request_bound_bytes': body_size + REQUEST_METADATA_RESERVE,
            'request_limit_bytes': LIMIT}


def encode(raw):
    git_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if len(raw) != RAW_BYTES or sha256(raw) != RAW_SHA256 or git_sha != RAW_GIT_SHA1:
        raise ValueError('Only the exact sealed raw bytes may be archived')
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    compressed = buffer.getvalue()
    if len(compressed) > LIMIT:
        raise ValueError('Compressed member exceeds limit')
    envelope = {'schema_version': 1, 'epoch': 22, 'format': 'gzip+base64',
                'artifact': {'path': RAW_PATH, 'bytes': RAW_BYTES, 'sha256': RAW_SHA256,
                             'git_blob_sha1': RAW_GIT_SHA1},
                'gzip': {'bytes': len(compressed), 'sha256': sha256(compressed), 'mtime': 0},
                'payload_base64': base64.b64encode(compressed).decode('ascii')}
    archive = (json.dumps(envelope, ensure_ascii=False, indent=2,
                          sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    sizes = encoded_request_sizes(archive)
    if len(archive) >= LIMIT or sizes['Git_API_JSON_request_bound_bytes'] >= LIMIT:
        raise ValueError('Archive or bounded Git API JSON request exceeds 8 MiB')
    return archive, envelope, sizes


def build(project_root):
    root = Path(project_root)
    if not root.is_absolute() or root != root.resolve() or not root.is_dir():
        raise ValueError('Canonical absolute project root required')
    for relative in [RAW_PATH, ARCHIVE_PATH]:
        path = root / relative
        for component in [path, *path.parents]:
            if component.exists() or component.is_symlink():
                if stat.S_ISLNK(component.lstat().st_mode):
                    raise ValueError('Symlinks are forbidden')
    source = root / RAW_PATH
    with source.open('rb') as stream:
        raw = stream.read(RAW_BYTES + 1)
    archive, envelope, sizes = encode(raw)
    output = root / ARCHIVE_PATH
    with output.open('xb') as stream:
        stream.write(archive)
        stream.flush()
        os.fsync(stream.fileno())
    return {'schema_version': 1, 'epoch': 22,
            'archive': {'path': ARCHIVE_PATH, 'bytes': len(archive), 'sha256': sha256(archive)},
            'artifact': envelope['artifact'], 'gzip': envelope['gzip'],
            'Git_API_request': sizes, 'CPU_affinity': sorted(os.sched_getaffinity(0)),
            'opaque_bytes_only': True, 'model_native_tokenizer_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True)
    arguments = parser.parse_args()
    os.sched_setaffinity(0, {0, 1})
    print(json.dumps(build(arguments.project_root), sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
