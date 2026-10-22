"""Binary mapping, token-domain and feed tests using a synthetic session only."""
import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch7_test_models', HERE / 'models.py')
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class Tokenizer:
    def __init__(self, multiplier=1, padded=False):
        self.multiplier = multiplier
        self.padded = padded

    def encode(self, text, pair=None, add_special_tokens=True):
        offsets = [m.span() for m in re.finditer(r'\w+|[^\w\s]', text)]
        count = len(offsets) * self.multiplier
        if pair is not None:
            count += len(re.findall(r'\w+|[^\w\s]', pair)) * self.multiplier + 3
        elif add_special_tokens:
            count += 2
        mask = [1] * count
        if self.padded and mask:
            mask[-1] = 0
        return SimpleNamespace(ids=list(range(count)), offsets=offsets,
                               attention_mask=mask, type_ids=[0] * count)


class DecoderTests(unittest.TestCase):
    def reader(self, multiplier=1, padded=False):
        reader = models.SingletonNli.__new__(models.SingletonNli)
        reader.tokenizer = Tokenizer()
        reader.model_tokenizer = Tokenizer(multiplier, padded)
        reader.label_indices = {'entailment': 0, 'not_entailment': 1}
        reader.inputs = {'input_ids', 'attention_mask'}
        reader.counters = dict.fromkeys(('nli_forward_pairs_attempted', 'nli_forward_pairs_completed',
                                        'nli_input_tokens_attempted', 'nli_input_tokens_completed'), 0)
        reader.counters['nli_forward_wall_seconds'] = 0.0
        reader.observed_feeds = []

        def run(outputs, feed):
            reader.observed_feeds.append(feed)
            return [np.asarray([[2.0, -1.0]], dtype=np.float32)]

        reader.session = SimpleNamespace(run=run)
        return reader

    def test_actual_config_binary_semantics(self):
        config = json.loads((HERE / 'assets/nli-large/config.json').read_text())
        self.assertEqual(models.label_indices(config), {'entailment': 0, 'not_entailment': 1})
        self.assertEqual(config['num_hidden_layers'], 24)
        self.assertEqual(config['hidden_size'], 1024)

    def test_label_index_permutation_preserves_binary_meaning(self):
        normal = models.probabilities([[3, 1]], models.label_indices({'id2label': {'0': 'entailment', '1': 'not_entailment'}}))
        swapped = models.probabilities([[1, 3]], models.label_indices({'id2label': {'0': 'not_entailment', '1': 'entailment'}}))
        self.assertEqual(normal, swapped)
        self.assertAlmostEqual(normal['Yes'] + normal['No'], 1)
        self.assertGreater(normal['Yes'], 0.8)

    def test_invalid_labels_shapes_and_nonfinite_logits_rejected(self):
        for mapping in ({'0': 'entailment', '1': 'neutral'}, {'0': 'entailment', '2': 'not_entailment'}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                models.label_indices({'id2label': mapping})
        for logits in ([[1, 2, 3]], [1, 2], [[float('nan'), 0]], [[0, float('inf')]]):
            with self.subTest(logits=logits), self.assertRaises(ValueError):
                models.probabilities(logits, {'entailment': 0, 'not_entailment': 1})

    def test_singleton_int64_unpadded_feed_and_both_token_traces(self):
        reader = self.reader(multiplier=2)
        output, trace = reader.decode('Complete source evidence.', 'Whole claim.')
        self.assertEqual(len(reader.observed_feeds), 1)
        feed = reader.observed_feeds[0]
        self.assertEqual(set(feed), {'input_ids', 'attention_mask'})
        self.assertEqual(feed['input_ids'].shape[0], 1)
        self.assertEqual(feed['input_ids'].dtype, np.int64)
        self.assertTrue(np.all(feed['attention_mask'] == 1))
        self.assertGreater(trace['actual_model_pair_tokens'], trace['frozen_epoch6_policy_pair_tokens'])
        self.assertEqual(trace['logits'], [2.0, -1.0])
        self.assertAlmostEqual(sum(output.values()), 1)
        self.assertEqual(reader.counters['nli_forward_pairs_completed'], 1)

    def test_actual_model_token_budget_rejects_before_session(self):
        reader = self.reader(multiplier=2)
        with self.assertRaises(ValueError):
            reader.decode(' '.join(['evidence'] * 255), 'Whole claim.')
        self.assertEqual(reader.observed_feeds, [])
        self.assertEqual(reader.counters['nli_forward_pairs_attempted'], 0)

    def test_padding_rejects_before_session(self):
        reader = self.reader(padded=True)
        with self.assertRaises(ValueError):
            reader.decode('Source evidence.', 'Whole claim.')
        self.assertEqual(reader.observed_feeds, [])


if __name__ == '__main__':
    unittest.main()
