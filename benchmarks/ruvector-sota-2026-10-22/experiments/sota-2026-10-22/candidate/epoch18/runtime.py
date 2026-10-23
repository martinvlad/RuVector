"""Actual native evidence plus stronger official typed reader and causal control."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = '1c6c09ebb831e9d8d58fd2de3f3ced98005841db1eac477e6e29df734ead5382'
BASE_RUNTIME_SHA256 = '64e65a6c5e36989f9e0dcd9cbe730838b13af97eb43d5a3b9a84ad35a173a52b'


def module(name, path, expected=None):
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Frozen source dependency changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


OLD = module('epoch18_frozen_runtime15', HERE.parent/'epoch15/runtime.py', BASE_RUNTIME_SHA256)
READER = module('epoch18_official_torch_reader', HERE/'torch_reader.py')
CONTEXT = module('epoch18_joint_reader_context', HERE/'context.py')
HELPERS = OLD.HELPERS
MODELS = READER
ARM_KEYS = ('ruvector_top2', 'lexical_top2', 'positional_first2')


def answer_with_typed(probabilities, decoding, repo, revision, head):
    answer = HELPERS.answer_for(probabilities)
    typed = decoding['raw_threeway_probabilities']
    answer.update(model=repo+'@'+revision, head=head,
                  typed_probabilities=copy.deepcopy(typed), typed_prediction=READER.typed_prediction(typed))
    return answer


class CandidateEngine(OLD.CandidateEngine):
    name = 'ruvector-native-official-deberta-v2-xlarge-typed-epoch18'
    attribution = ('Actual native RuVector evidence ranking plus one official pretrained24-layer1536 '
        'MNLI typed reader, original checkpoint explicitly loaded FP32 and dynamically quantized '
        'qint8 nn.Linear on CPU. Three same-model retrieval arms and one actual unchanged15 reader '
        'on the exact same primary premise/H. Both actual tokenizers admit all complete source '
        'units/priority160/pairs512; no training, calibration, NOT pooling or source rewriting. '
        'Greater pretrained capacity is a hypothesis; legal competence and generalization remain unproven.')

    def __init__(self, artifact_path=None):
        started = time.perf_counter()
        config = OLD.pinned_json(HERE/'config.json', CONFIG_SHA256)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != config:
            raise ValueError('Unfrozen epoch18 configuration')
        for name, field in [('context.py', 'definition_context_sha256'),
                            ('torch_reader.py', 'reader_source_sha256'),
                            ('model-assets.lock.json', 'new_assets_lock_sha256')]:
            if READER.sha(HERE/name) != config[field]:
                raise ValueError('Frozen epoch18 source/asset specification changed: '+name)
        old_config = OLD.pinned_json(HERE.parent/'epoch15/config.json', OLD.CONFIG_SHA256)
        for field in ('source_partition','query_prefix','ranking_depth','joint_pair_token_cap'):
            if config[field] != old_config[field]:
                raise ValueError('Frozen source/ranking field changed: '+field)
        if config['training'] or config['calibration'] or config['temperature'] != 1:
            raise ValueError('No training, calibration or temperature selection permitted')
        lock = json.loads((HERE/'model-assets.lock.json').read_text())
        for item in lock['assets']:
            OLD.verify_file(item)
        # Actual unchanged15 constructor verifies native/BGE/old reader closure
        # and initializes each exactly once; every operation stays in worker budget.
        super().__init__()
        self.config = config
        self.previous_nli = self.nli
        for key in ('new_reader_forward_pairs_attempted','new_reader_forward_pairs_completed',
                    'previous_reader_forward_pairs_attempted','previous_reader_forward_pairs_completed'):
            self.counters[key] = 0
        try:
            self.nli = READER.SingletonNli(HERE.parent/'epoch17/assets/official-deberta-v2-xlarge-mnli', self.counters)
        except BaseException:
            self.base.close()
            raise
        self.receipt.update(config=copy.deepcopy(config), config_sha256=CONFIG_SHA256,
            architecture=self.attribution, selected_model_changed=True,
            nli=copy.deepcopy(self.previous_nli.receipt),
            previous_reader=copy.deepcopy(self.previous_nli.receipt),
            new_reader=copy.deepcopy(self.nli.receipt),
            nli_receipt_scope='Legacy nli key is unchanged15 actual control; new_reader is epoch18 primary',
            assets_lock_sha256=config['new_assets_lock_sha256'],
            previous_reader_assets_lock_sha256=OLD.MODELS.sha(HERE.parent/'epoch15/model-assets.lock.json'),
            new_assets_lock_sha256=config['new_assets_lock_sha256'],
            model_choice_sha256=READER.sha(HERE.parent/'epoch17/research/MODEL_QUALIFICATION.epoch17.json'),
            license_and_training_provenance={'model_card_license': 'MIT', 'declared_supervision': 'MNLI',
                'known_ContractNLI_supervision': False, 'full_training_lineage_verified': False,
                'record_level_pretraining_overlap_verified': False, 'legal_competence_established': False},
            definition_priority_algorithm_sha256=config['definition_context_sha256'],
            base_constructor_source_sha256=BASE_RUNTIME_SHA256,
            previous_reader_actual_same_premise=True, nli_forwards_per_question=4,
            new_reader_forwards_per_question=3, previous_reader_forwards_per_question=1,
            old_base_NLI_session_initialized=True,
            no_initialization_model_forwards=True, no_not_pairing=True,
            confirmation_separation=config['confirmation_separation'],
            provenance_limits='Official source/card/config/MNLI aggregate claims pinned; no declared ContractNLI supervision, but training run lineage, record-level pretraining overlap and legal competence unproven. No weights republished.',
            initialization_wall_seconds=time.perf_counter()-started,
            resources_after_initialization=OLD.FROZEN4.resource_snapshot(self.native_pid),
            execution_counters=copy.deepcopy(self.counters),
            batch_policy='At most2 nonretryable CPU2/600s corpus processes including imports/load/quantization/inference/cleanup; zero paid/GPU; exactly4NLI forwards/question.')

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
            units = CONTEXT.partition(state, self.nli.tokenizer, self.previous_nli.tokenizer, self.bge.raw_tokenizer, **limits)
            self.counters['context_partitions_completed'] += 1
            prelude = CONTEXT.select_prelude(state, units, self.nli.tokenizer, self.previous_nli.tokenizer)
            priority_text, _ = CONTEXT._premise(state, units, prelude['selected_unit_ids'])
            chunks = [state[unit['start']:unit['end']] for unit in units]
            spans = [(unit['start'], unit['end']) for unit in units]
            depth = min(self.config['ranking_depth'], len(units))
            # Tokenizer-only guards for ALL queries and units precede BGE/native forwards.
            for hypothesis in predicates.values():
                if max(CONTEXT.pair_counts(self.nli.tokenizer, self.previous_nli.tokenizer, '', hypothesis).values()) > self.config['joint_pair_token_cap']:
                    raise ValueError('Exact whole hypothesis exceeds512 tokens; no clipping')
                if max(CONTEXT.pair_counts(self.nli.tokenizer, self.previous_nli.tokenizer, priority_text, hypothesis).values()) > self.config['joint_pair_token_cap']:
                    raise ValueError('Exact whole priority and hypothesis exceed512; priority not silently dropped')
                query = self.config['query_prefix'] + hypothesis
                if len(self.bge.raw_tokenizer.encode(query).ids) > 256:
                    raise ValueError('Exact retrieval query exceeds256 BGE tokens; no clipping')
            if any(len(self.bge.raw_tokenizer.encode(chunk).ids) > 256 for chunk in chunks):
                raise ValueError('Complete evidence unit exceeds256 BGE tokens; no clipping')
            answers = {name: {} for name in ARM_KEYS}
            previous_answers = {}
            diagnostics, baseline_answers, native_usages = {}, {}, {}
            for key, hypothesis in predicates.items():
                ranking, retrieval = self.retrieve(chunks, hypothesis)
                rankings = {'ruvector_top2': ranking,
                            'lexical_top2': HELPERS.lexical_ids(chunks, hypothesis, depth),
                            'positional_first2': list(range(depth))}
                contexts = {}
                for name, order in rankings.items():
                    self.counters['context_packs_attempted'] += 1
                    contexts[name] = CONTEXT.pack(state, units, order, hypothesis, self.nli.tokenizer, self.previous_nli.tokenizer,
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
                    answer = answer_with_typed(probabilities, decoding, READER.REPO, READER.REVISION, 'official-xlarge-fixed-dynamic-qint8-threeway')
                    answers[name][key] = answer
                    selected = coverage['selected_chunk_ids_rank_order']
                    arms[name] = {'chunk_ids': selected, 'chunk_spans': [spans[i] for i in selected],
                                  'ranking_ids': rankings[name], 'premise': premise, 'hypothesis': hypothesis,
                                  'coverage': coverage, 'new_decoding': decoding}
                self.counters['previous_reader_forward_pairs_attempted'] += 1
                previous_binary, previous_decoding = self.previous_nli.decode(primary_context, hypothesis)
                self.counters['previous_reader_forward_pairs_completed'] += 1
                previous_answers[key] = answer_with_typed(previous_binary, previous_decoding,
                    OLD.MODELS.REPO, OLD.MODELS.REVISION, 'actual-unchanged15-reader-on-exact-primary-native-premise')
                arms['ruvector_top2']['previous_decoding'] = previous_decoding
                if previous_decoding['input_text_sha256'] != arms['ruvector_top2']['new_decoding']['input_text_sha256']:
                    raise ValueError('Previous-reader control must use exact same whole premise and hypothesis')
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
                               'nli_singleton_pairs': 4 * len(questions), 'new_reader_pairs': 3 * len(questions), 'previous_reader_pairs': len(questions), 'per_question_native_usage': native_usages,
                               'execution_before': before, 'execution_after': self.execution_snapshot(),
                               'paid_calls': 0, 'latency_scope': 'Whole request includes three new-reader retrieval arms, one actual old-reader same-premise control, native104 excerpt and native retrieval; not primary-only serving latency.'}

            def response(name):
                return {'model': self.name + '-' + name, 'answers': copy.deepcopy(answers[name]),
                        'usage': copy.deepcopy(self.last_usage), 'attribution': self.attribution}

            result = response('ruvector_top2')
            result.update(baseline104_response=baseline,
                          ablation_responses={'same_nli_lexical_top2': response('lexical_top2'),
                                              'same_nli_positional_first2': response('positional_first2'),
                                              'previous_reader_native_same_premise': {'model': 'previous_reader_native_same_premise',
                                                  'answers': previous_answers, 'usage': copy.deepcopy(self.last_usage),
                                                  'attribution': 'Actual unchanged15 reader; exact same primary native premise/H; one real extra control forward'}},
                          diagnostics=diagnostics, whole_request_wall_ms=(time.perf_counter() - started) * 1000,
                          reader_model={'repo': MODELS.REPO, 'revision': MODELS.REVISION,
                                        'classes': 3, 'raw_labels': {'0':'contradiction','1':'neutral','2':'entailment'},
                                        'precision': READER.PRECISION,
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
        # Release references without any extra forward or model/session creation.
        self.nli = None
        self.previous_nli = None


Engine = CandidateEngine
