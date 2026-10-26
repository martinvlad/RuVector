"""Once opaque reuse of exposed E44 assets after independently read-back E47 SOURCE.

No archive reader, source body parser, label decoder, model or native capability.
The unchanged E44 feature/vault containers keep their original epoch header.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FEATURES_SHA='d47aab7b030bfdd0b0353b22d8a5ef123a063205ea8706943645152aff3e5a8d'


def feature_source():
    p = HERE / 'e47_features.py'
    b = p.read_bytes()
    if hashlib.sha256(b).hexdigest() != FEATURES_SHA:
        raise ValueError('FEATURE_SOURCE_SHA_DRIFT')
    spec = importlib.util.spec_from_file_location('e47_custodian_features', p)
    module = importlib.util.module_from_spec(spec)
    exec(compile(b, str(p), 'exec'), module.__dict__)
    return module


F = feature_source()
A = 'experiments/sota-2026-10-22/audit/epoch47/'
OLD = Path('/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725/private')
FEATURE_REF = {'path': str(OLD / 'DEV_FEATURES.json'), 'bytes': 73969,
               'sha256': '73443811bc58206012d6abbb1d1e738418d99a691706f19e9e1966722abdd21f'}
VAULT_REF = {'path': str(OLD / 'DEV_GOLD.vault.json'), 'bytes': 1178,
             'sha256': '6c4a5f6d1683b8d4fdc934a7fcca40fb8c73dd1936705e06746fd78d009c4cd5'}
COUNTS = {'357': 25, '227': 53, '46': 56, '212': 42}


def same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def public_ref(r):
    F.require(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'},
              'EXACT_THREE_KEY_PUBLIC_REFERENCE')
    p = Path(r['path'])
    root = F.WORKDIR / 'project'
    p = p if p.is_absolute() else root / p
    F.require(p.absolute() == p.resolve() and p.is_relative_to(root),
              'PUBLIC_REFERENCE_OUTSIDE_E47_PROJECT')
    return r


def public_json(r):
    return F.load_ref(public_ref(r))


def envelope(v):
    F.require(type(v) is dict and type(v.get('schema_version')) is int and
              v['schema_version'] == 1 and type(v.get('epoch')) is int and
              v['epoch'] == 47 and v.get('kind') == F.KIND and
              v.get('phase') == 'dev', 'EXACT_E47_DEV_ENVELOPE')


def verify_slot_binding(plan, source, independent, approval):
    slot = plan['worker_slot_reservation']
    F.require(type(slot) is dict and
              all(same(slot, value['worker_slot_reservation']) for value in
                  [source, independent, approval]), 'TYPE_EXACT_SOURCE_PLAN_SLOT_CHAIN')
    owner_ref = plan['owner_ref']
    F.require(type(owner_ref) is dict and set(owner_ref) == {'path', 'bytes', 'sha256'} and
              owner_ref['path'] == 'owner.json' and type(owner_ref['bytes']) is int and
              owner_ref['bytes'] > 0 and type(owner_ref['sha256']) is str and
              re.fullmatch('[0-9a-f]{64}', owner_ref['sha256']) and
              slot['owner_sha256'] == owner_ref['sha256'] and
              type(slot['epoch']) is int and slot['epoch'] == 47 and
              slot['kind'] == F.KIND and slot['phase'] == 'dev' and
              all(type(slot[k]) is int and slot[k] > 0 for k in
                  ['generation', 'pid', 'startticks']) and
              type(slot['reserved_worker_slots']) is int and slot['reserved_worker_slots'] == 1 and
              type(slot['reservation_token']) is str and
              re.fullmatch('[0-9a-f]{64}', slot['reservation_token']) and
              slot['permanently_burned_at_SOURCE_publication'] is True,
              'SOURCE_BURNED_E47_SLOT_AND_OWNER_CAPABILITY')
    return slot


def verify_actual_source_before_data(approval, policy_ref, seal_ref):
    plan_ref = approval['source_plan']
    source_ref = approval['source_admission']
    plan = public_json(plan_ref)
    source = public_json(source_ref)
    envelope(plan)
    envelope(source)
    freeze = public_json(plan['source_freeze'])
    ind = public_json(source['independent_actual_source_readback'])
    envelope(ind)
    F.require(plan['source_checkpoint'] == F.SOURCE and
              plan['source_bindings_ready'] is True and
              same(plan['data_roles'], {'train': [], 'dev': list(F.DEV_CASE_IDS),
                                       'calibration': [], 'confirmation': []}) and
              plan['used_confirmation_identities'] == [] and
              plan['data_custody_mode'] == 'REUSE_E44_EXPOSED_DEV_ASSETS',
              'EXACT_FROZEN_REUSE_SOURCE_PLAN')
    ps = plan_ref['sha256']
    F.require(source['checks_passed'] is True and
              source['verified_actual_remote_readback'] is True and
              source['actual_source_commit'] == source['published_source_commit'] ==
              approval['source_commit'] == ind['commit'] and
              re.fullmatch('[0-9a-f]{40}', approval['source_commit']) and
              source['source_plan_sha256'] == source['plan_sha256'] == ps ==
              ind['source_plan_sha256'] and ind['checks_passed'] is True and
              ind['verified_actual_remote_readback'] is True and
              source['source_freeze_sha256'] == ind['source_freeze_sha256'] ==
              plan['source_freeze']['sha256'] and source['tree_sha'] == ind['tree_sha'],
              'ACTUAL_INDEPENDENT_SOURCE_READBACK_BEFORE_OPAQUE_ACCESS')
    verify_slot_binding(plan, source, ind, approval)
    files = freeze['files']
    F.require(type(files) is list and files and
              len({r['path'] for r in files}) == len(files), 'EXACT_SOURCE_FREEZE_FILES')
    for r in files:
        F.read_ref(public_ref(r))
    for r in [policy_ref, seal_ref]:
        F.require(any(same(r, x) for x in files), 'POLICY_AND_SEAL_IN_ACTUAL_SOURCE')
    return plan, files, {'source_commit': approval['source_commit'],
                         'source_plan_sha256': ps,
                         'source_freeze_sha256': plan['source_freeze']['sha256'],
                         'source_admission': source_ref, 'source_plan': plan_ref}


def opaque_copy(ref, target):
    """Stable bounded regular-file read; exact hash; exclusive opaque write."""
    return F.put_bytes(target, F.read_ref(ref))


def safe_error(error):
    return {'code': 'OPAQUE_REUSE_FAILED_FINAL_NO_RETRY',
            'exception_type': type(error).__name__,
            'message_sha256': F.sha(str(error).encode())}


def materialize(out, policy_ref, seal_ref, approval_ref):
    policy = public_json(policy_ref)
    seal = public_json(seal_ref)
    approval = public_json(approval_ref)
    for value in [policy, seal, approval]:
        envelope(value)
    F.require(policy['source_checkpoint'] == seal['source_checkpoint'] ==
              approval['source_checkpoint'] == F.SOURCE and
              seal['policy_sha256'] == policy_ref['sha256'], 'EXACT_POLICY_AND_SOURCE_SEAL')
    review = public_json(approval['independent_source_review'])
    F.require(review['checks_passed'] is True and
              review['policy_sha256'] == policy_ref['sha256'] and
              review['source_seal_sha256'] == seal_ref['sha256'] and
              approval['root_one_custodian_authorized'] is True and
              approval['all_candidate_and_custody_source_frozen_before_data_access'] is True and
              approval['policy_sha256'] == policy_ref['sha256'] and
              approval['predataseal_sha256'] == seal_ref['sha256'],
              'EXACT_INDEPENDENT_REVIEW_AND_ROOT_ONCE_AUTHORIZATION')
    plan, frozen, binding = verify_actual_source_before_data(approval, policy_ref, seal_ref)
    node_ref = approval['node_runtime_admission']
    node = public_json(node_ref)
    envelope(node)
    manifest = public_json(plan['node_runtime_manifest'])
    expected_node = dict(manifest['executable'],
                         observed_local_version=manifest['observed_local_version'],
                         full_payload_hash_verified=True, ELF64_x86_64=True,
                         native_helper_or_module_initialized=False,
                         upstream_binary_reproducibility='NOT_ESTABLISHED_LOCAL_EXECUTABLE_PIN_ONLY')
    F.require(node['checks_passed'] is True and
              all(node[k] == binding[k] for k in
                  ['source_commit', 'source_plan_sha256', 'source_freeze_sha256']) and
              same(node['node_runtime_receipt'], expected_node) and
              plan['node_executable'] == manifest['executable']['path'] and
              any(same(plan['node_runtime_manifest'], x) for x in frozen) and
              any(same(plan['node_runtime_guard_source'], x) for x in frozen),
              'SOURCE_BOUND_METADATA_NODE_ADMISSION_BEFORE_OPAQUE_REUSE')
    F.require(policy['custody_mode'] == 'REUSE_E44_EXPOSED_DEV_ASSETS' and
              same(policy['reuse_source_features'], FEATURE_REF) and
              same(policy['reuse_source_vault'], VAULT_REF) and
              policy['case_ids'] == list(F.DEV_CASE_IDS) and
              policy['selected_document_ids'] == list(F.DEV_DOCUMENT_IDS) and
              policy['selected_hypothesis_ids'] == list(F.HYPOTHESIS_IDS) and
              policy['protected_confirmation_document_ids'] == list(F.PROTECTED_DOCUMENT_IDS) and
              same(policy['source_units_per_document'], COUNTS) and
              policy['source_units_total'] == 176 and
              policy['feature_vault_origin_kind'] == F.ORIGIN_KIND and
              plan['feature_vault_origin_kind'] == F.ORIGIN_KIND and
              policy['semantic_gold_decodes_authorized'] == 0 and
              same(policy['data_roles'], plan['data_roles']), 'EXACT_EXPOSED_REUSE_POLICY')
    for r in seal['source_files']:
        F.read_ref(public_ref(r))
        F.require(any(same(r, x) for x in frozen), 'CUSTODY_SOURCE_IN_FULL_FREEZE')
    own = next(r for r in seal['source_files'] if Path(r['path']).name == 'e47_materialize.py')
    F.require(F.sha(Path(__file__).read_bytes()) == own['sha256'], 'EXECUTED_CUSTODY_SOURCE_DRIFT')
    prior_ref = policy['prior_data_admission']
    prior_review_ref = policy['prior_independent_data_review']
    for r in [prior_ref, prior_review_ref]:
        F.require(any(same(r, x) for x in frozen), 'PRIOR_METADATA_IN_NEW_SOURCE_FREEZE')
    prior = public_json(prior_ref)
    prior_review = public_json(prior_review_ref)
    F.require(prior['epoch'] == 44 and prior['errors'] == [] and
              prior['status'] == 'READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT' and
              prior['selected_ids'] == list(F.DEV_CASE_IDS) and
              same(prior['private_features'], FEATURE_REF) and
              same(prior['private_vault'], VAULT_REF) and
              prior['semantic_gold_values_decoded'] == 0 and
              prior['selected_raw_choice_tokens_copied'] == 12 and
              prior['protected_confirmation_body_or_choice_decodes'] == 0 and
              prior_review['checks_passed'] is True and
              same(prior_review['private_features_ref'], FEATURE_REF) and
              same(prior_review['private_vault_ref'], VAULT_REF) and
              prior_review['semantic_gold_decodes'] == 0 and
              same(prior_review['source_units_per_document'], COUNTS),
              'AUTHENTICATED_PRIOR_EXPOSED_ASSET_METADATA')
    out = Path(out)
    F.require(out == F.WORKDIR / 'private' and out.absolute() == out.resolve() and
              policy['public_data_admission_path'] == str(F.WORKDIR / 'project' / A / 'DATA_ADMISSION.json'),
              'EXACT_NEW_PRIVATE_CUSTODY_AND_PUBLIC_REPORT_PATHS')
    out.mkdir(mode=0o700, exist_ok=True)
    marker = out / 'DATA_MATERIALIZATION_ATTEMPT.json'
    F.require(not any((out / n).exists() or (out / n).is_symlink() for n in
                      ['DATA_MATERIALIZATION_ATTEMPT.json', 'DEV_FEATURES.json',
                       'DEV_GOLD.vault.json', 'DEV_GOLD_JOINED.json']) and
              not Path(policy['public_data_admission_path']).exists(),
              'ONCE_REUSE_OUTPUTS_MUST_BE_ABSENT')
    F.put(marker, {'schema_version': 1, 'epoch': 47, 'kind': F.KIND, 'phase': 'dev',
                   'policy': policy_ref, 'source_seal': seal_ref, 'automatic_retry': False,
                   'opaque_reuse_function_calls': 1, 'semantic_gold_values_decoded': 0})
    report = {'schema_version': 1, 'epoch': 47, 'kind': F.KIND, 'phase': 'dev',
              'source_checkpoint': F.SOURCE, **{k: binding[k] for k in
                 ['source_commit', 'source_plan_sha256', 'source_freeze_sha256']},
              'worker_slot_reservation': plan['worker_slot_reservation'],
              'evidence': {'policy': policy_ref, 'source_seal': seal_ref,
                           'root_approval': approval_ref, 'source_admission': binding['source_admission'],
                           'source_plan': binding['source_plan'], 'prior_data_admission': prior_ref,
                           'prior_independent_data_review': prior_review_ref,
                           'node_runtime_admission': node_ref},
              'status': 'DATA_ADMISSION_FAILED_FINAL_NO_RETRY',
              'custody_mode': 'REUSE_E44_EXPOSED_DEV_ASSETS',
              'selected_ids': list(F.DEV_CASE_IDS), 'feature_vault_origin_epoch': 44,
              'feature_vault_origin_kind': F.ORIGIN_KIND,
              'freshness': 'EXPOSED_DEV_FOREVER_NOT_FRESH',
              'reuse_source_features': FEATURE_REF, 'reuse_source_vault': VAULT_REF,
              'selected_raw_choice_tokens_copied': 0, 'inherited_opaque_choice_tokens': 12,
              'semantic_gold_values_decoded': 0, 'feature_vault_JSON_parses': 0,
              'source_body_or_hypothesis_decodes': 0, 'original_archive_reads': 0,
              'model_tokenizer_native_calls': 0, 'errors': [], 'used_confirmation_identities': [],
              'protected_confirmation_document_ids': list(F.PROTECTED_DOCUMENT_IDS),
              'protected_confirmation_body_or_choice_decodes': 0,
              'statistics': {'source_units_per_document': COUNTS, 'unique_source_units': 176,
                             'expanded_pair_source_units': 528, 'expected_BGE_texts': 188,
                             'expected_BGE_forward_calls': 36, 'native_indexes': 4, 'native_queries': 12,
                             'counts_source': 'Verified published E44 receipts; no new body parse'}}
    try:
        report['private_features'] = opaque_copy(FEATURE_REF, out / 'DEV_FEATURES.json')
        report['private_vault'] = opaque_copy(VAULT_REF, out / 'DEV_GOLD.vault.json')
        report['status'] = 'READY_REUSED_EXPOSED_DEV_FEATURES_AND_OPAQUE_VAULT'
    except Exception as error:
        report['errors'].append(safe_error(error))
    F.put(Path(policy['public_data_admission_path']), report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['out', 'policy', 'seal', 'approval']:
        parser.add_argument('--' + name, required=True)
    for name in ['policy', 'seal', 'approval']:
        parser.add_argument('--expected-' + name + '-sha256', required=True)
    args = parser.parse_args()
    refs = {}
    for name in ['policy', 'seal', 'approval']:
        r = F.ref(getattr(args, name))
        public_ref(r)
        F.require(r['sha256'] == getattr(args, 'expected_' + name + '_sha256'),
                  'EXACT_COMMAND_SOURCE_REFERENCE')
        refs[name] = r
    value = materialize(args.out, refs['policy'], refs['seal'], refs['approval'])
    print(json.dumps({k: value[k] for k in ['status', 'selected_ids',
                    'semantic_gold_values_decoded', 'selected_raw_choice_tokens_copied', 'errors']}))
