"""Coherent legal-context policy over actual native RuVector evidence ranking.

Weights, decoder, native104 reader and native search worker remain unchanged.
The only candidate hypothesis is source partition and deterministic packing.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONFIG_SHA256 = '27f1f8064516b73ba32515adec20d4bb53ce355b46944cd33ba8a7191fc412a1'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


CONTEXT = module('epoch6_context', HERE / 'context.py')
PREVIOUS = module('epoch6_frozen4', HERE.parent / 'epoch4/runtime.py')
HELPERS = PREVIOUS.PREVIOUS


class CandidateEngine(PREVIOUS.CandidateEngine):
    name = 'ruvector-native-coherent-evidence-deberta-base-epoch6'
    attribution = ('Actual native RuVector BGE/core ranking of a complete legal-source partition; '
                   'ranked anchors plus immediate same-paragraph context packed under512 tokens; '
                   'unchanged DeBERTa-base singleton NLI. Matched same-policy lexical/positional arms. '
                   'Native104 reads the exact primary excerpt, not original full input. '
                   'Legacy top2 arm names are compatibility aliases; each ranking contains at most40 anchor candidates. '
                   'Same-paragraph neighbor expansion may inspect additional units identically for all3 arms under the same512-token budget.')

    def __init__(self, artifact_path=None):
        raw = (HERE / 'config.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != CONFIG_SHA256:
            raise ValueError('Frozen epoch6 configuration changed')
        config = json.loads(raw)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != config:
            raise ValueError('Unfrozen epoch6 configuration')
        super().__init__(None)
        self.config = config
        self.counters.update(context_partitions_attempted=0, context_partitions_completed=0,
                             context_packs_attempted=0, context_packs_completed=0)
        self.receipt.update(config=self.config, config_sha256=CONFIG_SHA256,
                            architecture=self.attribution,
                            reused_model_and_decoder='Exact frozen epoch4 DeBERTa-base singleton/T1; no new weights, fit or calibration',
                            source_policy='Full nonoverlapping paragraph/sentence partition; explicit oversize token-offset fallback; each arm ranks at most40 anchor candidates and may inspect additional same-paragraph neighbors through identical512-token packing',
                            native_ranking_depth=40,
                            execution_counters=copy.deepcopy(self.counters),
                            adaptive_history='Prior epoch5 used this same model and decoder; epoch6 changes context handling only. No fresh labels were inspected during candidate implementation.')

    def retrieve(self, chunks, hypothesis):
        # Frozen worker requests min40 neighbors and persists exact native bundles.
        unused_top2, diagnostics = super().retrieve(chunks, hypothesis)
        ranking = list(diagnostics['native']['queries'][0]['ids'])
        expected = min(self.config['ranking_depth'], len(chunks))
        if (len(ranking) != expected or len(ranking) != len(set(ranking))
                or any(type(i) is not int or i < 0 or i >= len(chunks) for i in ranking)):
            raise ValueError('Actual native ranking does not match the complete declared40-candidate budget')
        diagnostics['ranking_scope'] = {'requested': expected, 'actual_returned_ids': ranking,
                                        'all_document_units_ranked': len(chunks) <= expected,
                                        'units_outside_candidate_depth': max(0, len(chunks) - expected),
                                        'selection_policy': 'No exact/lexical substitution for observed native ranking'}
        return ranking, diagnostics

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
            chunks = [state[unit['start']:unit['end']] for unit in units]
            spans = [(unit['start'], unit['end']) for unit in units]
            depth = min(self.config['ranking_depth'], len(units))
            # Tokenizer-only guards for ALL queries and units precede BGE/native forwards.
            for hypothesis in predicates.values():
                if len(self.nli.tokenizer.encode('', hypothesis).ids) > self.config['joint_pair_token_cap']:
                    raise ValueError('Exact whole hypothesis exceeds512 tokens; no clipping')
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
                                                  rank_depth=depth)
                    self.counters['context_packs_completed'] += 1
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
                    answer.update(model='Xenova/nli-deberta-v3-base@80a99030ce45a69a39ea2a6f50756d03859ff521',
                                  head='coherent-complete-source-context-singleton-NLI')
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
                          diagnostics=diagnostics, whole_request_wall_ms=(time.perf_counter() - started) * 1000)
            return result
        finally:
            self.last_usage.update(execution_terminal=self.execution_snapshot(),
                                   request_wall_seconds=time.perf_counter() - started)
