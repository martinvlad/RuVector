"""Freeze DEV24 IDs and reuse only exact, model-unused epoch16 CONF24 identities.

No inference, fitting, balancing or redraw. Original choices are accessed only
after a source freeze; confirmation additionally requires the live worker gates.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_COMMIT = 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
PARENT = 'cec9a7bbdc8c4ced83e5d1b826bce67da18339df'
OLD_CONF_SHA = '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
ORIGIN_ALLOW_PATH = 'experiments/sota-2026-10-22/legal-transfer/epoch16/confirmation-input-allowlist.json'
ORIGIN_ALLOW_SHA = 'c3970a800cdc609bcd8a1324d0def90ad11853c3f68c3b7eb9faafce8e720fdb'
SALT = 'ruvector-sota-2026-10-22:epoch17:large-typed-reader:DEV:v1:'
DEV_IDS = [264, 214, 297, 570, 365, 281, 483, 139]
CONF_IDS = [308, 159, 284, 501, 267, 494, 261, 313]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
LABELS = {'Entailment': 'Yes', 'Contradiction': 'No', 'NotMentioned': 'No'}
INSTRUCTION = ('Determine whether the agreement entails the supplied hypothesis. '
               'Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.')
FREEZE_MEMBERS = ['build.py', 'draw-plan.json', 'eligibility-manifest.json',
                  'reserved-confirmation-reuse.json', 'document-selection.json']


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
    reuse = read(HERE / 'reserved-confirmation-reuse.json')
    if (plan['checkpoint_parent'] != PARENT or plan['source_sha256'] != SOURCE_SHA
            or plan['source_commit'] != SOURCE_COMMIT or plan['salt'] != SALT
            or plan['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or plan['reserved_reuse_manifest_sha256'] != sha(HERE / 'reserved-confirmation-reuse.json')
            or plan['hypotheses'] != HYPOTHESES or plan['dev_documents'] != 8
            or plan['confirmation_documents'] != 8 or plan['train'] or plan['calibration']
            or plan['old_confirmation_preserved_sha256'] != OLD_CONF_SHA
            or plan['DEV_document_ids_fixed_once'] != DEV_IDS
            or plan['confirmation_document_ids_fixed_from16'] != CONF_IDS
            or reuse['document_ids'] != CONF_IDS or reuse['bank_model_unconsumed'] is not True
            or reuse['origin_allowlist']['path'] != ORIGIN_ALLOW_PATH
            or reuse['origin_allowlist']['sha256'] != ORIGIN_ALLOW_SHA):
        raise ValueError('Frozen ID-only role plan or exact unused-bank origin changed')
    exposed = set(registry['excluded_document_ids'])
    reserved = set(registry['reserved_confirmation_document_ids'])
    eligible = set(registry['eligible_document_ids'])
    if (len(exposed) != 205 or len(reserved) != 24 or len(eligible) != 194
            or exposed & reserved or exposed & eligible or reserved & eligible
            or len(exposed | reserved | eligible) != 423 or not set(CONF_IDS) <= reserved):
        raise ValueError('205-exposed/24-reserved/194-unreserved partition changed')
    ranks = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in eligible)
    if [i for _, i in ranks[:8]] != DEV_IDS:
        raise ValueError('One fixed DEV8 ID-only draw changed; never redraw')
    selected = [{'document_rank': n, 'document_id': i, 'document_draw_key': key, 'role': 'dev'}
                for n, (key, i) in enumerate(ranks[:8])]
    origin = {d['document_id']: d for d in read(HERE.parents[0] / 'epoch16/document-selection.json')['documents']
              if d['role'] == 'confirmation'}
    selected += [dict(origin[i], role='confirmation', reused_origin_epoch=16) for i in CONF_IDS]
    return plan, registry, selected


def select_only():
    _, _, selected = selection_metadata()
    selection = {'schema_version': 1, 'epoch': 17, 'frozen_at': datetime.now(timezone.utc).isoformat(),
        'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
        'eligibility_manifest_sha256': sha(HERE / 'eligibility-manifest.json'),
        'reserved_reuse_manifest_sha256': sha(HERE / 'reserved-confirmation-reuse.json'),
        'builder_sha256': sha(__file__), 'source_sha256': SOURCE_SHA,
        'documents': selected, 'hypotheses': HYPOTHESES, 'train': [], 'calibration': [],
        'selection': 'First8 SHA256(salt+str(documentID)) ranks among194unreservedIDs for DEV; exact unconsumed epoch16 CONF24 reused unchanged. No new CONF draw.',
        'source_corpus_opened_for_selection': False, 'gold_accessed_for_selection': False,
        'uses_text_length_labels_outcomes_or_class_presence': False,
        'old_reserved_confirmation48_parsed': False, 'confirmation_roles_relabelled_or_newly_drawn': False,
        'if_collision_or_missing_class': 'Abort relevant acceptance if required; never redraw/rebalance.',
        'query_identity': 'Exact originaltrain source SHA, fixed IDs, three hypotheses and frozen builder pin all input/gold projections before annotation access.'}
    write_new(HERE / 'document-selection.json', selection)
    return {'status': 'DEV24_AND_EXACT_UNUSED_CONF24_ROLES_FROZEN_NO_GOLD', 'documents': selected,
            'selection_sha256': sha(HERE / 'document-selection.json'), 'source_or_annotation_choices_accessed': False}


def verify_source_freeze(path, expected, project):
    if not path or not expected or len(expected) != 64 or sha(path) != expected:
        raise PermissionError('Exact root source-freeze receipt required before corpus/input/choice projection')
    freeze = read(path)
    members = {r['path']: r for r in freeze['files']}
    for name in FREEZE_MEMBERS:
        member = HERE / name
        record = members.get(str(member.relative_to(Path(project))))
        if not record or record['bytes'] != member.stat().st_size or record['sha256'] != sha(member):
            raise PermissionError('Root source freeze does not bind current role/builder member: ' + name)
    if freeze['source_checkpoint'] != PARENT:
        raise PermissionError('Root source freeze checkpoint changed')


def verify_reuse_origin(project):
    reuse = read(HERE / 'reserved-confirmation-reuse.json')
    origin = {}
    for key in ('origin_allowlist', 'origin_validation', 'origin_selection', 'origin_retirement',
                'origin_eligibility', 'origin_source_freeze'):
        ref = reuse[key]
        path = Path(project) / ref['path']
        if path.stat().st_size != ref['bytes'] or sha(path) != ref['sha256']:
            raise ValueError('Immutable unused-bank origin changed: ' + key)
        origin[key] = read(path)
    if (reuse['origin_allowlist']['path'] != ORIGIN_ALLOW_PATH
            or reuse['origin_allowlist']['sha256'] != ORIGIN_ALLOW_SHA
            or origin['origin_allowlist']['source_sha256'] != SOURCE_SHA
            or origin['origin_allowlist']['annotation_choices_accessed'] != 0
            or origin['origin_retirement']['verification']['both_confirmation_banks_project_model_unused'] is not True
            or (Path(project) / ORIGIN_ALLOW_PATH).with_name('confirmation24.jsonl').exists()):
        raise ValueError('Origin CONF24 is not the exact verified model-unused bank')
    frozen = {(r['source_group'], r['hypothesis_id']): r for r in origin['origin_allowlist']['records']}
    validated = {(r['selection']['document_id'], r['hypothesis_id']): r
                 for r in origin['origin_validation']['records'] if r['selection']['role'] == 'confirmation'}
    if len(reuse['records']) != 24 or len(frozen) != 24 or len(validated) != 24:
        raise ValueError('Exact unused-bank cardinality changed')
    for r in reuse['records']:
        old = frozen[(r['source_group'], r['hypothesis_id'])]
        v = validated[(r['document_id'], r['hypothesis_id'])]
        if any(r[k] != old[k] for k in old) or any(r[k] != v[k] for k in
                ('input_sha256', 'normalized_input_sha256', 'normalized_document_sha256')):
            raise ValueError('Exact source/input/normalized reuse identity changed')
    old_hashes = set(origin['origin_eligibility']['old_and_reserved_normalized_document_sha256'])
    if old_hashes & {r['normalized_document_sha256'] for r in reuse['records']}:
        raise ValueError('Reused CONF document collides with an older exposed/reserved identity')
    return reuse


def exact_reuse_match(role, record, reused):
    if role != 'confirmation':
        return False
    return (record['selection']['document_id'] == reused['document_id']
            and record['hypothesis_id'] == reused['hypothesis_id']
            and all(record[k] == reused[k] for k in
                    ('input_sha256', 'normalized_input_sha256', 'normalized_document_sha256')))


def reject_prior_collision(role, record, prior, reuse):
    matches = [r for r in reuse['records'] if exact_reuse_match(role, record, r)]
    if role == 'confirmation' and len(matches) != 1:
        raise ValueError('CONF requires exact unused source16 input/normalized/document identity')
    for path, old in prior:
        if (record['input_sha256'] == old.get('input_sha256')
                or record['normalized_input_sha256'] == old.get('normalized_input_sha256')):
            if (len(matches) != 1 or path != ORIGIN_ALLOW_PATH
                    or any(old.get(k) != matches[0][k] for k in
                           ('id', 'input_sha256', 'normalized_input_sha256', 'source_group', 'hypothesis_id'))):
                raise ValueError('Historical exact/normalized collision outside exact unused CONF origin')


def validate_inputs(source_path, project, freeze_path, freeze_sha):
    verify_source_freeze(freeze_path, freeze_sha, project)
    _, registry, selected = selection_metadata()
    reuse = verify_reuse_origin(project)
    chosen = read(HERE / 'document-selection.json')
    if (chosen['builder_sha256'] != sha(__file__) or chosen['documents'] != selected
            or chosen['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or chosen['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or chosen['reserved_reuse_manifest_sha256'] != sha(HERE / 'reserved-confirmation-reuse.json')
            or chosen['source_corpus_opened_for_selection'] is not False
            or chosen['gold_accessed_for_selection'] is not False or sha(source_path) != SOURCE_SHA):
        raise ValueError('Frozen selection/builder/source changed')
    source = read(source_path)  # First corpus parse, after all freeze/origin checks. No choice access here.
    docs = {d['id']: d for d in source['documents']}
    expected = set().union(*(set(registry[k]) for k in
                            ('excluded_document_ids', 'reserved_confirmation_document_ids', 'eligible_document_ids')))
    if len(docs) != 423 or len(source['documents']) != 423 or set(docs) != expected:
        raise ValueError('Official423-document identity set changed')
    blocked_ids = {d['document_id'] for d in registry['cross_split_documents']}
    cross_hashes = {d['normalized_document_sha256'] for d in registry['cross_split_documents']}
    blocked_hashes = set(registry['old_and_reserved_normalized_document_sha256']) | cross_hashes
    allowed_conf_hashes = {r['normalized_document_sha256'] for r in reuse['records']}
    prior = []
    for path in sorted((Path(project) / 'experiments/sota-2026-10-22/legal-transfer').glob('epoch*/*allowlist*.json')):
        if path.parent != HERE:
            prior += [(str(path.relative_to(Path(project))), r) for r in read(path).get('records', [])]
    prepared, seen = [], set()
    for item in selected:
        d = docs[item['document_id']]
        normalized = hashlib.sha256(norm(d['text']).encode()).hexdigest()
        allowed = item['role'] == 'confirmation' and normalized in allowed_conf_hashes
        if (d['id'] in blocked_ids or normalized in cross_hashes or normalized in seen
                or (normalized in blocked_hashes and not allowed)):
            raise ValueError('Prior/reserved/cross-split/within-draw document collision; no redraw')
        seen.add(normalized)
        for h in HYPOTHESES:
            positive = source['labels'][h]['hypothesis']
            inputs = {'state': d['text'], 'questions': {'decision': {'type': 'choice',
                'instructions': INSTRUCTION, 'criteria': {'Yes': positive,
                    'No': 'The agreement does not establish the following: ' + positive}}}}
            r = {'selection': item, 'hypothesis_id': h, 'normalized_document_sha256': normalized,
                 'input': inputs, 'input_sha256': hashlib.sha256(canonical(inputs).encode()).hexdigest(),
                 'normalized_input_sha256': hashlib.sha256(norm(canonical(inputs)).encode()).hexdigest()}
            reject_prior_collision(item['role'], r, prior, reuse)
            prepared.append(r)
    assert len(prepared) == 48 and len(seen) == 16
    report = {'schema_version': 1, 'status': 'FROZEN_INPUT_IDENTITIES_AND_STRICT_REUSE_COLLISIONS_PASS',
        'source_sha256': SOURCE_SHA, 'selection_sha256': sha(HERE / 'document-selection.json'),
        'builder_sha256': sha(__file__), 'root_source_freeze_sha256': freeze_sha,
        'queries': 48, 'DEV_queries': 24, 'CONF_queries': 24, 'document_groups': 16,
        'historical_allowlist_records_checked': len(prior), 'exact_unused16_CONF_reused_queries': 24,
        'origin_allowlist_sha256': ORIGIN_ALLOW_SHA, 'unapproved_exact_or_normalized_collisions': 0,
        'fuzzy_or_pretraining_overlap_verified': False, 'DEV_annotation_choices_accessed': 0,
        'CONF_annotation_choices_accessed': 0,
        'records': [{k: v for k, v in r.items() if k != 'input'} for r in prepared]}
    return source, docs, prepared, report


def inputs_only(source_path, project, freeze_path, freeze_sha):
    _, _, prepared, report = validate_inputs(source_path, project, freeze_path, freeze_sha)
    write_new(HERE / 'pre-gold-input-validation.json', report)
    for role in ('dev', 'confirmation'):
        records = [r for r in prepared if r['selection']['role'] == role]
        rows = [{'id': row_id(role, r), 'input': r['input'], 'input_sha256': r['input_sha256']} for r in records]
        write_new(HERE / (role + '-inputs-only.json'), {'schema_version': 1, 'role': role, 'records': rows})
        write_new(HERE / (role + '-input-allowlist.json'), {
            'schema_version': 1, 'role': role, 'queries': 24, 'document_groups': 8,
            'source_sha256': SOURCE_SHA, 'selection_sha256': sha(HERE / 'document-selection.json'),
            'projection_builder_sha256': sha(__file__), 'projected_data_sha256': None,
            'records': [allow_record(row_id(role, r), r) for r in records],
            'contains_labels_or_inputs': False, 'annotation_choices_accessed': 0,
            'recipe_frozen_before_projection': True,
            'data_file_hash_bound_only_after_later_authorized_choice_projection': True})
    return {'status': report['status'], 'DEV_annotation_choices_accessed': 0,
            'CONF_annotation_choices_accessed': 0, 'validation_sha256': sha(HERE / 'pre-gold-input-validation.json')}


def row_id(role, record):
    return f"original-contractnli:train:epoch17:{role}:{record['selection']['document_id']}:{record['hypothesis_id']}"


def allow_record(identifier, record):
    return {'id': identifier, 'input_sha256': record['input_sha256'],
            'normalized_input_sha256': record['normalized_input_sha256'],
            'source_group': 'original-contractnli:' + str(record['selection']['document_id']),
            'hypothesis_id': record['hypothesis_id']}


def verify_confirmation_worker(project, freeze_sha):
    root = Path(project) / 'experiments/sota-2026-10-22/epoch17'
    plan_path = root / 'plan.json'
    plan_sha = sha(plan_path)
    plan = read(plan_path)
    lock = read(root / 'confirmation-selection-lock.json')
    dev_path = root / 'runs/development/development-comparison.json'
    runtime_path = root / 'runtime-admission.json'
    attempt = read(root / 'runs/confirmation/attempt.json')
    popen = read(root / 'runs/confirmation/popen-attempt.json')
    if (lock['plan_sha256'] != plan_sha or lock['development_comparison_sha256'] != sha(dev_path)
            or lock['runtime_admission_sha256'] != sha(runtime_path)
            or read(dev_path)['frozen_development_gate_passed'] is not True
            or read(runtime_path)['allowed'] is not True
            or plan['lazy_confirmation']['source_freeze_sha256'] != freeze_sha
            or attempt['phase'] != 'confirmation' or popen['phase'] != 'confirmation'
            or attempt['source_plan_sha256'] != plan_sha or popen['source_plan_sha256'] != plan_sha
            or attempt['pid'] != os.getpid() or attempt['pgid'] != os.getpgrp()
            or os.getpid() != os.getpgrp()):
        raise PermissionError('Lazy CONF choices require exact passing DEV/runtime gates and current durable worker attempt')


def materialize(role, source_path, project, freeze_path, freeze_sha, authorized):
    if role not in ('dev', 'confirmation') or not authorized:
        raise PermissionError('Explicit role-specific root authorization required before annotation-choice projection')
    if role == 'confirmation':
        verify_confirmation_worker(project, freeze_sha)  # Before corpus parse or any choice.
    source, docs, prepared, validation = validate_inputs(source_path, project, freeze_path, freeze_sha)
    selected = [r for r in prepared if r['selection']['role'] == role]
    write_new(HERE / (role + '-pre-gold-validation.json'), validation)
    rows = []
    for r in selected:
        item, h = r['selection'], r['hypothesis_id']
        d = docs[item['document_id']]
        if len(d['annotation_sets']) != 1:
            raise ValueError('Ambiguous source annotation')
        label = d['annotation_sets'][0]['annotations'][h]['choice']
        if label not in LABELS:
            raise ValueError('Unknown original threeway label')
        group = 'original-contractnli:' + str(d['id'])
        rows.append({'id': row_id(role, r), 'split': role,
            'source': 'stanfordnlp/contract-nli@' + SOURCE_COMMIT + '/train.json',
            'source_group': group, 'input': r['input'],
            'evaluation': {'type': 'choice', 'gold': LABELS[label], 'labels': ['Yes', 'No'],
                'source_family': h, 'group': group, 'gold_distribution': None, 'original_threeway_label': label},
            'input_sha256': r['input_sha256'], 'normalized_input_sha256': r['normalized_input_sha256'],
            'provenance': {'document_id': d['id'], 'file_name': d['file_name'], 'source_split': 'train',
                'hypothesis_id': h, 'document_draw_key': item['document_draw_key'],
                'document_rank': item['document_rank'], 'normalized_document_sha256': r['normalized_document_sha256'],
                'reused_origin_epoch': 16 if role == 'confirmation' else None,
                'origin_input_allowlist_sha256': ORIGIN_ALLOW_SHA if role == 'confirmation' else None,
                'license': 'CC-BY-4.0'},
            'exposure': 'Frozen project-unused role; CONF is exact unused16 bank. No training/calibration/label selection. Public-source NDA pilot; pretraining/fuzzy overlap unknown.'})
    filename = 'development24.jsonl' if role == 'dev' else 'confirmation24.jsonl'
    with (HERE / filename).open('x') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n')
    allow = {'schema_version': 1, 'role': role, 'queries': 24, 'document_groups': 8,
        'data_sha256': sha(HERE / filename), 'threeway_classes': list(LABELS), 'binary_mapping': LABELS,
        'records': [allow_record(row['id'], r) for row, r in zip(rows, selected)],
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
            if a.materialize_authorized:
                ap.error('Input-only projection cannot authorize choices')
            result = inputs_only(a.source, a.project, a.source_freeze, a.expected_source_freeze_sha)
        else:
            result = materialize(a.materialize_role, a.source, a.project, a.source_freeze,
                                 a.expected_source_freeze_sha, a.materialize_authorized)
    print(json.dumps(result, indent=2))
