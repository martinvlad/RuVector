"""Exact epoch26 archive transport checks; no scientific or runtime admission.

Only the two already measured originals named below may omit standalone Git
leaves. Both remain full checkpoint rows and are checked as public UTF8 JSON.
"""
from __future__ import annotations
import base64
from pathlib import Path
import zlib
from publication_common_v1 import (P, content, cp_rows, encoded, gitsha, loads,
    public_text, ref, relative, require, sha)

E = P+'epoch26/'
SOURCE_COMMIT = '00d49880e0b6a7dc2aea8cb155d64549f423c782'
BASE_STAGE_SHA256 = '903e42323b03c1da1ce5ca6af329025c588b8b9fdbba45ec5b237c3569da6ba0'
BASE_COMMON_SHA256 = '68e674a9e48f8acb5186c2f41d161bc5d744e424c54dde674cd408c7c60e1c52'
SOURCE_CP_ROWS = 3611
MANIFEST_PATH = E+'publication/archive-transport.v1.json'
EXTRACTOR_PATH = E+'publication/restore_epoch26_archives_v1.py'
HELPER_PATH = E+'publication/prepare_epoch26_archives_v1.py'
SPECS = {
    E+'runs/dev/raw.json': {'bytes': 22784264,
        'sha256': '0e35f4d7c49baefbfaeb40d37d23579782551228315ea928e20f17e68e6fac28',
        'git_blob_sha1': 'fa6286f4be64fab60cef1195654d6eb7393beea8',
        'archive': E+'publication/archives/actualarchive.dev.raw.v1.json'},
    E+'runs/dev/native-result.json': {'bytes': 9541777,
        'sha256': 'e0c5475d8a93a01975230c3c416825a9a9e697a9abee9f55476b08f98371ddcc',
        'git_blob_sha1': 'a21c72dd21806c358db5f3124679923f0db0d77c',
        'archive': E+'publication/archives/actualarchive.dev.native-result.v1.json'}
}
BOOTSTRAP_SHA256 = 'eceb2ca259feaf642bc81172aca57a2a209cc34cd17f9b281861c51f21b95806'
RESTORE_SHA256 = 'affd9ecf660f380c3632f78cd14fb7a36e00797ceb097cf48c0c60136fac0be8'
DESCRIPTOR_KEYS = {'format', 'archive', 'extractor', 'restored_artifact',
    'publication_helper', 'required_before_bootstrap', 'standalone_Git_leaf_omitted', 'source_commit'}
MAX_BLOB_JSON = 8384512


def checked_ref(project, row, checkpoint, expected_path):
    require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
            'Archive transport canonical reference required')
    require(type(row['bytes']) is int and row['bytes'] >= 0
            and relative(row['path']) == expected_path and checkpoint.get(expected_path) == row
            and ref(project, expected_path) == row, 'Archive transport source/CP identity differs')
    return row


def frozen_base_unchanged():
    here = Path(__file__).resolve().parent
    require(sha(content(here/'stage_publication_v1.py')) == BASE_STAGE_SHA256
            and sha(content(here/'publication_common_v1.py')) == BASE_COMMON_SHA256,
            'Frozen publication guard source changed')


