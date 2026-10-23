"""Pure rejection-boundary tests. All semantic receipts here are synthetic fixtures.

No fixture is a model/benchmark measurement. No source cases or choices are read.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import math
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('epoch20_data_builder_for_pure_tests', HERE / 'build.py')
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)


def fixture():
    state, tokenizer, plan, freeze = 'a' * 64, 'b' * 64, 'c' * 64, 'd' * 64
    examples = [('semantic-e-v1', 'The lamp is on.', 'Entailment', [4., -1., -2.]),
                ('semantic-c-v1', 'The lamp is not on.', 'Contradiction', [-2., -1., 4.]),
                ('semantic-n-v1', 'The box is blue.', 'NotMentioned', [-2., 4., -1.])]
    rows = []
    for identifier, premise, label, logits in examples:
        values = [math.exp(x - max(logits)) for x in logits]
        values = [x / sum(values) for x in values]
        rows.append({'fixture_id': identifier, 'expected_typed_label': label,
            'forward': {'premise': premise, 'hypothesis': 'The lamp is on.',
                'model_state_sha256': state, 'raw_logits': logits,
                'raw_probabilities': values,
                'typed_probabilities': {'Entailment': values[0], 'Contradiction': values[2],
                                        'NotMentioned': values[1]},
                'typed_prediction': label}})
    semantic = {'passed': True, 'correct': 3, 'n': 3, 'phase': 'dev',
        'source_freeze_sha256': freeze, 'fp32_state_sha256': state,
        'tokenizer_backend_sha256': tokenizer,
        'canary_forward_receipt_sha256': hashlib.sha256(B.canonical(rows).encode()).hexdigest()}
    raw = {'phase': 'dev', 'plan_sha256': plan, 'documents': [], 'errors': [],
        'canary_forwards': rows, 'semantic_readiness': copy.deepcopy(semantic),
        'fp32_state': {'state_sha256': state, 'all_floating_parameters_buffers_FP32': True,
                       'quantized_modules': 0, 'devices': ['cpu']},
        'FP32_state_after_canaries_sha256': state, 'tokenizer': {'backend_sha256': tokenizer},
        'counters': {'nli_forward_pairs_attempted': 3, 'nli_forward_pairs_completed': 3,
            'native_queries_completed': 3, 'native_index_initializations_completed': 1,
            'benchmark_documents_completed': 0, 'benchmark_questions_completed': 0,
            'BGE_initializations_attempted': 0, 'paid_API_calls': 0, 'GPU_calls': 0,
            'quantization_initializations': 0}}
    return raw, semantic, plan, freeze


def rebind(rows, semantic, raw):
    semantic['canary_forward_receipt_sha256'] = hashlib.sha256(B.canonical(rows).encode()).hexdigest()
    raw['semantic_readiness'] = copy.deepcopy(semantic)


class GuardTests(unittest.TestCase):
    def test_current_metadata_only_partition_and_fixed_draw(self):
        _, registry, selection, _, _ = B.verify_metadata(HERE.parents[3])
        self.assertEqual([len(registry[k]) for k in ('excluded_document_ids',
            'reserved_confirmation_document_ids', 'eligible_document_ids')], [221, 24, 178])
        self.assertEqual([r['document_id'] for r in selection['documents'] if r['role'] == 'dev'], B.DEV_IDS)

    def test_bool_document_identifier_is_not_integer(self):
        with self.assertRaises(ValueError): B.row_id('dev', True, 'nda-17')

    def test_unknown_hypothesis_is_rejected(self):
        with self.assertRaises(ValueError): B.row_id('dev', 470, 'nda-017')

    def test_absolute_and_parent_paths_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ['/etc/passwd', '../outside', 'a/../../outside', 'a\\b']:
                with self.subTest(name=name), self.assertRaises(ValueError): B.safe_target(Path(temp), name)

    def test_symlink_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'link').symlink_to(root / 'target')
            with self.assertRaises(ValueError): B.safe_target(root, 'link/file.json')

    def test_missing_freeze_cannot_open_original_corpus(self):
        original_reads = []
        old = B.read
        def guarded(path):
            if str(path).endswith('original-train.json'):
                original_reads.append(path); raise AssertionError('Original corpus should not be opened')
            return old(path)
        with patch.object(B, 'read', side_effect=guarded):
            with self.assertRaises((FileNotFoundError, PermissionError)):
                B.materialize_inputs(HERE.parents[3], 'dev', HERE / 'nonexistent-source-freeze.json', 'f' * 64)
        self.assertEqual(original_reads, [])

    def test_pure_synthetic_semantic_receipt_passes(self):
        raw, semantic, plan, freeze = fixture()
        B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_changed_literal_canary_rejected_even_rehashed(self):
        raw, semantic, plan, freeze = fixture()
        raw['canary_forwards'][2]['forward']['premise'] = 'The box is red.'
        rebind(raw['canary_forwards'], semantic, raw)
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_wrong_neutral_probability_mapping_rejected(self):
        raw, semantic, plan, freeze = fixture()
        f = raw['canary_forwards'][2]['forward']; f['typed_probabilities']['NotMentioned'], f['typed_probabilities']['Contradiction'] = f['typed_probabilities']['Contradiction'], f['typed_probabilities']['NotMentioned']
        rebind(raw['canary_forwards'], semantic, raw)
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_nan_raw_logit_rejected(self):
        raw, semantic, plan, freeze = fixture()
        raw['canary_forwards'][0]['forward']['raw_logits'][0] = float('nan')
        # Canonical serialization itself is a rejecting guard for NaN.
        with self.assertRaises(ValueError): rebind(raw['canary_forwards'], semantic, raw)

    def test_state_changed_after_canaries_rejected(self):
        raw, semantic, plan, freeze = fixture(); raw['FP32_state_after_canaries_sha256'] = 'e' * 64
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_stale_tokenizer_receipt_rejected(self):
        raw, semantic, plan, freeze = fixture(); raw['tokenizer']['backend_sha256'] = 'e' * 64
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_extra_forward_before_projection_rejected(self):
        raw, semantic, plan, freeze = fixture(); raw['counters']['nli_forward_pairs_completed'] = 4
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)

    def test_partial_legal_use_before_readiness_rejected(self):
        raw, semantic, plan, freeze = fixture(); raw['documents'] = [{'id': 'already-used'}]
        with self.assertRaises(PermissionError): B.replay_semantic_readiness(raw, semantic, 'dev', plan, freeze)


if __name__ == '__main__': unittest.main(verbosity=2)
