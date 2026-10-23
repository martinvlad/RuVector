"""Freeze source-only DEV and reused TRAIN sanity roles before annotation projection."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import build

HERE = Path(__file__).resolve().parent
S = HERE.parents[1]
KIT = S / 'epoch12/durable-kit'
SOURCE = S / 'epoch12/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
CONF_REL = 'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl'
CONF_SHA = '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
PARENT = 'edb193532821ddc43084eca932f36ec29d045b60'
BASE = 'experiments/sota-2026-10-22/'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    with (HERE / name).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


assert not (HERE / 'data-contract.json').exists(), 'No redraw or overwrite'
continuation = load(KIT / 'CONTINUATION.json')
manifest = load(KIT / 'CHECKPOINT_MANIFEST.json')
assert sha(KIT / 'CHECKPOINT_MANIFEST.json') == continuation['checkpoint_manifest_sha256']
assert load(S / 'epoch12/data-restoration.json')['model_calls'] == 0
pins = {x['path']: x for x in manifest['project_files']}
required = [BASE + 'legal-transfer/epoch11/eligibility-manifest.json',
            BASE + 'epoch11/USED_IDENTITIES.json',
            BASE + 'legal-transfer/epoch11/confirmation-allowlist.json',
            BASE + 'legal-transfer/epoch11/CC-BY-4.0.txt',
            BASE + 'legal-transfer/epoch10/train-allowlist.json', CONF_REL]
for relative in required:
    assert sha(KIT / relative) == pins[relative]['sha256']
    assert (KIT / relative).stat().st_size == pins[relative]['bytes']
assert sha(KIT / CONF_REL) == CONF_SHA  # Byte hashing only; no CONF JSON parse.
assert sha(SOURCE) == build.SOURCE_SHA
registry = load(KIT / required[0])
used = load(KIT / required[1])
confirmation_metadata = load(KIT / required[2])
train_metadata = load(KIT / required[4])
id_of = lambda group: int(group.rsplit(':', 1)[1])
old = set(registry['excluded_document_ids']) | {
    id_of(group) for group in used['source_frozen_roles']['development']['source_groups']}
reserved = {id_of(x['source_group']) for x in confirmation_metadata['records']}
train_pool = {id_of(x['source_group']) for x in train_metadata['records']}
assert len(old) == 173 and len(reserved) == 16 and not old & reserved
assert len(train_pool) == 24 and train_pool <= old
source = load(SOURCE)
docs = {doc['id']: doc for doc in source['documents']}
eligible = set(docs) - old - reserved
assert len(docs) == 423 and len(eligible) == 234
hashes = {i: hashlib.sha256(build.norm(doc['text']).encode()).hexdigest() for i, doc in docs.items()}
cross_ids = {x['document_id'] for x in registry['cross_split_documents']}
cross_hashes = {x['normalized_document_sha256'] for x in registry['cross_split_documents']}
blocked = {hashes[i] for i in old | reserved} | cross_hashes
assert not eligible & cross_ids and not {hashes[i] for i in eligible} & blocked
assert not train_pool & (reserved | cross_ids)
assert not {hashes[i] for i in train_pool} & (cross_hashes | {hashes[i] for i in reserved})
shutil.copy2(KIT / required[3], HERE / 'CC-BY-4.0.txt')
save('restored-source-verification.json', {
    'at': now(), 'checkpoint_commit': PARENT,
    'checkpoint_manifest_sha256': continuation['checkpoint_manifest_sha256'],
    'restored_pins_verified': [pins[x] for x in required], 'original_train_sha256': build.SOURCE_SHA,
    'confirmation_access': 'CONF projection byte hash only; metadata allowlist only. Reserved annotations not inspected, selected or fitted.',
    'native_model_paid_calls': 0})
save('eligibility-manifest.json', {
    'schema_version': 1, 'checkpoint_commit': PARENT, 'source_sha256': build.SOURCE_SHA,
    'excluded_document_ids': sorted(old), 'reserved_confirmation_document_ids': sorted(reserved),
    'eligible_document_ids': sorted(eligible), 'training_sanity_reuse_document_ids': sorted(train_pool),
    'counts': {'officialtrain': 423, 'exposed': 173, 'reserved_confirmation': 16,
               'eligible_unreserved': 234, 'reused_TRAIN_pool': 24},
    'cross_split_documents': registry['cross_split_documents'], 'cross_split_labels_used_for_selection': False,
    'old_and_reserved_normalized_document_sha256': sorted({hashes[i] for i in old | reserved}),
    'selected_cross_split_or_prior_text_collisions': 0,
    'previous_registry_sha256': sha(KIT / required[0]), 'used_identity_manifest_sha256': sha(KIT / required[1]),
    'training_sanity_pool_metadata_sha256': sha(KIT / required[4])})
dev_salt = 'ruvector-sota-epoch12-new-dev24-v1|'
train_salt = 'ruvector-sota-epoch12-reused-train-sanity6-v1|'
save('draw-plan.json', {
    'schema_version': 1, 'source_sha256': build.SOURCE_SHA,
    'source_commit': 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
    'eligibility_manifest_sha256': sha(HERE / 'eligibility-manifest.json'),
    'salt': dev_salt, 'train_sanity_salt': train_salt, 'hypotheses': ['nda-17', 'nda-7', 'nda-3'],
    'dev_documents': 8, 'train_sanity_documents': 2, 'calibration': [],
    'selection': 'One source-text/ID-only SHA256 rank: first8 of234 new eligible DEV; independently first2 of24 already-exposed e10TRAIN groups. No label/outcome/length stratification or redraw.',
    'confirmation_preserved_sha256': CONF_SHA})
dev = build.rank(eligible, docs, dev_salt)[:8]
train = build.rank(train_pool, docs, train_salt)[:2]
roles_at = now()
save('document-selection.json', {
    'schema_version': 1, 'frozen_at': roles_at, 'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
    'gold_access_for_selection': False, 'documents': build.role_records(dev, 'dev'),
    'train_sanity_documents': build.role_records(train, 'train_sanity'), 'calibration': [],
    'confirmation': 'Preserve exact epoch9 reserved48; no confirmation labels selected or fitted'})
for role, filename, allowname in [('dev', 'development24.jsonl', 'dev-allowlist.json'),
                                 ('train_sanity', 'train-sanity6.jsonl', 'train-allowlist.json')]:
    rows = build.draw(SOURCE, role)
    with (HERE / filename).open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    save(allowname, build.allow(rows, sha(HERE / filename), role))
shutil.copy2(KIT / required[2], HERE / 'confirmation-allowlist.json')
contract = {
    'schema_version': 1, 'frozen': True, 'frozen_at': now(), 'checkpoint_parent': PARENT,
    'scope': 'Internal source-licensed original ContractNLI three-predicate NDA pilot. Fixed pretrained FP32 versus quantized source-fidelity study; no fitting or precision selection. Not full LegalBench, current JevBench300 or ClaimBench.',
    'train': {'path': BASE + 'legal-transfer/epoch12/train-sanity6.jsonl',
              'sha256': sha(HERE / 'train-sanity6.jsonl'), 'queries': 6, 'questions': 6, 'document_groups': 2,
              'status': 'REUSED_TRAIN_SANITY_NO_FIT_NO_SELECTION; already exposed, never fresh benchmark generalization',
              'allowlist_path': BASE + 'legal-transfer/epoch12/train-allowlist.json',
              'allowlist_sha256': sha(HERE / 'train-allowlist.json')},
    'calibration': [], 'training_questions': 6, 'training_feature_questions': 0, 'train_sanity_questions': 6,
    'fitting': {'train_sanity_queries': 6, 'training_feature_queries': 0, 'calibration_queries': 0,
                'supervised_fit': False, 'model_precision_or_threshold_selection': False, 'temperature': 1.0},
    'development': {'path': BASE + 'legal-transfer/epoch12/development24.jsonl',
                    'sha256': sha(HERE / 'development24.jsonl'), 'queries': 24, 'document_groups': 8,
                    'status': 'New project-unused groups; one frozen gate, no fitting, selection or calibration'},
    'confirmation': {'path': CONF_REL, 'sha256': CONF_SHA, 'queries': 48, 'document_groups': 16,
                     'status': 'Existing epoch9 bank unchanged/project-model-unused; no labels for selection or fitting; scorer/auditor only after frozen gates',
                     'allowlist_path': BASE + 'legal-transfer/epoch12/confirmation-allowlist.json',
                     'allowlist_sha256': sha(HERE / 'confirmation-allowlist.json')},
    'roles_frozen_before_new_gold_projection_at': roles_at,
    'draw': {'plan_sha256': sha(HERE / 'draw-plan.json'),
             'selection_sha256': sha(HERE / 'document-selection.json'), 'eligible_unreserved_before': 234,
             'new_DEV_groups': 8, 'unreserved_remaining_after': 226, 'prior_exposed_train_groups': 173,
             'reserved_confirmation_groups': 16, 'reused_TRAIN_groups': 2, 'new_TRAIN_exposure_groups': 0,
             'selection_uses_labels_or_outcomes': False},
    'source': {'repository': 'stanfordnlp/contract-nli', 'commit': 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
               'member': 'contract-nli/train.json', 'member_sha256': build.SOURCE_SHA,
               'archive_sha256': 'e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b',
               'license': 'CC-BY-4.0', 'license_sha256': sha(HERE / 'CC-BY-4.0.txt')},
    'inference_boundary': {'only': ['state', 'questions'],
                           'forbidden': ['gold', 'evidence annotations', 'record IDs as model features', 'source groups', 'roles', 'provenance'],
                           'train_example_id_use': 'Boundary allowlist membership only; never model input',
                           'original_threeway_label_field': 'evaluation.original_threeway_label',
                           'binary_mapping': build.LABELS},
    'metadata_only_allowlists': {role: {'path': name, 'sha256': sha(HERE / name)}
                                for role, name in [('train', 'train-allowlist.json'), ('dev', 'dev-allowlist.json'),
                                                   ('confirmation', 'confirmation-allowlist.json')]},
    'data_files': {'train-sanity6.jsonl': {'sha256': sha(HERE / 'train-sanity6.jsonl'), 'queries': 6, 'document_groups': 2, 'role': 'train_sanity'},
                   'development24.jsonl': {'sha256': sha(HERE / 'development24.jsonl'), 'queries': 24, 'document_groups': 8, 'role': 'dev'},
                   'confirmation48.jsonl': {'sha256': CONF_SHA, 'queries': 48, 'document_groups': 16, 'role': 'confirmation', 'path': CONF_REL}},
    'limitations': 'Public-source project novelty only; unknown upstream pretraining/fuzzy versions. All previous exposed sets remain DEV forever. TRAIN sanity has no new generalization claim. Fixed FP32 candidate is not chosen from TRAIN outcomes.',
    'native_model_paid_calls': 0, 'official_score': None, 'official_rank': None}
save('data-contract.json', contract)
save('data-ids.json', {'schema_version': 1, 'train': load(HERE / 'train-allowlist.json'),
                     'calibration': [], 'development': load(HERE / 'dev-allowlist.json'),
                     'confirmation': confirmation_metadata, 'contains_labels_or_inputs': False})
print(json.dumps({'frozen_at': contract['frozen_at'], 'roles_at': roles_at,
                  'data_contract_sha256': sha(HERE / 'data-contract.json'),
                  'DEV_sha256': sha(HERE / 'development24.jsonl'),
                  'TRAIN_sanity_sha256': sha(HERE / 'train-sanity6.jsonl'),
                  'DEV_group_ids': [i for _, i, _ in dev], 'TRAIN_group_ids': [i for _, i, _ in train],
                  'confirmation_sha256': CONF_SHA, 'fitting': False, 'native_model_paid_calls': 0}))
