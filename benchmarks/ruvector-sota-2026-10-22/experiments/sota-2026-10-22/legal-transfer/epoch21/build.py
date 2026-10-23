"""Materialize one frozen phase's input text inside its qualified owned worker.

This module never indexes annotation_sets, annotations, or source choices. The
independent post-output scorer owns gold extraction. No input projection is
allowed before source freeze, worker admission and its saved 3/3 semantic pass.
"""
from __future__ import annotations
import hashlib
import json
import os
import math
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PARENT = '0c4392bb8b13a901dc416882f850230c1075fb6a'
PREFIX = 'experiments/sota-2026-10-22/'
REL = PREFIX + 'legal-transfer/epoch21/'
SOURCE_PATH = PREFIX + 'legal-transfer/epoch3/sources/original-train.json'
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_BYTES = 7608211
SOURCE_COMMIT = 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
DEV_IDS = [303, 176, 113, 186, 485, 512, 219, 520]
CONF_IDS = [308, 159, 284, 501, 267, 494, 261, 313]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
SALT = 'ruvector-sota-2026-10-22:epoch21:deberta-v3-large-FP32:DEV:v1:'
INSTRUCTION = ('Determine whether the agreement entails the supplied hypothesis. '
               'Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.')
FREEZE_MEMBERS = ['build.py', 'input-recipe.json', 'eligibility-manifest.json',
                  'draw-plan.json', 'document-selection.json',
                  'reserved-confirmation-reuse.json', 'dev-input-allowlist.json',
                  'confirmation-input-allowlist.json', 'source-qualification.json',
                  'MODEL_QUALIFICATION.json', 'model-assets.lock.json']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def norm(text):
    return ' '.join(text.casefold().split())


def safe_target(project, relative):
    project = Path(project)
    p = PurePosixPath(relative)
    if (not project.is_absolute() or project != project.resolve()
            or p.is_absolute() or not p.parts or any(x in {'.', '..'} for x in p.parts)
            or '\\' in relative):
        raise ValueError('Noncanonical project or unsafe relative path')
    result = project.joinpath(*p.parts)
    if result != result.resolve() or any(x.is_symlink() for x in [result, *result.parents]):
        raise ValueError('Symlink or noncanonical target')
    return result


def exact_ref(project, record):
    if (not isinstance(record, dict) or type(record.get('bytes')) is not int
            or not isinstance(record.get('sha256'), str) or len(record['sha256']) != 64):
        raise ValueError('Malformed frozen file reference')
    path = safe_target(project, record['path'])
    if not path.is_file() or path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
        raise ValueError('Frozen referenced file identity mismatch: ' + record['path'])
    return path


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False,
                                sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def row_id(phase, document_id, hypothesis_id):
    if (phase not in ('dev', 'confirmation') or type(document_id) is not int
            or type(hypothesis_id) is not str or hypothesis_id not in HYPOTHESES):
        raise ValueError('Invalid literal role/document/hypothesis identity')
    return f'original-contractnli:train:epoch21:{phase}:{document_id}:{hypothesis_id}'