def decode_archive(path, archive_body, original_path, original_body):
    """One canonical base64 string, one bounded gzip member, exact original."""
    require(original_path in SPECS and path == SPECS[original_path]['archive'],
            'Archive may name only exact two measured epoch26 originals')
    spec = SPECS[original_path]
    expected = {'path': original_path, 'bytes': spec['bytes'],
        'sha256': spec['sha256'], 'git_blob_sha1': spec['git_blob_sha1']}
    require(type(spec['bytes']) is int and 0 < spec['bytes'] <= 22784264,
            'Decoded archive bound exceeds exact measured maximum')
    original_text = public_text(original_path, original_body)
    loads(original_text)
    require(len(original_body) == spec['bytes'] and sha(original_body) == spec['sha256']
            and gitsha(original_body) == spec['git_blob_sha1'], 'Measured original identity changed')
    archive_text = public_text(path, archive_body)
    require(len(encoded({'content': archive_text, 'encoding': 'utf-8'})) < MAX_BLOB_JSON,
            'Archive does not fit exact JSON API transport cap')
    envelope = loads(archive_body)
    require(isinstance(envelope, dict) and set(envelope) == {'schema_version', 'epoch',
            'source_commit', 'format', 'artifact', 'gzip', 'payload_base64'}
            and type(envelope['schema_version']) is int and envelope['schema_version'] == 1
            and type(envelope['epoch']) is int and envelope['epoch'] == 26
            and envelope['source_commit'] == SOURCE_COMMIT
            and envelope['format'] == 'gzip+base64'
            and isinstance(envelope['artifact'], dict)
            and type(envelope['artifact'].get('bytes')) is int
            and envelope['artifact'] == expected, 'Archive envelope identity/namespace changed')
    packed = envelope['gzip']; payload = envelope['payload_base64']
    require(isinstance(packed, dict) and set(packed) == {'bytes', 'sha256', 'mtime'}
            and type(packed['bytes']) is int and packed['bytes'] > 0
            and type(packed['mtime']) is int and packed['mtime'] == 0
            and isinstance(payload, str), 'Gzip metadata must be exact and deterministic')
    try:
        compressed = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid strict archive base64') from error
    require(base64.b64encode(compressed).decode('ascii') == payload
            and len(compressed) == packed['bytes'] and sha(compressed) == packed['sha256']
            and len(compressed) >= 18 and compressed[:3] == b'\x1f\x8b\x08'
            and compressed[3] == 0 and compressed[4:8] == b'\0\0\0\0'
            and compressed[8:10] == b'\x02\xff', 'Compressed archive identity/header differs')
    try:
        decoder = zlib.decompressobj(16+zlib.MAX_WBITS)
        decoded = decoder.decompress(compressed, spec['bytes']+1)
    except zlib.error as error:
        raise ValueError('Invalid gzip member') from error
    require(len(decoded) <= spec['bytes'] and decoder.eof
            and not decoder.unconsumed_tail and not decoder.unused_data,
            'Gzip decoded oversize/incomplete/trailing/member data refused')
    require(decoded == original_body and len(decoded) == expected['bytes']
            and sha(decoded) == expected['sha256'] and gitsha(decoded) == expected['git_blob_sha1'],
            'Decoded original does not roundtrip exactly')
    public_text(original_path, decoded)
    return expected


def checked_restore(kit, value, manifest_ref, extractor_ref):
    require(isinstance(value, dict) and set(value) == {'manifest', 'extractor',
        'run_after_inherited_epoch22_restore', 'must_run_before_bootstrap',
        'original_bootstrap', 'original_restore', 'instructions'}
        and value['manifest'] == manifest_ref and value['extractor'] == extractor_ref
        and value['run_after_inherited_epoch22_restore'] is True
        and value['must_run_before_bootstrap'] is True
        and isinstance(value['instructions'], str) and value['instructions'].strip(),
        'Restore order must be old22, both epoch26 originals, unchanged bootstrap/restore')
    for key, path, expected_sha in [('original_bootstrap', 'bootstrap.py', BOOTSTRAP_SHA256),
                                  ('original_restore', 'restore_checkpoint.py', RESTORE_SHA256)]:
        row = value[key]
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'}
                and type(row['bytes']) is int and row['bytes'] >= 0
                and row == ref(kit, path) and row['sha256'] == expected_sha,
                'Original KIT bootstrap/restore identity changed')


