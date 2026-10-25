"""Input-only Epoch33 projection. Full annotated JSON is parsed; field isolation is logical."""
import argparse
from pathlib import Path
import json,re
from data_common import (TRAIN_IDS, DEV_IDS, HYPOTHESES, SOURCE_SHA, SOURCE_BYTES,
                         ALLOCATION_SHA, require, digest, canonical, norm, read,
                         identity, write_new, expected, SOURCE_CHECKPOINT)

def planning_admission(path, expected_commit):
    require(type(expected_commit) is str and re.fullmatch('[0-9a-f]{40}',expected_commit),
            'Exact actual planning commit required before source parse')
    proof = read(Path(path))
    require(proof.get('checks_passed') is True and proof.get('verified_actual_remote_readback') is True,
            'Independent actual planning reservation readback required')
    require(proof.get('commit') == expected_commit and proof.get('parent') == SOURCE_CHECKPOINT,
            'Current actual planning commit/parent differs')
    require(proof.get('reserved_DEV_document_ids') == DEV_IDS
            and proof.get('allocation_sha256') == ALLOCATION_SHA,
            'Remote reserved roles/allocation differ from fixed metadata')
    return identity(path)

def verify_freeze(path, freeze_sha, audit_dir):
    freeze = read(path, freeze_sha)
    require(freeze['epoch'] == 33, 'Wrong epoch freeze')
    seen = set()
    for pin in freeze['files']:
        name = pin['path']
        require(type(name) is str and '/' not in name and name not in ('.','..') and name not in seen, 'Unsafe/duplicate projection pin')
        seen.add(name)
        actual = identity(audit_dir/name)
        require(actual['bytes'] == pin['bytes'] and actual['sha256'] == pin['sha256'], 'Frozen projection source changed: '+name)
    require(set(['build_inputs.py','data_common.py','audit_input_identity.py','selection.json','exposure-metadata.json','protocol.json']) <= seen, 'Required projection sources not frozen')
    return freeze