def verify_metadata(project):
    project = Path(project)
    if safe_target(project, REL) != HERE:
        raise ValueError('Builder must run from this exact isolated projected project')
    plan = read(HERE / 'draw-plan.json')
    registry = read(HERE / 'eligibility-manifest.json')
    selection = read(HERE / 'document-selection.json')
    reuse = read(HERE / 'reserved-confirmation-reuse.json')
    recipe = read(HERE / 'input-recipe.json')
    if (plan['checkpoint_parent'] != PARENT or plan['source_sha256'] != SOURCE_SHA
            or plan['source_path'] != SOURCE_PATH or plan['source_bytes'] != SOURCE_BYTES
            or plan['source_commit'] != SOURCE_COMMIT or plan['salt'] != SALT
            or plan['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or plan['reserved_reuse_manifest_sha256'] != sha(HERE / 'reserved-confirmation-reuse.json')
            or plan['DEV_document_ids_fixed_once'] != DEV_IDS
            or plan['confirmation_document_ids_fixed_from16'] != CONF_IDS
            or plan['hypotheses'] != HYPOTHESES or plan['train'] or plan['calibration']
            or plan['selection_uses_labels_text_lengths_outcomes_or_class_balancing'] is not False):
        raise ValueError('Frozen metadata role plan changed')
    groups = [registry[k] for k in ('excluded_document_ids', 'reserved_confirmation_document_ids',
                                    'eligible_document_ids')]
    if (any(type(i) is not int for group in groups for i in group)
            or [len(g) for g in groups] != [229, 24, 170]
            or any(len(set(g)) != len(g) for g in groups)
            or any(set(groups[i]) & set(groups[j]) for i in range(3) for j in range(i))
            or len(set().union(*map(set, groups))) != 423):
        raise ValueError('Exact 229/24/170 partition changed')
    ranked = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in groups[2])
    if [i for _, i in ranked[:8]] != DEV_IDS or not set(CONF_IDS) <= set(groups[1]):
        raise ValueError('Fixed DEV draw or reserved confirmation identities changed')
    expected_dev = [{'document_rank': j, 'document_id': i,
                     'document_draw_key': key, 'role': 'dev'}
                    for j, (key, i) in enumerate(ranked[:8])]
    actual_dev = [r for r in selection['documents'] if r['role'] == 'dev']
    actual_conf = [r for r in selection['documents'] if r['role'] == 'confirmation']
    if (actual_dev != expected_dev or [r['document_id'] for r in actual_conf] != CONF_IDS
            or any(type(r['document_id']) is not int for r in selection['documents'])
            or selection['source_corpus_opened_for_selection'] is not False
            or selection['gold_accessed_for_selection'] is not False
            or selection['draw_plan_sha256'] != sha(HERE / 'draw-plan.json')
            or selection['eligibility_manifest_sha256'] != sha(HERE / 'eligibility-manifest.json')
            or selection['reserved_reuse_manifest_sha256'] != sha(HERE / 'reserved-confirmation-reuse.json')
            or reuse['document_ids'] != CONF_IDS or len(reuse['records']) != 24
            or reuse['bank_model_unconsumed'] is not True
            or reuse['case_inputs_or_choices_read_to_build_this_metadata'] is not False):
        raise ValueError('Exact role/input-only selection metadata changed')
    if (recipe['source_checkpoint'] != PARENT or recipe['source']['path'] != SOURCE_PATH
            or recipe['source']['sha256'] != SOURCE_SHA
            or recipe['source']['bytes'] != SOURCE_BYTES or recipe['train'] or recipe['calibration']
            or recipe['annotation_choices_permitted'] is not False):
        raise ValueError('Input-only recipe source or roles changed')
    for key in ('builder', 'selection', 'draw_plan', 'eligibility', 'reserved_confirmation_reuse'):
        exact_ref(project, recipe[key])
    for phase, ids in [('dev', DEV_IDS), ('confirmation', CONF_IDS)]:
        allow = read(exact_ref(project, recipe['roles'][phase]['input_allowlist']))
        expected = [(row_id(phase, i, h), i, h) for i in ids for h in HYPOTHESES]
        actual = [(r['id'], r['document_id'], r['hypothesis_id']) for r in allow['records']]
        if (actual != expected or len({r['id'] for r in allow['records']}) != 24
                or any(type(r['document_id']) is not int or type(r['hypothesis_id']) is not str
                       for r in allow['records'])
                or allow['annotation_choices_accessed'] != 0
                or allow['contains_labels_or_inputs'] is not False
                or allow['recipe_frozen_before_projection'] is not True):
            raise ValueError('Literal frozen phase identity allowlist changed')
    return plan, registry, selection, reuse, recipe


