"""One materiallyhighercapacity typed threeway reader over the unchanged frozen epoch6 context policy."""
from __future__ import annotations
import copy
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = 'f3dd2ceaa75bf1e250b4e77d5d90bb27075a77c739bd08172ded9be5ad27c5ca'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FROZEN6 = module('epoch12_frozen6', HERE.parent / 'epoch6/runtime.py')
FROZEN4 = FROZEN6.PREVIOUS
HELPERS = FROZEN6.HELPERS
MODELS = module('epoch12_models', HERE / 'models.py')


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
    name = 'ruvector-native-fixed-FP32-threeway-fidelity-epoch12'
    attribution = ('Actual native RuVector ranking and exact frozen epoch6 coherent source/context policy, '
                   'with fixed FP32 pretrained 24-layer/1024 DeBERTa-v3-large threeway NLI reader. '
                   'All3 retrieval arms share the exact old policy tokenizer/packer and new singleton reader. '
                   'At most40 ranked anchors; same-paragraph neighbors may be inspected identically under512 tokens. '
                   'Legacy top2 names are variable-unit compatibility aliases. Native104 reads the same primary excerpt, '
                   'not submitted full-input104. Model performance is unmeasured until the controlled corpus run.')

    def __init__(self, artifact_path=None, enable_training_sanity=False):
        started = time.perf_counter()
        initial = FROZEN4.resource_snapshot()
        self.config = pinned_json(HERE / 'config.json', CONFIG_SHA256)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != self.config:
            raise ValueError('Unfrozen epoch12 configuration')
        old_config = pinned_json(HERE.parent / 'epoch6/config.json', self.config['frozen_context_config_sha256'])
        for field in ('source_partition', 'query_prefix', 'ranking_depth', 'packing', 'joint_pair_token_cap'):
            if self.config[field] != old_config[field]:
                raise ValueError('Epoch12 must preserve exact frozen epoch6 context field: ' + field)
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
        old_model_lock = pinned_json(HERE.parent / 'epoch11/model-assets.lock.json',
                                     '26fa1cb66b5fda7034328172940095a17ac3506b057a09656ca0101da4512e45')
        for item in old_lock['assets'] + old_model_lock['assets'] + assets['assets']:
            verify_file(item)
        if type(enable_training_sanity) is not bool:
            raise ValueError('Training diagnostic mode must be an explicit boolean')
        self.training_enabled = enable_training_sanity
        self.training_phase = 'TRAIN_SANITY' if enable_training_sanity else 'EVAL_READY'
        self.training_attempted_ids = set()
        self.training_completed_ids = set()
        self.training_allowlist = pinned_json(ROOT / self.config['training_allowlist_path'],
                                             self.config['training_allowlist_sha256'])
        entries = self.training_allowlist['records']
        self.training_by_id = {item['id']: item for item in entries}
        if len(entries) != 6 or len(self.training_by_id) != 6:
            raise ValueError('Exactly six frozen TRAIN-only diagnostic identities are required')
        if any(not isinstance(v.get('input_sha256'), str) or len(v['input_sha256']) != 64 for v in entries):
            raise ValueError('TRAIN diagnostic canonical input identities are required')
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
        # No frozen4/frozen6 constructor is called: the old NLI session is unused
        # and never initialized. Its exact tokenizer alone fixes source contexts.
        policy_tokenizer = HERE.parent / 'epoch4/assets/nli-base/tokenizer.json'
        if MODELS.sha(policy_tokenizer) != self.config['frozen_context_tokenizer_sha256']:
            raise ValueError('Frozen epoch6 policy tokenizer changed')
        model_folder = HERE.parent / 'epoch11/assets/nli-large-threeway'
        self.nli = MODELS.SingletonNli(model_folder, policy_tokenizer, self.counters,
                                      model_path=HERE / 'assets/fp32/onnx/model.onnx', precision='FP32')
        self.base = HELPERS.BASE.CompositeEngine(ROOT / 'experiments/submission-2026-10-22/jevbench/round2-v2/rules.py')
        self.native_process = self.base.native.process
        self.native_pid = self.native_process.pid
        if self.base.receipt['binary_sha256'] != native_plan['native_candidate']['binary_sha256']:
            self.base.close()
            raise ValueError('Native104 binary changed')
        self.core_binary_sha256 = old_lock['native_core_binary_sha256']
        self.quantized_nli = None
        try:
            if enable_training_sanity:
                self.quantized_nli = MODELS.SingletonNli(model_folder, policy_tokenizer, self.counters,
                                                        model_path=model_folder / 'onnx/model_quantized.onnx',
                                                        precision='INT8_TRAIN_DIAGNOSTIC')
        except BaseException:
            self.base.close()
            raise
        self.evidence_cache = {}
        self.last_usage = None
        self.receipt = {**self.base.receipt, 'architecture': self.attribution, 'config': self.config,
                        'config_sha256': CONFIG_SHA256, 'nli': self.nli.receipt, 'bge': self.bge.receipt,
                        'quantized_nli': copy.deepcopy(self.quantized_nli.receipt) if self.quantized_nli is not None else None,
                        'quantized_session_initialized_in_batch': enable_training_sanity,
                        'training_sanity_phase': self.training_phase,
                        'training_allowlist_sha256': self.config['training_allowlist_sha256'],
                        'candidate_primary_precision': 'FP32', 'precision_selected_from_sanity': False,
                        'assets_lock_sha256': self.config['new_assets_lock_sha256'],
                        'frozen_context_assets_lock_sha256': MODELS.sha(HERE.parent / 'epoch4/assets.lock.json'),
                        'native_core_binary_sha256': self.core_binary_sha256,
                        'native_ranking_depth': 40, 'unchanged_epoch6_context_policy': True,
                        'old_base_NLI_session_initialized': False,
                        'model_choice_sha256': self.config['model_choice_sha256'],
                        'license_and_training_provenance': choice['upstream'],
                        'provenance_limits': 'Pinned upstream revision is the reviewed source card/config revision; converter does not identify its exact upstream weight commit. No separate conversion license or record-level contamination guarantee is published.',
                        'confirmation_separation': self.config['confirmation_separation'],
                        'initialization_wall_seconds': time.perf_counter() - started,
                        'resources_before_initialization': initial,
                        'resources_after_initialization': FROZEN4.resource_snapshot(self.native_pid),
                        'execution_counters': copy.deepcopy(self.counters),
                        'batch_policy': 'Phase1 TRAIN diagnostic6 then release INT8 and DEV24 in one600second process; phase2 only frozen FP32 CONF48 if accepted and timing-admitted. At most2 nonretryable CPU2 processes, paid0/GPU0. No fit, calibration or precision selection.'}

    def predict(self, state, questions):
        if self.training_phase != 'EVAL_READY':
            raise ValueError('DEV is blocked until all six frozen TRAIN diagnostics finish and INT8 is released')
        if isinstance(state, str) and isinstance(questions, dict):
            raw = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False,
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            digest = hashlib.sha256(raw).hexdigest()
            if digest in {entry['input_sha256'] for entry in self.training_by_id.values()}:
                raise ValueError('TRAIN diagnostic inputs cannot be replayed through DEV/CONF prediction')
        return self._predict_fp32(state, questions)

    def _predict_fp32(self, state, questions):
        result = super().predict(state, questions)
        # Frozen6 emits its historical model label. Correct only that provenance;
        # contexts, decisions, probabilities, logits and counters are untouched.
        responses = [result] + list(result['ablation_responses'].values())
        for response in responses:
            for answer in response['answers'].values():
                answer.update(model=MODELS.REPO + '@' + MODELS.REVISION,
                              head='fixed-FP32-large-threeway-NLI-over-frozen-epoch6-context')
        result['reader_model'] = {'repo': MODELS.REPO, 'revision': MODELS.REVISION,
                                  'classes': 3, 'precision': 'FP32', 'mapping': 'Yes=entailment;No=neutral+contradiction',
                                  'context_policy_unchanged_from_epoch6': True}
        return result


    def predict_train_sanity(self, state, questions, example_id):
        """Run exactly one immutable TRAIN diagnostic; never read its gold label."""
        if self.training_phase != 'TRAIN_SANITY' or self.quantized_nli is None:
            raise ValueError('TRAIN-only INT8 diagnostics are unavailable outside the one diagnostic phase')
        if not isinstance(state, str) or not isinstance(questions, dict) or len(questions) != 1:
            raise ValueError('One exact source string and one question are required per TRAIN diagnostic')
        entry = self.training_by_id.get(example_id)
        if entry is None or example_id in self.training_attempted_ids:
            raise ValueError('Unknown or already attempted TRAIN-only identity; no retries')
        input_raw = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False,
                               sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if hashlib.sha256(input_raw).hexdigest() != entry['input_sha256']:
            raise ValueError('TRAIN-only state/question identity differs from frozen metadata allowlist')
        self.training_attempted_ids.add(example_id)
        started = time.perf_counter()
        self.counters.setdefault('training_sanity_requests_attempted', 0)
        self.counters.setdefault('training_sanity_requests_completed', 0)
        self.counters['training_sanity_requests_attempted'] += 1
        result = self._predict_fp32(state, questions)
        quantized_answers = {}
        comparisons = {}
        for key, diagnostic in result['diagnostics'].items():
            primary = diagnostic['arms']['ruvector_top2']
            probabilities, trace = self.quantized_nli.decode(primary['premise'], primary['hypothesis'])
            quantized_answers[key] = HELPERS.answer_for(probabilities)
            quantized_answers[key].update(model=MODELS.REPO + '@' + MODELS.REVISION,
                                          head='INT8-TRAIN-only-precision-diagnostic')
            comparisons[key] = MODELS.paired_fidelity(primary['decoding'], trace)
            diagnostic['TRAIN_only_precision_pair'] = {'example_id': example_id,
                                                       'quantized_decoding': trace,
                                                       'fidelity': comparisons[key],
                                                       'same_primary_packed_context': True,
                                                       'primary_precision_always_FP32': True}
        self.counters['training_sanity_requests_completed'] += 1
        self.training_completed_ids.add(example_id)
        after = self.execution_snapshot()
        self.last_usage.update(nli_singleton_pairs=4, execution_after=after,
                               execution_terminal=after, request_wall_seconds=time.perf_counter()-started,
                               training_sanity_example_id=example_id,
                               latency_scope='Whole TRAIN HTTP includes three FP32 retrieval arms, one same-primary-context INT8 diagnostic, native104 and evidence retrieval; not deployment latency.')
        result['usage'] = copy.deepcopy(self.last_usage)
        for response in result['ablation_responses'].values():
            response['usage'] = copy.deepcopy(self.last_usage)
        result['quantized_primary_response'] = {'model': 'INT8-TRAIN-only-primary-context-diagnostic',
                                               'answers': quantized_answers,
                                               'usage': copy.deepcopy(self.last_usage),
                                               'scope': 'TRAIN-only diagnostic, no DEV/CONF evaluation, fit or model/precision selection'}
        result['precision_fidelity'] = comparisons
        result['training_sanity_example_id'] = example_id
        result['whole_request_wall_ms'] = (time.perf_counter()-started)*1000
        return result

    def finish_training_sanity(self):
        if (self.training_phase != 'TRAIN_SANITY' or self.training_attempted_ids != set(self.training_by_id)
                or self.training_completed_ids != set(self.training_by_id)):
            raise ValueError('All six immutable TRAIN diagnostics must complete exactly once before DEV')
        self._release_quantized()
        self.training_phase = 'EVAL_READY'
        self.receipt.update(training_sanity_phase=self.training_phase,
                            training_sanity_completed_ids=sorted(self.training_completed_ids),
                            quantized_session_released=True, precision_selected_from_sanity=False)
        return {'completed': 6, 'completed_ids': sorted(self.training_completed_ids),
                'quantized_session_released': True, 'fit': False, 'optimizer_fits': 0,
                'precision_selection': False, 'candidate_primary_precision': 'FP32',
                'scope': 'Completeness gate only; fixed FP32 candidate cannot be changed from these outputs'}

    def _release_quantized(self):
        if self.quantized_nli is not None:
            del self.quantized_nli.session
            self.quantized_nli = None
            gc.collect()

    def close(self):
        try:
            self._release_quantized()
        finally:
            self.base.close()
