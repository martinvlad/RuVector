"""Epoch31 independent source-free identity replay: no annotated-source traversal."""
import argparse
from pathlib import Path
import json
from data_common import (TRAIN_IDS, DEV_IDS, HYPOTHESES, ALLOCATION_SHA, require,
                         read, identity, write_new, expected, digest, canonical, norm)

def audit(project, audit_dir, data_dir):
    root, here, data = map(lambda p: Path(p).resolve(), [project, audit_dir, data_dir])
    allocation = read(here/'selection.json', ALLOCATION_SHA)
    exposure = read(here/'exposure-metadata.json')
    require(allocation['roles'] == {'train':TRAIN_IDS,'dev':DEV_IDS,'calibration':[],'confirmation':[]}, 'Fixed roles changed')
    verified = []
    for pin in exposure['historical_metadata_source_pins']:
        path = root/pin['project_path']
        got = identity(path)
        require(got['bytes'] == pin['bytes'] and got['sha256'] == pin['sha256'], 'Historical metadata bytes changed')
        verified.append(pin['project_path'])
    old = exposure['old_identity_records']
    old_ids = {r.get('id') for r in old}
    old_groups = {r.get('source_group') for r in old}
    old_inputs = {r[k] for r in old for k in ['input_sha256','normalized_input_sha256'] if k in r}
    blocked = set(exposure['blocked_normalized_document_sha256'])
    blocked |= {r['normalized_document_sha256'] for r in exposure['cross_split_documents']}
    blocked |= {r['normalized_document_sha256'] for r in old if 'normalized_document_sha256' in r}
    all_docs, roles = {}, {}
    for role, ids in [('dev',DEV_IDS)]:
        bank = read(data/(role+'.inputs.json')); meta = read(data/(role+'.input-identities.json'))
        require(bank['epoch'] == meta['epoch'] == 31 and bank['role'] == meta['role'] == role, 'Wrong bank role')
        require(meta['annotation_choices_accessed'] == 0 and meta['contains_labels_or_inputs'] is False, 'Not label-free identities')
        rows = meta['records']; require([(r['id'],r['document_id'],r['hypothesis_id']) for r in rows] == expected(role), 'Identity order changed')
        require([(r['id'],r['document_id'],r['hypothesis_id']) for r in bank['records']] == expected(role), 'Input order changed')
        require(set(ids) <= set(exposure['eligible_document_ids']), 'New role not eligible')
        for row, record in zip(rows, bank['records']):
            require(set(record) == {'id','document_id','hypothesis_id','document','hypothesis','input_sha256'}, 'Unexpected bank fields')
            require(row['id'] not in old_ids and row['source_group'] not in old_groups, 'Old ID/group alias')
            raw = canonical({'document':record['document'],'hypothesis':record['hypothesis']})
            require(record['input_sha256'] == row['input_sha256'] == digest(raw.encode()), 'Input literal hash mismatch')
            require(row['normalized_input_sha256'] == digest(norm(raw).encode()), 'Normalized input hash mismatch')
            require(row['input_sha256'] not in old_inputs and row['normalized_input_sha256'] not in old_inputs, 'Old input alias')
            nd = digest(norm(record['document']).encode())
            require(nd == exposure['catalog_selected_hashes'][str(row['document_id'])],
                    'Input source differs from fixed canonical metadata')
            require(nd == row['normalized_document_sha256'] and nd not in blocked, 'Old/protected/crosssplit document alias')
            require(row['document_sha256'] == digest(record['document'].encode()) and row['document_utf8_bytes'] == len(record['document'].encode()), 'Document hash/bytes mismatch')
            require(row['hypothesis_sha256'] == digest(record['hypothesis'].encode()), 'Hypothesis hash mismatch')
            did = row['document_id']
            require(did not in all_docs or all_docs[did] == nd, 'Inconsistent same-document hash')
            all_docs[did] = nd
        roles[role] = {'document_ids':ids,'cases':24,'inputs':identity(data/(role+'.inputs.json')),'identities':identity(data/(role+'.input-identities.json'))}
    require(len(all_docs) == len(set(all_docs.values())) == 8, 'New DEV source alias')
    return {'schema_version':1,'epoch':31,'status':'PASS_FIXED_DEV_INPUT_IDENTITY_AND_ALL_PRIOR_METADATA_BYTES',
        'roles':roles,'historical_metadata_files_bytes_verified':len(verified),'old_identity_records':len(old),
        'cross_split_metadata_rows':len(exposure['cross_split_documents']),'blocked_prior_and_reserved_document_hashes':len(exposure['blocked_normalized_document_sha256']),
        'exact_ID_group_document_input_alias_collisions':[],'annotation_choices_accessed':0,'source_evidence_lists_accessed':0,
        'old_or_reserved_text_fields_traversed':0,'model_tokenizer_native_calls':0,'confirmation':[],'calibration':[],
        'partition_after_projection':{'exposed':301,'unreserved':98,'reserved_confirmation':24,'total':423},
        'scope':'Current input texts and historical identity metadata only; no annotated source parse by auditor; logical isolation disclosed by builder'}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for n in ['project','audit-dir','data-dir','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();r=audit(a.project,a.audit_dir,a.data_dir);write_new(a.output,r)
    print(json.dumps({'status':r['status'],'cases':24,'annotation_choices_accessed':0}))
