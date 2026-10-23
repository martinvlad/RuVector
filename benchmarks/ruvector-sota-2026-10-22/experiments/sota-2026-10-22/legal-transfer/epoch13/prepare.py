"""Freeze one source-only DEV draw before annotation projection or model choice."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import build

HERE = Path(__file__).resolve().parent
S = HERE.parents[1]
KIT = S / 'epoch13/durable-kit'
SOURCE = S / 'epoch13/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
CONF_REL = 'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl'
CONF_SHA = '850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
PARENT = 'cd18a712d1adbaba92d7c26080923b437ae36af8'
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
assert load(S / 'epoch13/data-restoration.json')['model_calls'] == 0
pins = {item['path']: item for item in manifest['project_files']}
required = [BASE + 'legal-transfer/epoch12/eligibility-manifest.json',
            BASE + 'epoch12/USED_IDENTITIES.json',
            BASE + 'legal-transfer/epoch12/confirmation-allowlist.json',
            BASE + 'legal-transfer/epoch12/CC-BY-4.0.txt', CONF_REL]
for relative in required:
    assert sha(KIT / relative) == pins[relative]['sha256']
    assert (KIT / relative).stat().st_size == pins[relative]['bytes']
assert sha(KIT / CONF_REL) == CONF_SHA  # Byte hash only; never parse reserved CONF.
assert sha(SOURCE) == build.SOURCE_SHA
registry = load(KIT / required[0])
used = load(KIT / required[1])
confirmation_metadata = load(KIT / required[2])
id_of = lambda group: int(group.rsplit(':', 1)[1])
old = set(registry['excluded_document_ids']) | {
    id_of(group) for group in used['source_frozen_roles']['development']['source_groups']}
reserved = {id_of(item['source_group']) for item in confirmation_metadata['records']}
assert len(old) == 181 and len(reserved) == 16 and not old & reserved
source = load(SOURCE)
documents = {document['id']: document for document in source['documents']}
eligible = set(documents) - old - reserved
assert len(documents) == 423 and len(eligible) == 226
hashes = {document_id: hashlib.sha256(build.norm(document['text']).encode()).hexdigest()
          for document_id, document in documents.items()}
cross_ids = {item['document_id'] for item in registry['cross_split_documents']}
cross_hashes = {item['normalized_document_sha256'] for item in registry['cross_split_documents']}
blocked = {hashes[document_id] for document_id in old | reserved} | cross_hashes
assert not eligible & cross_ids and not {hashes[document_id] for document_id in eligible} & blocked
shutil.copy2(KIT / required[3], HERE / 'CC-BY-4.0.txt')
save('restored-source-verification.json', {
    'at': now(), 'checkpoint_commit': PARENT,
    'checkpoint_manifest_sha256': continuation['checkpoint_manifest_sha256'],
    'restored_pins_verified': [pins[relative] for relative in required],
    'original_train_sha256': build.SOURCE_SHA,
    'confirmation_access': 'Reserved projection byte hash and metadata allowlist only; no reserved labels parsed, selected or fitted.',
    'native_model_paid_calls': 0})
save('eligibility-manifest.json', {
    'schema_version': 1, 'checkpoint_commit': PARENT, 'source_sha256': build.SOURCE_SHA,
    'excluded_document_ids': sorted(old), 'reserved_confirmation_document_ids': sorted(reserved),
    'eligible_document_ids': sorted(eligible),
    'counts': {'officialtrain': 423, 'exposed': 181, 'reserved_confirmation': 16,
               'eligible_unreserved': 226},
    'cross_split_documents': registry['cross_split_documents'],
    'cross_split_labels_used_for_selection': False,
    'old_and_reserved_normalized_document_sha256': sorted({hashes[document_id] for document_id in old | reserved}),
    'selected_cross_split_or_prior_text_collisions': 0,
    'previous_registry_sha256': sha(KIT / required[0]),
    'used_identity_manifest_sha256': sha(KIT / required[1]),
    'prior_roles_preserved': 'Excluded means already exposed with original TRAIN/DEV roles preserved; this epoch does not relabel prior TRAIN as DEV.',
    'current_train': [], 'current_calibration': []})
salt = 'ruvector-sota-epoch13-new-dev24-v1|'
save('draw-plan.json', {
    'schema_version': 1, 'source_sha256': build.SOURCE_SHA, 'source_commit': build.SOURCE_COMMIT,
    'eligibility_manifest_sha256': sha(HERE / 'eligibility-manifest.json'),
    'salt': salt, 'hypotheses': build.HYPOTHESES, 'dev_documents': 8, 'train': [], 'calibration': [],
    'selection': 'One source-text/ID-only SHA256 rank; first8 of226 new eligible documents. No labels, outcomes, length stratification, balancing or redraw.',
    'confirmation_preserved_sha256': CONF_SHA})
chosen = build.rank(eligible, documents, salt)[:8]
roles_at = now()
save('document-selection.json', {
    'schema_version': 1, 'frozen_at': roles_at, 'draw_plan_sha256': sha(HERE / 'draw-plan.json'),
    'gold_access_for_selection': False, 'documents': build.role_records(chosen),
    'train': [], 'calibration': [],
    'confirmation': 'Preserve exact epoch9 reserved48; labels are unavailable for selection or fitting'})
rows = build.draw(SOURCE)
with (HERE / 'development24.jsonl').open('x') as stream:
    for row in rows:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
save('dev-allowlist.json', build.allow(rows, sha(HERE / 'development24.jsonl')))
shutil.copy2(KIT / required[2], HERE / 'confirmation-allowlist.json')
contract = {
    'schema_version': 1, 'frozen': True, 'frozen_at': now(), 'checkpoint_parent': PARENT,
    'scope': 'Internal source-licensed original ContractNLI three-predicate NDA pilot; one frozen zero-shot pretrained architecture test, no fitting or calibration. Not full LegalBench, current JevBench300 or ClaimBench.',
    'train': [], 'calibration': [], 'training_questions': 0, 'training_feature_questions': 0,
    'fitting': {'training_feature_queries': 0, 'calibration_queries': 0, 'supervised_fit': False,
                'model_precision_or_threshold_selection': False, 'temperature': 1.0},
    'development': {'path': BASE + 'legal-transfer/epoch13/development24.jsonl',
                    'sha256': sha(HERE / 'development24.jsonl'), 'queries': 24, 'document_groups': 8,
                    'status': 'New project-unused groups for one frozen gate; no fitting or calibration; becomes exposed DEV permanently after attempt'},
    'confirmation': {'path': CONF_REL, 'sha256': CONF_SHA, 'queries': 48, 'document_groups': 16,
                     'status': 'Existing epoch9 bank unchanged/project-model-unused; metadata only until frozen development gates pass. No labels for candidate selection or fitting.',
                     'allowlist_path': BASE + 'legal-transfer/epoch13/confirmation-allowlist.json',
                     'allowlist_sha256': sha(HERE / 'confirmation-allowlist.json')},
    'roles_frozen_before_new_gold_projection_at': roles_at,
    'draw': {'plan_sha256': sha(HERE / 'draw-plan.json'),
             'selection_sha256': sha(HERE / 'document-selection.json'), 'eligible_unreserved_before': 226,
             'new_DEV_groups': 8, 'unreserved_remaining_after': 218, 'prior_exposed_train_groups': 181,
             'reserved_confirmation_groups': 16, 'new_TRAIN_exposure_groups': 0,
             'selection_uses_labels_or_outcomes': False},
    'source': {'repository': 'stanfordnlp/contract-nli', 'commit': build.SOURCE_COMMIT,
               'member': 'contract-nli/train.json', 'member_sha256': build.SOURCE_SHA,
               'archive_sha256': 'e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b',
               'license': 'CC-BY-4.0', 'license_sha256': sha(HERE / 'CC-BY-4.0.txt')},
    'inference_boundary': {'only': ['state', 'questions'],
                           'forbidden': ['gold', 'evidence annotations', 'record IDs as model features', 'source groups', 'roles', 'provenance'],
                           'original_threeway_label_field': 'evaluation.original_threeway_label',
                           'binary_mapping': build.LABELS},
    'metadata_only_allowlists': {role: {'path': name, 'sha256': sha(HERE / name)}
                                for role, name in [('dev', 'dev-allowlist.json'), ('confirmation', 'confirmation-allowlist.json')]},
    'data_files': {'development24.jsonl': {'sha256': sha(HERE / 'development24.jsonl'), 'queries': 24, 'document_groups': 8, 'role': 'dev'},
                   'confirmation48.jsonl': {'sha256': CONF_SHA, 'queries': 48, 'document_groups': 16, 'role': 'confirmation', 'path': CONF_REL}},
    'limitations': 'Public-source project novelty only; upstream pretraining/fuzzy-version overlap unknown. Prior exposed roles remain fixed: previous designated DEV stays DEV and previous TRAIN is not relabeled as fresh DEV. No confirmation labels used to choose candidate.',
    'native_model_paid_calls': 0, 'official_score': None, 'official_rank': None}
save('data-contract.json', contract)
save('data-ids.json', {'schema_version': 1, 'train': [], 'calibration': [],
                     'development': load(HERE / 'dev-allowlist.json'), 'confirmation': confirmation_metadata,
                     'contains_labels_or_inputs': False})
print(json.dumps({'frozen_at': contract['frozen_at'], 'roles_at': roles_at,
                  'data_contract_sha256': sha(HERE / 'data-contract.json'),
                  'DEV_sha256': sha(HERE / 'development24.jsonl'),
                  'DEV_group_ids': [document_id for _, document_id, _ in chosen],
                  'confirmation_sha256': CONF_SHA, 'train': [], 'calibration': [],
                  'native_model_paid_calls': 0}))
