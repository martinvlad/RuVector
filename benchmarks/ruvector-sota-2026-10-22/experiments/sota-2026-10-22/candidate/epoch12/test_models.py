"""Typed threeway mapping, token-domain and feed tests using a synthetic session only."""
import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch12_test_models', HERE / 'models.py')
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
        reader.label_indices = {'entailment': 0, 'neutral': 1, 'contradiction': 2}
        reader.inputs = {'input_ids', 'attention_mask'}
        reader.precision = 'FP32'
        reader.counter_prefix = 'nli_fp32'
        reader.model_sha256 = 'fixture-FP32-weight'

        reader.counters = dict.fromkeys(('nli_forward_pairs_attempted', 'nli_forward_pairs_completed',
                                        'nli_input_tokens_attempted', 'nli_input_tokens_completed'), 0)
        reader.counters['nli_forward_wall_seconds'] = 0.0
        for suffix in ('forward_pairs_attempted', 'forward_pairs_completed', 'input_tokens_attempted', 'input_tokens_completed'):
            reader.counters['nli_fp32_' + suffix] = 0
        reader.counters['nli_fp32_forward_wall_seconds'] = 0.0
        reader.observed_feeds = []

        def run(outputs, feed):
            reader.observed_feeds.append(feed)
            return [np.asarray([[2.0, -1.0, 0.0]], dtype=np.float32)]

        reader.session = SimpleNamespace(run=run)
        return reader

    def test_actual_config_threeway_semantics(self):
        config = json.loads((HERE.parent / 'epoch11/assets/nli-large-threeway/config.json').read_text())
        self.assertEqual(models.label_indices(config), {'entailment': 0, 'neutral': 1, 'contradiction': 2})
        self.assertEqual(config['num_hidden_layers'], 24)
        self.assertEqual(config['hidden_size'], 1024)

    def test_label_index_permutation_preserves_threeway_meaning(self):
        normal = models.probabilities([[3, 2, 1]], models.label_indices({'id2label': {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}}))
        swapped = models.probabilities([[1, 3, 2]], models.label_indices({'id2label': {'0': 'contradiction', '1': 'entailment', '2': 'neutral'}}))
        self.assertEqual(normal, swapped)
        self.assertAlmostEqual(normal['Yes'] + normal['No'], 1)

    def test_neutral_mass_is_never_discarded(self):
        mapping = {'entailment': 0, 'neutral': 1, 'contradiction': 2}
        output = models.probabilities([[1, 5, 0]], mapping)
        self.assertGreater(output['No'], .9)
        typed = models.threeway_probabilities([[1, 5, 0]], mapping)
        self.assertEqual(set(typed), {'Entailment', 'Contradiction', 'NotMentioned'})
        self.assertAlmostEqual(output['No'], typed['Contradiction'] + typed['NotMentioned'])

    def test_exact_half_tie_is_no_under_canonical_decision(self):
        output = models.probabilities([[np.log(2), 0, 0]], {'entailment': 0, 'neutral': 1, 'contradiction': 2})
        self.assertEqual(output, {'Yes': .5, 'No': .5})
        self.assertEqual(min(output, key=lambda k: (-output[k], k)), 'No')

    def test_invalid_labels_shapes_and_nonfinite_logits_rejected(self):
        for mapping in ({'0': 'entailment', '1': 'neutral'}, {'0': 'entailment', '1': 'neutral', '3': 'contradiction'}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                models.label_indices({'id2label': mapping})
        for logits in ([[1, 2]], [1, 2, 3], [[float('nan'), 0, 0]], [[0, 0, float('inf')]]):
            with self.subTest(logits=logits), self.assertRaises(ValueError):
                models.probabilities(logits, {'entailment': 0, 'neutral': 1, 'contradiction': 2})

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
        self.assertEqual(trace['logits'], [2.0, -1.0, 0.0])
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


class FidelityTests(unittest.TestCase):
    def trace(self, logits, precision):
        mapping = {'entailment': 0, 'neutral': 1, 'contradiction': 2}
        return {'input_ids': [1, 7, 2, 8, 2], 'attention_mask': [1]*5,
                'token_type_ids': [0,0,0,1,1], 'input_text_sha256': 'fixture',
                'raw_label_indices': mapping, 'precision': precision,
                'canonical_logits_E_C_N': [logits[0], logits[2], logits[1]],
                'raw_threeway_probabilities': models.threeway_probabilities([logits], mapping)}

    def test_common_logit_offset_preserves_probabilities(self):
        a=self.trace([1,2,3], 'FP32');b=self.trace([11,12,13], 'INT8_TRAIN_DIAGNOSTIC')
        out=models.paired_fidelity(a,b)
        self.assertEqual(out['raw_logits_max_absolute_difference'],10)
        self.assertEqual(out['centered_logits_max_absolute_difference'],0)
        self.assertEqual(out['typed_probability_max_absolute_difference'],0)
        self.assertEqual(out['Jensen_Shannon_divergence_nats'],0)
        self.assertTrue(out['typed_decision_agrees'])
        self.assertFalse(out['source_original_fidelity_established'])

    def test_different_typed_decision_and_identical_feed_required(self):
        a=self.trace([5,-2,-2], 'FP32');b=self.trace([-2,-2,5], 'INT8_TRAIN_DIAGNOSTIC')
        out=models.paired_fidelity(a,b)
        self.assertFalse(out['binary_decision_agrees'])
        self.assertFalse(out['typed_decision_agrees'])
        self.assertGreater(out['Jensen_Shannon_divergence_nats'],.6)
        for field in ('input_ids','attention_mask','token_type_ids','input_text_sha256','raw_label_indices'):
            changed=dict(b);changed[field]='different'
            with self.subTest(field=field),self.assertRaises(ValueError):
                models.paired_fidelity(a,changed)

    def test_invalid_precision_and_nonfinite_traces_rejected(self):
        a=self.trace([1,2,3], 'FP32');b=self.trace([1,2,3], 'INT8_TRAIN_DIAGNOSTIC')
        changed=dict(b);changed['precision']='FP32'
        with self.assertRaises(ValueError):models.paired_fidelity(a,changed)
        changed=dict(b);changed['canonical_logits_E_C_N']=[0,float('nan'),0]
        with self.assertRaises(ValueError):models.paired_fidelity(a,changed)
        changed=dict(b);changed['raw_threeway_probabilities']={'Entailment':.2,'Contradiction':.2,'NotMentioned':.2}
        with self.assertRaises(ValueError):models.paired_fidelity(a,changed)


if __name__ == '__main__':
    unittest.main()
