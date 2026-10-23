"""Injected engine wiring checks; no actual reader, ANN or native104 execution."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from tokenizers import Tokenizer
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch15_runtime_engineering', HERE / 'runtime.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


class InjectedReader:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.calls = []
    def decode(self, premise, hypothesis):
        self.calls.append((premise, hypothesis))
        return {'Yes': 0.6, 'No': 0.4}, {'injected_engineering_only': True}


class InjectedNative104:
    def __init__(self):
        self.calls = []
    def predict(self, state, questions):
        self.calls.append((state, questions))
        return {'answers': {k: R.HELPERS.answer_for({'Yes': 0.6, 'No': 0.4}) for k in questions},
                'usage': {'injected_engineering_only': True}}


class RuntimeTests(unittest.TestCase):
    def engine(self):
        t = Tokenizer.from_file(str(HERE / 'assets/official-deberta-v3-large/tokenizer.json'))
        t.no_truncation();t.no_padding()
        e = R.CandidateEngine.__new__(R.CandidateEngine)
        e.config = {'source_partition': {'target': 32, 'nli_cap': 64, 'bge_cap': 256, 'max_units': 192},
                    'ranking_depth': 40, 'joint_pair_token_cap': 512,
                    'query_prefix': 'Represent this sentence for searching relevant passages: ',
                    'legacy_arm_names': 'Injected engineering aliases only'}
        e.counters = dict.fromkeys(('requests_attempted', 'requests_completed',
                                   'context_partitions_attempted', 'context_partitions_completed',
                                   'context_packs_attempted', 'context_packs_completed',
                                   'native104_requests_attempted', 'native104_requests_completed'), 0)
        e.nli = InjectedReader(t)
        e.bge = SimpleNamespace(raw_tokenizer=t)
        e.base = InjectedNative104()
        e.last_usage = None
        e.retrieve = lambda chunks, hypothesis: (list(reversed(range(min(40, len(chunks))))),
                                                 {'injected_engineering_ranking': True})
        return e

    def test_matched_priority_and_native104_exact_primary_excerpt(self):
        e = self.engine()
        state = 'This agreement is between Acme and Beta.\n\nThe material (“Confidential Information”) stays protected.\n\nKeep records for 20 days.'
        q = {'p': {'type': 'choice', 'criteria': {'Yes': 'Records stay protected.', 'No': 'Other.'}}}
        result = e.predict(state, q)
        arms = result['diagnostics']['p']['arms']
        priorities = [a['coverage']['definition_priority'] for a in arms.values()]
        self.assertTrue(all(p == priorities[0] for p in priorities))
        self.assertLessEqual(priorities[0]['priority_tokens'], 160)
        self.assertEqual(e.base.calls[0][0], arms['ruvector_top2']['premise'])
        self.assertEqual(e.base.calls[0][1], q)
        self.assertEqual(len(e.nli.calls), 3)
        self.assertTrue(all(h == q['p']['criteria']['Yes'] for _, h in e.nli.calls))
        self.assertTrue(all(a['coverage']['no_priority_counterfactual']['model_forwards'] == 0 for a in arms.values()))
        self.assertEqual(result['reader_model']['definition_priority_token_cap'], 160)
        self.assertEqual(e.counters['requests_completed'], 1)

    def test_claim_conflict_rejected_before_any_injected_call(self):
        e = self.engine()
        e.config['joint_pair_token_cap'] = 8
        with self.assertRaises(ValueError):
            e.predict('The material (“Confidential Information”) stays protected.',
                      {'p': {'type': 'choice', 'criteria': {'Yes': 'These source records remain protected forever.', 'No': 'Other.'}}})
        self.assertEqual(e.base.calls, [])
        self.assertEqual(e.nli.calls, [])
        self.assertEqual(e.counters['requests_completed'], 0)


if __name__ == '__main__':
    unittest.main()