def archive_omissions(project, kit, current, checkpoint, cont, parent, plan, frozen, prior_rows):
    frozen_base_unchanged()
    require(parent == SOURCE_COMMIT and len(prior_rows) == SOURCE_CP_ROWS
            and not set(SPECS).intersection(prior_rows), 'Archive adapter must extend exact frozen source')
    wrapper = cont.get('epoch26_artifact_transports')
    require(isinstance(wrapper, dict) and set(wrapper) == {'manifest', 'descriptors'},
            'Exact namespaced archive manifest/descriptors wrapper required')
    checked_ref(project, wrapper['manifest'], checkpoint, MANIFEST_PATH)
    manifest = loads(current[MANIFEST_PATH])
    require(isinstance(manifest, dict) and set(manifest) == {'schema_version', 'epoch',
        'source_commit', 'format', 'descriptors'} and manifest['schema_version'] == 1
        and type(manifest['schema_version']) is int and type(manifest['epoch']) is int
        and manifest['epoch'] == 26 and manifest['source_commit'] == SOURCE_COMMIT
        and manifest['format'] == 'gzip+base64' and manifest['descriptors'] == wrapper['descriptors'],
        'Archive manifest differs from exact continuation descriptors')
    descriptors = manifest['descriptors']
    require(isinstance(descriptors, list) and len(descriptors) == 2, 'Exactly two archive descriptors required')
    omitted = set()
    for descriptor in descriptors:
        require(isinstance(descriptor, dict) and set(descriptor) == DESCRIPTOR_KEYS
                and descriptor['format'] == 'gzip+base64'
                and descriptor['source_commit'] == SOURCE_COMMIT
                and descriptor['required_before_bootstrap'] is True, 'Archive descriptor contract differs')
        original = descriptor['restored_artifact']
        require(isinstance(original, dict), 'Original artifact reference required')
        path = original.get('path')
        require(path in SPECS and path not in omitted
                and descriptor['standalone_Git_leaf_omitted'] == path,
                'Only exact two unique measured originals may omit Git leaves')
        require(path in current, 'Omitted original must remain fully selected and privacy checked')
        checked_ref(project, original, checkpoint, path)
        checked_ref(project, descriptor['archive'], checkpoint, SPECS[path]['archive'])
        checked_ref(project, descriptor['extractor'], checkpoint, EXTRACTOR_PATH)
        checked_ref(project, descriptor['publication_helper'], checkpoint, HELPER_PATH)
        require(all(row['path'] in current for row in (descriptor['archive'], descriptor['extractor'], descriptor['publication_helper'])),
                'Every archive and reconstruction helper must be published')
        decode_archive(SPECS[path]['archive'], current[SPECS[path]['archive']], path, current[path])
        omitted.add(path)
    require(omitted == set(SPECS), 'No additional or missing epoch26 Git omissions allowed')
    checked_restore(kit, cont.get('epoch26_restore'), wrapper['manifest'], descriptors[0]['extractor'])
    raw = loads(current[E+'runs/dev/raw.json']); native = loads(current[E+'runs/dev/native-result.json'])
    execution = loads(current[E+'execution.json'])
    require(raw.get('plan_sha256') == frozen['plan']['sha256']
            and raw.get('source_freeze_sha256') == frozen['source_freeze']['sha256']
            and raw.get('source_checkpoint') == plan.get('source_checkpoint'), 'Raw changed frozen source identity')
    require(execution.get('raw_sha256') == SPECS[E+'runs/dev/raw.json']['sha256']
            and execution.get('raw_bytes') == SPECS[E+'runs/dev/raw.json']['bytes'],
            'Outer execution does not bind exact archived raw')
    require(native.get('epoch') == 26 and native.get('native') is True
            and native.get('stage') == 'HELPER_COMPLETED'
            and native.get('native_index_initializations_completed') == 8
            and native.get('native_queries_completed') == 24
            and native.get('Node_network_operations_attempted') == 0
            and native.get('network_violations') == [], 'Native archived result differs from actual completed retrieval')
    bundle = E+'runs/dev/native-bundle.json'
    require(bundle in current and native.get('bundle_sha256') == sha(current[bundle]),
            'Native result/bundle identity differs; bundle cannot be omitted')
    manifest = loads(current[E+'EPOCH_MANIFEST.json'])
    require(manifest.get('diagnostic_qualified') is False
            and manifest.get('benchmark_accepted') is False
            and manifest.get('champion_promoted') is False and manifest.get('new_submission') is False
            and 'REJECTED' in manifest.get('status', '').upper(),
            'This transport adapter may publish only the exact rejected candidate evidence')
    return omitted


def publication_items(current, bodies, omitted):
    require(omitted == set(SPECS), 'Exact two-path omission set required')
    require(omitted <= set(current) and not omitted.intersection(bodies), 'Omitted originals must remain CP-only current inputs')
    return {path: body for path, body in {**current, **bodies}.items() if path not in omitted}
