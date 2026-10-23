"""Rebuild frozen DEV and reused TRAIN sanity; never parse CONF projection."""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
LABELS = {'Entailment': 'Yes', 'Contradiction': 'No', 'NotMentioned': 'No'}
INSTRUCTION = ('Determine whether the agreement entails the supplied hypothesis. '
               'Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def norm(text):
    return ' '.join(text.casefold().split())


def load(path):
    return json.loads(Path(path).read_text())


def rank(ids, docs, salt):
    result = []
    for doc_id in ids:
        text_sha = hashlib.sha256(norm(docs[doc_id]['text']).encode()).hexdigest()
        key = hashlib.sha256((salt + str(doc_id) + '|' + text_sha).encode()).hexdigest()
        result.append((key, doc_id, text_sha))
    return sorted(result)


def role_records(chosen, role):
    return [{'document_rank': n, 'document_id': doc_id,
             'normalized_document_sha256': text_sha,
             'document_draw_key': key, 'role': role}
            for n, (key, doc_id, text_sha) in enumerate(chosen)]


def select(source_path):
    plan = load(HERE / 'draw-plan.json')
    registry = load(HERE / 'eligibility-manifest.json')
    selection = load(HERE / 'document-selection.json')
    if sha(source_path) != SOURCE_SHA or plan['source_sha256'] != SOURCE_SHA:
        raise ValueError('Pinned original source changed')
    if sha(HERE / 'eligibility-manifest.json') != plan['eligibility_manifest_sha256']:
        raise ValueError('Pinned identity registry changed')
    if plan['hypotheses'] != ['nda-17', 'nda-7', 'nda-3']:
        raise ValueError('Frozen predicate set changed')
    source = load(source_path)
    docs = {doc['id']: doc for doc in source['documents']}
    old = set(registry['excluded_document_ids'])
    reserved = set(registry['reserved_confirmation_document_ids'])
    eligible = set(docs) - old - reserved
    train_pool = set(registry['training_sanity_reuse_document_ids'])
    if (len(docs) != 423 or len(old) != 173 or len(reserved) != 16
            or old & reserved or len(eligible) != 234
            or eligible != set(registry['eligible_document_ids'])
            or len(train_pool) != 24 or not train_pool <= old):
        raise ValueError('Exposed/reserved/eligible/TRAIN identities changed')
    cross_ids = {x['document_id'] for x in registry['cross_split_documents']}
    cross_hashes = {x['normalized_document_sha256'] for x in registry['cross_split_documents']}
    blocked = set(registry['old_and_reserved_normalized_document_sha256']) | cross_hashes
    hashes = {i: hashlib.sha256(norm(docs[i]['text']).encode()).hexdigest() for i in docs}
    if eligible & cross_ids or {hashes[i] for i in eligible} & blocked:
        raise ValueError('New DEV collides with prior, reserved or official split')
    if train_pool & (reserved | cross_ids) or {hashes[i] for i in train_pool} & (
            cross_hashes | {hashes[i] for i in reserved}):
        raise ValueError('Reused TRAIN collides with reserved or official split')
    dev = rank(eligible, docs, plan['salt'])[:8]
    train = rank(train_pool, docs, plan['train_sanity_salt'])[:2]
    if (selection['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or selection['documents'] != role_records(dev, 'dev')
            or selection['train_sanity_documents'] != role_records(train, 'train_sanity')
            or selection['gold_access_for_selection'] is not False):
        raise ValueError('Frozen source-only role assignment changed')
    return plan, source, {'dev': dev, 'train_sanity': train}


def draw(source_path, role='dev'):
    if role not in ('dev', 'train_sanity'):
        raise ValueError('Unfrozen role')
    plan, source, groups = select(source_path)
    docs = {doc['id']: doc for doc in source['documents']}
    result = []
    # Identity/role freeze is verified before any selected annotation projection.
    for n, (key, doc_id, text_sha) in enumerate(groups[role]):
        doc = docs[doc_id]
        if len(doc['annotation_sets']) != 1:
            raise ValueError('Ambiguous source annotation')
        for hypothesis_id in plan['hypotheses']:
            positive = source['labels'][hypothesis_id]['hypothesis']
            inp = {'state': doc['text'], 'questions': {'decision': {
                'type': 'choice', 'instructions': INSTRUCTION,
                'criteria': {'Yes': positive, 'No': 'The agreement does not establish the following: ' + positive}}}}
            label = doc['annotation_sets'][0]['annotations'][hypothesis_id]['choice']
            result.append({
                'id': f'original-contractnli:train:epoch12:{role}:{doc_id}:{hypothesis_id}',
                'split': role,
                'source': 'stanfordnlp/contract-nli@eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/train.json',
                'source_group': 'original-contractnli:' + str(doc_id), 'input': inp,
                'evaluation': {'type': 'choice', 'gold': LABELS[label], 'labels': ['Yes', 'No'],
                               'source_family': hypothesis_id, 'group': 'original-contractnli:' + str(doc_id),
                               'gold_distribution': None, 'original_threeway_label': label},
                'input_sha256': hashlib.sha256(canonical(inp).encode()).hexdigest(),
                'normalized_input_sha256': hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),
                'provenance': {'document_id': doc_id, 'file_name': doc['file_name'], 'source_split': 'train',
                               'hypothesis_id': hypothesis_id, 'document_draw_key': key, 'document_rank': n,
                               'normalized_document_sha256': text_sha, 'license': 'CC-BY-4.0'},
                'exposure': ('Already-exposed TRAIN diagnostic only; no fitting, precision/model selection or fresh generalization.'
                             if role == 'train_sanity' else
                             'New project-unused DEV for one frozen gate; no fitting or calibration. Public-source pilot; pretraining overlap unknown.')})
    return result


def allow(rows, data_sha, role='dev'):
    records = []
    for row in rows:
        inp = row['input']
        record = {'id': row['id'], 'input_sha256': row['input_sha256'],
                  'source_group': row['source_group'], 'hypothesis_id': row['provenance']['hypothesis_id']}
        if role == 'train_sanity':
            record.update(
                state_sha256=hashlib.sha256(inp['state'].encode()).hexdigest(),
                questions_sha256=hashlib.sha256(canonical(inp['questions']).encode()).hexdigest(),
                wire_input_sha256=hashlib.sha256(json.dumps(inp, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
        records.append(record)
    return {'schema_version': 1, 'role': role, 'queries': len(rows),
            'document_groups': len({x['source_group'] for x in rows}), 'data_sha256': data_sha,
            'threeway_classes': list(LABELS), 'binary_mapping': LABELS, 'records': records,
            'input_hash_recipe': 'UTF8 JSON ensure_ascii=False,sort_keys=True,separators=(comma,colon),allow_nan=False over state/questions',
            'contains_labels_or_inputs': False, 'fit_permitted': False,
            'model_precision_or_threshold_selection_permitted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=True)
    for role, filename, allowname in [('dev', 'development24.jsonl', 'dev-allowlist.json'),
                                     ('train_sanity', 'train-sanity6.jsonl', 'train-allowlist.json')]:
        rows = draw(args.source, role)
        target = args.output_dir / filename
        with target.open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        with (args.output_dir / allowname).open('x') as stream:
            stream.write(json.dumps(allow(rows, sha(target), role), indent=2) + '\n')
        print(json.dumps({'role': role, 'queries': len(rows), 'sha256': sha(target)}))
