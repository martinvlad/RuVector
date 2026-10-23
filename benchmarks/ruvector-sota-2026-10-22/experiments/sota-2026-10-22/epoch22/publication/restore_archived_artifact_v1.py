"""Restore only the pinned epoch22 DEV trace, before the unchanged bootstrap.

Archive contents are opaque bytes. No archived code, hooks, or model is run.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zlib

PREFIX = 'experiments/sota-2026-10-22/epoch22/'
ARCHIVE_PATH = PREFIX + 'publication/actualarchive.dev.raw.v1.json'
EXTRACTOR_PATH = PREFIX + 'publication/restore_archived_artifact_v1.py'
PUBLICATION_HELPER_PATH = PREFIX + 'publication/prepare_publication_archive_v1.py'
RAW_PATH = PREFIX + 'runs/dev/raw.json'
RAW_BYTES = 21631719
RAW_SHA256 = '2b012e1595bdb9b3bb1e5dacc242e9136a189638704f3a55229fe4d828cd0414'
RAW_GIT_SHA1 = '113b883813afc968e1dd24732f2f70be992d4cfa'
LIMIT = 8 * 1024 * 1024
METADATA_LIMIT = 2 * 1024 * 1024
RAW_REF = {'path': RAW_PATH, 'bytes': RAW_BYTES, 'sha256': RAW_SHA256}
ARTIFACT = {**RAW_REF, 'git_blob_sha1': RAW_GIT_SHA1}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_sha1(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON member')
        result[key] = value
    return result


def strict_json(data):
    def invalid_constant(_):
        raise ValueError('Nonfinite JSON value')
    return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                      parse_constant=invalid_constant)


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Canonical relative POSIX path required')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in {'.', '..'} for p in path.parts):
        raise ValueError('Unsafe relative path')
    return path


def safe_path(root, relative, *, allow_missing=False):
    parts = relative_path(relative).parts
    target = root.joinpath(*parts)
    for path in [root, *[root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)]]:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            if allow_missing:
                continue
            raise ValueError('Required path is absent') from None
        if stat.S_ISLNK(mode):
            raise ValueError('Symlinks are forbidden')
        if path != target and not stat.S_ISDIR(mode):
            raise ValueError('Parent is not a directory')
    return target


def canonical_root(value):
    root = Path(value)
    if not root.is_absolute() or root != root.resolve():
        raise ValueError('Absolute canonical kit root required')
    for path in [root, *root.parents]:
        if stat.S_ISLNK(path.lstat().st_mode):
            raise ValueError('Symlink in kit root')
    if not root.is_dir():
        raise ValueError('Kit root must be a directory')
    return root


def read_bounded(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Regular file required')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('File exceeds bounded read')
    return data


def file_ref(path, relative, limit):
    data = read_bounded(path, limit)
    return data, {'path': relative, 'bytes': len(data), 'sha256': sha256(data)}


def validate_ref(ref):
    if not isinstance(ref, dict) or set(ref) != {'path', 'bytes', 'sha256'}:
        raise ValueError('Exact file reference required')
    relative_path(ref['path'])
    if type(ref['bytes']) is not int or ref['bytes'] < 0:
        raise ValueError('Invalid reference size')
    if not isinstance(ref['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', ref['sha256']):
        raise ValueError('Invalid reference hash')
    return ref


def decompress_bounded(compressed, expected_bytes):
    if len(compressed) > LIMIT or len(compressed) < 18:
        raise ValueError('Compressed size outside limit')
    if compressed[:4] != b'\x1f\x8b\x08\x00' or compressed[4:8] != b'\0' * 4:
        raise ValueError('One gzip member with mtime zero and no optional fields required')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        output = decoder.decompress(compressed, expected_bytes + 1)
    except zlib.error as error:
        raise ValueError('Invalid gzip member') from error
    if (len(output) != expected_bytes or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail):
        raise ValueError('Bounded gzip size, EOF, or trailing-member mismatch')
    return output


def decode_envelope(data):
    if len(data) > LIMIT:
        raise ValueError('Archive exceeds limit')
    envelope = strict_json(data)
    if (not isinstance(envelope, dict) or set(envelope) != {
            'schema_version', 'epoch', 'format', 'artifact', 'gzip', 'payload_base64'}
            or type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
            or type(envelope['epoch']) is not int or envelope['epoch'] != 22
            or envelope['format'] != 'gzip+base64' or envelope['artifact'] != ARTIFACT):
        raise ValueError('Only the exact sealed DEV artifact is supported')
    member = envelope['gzip']
    if (not isinstance(member, dict) or set(member) != {'bytes', 'sha256', 'mtime'}
            or type(member['bytes']) is not int or not 18 <= member['bytes'] <= LIMIT
            or type(member['mtime']) is not int or member['mtime'] != 0
            or not isinstance(member['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', member['sha256'])):
        raise ValueError('Invalid gzip metadata')
    payload = envelope['payload_base64']
    if not isinstance(payload, str) or len(payload) > 4 * ((LIMIT + 2) // 3):
        raise ValueError('Invalid base64 payload size')
    try:
        compressed = base64.b64decode(payload.encode('ascii'), validate=True)
    except (ValueError, UnicodeError) as error:
        raise ValueError('Strict ASCII base64 required') from error
    if (base64.b64encode(compressed).decode('ascii') != payload
            or len(compressed) != member['bytes'] or sha256(compressed) != member['sha256']):
        raise ValueError('Compressed identity mismatch')
    output = decompress_bounded(compressed, RAW_BYTES)
    if sha256(output) != RAW_SHA256 or git_sha1(output) != RAW_GIT_SHA1:
        raise ValueError('Decoded sealed raw identity mismatch')
    return envelope, output


def restore(kit_root, archive_relative, expected_archive_sha256, *, verify_only=False):
    root = canonical_root(kit_root)
    if archive_relative != ARCHIVE_PATH:
        raise ValueError('Only the exact archive path is allowed')
    if not isinstance(expected_archive_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_archive_sha256):
        raise ValueError('Expected archive SHA256 is required')
    cp_data = read_bounded(safe_path(root, 'CHECKPOINT_MANIFEST.json'), METADATA_LIMIT)
    continuation = strict_json(read_bounded(safe_path(root, 'CONTINUATION.json'), METADATA_LIMIT))
    checkpoint = strict_json(cp_data)
    if (not isinstance(checkpoint, dict) or checkpoint.get('schema_version') != 1
            or not isinstance(continuation, dict) or continuation.get('schema_version') != 1
            or continuation.get('checkpoint_manifest_sha256') != sha256(cp_data)):
        raise ValueError('CONT checkpoint manifest pin mismatch')
    rows = checkpoint.get('project_files')
    if not isinstance(rows, list):
        raise ValueError('Checkpoint project_files required')
    indexed = {}
    for row in rows:
        validate_ref(row)
        if row['path'] in indexed:
            raise ValueError('Duplicate checkpoint path')
        indexed[row['path']] = row
    if indexed.get(RAW_PATH) != RAW_REF:
        raise ValueError('Checkpoint must pin the exact original raw file')
    transport = continuation.get('artifact_transport')
    if (not isinstance(transport, dict) or set(transport) != {
            'format', 'archive', 'extractor', 'restored_artifact', 'publication_helper',
            'required_before_bootstrap', 'standalone_Git_leaf_omitted'}
            or transport['format'] != 'gzip+base64'
            or transport['required_before_bootstrap'] is not True
            or transport['restored_artifact'] != RAW_REF
            or transport['standalone_Git_leaf_omitted'] != RAW_PATH):
        raise ValueError('Exact pre-bootstrap artifact transport contract required')
    helper_ref = validate_ref(transport['publication_helper'])
    if (helper_ref['path'] != PUBLICATION_HELPER_PATH
            or indexed.get(PUBLICATION_HELPER_PATH) != helper_ref):
        raise ValueError('Publication helper CP/CONT pin mismatch')
    archive_path = safe_path(root, ARCHIVE_PATH)
    archive_data, archive_ref = file_ref(archive_path, ARCHIVE_PATH, LIMIT)
    if (archive_ref['sha256'] != expected_archive_sha256
            or indexed.get(ARCHIVE_PATH) != archive_ref or transport['archive'] != archive_ref):
        raise ValueError('Archive argument, CP, or CONT pin mismatch')
    source_path = safe_path(root, EXTRACTOR_PATH)
    if Path(__file__).absolute() != source_path:
        raise ValueError('Run the CP-pinned extractor inside this kit')
    _, source_ref = file_ref(source_path, EXTRACTOR_PATH, 256 * 1024)
    if indexed.get(EXTRACTOR_PATH) != source_ref or transport['extractor'] != source_ref:
        raise ValueError('Extractor own-source pin mismatch')
    envelope, output = decode_envelope(archive_data)
    target = safe_path(root, RAW_PATH, allow_missing=True)
    if target.exists():
        existing = read_bounded(target, RAW_BYTES)
        if existing != output:
            raise ValueError('Existing raw mismatch preserved without overwrite')
        status = 'VERIFIED_EXISTING' if verify_only else 'ALREADY_PRESENT_MATCHING'
    elif verify_only:
        status = 'VERIFIED_ARCHIVE_ONLY'
    else:
        current = root
        for part in relative_path(RAW_PATH).parts[:-1]:
            current = current / part
            try:
                current.mkdir()
            except FileExistsError:
                pass
            if stat.S_ISLNK(current.lstat().st_mode) or not current.is_dir():
                raise ValueError('Unsafe target parent')
        safe_path(root, RAW_PATH, allow_missing=True)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        status = 'RESTORED_EXCLUSIVE'
    return {'schema_version': 1, 'epoch': 22, 'status': status, 'archive': archive_ref,
            'extractor': source_ref, 'artifact': envelope['artifact'],
            'checkpoint_manifest_sha256': sha256(cp_data), 'verify_only': verify_only,
            'run_unchanged_bootstrap_and_restore_next': True, 'model_native_tokenizer_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-root', required=True)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--expected-archive-sha256', required=True)
    parser.add_argument('--verify-only', action='store_true')
    arguments = parser.parse_args()
    os.sched_setaffinity(0, {0, 1})
    result = restore(arguments.kit_root, arguments.archive,
                     arguments.expected_archive_sha256, verify_only=arguments.verify_only)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
