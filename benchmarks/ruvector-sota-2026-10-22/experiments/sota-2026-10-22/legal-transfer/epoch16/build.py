"""Freeze one ID-only DEV24/CONF24 draw; project choices only after source freeze.

Engineering/projection utility only: no inference, fitting, model selection,
case balancing or redraw. The older reserved CONF48 is never parsed.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_COMMIT = 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
PARENT = 'e4360639a5ff1577263569b863bd7a594cea2ff2'
OLD_CONF_SHA = '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
SALT = 'ruvector-sota-epoch16-new-dev24-confirmation24-v1|'
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
LABELS = {'Entailment': 'Yes', 'Contradiction': 'No', 'NotMentioned': 'No'}
INSTRUCTION = ('Determine whether the agreement entails the supplied hypothesis. '
               'Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def norm(text):
    return ' '.join(text.casefold().split())


def write_new(path, value):
    with Path(path).open('x') as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def selection_metadata():
    plan = read(HERE / 'draw-plan.json')
    registry = read(HERE / 'eligibility-manifest.json')
    if (plan['checkpoint_parent'] != PARENT or plan['source_sha256'] != SOURCE_SHA
            or plan['source_commit'] != SOURCE_COMMIT or plan['salt'] != SALT
            or plan['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or plan['hypotheses'] != HYPOTHESES or plan['dev_documents'] != 8
            or plan['confirmation_documents'] != 8 or plan['train'] or plan['calibration']
            or plan['old_confirmation_preserved_sha256'] != OLD_CONF_SHA):
        raise ValueError('Frozen ID-only plan changed')
    exposed = set(registry['excluded_document_ids'])
    reserved = set(registry['reserved_confirmation_document_ids'])
    eligible = set(registry['eligible_document_ids'])
    if (len(exposed) != 197 or len(reserved) != 16 or len(eligible) != 210
            or exposed & reserved or exposed & eligible or reserved & eligible
            or len(exposed | reserved | eligible) != 423):
        raise ValueError('Exposure/reservation/eligibility identity partition changed')
    ranks = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in eligible)
    selected = [{'document_rank': n, 'document_id': i, 'document_draw_key': key,
                 'role': 'dev' if n < 8 else 'confirmation'}
                for n, (key, i) in enumerate(ranks[:16])]
    return plan, registry, selected


def select_only():
    plan, registry, selected = selection_metadata()
    selection = {'schema_version': 1, 'epoch': 16,
        'frozen_at': datetime.now(timezone.utc).isoformat(),
        'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
        'eligibility_manifest_sha256': sha(HERE / 'eligibility-manifest.json'),
        'builder_sha256': sha(__file__), 'source_sha256': SOURCE_SHA,
        'documents': selected, 'hypotheses': HYPOTHESES, 'train': [], 'calibration': [],
        'selection': 'First16 SHA256(salt+str(documentID)) ranks among210eligibleIDs: ranks0..7 DEV,8..15 CONF; one draw, no balancing/redraw.',
        'source_corpus_opened_for_selection': False, 'gold_accessed_for_selection': False,
        'uses_text_length_labels_outcomes_or_class_presence': False,
        'old_reserved_confirmation48_parsed': False,
        'if_collision_or_missing_class': 'Abort relevant acceptance if required; never redraw/rebalance.',
        'query_identity': 'Exact originaltrain source SHA + chosen IDs + fixed3hypotheses + builder fixes all48 input/gold projections before annotation access.'}
    write_new(HERE / 'document-selection.json', selection)
    return {'status': 'DEV24_CONF24_ID_ROLES_FROZEN_NO_GOLD', 'documents': selected,
            'selection_sha256': sha(HERE / 'document-selection.json'),
            'source_or_annotation_choices_accessed': False}


def verify_source_freeze(path, expected):
    if not path or not expected or len(expected) != 64 or sha(path) != expected:
        raise PermissionError('Exact root source-freeze receipt required before corpus/input/choice projection')
    read(path)  # Valid immutable JSON receipt, externally bound by root/auditor.


def validate_inputs(source_path, project, freeze_path, freeze_sha):
    verify_source_freeze(freeze_path, freeze_sha)
    plan, registry, selected = selection_metadata()
    chosen = read(HERE / 'document-selection.json')
    if (chosen['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or chosen['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or chosen['builder_sha256'] != sha(__file__) or chosen['documents'] != selected
            or chosen['source_corpus_opened_for_selection'] is not False
            or chosen['gold_accessed_for_selection'] is not False or sha(source_path) != SOURCE_SHA):
        raise ValueError('Frozen selection/builder/source changed')
    source = read(source_path)
    docs = {d['id']: d for d in source['documents']}
    expected = (set(registry['excluded_document_ids']) | set(registry['reserved_confirmation_document_ids'])
                | set(registry['eligible_document_ids']))
    if len(docs) != 423 or set(docs) != expected:
        raise ValueError('Official423-document identity set changed')
    blocked_ids = {d['document_id'] for d in registry['cross_split_documents']}
    blocked_hashes = (set(registry['old_and_reserved_normalized_document_sha256'])
                      | {d['normalized_document_sha256'] for d in registry['cross_split_documents']})
    prior, prior_norm = set(), set()
    for path in sorted((Path(project) / 'experiments/sota-2026-10-22/legal-transfer').glob('epoch*/*allowlist*.json')):
        if path.parent == HERE:
            continue
        for r in read(path).get('records', []):
            if r.get('input_sha256'): prior.add(r['input_sha256'])
            if r.get('normalized_input_sha256'): prior_norm.add(r['normalized_input_sha256'])
    prepared, seen = [], set()
    for item in selected:
        d = docs[item['document_id']]
        normalized = hashlib.sha256(norm(d['text']).encode()).hexdigest()
        if d['id'] in blocked_ids or normalized in blocked_hashes or normalized in seen:
            raise ValueError('Prior/reserved/cross-split/within-draw document collision; no redraw')
        seen.add(normalized)
        for h in HYPOTHESES:
            positive = source['labels'][h]['hypothesis']
            inputs = {'state': d['text'], 'questions': {'decision': {'type': 'choice',
                'instructions': INSTRUCTION, 'criteria': {'Yes': positive,
                    'No': 'The agreement does not establish the following: ' + positive}}}}
            digest = hashlib.sha256(canonical(inputs).encode()).hexdigest()
            normalized_digest = hashlib.sha256(norm(canonical(inputs)).encode()).hexdigest()
            if digest in prior or normalized_digest in prior_norm:
                raise ValueError('Exact/normalized prior input collision; no redraw')
            prepared.append({'selection': item, 'hypothesis_id': h,
                'normalized_document_sha256': normalized, 'input': inputs,
                'input_sha256': digest, 'normalized_input_sha256': normalized_digest})
    assert len(prepared) == 48 and len(seen) == 16
    report = {'schema_version': 1, 'status': 'FROZEN_INPUT_IDENTITIES_AND_COLLISIONS_PASS',
        'source_sha256': SOURCE_SHA, 'selection_sha256': sha(HERE / 'document-selection.json'),
        'builder_sha256': sha(__file__), 'root_source_freeze_sha256': freeze_sha,
        'queries': 48, 'DEV_queries': 24, 'CONF_queries': 24, 'document_groups': 16,
        'prior_input_hashes_checked': len(prior), 'prior_normalized_input_hashes_checked': len(prior_norm),
        'exact_or_normalized_collisions': 0, 'fuzzy_or_pretraining_overlap_verified': False,
        'DEV_annotation_choices_accessed': 0, 'CONF_annotation_choices_accessed': 0,
        'records': [{k: v for k, v in r.items() if k != 'input'} for r in prepared]}
    return source, docs, prepared, report


def inputs_only(source_path, project, freeze_path, freeze_sha):
    source, docs, prepared, report = validate_inputs(source_path, project, freeze_path, freeze_sha)
    write_new(HERE / 'pre-gold-input-validation.json', report)
    for role in ('dev', 'confirmation'):
        records = [r for r in prepared if r['selection']['role'] == role]
        rows = [{'id': f"original-contractnli:train:epoch16:{role}:{r['selection']['document_id']}:{r['hypothesis_id']}",
                 'input': r['input'], 'input_sha256': r['input_sha256']} for r in records]
        write_new(HERE / (role + '-inputs-only.json'), {'schema_version': 1, 'role': role, 'records': rows})
        write_new(HERE / (role + '-input-allowlist.json'), {
            'schema_version': 1, 'role': role, 'queries': 24, 'document_groups': 8,
            'source_sha256': SOURCE_SHA, 'selection_sha256': sha(HERE / 'document-selection.json'),
            'projection_builder_sha256': sha(__file__), 'projected_data_sha256': None,
            'records': [{'id': x['id'], 'input_sha256': x['input_sha256'],
                'normalized_input_sha256': r['normalized_input_sha256'],
                'source_group': 'original-contractnli:' + str(r['selection']['document_id']),
                'hypothesis_id': r['hypothesis_id']} for x, r in zip(rows, records)],
            'contains_labels_or_inputs': False, 'annotation_choices_accessed': 0,
            'recipe_frozen_before_projection': True,
            'data_file_hash_bound_only_after_later_authorized_choice_projection': True})
    return {'status': report['status'], 'DEV_annotation_choices_accessed': 0,
            'CONF_annotation_choices_accessed': 0, 'validation_sha256': sha(HERE / 'pre-gold-input-validation.json')}


def materialize(role, source_path, project, freeze_path, freeze_sha, authorized):
    if role not in ('dev', 'confirmation') or not authorized:
        raise PermissionError('Explicit role-specific root authorization required before annotation-choice projection')
    source, docs, prepared, validation = validate_inputs(source_path, project, freeze_path, freeze_sha)
    selected = [r for r in prepared if r['selection']['role'] == role]
    write_new(HERE / (role + '-pre-gold-validation.json'), validation)
    rows = []
    for r in selected:
        item, h = r['selection'], r['hypothesis_id']
        d = docs[item['document_id']]
        if len(d['annotation_sets']) != 1: raise ValueError('Ambiguous source annotation')
        label = d['annotation_sets'][0]['annotations'][h]['choice']
        if label not in LABELS: raise ValueError('Unknown original threeway label')
        group = 'original-contractnli:' + str(d['id'])
        rows.append({'id': f"original-contractnli:train:epoch16:{role}:{d['id']}:{h}",
            'split': role, 'source': 'stanfordnlp/contract-nli@' + SOURCE_COMMIT + '/train.json',
            'source_group': group, 'input': r['input'],
            'evaluation': {'type': 'choice', 'gold': LABELS[label], 'labels': ['Yes', 'No'],
                'source_family': h, 'group': group, 'gold_distribution': None, 'original_threeway_label': label},
            'input_sha256': r['input_sha256'], 'normalized_input_sha256': r['normalized_input_sha256'],
            'provenance': {'document_id': d['id'], 'file_name': d['file_name'], 'source_split': 'train',
                'hypothesis_id': h, 'document_draw_key': item['document_draw_key'],
                'document_rank': item['document_rank'], 'normalized_document_sha256': r['normalized_document_sha256'],
                'license': 'CC-BY-4.0'},
            'exposure': 'One frozen ID-only project-unused role; no training/calibration/label selection. Public-source NDA pilot; upstream pretraining/fuzzy overlap unknown.'})
    filename = 'development24.jsonl' if role == 'dev' else 'confirmation24.jsonl'
    with (HERE / filename).open('x') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n')
    allow = {'schema_version': 1, 'role': role, 'queries': 24, 'document_groups': 8,
        'data_sha256': sha(HERE / filename), 'threeway_classes': list(LABELS), 'binary_mapping': LABELS,
        'records': [{'id': r['id'], 'input_sha256': r['input_sha256'],
            'normalized_input_sha256': r['normalized_input_sha256'], 'source_group': r['source_group'],
            'hypothesis_id': r['provenance']['hypothesis_id']} for r in rows],
        'contains_labels_or_inputs': False, 'fit_permitted': False, 'model_or_threshold_selection_permitted': False}
    write_new(HERE / (role + '-allowlist.json'), allow)
    receipt = {'schema_version': 1, 'status': 'FROZEN_' + role.upper() + '24_PROJECTED_ONCE',
        'role': role, 'queries': 24, 'document_groups': 8, 'data_sha256': allow['data_sha256'],
        'allowlist_sha256': sha(HERE / (role + '-allowlist.json')), 'builder_sha256': sha(__file__),
        'source_sha256': SOURCE_SHA, 'selection_sha256': sha(HERE / 'document-selection.json'),
        'root_source_freeze_sha256': freeze_sha, 'annotation_choices_projected': 24,
        'other_role_annotation_choices_accessed': 0, 'old_reserved_CONF48_choices_accessed': 0,
        'native_model_fit_paid_GPU_calls': 0, 'CONF_labels_used_for_training_selection': False}
    write_new(HERE / (role + '-materialization.json'), receipt)
    return receipt


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--select-only', action='store_true')
    ap.add_argument('--inputs-only', action='store_true')
    ap.add_argument('--materialize-role', choices=['dev', 'confirmation'])
    ap.add_argument('--materialize-authorized', action='store_true')
    ap.add_argument('--source', type=Path); ap.add_argument('--project', type=Path)
    ap.add_argument('--source-freeze', type=Path); ap.add_argument('--expected-source-freeze-sha')
    a = ap.parse_args()
    if a.select_only:
        if a.source or a.inputs_only or a.materialize_role or a.materialize_authorized:
            ap.error('ID-only selection cannot access source or project choices')
        result = select_only()
    else:
        if not a.source or not a.project or not (a.inputs_only ^ bool(a.materialize_role)):
            ap.error('Source/project and exactly one explicit projection mode required')
        if a.inputs_only:
            if a.materialize_authorized: ap.error('Input-only projection cannot authorize choices')
            result = inputs_only(a.source, a.project, a.source_freeze, a.expected_source_freeze_sha)
        else:
            result = materialize(a.materialize_role, a.source, a.project, a.source_freeze,
                                 a.expected_source_freeze_sha, a.materialize_authorized)
    print(json.dumps(result, indent=2))