def verify_source_freeze(project, path, expected_sha256):
    path = Path(path)
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or path != path.resolve() or any(x.is_symlink() for x in [path, *path.parents])
            or sha(path) != expected_sha256):
        raise PermissionError('Exact nonsymlink root source freeze required')
    freeze = read(path)
    if freeze['source_checkpoint'] != PARENT:
        raise PermissionError('Source checkpoint differs from frozen parent')
    records = {r['path']: r for r in freeze['files']}
    if len(records) != len(freeze['files']):
        raise PermissionError('Duplicate source-freeze path')
    for name in FREEZE_MEMBERS:
        record = records.get(REL + name)
        if record is None or exact_ref(project, record) != HERE / name:
            raise PermissionError('Input builder/identity file absent from root freeze: ' + name)


def replay_semantic_readiness(raw, semantic, phase, plan_sha, freeze_sha):
    expected = [('semantic-e-v1', 'The lamp is on.', 'The lamp is on.', 'Entailment'),
                ('semantic-c-v1', 'The lamp is not on.', 'The lamp is on.', 'Contradiction'),
                ('semantic-n-v1', 'The box is blue.', 'The lamp is on.', 'NotMentioned')]
    rows = raw.get('canary_forwards', [])
    if (len(rows) != 3 or raw.get('phase') != phase or raw.get('plan_sha256') != plan_sha
            or raw.get('documents') != [] or raw.get('errors') != []
            or semantic.get('canary_forward_receipt_sha256') != hashlib.sha256(canonical(rows).encode()).hexdigest()
            or raw.get('semantic_readiness') != semantic):
        raise PermissionError('Exact saved semantic forwards and current phase are required')
    state = raw.get('fp32_state', {})
    state_sha = semantic.get('fp32_state_sha256')
    if (not isinstance(state_sha, str) or len(state_sha) != 64
            or state.get('state_sha256') != state_sha
            or raw.get('FP32_state_after_canaries_sha256') != state_sha
            or state.get('all_floating_parameters_buffers_FP32') is not True
            or state.get('quantized_modules') != 0 or state.get('devices') != ['cpu']
            or raw.get('tokenizer', {}).get('backend_sha256') != semantic.get('tokenizer_backend_sha256')
            or not isinstance(semantic.get('tokenizer_backend_sha256'), str)
            or len(semantic['tokenizer_backend_sha256']) != 64):
        raise PermissionError('Unchanged FP32 state and tokenizer receipt required')
    counters = raw.get('counters', {})
    for key, count in [('nli_forward_pairs_attempted', 3), ('nli_forward_pairs_completed', 3),
                       ('native_queries_completed', 3), ('native_index_initializations_completed', 1),
                       ('benchmark_documents_completed', 0), ('benchmark_questions_completed', 0),
                       ('BGE_initializations_attempted', 0), ('paid_API_calls', 0), ('GPU_calls', 0),
                       ('quantization_initializations', 0)]:
        if type(counters.get(key)) is not int or counters[key] != count:
            raise PermissionError('Readiness requires only the fixed three engineering forwards/searches')
    order = ['Entailment', 'Contradiction', 'NotMentioned']
    for row, (identifier, premise, hypothesis, label) in zip(rows, expected):
        f = row.get('forward', {})
        if ((row.get('fixture_id'), f.get('premise'), f.get('hypothesis'), row.get('expected_typed_label'))
                != (identifier, premise, hypothesis, label)
                or f.get('model_state_sha256') != state_sha):
            raise PermissionError('Literal canary or actual model state changed')
        logits = f.get('raw_logits')
        values = f.get('raw_probabilities')
        typed = f.get('typed_probabilities')
        if (not isinstance(logits, list) or len(logits) != 3
                or not isinstance(values, list) or len(values) != 3
                or not isinstance(typed, dict) or set(typed) != set(order)
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in logits + values + list(typed.values()))):
            raise PermissionError('Finite original threeway probabilities are required')
        exponents = [math.exp(x - max(logits)) for x in logits]
        total = sum(exponents); replayed = [x / total for x in exponents]
        mapped = {'Entailment': replayed[0], 'Contradiction': replayed[2], 'NotMentioned': replayed[1]}
        if (max(abs(a - b) for a, b in zip(values, replayed)) > 1e-12
                or max(abs(typed[k] - mapped[k]) for k in order) > 1e-12
                or f.get('typed_prediction') != max(order, key=mapped.get)
                or f.get('typed_prediction') != label):
            raise PermissionError('Actual raw E0/N1/C2 logits fail threeway semantic readiness')
    if semantic.get('source_freeze_sha256') != freeze_sha:
        raise PermissionError('Semantic forward receipt belongs to a different source freeze')


