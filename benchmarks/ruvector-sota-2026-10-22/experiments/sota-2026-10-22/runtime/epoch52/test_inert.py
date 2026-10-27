"""Synthetic stdlib-only checks: no model/tokenizer/native/corpus/Gold execution."""
import copy
import ast
import hashlib
import json
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


TOKENIZER_METADATA = Path('/dev/shm/ruvector-e51-data/assets/contractnli-bert-nda-standard-ac92b6b512d7/tokenizer.json')
FAST_SOURCE = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/lib/python3.12/site-packages/transformers/tokenization_utils_fast.py')


class TemplateOnlyTokenizer:
    """Invented char-token sequences interpreted by original JSON templates only.

    Models the pinned Python fast wrapper's truthiness branch, never instantiates a
    tokenizer or performs corpus/model work. Empty second text uses SINGLE, which
    is precisely the behavior E51's fake overlooked.
    """
    def __init__(self):
        raw = TOKENIZER_METADATA.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == 'cb374d6bc042c22455946f4e09a89d29882a199fdaf8fb25be00dc8b8857a448'
        self.processor = json.loads(raw)['post_processor']
        self.calls = []

    def num_special_tokens_to_add(self, pair=False):
        return sum(len(self.processor['special_tokens'][entry['SpecialToken']['id']]['ids'])
                   for entry in self.processor['pair' if pair else 'single'] if 'SpecialToken' in entry)

    def __call__(self, first, second=None, **kwargs):
        self.calls.append((first, second, kwargs))
        chosen = 'pair' if second else 'single'
        synthetic = {'A': [11] * len(first), 'B': [12] * len(second or '')}
        ids = []; types = []
        for entry in self.processor[chosen]:
            if 'Sequence' in entry:
                part = entry['Sequence']; values = synthetic[part['id']]
            else:
                part = entry['SpecialToken']; values = self.processor['special_tokens'][part['id']]['ids']
            ids.extend(values); types.extend([part['type_id']] * len(values))
        return {'input_ids': ids, 'attention_mask': [1] * len(ids), 'token_type_ids': types}


def inert_reader():
    r = reader.Reader.__new__(reader.Reader)
    r.counters = {'reader_pair_tokenizations': 0, 'reader_capacity_tokenizations': 0,
                  'reader_forward_pair_validations': 0, 'NLI_forwards_attempted': 0}
    r.check_deadline = lambda: None
    r.tokenizer = TemplateOnlyTokenizer()
    return r


_INERT_READER = inert_reader()


def fake_tokenize(premise, claim):
    return _INERT_READER.tokenize(premise, claim)


def fake_capacity(claim):
    return _INERT_READER.hypothesis_pair_capacity(claim)


