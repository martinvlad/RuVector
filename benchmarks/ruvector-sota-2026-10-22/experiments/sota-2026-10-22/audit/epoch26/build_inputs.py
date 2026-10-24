"""Frozen epoch26 input-only source projection. No source annotation access.

Full annotated JSON is parsed into this process: logical field isolation only.
Run only after the external source-freeze SHA has been recorded by root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SELECTION_SHA = '33c47bf8c8023bdf0329214203cd9b6885c6d0bfa198adfff4ec3d2fae6fbc54'
EXPOSURE_SHA = 'ddbf848e5d3700323ddfc494744a3a01178cfca2b8dc10c45e95d85132d33b93'
DEV_IDS = [437, 614, 194, 174, 256, 490, 317, 196]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def norm(value):
    return ' '.join(value.casefold().split())


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def read(path, expected_sha=None, expected_bytes=None):
    p = Path(path)
    require(p.is_absolute() and p == p.resolve() and not p.is_symlink(),
            'Absolute nonsymlink path required')
    raw = p.read_bytes()
    require(expected_sha is None or digest(raw) == expected_sha, 'SHA mismatch: ' + str(p))
    require(expected_bytes is None or len(raw) == expected_bytes, 'Byte mismatch: ' + str(p))
    return json.loads(raw, object_pairs_hook=unique_object)


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def verify_freeze(path, expected_sha):
    freeze = read(path, expected_sha)
    require(freeze.get('epoch') == 26, 'Wrong source freeze epoch')
    rows = freeze['files']
    require(type(rows) is list and rows, 'Missing frozen files')
    seen = set()
    for row in rows:
        p = str(Path(row['path']).resolve())
        require(p not in seen and type(row['bytes']) is int, 'Duplicate or bad frozen file')
        seen.add(p)
        raw = Path(p).read_bytes()
        require(len(raw) == row['bytes'] and digest(raw) == row['sha256'], 'Frozen file changed: ' + p)
    require({str(Path(__file__).resolve()), str(HERE/'selection.json'),
             str(HERE/'exposure-metadata.json')} <= seen,
            'Builder, selection and exposure metadata must be frozen')
    return freeze


def project(source_path, output_dir, freeze_path, freeze_sha):
    verify_freeze(freeze_path, freeze_sha)
    selection = read(HERE/'selection.json', SELECTION_SHA)
    exposure = read(HERE/'exposure-metadata.json', EXPOSURE_SHA)
    require(selection['roles'] == {'train': [], 'dev': DEV_IDS, 'calibration': [], 'confirmation': []},
            'Exact DEV-only roles required')
    require(selection['hypotheses'] == HYPOTHESES, 'Wrong fixed hypotheses')
    require(set(DEV_IDS) <= set(exposure['eligible_document_ids']), 'DEV not eligible metadata')
    require(not (set(DEV_IDS) & set(exposure['reserved_document_ids'])), 'Reserved ID selected')
    out = Path(output_dir).resolve()
    require(out.is_dir() and not any(out.iterdir()), 'New empty output directory required')
    # Reserve all fixed IDs before first source parse. Any subsequent exposure or
    # failure conservatively retires these same IDs; no replacement draw exists.
    write_new(out/'reservation.json', {'epoch': 26, 'role': 'dev', 'document_ids': DEV_IDS,
        'hypotheses': HYPOTHESES, 'source_freeze_sha256': freeze_sha,
        'retire_all_selected_ids_on_any_subsequent_failure': True,
        'confirmation': [], 'source_annotation_choices_accessed': 0})
    source = read(source_path, SOURCE_SHA, 7608211)
    docs = {d['id']: d for d in source['documents']}
    universe = set(exposure['eligible_document_ids']) | set(exposure['exposed_document_ids']) | set(exposure['reserved_document_ids'])
    require(len(source['documents']) == len(docs) == 423 and set(docs) == universe,
            'Official423-document universe changed')
    require(all(type(d['id']) is int for d in source['documents']), 'Noninteger document ID')
    blocked = set(exposure['blocked_normalized_document_sha256'])
    cross = {r['normalized_document_sha256'] for r in exposure['cross_split_documents']}
    old_input = {r[k] for r in exposure['old_identity_records'] for k in
                 ['input_sha256', 'normalized_input_sha256'] if k in r}
    old_docs = {r['normalized_document_sha256'] for r in exposure['old_identity_records']
                if 'normalized_document_sha256' in r}
    seen, records, identities = set(), [], []
    for did in DEV_IDS:
        document = docs[did]['text']
        require(type(document) is str, 'Nonstring source document')
        document_sha = digest(norm(document).encode('utf-8'))
        require(document_sha not in blocked | cross | old_docs | seen,
                'Normalized old/reserved/cross-split/selected alias; HOLD, never redraw')
        seen.add(document_sha)
        for hid in HYPOTHESES:
            hypothesis = source['labels'][hid]['hypothesis']
            require(type(hypothesis) is str, 'Nonstring source hypothesis')
            payload = {'document': document, 'hypothesis': hypothesis}
            encoded = canonical(payload)
            input_sha = digest(encoded.encode('utf-8'))
            normalized_input_sha = digest(norm(encoded).encode('utf-8'))
            require(input_sha not in old_input and normalized_input_sha not in old_input,
                    'Old exact/normalized input alias; HOLD, never redraw')
            identifier = f'original-contractnli:train:epoch26:dev:{did}:{hid}'
            records.append({'id': identifier, 'document_id': did, 'hypothesis_id': hid,
                            **payload, 'input_sha256': input_sha})
            identities.append({'id': identifier, 'document_id': did, 'hypothesis_id': hid,
                'source_group': f'original-contractnli:{did}', 'input_sha256': input_sha,
                'normalized_input_sha256': normalized_input_sha,
                'normalized_document_sha256': document_sha})
    require(len(records) == 24 and len(seen) == 8, 'Incomplete DEV bank')
    bank = {'schema_version': 1, 'epoch': 26, 'role': 'dev', 'records': records}
    write_new(out/'inputs.json', bank)
    write_new(out/'input-identities.json', {'schema_version': 1, 'epoch': 26, 'role': 'dev',
        'records': identities, 'source_sha256': SOURCE_SHA, 'source_freeze_sha256': freeze_sha,
        'contains_labels_or_inputs': False, 'annotation_choices_accessed': 0})
    write_new(out/'projection.json', {'schema_version': 1, 'epoch': 26,
        'status': 'FIXED_DEV24_INPUT_ONLY_PROJECTED', 'source_sha256': SOURCE_SHA,
        'source_freeze_sha256': freeze_sha, 'document_ids': DEV_IDS, 'hypotheses': HYPOTHESES,
        'input_sha256': digest((out/'inputs.json').read_bytes()),
        'identities_sha256': digest((out/'input-identities.json').read_bytes()),
        'annotation_choices_accessed': 0, 'other_role_text_projected': 0,
        'old_banks_or_reserved_text_opened': 0, 'DEV_now_permanently_exposed': True,
        'isolation': 'Complete annotated JSON parsed; logical field isolation only, not OS isolation',
        'unknown_supervised_and_pretraining_overlap': True, 'confirmation': [],
        'benchmark_accepted': False, 'champion_promoted': False,
        'source_license': 'CC-BY-4.0',
        'attribution': 'Koreeda and Manning (2021), ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts',
        'source_url': 'https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'transformations': 'Selected8 original TRAIN documents ×3 fixed hypotheses; exact text preserved; metadata and canonical input hashes added.'})
    return {'status': 'FIXED_DEV24_INPUT_ONLY_PROJECTED', 'documents': 8, 'cases': 24,
            'annotation_choices_accessed': 0, 'input_sha256': digest((out/'inputs.json').read_bytes())}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--source-freeze', required=True)
    ap.add_argument('--source-freeze-sha256', required=True)
    a = ap.parse_args()
    print(json.dumps(project(a.source, a.output_dir, a.source_freeze,
                             a.source_freeze_sha256), sort_keys=True))