def verify_worker(project, phase, freeze_sha):
    root = safe_target(project, PREFIX + 'epoch21/')
    plan_path = root / 'plan.json'
    plan_sha = sha(plan_path)
    plan = read(plan_path)
    run = root / 'runs' / phase
    attempt, popen = read(run / 'attempt.json'), read(run / 'popen-attempt.json')
    semantic = read(run / 'semantic-readiness.json')
    if (type(attempt.get('pid')) is not int or type(attempt.get('pgid')) is not int
            or attempt['pid'] != os.getpid() or attempt['pgid'] != os.getpgrp()
            or os.getpid() != os.getpgrp() or attempt.get('phase') != phase
            or attempt.get('plan_sha256') != plan_sha
            or popen.get('phase') != phase or popen.get('plan_sha256') != plan_sha
            or popen.get('pid') not in (None, os.getpid())):
        raise PermissionError('Exact current durable phase worker markers required')
    if (semantic.get('passed') is not True or type(semantic.get('correct')) is not int
            or type(semantic.get('n')) is not int or semantic['correct'] != 3 or semantic['n'] != 3
            or semantic.get('pid') != os.getpid() or semantic.get('phase') != phase
            or semantic.get('plan_sha256') != plan_sha
            or semantic.get('source_freeze_sha256') != freeze_sha):
        raise PermissionError('Current worker durable 3/3 semantic readiness required before legal inputs')
    raw = read(run / 'raw.json')
    replay_semantic_readiness(raw, semantic, phase, plan_sha, freeze_sha)
    rule = plan['phases'][phase]
    if (rule['input_recipe_path'] != REL + 'input-recipe.json'
            or rule['input_recipe_sha256'] != sha(HERE / 'input-recipe.json')
            or rule['input_allowlist_path'] != REL + phase + '-input-allowlist.json'
            or rule['input_allowlist_sha256'] != sha(HERE / (phase + '-input-allowlist.json'))):
        raise PermissionError('Plan does not bind exact lazy input recipe/identity allowlist')
    if phase == 'confirmation':
        admission = read(root / 'CONFIRMATION_ADMISSION.json')
        if (admission.get('checks_passed') is not True
                or admission.get('independent_DEV_accepted') is not True
                or admission.get('runtime_gate_passed') is not True
                or admission.get('plan_sha256') != plan_sha):
            raise PermissionError('Independent passing DEV and runtime admission required for CONF')
        report = safe_target(project, admission['independent_DEV_report_path'])
        if sha(report) != admission['independent_DEV_report_sha256']:
            raise PermissionError('Independent DEV report identity changed')
        decision = read(report)
        if (decision.get('checks_passed') is not True
                or decision.get('accepted_for_confirmation') is not True
                or decision.get('phase') != 'dev' or decision.get('plan_sha256') != plan_sha
                or admission.get('expected_FP32_state_sha256') != semantic['fp32_state_sha256']
                or admission.get('expected_tokenizer_backend_sha256') != semantic['tokenizer_backend_sha256']):
            raise PermissionError('Actual independent DEV report did not admit confirmation')
    return plan_sha


