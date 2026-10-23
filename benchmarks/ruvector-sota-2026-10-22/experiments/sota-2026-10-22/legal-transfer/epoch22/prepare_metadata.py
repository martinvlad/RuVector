"""One fixed ID-only role draw; never open original cases or annotation choices."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
P = 'experiments/sota-2026-10-22/'
REL = P + 'legal-transfer/epoch22/'
OLD = ROOT / (P + 'legal-transfer/epoch21/')
RETIREMENT = ROOT / (P + 'epoch21/reviews/postrun-data-identities-independent-v1.json')
PARENT = 'c7823614cd5bc59f031445b55682f59230dc1901'
SALT = 'ruvector-sota-2026-10-22:epoch22:sentence-groups:DEV:v1:'
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
CONF = [308, 159, 284, 501, 267, 494, 261, 313]


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    assert path == path.resolve() and path.is_relative_to(ROOT)
    assert not any(p.is_symlink() for p in [path, *path.parents])
    b = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(b),
            'sha256': hashlib.sha256(b).hexdigest()}


def save(name, value):
    with (HERE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    return ref(HERE / name)


def source(name, text):
    with (HERE / name).open('x') as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    return ref(HERE / name)


def main():
    prior = read(OLD / 'eligibility-manifest.json')
    retired = read(RETIREMENT)
    assert retired['checks_passed'] is True
    assert retired['partition_after_DEV_projection'] == {
        'exposed': 237, 'reserved_NLI_label_unused': 24, 'total': 423, 'unreserved': 162}
    conf = retired['confirmation']
    assert conf['actual_confirmation_phase_attempts'] == 0
    assert conf['actual_confirmation_corpus_NLI_forwards'] == 0
    assert conf['confirmation_original_annotation_choices_projected'] == 0
    assert conf['retired_as_exposed_DEV'] is False and conf['document_ids'] == CONF
    registry = copy.deepcopy(prior)
    registry.update(epoch=22, checkpoint_commit=PARENT,
        excluded_document_ids=retired['excluded_document_ids_after_DEV'],
        eligible_document_ids=retired['unreserved_document_ids_after_DEV'],
        reserved_confirmation_document_ids=retired['reserved_confirmation_document_ids'],
        counts={'historically_exposed': 237, 'reserved_unused': 24, 'unreserved': 162, 'total': 423},
        old_and_reserved_normalized_document_sha256=retired['blocked_normalized_document_sha256_after_DEV'],
        epoch21_added_DEV_document_ids=retired['development']['document_ids'],
        epoch21_normalized_document_metadata=read(OLD / 'inputs.dev.allowlist.json')['records'],
        previous_registry_sha256=sha(OLD / 'eligibility-manifest.json'),
        previous_retirement=ref(RETIREMENT), prior_eligibility=ref(OLD / 'eligibility-manifest.json'),
        latest_identity_verification=ref(RETIREMENT),
        prior_used_identities=ref(ROOT / (P + 'epoch21/USED_IDENTITIES.json')),
        used_identity_manifest_sha256=sha(ROOT / (P + 'epoch21/USED_IDENTITIES.json')),
        prior_roles_preserved='All237 historically exposed groups retain their TRAIN/DEV roles; all previous DEV forever. Reserved24 remain project-NLI-prediction/label unused, with disclosed prior tokenizer-only input access. No old TRAIN relabelled fresh DEV.',
        inherited_legacy_epoch_metadata_fields_scope='Earlier lineage fields remain historical provenance; explicit current partition and epoch21 references govern.')
    groups = [registry[k] for k in ('excluded_document_ids', 'reserved_confirmation_document_ids', 'eligible_document_ids')]
    assert [len(g) for g in groups] == [237, 24, 162]
    assert all(type(i) is int for g in groups for i in g)
    assert len(set().union(*map(set, groups))) == 423
    assert not any(set(groups[i]) & set(groups[j]) for i in range(3) for j in range(i))
    assert len(set(registry['old_and_reserved_normalized_document_sha256'])) == 261
    ranking = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in groups[2])
    dev = [i for _, i in ranking[:8]]
    assert dev == [328, 350, 135, 248, 441, 123, 98, 87]
    assert not set(dev) & set(CONF)
    reuse = copy.deepcopy(read(OLD / 'reserved-confirmation-reuse.json'))
    reuse.update(epoch=22,
        kind='EXACT_UNCONSUMED_EPOCH16_CONFIRMATION24_REUSE_THROUGH_CLOSED21_NOT_FRESH_REDRAW',
        latest_identity_verification=ref(RETIREMENT), previous_epoch=21,
        previous_allowlist=ref(OLD / 'confirmation-input-allowlist.json'),
        previous_validation=ref(RETIREMENT), previous_selection=ref(OLD / 'document-selection.json'),
        previous_retirement=ref(RETIREMENT),
        previous_source_freeze=ref(ROOT / (P + 'epoch21/candidate-source-freeze.json')),
        previous_model_attempts=0,
        previous_model_attempts_scope='Confirmation phase attempts only; epoch21 DEV attempt is separately preserved.',
        prior_confirmation_tokenizer_only_access=conf['worker_tokenizer_only_capacity'],
        prior_capacity_text_access_does_not_claim_text_never_read=True)
    reuse['historical_allowlist_exceptions'].append(ref(OLD / 'confirmation-input-allowlist.json'))
    assert [(r['document_id'], r['hypothesis_id']) for r in reuse['records']] == [
        (d, h) for d in CONF for h in HYPOTHESES]
    registry['reused_conf_exact_metadata_sha256'] = hashlib.sha256(
        json.dumps(reuse['records'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    save('eligibility-manifest.json', registry)
    save('reserved-confirmation-reuse.json', reuse)
    draw = copy.deepcopy(read(OLD / 'draw-plan.json'))
    draw.update(epoch=22, checkpoint_parent=PARENT, salt=SALT, DEV_document_ids_fixed_once=dev,
        eligibility_manifest_sha256=sha(HERE / 'eligibility-manifest.json'),
        reserved_reuse_manifest_sha256=sha(HERE / 'reserved-confirmation-reuse.json'))
    save('draw-plan.json', draw)
    selection = copy.deepcopy(read(OLD / 'document-selection.json'))
    selection.update(epoch=22, frozen_at=datetime.now(timezone.utc).isoformat(),
        draw_plan_sha256=sha(HERE / 'draw-plan.json'),
        eligibility_manifest_sha256=sha(HERE / 'eligibility-manifest.json'),
        reserved_reuse_manifest_sha256=sha(HERE / 'reserved-confirmation-reuse.json'),
        selection='First8 SHA256(salt+str(documentID)) ranks among162 unreserved IDs; exact project-NLI/label-unused epoch16 CONF24 reused unchanged. No source cases/choices/lengths/class counts accessed.',
        documents=[{'document_rank': j, 'document_id': i, 'document_draw_key': key, 'role': 'dev'}
                   for j, (key, i) in enumerate(ranking[:8])] +
                  [r for r in selection['documents'] if r['role'] == 'confirmation'])
    save('document-selection.json', selection)
    for phase, ids in [('dev', dev), ('confirmation', CONF)]:
        allow = copy.deepcopy(read(OLD / (phase + '-input-allowlist.json')))
        allow.update(epoch=22, selection_sha256=sha(HERE / 'document-selection.json'))
        if phase == 'dev':
            allow['records'] = [{'id': f'original-contractnli:train:epoch22:dev:{i}:{h}',
                'document_id': i, 'hypothesis_id': h, 'source_group': 'original-contractnli:' + str(i)}
                for i in ids for h in HYPOTHESES]
        else:
            for r in allow['records']:
                r['id'] = f"original-contractnli:train:epoch22:confirmation:{r['document_id']}:{r['hypothesis_id']}"
        save(phase + '-input-allowlist.json', allow)
    model_lock = copy.deepcopy(read(OLD / 'model-assets.lock.json'))
    model_lock['epoch'] = 22
    for r in model_lock['assets']:
        r['path'] = r['path'].replace('/candidate/epoch21/', '/candidate/epoch22/')
    model_lock['metadata_acquisition_field_scope'] = ('Historical epoch21 source-qualification flags only; not a claim that epoch22 runtime destinations exist. Root must independently verify/copy all9 exact original assets before admission.')
    save('model-assets.lock.json', model_lock)
    qualification = {'schema_version': 1, 'epoch': 22, 'source_checkpoint': PARENT,
        'status': 'SAME_ORIGINAL_QUALIFIED_READER_CONTEXT_ONLY_STUDY_PENDING_NEW_BOUNDED_RUNTIME',
        'repository': model_lock['repository'], 'revision': model_lock['revision'],
        'model_asset_lock': ref(HERE / 'model-assets.lock.json'),
        'previous_metadata_qualification': ref(OLD / 'MODEL_QUALIFICATION.json'),
        'immutable_official_model_card': ref(OLD / 'model-README.md'),
        'immutable_official_API': ref(OLD / 'model-api.json'),
        'immutable_official_config': ref(OLD / 'model-config.json'),
        'previous_actual_source_header': ref(ROOT / (P + 'candidate/epoch21/source-safetensors-header.json')),
        'previous_independent_runtime': ref(ROOT / (P + 'audit/epoch21/acceptance-rejection.dev.json')),
        'licensing': 'MIT declared by immutable official card/API; no separate LICENSE asset.',
        'source_storage': '394original FP16 learned tensors and one I64 position buffer; explicit FP32 CPU computation, all original trained values required; no quantization or reinitialization.',
        'selection': 'Same qualified reader, frozen mathematical mapping and512 pair cap. Only source-sentence grouping/packing changes; no model grid.',
        'training_lineage': read(OLD / 'MODEL_QUALIFICATION.json')['training_lineage'],
        'model_native_parser_paid_GPU_calls_this_metadata_step': 0,
        'new_legal_accuracy_or_generalization_established': False}
    save('MODEL_QUALIFICATION.json', qualification)
    build = (OLD / 'build.py').read_text().replace('0c4392bb8b13a901dc416882f850230c1075fb6a', PARENT)
    build = build.replace('epoch21', 'epoch22').replace(
        'ruvector-sota-2026-10-22:epoch22:deberta-v3-large-FP32:DEV:v1:', SALT)
    build = build.replace('DEV_IDS = [303, 176, 113, 186, 485, 512, 219, 520]', 'DEV_IDS = ' + repr(dev))
    build = build.replace('[229, 24, 170]', '[237, 24, 162]').replace('229/24/170', '237/24/162')
    build = build.replace('for epoch in (16, 17, 18, 20, 21):', 'for epoch in (16, 17, 18, 20, 21, 22):')
    # Global namespace replacement above changed that terminal tuple21 to22.
    build = build.replace('for epoch in (16, 17, 18, 20, 22):', 'for epoch in (16, 17, 18, 20, 21, 22):')
    build = build.replace("    plan = read(plan_path)\n", "    plan = read(plan_path)\n    if (plan.get('study_id') != 'native-deberta-v3-fp32-sentencegroups-e22' or plan.get('epoch') != 22 or plan.get('source_checkpoint') != PARENT):\n        raise PermissionError('Exact epoch22 source study required before legal parsing')\n")
    source('build.py', build)
    test = (OLD / 'test_builder.py').read_text().replace('epoch21', 'epoch22')
    test = test.replace('[229, 24, 170]', '[237, 24, 162]')
    source('test_builder.py', test)
    sq = copy.deepcopy(read(OLD / 'source-qualification.json'))
    sq.update(epoch=22, source_checkpoint=PARENT, model_source_qualification=ref(HERE / 'MODEL_QUALIFICATION.json'),
        current_original_train_partition={'exposed': 237, 'unreserved': 162, 'reserved': 24},
        new_original_source_inputs_or_annotation_choices_accessed=0)
    save('source-qualification.json', sq)
    recipe = copy.deepcopy(read(OLD / 'input-recipe.json'))
    recipe.update(epoch=22, source_checkpoint=PARENT)
    for key, name in [('builder', 'build.py'), ('selection', 'document-selection.json'),
                      ('draw_plan', 'draw-plan.json'), ('eligibility', 'eligibility-manifest.json'),
                      ('reserved_confirmation_reuse', 'reserved-confirmation-reuse.json')]:
        recipe[key] = ref(HERE / name)
    recipe['builder_path'] = recipe['builder']['path']; recipe['builder_sha256'] = recipe['builder']['sha256']
    for phase in ('dev', 'confirmation'):
        recipe['roles'][phase]['input_allowlist'] = ref(HERE / (phase + '-input-allowlist.json'))
        recipe['roles'][phase]['output_path'] = REL + 'inputs.' + phase + '.json'
    save('input-recipe.json', recipe)
    contract = copy.deepcopy(read(OLD / 'data-contract.pre-label.json'))
    contract.update(epoch=22, source_checkpoint=PARENT, source_roles=recipe['roles'],
        DEV_document_ids=dev, CONF_document_ids=CONF,
        original_train_partition={'exposed': 237, 'unreserved': 162, 'reserved': 24})
    contract['input_recipe'] = ref(HERE / 'input-recipe.json')
    contract['source_qualification'] = ref(HERE / 'source-qualification.json')
    contract['development'].update(document_ids=dev, input_allowlist=ref(HERE / 'dev-input-allowlist.json'))
    contract['confirmation'].update(document_ids=CONF, input_allowlist=ref(HERE / 'confirmation-input-allowlist.json'))
    contract['logical_annotation_isolation_limit'] = 'Original source JSON fields enter memory only after saved3of3; worker never indexes annotation choices. This is logical role separation, not OS label isolation. Independent postprediction scorer alone joins the fixed role labels.'
    save('data-contract.pre-label.json', contract)
    print(json.dumps({'DEV_document_ids_fixed_once': dev, 'CONF_document_ids': CONF,
        'partition': [237, 24, 162], 'blocked_normalized_documents': 261,
        'input_recipe': ref(HERE / 'input-recipe.json'), 'model_asset_lock': ref(HERE / 'model-assets.lock.json'),
        'model_native_calls': 0, 'original_case_or_annotation_choices_parsed': 0}))


if __name__ == '__main__': main()