def synthetic_raw_rows():
    expected = []; labels = {}; rows = []
    units = units_from(['alpha ' * 50, 'beta ' * 60])
    windows = packing.pack_whole_source(units, 'claim', fake_tokenize, fake_capacity)
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
        windows = packing.pack_whole_source(units, 'claim', fake_tokenize, fake_capacity)
        self.assertEqual([i for w in windows for i in w['evidence']['selected_unit_ids']], list(range(4)))
        self.assertTrue(all(w['evidence']['pair_token_count'] <= 512 for w in windows))
        self.assertEqual(sum(w['evidence']['selected_source_characters'] for w in windows), sum(len(x['sentence']) for x in units))
        self.assertTrue(all(w['evidence']['full_source_numeric_partition_audit']['source_and_premise_occurrence_counts_match'] for w in windows))

    def test_single_overlong_unit_rejected_without_partial_output(self):
        with self.assertRaisesRegex(ValueError, 'WHOLE_SOURCE_SINGLE_UNIT_EXCEEDS_PAIR_CAP'):
            packing.pack_whole_source(units_from(['x' * 510]), 'claim', fake_tokenize, fake_capacity)

    def test_seventeenth_window_rejected(self):
        with self.assertRaisesRegex(ValueError, 'WHOLE_SOURCE_EXCEEDS_16_WINDOWS'):
            packing.pack_whole_source(units_from(['x' * 300] * 17), 'claim', fake_tokenize, fake_capacity)

    def test_pinned_wrapper_empty_second_is_single_and_capacity_scalar(self):
        module = ast.parse(FAST_SOURCE.read_text())
        method = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == '_encode_plus')
        assignment = next(n for n in ast.walk(method) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'batched_input' for t in n.targets))
        self.assertIsInstance(assignment.value, ast.IfExp)
        self.assertIsInstance(assignment.value.test, ast.Name)
        self.assertEqual(assignment.value.test.id, 'text_pair')
        r = inert_reader(); single = r.tokenizer('claim', '')
        self.assertEqual(set(single['token_type_ids']), {0})
        with self.assertRaisesRegex(ValueError, 'TOKENIZER_WHOLE_PAIR_CAPTURE'):
            reader.validate_encoding(single, pair=True)
        count = r.hypothesis_pair_capacity('claim')
        self.assertIs(type(count), int)
        self.assertEqual(count, len(single['input_ids']) + 1)
        pair = r.tokenize('source', 'claim')
        self.assertEqual(len(pair['input_ids']), count + len('source'))
        self.assertEqual(set(pair['token_type_ids']), {0, 1})
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_capacity_or_single_packet_never_reaches_forward(self):
        r = inert_reader()
        for value in [r.hypothesis_pair_capacity('claim'), r.tokenizer('claim'), {},
                      {'input_ids': [101, 11, 102], 'attention_mask': [1] * 3,
                       'token_type_ids': [0] * 3}]:
            with self.assertRaisesRegex(ValueError, 'TOKENIZER_WHOLE_PAIR_CAPTURE'):
                r.score(value)
        for empty in ['', '  ']:
            with self.assertRaisesRegex(ValueError, 'GENUINE_NONEMPTY'):
                r.tokenize(empty, 'claim')
        self.assertEqual(r.counters['reader_forward_pair_validations'], 0)
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_both_packers_never_tokenize_empty_source(self):
        r = inert_reader(); units = units_from(['First sentence. ', 'Pay 3 days unless except.'])
        packing.pack(units, 'claim', [1, 0], r.tokenize, r.hypothesis_pair_capacity)
        packing.pack_whole_source(units, 'claim', r.tokenize, r.hypothesis_pair_capacity)
        self.assertTrue(all(second is None or bool(second.strip()) for _, second, _ in r.tokenizer.calls))
        self.assertEqual(r.counters['reader_capacity_tokenizations'], 2)

    def test_original_template_and_backend_special_count_metadata(self):
        metadata = TemplateOnlyTokenizer()
        self.assertEqual(metadata.num_special_tokens_to_add(False), 2)
        self.assertEqual(metadata.num_special_tokens_to_add(True), 3)
        self.assertEqual(metadata.processor['special_tokens']['[CLS]']['ids'], [101])
        self.assertEqual(metadata.processor['special_tokens']['[SEP]']['ids'], [102])
        module = ast.parse(FAST_SOURCE.read_text())
        method = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)
                      and n.name == 'num_special_tokens_to_add')
        returned = next(n.value for n in method.body if isinstance(n, ast.Return))
        self.assertIsInstance(returned, ast.Call)
        self.assertEqual(returned.func.attr, 'num_special_tokens_to_add')
        self.assertEqual(returned.func.value.attr, '_tokenizer')
        self.assertEqual(returned.args[0].id, 'pair')

    def test_forward_revalidates_special_boundaries_and_segment_order(self):
        r = inert_reader(); good = r.tokenize('source', 'claim')
        bad = copy.deepcopy(good); bad['token_type_ids'][1] = 1
        with self.assertRaisesRegex(ValueError, 'PINNED_BERT_GENUINE_SOURCE_PAIR_SEGMENTS'):
            r.score(bad)
        bad = copy.deepcopy(good); bad['input_ids'][0] = 12
        with self.assertRaisesRegex(ValueError, 'PINNED_BERT_SPECIAL_TOKEN_BOUNDARIES'):
            r.score(bad)
        bad = copy.deepcopy(good); bad['attention_mask'][1] = True
        with self.assertRaisesRegex(ValueError, 'TOKENIZER_WHOLE_PAIR_CAPTURE'):
            r.score(bad)
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

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
