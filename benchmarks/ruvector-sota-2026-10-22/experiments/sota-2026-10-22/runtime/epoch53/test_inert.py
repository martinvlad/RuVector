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


def synthetic_bank(parts):
    """Invented four-document source/claims; no real benchmark text or labels."""
    archive = '0' * 64; docs = []; cases = []
    claims = [('nda-1', 'claim'), ('nda-10', 'some longer frozen claim'),
              ('nda-16', 'frozen hypothesis with additional words')]
    for ordinal, did in enumerate([901, 902, 903, 904]):
        units = units_from(parts); text = ''.join(parts)
        docs.append(dict(document_id=did, record_ordinal=ordinal,
            source_group_sha256=packing.digest('ContractNLI|' + archive + '|dev|' + str(did)),
            source_document_sha256=packing.digest(text),
            normalized_document_sha256=packing.digest(' '.join(text.casefold().split())),
            source_filename_key_sha256=packing.digest('invented-' + str(did)), evidence=units))
        for hid, claim in claims:
            cases.append(dict(id='invented-' + str(did) + '-' + hid, document_id=did,
                              hypothesis_id=hid, claim=claim,
                              input_sha256=hashlib.sha256(packing.canonical(dict(claim=claim, document=text))).hexdigest()))
    return dict(schema_version=1, epoch=53, kind=packing.KIND, role='dev',
                source_archive_sha256=archive, documents=docs, cases=cases)


