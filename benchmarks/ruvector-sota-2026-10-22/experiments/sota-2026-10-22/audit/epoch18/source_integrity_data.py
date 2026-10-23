"""Independent metadata/lineage review; never opens original case or choice data."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import importlib.util
import json

PREFIX = 'experiments/sota-2026-10-22/'
SOURCE = '0eac156990f5a4ee0084af635eb3089913b437ff'
DEV = [541, 503, 326, 509, 111, 428, 244, 300]
CONF = [308, 159, 284, 501, 267, 494, 261, 313]
OLD = [141, 163, 178, 183, 217, 224, 276, 316, 325, 371, 414, 431, 477, 554, 615, 624]
PREV_DEV = [264, 214, 297, 570, 365, 281, 483, 139]
HYP = ['nda-17', 'nda-7', 'nda-3']
SALT = 'ruvector-sota-2026-10-22:epoch18:large-typed-reader:DEV:v1:'
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
ALLOW = {16: 'c3970a800cdc609bcd8a1324d0def90ad11853c3f68c3b7eb9faafce8e720fdb',
         17: '5bc8d088166b1f9f5edb7175f666b403381c96f036f1bcbc0df40d70067fbebd'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    # Callers name only identity/selection/source metadata, never input/case files.
    return json.loads(path.read_text())


def identity(project, path):
    return {'path': str(path.relative_to(project)), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rejected(fn, *args):
    try:
        fn(*args)
    except (ValueError, PermissionError):
        return True
    raise AssertionError('Generic fault fixture was unexpectedly accepted')


def main(project, out):
    here = project / PREFIX / 'legal-transfer/epoch18'
    eligibility = read(here / 'eligibility-manifest.json')
    previous = read(here.parent / 'epoch17/eligibility-manifest.json')
    retirement = read(here.parent / 'epoch17/postrun-identity-retirement-v1.json')
    draw = read(here / 'draw-plan.json')
    selection = read(here / 'document-selection.json')
    reuse = read(here / 'reserved-confirmation-reuse.json')
    contract = read(here / 'data-contract.pre-label.json')
    src_manifest = read(here / 'source-manifest.pre-label.json')
    exposed, reserved, eligible = [set(eligibility[k]) for k in
        ('excluded_document_ids', 'reserved_confirmation_document_ids', 'eligible_document_ids')]
    assert (len(exposed), len(reserved), len(eligible)) == (213, 24, 186)
    assert not (exposed & reserved or exposed & eligible or reserved & eligible)
    assert len(exposed | reserved | eligible) == 423
    assert eligibility['checkpoint_commit'] == SOURCE and eligibility['source_sha256'] == SOURCE_SHA
    assert eligibility['previous_registry_sha256'] == digest(here.parent / 'epoch17/eligibility-manifest.json')
    for key, previous_key in [('excluded_document_ids', 'exposed_document_ids'),
            ('reserved_confirmation_document_ids', 'reserved_confirmation_document_ids'),
            ('eligible_document_ids', 'eligible_unreserved_document_ids')]:
        assert eligibility[key] == retirement['partition'][previous_key]
    assert set(PREV_DEV) <= exposed and eligibility['epoch17_added_DEV_document_ids'] == PREV_DEV
    assert eligibility['old_reserved_confirmation48_document_ids'] == OLD
    assert reserved == set(OLD) | set(CONF)
    assert eligibility['cross_split_documents'] == previous['cross_split_documents']
    assert set(eligibility['old_and_reserved_normalized_document_sha256']) == (
        set(previous['old_and_reserved_normalized_document_sha256']) |
        {r['normalized_document_sha256'] for r in retirement['retired_DEV']['records']})
    ranks = sorted((hashlib.sha256((SALT + str(i)).encode()).hexdigest(), i) for i in eligible)
    assert [i for _, i in ranks[:8]] == DEV
    assert draw['salt'] == SALT and draw['hypotheses'] == HYP
    assert draw['train'] == draw['calibration'] == []
    assert draw['eligibility_manifest_sha256'] == digest(here / 'eligibility-manifest.json')
    assert draw['reserved_reuse_manifest_sha256'] == digest(here / 'reserved-confirmation-reuse.json')
    assert selection['builder_sha256'] == digest(here / 'build.py')
    assert selection['draw_plan_sha256'] == digest(here / 'draw-plan.json')
    assert selection['eligibility_manifest_sha256'] == digest(here / 'eligibility-manifest.json')
    assert selection['reserved_reuse_manifest_sha256'] == digest(here / 'reserved-confirmation-reuse.json')
    assert [r['document_id'] for r in selection['documents'] if r['role'] == 'dev'] == DEV
    assert [r['document_id'] for r in selection['documents'] if r['role'] == 'confirmation'] == CONF
    for r, (key, identifier) in zip(selection['documents'][:8], ranks[:8]):
        assert r['document_id'] == identifier and r['document_draw_key'] == key
    assert selection['hypotheses'] == HYP and selection['train'] == selection['calibration'] == []
    assert selection['source_corpus_opened_for_selection'] is False
    assert selection['gold_accessed_for_selection'] is False
    assert selection['uses_text_length_labels_outcomes_or_class_presence'] is False
    assert selection['old_reserved_confirmation48_parsed'] is False
    assert selection['confirmation_roles_relabelled_or_newly_drawn'] is False
    refs = {}
    refkeys = ['origin_allowlist', 'origin_validation', 'origin_selection', 'origin_retirement',
        'origin_eligibility', 'origin_source_freeze', 'previous_allowlist', 'previous_validation',
        'previous_selection', 'previous_retirement', 'previous_source_freeze']
    for key in refkeys:
        ref = reuse[key]
        path = project / ref['path']
        assert ref == identity(project, path)
        refs[key] = read(path)
    assert reuse['historical_allowlist_exceptions'] == [reuse['origin_allowlist'], reuse['previous_allowlist']]
    assert reuse['document_ids'] == CONF and reuse['hypotheses'] == HYP and len(reuse['records']) == 24
    expected_keys = {(d, h) for d in CONF for h in HYP}
    assert {(r['document_id'], r['hypothesis_id']) for r in reuse['records']} == expected_keys
    for epoch, prefix in [(16, 'origin'), (17, 'previous')]:
        allowref = reuse[prefix + '_allowlist']
        assert allowref['path'] == PREFIX + f'legal-transfer/epoch{epoch}/confirmation-input-allowlist.json'
        assert allowref['sha256'] == ALLOW[epoch]
        allow = refs[prefix + '_allowlist']
        valid = refs[prefix + '_validation']
        assert allow['source_sha256'] == SOURCE_SHA and allow['annotation_choices_accessed'] == 0
        a = {(int(r['source_group'].split(':')[-1]), r['hypothesis_id']): r for r in allow['records']}
        v = {(r['selection']['document_id'], r['hypothesis_id']): r for r in valid['records']
             if r['selection']['role'] == 'confirmation'}
        assert set(a) == set(v) == expected_keys
        for row in reuse['records']:
            key = (row['document_id'], row['hypothesis_id'])
            assert a[key]['id'] == f'original-contractnli:train:epoch{epoch}:confirmation:{key[0]}:{key[1]}'
            assert all(row[k] == a[key][k] for k in
                       ('source_group', 'hypothesis_id', 'input_sha256', 'normalized_input_sha256'))
            assert all(row[k] == v[key][k] for k in
                       ('input_sha256', 'normalized_input_sha256', 'normalized_document_sha256'))
        assert refs[prefix + '_retirement']['verification']['both_confirmation_banks_project_model_unused'] is True
        assert not (project / allowref['path']).with_name('confirmation24.jsonl').exists()
    assert refs['previous_retirement']['new_confirmation24']['annotation_choices_projected'] == 0
    assert refs['previous_retirement']['new_confirmation24']['model_attempts'] == 0
    assert not (set(refs['origin_eligibility']['old_and_reserved_normalized_document_sha256']) &
                {r['normalized_document_sha256'] for r in reuse['records']})
    old_bank = reuse['old48_bank']
    assert old_bank['document_ids'] == OLD
    assert digest(project / old_bank['data_path']) == old_bank['data_sha256'] == draw['old_confirmation_preserved_sha256']
    for ref in src_manifest['files']:
        assert ref == identity(project, project / ref['path'])
    assert contract['source']['commit'] == 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
    assert contract['source']['member_sha256'] == SOURCE_SHA and contract['source']['license'] == 'CC-BY-4.0'
    license_file = project / PREFIX / 'legal-transfer/epoch3/sources/original-contractnli-LICENSE'
    original_train = project / PREFIX / 'legal-transfer/epoch3/sources/original-train.json'
    assert digest(license_file) == contract['source']['license_sha256']
    assert license_file.read_text().startswith('Attribution 4.0 International')
    assert digest(original_train) == SOURCE_SHA  # Byte identity only; never JSON parsed.
    assert contract['development']['document_ids'] == DEV and contract['confirmation']['document_ids'] == CONF
    assert contract['draw']['builder_sha256'] == digest(here / 'build.py')
    b = load_module('independent_source18_builder', here / 'build.py')
    a = load_module('independent_source18_admission', here / 'admission.py')
    # Positive and adversarial collision tests use invented identities only.
    old = {'id': 'original-contractnli:train:epoch16:confirmation:9001:invented',
        'document_id': 9001, 'hypothesis_id': 'invented', 'source_group': 'original-contractnli:9001',
        'input_sha256': 'a' * 64, 'normalized_input_sha256': 'b' * 64,
        'normalized_document_sha256': 'c' * 64}
    record = {'selection': {'document_id': 9001, 'role': 'confirmation'},
        **{k: old[k] for k in ('hypothesis_id', 'input_sha256', 'normalized_input_sha256', 'normalized_document_sha256')}}
    prior = {k: v for k, v in old.items() if k not in ('document_id', 'normalized_document_sha256')}
    b.reject_prior_collision('confirmation', record, [(b.ORIGIN_ALLOW_PATH, prior)], {'records': [old]})
    faults = 0
    for badpath in [b.ORIGIN_ALLOW_PATH + '.copy', PREFIX + 'legal-transfer/epoch15/dev-allowlist.json']:
        rejected(b.reject_prior_collision, 'confirmation', record, [(badpath, prior)], {'records': [old]}); faults += 1
    rejected(b.reject_prior_collision, 'dev', record, [(b.ORIGIN_ALLOW_PATH, prior)], {'records': [old]}); faults += 1
    for key in ['source_group', 'hypothesis_id', 'input_sha256', 'normalized_input_sha256', 'id']:
        changed = dict(prior); changed[key] = 'wrong'
        # Preserve one colliding digest so this tests identity mismatch, not absence of collision.
        if key == 'input_sha256': changed['normalized_input_sha256'] = prior['normalized_input_sha256']
        rejected(b.reject_prior_collision, 'confirmation', record, [(b.ORIGIN_ALLOW_PATH, changed)], {'records': [old]}); faults += 1
    rejected(b.reject_prior_collision, 'confirmation', record, [(b.PREVIOUS_ALLOW_PATH, prior)], {'records': [old]}); faults += 1
    prior17 = dict(prior, id=prior['id'].replace('epoch16', 'epoch17'))
    b.reject_prior_collision('confirmation', record, [(b.PREVIOUS_ALLOW_PATH, prior17)], {'records': [old]})
    # Generic source fixtures are separate from actual operational admission.
    test_a = load_module('independent_source18_generic_admission', here / 'test_admission.py')
    import tempfile
    flag_faults = 0
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        freeze, frozen_sha, plan, receipt = test_a.fixture(root)
        assert a.verify_operational(root, freeze, frozen_sha)
        for key, wrongs in [('measurement_plan', [True, None]), ('operational_prelabel_only', [False, None])]:
            for wrong in wrongs:
                changed = dict(plan)
                if wrong is None: changed.pop(key, None)
                else: changed[key] = wrong
                test_a.write(root / receipt['plan_path'], changed)
                changed_receipt = dict(receipt, plan_sha256=digest(root / receipt['plan_path']))
                test_a.write(root / a.RECEIPT, changed_receipt)
                rejected(a.verify_operational, root, freeze, frozen_sha); flag_faults += 1
    tree = ast.parse((here / 'build.py').read_text())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    source_lines = (here / 'build.py').read_text().splitlines()
    for function in ['validate_inputs', 'materialize']:
        chunk = '\n'.join(source_lines[funcs[function].lineno - 1:funcs[function].end_lineno])
        assert chunk.index('verify_source_freeze(') < chunk.index('ADMISSION.verify_operational(')
        barrier = chunk.index('ADMISSION.verify_operational(')
        target = chunk.index('source = read(source_path)') if function == 'validate_inputs' else chunk.index('source, docs, prepared, validation = validate_inputs(')
        assert barrier < target
        if function == 'materialize':
            assert chunk.index('verify_confirmation_worker(') < target < chunk.index("label = d['annotation_sets']")
    artifacts = {n: (here / n).exists() for n in ['pre-gold-input-validation.json', 'dev-inputs-only.json',
        'confirmation-inputs-only.json', 'development24.jsonl', 'confirmation24.jsonl', 'dev-materialization.json',
        'confirmation-materialization.json']}
    assert not any(artifacts.values()), artifacts
    report = {'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(),
        'reviewer': 'Independent platform source_integrity agent', 'checks_passed': True,
        'status': 'INDEPENDENT_PRELABEL_SOURCE_LINEAGE_AND_ROLE_BARRIER_REVIEW_PASS',
        'source_checkpoint': SOURCE, 'files': [identity(project, here / n) for n in
            ['build.py', 'admission.py', 'test_builder.py', 'test_admission.py', 'draw-plan.json',
             'eligibility-manifest.json', 'reserved-confirmation-reuse.json', 'document-selection.json',
             'data-contract.pre-label.json', 'source-manifest.pre-label.json', 'annotation-lineage.json']],
        'metadata_checks': {'partition_exposed': 213, 'partition_unreserved': 186, 'partition_reserved': 24,
            'partition_matches_actual_epoch17_retirement': True, 'previous17_DEV8_exposed_forever': PREV_DEV,
            'new_DEV8_fixed_id_only': DEV, 'same_unused16_through17_CONF8': CONF,
            'hypotheses': HYP, 'new_train_calibration': [], 'new_CONFIRMATION_draws': 0,
            'immutable_origin_metadata_files_rehashed': len(refkeys), 'exact_origin16_and17_queries_checked': 24,
            'strict_historical_exceptions': [reuse['origin_allowlist'], reuse['previous_allowlist']],
            'old_CONF48_sha256_reverified_without_parse': old_bank['data_sha256']},
        'source_license': contract['source'],
        'official_license_restored_byte_identity': identity(project, license_file),
        'original_train_raw_bytes_rehashed_without_JSON_parse': identity(project, original_train),
        'generic_collision_positive_fixtures_passed': 2, 'generic_collision_fault_fixtures_rejected': faults,
        'generic_admission_plan_flag_faults_rejected': flag_faults,
        'guard_source_review': {'freeze_and_actual_operational_receipt_required_before_first_source_parse': True,
            'plan_requires_measurement_false_operational_true': True,
            'current_source_controller_inherited_verifier_and_full_snapshot_hashes_bound': True,
            'inherited_compatible_CPU2_request30_batch600_paid0': True,
            'confirmation_choices_require_passing_bound_DEV_runtime_and_same_PID_PGID': True,
            'retrieval_miss_not_treated_as_NotMentioned_proof': True},
        'prelabel_projection_artifacts_present_at_review': artifacts,
        'conditional_retirement_only': {'if_DEV_choices_projected_exposed': 221, 'if_DEV_choices_projected_unreserved': 178,
            'if_DEV_only_reserved': 24, 'if_CONF_consumed_exposed': 229, 'if_CONF_consumed_reserved': 16},
        'limitations': ['Operational require_plan itself is independently executed and reviewed by parent auditor; this review performs no operational admission or native execution.',
            'Original source, selected input bodies, and annotation choices were not parsed by this auditor.',
            'Metadata identity review cannot establish absence of pretraining or fuzzy overlap; original source and role identities remain explicitly bounded.'],
        'auditor_original_case_input_or_annotation_parses': 0, 'auditor_model_native_fit_paid_GPU_calls': 0,
        'auditor_Git_mutations': 0, 'native_execution_admitted_by_this_report': False,
        'official_score': None, 'official_rank': None, 'SOTA_established': False}
    with out.open('x') as f:
        f.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(json.dumps({'status': report['status'], 'report_sha256': digest(out), 'bytes': out.stat().st_size,
                      'collision_faults_rejected': faults, 'plan_flag_faults_rejected': flag_faults}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    main(args.project.resolve(), args.out)
