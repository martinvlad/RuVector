"""Create deterministic lossless transport for exactly two frozen DEV artifacts.

Only new archive/manifest bytes are written. Originals and frozen runtime source
remain unchanged. This is procedural publication work, not a model rerun or a
change to the scientific rejection. No Git, network or ML imports occur.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

P = 'experiments/sota-2026-10-22/epoch26/'
SOURCE_COMMIT = '00d49880e0b6a7dc2aea8cb155d64549f423c782'
FREEZE_SHA = 'e5b008f678eaeefd050d70ea2bad3295c893768c7b24691e66267c5f3dbdf201'
PLAN_SHA = 'db258b42015fd27b3540a022a4a58ab6737391777a87ce925e49b0d7ace3b808'
MAX_BLOB_JSON_BYTES = 8384512


def load_extractor():
    path = Path(__file__).with_name('restore_epoch26_archives_v1.py').absolute()
    if path != path.resolve() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Canonical regular extractor source required')
    spec = importlib.util.spec_from_file_location('epoch26_archive_format_v1', path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def blob_request(data):
    return json.dumps({'owner': 'ruvnet', 'repo': 'RuVector',
                       'content': data.decode('utf-8', errors='strict'),
                       'encoding': 'utf-8'}, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def canonical_gzip(data):
    # GzipFile writes OS255 on every supported Python; gzip.compress(mtime=0)
    # delegated that byte to zlib in Python3.11/12. Restoration never recompresses.
    output = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=9, mtime=0) as stream:
        stream.write(data)
    return output.getvalue()


def envelope_for(module, data, spec):
    # Audit uncompressed original text before compressing or publishing anything.
    module.public_original(data)
    module.require(module.ref(data, spec['path']) == module.original_ref(spec)
                   and module.gitsha(data) == spec['git_blob_sha1'],
                   'Actual sealed original changed')
    compressed = canonical_gzip(data)
    value = {'schema_version': 1, 'epoch': 26, 'source_commit': SOURCE_COMMIT,
             'format': 'gzip+base64', 'artifact': spec,
             'gzip': {'bytes': len(compressed), 'sha256': module.sha(compressed), 'mtime': 0},
             'payload_base64': base64.b64encode(compressed).decode('ascii')}
    encoded = module.encode(value)
    module.require(len(encoded) < MAX_BLOB_JSON_BYTES
                   and len(blob_request(encoded)) < MAX_BLOB_JSON_BYTES,
                   'Archive JSON or JSON-encoded Git blob request exceeds8MiB reserve bound')
    module.require(module.decode_envelope(encoded, spec) == data, 'Archive round-trip differs')
    return encoded


def source_proof(module, project):
    freeze_data = module.read(module.safe_path(project, P + 'source-freeze.json'), 4 * 1024 * 1024)
    plan_data = module.read(module.safe_path(project, P + 'plan.json'), 4 * 1024 * 1024)
    module.require(module.sha(freeze_data) == FREEZE_SHA and module.sha(plan_data) == PLAN_SHA,
                   'Frozen source/plan identity changed')
    freeze = module.strict_json(freeze_data)
    plan = module.strict_json(plan_data)
    module.require(plan.get('diagnostic_only') is True
                   and plan.get('champion_promotion_allowed') is False
                   and plan.get('confirmation_execution_allowed') is False
                   and plan.get('new_submission_allowed') is False
                   and plan.get('source_freeze_sha256') == FREEZE_SHA,
                   'Diagnostic evidence class/plan changed')
    entries = freeze.get('source_entries')
    module.require(isinstance(entries, list) and len(entries) == 68
                   and entries == freeze.get('entries'), 'Frozen68 source entries changed')
    seen = set()
    for item in entries:
        module.validate_ref(item)
        module.require(item['path'] not in seen, 'Duplicate frozen source path')
        seen.add(item['path'])
        data = module.read(module.safe_path(project, item['path']), item['bytes'])
        module.require(module.ref(data, item['path']) == item,
                       'Frozen source changed: ' + item['path'])
    admission = module.strict_json(module.read(
        module.safe_path(project, P + 'NATIVE_ADMISSION.json'), 4 * 1024 * 1024))
    module.require(admission.get('published_source_commit') == SOURCE_COMMIT
                   and admission.get('plan_sha256') == PLAN_SHA
                   and admission.get('source_freeze_sha256') == FREEZE_SHA,
                   'Immutable actual source commit/admission changed')
    return {'source_commit': SOURCE_COMMIT, 'source_freeze_sha256': FREEZE_SHA,
            'plan_sha256': PLAN_SHA, 'frozen_source_files_verified': len(entries) + 2}


def write_new_or_matching(module, path, data):
    if path.exists():
        module.require(module.read(path, max(len(data), 1)) == data,
                       'Existing transport bytes differ; no overwrite')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for ancestor in (path, *path.parents):
        module.require(not ancestor.is_symlink(), 'Symlink in publication output refused')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def prepare(project_root):
    module = load_extractor()
    project = module.root_path(project_root)
    module.require(Path(__file__).absolute() == module.safe_path(project, module.HELPER_PATH)
                   and module.SOURCE_COMMIT == SOURCE_COMMIT,
                   'Run the exact helper inside the actual source project')
    proof = source_proof(module, project)
    helper_data = module.read(module.safe_path(project, module.HELPER_PATH), 4 * 1024 * 1024)
    extractor_data = module.read(module.safe_path(project, module.EXTRACTOR_PATH), 4 * 1024 * 1024)
    helper_ref = module.ref(helper_data, module.HELPER_PATH)
    extractor_ref = module.ref(extractor_data, module.EXTRACTOR_PATH)
    archives, originals = [], []
    for spec, archive in zip(module.SPECS, module.ARCHIVES):
        data = module.read(module.safe_path(project, spec['path']), spec['bytes'])
        originals.append((spec, data))
        encoded = envelope_for(module, data, spec)
        archives.append((archive, encoded))
    descriptors = []
    for (archive, encoded), spec in zip(archives, module.SPECS):
        descriptors.append({'format': 'gzip+base64', 'source_commit': SOURCE_COMMIT,
            'archive': module.ref(encoded, archive), 'extractor': extractor_ref,
            'restored_artifact': module.original_ref(spec), 'publication_helper': helper_ref,
            'required_before_bootstrap': True, 'standalone_Git_leaf_omitted': spec['path']})
    value = {'schema_version': 1, 'epoch': 26, 'source_commit': SOURCE_COMMIT,
             'format': 'gzip+base64', 'descriptors': descriptors}
    module.validate_manifest(value)
    manifest_data = module.encode(value)
    for archive, encoded in archives:
        write_new_or_matching(module, module.safe_path(project, archive, missing=True), encoded)
    write_new_or_matching(module, module.safe_path(project, module.MANIFEST_PATH, missing=True), manifest_data)
    for spec, original in originals:
        module.require(module.read(module.safe_path(project, spec['path']), spec['bytes']) == original,
                       'Original bytes changed while preparing archive')
    module.require(source_proof(module, project) == proof, 'Frozen source proof changed')
    return {'schema_version': 1, 'epoch': 26, 'manifest': module.ref(manifest_data, module.MANIFEST_PATH),
            'descriptors': descriptors, 'source_proof': proof,
            'archive_blob_JSON_bytes': [len(blob_request(data)) for _, data in archives],
            'blob_JSON_exclusive_limit': MAX_BLOB_JSON_BYTES,
            'uncompressed_originals_privacy_UTF8_strictJSON_checked': True,
            'uncompressed_originals_unchanged': True,
            'scientific_acceptance_changed': False, 'model_native_tokenizer_Git_network_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    print(json.dumps(prepare(parser.parse_args().project), sort_keys=True))


if __name__ == '__main__':
    main()
