"""Epoch27 metadata/input-identity audit, no annotated-source field traversal."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV_IDS = [609, 380, 592, 454, 559, 515, 349, 223]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
EXPOSURE_SHA = 'b19bdef9da89b8196afd39f0e2b0bd4983b6d747f2b11932df44a38d5f483bf4'
SELECTION_SHA = '6d97e6e68266f44b0055953ed4a0a8d2546443f89c49043bdf14c29a38828955'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, sha=None):
    raw = Path(path).read_bytes()
    require(sha is None or digest(raw) == sha, 'SHA mismatch')
    return json.loads(raw)


def rebase(old_path, root):
    marker = '/experiments/'
    require(marker in old_path, 'Expected experiment-relative historical source')
    path = root / ('experiments/' + old_path.split(marker, 1)[1])
    require(path.resolve().is_relative_to(root) and not path.is_symlink(), 'Unsafe source path')
    return path


def audit(root, identities_path):
    root = Path(root).resolve()
    selection = read(HERE/'selection.json', SELECTION_SHA)
    exposure = read(HERE/'exposure-metadata.json', EXPOSURE_SHA)
    require(selection['roles']['dev'] == DEV_IDS and not selection['roles']['confirmation'],
            'Fixed DEV-only scope changed')
    verified = []
    for row in exposure['old_allowlist_files'] + exposure['metadata_source_pins']:
        path = rebase(row['path'], root)
        # Raw byte identity only: no old input/text/choice/prediction field traversal.
        raw = path.read_bytes()
        require(len(raw) == row['bytes'] and digest(raw) == row['sha256'],
                'Actual restored historical metadata byte mismatch: ' + str(path))
        verified.append(str(path.relative_to(root)))
    new = read(identities_path)
    require(new['epoch'] == 27 and new['role'] == 'dev'
            and new['annotation_choices_accessed'] == 0
            and new['contains_labels_or_inputs'] is False, 'Not label-free DEV identities')
    rows = new['records']
    expected = [(f'original-contractnli:train:epoch27:dev:{did}:{hid}', did, hid)
                for did in DEV_IDS for hid in HYPOTHESES]
    require([(r['id'], r['document_id'], r['hypothesis_id']) for r in rows] == expected,
            'Fixed ordered identities mismatch')
    old = exposure['old_identity_records']
    old_groups = {r.get('source_group') for r in old}
    old_ids = {r.get('id') for r in old}
    old_input = {r[k] for r in old for k in ['input_sha256', 'normalized_input_sha256'] if k in r}
    blocked = set(exposure['blocked_normalized_document_sha256'])
    cross = {r['normalized_document_sha256'] for r in exposure['cross_split_documents']}
    old_doc = {r['normalized_document_sha256'] for r in old if 'normalized_document_sha256' in r}
    require(set(DEV_IDS) <= set(exposure['eligible_document_ids']), 'Fixed DEV not eligible')
    require(not(set(DEV_IDS) & (set(exposure['exposed_document_ids'])
                              | set(exposure['reserved_document_ids']))), 'Prior or reserved ID alias')
    for row in rows:
        require(row['id'] not in old_ids and row['source_group'] not in old_groups,
                'Prior exact ID/group alias')
        require(row['input_sha256'] not in old_input
                and row['normalized_input_sha256'] not in old_input, 'Prior raw/normalized input alias')
        require(row['normalized_document_sha256'] not in blocked | cross | old_doc,
                'Prior/reserved/cross-split normalized document alias')
    hashes = {did: {r['normalized_document_sha256'] for r in rows if r['document_id'] == did}
              for did in DEV_IDS}
    require(all(len(v) == 1 for v in hashes.values()), 'Inconsistent within-document hashes')
    require(len(set.union(*hashes.values())) == 8, 'Selected normalized document alias')
    return {'schema_version': 1, 'epoch': 27,
        'status': 'PASS_FIXED_DEV_IDENTITY_EXPOSURE_AND_RESTORED_METADATA_BYTES',
        'selected_docs': DEV_IDS, 'hypotheses': HYPOTHESES, 'cases': 24,
        'selected_doc_hashes': [next(iter(hashes[d])) for d in DEV_IDS],
        'old_allowlist_files_actual_restored_bytes_verified': len(exposure['old_allowlist_files']),
        'historical_metadata_source_pin_bytes_verified': len(exposure['metadata_source_pins']),
        'old_identity_records': len(old), 'blocked_prior_reserved_normalized_docs': len(blocked),
        'cross_split_metadata_rows': len(exposure['cross_split_documents']),
        'exact_ID_group_normalized_doc_raw_input_normalized_input_collisions': [],
        'partition_after_input_projection': {'exposed': 261, 'reserved': 24,
                                             'unreserved': 138, 'total': 423},
        'old_source_or_reserved_text_fields_traversed_by_identity_audit': 0,
        'old_reserved_choices_and_model_predictions_this_audit': 0,
        'source_annotation_choices_accessed': 0, 'model_tokenizer_native_calls': 0,
        'confirmation': [], 'benchmark_accepted': False, 'champion_promoted': False,
        'unknown_foundation_text_and_fuzzy_overlap': True,
        'scope': 'Historical metadata files hashed as raw bytes; only fixed new input identity records parsed. Root restoration proof and builder authenticity remain separate evidence. Logical field isolation only.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ['project', 'identities', 'output']:
        ap.add_argument('--' + name, required=True)
    args = ap.parse_args()
    result = audit(args.project, args.identities)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'source_annotation_choices_accessed': 0}))
