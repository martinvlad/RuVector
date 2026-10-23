"""Engineering-only injected identical tokenizers prove algorithm preservation and corrected model provenance; actual active BPE context strings differ."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_models import Tokenizer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch13_test_runtime', HERE / 'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class ContextInvariantTests(unittest.TestCase):
    def test_actual_shared_answer_helper_tie_is_no(self):
        answer = runtime.HELPERS.answer_for({'Yes': .5, 'No': .5})
        self.assertEqual(answer['choice'], 'No')

    def reader(self, cls, config):
        reader = cls.__new__(cls)
        reader.config = config
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

    def test_identical_injected_tokenizers_preserve_algorithm_controls_all_arms(self):
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
        self.assertFalse(after['reader_model']['context_policy_unchanged_from_epoch6'])
        self.assertTrue(after['reader_model']['context_algorithm_unchanged_from_epoch6'])
        self.assertEqual(after['reader_model']['classes'], 3)

    def test_frozen_context_fields_match_old_config(self):
        old = json.loads((HERE.parent / 'epoch6/config.json').read_text())
        new = json.loads((HERE / 'config.json').read_text())
        for key in ('source_partition', 'query_prefix', 'ranking_depth', 'packing', 'joint_pair_token_cap'):
            self.assertEqual(new[key], old[key])


if __name__ == '__main__':
    unittest.main()