def materialize_inputs(project: Path, phase: str, source_freeze_path: Path,
                       expected_source_freeze_sha256: str) -> dict:
    if phase not in ('dev', 'confirmation'):
        raise PermissionError('Explicit phase must be dev or confirmation')
    project = Path(project)
    verify_source_freeze(project, source_freeze_path, expected_source_freeze_sha256)
    _, registry, selection, reuse, recipe = verify_metadata(project)
    plan_sha = verify_worker(project, phase, expected_source_freeze_sha256)
    for key in ('origin_allowlist', 'origin_validation', 'origin_selection',
                'origin_retirement', 'origin_eligibility', 'origin_source_freeze',
                'previous_allowlist', 'previous_validation', 'previous_selection',
                'previous_retirement', 'previous_source_freeze', 'latest_identity_verification'):
        exact_ref(project, reuse[key])
    old48 = safe_target(project, PREFIX + 'legal-transfer/epoch9/confirmation48.jsonl')
    if sha(old48) != '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50':
        raise PermissionError('Preserved old confirmation bank changed')
    for epoch in (16, 17, 18, 20, 21):
        if safe_target(project, PREFIX + f'legal-transfer/epoch{epoch}/confirmation24.jsonl').exists():
            raise PermissionError('Reserved confirmation choices have already been projected')
    output = safe_target(project, recipe['roles'][phase]['output_path'])
    allow_output = HERE / ('inputs.' + phase + '.allowlist.json')
    receipt_output = HERE / ('inputs.' + phase + '.projection.json')
    reservation_output = HERE / ('role-reservation.' + phase + '.json')
    if any(p.exists() for p in [output, allow_output, receipt_output, reservation_output]):
        raise PermissionError('One-shot role already reserved or projected; never overwrite/retry')
    selected = [r for r in selection['documents'] if r['role'] == phase]
    ids = DEV_IDS if phase == 'dev' else CONF_IDS
    if [r['document_id'] for r in selected] != ids:
        raise PermissionError('Fixed phase document order changed')
    write_new(reservation_output, {'schema_version': 1, 'phase': phase,
        'at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(), 'pgid': os.getpgrp(),
        'plan_sha256': plan_sha, 'source_freeze_sha256': expected_source_freeze_sha256,
        'document_ids': ids, 'hypotheses': HYPOTHESES, 'annotation_choices_accessed': 0,
        'conservative_DEV_retirement_on_any_subsequent_failure': phase == 'dev',
        'reserved_confirmation_role_preserved': phase == 'confirmation'})
    source_path = exact_ref(project, recipe['source'])
    source = read(source_path)  # First original-corpus parse; no source choices indexed.
    docs = {d['id']: d for d in source['documents']}
    expected_ids = set().union(*(set(registry[k]) for k in
        ('excluded_document_ids', 'reserved_confirmation_document_ids', 'eligible_document_ids')))
    if (len(source['documents']) != 423 or len(docs) != 423 or set(docs) != expected_ids
            or any(type(d['id']) is not int for d in source['documents'])):
        raise ValueError('Exact official 423-document identity universe changed')
    cross_ids = {r['document_id'] for r in registry['cross_split_documents']}
    blocked = set(registry['old_and_reserved_normalized_document_sha256'])
    cross_hashes = {r['normalized_document_sha256'] for r in registry['cross_split_documents']}
    prior = []
    for old in sorted((HERE.parent).glob('epoch*/*allowlist*.json')):
        if old.parent != HERE:
            prior += [(str(old.relative_to(project)), r) for r in read(old).get('records', [])]
    approved_paths = {r['path'] for r in reuse['historical_allowlist_exceptions']}
    reuse_rows = {(r['document_id'], r['hypothesis_id']): r for r in reuse['records']}
    rows, identities, seen = [], [], set()
    for item in selected:
        document_id = item['document_id']; doc = docs[document_id]
        if type(doc['text']) is not str:
            raise ValueError('Document text must be an exact string')
        doc_sha = hashlib.sha256(norm(doc['text']).encode()).hexdigest()
        allowed_conf = phase == 'confirmation' and all(
            reuse_rows[(document_id, h)]['normalized_document_sha256'] == doc_sha for h in HYPOTHESES)
        if (document_id in cross_ids or doc_sha in cross_hashes or doc_sha in seen
                or (doc_sha in blocked and not allowed_conf)):
            raise ValueError('Prior/reserved/cross-split/document collision; never redraw')
        seen.add(doc_sha)
        for h in HYPOTHESES:
            hypothesis = source['labels'][h]['hypothesis']
            if type(hypothesis) is not str:
                raise ValueError('Source hypothesis must be an exact string')
            inputs = {'state': doc['text'], 'questions': {'decision': {'type': 'choice',
                'instructions': INSTRUCTION, 'criteria': {'Yes': hypothesis,
                    'No': 'The agreement does not establish the following: ' + hypothesis}}}}
            raw = canonical(inputs); input_sha = hashlib.sha256(raw.encode()).hexdigest()
            normalized_sha = hashlib.sha256(norm(raw).encode()).hexdigest()
            identifier = row_id(phase, document_id, h)
            if phase == 'confirmation':
                original = reuse_rows[(document_id, h)]
                if (original['input_sha256'] != input_sha
                        or original['normalized_input_sha256'] != normalized_sha
                        or original['normalized_document_sha256'] != doc_sha):
                    raise ValueError('Reused CONF differs from exact unused epoch16 input identity')
            for path, old in prior:
                collision = (old.get('input_sha256') == input_sha
                             or old.get('normalized_input_sha256') == normalized_sha)
                if collision and (phase != 'confirmation' or path not in approved_paths
                        or old.get('source_group') != 'original-contractnli:' + str(document_id)
                        or old.get('hypothesis_id') != h
                        or old.get('input_sha256') != input_sha
                        or old.get('normalized_input_sha256') != normalized_sha):
                    raise ValueError('Historical exact/normalized input collision outside exact unused CONF')
            rows.append({'id': identifier, 'input': inputs, 'input_sha256': input_sha})
            identities.append({'id': identifier, 'document_id': document_id,
                'hypothesis_id': h, 'source_group': 'original-contractnli:' + str(document_id),
                'input_sha256': input_sha, 'normalized_input_sha256': normalized_sha,
                'normalized_document_sha256': doc_sha})
    if len(rows) != 24 or len(seen) != 8:
        raise ValueError('Fixed phase requires exactly 24 questions in 8 unique documents')
    result = {'schema_version': 1, 'role': phase, 'records': rows}
    write_new(output, result)
    write_new(allow_output, {'schema_version': 1, 'role': phase, 'queries': 24,
        'document_groups': 8, 'source_sha256': SOURCE_SHA,
        'source_freeze_sha256': expected_source_freeze_sha256,
        'records': identities, 'contains_labels_or_inputs': False,
        'annotation_choices_accessed': 0, 'recipe_frozen_before_projection': True})
    write_new(receipt_output, {'schema_version': 1, 'status': 'PHASE_INPUTS_PROJECTED_ONCE_NO_CHOICES',
        'phase': phase, 'pid': os.getpid(), 'plan_sha256': plan_sha,
        'source_freeze_sha256': expected_source_freeze_sha256, 'source_sha256': SOURCE_SHA,
        'input_file_sha256': sha(output), 'input_allowlist_sha256': sha(allow_output),
        'queries': 24, 'document_groups': 8, 'document_ids': ids,
        'original_annotation_choices_accessed': 0, 'old48_confirmation_parsed': False,
        'other_role_inputs_or_choices_accessed': 0, 'TRAIN_calibration_fits': 0,
        'DEV_documents_now_exposed_forever': phase == 'dev',
        'pretraining_fuzzy_overlap_verified': False})
    return result
