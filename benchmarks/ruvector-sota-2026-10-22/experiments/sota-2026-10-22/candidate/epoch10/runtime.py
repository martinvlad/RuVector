"""Native RuVector with fixed context policy and a once-fitted legal3way head."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = '0bc127ff92ffd9a3362517010c86e9d4d5113950d17e31a24af79090a165d9c5'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FROZEN9 = module('epoch10_frozen9', HERE.parent / 'epoch9/runtime.py')
FROZEN6 = FROZEN9.FROZEN6
FROZEN4 = FROZEN6.PREVIOUS
MODELS = module('epoch10_models', HERE / 'models.py')
HEAD = MODELS.HEAD


def pinned_json(path, expected):
    if HEAD.sha(path) != expected:
        raise ValueError('Frozen source/role contract identity changed: ' + str(path))
    return json.loads(Path(path).read_text())


def cached_training_scores(artifact, fitted):
    output = []
    for example in artifact['training_examples']:
        typed = fitted.predict(example['features'], example['canonical_logits'])
        binary = {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}
        prediction = min(binary, key=lambda key: (-binary[key], key))
        gold_binary = 'Yes' if example['original_threeway_label'] == 'Entailment' else 'No'
        output.append({'id': example['id'], 'arm': example['arm'], 'weight': example['weight'],
                       'threeway_probabilities': typed, 'binary_probabilities': binary,
                       'correct': prediction == gold_binary, 'original_threeway_label': example['original_threeway_label']})
    summaries = {arm: {'n': sum(row['arm'] == arm for row in output),
                       'correct': sum(row['arm'] == arm and row['correct'] for row in output),
                       'scope': 'In-sample cached TRAIN replay, not independent performance'} for arm in HEAD.ARMS}
    return output, summaries


class CandidateEngine(FROZEN9.CandidateEngine):
    name = 'ruvector-native-evidence-role-coverage-crossfit-threeway-epoch10'
    attribution = ('Actual native RuVector ranking with exact frozen epoch6 context policy, pinned DeBERTa-base3way '
                   'and one TRAIN-only clause-binding and document-crossfitted annotation-overlap residual head. All3 retrieval arms share one fitted head; '
                   'Yes=Entailment,No=Contradiction+NotMentioned. Legacy top2 names are variable-unit aliases. '
                   'Native104 reads the same primary excerpt, not submitted full-input104.')

    def __init__(self, fitted_head_path=None, training_contract_path=None):
        runtime_started = time.perf_counter()
        runtime_initial_resources = FROZEN4.resource_snapshot()
        config = pinned_json(HERE / 'config.json', CONFIG_SHA256)
        if config['optimizer'] != HEAD.ALGORITHM or config['feature_names'] != list(HEAD.FEATURES.FEATURE_NAMES):
            raise ValueError('Fixed optimizer/feature policy changed')
        old_config = pinned_json(HERE.parent / 'epoch6/config.json', config['frozen_context_config_sha256'])
        for key in ('source_partition', 'query_prefix', 'ranking_depth', 'packing', 'joint_pair_token_cap'):
            if config[key] != old_config[key]:
                raise ValueError('Epoch8 context selection must equal frozen epoch6')
        self.train_allowlist = pinned_json(ROOT / config['training_allowlist_path'], config['training_allowlist_sha256'])
        self.training_contract_path = Path(training_contract_path) if training_contract_path else ROOT / config['training_contract_path']
        self.training_source_path = ROOT / config['training_source_path']
        self.training_annotations_path = ROOT / config['training_annotations_path']
        if HEAD.sha(self.training_contract_path) != config['training_contract_sha256']:
            raise ValueError('Data role contract changed')
        pending = None
        if fitted_head_path is not None:
            pending = json.loads(Path(fitted_head_path).read_text())
            if (pending.get('runtime_source_sha256') != HEAD.sha(__file__)
                    or pending.get('data_contract_sha256') != config['training_contract_sha256']
                    or pending.get('training_source_sha256') != config['training_source_sha256']
                    or pending.get('annotations_sha256') != config['training_annotations_sha256']):
                raise ValueError('Loaded artifact runtime/data provenance differs before model initialization')
            HEAD.FrozenHead(pending, CONFIG_SHA256, config['training_allowlist_sha256'], config['model_identity'])
        # Frozen9 initializes exactly one active broader threeway decoder, BGE and native104; no old base session.
        FROZEN9.CandidateEngine.__init__(self, None)
        self.config = config
        self.counters.update(context_partitions_attempted=0, context_partitions_completed=0,
                             context_packs_attempted=0, context_packs_completed=0)
        self.nli = MODELS.TypedNli(self.nli)
        self.head_state = 'TRAIN_COLLECTION'
        self._fit_attempted = False
        self.fitted_head_path = None
        self.fitted_head_sha256 = None
        self.receipt.update(config=config, config_sha256=CONFIG_SHA256, architecture=self.attribution,
                            nli=self.nli.receipt, typed_head_state=self.head_state,
                            train_allowlist_sha256=config['training_allowlist_sha256'],
                            training_contract_sha256=config['training_contract_sha256'],
                            head_feature_names=list(HEAD.FEATURES.FEATURE_NAMES), fit_algorithm=HEAD.ALGORITHM,
                            execution_counters=copy.deepcopy(self.counters),
                            batch_policy='Phase1 TRAIN72+one fit+DEV24 combined600seconds; phase2 only locked fitted-head CONF48≤600seconds. CPU2,paid0,GPU0; parent controls admission.')
        if pending is not None:
            try:
                if hashlib.sha256(HEAD.canonical(pending) + b'\n').hexdigest() != HEAD.sha(fitted_head_path):
                    raise ValueError('Loaded frozen artifact bytes changed or are not canonical')
                self._load_frozen(pending, Path(fitted_head_path))
                self._fit_attempted = True
            except BaseException:
                self.base.close()
                raise
        self.receipt.update(base_initialization_wall_seconds=self.receipt['initialization_wall_seconds'],
                            initialization_wall_seconds=time.perf_counter() - runtime_started,
                            resources_before_initialization=runtime_initial_resources,
                            resources_after_initialization=FROZEN4.resource_snapshot(self.native_pid),
                            initialization_timing_scope='Whole epoch10 constructor, including source/role checks, wrapper and fitted-artifact validation/loading')

    def _load_frozen(self, artifact, path):
        if (artifact.get('runtime_source_sha256') != HEAD.sha(__file__)
                or artifact.get('data_contract_sha256') != self.config['training_contract_sha256']
                or artifact.get('training_source_sha256') != self.config['training_source_sha256']
                or artifact.get('annotations_sha256') != self.config['training_annotations_sha256']):
            raise ValueError('Fitted readout runtime/data provenance changed')
        fitted = HEAD.FrozenHead(artifact, CONFIG_SHA256, self.config['training_allowlist_sha256'], self.config['model_identity'])
        digest = HEAD.sha(path)
        self.nli.freeze(fitted, digest)
        self.head_state = 'FROZEN'
        self.fitted_head_path = path
        self.fitted_head_sha256 = digest
        self.receipt.update(typed_head_state='FROZEN', fitted_head_sha256=digest,
                            fitted_head_path=str(path), nli=self.nli.receipt)

    def fit_from_records(self, train_records, artifact_path):
        if self._fit_attempted or self.head_state != 'TRAIN_COLLECTION':
            raise ValueError('Exactly one TRAIN-only fit is permitted; frozen/loaded heads cannot refit')
        self._fit_attempted = True
        self.head_state = 'FITTING'; self.nli.head_state = 'FITTING'
        self.receipt['typed_head_state'] = 'FITTING'
        temporary = None
        try:
            if HEAD.sha(self.training_contract_path) != self.config['training_contract_sha256']:
                raise ValueError('Frozen data role contract changed before fit')
            records = list(train_records)
            # Read only the small, frozen TRAIN projection at fit time. Never
            # open the original corpus, DEV or confirmation labels here.
            source_bytes = self.training_source_path.read_bytes()
            if hashlib.sha256(source_bytes).hexdigest() != self.config['training_source_sha256']:
                raise ValueError('Frozen TRAIN72 label projection bytes changed')
            originals = [json.loads(line) for line in source_bytes.splitlines() if line]
            by_id = {row['id']: row for row in originals}
            if len(originals) != 72 or len(by_id) != 72 or set(by_id) != {row['id'] for row in self.train_allowlist['records']}:
                raise ValueError('TRAIN72 source projection identity set differs')
            for row in records:
                original = by_id.get(row['id'])
                if (original is None or original.get('split') != 'train'
                        or row['evaluation']['original_threeway_label'] != original['evaluation']['original_threeway_label']
                        or row['evaluation']['gold'] != original['evaluation']['gold']):
                    raise ValueError('Cached training labels differ from the exact TRAIN-only source projection')
            if HEAD.sha(self.training_annotations_path) != self.config['training_annotations_sha256']:
                raise ValueError('Frozen TRAIN-only annotation projection changed')
            annotations = json.loads(self.training_annotations_path.read_text())
            artifact = HEAD.fit(records, self.train_allowlist, CONFIG_SHA256,
                                self.config['training_allowlist_sha256'], self.config['model_identity'],
                                annotations, self.config['training_annotations_sha256'])
            artifact.update(runtime_source_sha256=HEAD.sha(__file__),
                            data_contract_sha256=self.config['training_contract_sha256'],
                            training_source_sha256=self.config['training_source_sha256'],
                            training_records_canonical_sha256=hashlib.sha256(HEAD.canonical(records)).hexdigest())
            fitted = HEAD.FrozenHead(artifact, CONFIG_SHA256, self.config['training_allowlist_sha256'], self.config['model_identity'])
            replay, summaries = cached_training_scores(artifact, fitted)
            artifact['cached_training_replay'] = replay
            artifact['cached_training_metrics'] = summaries
            encoded = HEAD.canonical(artifact) + b'\n'
            target = Path(artifact_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.fitted-head-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            os.link(temporary, target)  # Exclusive admission; existing artifacts are never overwritten.
            self._load_frozen(artifact, target)
            receipt = {'head_state': 'FROZEN', 'artifact_path': str(target), 'artifact_sha256': self.fitted_head_sha256,
                       'training_questions': 72, 'training_groups': 24, 'training_arm_examples': 216,
                       'training_total_weight': artifact['training_total_weight'],
                       'class_question_counts': artifact['training_class_question_counts'],
                       'fit_diagnostics': artifact['fit_diagnostics'], 'algorithm': HEAD.ALGORITHM,
                       'cached_training_metrics': summaries, 'new_model_forwards_for_fit': 0,
                       'train_allowlist_sha256': self.config['training_allowlist_sha256'],
                       'training_records_canonical_sha256': artifact['training_records_canonical_sha256']}
            self.receipt['fitted_head'] = receipt
            return receipt
        except BaseException as failure:
            self.head_state = 'FIT_FAILED'; self.nli.head_state = 'FIT_FAILED'
            self.receipt['typed_head_state'] = 'FIT_FAILED'
            self.receipt['fit_failure'] = {
                'head_state': 'FIT_FAILED', 'error_type': type(failure).__name__, 'message': str(failure),
                'diagnostics': getattr(failure, 'diagnostics', {'stage': 'boundary_or_artifact_admission', 'reason': str(failure)}),
                'new_model_forwards_for_fit': 0, 'retry_permitted': False, 'DEV_or_confirmation_permitted': False}
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def finalize(self, artifact_path=None):
        if self.head_state != 'FROZEN' or self.fitted_head_path is None:
            raise ValueError('No accepted frozen readout exists')
        path = Path(artifact_path) if artifact_path else self.fitted_head_path
        if HEAD.sha(path) != self.fitted_head_sha256:
            raise ValueError('Frozen artifact bytes changed')
        return {'head_state': 'FROZEN', 'artifact_path': str(path), 'artifact_sha256': self.fitted_head_sha256,
                'fit_repeated': False, 'new_model_forwards': 0}

    def predict(self, state, questions):
        if self.head_state not in ('TRAIN_COLLECTION', 'FROZEN'):
            raise ValueError('Head fit failed/in progress; no fallback inference permitted')
        result = super().predict(state, questions)
        for response in [result] + list(result['ablation_responses'].values()):
            response['usage']['typed_head_state'] = self.head_state
            for answer in response['answers'].values():
                answer.update(model='Xenova/DeBERTa-v3-base-mnli-fever-anli@72a1ce83a0144efaf828b3c3844320a61197a53d',
                              head='TRAIN-only-role-and-document-crossfit-annotation-overlap-threeway' if self.head_state == 'FROZEN' else 'unfitted-threeway-TRAIN-collection')
        self.last_usage['typed_head_state'] = self.head_state
        result['typed_head'] = {'state': self.head_state, 'artifact_sha256': self.fitted_head_sha256,
                                 'mapping': self.config['mapping'], 'class_order': list(HEAD.FEATURES.CLASSES)}
        return result
