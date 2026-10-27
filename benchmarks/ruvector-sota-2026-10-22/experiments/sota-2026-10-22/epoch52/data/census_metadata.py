"""Whole-source metadata census; no corpus payload, labels, text or lengths used."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib
import json
import re

OUT = Path('/dev/shm/ruvector-e52-data')
P = Path('/dev/shm/ruvector-e51-data/provenance')
R = Path('/dev/shm/ruvector-e52-audit/remote-current')

def read(path):
    return json.loads(path.read_bytes())

cont = read(R / 'CONTINUATION.json')
ledger = read(Path('/dev/shm/ruvector-sota-2026-10-22/epoch51-0e1f4181df1f/project/experiments/sota-2026-10-22/epoch51/REJECTION_LEDGER.json'))
prior = read(P / 'IDENTITY_POLICY.v1.json')
audit = read(P / 'PRIOR_LEGAL96_AND_SPLIT_IDENTITY_AUDIT.v1.json')
e34 = read(P / 'exposure-metadata.json')
e9 = read(P / 'eligibility-manifest.json')
bindings = read(OUT / 'PROVENANCE_BINDINGS.v1.json')

# Only allowlisted metadata keys enter the census. No raw corpus files opened.
KEYS = ('document_id', 'source_split', 'normalized_document_sha256',
        'document_filename_key_sha256', 'metadata_exclusion_flags')
rows = [{k: row[k] for k in KEYS} for row in audit['official_dev_test_metadata']]
assert len(rows) == 184
assert Counter(r['source_split'] for r in rows) == {'dev': 61, 'test': 123}
assert len({(r['source_split'], r['document_id']) for r in rows}) == 184
by_key = {(r['source_split'], r['document_id']): r for r in rows}
train_ids = set(e9['eligible_document_ids']) | set(e9['excluded_document_ids'])
assert len(train_ids) == 423
train_hashes = set(e34['blocked_normalized_document_sha256']) | set(e34['catalog_selected_hashes'].values())
legal96_filename_hashes = {r['document_filename_key_sha256'] for r in audit['Legal96_identity_hashes']}

original_dev = set(e9['retired_confirmation']['originaldev_document_ids'])
assert original_dev == set(prior['retired_originalDEV96_document_ids'])
assert len(original_dev) == 32
exposed = defaultdict(list)
for doc in original_dev:
    exposed['dev', doc].append('original_DEV96_consumed_or_attempted_E8_whole_group')

# Exact role references in current durable controls, covering E40 through E50.
# All hypotheses in any exposed group are excluded, even when only 1/3 measured.
role_refs = []
for key, value in cont.items():
    if not re.fullmatch(r'epoch\d+_data_roles', key):
        continue
    roles = value.get('roles', value)
    for role in ('train', 'dev', 'calibration', 'confirmation'):
        ids = roles.get(role, [])
        for identity in ids:
            if not isinstance(identity, str):
                continue
            m = re.fullmatch(r'contractnli:eced6528:(dev|test):(\d+):nda-\d+', identity)
            if not m:
                continue
            group = (m[1], int(m[2]))
            role_refs.append({'control_key': key, 'role': role, 'identity': identity})
            if role != 'confirmation':
                exposed[group].append(key + ':' + role)

protected = defaultdict(list)
for item in role_refs:
    if item['role'] == 'confirmation':
        m = re.fullmatch(r'contractnli:eced6528:(dev|test):(\d+):nda-\d+', item['identity'])
        protected[m[1], int(m[2])].append(item['control_key'] + ':unused_confirmation_HOLD')
for doc in prior['existing_protected_confirmation_document_ids']:
    protected['test', doc].append('original_test_unused_confirmation_HOLD')
assert set(d for (s, d) in protected if s == 'dev') == {72, 44, 486, 3, 19, 45, 56, 12}
assert set(d for (s, d) in protected if s == 'test') == {62, 321, 2, 18, 225, 293, 361}

retired_hashes = {by_key[k]['normalized_document_sha256'] for k in exposed if k in by_key}
reserved_hashes = {by_key[k]['normalized_document_sha256'] for k in protected if k in by_key}
retired_filenames = {by_key[k]['document_filename_key_sha256'] for k in exposed if k in by_key}
reserved_filenames = {by_key[k]['document_filename_key_sha256'] for k in protected if k in by_key}
all_hashes = defaultdict(list)
for row in rows:
    all_hashes[row['normalized_document_sha256']].append((row['source_split'], row['document_id']))

for row in rows:
    key = (row['source_split'], row['document_id'])
    reasons = list(row['metadata_exclusion_flags'])
    if row['document_id'] in train_ids:
        reasons.append('official_TRAIN_source_ID_excluded')
    if row['normalized_document_sha256'] in train_hashes:
        reasons.append('official_TRAIN_normalized_document_hash_excluded')
    if row['document_filename_key_sha256'] in legal96_filename_hashes:
        reasons.append('Legal96_exposed_filename_hash_excluded')
    reasons.extend(exposed.get(key, []))
    reasons.extend(protected.get(key, []))
    if row['normalized_document_sha256'] in retired_hashes:
        reasons.append('historical_whole_group_exposed_normalized_hash')
    if row['normalized_document_sha256'] in reserved_hashes:
        reasons.append('protected_confirmation_normalized_hash')
    if row['document_filename_key_sha256'] in retired_filenames:
        reasons.append('historical_whole_group_exposed_filename_hash')
    if row['document_filename_key_sha256'] in reserved_filenames:
        reasons.append('protected_confirmation_filename_hash')
    if len(all_hashes[row['normalized_document_sha256']]) > 1:
        reasons.append('cross_source_duplicate_normalized_hash')
    row['exclusion_reasons'] = sorted(set(reasons))
    row['project_unused_unassigned_metadata_eligible'] = not reasons

pools = {s: [r for r in rows if r['source_split'] == s and not r['exclusion_reasons']]
         for s in ('dev', 'test')}
assert len(pools['dev']) == 9
assert pools['test'] == []
assert not (retired_hashes & {r['normalized_document_sha256'] for rs in pools.values() for r in rs})
assert not (reserved_hashes & {r['normalized_document_sha256'] for rs in pools.values() for r in rs})

facts = {
    'schema_version': 1, 'epoch': 52, 'created_at': datetime.now(timezone.utc).isoformat(),
    'source_checkpoint': bindings['fresh_root_HEAD'],
    'kind': 'LABEL_BLIND_FULL_HISTORICAL_SOURCE_GROUP_HASH_EXCLUSION_CENSUS',
    'dataset': {'repository': 'stanfordnlp/contract-nli',
        'revision': 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'dataset_license': 'CC-BY-4.0', 'official_code_license': 'Apache-2.0',
        'official_split_counts': {'train': 423, 'dev': 61, 'test': 123}},
    'metadata_only': True, 'case_payloads_opened': 0, 'labels_or_choices_decoded': 0,
    'confirmation_payload_accesses': 0, 'source_text_or_source_lengths_used_for_selection': False,
    'model_tokenizer_native_Gold_calls': 0, 'scientific_slots_admitted': 0,
    'roles_selected_or_frozen': False,
    'all423_official_TRAIN_source_groups_excluded_from_confirmation': True,
    'all423_TRAIN_source_IDs': sorted(train_ids),
    'historical_TRAIN_normalized_document_hashes': sorted(train_hashes),
    'historical_train_group_partition_current': {'exposed': 325, 'protected_confirmation': 24, 'unassigned': 74},
    'historical_TRAIN_hash_scope': 'Current pinned E34 blocked+catalog metadata covers all officialTRAIN source groups by ID; hashes used to exclude cross-split aliases. No protected bodies opened.',
    'Legal96_exposed_filename_hashes': sorted(legal96_filename_hashes),
    'historical_exposed_dev_test_groups': [{'source_split': k[0], 'document_id': k[1],
        'source_control_roles': sorted(set(v)), 'all_hypotheses_excluded': True}
        for k, v in sorted(exposed.items())],
    'protected_unused_confirmation_dev_test_groups': [{'source_split': k[0], 'document_id': k[1],
        'source_control_roles': sorted(set(v)), 'all_hypotheses_protected': True}
        for k, v in sorted(protected.items())],
    'historical_exact_typed_role_references_from_current_CONT': role_refs,
    'all184_official_dev_test_metadata_and_exclusion_census': rows,
    'eligible_metadata_counts': {s: len(rs) for s, rs in pools.items()},
    'eligible_metadata_pools': pools,
    'cross_source_duplicate_normalized_hash_groups': [ks for ks in all_hashes.values() if len(ks) > 1],
    'metadata_feasibility': {'four_project_unused_DEV_from_official_dev_and_four_project_unused_CONF_from_official_test': False,
        'four_project_unused_DEV_available_existing_four_TEST_CF_reserved_HOLD': True,
        'official_dev_may_be_pretrained_checkpoint_development_exposed': True,
        'official_test_independently_verified_unseen_by_selected_checkpoint': False,
        'model_training_lineage_qualification_pending_independent_review': True,
        'no_checkpoint_unseen_claim_for_DEV': True},
    'future_requirements': ['Root/audit model-lineage decision before role selection',
        'New exact DEV/train/cal/CONF identities and case budget frozen before any measurement',
        'DEV exposure retires whole source groups and all hypotheses permanently',
        'No replacement on class support, capacity, admission or collision failure',
        'Exact archive/member/selected-ID/hash rechecks in isolated custody before input admission',
        'No CONF payload/Gold in E52: existing TEST reservation remains UNQUALIFIED_HOLD; no lineage probe, replacement or admission'],
    'protected_E48_E50_original_and_train_CF_retained': True,
    'source_provenance': bindings,
    'public_limitations': ['Project-unused is distinct from checkpoint-unseen.',
        'Public foundation/pretraining overlap remains unknown.',
        'A model card split declaration is weaker evidence than an exact training/evaluation ID manifest.',
        'This is metadata feasibility, not a score, data admission or official result.'],
}
payload = (json.dumps(facts, sort_keys=True, indent=2) + '\n').encode()
dest = OUT / 'FULL_HISTORICAL_SOURCE_GROUP_HASH_CENSUS.v1.json'
with dest.open('xb') as f:
    f.write(payload)
print(json.dumps({'path': str(dest), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
    'pools': {s: [r['document_id'] for r in rs] for s, rs in pools.items()},
    'train_hash_count': len(train_hashes), 'exposed_dev_test_group_count': len(exposed),
    'protected_dev_test_group_count': len(protected), 'roles_selected': False}))
