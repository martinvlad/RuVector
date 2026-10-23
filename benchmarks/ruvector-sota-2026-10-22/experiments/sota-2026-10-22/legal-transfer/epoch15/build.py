"""One frozen source-ID-only DEV draw; gold projection requires root authorization.

--select-only never opens the original source corpus or any labels. The later
projection validates source, exclusion, exact input and full-text identities
before accessing annotation choices for the eight frozen DEV documents only.
This module never reads the reserved confirmation JSONL.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_COMMIT = 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
LABELS = {'Entailment': 'Yes', 'Contradiction': 'No', 'NotMentioned': 'No'}
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
INSTRUCTION = 'Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
SALT = 'ruvector-sota-epoch15-new-dev24-v1|'
CONF_SHA = '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def norm(text):
    return ' '.join(text.casefold().split())


def write_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def metadata():
    plan = load(HERE / 'draw-plan.json')
    registry = load(HERE / 'eligibility-manifest.json')
    if (plan['source_sha256'] != SOURCE_SHA or plan['source_commit'] != SOURCE_COMMIT
            or plan['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or plan['salt'] != SALT or plan['hypotheses'] != HYPOTHESES
            or plan['dev_documents'] != 8 or plan['train'] != [] or plan['calibration'] != []
            or plan['confirmation_preserved_sha256'] != CONF_SHA):
        raise ValueError('Frozen plan/source/projection changed')
    old = set(registry['excluded_document_ids'])
    reserved = set(registry['reserved_confirmation_document_ids'])
    eligible = set(registry['eligible_document_ids'])
    if (len(old) != 189 or len(reserved) != 16 or len(eligible) != 218
            or old & reserved or old & eligible or reserved & eligible
            or len(old | reserved | eligible) != 423):
        raise ValueError('Frozen exposure/reservation/eligibility counts or identities changed')
    ranked = sorted((hashlib.sha256((SALT + str(document_id)).encode()).hexdigest(), document_id)
                    for document_id in eligible)
    chosen = [{'document_rank': position, 'document_id': document_id,
               'document_draw_key': key, 'role': 'dev'}
              for position, (key, document_id) in enumerate(ranked[:8])]
    return plan, registry, chosen


def select_only():
    plan, registry, chosen = metadata()
    selection = {
        'schema_version': 1, 'frozen_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
        'eligibility_manifest_sha256': sha(HERE / 'eligibility-manifest.json'),
        'builder_sha256': sha(__file__), 'source_sha256': SOURCE_SHA,
        'selection': 'First8 SHA256(salt+str(documentID)) ranks of218eligible IDs; no source file opened',
        'gold_access_for_selection': False, 'source_corpus_opened_for_selection': False,
        'documents': chosen, 'hypotheses': HYPOTHESES, 'train': [], 'calibration': [],
        'confirmation': {'path': 'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl',
                         'sha256': CONF_SHA, 'project_model_unused': True,
                         'read_or_modified_by_this_builder': False},
        'query_identity': 'Exact pinned original train bytes + selected document IDs + fixed hypothesis IDs + frozen builder fixes all24input/gold projection identities before annotation access',
        'if_later_collision': 'Abort without redraw or outcome-based replacement',
    }
    write_new(HERE / 'document-selection.json', selection)
    return {'status': 'SOURCE_ID_ROLES_FROZEN_NO_GOLD_ACCESS', 'documents': chosen,
            'selection_sha256': sha(HERE / 'document-selection.json'),
            'source_corpus_opened': False, 'gold_accessed': False}


def validate_before_gold(source_path, project):
    plan, registry, chosen = metadata()
    selection = load(HERE / 'document-selection.json')
    if (selection['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or selection['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or selection['builder_sha256'] != sha(__file__)
            or selection['documents'] != chosen
            or selection['gold_access_for_selection'] is not False
            or selection['source_corpus_opened_for_selection'] is not False
            or selection['train'] != [] or selection['calibration'] != []
            or sha(source_path) != SOURCE_SHA):
        raise ValueError('Frozen source-only selection/builder/source changed')
    source = load(source_path)
    documents = {document['id']: document for document in source['documents']}
    expected = (set(registry['excluded_document_ids']) | set(registry['reserved_confirmation_document_ids'])
                | set(registry['eligible_document_ids']))
    if len(documents) != 423 or set(documents) != expected:
        raise ValueError('Official source document identity set changed')
    blocked_ids = {item['document_id'] for item in registry['cross_split_documents']}
    blocked_hashes = (set(registry['old_and_reserved_normalized_document_sha256'])
                      | {item['normalized_document_sha256'] for item in registry['cross_split_documents']})
    # Read metadata-only historical allowlists, never archived gold JSONL rows.
    prior_input_hashes = set()
    prior_normalized_input_hashes = set()
    history = Path(project) / 'experiments/sota-2026-10-22/legal-transfer'
    for allowlist in sorted(history.glob('epoch*/*allowlist*.json')):
        if allowlist.parent == HERE:
            continue
        value = load(allowlist)
        for row in value.get('records', []):
            if row.get('input_sha256'):
                prior_input_hashes.add(row['input_sha256'])
            if row.get('normalized_input_sha256'):
                prior_normalized_input_hashes.add(row['normalized_input_sha256'])
    prepared = []
    seen = set()
    for item in chosen:
        document_id = item['document_id']
        document = documents[document_id]
        normalized_sha = hashlib.sha256(norm(document['text']).encode()).hexdigest()
        if document_id in blocked_ids or normalized_sha in blocked_hashes or normalized_sha in seen:
            raise ValueError('Cross-split/prior/reserved/within-draw full-text collision; no redraw')
        seen.add(normalized_sha)
        for hypothesis_id in HYPOTHESES:
            positive = source['labels'][hypothesis_id]['hypothesis']
            inputs = {'state': document['text'], 'questions': {'decision': {
                'type': 'choice', 'instructions': INSTRUCTION,
                'criteria': {'Yes': positive, 'No': 'The agreement does not establish the following: ' + positive}}}}
            input_sha = hashlib.sha256(canonical(inputs).encode()).hexdigest()
            normalized_input_sha = hashlib.sha256(norm(canonical(inputs)).encode()).hexdigest()
            if input_sha in prior_input_hashes or normalized_input_sha in prior_normalized_input_hashes:
                raise ValueError('Exact/normalized historical input collision; no redraw')
            prepared.append((item, hypothesis_id, normalized_sha, inputs, input_sha, normalized_input_sha))
    if len(prepared) != 24:
        raise ValueError('Expected exactly24 frozen DEV inputs')
    return source, documents, prepared, {
        'status': 'PRE_GOLD_SOURCE_AND_INPUT_COLLISIONS_PASS',
        'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
        'selection_sha256': sha(HERE / 'document-selection.json'),
        'source_sha256': SOURCE_SHA, 'queries': 24, 'groups': 8,
        'prior_metadata_input_hashes_checked': len(prior_input_hashes),
        'prior_metadata_normalized_input_hashes_checked': len(prior_normalized_input_hashes),
        'exact_full_document_and_input_collisions': 0,
        'fuzzy_excerpt_or_pretraining_overlap_verified': False,
        'new_DEV_gold_accessed': False, 'confirmation_gold_accessed': False,
        'records': [{'document_id': item['document_id'], 'hypothesis_id': hypothesis,
                     'normalized_document_sha256': normalized_sha, 'input_sha256': input_sha,
                     'normalized_input_sha256': norm_sha}
                    for item, hypothesis, normalized_sha, inputs, input_sha, norm_sha in prepared],
    }


def materialize(source_path, project, authorized):
    if not authorized:
        raise PermissionError('Separate explicit root authorization required before DEV annotation access')
    source, documents, prepared, validation = validate_before_gold(source_path, project)
    # This file is written before the first annotation choice access. Its identity
    # proves source/input collision checks do not depend on DEV outcomes.
    write_new(HERE / 'pre-gold-validation.json', validation)
    rows = []
    for item, hypothesis_id, normalized_sha, inputs, input_sha, normalized_input_sha in prepared:
        document = documents[item['document_id']]
        if len(document['annotation_sets']) != 1:
            raise ValueError('Ambiguous source annotation')
        label = document['annotation_sets'][0]['annotations'][hypothesis_id]['choice']
        if label not in LABELS:
            raise ValueError('Unknown original annotation')
        group = 'original-contractnli:' + str(item['document_id'])
        rows.append({
            'id': f"original-contractnli:train:epoch15:dev:{item['document_id']}:{hypothesis_id}",
            'split': 'dev', 'source': 'stanfordnlp/contract-nli@' + SOURCE_COMMIT + '/train.json',
            'source_group': group, 'input': inputs,
            'evaluation': {'type': 'choice', 'gold': LABELS[label], 'labels': ['Yes', 'No'],
                           'source_family': hypothesis_id, 'group': group, 'gold_distribution': None,
                           'original_threeway_label': label},
            'input_sha256': input_sha, 'normalized_input_sha256': normalized_input_sha,
            'provenance': {'document_id': item['document_id'], 'file_name': document['file_name'],
                           'source_split': 'train', 'hypothesis_id': hypothesis_id,
                           'document_draw_key': item['document_draw_key'],
                           'document_rank': item['document_rank'],
                           'normalized_document_sha256': normalized_sha, 'license': 'CC-BY-4.0'},
            'exposure': 'One fixed project-unused DEV draw after source-only identity freeze; no fitting/calibration. Public-source NDA pilot, upstream pretraining/fuzzy overlap unknown.'})
    target = HERE / 'development24.jsonl'
    with target.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    allow = {'schema_version': 1, 'role': 'dev', 'queries': 24, 'document_groups': 8,
             'data_sha256': sha(target), 'threeway_classes': list(LABELS), 'binary_mapping': LABELS,
             'records': [{'id': row['id'], 'input_sha256': row['input_sha256'],
                          'normalized_input_sha256': row['normalized_input_sha256'],
                          'source_group': row['source_group'],
                          'hypothesis_id': row['provenance']['hypothesis_id']} for row in rows],
             'contains_labels_or_inputs': False, 'fit_permitted': False,
             'model_or_threshold_selection_permitted': False}
    write_new(HERE / 'dev-allowlist.json', allow)
    result = {'status': 'FROZEN_DEV24_MATERIALIZED_ONCE', 'queries': 24, 'document_groups': 8,
              'data_sha256': sha(target), 'allowlist_sha256': sha(HERE / 'dev-allowlist.json'),
              'builder_sha256': sha(__file__), 'selection_sha256': sha(HERE / 'document-selection.json'),
              'source_sha256': SOURCE_SHA, 'pre_gold_validation_sha256': sha(HERE / 'pre-gold-validation.json'),
              'DEV_annotation_choices_accessed': 24, 'confirmation_gold_accessed': False,
              'new_model_native_fit_paid_GPU_calls': 0,
              'originaltrain_exposed_groups_if_phase1_attempts': 197,
              'unreserved_originaltrain_remaining_if_attempted': 210}
    write_new(HERE / 'materialization.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--select-only', action='store_true')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--materialize-authorized', action='store_true')
    args = parser.parse_args()
    if args.select_only:
        if args.source or args.materialize_authorized:
            parser.error('ID-only selection must not access source or annotation projection')
        result = select_only()
    else:
        if not args.source or not args.project:
            parser.error('Frozen source and project are required for validation/materialization')
        result = materialize(args.source, args.project, args.materialize_authorized)
    print(json.dumps(result, indent=2))