def inert_catalog(parts):
    bank = synthetic_bank(parts); r = inert_reader(); r.set_tokenization_stage('fragmentation')
    audit = {}; out = packing.build_fragment_catalog(bank, r.tokenize, lambda: None, audit)
    packing.validate_features(out, 'dev', [901,902,903,904], [c['id'] for c in out['cases']], '0' * 64)
    return bank, out, audit, r


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
    def test_very_long_invented_unit_bounded_proposals_cost_and_utf8_numeric_integrity(self):
        text = ('café $12.50 USD; ' * 2000)[:30000]
        self.assertEqual(len(text), 30000)
        self.assertGreater(len(text.encode('utf-8')), len(text))
        bank, out, audit, r = inert_catalog([text])
        self.assertLessEqual(r.counters['reader_fragmentation_pair_tokenizations'], 12000)
        self.assertEqual(r.counters['reader_fragmentation_pair_tokenizations'],
                         r.counters['reader_fragmentation_pair_tokenizations_completed'])
        self.assertEqual(audit['proposal_search_horizon_codepoints'], 1024)
        self.assertEqual(audit['max_endpoint_proposals_per_fragment'], 16)
        for d, doc in zip(audit['documents'], out['documents']):
            self.assertEqual(''.join(u['sentence'] for u in doc['evidence']).encode('utf-8'), text.encode('utf-8'))
            for f in d['fragments']:
                self.assertFalse(any(p['start'] < at < p['end'] for p in d['protected_occurrence_ranges']
                                     for at in (f['start'],f['end'])))
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_fragment_catalog_oversized_first_and_middle_source_units(self):
        for parts in [['word ' * 140, 'Then end. '],
                      ['First short. ', 'middle word ' * 100, 'Last short. ']]:
            bank, out, audit, r = inert_catalog(parts)
            self.assertTrue(audit['complete'])
            self.assertTrue(any(g['over_capacity'] for g in audit['documents'][0]['coalesced_groups']))
            self.assertGreater(len(out['documents'][0]['evidence']), len(parts))
            self.assertEqual(''.join(u['sentence'] for u in out['documents'][0]['evidence']), ''.join(parts))
            self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_fragment_catalog_whitespace_only_parent_prefix_middle_tail(self):
        parts = [' \n ', 'Content one; ', ' \t ', 'Content two. ', ' \n']
        bank, out, audit, r = inert_catalog(parts)
        for doc in out['documents']:
            self.assertEqual(''.join(u['sentence'] for u in doc['evidence']), ''.join(parts))
            self.assertTrue(all(u['sentence'].strip() for u in doc['evidence']))
        self.assertTrue(audit['documents'][0]['coalesced_boundary_offsets'])

    def test_fragment_catalog_coalesces_cross_parent_numeric_and_negation_occurrences(self):
        parts = ['Pay 5', ' days; $12,', '345.50 USD; ne', 'ver release unless permitted. ']
        _, out, audit, _ = inert_catalog(parts)
        self.assertEqual(len(audit['documents'][0]['coalesced_groups']), 1)
        self.assertEqual(len(out['documents'][0]['evidence']), 1)
        self.assertTrue(audit['documents'][0]['numeric_date_currency_negation_partition_audit']['source_and_premise_occurrence_counts_match'])
        self.assertEqual(out['documents'][0]['evidence'][0]['sentence'], ''.join(parts))

    def test_fragment_catalog_coalesces_unsafe_original_unicode_boundaries(self):
        parts = ['A;', '\u0301 B;', '\u200dC; end.']
        _, out, audit, _ = inert_catalog(parts)
        self.assertEqual(audit['documents'][0]['coalesced_boundary_offsets'], [2, 6])
        self.assertEqual(len(out['documents'][0]['evidence']), 1)

    def test_fragment_catalog_longest_of_all_three_claims_controls_capacity(self):
        _, _, audit, _ = inert_catalog(['word ' * 100])
        group = audit['documents'][0]['coalesced_groups'][0]
        self.assertLessEqual(group['original_pair_token_counts']['nda-1'], 512)
        self.assertGreater(group['original_pair_token_counts']['nda-16'], 512)
        self.assertGreater(len(group['fragment_ids']), 1)
        self.assertTrue(all(max(f['checked_pair_token_counts'].values()) <= 512
                            for d in audit['documents'] for f in d['fragments']))

    def test_fragment_catalog_preserves_fitting_unit_and_all_four_arm_inputs(self):
        parts = ['First short. ', 'word ' * 130, 'Pay 30 days unless permitted. ']
        bank, out, audit, r = inert_catalog(parts)
        self.assertEqual(out['documents'][0]['evidence'][0]['sentence'], parts[0])
        self.assertEqual(audit['documents'][0]['coalesced_groups'][0]['fragmented'], False)
        r.set_tokenization_stage('packing')
        for doc in out['documents']:
            units = doc['evidence']; claim = next(c['claim'] for c in bank['cases'] if c['document_id'] == doc['document_id'])
            # Invented native ranking permutation is an integration fixture, not RuVector execution.
            for order in [list(reversed(range(len(units)))), packing.bm25_order(units, claim), list(range(len(units)))]:
                tokens, evidence = packing.pack(units, claim, order, r.tokenize, r.hypothesis_pair_capacity)
                self.assertLessEqual(len(tokens['input_ids']), 512)
            windows = packing.pack_whole_source(units, claim, r.tokenize, r.hypothesis_pair_capacity)
            self.assertEqual([i for w in windows for i in w['evidence']['selected_unit_ids']], list(range(len(units))))
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_fragment_catalog_protected_atom_rejects_without_partial_prediction(self):
        bank = synthetic_bank(['Pay ' + '1' * 600 + ' USD now.'])
        r = inert_reader(); r.set_tokenization_stage('fragmentation'); audit = {}
        with self.assertRaisesRegex(ValueError, 'GREEDY_SOURCE_FRAGMENT_PARTITION_FAILED_NO_FALLBACK'):
            packing.build_fragment_catalog(bank, r.tokenize, lambda: None, audit)
        self.assertFalse(audit['complete'])
        self.assertEqual(r.counters['NLI_forwards_attempted'], 0)

    def test_fragment_catalog_greedy_failure_not_global_impossibility(self):
        bank = synthetic_bank(['a b c d ']); audit = {}
        def nonmonotonic(premise, claim):
            count = {'a b c ': 510, 'a b ': 510, 'c d ': 510}.get(premise, 999)
            return dict(input_ids=[11] * count)  # Invented scalar-length oracle fixture only.
        with self.assertRaisesRegex(ValueError, 'GREEDY_SOURCE_FRAGMENT_PARTITION_FAILED_NO_FALLBACK'):
            packing.build_fragment_catalog(bank, nonmonotonic, lambda: None, audit)
        self.assertEqual(len(nonmonotonic('a b ', 'claim')['input_ids']), 510)
        self.assertEqual(len(nonmonotonic('c d ', 'claim')['input_ids']), 510)
        self.assertFalse(audit['complete'])

    def test_actual_pair_tokenization_stage_budgets_deny_before_tokenizer_call(self):
        r = inert_reader(); r.set_tokenization_stage('fragmentation')
        r.counters['reader_fragmentation_pair_tokenizations'] = 12000
        with self.assertRaisesRegex(ValueError, 'FROZEN_STAGE_PAIR_TOKENIZATION_CAP'):
            r.tokenize('source', 'claim')
        self.assertEqual(r.tokenizer.calls, [])
        r.set_tokenization_stage('packing'); r.counters['reader_packing_pair_tokenizations'] = 24000
        with self.assertRaisesRegex(ValueError, 'FROZEN_STAGE_PAIR_TOKENIZATION_CAP'):
            r.tokenize('source', 'claim')
        self.assertEqual(r.tokenizer.calls, [])

    def test_public_fragment_metadata_replay_detects_offset_or_capacity_tampering(self):
        _, _, catalog, r = inert_catalog(['Pay 30 days; ', 'word ' * 120])
        receipt = dict(catalog_complete_before_BGE_native_and_NLI=True,
                       original_source_unchanged=True, all_three_hypotheses_prevalidated=True,
                       same_fragment_catalog_all_four_arms=True, elapsed_seconds=.1,
                       fragment_pair_tokenizations=r.counters['reader_fragmentation_pair_tokenizations'],
                       fragment_pair_tokenizations_completed=r.counters['reader_fragmentation_pair_tokenizations_completed'])
        work = dict.fromkeys(('NLI_forwards_attempted','BGE_initializations_attempted',
                              'BGE_forward_calls_attempted','native_corpus_batches_attempted'),0)
        receipt['before_catalog_work_counters'] = dict(work)
        receipt['after_catalog_work_counters'] = dict(work)
        counters = dict(r.counters, native_insertions_attempted=catalog['fragment_count'],
                        native_insertions_completed=catalog['fragment_count'],
                        native_hit_source_validations=catalog['fragment_count'] * 3)
        raw = dict(fragment_catalog_audit=catalog, fragmentation_receipt=receipt, counters=counters,
                   native_result=dict(documents=[dict(document_id=d['document_id'], initialized_vectors=d['fragment_count'])
                                                 for d in catalog['documents']]), rows=[])
        self.assertTrue(evaluate.validate_fragment_catalog_receipt(raw))
        bad = copy.deepcopy(raw); bad['fragment_catalog_audit']['documents'][0]['fragments'][0]['end'] -= 1
        with self.assertRaises(AssertionError): evaluate.validate_fragment_catalog_receipt(bad)
        bad = copy.deepcopy(raw); bad['fragment_catalog_audit']['documents'][0]['fragments'][0]['checked_pair_token_counts']['nda-1'] = 513
        with self.assertRaises(AssertionError): evaluate.validate_fragment_catalog_receipt(bad)

    def test_worker_order_shared_catalog_precedes_embeddings_native_and_all_forwards(self):
        module = ast.parse((HERE/'worker.py').read_bytes())
        main = next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name == 'main')
        calls = list(n for n in ast.walk(main) if isinstance(n,ast.Call))
        def at(name):
            return min(n.lineno for n in calls if (isinstance(n.func,ast.Name) and n.func.id == name)
                       or (isinstance(n.func,ast.Attribute) and n.func.attr == name))
        self.assertLess(at('Reader'), at('build_fragment_catalog'))
        self.assertLess(at('build_fragment_catalog'), at('embed_documents'))
        self.assertLess(at('embed_documents'), at('run_native'))
        self.assertLess(at('pack_whole_source'), at('score'))
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

    def test_twenty_fifth_window_rejected(self):
        with self.assertRaisesRegex(ValueError, 'WHOLE_SOURCE_EXCEEDS_24_WINDOWS'):
            packing.pack_whole_source(units_from(['x' * 300] * 25), 'claim', fake_tokenize, fake_capacity)

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
