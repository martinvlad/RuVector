"""Frozen TRAIN-only selective choice extraction; called only inside admitted TRAIN worker.

Parsing complete public annotated JSON is logical field isolation, not OS secrecy.
This module has no CLI and performs no I/O on import. Evidence fields are unused.
"""
from data_common import (SOURCE_SHA, SOURCE_BYTES, SOURCE_MAP, expected, read,
                         require, identity, digest, canonical)

_EXTRACTION_ATTEMPTED = False

def extract_train_choices(source_path, inputs_path, on_choice=None):
    global _EXTRACTION_ATTEMPTED
    require(_EXTRACTION_ATTEMPTED is False, 'TRAIN choice extraction permitted once per admitted worker')
    _EXTRACTION_ATTEMPTED = True
    bank = read(inputs_path)
    require(bank['schema_version'] == 1 and bank['epoch'] == 29 and bank['role'] == 'train', 'Exact TRAIN bank required')
    require([(r['id'],r['document_id'],r['hypothesis_id']) for r in bank['records']] == expected('train'), 'Fixed TRAIN24 order required')
    source = read(source_path, SOURCE_SHA, SOURCE_BYTES)
    docs = {d['id']:d for d in source['documents']}
    require(len(docs) == len(source['documents']) == 423, 'Official source universe changed')
    # Finish every source/input authenticity check before the first choice read.
    for row in bank['records']:
        doc = docs[row['document_id']]
        require(doc['text'] == row['document'], 'TRAIN source document mismatch')
        require(source['labels'][row['hypothesis_id']]['hypothesis'] == row['hypothesis'], 'TRAIN hypothesis mismatch')
        require(row['input_sha256'] == digest(canonical({'document':row['document'],'hypothesis':row['hypothesis']}).encode()), 'TRAIN input hash mismatch')
        require(len(doc['annotation_sets']) == 1, 'Unique original annotation set required')
    records = []
    for row in bank['records']:
        if on_choice is not None:
            on_choice(row['id'])  # caller records attempted read before field access
        original = docs[row['document_id']]['annotation_sets'][0]['annotations'][row['hypothesis_id']]['choice']
        require(type(original) is str and original in SOURCE_MAP, 'Unknown original TRAIN choice')
        records.append({k:row[k] for k in ['id','document_id','hypothesis_id','input_sha256']} |
                       {'native_target_index':SOURCE_MAP[original],'source_choice':original})
    return {'schema_version':1,'epoch':29,'role':'train','source':identity(source_path),'inputs':identity(inputs_path),
            'records':records,'TRAIN_annotation_choices_accessed':24,'DEV_annotation_choices_accessed':0,
            'CONF_annotation_choices_accessed':0,'other_role_annotation_choices_accessed':0,
            'source_evidence_lists_accessed':0,'isolation':'Complete annotated source JSON parsed; logical selected-field access only, not OS label secrecy'}
