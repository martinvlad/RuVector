"""Injected readers prove unchanged context and corrected model provenance."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_models import Tokenizer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch12_test_runtime', HERE / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class ContextInvariantTests(unittest.TestCase):
    def test_actual_shared_answer_helper_tie_is_no(self):
        answer = runtime.HELPERS.answer_for({'Yes': .5, 'No': .5})
        self.assertEqual(answer['choice'], 'No')

    def reader(self, cls, config):
        reader = cls.__new__(cls)
        reader.config = config
        reader.training_phase = 'EVAL_READY'
        reader.training_by_id = {}
        reader.counters = dict.fromkeys(('requests_attempted', 'requests_completed',
                                        'context_partitions_attempted', 'context_partitions_completed',
                                        'context_packs_attempted', 'context_packs_completed',
                                        'native104_requests_attempted', 'native104_requests_completed'), 0)
        reader.execution_snapshot = lambda: {'counters': copy.deepcopy(reader.counters), 'resources': {'fixture': True}}
        reader.observed_premises = []
        reader.observed_controls = []

        def decode(premise, hypothesis):
            reader.observed_premises.append((premise, hypothesis))
            return {'Yes': 0.7, 'No': 0.3}, {'fixture_logits': [2, 1]}

        def native(state, questions):
            reader.observed_controls.append({'state': state, 'questions': copy.deepcopy(questions)})
            return {'answers': {key: {'type': 'choice', 'choice': 'No', 'probabilities': {'Yes': 0.4, 'No': 0.6}}
                                for key in questions}, 'usage': {'fixture': True}}

        reader.nli = SimpleNamespace(tokenizer=Tokenizer(), decode=decode)
        reader.bge = SimpleNamespace(raw_tokenizer=Tokenizer())
        reader.base = SimpleNamespace(predict=native)
        reader.retrieve = lambda chunks, hypothesis: (list(reversed(range(min(40, len(chunks))))), {'fixture': True})
        return reader

    def test_exact_epoch6_contexts_controls_and_all_arms(self):
        config6 = json.loads((HERE.parent / 'epoch6/config.json').read_text())
        config9 = json.loads((HERE / 'config.json').read_text())
        old = self.reader(runtime.FROZEN6.CandidateEngine, config6)
        new = self.reader(runtime.CandidateEngine, config9)
        state = 'First clause permits copies. Second clause requires return.\n\nTerm is30 days. Exception lasts24 months.'
        question = {'type': 'choice', 'criteria': {'Yes': 'Receiving party may make copies.', 'No': 'No copies.'}}
        before = old.predict(state, {'decision': question})
        after = new.predict(state, {'decision': question})
        self.assertEqual(old.observed_premises, new.observed_premises)
        self.assertEqual(old.observed_controls, new.observed_controls)
        self.assertEqual(before['diagnostics']['decision']['arms'], after['diagnostics']['decision']['arms'])
        self.assertEqual(before['baseline104_response'], after['baseline104_response'])
        for response in [after] + list(after['ablation_responses'].values()):
            self.assertEqual(response['answers']['decision']['model'], runtime.MODELS.REPO + '@' + runtime.MODELS.REVISION)
            self.assertEqual(response['answers']['decision']['probabilities'], {'Yes': 0.7, 'No': 0.3})
        self.assertTrue(after['reader_model']['context_policy_unchanged_from_epoch6'])
        self.assertEqual(after['reader_model']['classes'], 3)

    def test_frozen_context_fields_match_old_config(self):
        old = json.loads((HERE.parent / 'epoch6/config.json').read_text())
        new = json.loads((HERE / 'config.json').read_text())
        for key in ('source_partition', 'query_prefix', 'ranking_depth', 'packing', 'joint_pair_token_cap'):
            self.assertEqual(new[key], old[key])


class TrainingBoundaryTests(unittest.TestCase):
    state='The recipient must return the material.'
    questions={'decision': {'type':'choice','criteria': {'Yes':'The material must be returned.','No':'No return duty.'}}}

    def reader(self):
        import hashlib
        reader=runtime.CandidateEngine.__new__(runtime.CandidateEngine)
        reader.training_phase='TRAIN_SANITY';reader.training_attempted_ids=set();reader.training_completed_ids=set()
        raw=json.dumps({'state':self.state,'questions':self.questions},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        reader.training_by_id={str(i):{'id':str(i),'input_sha256':hashlib.sha256(raw).hexdigest()} for i in range(6)}
        reader.counters={};reader.receipt={};reader.last_usage={}
        reader.execution_snapshot=lambda: {'counters':copy.deepcopy(reader.counters)}
        trace={'input_ids':[1,2], 'attention_mask':[1,1], 'token_type_ids':[0,1],
               'input_text_sha256':'fixture','raw_label_indices':{'entailment':0,'neutral':1,'contradiction':2},
               'precision':'FP32','canonical_logits_E_C_N':[3.,0.,0.],
               'raw_threeway_probabilities':{'Entailment':.9,'Contradiction':.05,'NotMentioned':.05}}
        def primary(state,questions):
            return {'answers':{},'ablation_responses':{'same_nli_lexical_top2':{'answers':{}},'same_nli_positional_first2':{'answers':{}}},
                    'diagnostics':{'decision':{'arms':{'ruvector_top2':{'premise':'exact packed source','hypothesis':'whole claim','decoding':copy.deepcopy(trace)}}}}}
        reader._predict_fp32=primary;reader.quantized_calls=[]
        def quantized(premise,hypothesis):
            reader.quantized_calls.append((premise,hypothesis));q=copy.deepcopy(trace);q['precision']='INT8_TRAIN_DIAGNOSTIC'
            return {'Yes':.9,'No':.1},q
        reader.quantized_nli=SimpleNamespace(decode=quantized,session=SimpleNamespace())
        return reader

    def test_six_exact_identities_release_quantized_and_prevent_reuse(self):
        reader=self.reader()
        with self.assertRaises(ValueError):reader.predict(self.state,self.questions)
        with self.assertRaises(ValueError):reader.finish_training_sanity()
        for i in range(6):
            out=reader.predict_train_sanity(self.state,self.questions,str(i))
            self.assertTrue(out['precision_fidelity']['decision']['binary_decision_agrees'])
            self.assertEqual(out['usage']['nli_singleton_pairs'],4)
            self.assertEqual(out['quantized_primary_response']['answers']['decision']['choice'],'Yes')
        self.assertEqual(reader.quantized_calls,[('exact packed source','whole claim')]*6)
        receipt=reader.finish_training_sanity()
        self.assertEqual(receipt['completed'],6);self.assertTrue(receipt['quantized_session_released'])
        self.assertIsNone(reader.quantized_nli);self.assertEqual(reader.training_phase,'EVAL_READY')
        self.assertFalse(receipt['precision_selection']);self.assertEqual(receipt['optimizer_fits'],0)
        with self.assertRaises(ValueError):reader.predict(self.state,self.questions)
        for operation in (lambda:reader.finish_training_sanity(),lambda:reader.predict_train_sanity(self.state,self.questions,'0')):
            with self.assertRaises(ValueError):operation()

    def test_unknown_mutated_duplicate_inputs_never_get_another_diagnostic(self):
        reader=self.reader()
        for call in (lambda:reader.predict_train_sanity(self.state,self.questions,'unknown'),
                     lambda:reader.predict_train_sanity(self.state+' changed',self.questions,'0')):
            with self.assertRaises(ValueError):call()
        self.assertEqual(reader.quantized_calls,[])
        reader.predict_train_sanity(self.state,self.questions,'0')
        with self.assertRaises(ValueError):reader.predict_train_sanity(self.state,self.questions,'0')
        self.assertEqual(len(reader.quantized_calls),1)

    def test_partial_failure_retires_attempt_and_blocks_DEV(self):
        reader=self.reader()
        def failed(*args):raise RuntimeError('injected INT8 failure')
        reader.quantized_nli.decode=failed
        with self.assertRaises(RuntimeError):reader.predict_train_sanity(self.state,self.questions,'0')
        self.assertEqual(reader.training_attempted_ids,{'0'});self.assertEqual(reader.training_completed_ids,set())
        with self.assertRaises(ValueError):reader.predict_train_sanity(self.state,self.questions,'0')
        with self.assertRaises(ValueError):reader.finish_training_sanity()
        with self.assertRaises(ValueError):reader.predict(self.state,self.questions)


if __name__ == '__main__':
    unittest.main()
