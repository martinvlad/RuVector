"""Injected evidence-reader tests; no constructor, addon, model or corpus call."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_context import Tokenizer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch6_test_runtime', HERE / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def engine(self):
        engine = runtime.CandidateEngine.__new__(runtime.CandidateEngine)
        engine.config = json.loads((HERE / 'config.json').read_text())
        engine.counters = dict.fromkeys(('requests_attempted', 'requests_completed',
                                        'context_partitions_attempted', 'context_partitions_completed',
                                        'context_packs_attempted', 'context_packs_completed',
                                        'native104_requests_attempted', 'native104_requests_completed'), 0)
        engine.execution_snapshot = lambda: {'counters': copy.deepcopy(engine.counters), 'resources': {'fixture': True}}
        engine.nli_inputs = []
        engine.native_inputs = []

        def decode(premise, hypothesis):
            engine.nli_inputs.append((premise, hypothesis))
            return {'Yes': 0.6, 'No': 0.4}, {'logits': [0.0, 0.0, 1.0], 'input_tokens': len(Tokenizer().encode(premise, hypothesis).ids),
                                         'batch_size': 1, 'truncated': False}

        def native_predict(state, questions):
            engine.native_inputs.append({'state': state, 'questions': copy.deepcopy(questions)})
            return {'answers': {key: {'type': 'choice', 'choice': 'No', 'probabilities': {'Yes': 0.4, 'No': 0.6}}
                                for key in questions}, 'usage': {'fixture': True}}

        engine.nli = SimpleNamespace(tokenizer=Tokenizer(), decode=decode)
        engine.bge = SimpleNamespace(raw_tokenizer=Tokenizer())
        engine.base = SimpleNamespace(predict=native_predict)
        engine.retrieve = lambda chunks, hypothesis: (list(reversed(range(min(40, len(chunks))))), {'fixture': True})
        return engine

    def test_input_only_api_control_excerpt_hash_question_and_all_arms(self):
        engine = self.engine()
        state = '\n\n'.join('Clause' + str(i) + ' retains ' + str(i + 10) + ' records.' for i in range(45))
        question = {'type': 'choice', 'criteria': {'Yes': 'Copies may be retained.', 'No': 'Copies may not be retained.'}}
        out = engine.predict(state, {'decision': question})
        diag = out['diagnostics']['decision']
        self.assertEqual(diag['source_state'], state)
        self.assertEqual(diag['ranking_candidate_depth'], 40)
        self.assertEqual(engine.native_inputs, [diag['baseline_control_input']])
        self.assertEqual(engine.native_inputs[0]['questions'], {'decision': question})
        self.assertEqual(engine.native_inputs[0]['state'], diag['arms']['ruvector_top2']['premise'])
        literal = json.dumps(engine.native_inputs[0], ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(runtime.hashlib.sha256(literal).hexdigest(), diag['baseline_control_input_sha256'])
        self.assertEqual(len(engine.nli_inputs), 3)
        self.assertTrue(all(hypothesis == question['criteria']['Yes'] for premise, hypothesis in engine.nli_inputs))
        self.assertTrue(all(len(arm['ranking_ids']) == 40 for arm in diag['arms'].values()))
        self.assertEqual(set(out['ablation_responses']), {'same_nli_lexical_top2', 'same_nli_positional_first2'})
        self.assertEqual(out['baseline104_response']['model'], 'native104_on_ruvector_evidence')
        self.assertEqual(engine.counters['context_packs_completed'], 3)
        self.assertEqual(engine.counters['requests_completed'], 1)
        self.assertIn('compatibility aliases', out['attribution'])

    def test_renamed_question_key_does_not_change_context_or_distribution(self):
        state = 'Receiving party may copy a record. Copies remain confidential.'
        question = {'type': 'choice', 'criteria': {'Yes': 'Party may make copies.', 'No': 'Party may not make copies.'}}
        first = self.engine().predict(state, {'first': question})
        second = self.engine().predict(state, {'renamed': question})
        self.assertEqual(first['answers']['first'], second['answers']['renamed'])
        self.assertEqual(first['diagnostics']['first']['arms']['ruvector_top2']['premise'],
                         second['diagnostics']['renamed']['arms']['ruvector_top2']['premise'])

    def test_overlong_query_rejected_before_retrieval_or_reader(self):
        engine = self.engine()
        engine.retrieve = lambda *args: self.fail('Retrieval must not run')
        question = {'type': 'choice', 'criteria': {'Yes': ' '.join(['claim'] * 260), 'No': 'No.'}}
        with self.assertRaises(ValueError):
            engine.predict('Complete source sentence.', {'decision': question})
        self.assertEqual(engine.native_inputs, [])
        self.assertEqual(engine.nli_inputs, [])
        self.assertEqual(engine.counters['requests_completed'], 0)
        self.assertIn('execution_terminal', engine.last_usage)

    def test_native_ranking_uses_observed40_not_hidden_exact_substitution(self):
        engine = self.engine()
        engine.config['ranking_depth'] = 40
        old = runtime.PREVIOUS.CandidateEngine.retrieve
        diagnostics = {'native': {'queries': [{'ids': list(reversed(range(40)))}]}}
        try:
            runtime.PREVIOUS.CandidateEngine.retrieve = lambda *args: ([39, 38], diagnostics)
            ranking, trace = runtime.CandidateEngine.retrieve(engine, ['chunk'] * 45, 'Hypothesis.')
            self.assertEqual(ranking, list(reversed(range(40))))
            self.assertEqual(trace['ranking_scope']['units_outside_candidate_depth'], 5)
            self.assertEqual(trace['ranking_scope']['actual_returned_ids'], ranking)
        finally:
            runtime.PREVIOUS.CandidateEngine.retrieve = old


if __name__ == '__main__':
    unittest.main()
