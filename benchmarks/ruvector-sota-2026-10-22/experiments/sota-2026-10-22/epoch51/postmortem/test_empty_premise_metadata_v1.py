"""Source/JSON metadata regression only. Never imports or instantiates tokenizers."""
import ast
import json
from pathlib import Path
import unittest

FAST_SOURCE = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv/lib/python3.12/site-packages/transformers/tokenization_utils_fast.py')
TOKENIZER_JSON = Path('/dev/shm/ruvector-e51-data/assets/contractnli-bert-nda-standard-ac92b6b512d7/tokenizer.json')


def template_type_ids(processor, template_name, synthetic_A, synthetic_B):
    """Interpret only documented JSON type-id metadata on invented token sequences."""
    result = []
    for entry in processor[template_name]:
        if 'SpecialToken' in entry:
            item = entry['SpecialToken']
            result.extend([item['type_id']] * len(processor['special_tokens'][item['id']]['ids']))
        else:
            item = entry['Sequence']
            result.extend([item['type_id']] * len(synthetic_A if item['id'] == 'A' else synthetic_B))
    return result


def future_capacity_only_types_valid(types):
    return bool(types) and all(type(t) is int and t == 0 for t in types)


def future_genuine_pair_types_valid(types):
    return bool(types) and all(type(t) is int and t in (0, 1) for t in types) and 0 in types and 1 in types


class SourceMetadataRegression(unittest.TestCase):
    def setUp(self):
        self.source = FAST_SOURCE.read_text()
        self.processor = json.loads(TOKENIZER_JSON.read_text())['post_processor']

    def test_pinned_fast_single_encode_routes_empty_second_by_truthiness(self):
        module = ast.parse(self.source)
        method = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == '_encode_plus')
        assignment = next(n for n in ast.walk(method) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'batched_input' for t in n.targets))
        self.assertIsInstance(assignment.value, ast.IfExp)
        self.assertIsInstance(assignment.value.test, ast.Name)
        self.assertEqual(assignment.value.test.id, 'text_pair')
        self.assertFalse(bool(''))

    def test_empty_baseline_single_template_has_no_type_one(self):
        types = template_type_ids(self.processor, 'single', [11, 12], [])
        self.assertEqual(types, [0, 0, 0, 0])
        self.assertFalse(0 in types and 1 in types)  # Frozen E51 guard necessarily fails.
        self.assertTrue(future_capacity_only_types_valid(types))

    def test_genuine_nonempty_pair_keeps_true_bert_segment_ids(self):
        types = template_type_ids(self.processor, 'pair', [11, 12], [13])
        self.assertEqual(types, [0, 0, 0, 0, 1, 1])
        self.assertTrue(future_genuine_pair_types_valid(types))
        self.assertFalse(future_capacity_only_types_valid(types))
        self.assertFalse(future_genuine_pair_types_valid([0, 0, 0]))

    def test_explicit_type_id_return_key_is_present_in_conversion_source(self):
        self.assertIn('if return_token_type_ids:\n                encoding_dict["token_type_ids"].append(e.type_ids)', self.source)


if __name__ == '__main__':
    unittest.main()
