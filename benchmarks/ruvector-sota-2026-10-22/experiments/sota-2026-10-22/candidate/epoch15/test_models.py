"""Real tokenizer plus injected fake logits; no ORT/native/model execution."""
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch15_models_engineering', HERE / 'models.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class FakeSession:
    def __init__(self):
        self.calls = []
    def run(self, names, feed):
        self.calls.append(feed)
        return [np.asarray([[0.0, 2.0, -1.0]], dtype=np.float32)]


class ModelTests(unittest.TestCase):
    def test_raw_C_E_N_to_typed_and_binary_mapping(self):
        mapping = M.label_indices({'id2label': {'0': 'contradiction', '1': 'entailment', '2': 'neutral'}})
        typed = M.threeway_probabilities([[0.0, 2.0, -1.0]], mapping)
        binary = M.probabilities([[0.0, 2.0, -1.0]], mapping)
        self.assertGreater(typed['Entailment'], typed['Contradiction'])
        self.assertAlmostEqual(binary['Yes'], typed['Entailment'])
        self.assertAlmostEqual(binary['No'], typed['Contradiction'] + typed['NotMentioned'])
        self.assertAlmostEqual(sum(typed.values()), 1.0)

    def test_nonfinite_logits_rejected(self):
        with self.assertRaises(ValueError):
            M.probabilities([[np.nan, 0, 1]], {'entailment': 1, 'contradiction': 0, 'neutral': 2})

    def test_real_pair_template_three_specials_and_B_type1(self):
        t = Tokenizer.from_file(str(HERE / 'assets/official-deberta-v3-large/tokenizer.json'))
        t.no_truncation(); t.no_padding()
        e = t.encode('An exact synthetic premise.', 'A complete synthetic claim.')
        self.assertEqual(e.ids[0], 1)
        self.assertEqual(e.ids[-1], 2)
        self.assertEqual(e.type_ids[0], 0)
        self.assertEqual(e.type_ids[-1], 1)
        self.assertTrue(all(x == 1 for x in e.attention_mask))
        self.assertEqual(sum(e.special_tokens_mask), 3)

    def engine(self):
        n = M.SingletonNli.__new__(M.SingletonNli)
        n.model_tokenizer = Tokenizer.from_file(str(HERE / 'assets/official-deberta-v3-large/tokenizer.json'))
        n.model_tokenizer.no_padding(); n.model_tokenizer.no_truncation()
        n.tokenizer = n.model_tokenizer
        n.inputs = {'input_ids', 'attention_mask'}
        n.session = FakeSession()
        n.label_indices = {'contradiction': 0, 'entailment': 1, 'neutral': 2}
        n.counters = dict.fromkeys(('nli_forward_pairs_attempted', 'nli_input_tokens_attempted',
                                   'nli_forward_pairs_completed', 'nli_input_tokens_completed'), 0)
        n.counters['nli_forward_wall_seconds'] = 0.0
        n.receipt = {'model_sha256': 'injected-engineering-fake-no-model-asset'}
        return n

    def test_injected_session_feeds_only_static_graph_inputs(self):
        n = self.engine()
        _, trace = n.decode('The synthetic recipient protects records.', 'Records are protected.')
        self.assertEqual(len(n.session.calls), 1)
        self.assertEqual(set(n.session.calls[0]), {'input_ids', 'attention_mask'})
        self.assertTrue(all(x.dtype == np.int64 for x in n.session.calls[0].values()))
        self.assertEqual(trace['token_type_ids'][-1], 1)
        self.assertEqual(trace['precision'], 'OFFICIAL_QUINT8_AVX2')
        self.assertFalse(trace['truncated'])

    def test_oversize_pair_rejected_before_injected_session(self):
        n = self.engine()
        with self.assertRaisesRegex(ValueError, 'exceed512'):
            n.decode('word ' * 600, 'A complete synthetic claim.')
        self.assertEqual(n.session.calls, [])
        self.assertEqual(n.counters['nli_forward_pairs_attempted'], 0)


if __name__ == '__main__':
    unittest.main()
