"""Synthetic stdlib-only checks: no model/tokenizer/native/corpus/Gold execution."""
import copy
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packing
import reader
import evaluate


def units_from(parts):
    units = []; offset = 0
    for index, part in enumerate(parts):
        units.append({'unit_id': index, 'sentence': part, 'start': offset, 'end': offset + len(part)})
        offset += len(part)
    return units


def fake_tokenize(premise, claim):
    count = len(premise) + len(claim) + 3
    return {'input_ids': [1] * count, 'attention_mask': [1] * count,
            'token_type_ids': [0] * (len(claim) + 2) + [1] * (len(premise) + 1)}


def synthetic_raw_rows():
    expected = []; labels = {}; rows = []
    units = units_from(['alpha ' * 50, 'beta ' * 60])
    windows = packing.pack_whole_source(units, 'claim', fake_tokenize)
    assert len(windows) == 2
    for i in range(12):
        case = 'synthetic-' + str(i); expected.append(case)
        gold = evaluate.LABELS[i % 3]; labels[case] = gold
        for arm in evaluate.ARMS:
            prediction = i % 3 if arm in ('native', 'whole_source') or i >= 3 else (i + 1) % 3
            logits = [0.0, 0.0, 0.0]; logits[prediction] = 4.0
            value = reader.stable_scores(logits)
            row = dict(case_id=case, document_id=i // 3, hypothesis_id='h' + str(i % 3),
                       arm=arm, elapsed_seconds=.02, forward_seconds=.02,
                       model_forward_calls=2 if arm == 'whole_source' else 1,
                       window_count=2 if arm == 'whole_source' else 1, **value)
            if arm == 'whole_source':
                forecasts = [{**reader.stable_scores(logits), 'forward_seconds': .01,
                              'evidence': copy.deepcopy(w['evidence'])} for w in windows]
                winner, selected = packing.select_whole_source_forecast(forecasts)
                row['evidence'] = copy.deepcopy(selected['evidence'])
                row['evidence']['aggregation'] = dict(selected_window_index=winner,
                    all_window_count=len(forecasts), selected_three_way_forecast_unchanged=True,
                    all_source_units_once=True, all_source_characters_once=True,
                    no_probability_clipping_or_calibration=True, author_documented_aggregation=False)
                row['window_forecasts'] = forecasts
            rows.append(row)
    return rows, labels, expected


class InertChecks(unittest.TestCase):
    def test_complete_source_partition_and_numeric_boundary(self):
        units = units_from(['Pay 3', ' days. ', 'alpha ' * 70, 'beta ' * 70])
        windows = packing.pack_whole_source(units, 'claim', fake_tokenize)
        self.assertEqual([i for w in windows for i in w['evidence']['selected_unit_ids']], list(range(4)))
        self.assertTrue(all(w['evidence']['pair_token_count'] <= 512 for w in windows))
        self.assertEqual(sum(w['evidence']['selected_source_characters'] for w in windows), sum(len(x['sentence']) for x in units))
        self.assertTrue(all(w['evidence']['full_source_numeric_partition_audit']['source_and_premise_occurrence_counts_match'] for w in windows))

    def test_single_overlong_unit_rejected_without_partial_output(self):
        with self.assertRaisesRegex(ValueError, 'WHOLE_SOURCE_SINGLE_UNIT_EXCEEDS_PAIR_CAP'):
            packing.pack_whole_source(units_from(['x' * 510]), 'claim', fake_tokenize)

    def test_seventeenth_window_rejected(self):
        with self.assertRaisesRegex(ValueError, 'WHOLE_SOURCE_EXCEEDS_16_WINDOWS'):
            packing.pack_whole_source(units_from(['x' * 300] * 17), 'claim', fake_tokenize)

    def test_aggregation_exact_tie_earliest_and_whole_vector(self):
        rows = []
        for index, logits in enumerate([[1.0, 0.0, -1.0], [0.0, 1.0, -1.0]]):
            rows.append({**reader.stable_scores(logits), 'evidence': {'window_index': index, 'complete_source_coverage': True}})
        index, selected = packing.select_whole_source_forecast(rows)
        self.assertEqual(index, 0)
        self.assertIs(selected, rows[0])
        self.assertEqual(selected['probabilities'], rows[0]['probabilities'])

    def test_tiny_logit_argmax_survives_probability_rounding(self):
        logits = [0.0, 1e-20, 0.0]
        value = reader.stable_scores(logits)
        self.assertEqual(value['probabilities'], [1.0 / 3.0] * 3)
        self.assertEqual(value['prediction'], 'Contradiction')
        scorer_prediction = evaluate.LABELS[max(range(3), key=lambda i: logits[i])]
        self.assertEqual(value['prediction'], scorer_prediction)
        tied = reader.stable_scores([0.0, 0.0, 0.0])
        self.assertEqual(tied['prediction'], 'Entailment')

    def test_hypothesis_first_and_true_bert_segment_ids(self):
        calls = []
        r = reader.Reader.__new__(reader.Reader)
        r.counters = {'reader_pair_tokenizations': 0}; r.check_deadline = lambda: None
        def tokenizer(first, second, **kwargs):
            calls.append((first, second, kwargs))
            return {'input_ids': [101, 11, 102, 12, 102], 'attention_mask': [1] * 5,
                    'token_type_ids': [0, 0, 0, 1, 1]}
        r.tokenizer = tokenizer
        tokens = r.tokenize('source premise', 'whole hypothesis')
        self.assertEqual(calls[0][0:2], ('whole hypothesis', 'source premise'))
        self.assertTrue(calls[0][2]['return_token_type_ids'])
        self.assertFalse(calls[0][2]['truncation'])
        self.assertEqual(tokens['token_type_ids'], [0, 0, 0, 1, 1])

    def test_fourth_control_blocks_gate_and_window_replay_detects_tamper(self):
        rows, labels, expected = synthetic_raw_rows()
        result = evaluate.evaluate_rows(rows, labels, expected)
        self.assertTrue(result['gate_checks']['lexical:native_gain_at_least_two_correct'])
        self.assertTrue(result['gate_checks']['source_order:native_gain_at_least_two_correct'])
        self.assertFalse(result['gate_checks']['whole_source:native_gain_at_least_two_correct'])
        self.assertFalse(result['point_gates_passed'])
        self.assertEqual(evaluate.validate_whole_source_aggregation(rows), 60)
        altered = copy.deepcopy(rows)
        target = next(r for r in altered if r['arm'] == 'whole_source')
        target['evidence']['aggregation']['selected_window_index'] = 1
        with self.assertRaises(AssertionError):
            evaluate.validate_whole_source_aggregation(altered)
        truncated = copy.deepcopy(rows)
        target = next(r for r in truncated if r['arm'] == 'whole_source')
        target['window_forecasts'][1]['probabilities'].pop()
        with self.assertRaises(AssertionError):
            evaluate.validate_whole_source_aggregation(truncated)


if __name__ == '__main__':
    unittest.main()
