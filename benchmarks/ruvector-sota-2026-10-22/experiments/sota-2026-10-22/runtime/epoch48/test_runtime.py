"""Invented metadata/packing/state-validation fixtures; no actual models or benchmark labels."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packing
import reader


def fake_tokens(premise, claim):
    count = len(premise.split()) + len(claim.split()) + 4
    return {'input_ids': list(range(count)), 'attention_mask': [1] * count}


class FakeTensor:
    def __init__(self, shape, dtype='float32', values=None, finite=True):
        self.shape = shape; self.dtype = dtype; self.values = values; self.finite = finite
    def is_floating_point(self):
        return self.dtype == 'float32'
    def unsqueeze(self, axis):
        return FakeTensor((1, *self.shape), self.dtype, self.values, self.finite)


class FakeTruth:
    def __init__(self, value): self.value = value
    def all(self): return self.value


class FakeTorch:
    Tensor = FakeTensor
    int64 = 'int64'
    @staticmethod
    def arange(size, dtype): return FakeTensor((size,), dtype, tuple(range(size)))
    @staticmethod
    def equal(a, b): return a.shape == b.shape and a.dtype == b.dtype and a.values == b.values
    @staticmethod
    def isfinite(a): return FakeTruth(a.finite)


def fake_state():
    return {k: FakeTensor(shape) for k, shape in [
        ('roberta.embeddings.word_embeddings.weight', (50265, 1024)),
        ('classifier.dense.weight', (1024, 1024)), ('classifier.dense.bias', (1024,)),
        ('classifier.out_proj.weight', (3, 1024)), ('classifier.out_proj.bias', (3,))]}


class RuntimeTests(unittest.TestCase):
    def test_pack_skips_oversized_whole_unit_keeps_claim_and_source_order(self):
        texts = ['x ' * 510, 'USD 10 must not be disclosed.\n', 'After 30 days.\n']
        units = []; end = 0
        for i, text in enumerate(texts):
            units.append({'unit_id': i, 'start': end, 'end': end + len(text), 'sentence': text})
            end += len(text)
        tokens, facts = packing.pack(units, 'The duty lasts 30 days.', [0, 2, 1], fake_tokens)
        self.assertEqual(facts['selected_unit_ids'], [1, 2])
        self.assertFalse(facts['packing_proposals'][0]['accepted'])
        self.assertEqual(facts['claim_sha256'], packing.digest('The duty lasts 30 days.'))
        self.assertEqual(facts['premise_sha256'], packing.digest(texts[1] + '\n\n' + texts[2]))
        self.assertLessEqual(len(tokens['input_ids']), 512)
        self.assertTrue(facts['numeric_date_currency_negation_audit']['source_and_premise_occurrence_counts_match'])

    def test_no_evidence_is_failure_not_neutral(self):
        units = [{'unit_id': 0, 'start': 0, 'end': 1200, 'sentence': 'x ' * 600}]
        with self.assertRaisesRegex(ValueError, 'NO_WHOLE_SOURCE_UNIT_FITS'):
            packing.pack(units, 'Whole claim.', [0], fake_tokens)

    def test_rank_duplicate_and_overlap_rejected(self):
        units = [{'unit_id': 0, 'start': 0, 'end': 5, 'sentence': 'first'},
                 {'unit_id': 1, 'start': 4, 'end': 10, 'sentence': 'second'}]
        with self.assertRaisesRegex(ValueError, 'PERMUTATION'):
            packing.pack(units, 'claim', [0, 0], fake_tokens)
        with self.assertRaisesRegex(ValueError, 'OVERLAP'):
            packing.pack(units, 'claim', [0, 1], fake_tokens)

    def test_maximum_four_units_fixed_bm25_ties(self):
        units = [{'unit_id': i, 'start': i * 5, 'end': i * 5 + 5, 'sentence': 'same.'}
                 for i in range(7)]
        self.assertEqual(packing.bm25_order(units, 'missing'), list(range(7)))
        _, evidence = packing.pack(units, 'claim', list(range(7)), fake_tokens)
        self.assertEqual(evidence['selected_unit_ids'], [0, 1, 2, 3])

    def test_exact_legacy_buffer_only_and_learned_state_strict(self):
        expected = fake_state(); state = dict(expected)
        state['roberta.embeddings.position_ids'] = FakeTorch.arange(514, 'int64').unsqueeze(0)
        clean, audit = reader.strict_state(state, expected, FakeTorch)
        self.assertEqual(set(clean), set(expected))
        self.assertEqual(audit['removed_validated_nonlearned_legacy_buffers'],
                         ['roberta.embeddings.position_ids'])
        for edit in ['missing', 'extra', 'head_shape', 'nonfinite', 'bad_buffer']:
            state = dict(expected)
            if edit == 'missing': del state['classifier.out_proj.weight']
            if edit == 'extra': state['arbitrary.unexpected'] = FakeTensor((1,))
            if edit == 'head_shape': state['classifier.out_proj.weight'] = FakeTensor((2, 1024))
            if edit == 'nonfinite': state['classifier.out_proj.bias'] = FakeTensor((3,), finite=False)
            if edit == 'bad_buffer':
                state['roberta.embeddings.position_ids'] = FakeTensor((1, 514), 'int64', (99,))
            with self.assertRaises(ValueError, msg=edit): reader.strict_state(state, expected, FakeTorch)

    def test_typed_mapping_stable_extreme_log_scores_no_epsilon(self):
        value = reader.stable_scores([1000.0, -1000.0, 999.0])
        self.assertEqual(value['prediction'], 'Entailment')
        self.assertEqual(value['logits'], [1000.0, 999.0, -1000.0])
        self.assertAlmostEqual(sum(value['probabilities']), 1.0)
        self.assertLess(value['log_probabilities'][2], -1999)
        self.assertEqual(value['probabilities'][2], 0.0)
        self.assertTrue(all(__import__('math').isfinite(x) for x in value['log_probabilities']))

    def test_no_unrestricted_load_or_import_time_model(self):
        tree = ast.parse((HERE / 'reader.py').read_text())
        loads = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'load'
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == 'torch']
        self.assertEqual(len(loads), 1)
        keywords = {k.arg: ast.literal_eval(k.value) for k in loads[0].keywords}
        self.assertEqual(keywords, {'map_location': 'cpu', 'weights_only': True, 'mmap': False})
        self.assertFalse(any(isinstance(n, ast.Import) and any(a.name == 'torch' for a in n.names)
                             for n in tree.body))

    def test_feature_bank_hashes_and_no_choice_keys(self):
        archive = 'a' * 64; docs = []; cases = []; ids = []; docids = [901, 902, 903, 904]
        for docid in docids:
            text = 'Invented company must not disclose USD 10.\n'
            docs.append({'document_id': docid, 'record_ordinal': docid,
                'source_group_sha256': packing.digest('ContractNLI|' + archive + '|dev|' + str(docid)),
                'source_document_sha256': packing.digest(text),
                'normalized_document_sha256': packing.digest(' '.join(text.casefold().split())),
                'source_filename_key_sha256': 'b' * 64,
                'evidence': [{'unit_id': 0, 'start': 0, 'end': len(text), 'sentence': text}]})
            for hyp in ['nda-1', 'nda-10', 'nda-16']:
                ident = str(docid) + ':' + hyp; ids.append(ident); claim = 'An invented full claim.'
                cases.append({'id': ident, 'document_id': docid, 'hypothesis_id': hyp, 'claim': claim,
                    'input_sha256': hashlib.sha256(packing.canonical({'claim': claim,
                                                                     'document': text})).hexdigest()})
        bank = {'schema_version': 1, 'epoch': 48, 'kind': packing.KIND, 'role': 'dev',
                'source_archive_sha256': archive, 'documents': docs, 'cases': cases}
        self.assertEqual(len(packing.validate_features(bank, 'dev', docids, ids, archive)), 4)
        bad = copy.deepcopy(bank); bad['cases'][0]['choice'] = 'secret'
        with self.assertRaisesRegex(ValueError, 'FEATURE_CASE_KEYS'):
            packing.validate_features(bad, 'dev', docids, ids, archive)
        bad = copy.deepcopy(bank); bad['documents'][0]['evidence'][0]['sentence'] = 'changed'
        with self.assertRaises(ValueError): packing.validate_features(bad, 'dev', docids, ids, archive)


if __name__ == '__main__':
    unittest.main()
