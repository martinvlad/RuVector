"""Official DeBERTa-v3-large with shared exact-source whole-unit definition priority."""
from __future__ import annotations
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = 'e465632385bc729d28a557721db0c79f03861366889d6aaedfa3c36a926daff2'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FROZEN6 = module('epoch15_frozen6', HERE.parent / 'epoch6/runtime.py')
FROZEN4 = FROZEN6.PREVIOUS
HELPERS = FROZEN6.HELPERS
MODELS = module('epoch15_models', HERE / 'models.py')
CONTEXT = module('epoch15_definition_priority_context', HERE / 'context.py')


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
    name = 'ruvector-native-official-deberta-definition-priority-threeway-epoch15'
    attribution = ('Actual native RuVector evidence ranking with one official fixed24layer1024 '
                   'SNLI+MultiNLI threeway reader and claim-independent whole-unit definition priority. '
                   'All3 matched retrieval arms share the same actual Unigram tokenizer,160token priority '
                   'IDs,512joint-pair cap and singleton decoder. Final evidence stays in global source '
                   'order; priority definitions are not guaranteed to be literally first. '
                   'Native104 reads exactly the primary packed excerpt. Higher capacity is not proof '
                   'of legal superiority; no learned alias, gold evidence lookup or extra inference arm.')

    def __init__(self, artifact_path=None):
        started = time.perf_counter()
        initial = FROZEN4.resource_snapshot()
        self.config = pinned_json(HERE / 'config.json', CONFIG_SHA256)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != self.config:
            raise ValueError('Unfrozen epoch15 configuration')
        old_config = pinned_json(HERE.parent / 'epoch6/config.json', self.config['frozen_context_config_sha256'])
        for field in ('source_partition', 'query_prefix', 'ranking_depth', 'joint_pair_token_cap'):
            if self.config[field] != old_config[field]:
                raise ValueError('Epoch13 must preserve exact frozen epoch6 context field: ' + field)
        if MODELS.sha(HERE.parent / 'epoch6/context.py') != self.config['frozen_context_algorithm_sha256']:
            raise ValueError('Reviewed epoch6 partition/packing algorithm changed')
        if MODELS.sha(HERE / 'context.py') != self.config['definition_context_sha256']:
            raise ValueError('Frozen definition-priority algorithm changed')
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
        for item in [x for x in old_lock['assets'] if not x['path'].startswith('experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/')] + assets['assets']:
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
        # No old NLI constructor, weights or tokenizer are initialized. The
        # selected Unigram tokenizer governs both packing and reader input.
        static = pinned_json(HERE / 'onnx-static.json', self.config['onnx_static_sha256'])
        expected_inputs = [item['name'] for item in static['inputs']]
        self.nli = MODELS.SingletonNli(HERE / 'assets/official-deberta-v3-large', self.counters,
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
                        'native_ranking_depth': 40, 'unchanged_epoch6_context_algorithm': False,
                        'unchanged_epoch6_context_policy': False, 'exact_epoch6_context_strings': False,
                        'active_Unigram_token_budget_adapter': True,
                        'definition_priority_token_cap': 160,
                        'definition_priority_claim_independent': True,
                        'final_global_source_order': True,
                        'definition_priority_algorithm_sha256': self.config['definition_context_sha256'],
                        'epoch6_context_algorithm_sha256': self.config['frozen_context_algorithm_sha256'],
                        'old_base_NLI_session_initialized': False,
                        'model_choice_sha256': self.config['model_choice_sha256'],
                        'license_and_training_provenance': choice['upstream'],
                        'provenance_limits': 'Official source/export repository revision, card, config, tokenizer and official QUINT8AVX2 ONNX are pinned together. Training run lineage and record-level pretraining contamination are not independently proven. No declared ContractNLI supervision. No weights are republished.',
                        'confirmation_separation': self.config['confirmation_separation'],
                        'initialization_wall_seconds': time.perf_counter() - started,
                        'resources_before_initialization': initial,
                        'resources_after_initialization': FROZEN4.resource_snapshot(self.native_pid),
                        'execution_counters': copy.deepcopy(self.counters),
                        'batch_policy': 'Parent-controlled DEV24 then statistically and timing-gated confirmation48; at most2 corpus batches, each600seconds,CPU2,paid0,GPU0; no extra forwards.'}

    def predict(self, state, questions):
        self.counters['requests_attempted'] += 1
        started = time.perf_counter()
        before = self.execution_snapshot()
        if not isinstance(state, str):
            state = json.dumps(state, ensure_ascii=False, separators=(',', ':'))
        self.last_usage = {'execution_before': before, 'paid_calls': 0}
        try:
            predicates = {key: HELPERS.validate_question(question) for key, question in questions.items()}
            self.counters['context_partitions_attempted'] += 1
            limits = {name: self.config['source_partition'][name]
                      for name in ('target', 'nli_cap', 'bge_cap', 'max_units')}
            units = CONTEXT.partition(state, self.nli.tokenizer, self.bge.raw_tokenizer, **limits)
            self.counters['context_partitions_completed'] += 1
            prelude = CONTEXT.select_prelude(state, units, self.nli.tokenizer)
            priority_text, _ = CONTEXT._premise(state, units, prelude['selected_unit_ids'])
            chunks = [state[unit['start']:unit['end']] for unit in units]
            spans = [(unit['start'], unit['end']) for unit in units]
            depth = min(self.config['ranking_depth'], len(units))
            # Tokenizer-only guards for ALL queries and units precede BGE/native forwards.
            for hypothesis in predicates.values():
                if len(self.nli.tokenizer.encode('', hypothesis).ids) > self.config['joint_pair_token_cap']:
                    raise ValueError('Exact whole hypothesis exceeds512 tokens; no clipping')
                if len(self.nli.tokenizer.encode(priority_text, hypothesis).ids) > self.config['joint_pair_token_cap']:
                    raise ValueError('Exact whole priority and hypothesis exceed512; priority not silently dropped')
                query = self.config['query_prefix'] + hypothesis
                if len(self.bge.raw_tokenizer.encode(query).ids) > 256:
                    raise ValueError('Exact retrieval query exceeds256 BGE tokens; no clipping')
            if any(len(self.bge.raw_tokenizer.encode(chunk).ids) > 256 for chunk in chunks):
                raise ValueError('Complete evidence unit exceeds256 BGE tokens; no clipping')
            answers = {name: {} for name in ('ruvector_top2', 'lexical_top2', 'positional_first2')}
            diagnostics, baseline_answers, native_usages = {}, {}, {}
            for key, hypothesis in predicates.items():
                ranking, retrieval = self.retrieve(chunks, hypothesis)
                rankings = {'ruvector_top2': ranking,
                            'lexical_top2': HELPERS.lexical_ids(chunks, hypothesis, depth),
                            'positional_first2': list(range(depth))}
                contexts = {}
                for name, order in rankings.items():
                    self.counters['context_packs_attempted'] += 1
                    contexts[name] = CONTEXT.pack(state, units, order, hypothesis, self.nli.tokenizer,
                                                  pair_cap=self.config['joint_pair_token_cap'],
                                                  rank_depth=depth, prelude=prelude)
                    self.counters['context_packs_completed'] += 1
                if any(cov['definition_priority'] != prelude for _, cov in contexts.values()):
                    raise ValueError('Matched retrieval arms must share identical definition priority')
                primary_context, primary_coverage = contexts['ruvector_top2']
                control_input = {'state': primary_context, 'questions': {key: questions[key]}}
                if len(primary_context.encode()) > 16 * 1024:
                    raise ValueError('Complete native-selected context exceeds native10416KiB; no clipping')
                encoded_control = json.dumps(control_input, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
                self.counters['native104_requests_attempted'] += 1
                control_started = time.perf_counter()
                control = self.base.predict(control_input['state'], control_input['questions'])
                self.counters['native104_requests_completed'] += 1
                baseline_answers[key] = copy.deepcopy(control['answers'][key])
                native_usages[key] = copy.deepcopy(control.get('usage', {}))
                control_ms = (time.perf_counter() - control_started) * 1000
                arms = {}
                for name, (premise, coverage) in contexts.items():
                    probabilities, decoding = self.nli.decode(premise, hypothesis)
                    answer = HELPERS.answer_for(probabilities)
                    answer.update(model=MODELS.REPO + '@' + MODELS.REVISION,
                                  head='official-DeBERTa-v3-large-QUINT8AVX2-threeway-definition-priority')
                    answers[name][key] = answer
                    selected = coverage['selected_chunk_ids_rank_order']
                    arms[name] = {'chunk_ids': selected, 'chunk_spans': [spans[i] for i in selected],
                                  'ranking_ids': rankings[name], 'premise': premise, 'hypothesis': hypothesis,
                                  'coverage': coverage, 'decoding': decoding}
                diagnostics[key] = {'source_state': state, 'source_state_sha256': hashlib.sha256(state.encode()).hexdigest(),
                                    'state_bytes': len(state.encode()), 'total_chunks': len(units),
                                    'chunk_spans': spans, 'source_units': units,
                                    'full_source_partition': True, 'source_partition_has_overlap': False,
                                    'ranking_candidate_depth': depth, 'retrieval': retrieval, 'arms': arms,
                                    'definition_priority': prelude,
                                    'baseline_control_label': 'native104_on_ruvector_evidence',
                                    'baseline_control_input': control_input,
                                    'baseline_control_input_sha256': hashlib.sha256(encoded_control).hexdigest(),
                                    'baseline_control_input_hash_encoding': "UTF8 JSON ensure_ascii=False separators=(',',':') allow_nan=False",
                                    'baseline_control_source_chunk_ids': primary_coverage['selected_chunk_ids_rank_order'],
                                    'baseline_control_state_bytes': len(primary_context.encode()),
                                    'baseline_control_wall_ms': control_ms,
                                    'legacy_arm_name_scope': self.config['legacy_arm_names']}
            baseline = {'model': 'native104_on_ruvector_evidence', 'answers': baseline_answers,
                        'usage': {'native_requests': len(native_usages), 'per_question_native_usage': native_usages},
                        'attribution': 'Native104 sees exactly the coherent primary selected excerpt and original question; not submitted full-input104.'}
            self.counters['requests_completed'] += 1
            self.last_usage = {'native_requests': len(native_usages), 'native_core_searches': len(questions),
                               'nli_singleton_pairs': 3 * len(questions), 'per_question_native_usage': native_usages,
                               'execution_before': before, 'execution_after': self.execution_snapshot(),
                               'paid_calls': 0, 'latency_scope': 'Whole request includes all3 coherent NLI arms, native104 excerpt reference and native retrieval; not primary-only serving latency.'}

            def response(name):
                return {'model': self.name + '-' + name, 'answers': copy.deepcopy(answers[name]),
                        'usage': copy.deepcopy(self.last_usage), 'attribution': self.attribution}

            result = response('ruvector_top2')
            result.update(baseline104_response=baseline,
                          ablation_responses={'same_nli_lexical_top2': response('lexical_top2'),
                                              'same_nli_positional_first2': response('positional_first2')},
                          diagnostics=diagnostics, whole_request_wall_ms=(time.perf_counter() - started) * 1000,
                          reader_model={'repo': MODELS.REPO, 'revision': MODELS.REVISION,
                                        'classes': 3, 'raw_labels': {'0':'contradiction','1':'entailment','2':'neutral'},
                                        'precision': 'OFFICIAL_QUINT8_AVX2',
                                        'mapping': 'Yes=E;No=C+N;typedE/C/N;T1',
                                        'definition_priority_shared_all_arms': True,
                                        'definition_priority_token_cap': 160,
                                        'final_global_source_order': True})
            return result
        finally:
            self.last_usage.update(execution_terminal=self.execution_snapshot(),
                                   request_wall_seconds=time.perf_counter() - started)

    def close(self):
        self.base.close()