def project(source_path, output_dir, audit_dir, freeze_path, freeze_sha, planning_readback, planning_commit):
    audit_dir = Path(audit_dir).resolve()
    verify_freeze(freeze_path, freeze_sha, audit_dir)
    allocation = read(audit_dir/'selection.json', ALLOCATION_SHA)
    require(allocation['roles'] == {'train': TRAIN_IDS, 'dev': DEV_IDS, 'calibration': [], 'confirmation': []}, 'Fixed roles changed')
    exposure = read(audit_dir/'exposure-metadata.json')
    planning_proof = planning_admission(planning_readback,planning_commit)
    out = Path(output_dir).resolve()
    require(out.is_dir() and not any(out.iterdir()), 'New empty output directory required')
    write_new(out/'reservation.json', {'epoch': 33, 'roles': allocation['roles'], 'hypotheses': HYPOTHESES,
              'retire_all_selected_ids_on_any_subsequent_failure': True, 'source_freeze_sha256': freeze_sha,
              'source_annotation_choices_accessed': 0, 'confirmation': [],
              'planning_readback': planning_proof, 'published_planning_commit': planning_commit})
    # Parse full public annotated source into RAM; intentionally traverse only
    # document id/text and hypothesis descriptors, never annotation/evidence fields.
    source = read(source_path, SOURCE_SHA, SOURCE_BYTES)
    docs = {d['id']: d for d in source['documents']}
    universe = set(exposure['exposed_document_ids']) | set(exposure['reserved_document_ids']) | set(exposure['eligible_document_ids'])
    require(len(source['documents']) == len(docs) == 423 and set(docs) == universe, 'Source universe changed')
    blocked = set(exposure['blocked_normalized_document_sha256'])
    cross = {x['normalized_document_sha256'] for x in exposure['cross_split_documents']}
    old = exposure['old_identity_records']
    old_inputs = {r[k] for r in old for k in ['input_sha256', 'normalized_input_sha256'] if k in r}
    old_docs = {r['normalized_document_sha256'] for r in old if 'normalized_document_sha256' in r}
    seen = set()
    reports = {}
    for role, ids in [('dev', DEV_IDS)]:
        records, identities = [], []
        for did in ids:
            document = docs[did]['text']
            require(type(document) is str, 'Nonstring source document')
            nd = digest(norm(document).encode())
            require(nd == exposure['catalog_selected_hashes'][str(did)],
                    'Selected source differs from frozen E29 canonical hash: HOLD, never redraw')
            require(nd not in blocked | cross | old_docs | seen, 'Normalized prior/reserved/cross-split/selected alias: HOLD, never redraw')
            seen.add(nd)
            for hid in HYPOTHESES:
                hypothesis = source['labels'][hid]['hypothesis']
                require(type(hypothesis) is str, 'Nonstring hypothesis')
                encoded = canonical({'document': document, 'hypothesis': hypothesis})
                raw_sha, normalized_sha = digest(encoded.encode()), digest(norm(encoded).encode())
                require(raw_sha not in old_inputs and normalized_sha not in old_inputs, 'Prior raw/normalized input alias: HOLD, never redraw')
                identifier = f'original-contractnli:train:epoch33:{role}:{did}:{hid}'
                records.append({'id': identifier, 'document_id': did, 'hypothesis_id': hid,
                                'document': document, 'hypothesis': hypothesis, 'input_sha256': raw_sha})
                identities.append({'id': identifier, 'document_id': did, 'hypothesis_id': hid,
                    'source_group': f'original-contractnli:{did}', 'input_sha256': raw_sha,
                    'normalized_input_sha256': normalized_sha, 'normalized_document_sha256': nd,
                    'document_sha256': digest(document.encode()), 'document_utf8_bytes': len(document.encode()),
                    'hypothesis_sha256': digest(hypothesis.encode())})
        require([(r['id'],r['document_id'],r['hypothesis_id']) for r in records] == expected(role), 'Fixed case order changed')
        write_new(out/(role+'.inputs.json'), {'schema_version': 1, 'epoch': 33, 'role': role, 'records': records})
        write_new(out/(role+'.input-identities.json'), {'schema_version': 1, 'epoch': 33, 'role': role,
                  'records': identities, 'source_sha256': SOURCE_SHA, 'source_freeze_sha256': freeze_sha,
                  'contains_labels_or_inputs': False, 'annotation_choices_accessed': 0})
        reports[role] = {'document_ids': ids, 'cases': 24, 'inputs': identity(out/(role+'.inputs.json')),
                         'identities': identity(out/(role+'.input-identities.json'))}
    require(len(seen) == 8, 'New bank source aliases')
    result = {'schema_version': 1, 'epoch': 33, 'status': 'FIXED_DEV24_TYPED_DECISION_INPUTS_ONLY_PROJECTED',
        'source': identity(source_path), 'source_freeze_sha256': freeze_sha, 'roles': reports,
        'planning_readback': planning_proof, 'published_planning_commit': planning_commit,
        'source_annotation_choices_accessed': 0, 'source_evidence_lists_accessed': 0,
        'other_role_text_projected': 0, 'old_banks_or_reserved_text_fields_traversed': 0,
        'all8_selected_document_identities_permanently_exposed': True,
        'partition_after_projection': {'exposed': 317, 'unreserved': 82, 'reserved_confirmation': 24, 'total': 423},
        'isolation': 'Complete annotated source JSON parsed in RAM; logical field isolation, never OS-enforced label secrecy',
        'confirmation': [], 'calibration': [], 'benchmark_accepted': False, 'champion_promoted': False,
        'source_license': 'CC-BY-4.0', 'attribution': 'Koreeda and Manning (2021), ContractNLI',
        'source_url': 'https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'transformations': 'Select exact8 original TRAIN source documents ×3 fixed hypotheses; preserve text; add metadata/canonical hashes; no source annotation or evidence projection'}
    write_new(out/'projection.json', result)
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for n in ['source', 'output-dir', 'audit-dir', 'source-freeze', 'source-freeze-sha256',
              'planning-readback','expected-planning-commit']:
        p.add_argument('--'+n, required=True)
    a = p.parse_args()
    r = project(a.source, a.output_dir, a.audit_dir, a.source_freeze, a.source_freeze_sha256,
                a.planning_readback,a.expected_planning_commit)
    print(json.dumps({'status':r['status'],'cases':24,'annotation_choices_accessed':0}))
