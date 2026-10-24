"""Restore exactly two immutable epoch26 diagnostic artifacts before bootstrap.

Strict local byte transport only: no archived code, runtime, model, Git or network.
The original CP identities remain authoritative; the scientific rejection stands.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zlib

P = 'experiments/sota-2026-10-22/epoch26/'
SOURCE_COMMIT = '00d49880e0b6a7dc2aea8cb155d64549f423c782'
EXTRACTOR_PATH = P + 'publication/restore_epoch26_archives_v1.py'
HELPER_PATH = P + 'publication/prepare_epoch26_archives_v1.py'
MANIFEST_PATH = P + 'publication/archive-transport.v1.json'
LIMIT = 8384512
META_LIMIT = 4 * 1024 * 1024
SPECS = (
    {'path': P + 'runs/dev/raw.json', 'bytes': 22784264,
     'sha256': '0e35f4d7c49baefbfaeb40d37d23579782551228315ea928e20f17e68e6fac28',
     'git_blob_sha1': 'fa6286f4be64fab60cef1195654d6eb7393beea8'},
    {'path': P + 'runs/dev/native-result.json', 'bytes': 9541777,
     'sha256': 'e0c5475d8a93a01975230c3c416825a9a9e697a9abee9f55476b08f98371ddcc',
     'git_blob_sha1': 'a21c72dd21806c358db5f3124679923f0db0d77c'},
)
ARCHIVES = (P + 'publication/archives/actualarchive.dev.raw.v1.json',
            P + 'publication/archives/actualarchive.dev.native-result.v1.json')
DESCRIPTOR_KEYS = {'format', 'archive', 'extractor', 'restored_artifact',
                   'publication_helper', 'required_before_bootstrap',
                   'standalone_Git_leaf_omitted', 'source_commit'}
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


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gitsha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('Nonfinite JSON constant')
    value = json.loads(data.decode('utf-8', errors='strict'),
                       object_pairs_hook=unique, parse_constant=nonfinite)
    def finite(item):
        if isinstance(item, float):
            require(math.isfinite(item), 'Nonfinite JSON number')
        elif isinstance(item, dict):
            for child in item.values(): finite(child)
        elif isinstance(item, list):
            for child in item: finite(child)
    finite(value)
    return value


def public_original(data):
    text = data.decode('utf-8', errors='strict')
    require('\0' not in text and not any(ord(c) < 32 and c not in '\t\r\n' for c in text),
            'Binary/control payload refused')
    require(not any(pattern.search(text) for pattern in PRIVATE_PATTERNS),
            'Credential/raw mail/raw page refused')
    strict_json(data)


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value,
            'Canonical relative POSIX path required')
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and not any(part in ('', '.', '..') for part in value.split('/')),
            'Path traversal/noncanonical path refused')
    return path


def root_path(value):
    root = Path(value)
    require(root.is_absolute() and root == root.resolve() and root.is_dir(),
            'Absolute canonical existing kit root required')
    require(not any(path.is_symlink() for path in (root, *root.parents)),
            'Symlink in root refused')
    return root


def safe_path(root, value, *, missing=False):
    parts = relative(value).parts
    for number in range(len(parts) + 1):
        path = root.joinpath(*parts[:number])
        try: mode = path.lstat().st_mode
        except FileNotFoundError:
            require(missing, 'Required path absent')
            continue
        require(not stat.S_ISLNK(mode), 'Symlink refused')
        if number < len(parts):
            require(stat.S_ISDIR(mode), 'Nondirectory ancestor refused')
    return root.joinpath(*parts)


def read(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Regular file required')
        data = stream.read(limit + 1)
    require(len(data) <= limit, 'Bounded read exceeded')
    return data


def ref(data, path):
    return {'path': path, 'bytes': len(data), 'sha256': sha(data)}


def validate_ref(value):
    require(isinstance(value, dict) and set(value) == {'path', 'bytes', 'sha256'},
            'Canonical three-key reference required')
    relative(value['path'])
    require(type(value['bytes']) is int and value['bytes'] >= 0
            and isinstance(value['sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Invalid reference identity')
    return value


def original_ref(spec):
    return {key: spec[key] for key in ('path', 'bytes', 'sha256')}


def compressed_member(compressed, expected_bytes):
    require(18 <= len(compressed) < LIMIT and compressed[:4] == b'\x1f\x8b\x08\x00'
            and compressed[4:8] == b'\0' * 4 and compressed[8:10] == b'\x02\xff',
            'Single canonical gzip member mtime0 without options and OS255 required')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try: output = decoder.decompress(compressed, expected_bytes + 1)
    except zlib.error as error: raise ValueError('Invalid gzip member') from error
    require(len(output) == expected_bytes and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail, 'Gzip expansion/EOF/trailing-member mismatch')
    return output


def decode_envelope(data, expected_spec):
    require(len(data) < LIMIT and expected_spec in SPECS, 'Archive/path outside exact allowlist')
    value = strict_json(data)
    require(isinstance(value, dict) and set(value) == {
        'schema_version', 'epoch', 'source_commit', 'format', 'artifact', 'gzip', 'payload_base64'},
        'Archive envelope fields differ')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['epoch']) is int and value['epoch'] == 26
            and value['source_commit'] == SOURCE_COMMIT and value['format'] == 'gzip+base64'
            and value['artifact'] == expected_spec, 'Frozen artifact metadata changed')
    member = value['gzip']
    require(isinstance(member, dict) and set(member) == {'bytes', 'sha256', 'mtime'}
            and type(member['bytes']) is int and 18 <= member['bytes'] < LIMIT
            and type(member['mtime']) is int and member['mtime'] == 0
            and isinstance(member['sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', member['sha256']), 'Gzip metadata invalid')
    payload = value['payload_base64']
    require(isinstance(payload, str) and len(payload) < LIMIT, 'Base64 payload bound exceeded')
    try: compressed = base64.b64decode(payload.encode('ascii'), validate=True)
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise ValueError('Strict ASCII base64 required') from error
    require(base64.b64encode(compressed).decode('ascii') == payload
            and len(compressed) == member['bytes'] and sha(compressed) == member['sha256'],
            'Compressed identity mismatch')
    output = compressed_member(compressed, expected_spec['bytes'])
    require(ref(output, expected_spec['path']) == original_ref(expected_spec)
            and gitsha(output) == expected_spec['git_blob_sha1'], 'Decoded original identity differs')
    public_original(output)
    return output


def validate_manifest(value):
    require(isinstance(value, dict) and set(value) == {
        'schema_version', 'epoch', 'source_commit', 'format', 'descriptors'},
        'Transport manifest fields differ')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['epoch']) is int and value['epoch'] == 26
            and value['source_commit'] == SOURCE_COMMIT and value['format'] == 'gzip+base64'
            and isinstance(value['descriptors'], list) and len(value['descriptors']) == 2,
            'Exact epoch26 source and two transports required')
    for descriptor, spec, archive in zip(value['descriptors'], SPECS, ARCHIVES):
        require(isinstance(descriptor, dict) and set(descriptor) == DESCRIPTOR_KEYS,
                'Transport descriptor fields differ')
        require(descriptor['format'] == 'gzip+base64' and descriptor['source_commit'] == SOURCE_COMMIT
                and descriptor['required_before_bootstrap'] is True
                and descriptor['standalone_Git_leaf_omitted'] == spec['path']
                and descriptor['restored_artifact'] == original_ref(spec),
                'Transport frozen original identity differs')
        for key, path in [('archive', archive), ('extractor', EXTRACTOR_PATH),
                          ('publication_helper', HELPER_PATH), ('restored_artifact', spec['path'])]:
            require(validate_ref(descriptor[key])['path'] == path, 'Transport path outside allowlist')
    return value


def restore(kit_root, *, manifest_relative=None, expected_manifest_sha256=None, verify_only=False):
    root = root_path(kit_root)
    cp_data = read(safe_path(root, 'CHECKPOINT_MANIFEST.json'), META_LIMIT)
    checkpoint = strict_json(cp_data)
    require(isinstance(checkpoint, dict) and isinstance(checkpoint.get('project_files'), list),
            'Checkpoint project_files required')
    indexed = {}
    for row in checkpoint['project_files']:
        validate_ref(row)
        require(row['path'] not in indexed, 'Duplicate CP path')
        indexed[row['path']] = row
    continuation_path = safe_path(root, 'CONTINUATION.json', missing=True)
    continuation = None
    if continuation_path.exists():
        continuation = strict_json(read(continuation_path, META_LIMIT))
        require(continuation.get('checkpoint_manifest_sha256') == sha(cp_data), 'CONT CP hash differs')
    if manifest_relative is None:
        require(isinstance(continuation, dict), 'CONT transport or explicit manifest hash required')
        transport = continuation.get('epoch26_artifact_transports')
        require(isinstance(transport, dict) and set(transport) == {'manifest', 'descriptors'},
                'New epoch26 namespace required; inherited transport is untouched')
        manifest_reference = validate_ref(transport['manifest'])
        manifest_relative = manifest_reference['path']
        expected_manifest_sha256 = manifest_reference['sha256']
    else:
        require(isinstance(expected_manifest_sha256, str)
                and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256),
                'Explicit expected manifest SHA256 required')
        transport = None
    require(manifest_relative == MANIFEST_PATH, 'Only exact epoch26 manifest is permitted')
    manifest_data = read(safe_path(root, manifest_relative), META_LIMIT)
    manifest_reference = ref(manifest_data, manifest_relative)
    require(manifest_reference['sha256'] == expected_manifest_sha256
            and indexed.get(manifest_relative) == manifest_reference, 'Manifest CP/argument pin differs')
    manifest = validate_manifest(strict_json(manifest_data))
    if transport is not None:
        require(transport == {'manifest': manifest_reference, 'descriptors': manifest['descriptors']},
                'CONT manifest/descriptors differ')
    require(Path(__file__).absolute() == safe_path(root, EXTRACTOR_PATH),
            'Run the CP-pinned extractor inside this kit')
    outputs = []
    # Validate every archive, helper, extractor and original CP row before writes.
    for descriptor, spec in zip(manifest['descriptors'], SPECS):
        require(indexed.get(spec['path']) == original_ref(spec), 'Original CP identity changed')
        for key in ('archive', 'extractor', 'publication_helper'):
            item = descriptor[key]
            data = read(safe_path(root, item['path']), LIMIT if key == 'archive' else META_LIMIT)
            require(ref(data, item['path']) == item and indexed.get(item['path']) == item,
                    'Archive/extractor/helper manifest or CP hash differs')
        data = read(safe_path(root, descriptor['archive']['path']), LIMIT)
        output = decode_envelope(data, spec)
        target = safe_path(root, spec['path'], missing=True)
        if target.exists():
            existing = read(target, spec['bytes'])
            require(verify_only and existing == output,
                    'Existing artifact refused; use verify-only for an exact matching file')
        outputs.append((spec, output, target))
    # Prove all other CP files before creating either original artifact.
    original_paths = {spec['path'] for spec in SPECS}
    for path, item in indexed.items():
        if path not in original_paths:
            data = read(safe_path(root, path), item['bytes'])
            require(ref(data, path) == item, 'Full checkpoint source hash differs: ' + path)
    statuses = []
    for spec, output, target in outputs:
        if verify_only:
            status = 'VERIFIED_EXISTING' if target.exists() else 'VERIFIED_ARCHIVE_ONLY'
        else:
            current = root
            for part in relative(spec['path']).parts[:-1]:
                current /= part
                try: current.mkdir()
                except FileExistsError: pass
                require(not current.is_symlink() and current.is_dir(), 'Unsafe destination ancestor')
            safe_path(root, spec['path'], missing=True)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(output); stream.flush(); os.fsync(stream.fileno())
            status = 'RESTORED_EXCLUSIVE'
        statuses.append({'artifact': original_ref(spec), 'status': status})
    # Full CP byte proof after reconstruction, before the unchanged bootstrap.
    # In archive-only verification the two absent outputs are proven in memory.
    in_memory = {spec['path']: output for spec, output, _ in outputs}
    for path, item in indexed.items():
        target = safe_path(root, path, missing=verify_only and path in in_memory)
        data = in_memory[path] if not target.exists() and path in in_memory else read(target, item['bytes'])
        require(ref(data, path) == item, 'Full checkpoint restoration hash differs: ' + path)
    return {'schema_version': 1, 'epoch': 26, 'source_commit': SOURCE_COMMIT,
            'manifest': manifest_reference, 'artifacts': statuses,
            'checkpoint_manifest_sha256': sha(cp_data), 'checkpoint_files_verified': len(indexed),
            'required_before_bootstrap': True, 'run_unchanged_bootstrap_and_restore_next': True,
            'verify_only': verify_only, 'model_native_tokenizer_Git_network_calls': 0,
            'scientific_acceptance_changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-root', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--expected-manifest-sha256')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(restore(args.kit_root, manifest_relative=args.manifest,
                            expected_manifest_sha256=args.expected_manifest_sha256,
                            verify_only=args.verify_only), sort_keys=True))


if __name__ == '__main__':
    main()
