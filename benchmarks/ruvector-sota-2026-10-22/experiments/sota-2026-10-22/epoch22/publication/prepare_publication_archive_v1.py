"""Final-only lossless archive exception around the unchanged reviewed V1 helper.

Contract: V1 checks every project file, CP row, source tuple and reviewed byte.
Only the exact, never-published DEV raw artifact loses its standalone Git leaf.
Its CP row remains, and exact archive/extractor/self references must be present
in CONTINUATION.artifact_transport before an outside temporary V1 stage runs.
Rebuild transport from that checked stage, preserve every prior source leaf,
and bound each blob request below8MiB (with4KiB metadata reserve), trees190k.
No Git/network calls, runtime/model imports, source edits, or inference occur.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import zlib

P = 'experiments/sota-2026-10-22/epoch22/'
RAW_PATH = P + 'runs/dev/raw.json'
ARCHIVE_PATH = P + 'publication/actualarchive.dev.raw.v1.json'
EXTRACTOR_PATH = P + 'publication/restore_archived_artifact_v1.py'
HELPER_PATH = P + 'publication/prepare_publication_archive_v1.py'
RAW_SPEC = {'path': RAW_PATH, 'bytes': 21631719,
            'sha256': '2b012e1595bdb9b3bb1e5dacc242e9136a189638704f3a55229fe4d828cd0414',
            'git_blob_sha1': '113b883813afc968e1dd24732f2f70be992d4cfa'}
PARENT = '820f885f9d9c02e861c1a0ff47d7c8b26499424c'
PRIOR_EXPECTED_SHA = '7246382b308967f1532d45116b00e0b68f86c623215113bdbf904b0dfd29d9ac'
V1_SHA = '4798ccca6a501a7a2b06fd83d008c6d287d0bb690832aeb3cc0a26b6a0a07053'
MAX_BLOB_JSON_BYTES = 8 * 1024 * 1024 - 4096
MAX_TREE_JSON_BYTES = 190000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def load_v1():
    path = Path(__file__).with_name('prepare_publication_v1.py').absolute()
    require(path == path.resolve() and not any(p.is_symlink() for p in (path, *path.parents)),
            'Noncanonical reviewed V1 helper')
    require(digest(path.read_bytes()) == V1_SHA, 'Original reviewed V1 helper changed')
    spec = importlib.util.spec_from_file_location('epoch22_held_publication_v1', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_envelope(value, expected_artifact):
    """Bounded file-format verification; expected identity is supplied by caller.

    The actual publication path always supplies the hard-coded RAW_SPEC.
    The explicit argument also permits small author-only format fixtures.
    """
    require(isinstance(value, dict) and set(value) == {
        'schema_version', 'epoch', 'format', 'artifact', 'gzip', 'payload_base64'},
        'Archive envelope keys differ')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['epoch']) is int and value['epoch'] == 22
            and value['format'] == 'gzip+base64', 'Archive format/version differs')
    require(value['artifact'] == expected_artifact
            and type(value['artifact'].get('bytes')) is int,
            'Archive artifact is not the exact required identity')
    meta = value['gzip']
    require(isinstance(meta, dict) and set(meta) == {'bytes', 'sha256', 'mtime'}
            and type(meta['bytes']) is int and 0 < meta['bytes'] < MAX_BLOB_JSON_BYTES
            and type(meta['mtime']) is int and meta['mtime'] == 0,
            'Archive compressed metadata differs')
    encoded = value['payload_base64']
    require(isinstance(encoded, str) and len(encoded) <= MAX_BLOB_JSON_BYTES,
            'Archive base64 payload exceeds bound')
    try:
        compressed = base64.b64decode(encoded.encode('ascii'), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise ValueError('Archive payload is not strict ASCII base64') from exc
    require(base64.b64encode(compressed).decode('ascii') == encoded,
            'Noncanonical base64 payload')
    require(len(compressed) == meta['bytes'] and digest(compressed) == meta['sha256'],
            'Compressed archive identity differs')
    require(len(compressed) >= 18 and compressed[:3] == b'\x1f\x8b\x08'
            and compressed[4:8] == b'\0\0\0\0', 'Gzip header/mtime differs')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        data = decoder.decompress(compressed, expected_artifact['bytes'] + 1)
    except zlib.error as exc:
        raise ValueError('Invalid gzip member') from exc
    require(len(data) == expected_artifact['bytes'] and decoder.eof
            and not decoder.unconsumed_tail and not decoder.unused_data,
            'Archive size/trailing-member/expansion bound differs')
    require(digest(data) == expected_artifact['sha256']
            and git_blob(data) == expected_artifact['git_blob_sha1'],
            'Restored raw bytes are not the exact sealed artifact')
    return data


def reject_previously_published_raw(baseline, prior, scope):
    require(RAW_PATH not in baseline and scope + RAW_PATH not in prior,
            'Archive exception cannot replace a historical or published source leaf')


def project_expected_to_git(project_rows, prior, scope, controls):
    """Remove exactly the one explicitly reconstructed project-only leaf."""
    rows = {row['path']: copy.deepcopy(row) for row in project_rows}
    require(len(rows) == len(project_rows), 'Duplicate project expected leaf')
    key = scope + RAW_PATH
    require(rows.get(key) == {'path': key, 'mode': '100644', 'type': 'blob',
                             'sha': RAW_SPEC['git_blob_sha1'], 'size': RAW_SPEC['bytes']},
            'Raw project expected Git tuple changed')
    require(key not in prior, 'Raw was already present in published source')
    del rows[key]
    require(set(rows) == {row['path'] for row in project_rows} - {key},
            'Unexpected additional project-to-Git omission')
    for path, row in prior.items():
        if path[len(scope):] not in controls:
            require(rows.get(path) == row, 'Published source leaf changed: ' + path)
    return rows


def checked_reconstruction(helper, project, controls):
    continuation = helper.parse(controls / 'CONTINUATION.json')
    active = helper.parse(controls / 'ACTIVE_RUN.json')
    transport = continuation.get('artifact_transport')
    require(isinstance(transport, dict) and set(transport) == {
        'archive', 'extractor', 'restored_artifact', 'required_before_bootstrap',
        'publication_helper', 'format', 'standalone_Git_leaf_omitted'},
        'Exact reconstruction references required')
    require(transport['required_before_bootstrap'] is True,
            'Archive restoration must precede unchanged bootstrap/restoration')
    require(transport['format'] == 'gzip+base64'
            and transport['standalone_Git_leaf_omitted'] == RAW_PATH,
            'Only the fixed raw gzip+base64 archive exception is permitted')
    require(active.get('checkpoint_parent') == PARENT
            and continuation.get('prior_published_base_commit') == PARENT,
            'Final archive stage must descend from the actual published source')
    for key, rel in [('archive', ARCHIVE_PATH), ('extractor', EXTRACTOR_PATH),
                     ('publication_helper', HELPER_PATH)]:
        data = helper.content(project / rel)
        helper.public_text(rel, data)
        require(transport[key] == {'path': rel, 'bytes': len(data), 'sha256': digest(data)},
                'Reconstruction file reference changed: ' + key)
    require(transport['publication_helper']['sha256'] == digest(helper.content(Path(__file__))),
            'Publication helper reference is not this exact wrapper')
    raw_ref = {k: RAW_SPEC[k] for k in ('path', 'bytes', 'sha256')}
    require(transport['restored_artifact'] == raw_ref, 'Restored artifact reference changed')
    raw = helper.content(project / RAW_PATH)
    require(len(raw) == RAW_SPEC['bytes'] and digest(raw) == RAW_SPEC['sha256']
            and git_blob(raw) == RAW_SPEC['git_blob_sha1'], 'Sealed local raw bytes changed')
    envelope = helper.parse(project / ARCHIVE_PATH)
    require(decode_envelope(envelope, RAW_SPEC) == raw, 'Archive is not lossless exact local raw')
    cp = helper.parse(controls / 'CHECKPOINT_MANIFEST.json')
    cp_rows = {row['path']: row for row in cp['project_files']}
    require(len(cp_rows) == len(cp['project_files']), 'Duplicate CP artifact path')
    for row in [raw_ref, transport['archive'], transport['extractor'],
                transport['publication_helper']]:
        require(cp_rows.get(row['path']) == row, 'CP reconstruction identity changed')
    return transport, len(cp_rows)


def build_transport(helper, changed):
    _, big, groups = helper.transport_groups(changed)
    for _, payload, _, _ in big:
        require(len(helper.raw_json(payload)) < MAX_BLOB_JSON_BYTES,
                'Blob request exceeds8MiB including metadata reserve')
    for group in groups:
        require(len(helper.raw_json({'tree_elements': group})) < MAX_TREE_JSON_BYTES,
                'Tree request exceeds190k')
    return big, groups


def prepare(args):
    helper = load_v1()
    require(args.mode == 'final' and args.prior_expected is not None,
            'Archive wrapper supports final stages with exact prior source only')
    project = helper.regular_dir(args.project)
    kit = helper.regular_dir(args.kit)
    controls = helper.regular_dir(args.controls_dir)
    out = Path(args.out).absolute()
    require(out == out.resolve() and not out.exists() and not out.is_symlink(),
            'Final archive stage must be a new canonical path')
    helper.regular_dir(out.parent)
    require(not any(out.is_relative_to(root) or root.is_relative_to(out)
                    for root in (project, kit)), 'Stage must be outside project and kit')
    prior_bytes = helper.content(args.prior_expected)
    require(digest(prior_bytes) == PRIOR_EXPECTED_SHA, 'Exact published source expected leaves changed')
    prior_doc = json.loads(prior_bytes)
    prior = {row['path']: row for row in prior_doc['files']}
    require(len(prior) == len(prior_doc['files']) == 3329, 'Exact3329 prior source leaves required')
    baseline = {row['path']: row for row in helper.parse(args.source_filemap)['files']}
    reject_previously_published_raw(baseline, prior, helper.SCOPE)
    reconstruction, cp_count = checked_reconstruction(helper, project, controls)
    # V1 remains the authority for the full source-map, file/asset exclusions,
    # privacy walk, exact current allowlist, CP coverage and final closed controls.
    with tempfile.TemporaryDirectory(prefix='epoch22-prearchive-', dir=out.parent) as work:
        pre = Path(work) / 'checked-v1'
        v1_args = SimpleNamespace(**vars(args))
        v1_args.out = pre
        helper.prepare(v1_args)
        original = helper.parse(pre / 'manifest.json')
        project_expected = helper.parse(pre / 'expected-leaves.json')
        expected = project_expected_to_git(project_expected['files'], prior,
                                           helper.SCOPE, helper.CONTROLS)
        changed = {row['path']: helper.content(pre / 'changed' / row['path'])
                   for row in original['new_and_control_files']}
        require(RAW_PATH in changed, 'Exact raw exception is not a new final-stage payload')
        del changed[RAW_PATH]
        big, groups = build_transport(helper, changed)
        current_count = original['new_public22_leaves']
        require(cp_count == 3172 + current_count
                and len(project_expected['files']) == 3249 + current_count
                and len(expected) == 3249 + current_count - 1,
                'Project versus Git checkpoint counts disagree')
        meta = copy.deepcopy(original)
        meta.update(archived_project_files_not_standalone_git_blobs=1,
            archived_project_artifacts=[copy.deepcopy(RAW_SPEC)],
            project_vs_git_counts={'public_epoch22_project_files': current_count,
                'public_epoch22_standalone_git_leaves': current_count - 1,
                'checkpoint_project_files': cp_count,
                'expected_project_leaves': len(project_expected['files']),
                'expected_standalone_git_leaves': len(expected)},
            source_constraints={'actual_parent_source_commit': PARENT,
                'prior_expected_sha256': digest(prior_bytes),
                'all_prior_noncontrol_tuples_preserved': True,
                'archived_raw_absent_baseline_and_prior_source': True},
            reconstruction_refs=copy.deepcopy(reconstruction),
            transport_limits={'blob_JSON_bytes_exclusive': MAX_BLOB_JSON_BYTES,
                'request_metadata_reserve_bytes': 4096,
                'tree_JSON_bytes_exclusive': MAX_TREE_JSON_BYTES},
            large_blob_requests=[], create_tree_groups=[], new_and_control_files=[])
        out.mkdir(mode=0o700)
        (out / 'changed').mkdir(mode=0o700)
        (out / 'transport').mkdir(mode=0o700)
        for rel, data in sorted(changed.items()):
            path = out / 'changed' / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            helper.write(path, data)
            meta['new_and_control_files'].append({'path': rel, 'bytes': len(data),
                'sha256': digest(data), 'git_blob_sha1': git_blob(data)})
        for name, payload, rel, data in big:
            raw = helper.raw_json(payload)
            helper.write(out / 'transport' / name, raw)
            meta['large_blob_requests'].append({'path': rel, 'file': 'transport/' + name,
                'bytes': len(raw), 'sha256': digest(raw), 'expected_blob_sha1': git_blob(data),
                'must_create_and_verify_before_tree': True})
        for number, group in enumerate(groups):
            name = 'tree-%03d.json' % number
            raw = helper.raw_json({'tree_elements': group})
            helper.write(out / 'transport' / name, raw)
            meta['create_tree_groups'].append({'file': 'transport/' + name,
                'bytes': len(raw), 'sha256': digest(raw), 'entries': len(group)})
        expect = dict(project_expected, files=[expected[p] for p in sorted(expected)])
        raw = helper.raw_json(expect)
        helper.write(out / 'expected-leaves.json', raw)
        meta['expected_leaves'] = {'file': 'expected-leaves.json', 'bytes': len(raw),
                                   'sha256': digest(raw), 'count': len(expected)}
        helper.write(out / 'manifest.json', helper.raw_json(meta))
    return {key: value for key, value in meta.items() if key not in
            ('new_and_control_files', 'large_blob_requests', 'create_tree_groups')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'kit', 'source-filemap', 'controls-dir', 'out',
                 'prior-expected', 'reviewed-files'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=['final'], required=True)
    print(json.dumps(prepare(parser.parse_args()), sort_keys=True))


if __name__ == '__main__':
    main()
