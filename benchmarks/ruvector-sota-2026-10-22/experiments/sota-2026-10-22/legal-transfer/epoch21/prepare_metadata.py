"""One-shot metadata-only role recipe; no original case or annotation JSON parse."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
P = 'experiments/sota-2026-10-22/'
REL = P + 'legal-transfer/epoch21/'
OLD = ROOT / (P + 'legal-transfer/epoch20/')
PARENT = '0c4392bb8b13a901dc416882f850230c1075fb6a'
SALT = 'ruvector-sota-2026-10-22:epoch21:deberta-v3-large-FP32:DEV:v1:'
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
CONF = [308, 159, 284, 501, 267, 494, 261, 313]


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    assert path == path.resolve() and path.is_relative_to(ROOT)
    b = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(b),
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
    # These are previously sealed input-only identity records, never source cases.
    prior = read(OLD / 'eligibility-manifest.json')
    retired = read(OLD / 'postrun-identity-retirement-v1.json')
    assert retired['checks_passed'] is True
    assert retired['partition_after_DEV_projection'] == {
        'exposed': 229, 'reserved_NLI_label_unused': 24, 'total': 423, 'unreserved': 170}
    conf = retired['confirmation']
    assert conf['actual_confirmation_phase_attempts'] == 0
    assert conf['actual_confirmation_corpus_NLI_forwards'] == 0
    assert conf['confirmation_original_annotation_choices_projected'] == 0
    assert conf['retired_as_exposed_DEV'] is False and conf['document_ids'] == CONF
    registry = copy.deepcopy(prior)
    registry.update(epoch=21, checkpoint_commit=PARENT,
        excluded_document_ids=retired['excluded_document_ids_after_DEV'],
        eligible_document_ids=retired['unreserved_document_ids_after_DEV'],
        reserved_confirmation_document_ids=retired['reserved_confirmation_document_ids'],
        counts={'historically_exposed': 229, 'reserved_unused': 24, 'unreserved': 170, 'total': 423},
        old_and_reserved_normalized_document_sha256=retired['blocked_normalized_document_sha256_after_DEV'],
        epoch20_added_DEV_document_ids=retired['development']['document_ids'],
        epoch20_normalized_document_metadata=read(OLD / 'inputs.dev.allowlist.json')['records'],
        previous_registry_sha256=sha(OLD / 'eligibility-manifest.json'),
        previous_retirement=ref(OLD / 'postrun-identity-retirement-v1.json'),
        prior_eligibility=ref(OLD / 'eligibility-manifest.json'),
        latest_identity_verification=ref(OLD / 'postrun-identity-retirement-v1.json'),
        prior_used_identities=ref(ROOT / (P + 'epoch20/USED_IDENTITIES.json')),
        used_identity_manifest_sha256=sha(ROOT / (P + 'epoch20/USED_IDENTITIES.json')),
        prior_roles_preserved='All229 historically exposed train-document groups retain their prior TRAIN/DEV roles; all prior DEV forever. Reserved24 remain project-NLI-prediction/label unused, with disclosed prior tokenizer-only capacity access. No old TRAIN relabelled fresh DEV.',
        inherited_legacy_epoch_metadata_fields_scope='Earlier epoch15/16/17/18 lineage fields remain historical provenance; explicit current partition and epoch20 refs govern.')
    groups = [registry[k] for k in ('excluded_document_ids', 'reserved_confirmation_document_ids', 'eligible_document_ids')]
    assert [len(g) for g in groups] == [229, 24, 170]
    assert all(type(x) is int for g in groups for x in g)
    assert len(set().union(*map(set, groups))) == 423
    assert not any(set(groups[i]) & set(groups[j]) for i in range(3) for j in range(i))
    assert len(set(registry['old_and_reserved_normalized_document_sha256'])) == 253
    ranking = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in groups[2])
    dev = [i for _, i in ranking[:8]]
    assert len(set(dev)) == 8 and not set(dev) & set(CONF)
    reuse = copy.deepcopy(read(OLD / 'reserved-confirmation-reuse.json'))
    reuse.update(epoch=21,
        kind='EXACT_UNCONSUMED_EPOCH16_CONFIRMATION24_REUSE_THROUGH_CLOSED20_NOT_FRESH_REDRAW',
        latest_identity_verification=ref(OLD / 'postrun-identity-retirement-v1.json'),
        previous_epoch=20, previous_allowlist=ref(OLD / 'confirmation-input-allowlist.json'),
        previous_validation=ref(OLD / 'postrun-identity-retirement-v1.json'),
        previous_selection=ref(OLD / 'document-selection.json'),
        previous_retirement=ref(OLD / 'postrun-identity-retirement-v1.json'),
        previous_source_freeze=ref(ROOT / (P + 'epoch20/candidate-source-freeze.json')),
        previous_model_attempts=0, previous_model_attempts_scope='Confirmation phase attempts only; epoch20 DEV attempt is separately preserved.',
        prior_confirmation_tokenizer_only_access=conf['worker_tokenizer_only_capacity'],
        prior_capacity_text_access_does_not_claim_text_never_read=True)
    reuse['historical_allowlist_exceptions'].append(ref(OLD / 'confirmation-input-allowlist.json'))
    assert len(reuse['records']) == 24
    assert [(r['document_id'], r['hypothesis_id']) for r in reuse['records']] == [
        (d, h) for d in CONF for h in HYPOTHESES]
    registry['reused_conf_exact_metadata_sha256'] = hashlib.sha256(
        json.dumps(reuse['records'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    save('eligibility-manifest.json', registry)
    save('reserved-confirmation-reuse.json', reuse)
    draw = copy.deepcopy(read(OLD / 'draw-plan.json'))
    draw.update(epoch=21, checkpoint_parent=PARENT, salt=SALT,
        DEV_document_ids_fixed_once=dev,
        eligibility_manifest_sha256=sha(HERE / 'eligibility-manifest.json'),
        reserved_reuse_manifest_sha256=sha(HERE / 'reserved-confirmation-reuse.json'))
    save('draw-plan.json', draw)
    selection = copy.deepcopy(read(OLD / 'document-selection.json'))
    selection.update(epoch=21, frozen_at=datetime.now(timezone.utc).isoformat(),
        draw_plan_sha256=sha(HERE / 'draw-plan.json'),
        eligibility_manifest_sha256=sha(HERE / 'eligibility-manifest.json'),
        reserved_reuse_manifest_sha256=sha(HERE / 'reserved-confirmation-reuse.json'),
        selection='First8 SHA256(salt+str(documentID)) ranks among170 unreserved IDs; exact project-NLI/label-unused epoch16 CONF24 reused unchanged. No source cases/choices/lengths/class counts accessed.',
        documents=[{'document_rank': j, 'document_id': i, 'document_draw_key': key, 'role': 'dev'}
                   for j, (key, i) in enumerate(ranking[:8])] +
                  [r for r in selection['documents'] if r['role'] == 'confirmation'])
    save('document-selection.json', selection)
    for phase, ids in [('dev', dev), ('confirmation', CONF)]:
        allow = copy.deepcopy(read(OLD / (phase + '-input-allowlist.json')))
        allow.update(epoch=21, selection_sha256=sha(HERE / 'document-selection.json'))
        if phase == 'dev':
            allow['records'] = [{'id': f'original-contractnli:train:epoch21:dev:{i}:{h}',
                'document_id': i, 'hypothesis_id': h, 'source_group': 'original-contractnli:' + str(i)}
                for i in ids for h in HYPOTHESES]
        else:
            for r in allow['records']:
                r['id'] = f"original-contractnli:train:epoch21:confirmation:{r['document_id']}:{r['hypothesis_id']}"
        save(phase + '-input-allowlist.json', allow)
    build = (OLD / 'build.py').read_text()
    build = build.replace('01c42365b8d79c968ea4f49120a5c1d71b9e0687', PARENT)
    build = build.replace('epoch20', 'epoch21').replace('ynie-roberta-large-FP32', 'deberta-v3-large-FP32')
    build = build.replace('DEV_IDS = [470, 423, 109, 418, 613, 580, 167, 393]', 'DEV_IDS = ' + repr(dev))
    build = build.replace('[221, 24, 178]', '[229, 24, 170]').replace('221/24/178', '229/24/170')
    build = build.replace('for epoch in (16, 17, 18, 20):', 'for epoch in (16, 17, 18, 20, 21):')
    source('build.py', build)
    test = (OLD / 'test_builder.py').read_text().replace('epoch20', 'epoch21')
    test = test.replace('[221, 24, 178]', '[229, 24, 170]')
    source('test_builder.py', test)
    qualification = copy.deepcopy(read(OLD / 'source-qualification.json'))
    qualification.update(epoch=21, source_checkpoint=PARENT,
        model_source_qualification=ref(HERE / 'MODEL_QUALIFICATION.json'),
        current_model='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli@b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7',
        current_original_train_partition={'exposed':229,'unreserved':170,'reserved':24},
        new_original_source_inputs_or_annotation_choices_accessed=0)
    save('source-qualification.json', qualification)
    recipe = copy.deepcopy(read(OLD / 'input-recipe.json'))
    recipe.update(epoch=21, source_checkpoint=PARENT)
    for key, name in [('builder','build.py'),('selection','document-selection.json'),
                      ('draw_plan','draw-plan.json'),('eligibility','eligibility-manifest.json'),
                      ('reserved_confirmation_reuse','reserved-confirmation-reuse.json')]:
        recipe[key] = ref(HERE / name)
    recipe['builder_path'] = recipe['builder']['path']; recipe['builder_sha256'] = recipe['builder']['sha256']
    for phase in ('dev','confirmation'):
        recipe['roles'][phase]['input_allowlist'] = ref(HERE / (phase + '-input-allowlist.json'))
        recipe['roles'][phase]['output_path'] = REL + 'inputs.' + phase + '.json'
    save('input-recipe.json', recipe)
    contract = copy.deepcopy(read(OLD / 'data-contract.pre-label.json'))
    contract.update(epoch=21, source_checkpoint=PARENT, source_roles=recipe['roles'],
        DEV_document_ids=dev, CONF_document_ids=CONF, original_train_partition={'exposed':229,'unreserved':170,'reserved':24})
    contract['input_recipe'] = ref(HERE / 'input-recipe.json')
    contract['source_qualification'] = ref(HERE / 'source-qualification.json')
    contract['development'].update(document_ids=dev,
        input_allowlist=ref(HERE / 'dev-input-allowlist.json'))
    contract['confirmation'].update(document_ids=CONF,
        input_allowlist=ref(HERE / 'confirmation-input-allowlist.json'),
        scope='Exact lazy original epoch16 reserved source identities, project-NLI-prediction and label unused; prior tokenizer-only text capacity access is disclosed, no new draw.')
    save('data-contract.pre-label.json', contract)
    print(json.dumps({'DEV_document_ids_fixed_once':dev,'CONF_document_ids':CONF,
                      'partition':[229,24,170],'blocked_normalized_documents':253,
                      'input_recipe':ref(HERE/'input-recipe.json'),
                      'model_native_calls':0,'original_case_or_annotation_choices_parsed':0}))


if __name__ == '__main__': main()

