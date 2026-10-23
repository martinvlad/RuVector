"""One native evidence selection and six same-model H/full-NOT-H forwards.

The unchanged official epoch15 constructor verifies and initializes the selected
reader/native closure once. Its source and assets remain immutable dependencies.
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
CONFIG_SHA256 = '9219a0c8b1af2b30847bc9ede7b08df39c1326b82e751709479cfe666a49d0ae'
BASE_RUNTIME_SHA256 = '64e65a6c5e36989f9e0dcd9cbe730838b13af97eb43d5a3b9a84ad35a173a52b'


def module(name, path, expected=None):
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Frozen source dependency changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


OLD = module('epoch16_frozen_runtime15', HERE.parent/'epoch15/runtime.py', BASE_RUNTIME_SHA256)
PAIRING = module('epoch16_polarity_pairing', HERE/'pairing.py')
CONTEXT = module('epoch16_paired_budget_context', HERE/'context.py')
HELPERS = OLD.HELPERS
MODELS = OLD.MODELS
ARM_KEYS = ('ruvector_top2', 'lexical_top2', 'positional_first2')


def answer_with_typed(probabilities, typed, head):
    answer = HELPERS.answer_for(probabilities)
    answer.update(model=MODELS.REPO+'@'+MODELS.REVISION, head=head,
                  typed_probabilities=copy.deepcopy(typed),
                  typed_prediction=PAIRING.prediction(typed))
    return answer


class CandidateEngine(OLD.CandidateEngine):
    name = 'ruvector-native-full-proposition-polarity-pair-epoch16'
    attribution = ('Actual native RuVector evidence ranking with the unchanged official '
        'DeBERTa-v3-large reader. Each selector uses one exact source premise for original H '
        'and full-proposition NOT H. Raw threeway outputs are mirrored and averaged. '
        'The actual rawH native pass is retained as a same-premise causal control at no extra '
        'forward. Neutral and conflict uncertainty are retained; missing retrieval or missing '
        'entailment does not establish contradiction or insufficient evidence. No fitting, '
        'temperature selection, source rewriting, new model or official benchmark claim.')

    def __init__(self, artifact_path=None):
        started = time.perf_counter()
        if CONFIG_SHA256 is None:
            raise ValueError('Epoch16 configuration/source handoff is not frozen')
        config = OLD.pinned_json(HERE/'config.json', CONFIG_SHA256)
        if artifact_path and json.loads(Path(artifact_path).read_text()) != config:
            raise ValueError('Unfrozen epoch16 configuration')
        if (config['counterclaim_prefix'] != PAIRING.PREFIX or
                config['supported_hypotheses'] != PAIRING.HYPOTHESES or
                config['temperature'] != 1 or config['training'] or config['calibration']):
            raise ValueError('Frozen exact-proposition pairing contract changed')
        for name, field in [('pairing.py','pairing_source_sha256'),
                            ('context.py','paired_context_source_sha256')]:
            if MODELS.sha(HERE/name) != config[field]:
                raise ValueError('Frozen paired semantic/context source changed')
        old_config = OLD.pinned_json(HERE.parent/'epoch15/config.json', OLD.CONFIG_SHA256)
        for field in ('source_partition','query_prefix','ranking_depth','joint_pair_token_cap'):
            if config[field] != old_config[field]:
                raise ValueError('Unchanged source/ranking field changed: '+field)
        # This verifies all old config, source, official asset hashes, exact
        # native22 closure and dependency versions before its sole initialization.
        super().__init__()
        self.config = config
        for key in ('nli_positive_pairs_attempted','nli_positive_pairs_completed',
                    'nli_counterclaim_pairs_attempted','nli_counterclaim_pairs_completed'):
            self.counters[key] = 0
        self.receipt.update(config=copy.deepcopy(config), config_sha256=CONFIG_SHA256,
            architecture=self.attribution, selected_model_changed=False,
            base_constructor_source_sha256=BASE_RUNTIME_SHA256,
            decision_pool='E=(E_H+C_Q)/2;C=(C_H+E_Q)/2;N=(N_H+N_Q)/2;T1',
            counterclaim_prefix=PAIRING.PREFIX,
            both_whole_propositions_must_fit_same_premise=True,
            rawH_same_native_premise_control='same_nli_native_raw_h',
            paired_context_source_sha256=config['paired_context_source_sha256'],
            pairing_source_sha256=config['pairing_source_sha256'],
            confirmation_separation=config['confirmation_separation'],
            initialization_wall_seconds=time.perf_counter()-started,
            batch_policy='One DEV24 then conditional newly frozenCONF24; at most2 nonretryable CPU2/600s processes including initialization/cleanup; sixNLIforwards per request; no extra probes.')

    def predict(self, state, questions):
        self.counters['requests_attempted'] += 1
        started = time.perf_counter()
        before = self.execution_snapshot()
        if not isinstance(state, str):
            state = json.dumps(state, ensure_ascii=False, separators=(',', ':'))
        self.last_usage = {'execution_before': before, 'paid_calls': 0}
        try:
            predicates = {key: HELPERS.validate_question(question) for key, question in questions.items()}
            # Total exact table guard for ALL questions BEFORE partition/BGE/core/NLI forwards.
            counterclaims = {key: PAIRING.counterclaim(h) for key, h in predicates.items()}
            self.counters['context_partitions_attempted'] += 1
            limits = {name:self.config['source_partition'][name]
                      for name in ('target','nli_cap','bge_cap','max_units')}
            units = CONTEXT.partition(state,self.nli.tokenizer,self.bge.raw_tokenizer,**limits)
            self.counters['context_partitions_completed'] += 1
            prelude = CONTEXT.select_prelude(state,units,self.nli.tokenizer)
            priority_text,_ = CONTEXT._premise(state,units,prelude['selected_unit_ids'])
            chunks = [state[unit['start']:unit['end']] for unit in units]
            spans = [(unit['start'],unit['end']) for unit in units]
            depth = min(self.config['ranking_depth'],len(units))
            for key,h in predicates.items():
                q = counterclaims[key]
                for premise in ('',priority_text):
                    if max(CONTEXT.pair_counts(self.nli.tokenizer,premise,h,q).values())>self.config['joint_pair_token_cap']:
                        raise ValueError('Exact priority and whole H/Q exceed512; no clipping/drop')
                if len(self.bge.raw_tokenizer.encode(self.config['query_prefix']+h).ids)>256:
                    raise ValueError('Whole originalH retrieval query exceeds256; no clipping')
            if any(len(self.bge.raw_tokenizer.encode(chunk).ids)>256 for chunk in chunks):
                raise ValueError('Complete source unit exceeds256 BGE tokens; no clipping')
            answers = {name:{} for name in ARM_KEYS}
            raw_answers = {name:{} for name in ARM_KEYS}
            diagnostics,baseline_answers,native_usages = {},{},{}
            for key,h in predicates.items():
                q = counterclaims[key]
                ranking,retrieval = self.retrieve(chunks,h)
                rankings = {'ruvector_top2':ranking,
                    'lexical_top2':HELPERS.lexical_ids(chunks,h,depth),
                    'positional_first2':list(range(depth))}
                contexts = {}
                for name,order in rankings.items():
                    self.counters['context_packs_attempted'] += 1
                    contexts[name] = CONTEXT.pack(state,units,order,h,q,self.nli.tokenizer,
                        pair_cap=self.config['joint_pair_token_cap'],rank_depth=depth,prelude=prelude)
                    self.counters['context_packs_completed'] += 1
                if any(cov['definition_priority']!=prelude for _,cov in contexts.values()):
                    raise ValueError('Matched selector priority IDs differ')
                primary_context,primary_coverage = contexts['ruvector_top2']
                control_input = {'state':primary_context,'questions':{key:questions[key]}}
                if len(primary_context.encode())>16*1024:
                    raise ValueError('Complete selected source exceeds native10416KiB; no clipping')
                encoded_control = json.dumps(control_input,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
                self.counters['native104_requests_attempted'] += 1
                control_started = time.perf_counter()
                control = self.base.predict(control_input['state'],control_input['questions'])
                self.counters['native104_requests_completed'] += 1
                baseline_answers[key] = copy.deepcopy(control['answers'][key])
                native_usages[key] = copy.deepcopy(control.get('usage',{}))
                control_ms = (time.perf_counter()-control_started)*1000
                arms = {}
                for name,(premise,coverage) in contexts.items():
                    self.counters['nli_positive_pairs_attempted'] += 1
                    positive_binary,positive_decoding = self.nli.decode(premise,h)
                    self.counters['nli_positive_pairs_completed'] += 1
                    self.counters['nli_counterclaim_pairs_attempted'] += 1
                    _,counterclaim_decoding = self.nli.decode(premise,q)
                    self.counters['nli_counterclaim_pairs_completed'] += 1
                    positive = positive_decoding['raw_threeway_probabilities']
                    negative = counterclaim_decoding['raw_threeway_probabilities']
                    typed = PAIRING.pool(positive,negative)
                    binary = PAIRING.binary(typed)
                    answers[name][key] = answer_with_typed(binary,typed,'full-proposition-NOT mirrored arithmetic mean')
                    raw_answers[name][key] = answer_with_typed(positive_binary,positive,'actual rawH pass on SAME paired-budget premise; no extra inference')
                    selected = coverage['selected_chunk_ids_rank_order']
                    arms[name] = {'chunk_ids':selected,'chunk_spans':[spans[i] for i in selected],
                        'ranking_ids':rankings[name],'premise':premise,'hypothesis':h,'counterclaim':q,
                        'coverage':coverage,'positive_decoding':positive_decoding,
                        'counterclaim_decoding':counterclaim_decoding,
                        'pooled_threeway_probabilities':typed,'pooled_binary_probabilities':binary,
                        'pooling':PAIRING.receipt(positive,negative)}
                diagnostics[key] = {'source_state':state,
                    'source_state_sha256':hashlib.sha256(state.encode()).hexdigest(),
                    'state_bytes':len(state.encode()),'total_chunks':len(units),
                    'chunk_spans':spans,'source_units':units,'full_source_partition':True,
                    'source_partition_has_overlap':False,'ranking_candidate_depth':depth,
                    'retrieval':retrieval,'arms':arms,'definition_priority':prelude,
                    'baseline_control_label':'native104_on_ruvector_evidence',
                    'baseline_control_input':control_input,
                    'baseline_control_input_sha256':hashlib.sha256(encoded_control).hexdigest(),
                    'baseline_control_input_hash_encoding':"UTF8 JSON ensure_ascii=False separators=(',',':') allow_nan=False",
                    'baseline_control_source_chunk_ids':primary_coverage['selected_chunk_ids_rank_order'],
                    'baseline_control_state_bytes':len(primary_context.encode()),
                    'baseline_control_wall_ms':control_ms,
                    'semantic_control_label':'same_nli_native_raw_h',
                    'semantic_control_source':'Actual positive_decoding of ruvector_top2; exact same premise/claim/probabilities; zero extra forwards',
                    'legacy_arm_name_scope':self.config['legacy_arm_names']}
            baseline = {'model':'native104_on_ruvector_evidence','answers':baseline_answers,
                'usage':{'native_requests':len(native_usages),'per_question_native_usage':native_usages},
                'attribution':'Native104 sees exact primary paired-budget source excerpt and original question; not submitted full-input104.'}
            self.counters['requests_completed'] += 1
            self.last_usage = {'native_requests':len(native_usages),'native_core_searches':len(questions),
                'nli_singleton_pairs':6*len(questions),'nli_positive_pairs':3*len(questions),
                'nli_counterclaim_pairs':3*len(questions),'semantic_control_extra_forwards':0,
                'per_question_native_usage':native_usages,'execution_before':before,
                'execution_after':self.execution_snapshot(),'paid_calls':0,
                'latency_scope':'Whole all-arm request: three paired readers, native104 excerpt and native evidence; not primary-only serving latency.'}

            def response(name,raw=False):
                chosen = raw_answers if raw else answers
                return {'model':self.name+'-'+name+('-rawH' if raw else ''),
                    'answers':copy.deepcopy(chosen[name]),'usage':copy.deepcopy(self.last_usage),
                    'attribution':self.attribution}

            raw_native = response('ruvector_top2',raw=True)
            result = response('ruvector_top2')
            result.update(baseline104_response=baseline,
                ablation_responses={'same_nli_lexical_top2':response('lexical_top2'),
                    'same_nli_positional_first2':response('positional_first2'),
                    'same_nli_native_raw_h':raw_native},
                semantic_ablation_responses={'same_nli_native_raw_h':copy.deepcopy(raw_native),
                    'same_nli_lexical_raw_h':response('lexical_top2',raw=True),
                    'same_nli_positional_raw_h':response('positional_first2',raw=True)},
                diagnostics=diagnostics,whole_request_wall_ms=(time.perf_counter()-started)*1000,
                reader_model={'repo':MODELS.REPO,'revision':MODELS.REVISION,'classes':3,
                    'raw_labels':{'0':'contradiction','1':'entailment','2':'neutral'},
                    'precision':'OFFICIAL_QUINT8_AVX2','selected_model_changed':False,
                    'mapping':'Full-proposition-NOT mirrored arithmeticmean; Yes=E;No=C+N;T1',
                    'counterclaim_prefix':PAIRING.PREFIX,'positive_query_ranking_only':True,
                    'definition_priority_shared_all_arms':True,'definition_priority_token_cap':160,
                    'same_premise_for_positive_counterclaim_rawH':True,
                    'final_global_source_order':True})
            return result
        finally:
            self.last_usage.update(execution_terminal=self.execution_snapshot(),
                                   request_wall_seconds=time.perf_counter()-started)
