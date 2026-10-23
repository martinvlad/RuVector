"""Official RoBERTa semantic-family reader with active BPE budget over unchanged context algorithm."""
from __future__ import annotations
import copy
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = 'cf12fdbc2d3ec3ba0cf013858ed8c79d7494cc05f50834e155348581bb311002'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FROZEN6 = module('epoch13_frozen6', HERE.parent / 'epoch6/runtime.py')
FROZEN4 = FROZEN6.PREVIOUS
HELPERS = FROZEN6.HELPERS
MODELS = module('epoch13_models', HERE / 'models.py')


def pinned_json(path, expected):
    if MODELS.sha(path) != expected:
        raise ValueError('Pinned manifest/config identity changed: ' + str(path))
    return json.loads(Path(path).read_text())


def verify_file(item, materialized=False):
    path = ROOT / item['path']
    if materialized:
        current = path
        while current != ROOT:
            if current.is_symlink():
                raise ValueError('Native runtime closure must be materialized: ' + item['path'])
            current = current.parent
    if (not path.is_file() or path.stat().st_size != item['bytes']
            or MODELS.sha(path) != item['sha256']):
        raise ValueError('Runtime/model file identity changed: ' + item['path'])


class CandidateEngine(FROZEN6.CandidateEngine):
    name = 'ruvector-native-official-roberta-semantic-threeway-epoch13'
    attribution = ('Actual native RuVector ranking with unchanged epoch6 partition/packing algorithm, '
                   'using a frozen active RoBERTa byte-level BPE token-budget adapter and '
                   'the official fixed FP32 12-layer/768 SNLI+MultiNLI threeway reader. '
                   'All3 retrieval arms share that exact tokenizer, algorithm and singleton reader. '
                   'At most40 ranked anchors; immediate same-paragraph neighbors may be inspected identically under512 tokens. '
                   'Legacy top2 names are variable-unit interface aliases. Native104 reads the same primary excerpt. '
                   'Historical SentencePiece context strings are not preserved. No known accuracy superiority is claimed.')

    def __init__(self, artifact_path=None):
        started = time.perf_counter()
        initial = FROZEN4.resource_snapshot()
        self.config = pinned_json(HERE / 'config.json', CONFIG_SHA256)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != self.config:
            raise ValueError('Unfrozen epoch13 configuration')
        old_config = pinned_json(HERE.parent / 'epoch6/config.json', self.config['frozen_context_config_sha256'])
        for field in ('source_partition', 'query_prefix', 'ranking_depth', 'packing', 'joint_pair_token_cap'):
            if self.config[field] != old_config[field]:
                raise ValueError('Epoch13 must preserve exact frozen epoch6 context field: ' + field)
        if MODELS.sha(HERE.parent / 'epoch6/context.py') != self.config['frozen_context_algorithm_sha256']:
            raise ValueError('Reviewed epoch6 partition/packing algorithm changed')
        choice = pinned_json(HERE / 'model-choice.json', self.config['model_choice_sha256'])
        assets = pinned_json(HERE / 'model-assets.lock.json', self.config['new_assets_lock_sha256'])
        if (assets['repo'] != MODELS.REPO or assets['revision'] != MODELS.REVISION
                or choice['repo'] != MODELS.REPO or choice['revision'] != MODELS.REVISION):
            raise ValueError('Selected model revision changed')
        old_lock = pinned_json(HERE.parent / 'epoch4/assets.lock.json',
                               '91f035c3bd5e24d6094a4656b2c2c35257bd0346eb7d278e5a8faf1ce817cfbd')
        for package, version in old_lock['python_versions'].items():
            if importlib.metadata.version(package) != version:
                raise ValueError('Pinned Python dependency mismatch: ' + package)
        for item in old_lock['assets'] + assets['assets']:
            verify_file(item)
        closure_root = ROOT / 'experiments/sota-2026-10-22/epoch5'
        core = pinned_json(ROOT / 'experiments/sota-2026-10-22/epoch4/runtime-repair/official-package-closure.json',
                           '3efc9666b549da8f70a22b0fca285dca68112f6835c767d08fd7f5946fc31726')
        typesafe = pinned_json(closure_root / 'typesafe-runtime-closure.json',
                               '363bb39e63fd6fb212a0aed25974443f5a286ca5eaff867314f3daad5fbe0718')
        for item in [item for package in core['packages'] for item in package['files']] + typesafe['files']:
            verify_file(item, materialized=True)
        selected = ROOT / 'experiments/submission-2026-10-22/jevbench/round2-v2/plan.json'
        native_plan = pinned_json(selected, '782db4034b2eb51ad9520a632ee94f7bdbb5bf0e8826ca44a91a055c15971f17')
        for path, expected in native_plan['source_sha256'].items():
            if MODELS.sha(ROOT / path) != expected:
                raise ValueError('Native104 source changed: ' + path)
        bundle = os.environ.get('RUVECTOR_SOTA_BUNDLE_DIR')
        if not bundle:
            raise ValueError('RUVECTOR_SOTA_BUNDLE_DIR required')
        self.bundle_directory = Path(bundle).resolve()
        self.bundle_directory.mkdir(parents=True, exist_ok=True)
        self.counters = dict.fromkeys(('requests_attempted', 'requests_completed',
                                      'native104_requests_attempted', 'native104_requests_completed',
                                      'native_core_searches_attempted', 'native_core_searches_completed',
                                      'bge_forward_batches_attempted', 'bge_forward_batches_completed',
                                      'bge_texts_attempted', 'bge_texts_completed',
                                      'nli_forward_pairs_attempted', 'nli_forward_pairs_completed',
                                      'nli_input_tokens_attempted', 'nli_input_tokens_completed',
                                      'context_partitions_attempted', 'context_partitions_completed',
                                      'context_packs_attempted', 'context_packs_completed'), 0)
        self.counters.update(bge_forward_wall_seconds=0.0, nli_forward_wall_seconds=0.0)
        self.bge = HELPERS.MODELS.BgeEncoder(ROOT)
        self.bge.session = FROZEN4.MODELS.CountedSession(self.bge.session, self.counters)
        # No old constructor or NLI session is initialized. The one selected
        # active BPE tokenizer governs both packing and actual reader input.
        static = pinned_json(HERE / 'onnx-static.json', self.config['onnx_static_sha256'])
        expected_inputs = [item['name'] for item in static['inputs']]
        self.nli = MODELS.SingletonNli(HERE / 'assets/official-roberta-base', self.counters,
                                      expected_inputs=expected_inputs)
        self.base = HELPERS.BASE.CompositeEngine(ROOT / 'experiments/submission-2026-10-22/jevbench/round2-v2/rules.py')
        self.native_process = self.base.native.process
        self.native_pid = self.native_process.pid
        if self.base.receipt['binary_sha256'] != native_plan['native_candidate']['binary_sha256']:
            self.base.close()
            raise ValueError('Native104 binary changed')
        self.core_binary_sha256 = old_lock['native_core_binary_sha256']
        self.evidence_cache = {}
        self.last_usage = None
        self.receipt = {**self.base.receipt, 'architecture': self.attribution, 'config': self.config,
                        'config_sha256': CONFIG_SHA256, 'nli': self.nli.receipt, 'bge': self.bge.receipt,
                        'assets_lock_sha256': self.config['new_assets_lock_sha256'],
                        'frozen_context_assets_lock_sha256': MODELS.sha(HERE.parent / 'epoch4/assets.lock.json'),
                        'native_core_binary_sha256': self.core_binary_sha256,
                        'native_ranking_depth': 40, 'unchanged_epoch6_context_algorithm': True,
                        'unchanged_epoch6_context_policy': False, 'exact_epoch6_context_strings': False,
                        'active_BPE_token_budget_adapter': True,
                        'epoch6_context_algorithm_sha256': self.config['frozen_context_algorithm_sha256'],
                        'old_base_NLI_session_initialized': False,
                        'model_choice_sha256': self.config['model_choice_sha256'],
                        'license_and_training_provenance': choice['upstream'],
                        'provenance_limits': 'Official source/export repository revision, card, config, tokenizer and FP32 ONNX are pinned together. Training run lineage and record-level pretraining contamination are not independently proven. No declared ContractNLI supervision. No weights are republished.',
                        'confirmation_separation': self.config['confirmation_separation'],
                        'initialization_wall_seconds': time.perf_counter() - started,
                        'resources_before_initialization': initial,
                        'resources_after_initialization': FROZEN4.resource_snapshot(self.native_pid),
                        'execution_counters': copy.deepcopy(self.counters),
                        'batch_policy': 'Parent-controlled DEV24 then statistically and timing-gated confirmation48; at most2 corpus batches, each600seconds,CPU2,paid0,GPU0; no extra forwards.'}

    def predict(self, state, questions):
        result = super().predict(state, questions)
        # Frozen6 emits its historical model label. Correct only that provenance;
        # contexts, decisions, probabilities, logits and counters are untouched.
        responses = [result] + list(result['ablation_responses'].values())
        for response in responses:
            for answer in response['answers'].values():
                answer.update(model=MODELS.REPO + '@' + MODELS.REVISION,
                              head='official-roberta-base-FP32-threeway-over-active-BPE-context')
        result['reader_model'] = {'repo': MODELS.REPO, 'revision': MODELS.REVISION,
                                  'classes': 3, 'mapping': 'Yes=entailment;No=neutral+contradiction',
                                  'precision': 'FP32', 'context_algorithm_unchanged_from_epoch6': True,
                                  'context_policy_unchanged_from_epoch6': False,
                                  'active_BPE_token_budget_adapter': True}
        return result

    def close(self):
        self.base.close()
