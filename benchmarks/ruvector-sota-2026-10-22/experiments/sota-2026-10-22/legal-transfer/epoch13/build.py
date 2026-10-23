"""Rebuild the single frozen epoch13 DEV draw; never parse reserved CONF labels."""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_COMMIT = 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
LABELS = {'Entailment': 'Yes', 'Contradiction': 'No', 'NotMentioned': 'No'}
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
INSTRUCTION = 'Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def norm(text):
    return ' '.join(text.casefold().split())


def rank(pool, documents, salt):
    ranked = []
    for document_id in pool:
        normalized_sha = hashlib.sha256(norm(documents[document_id]['text']).encode()).hexdigest()
        key = hashlib.sha256((salt + str(document_id) + '|' + normalized_sha).encode()).hexdigest()
        ranked.append((key, document_id, normalized_sha))
    return sorted(ranked)


def role_records(groups, role='dev'):
    return [{'document_rank': position, 'document_id': document_id,
             'normalized_document_sha256': normalized_sha, 'document_draw_key': key, 'role': role}
            for position, (key, document_id, normalized_sha) in enumerate(groups)]


def select(source_path):
    plan = load(HERE / 'draw-plan.json')
    registry = load(HERE / 'eligibility-manifest.json')
    selection = load(HERE / 'document-selection.json')
    if (sha(source_path) != SOURCE_SHA or plan['source_sha256'] != SOURCE_SHA
            or plan['source_commit'] != SOURCE_COMMIT
            or sha(HERE / 'eligibility-manifest.json') != plan['eligibility_manifest_sha256']):
        raise ValueError('Pinned source or registry changed')
    if (plan['hypotheses'] != HYPOTHESES or plan['dev_documents'] != 8
            or plan['train'] != [] or plan['calibration'] != []):
        raise ValueError('Frozen projection or empty training/calibration roles changed')
    source = load(source_path)
    documents = {document['id']: document for document in source['documents']}
    old = set(registry['excluded_document_ids'])
    reserved = set(registry['reserved_confirmation_document_ids'])
    eligible = set(documents) - old - reserved
    if (len(documents) != 423 or len(old) != 181 or len(reserved) != 16 or old & reserved
            or len(eligible) != 226 or eligible != set(registry['eligible_document_ids'])):
        raise ValueError('Exposed, reserved or eligible identities changed')
    cross_ids = {item['document_id'] for item in registry['cross_split_documents']}
    cross_hashes = {item['normalized_document_sha256'] for item in registry['cross_split_documents']}
    blocked = set(registry['old_and_reserved_normalized_document_sha256']) | cross_hashes
    ranked = rank(eligible, documents, plan['salt'])
    for _, document_id, normalized_sha in ranked:
        if document_id in cross_ids or normalized_sha in blocked:
            raise ValueError('Cross-split, prior exposed or reserved text/identity collision')
    chosen = ranked[:8]
    if (selection['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or selection['documents'] != role_records(chosen)
            or selection['gold_access_for_selection'] is not False
            or selection['train'] != [] or selection['calibration'] != []):
        raise ValueError('Frozen source-only roles changed')
    return plan, source, chosen


def draw(source_path):
    plan, source, chosen = select(source_path)
    documents = {document['id']: document for document in source['documents']}
    output = []
    # Annotation access begins only after source-only selection and role checks above.
    for position, (key, document_id, normalized_sha) in enumerate(chosen):
        document = documents[document_id]
        if len(document['annotation_sets']) != 1:
            raise ValueError('Ambiguous source annotation')
        for hypothesis_id in plan['hypotheses']:
            positive = source['labels'][hypothesis_id]['hypothesis']
            inputs = {'state': document['text'], 'questions': {'decision': {
                'type': 'choice', 'instructions': INSTRUCTION,
                'criteria': {'Yes': positive, 'No': 'The agreement does not establish the following: ' + positive}}}}
            label = document['annotation_sets'][0]['annotations'][hypothesis_id]['choice']
            group = 'original-contractnli:' + str(document_id)
            output.append({
                'id': f'original-contractnli:train:epoch13:dev:{document_id}:{hypothesis_id}',
                'split': 'dev', 'source': 'stanfordnlp/contract-nli@' + SOURCE_COMMIT + '/train.json',
                'source_group': group, 'input': inputs,
                'evaluation': {'type': 'choice', 'gold': LABELS[label], 'labels': ['Yes', 'No'],
                               'source_family': hypothesis_id, 'group': group, 'gold_distribution': None,
                               'original_threeway_label': label},
                'input_sha256': hashlib.sha256(canonical(inputs).encode()).hexdigest(),
                'normalized_input_sha256': hashlib.sha256(norm(canonical(inputs)).encode()).hexdigest(),
                'provenance': {'document_id': document_id, 'file_name': document['file_name'],
                               'source_split': 'train', 'hypothesis_id': hypothesis_id,
                               'document_draw_key': key, 'document_rank': position,
                               'normalized_document_sha256': normalized_sha, 'license': 'CC-BY-4.0'},
                'exposure': 'New project-unused DEV for one frozen gate; no training or calibration. Public-source NDA pilot; upstream pretraining overlap unknown.'})
    return output


def allow(rows, data_sha):
    return {'schema_version': 1, 'role': 'dev', 'queries': len(rows),
            'document_groups': len({row['source_group'] for row in rows}), 'data_sha256': data_sha,
            'threeway_classes': list(LABELS), 'binary_mapping': LABELS,
            'records': [{'id': row['id'], 'input_sha256': row['input_sha256'],
                         'source_group': row['source_group'], 'hypothesis_id': row['provenance']['hypothesis_id']}
                        for row in rows],
            'contains_labels_or_inputs': False, 'fit_permitted': False,
            'model_or_threshold_selection_permitted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=True)
    rows = draw(args.source)
    target = args.output_dir / 'development24.jsonl'
    with target.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    with (args.output_dir / 'dev-allowlist.json').open('x') as stream:
        stream.write(json.dumps(allow(rows, sha(target)), indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'queries': len(rows), 'document_groups': len({row['source_group'] for row in rows}),
                      'sha256': sha(target)}))
