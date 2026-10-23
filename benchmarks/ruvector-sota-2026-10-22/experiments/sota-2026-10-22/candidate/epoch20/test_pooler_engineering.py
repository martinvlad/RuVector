"""Pure pooler-compatibility faults plus inherited generic protocol tests."""
import copy
import unittest
import test_engineering as Old
import reader_pooler_v1 as reader
import worker_pooler_v1
import launch_pooler_v1


def loading():
    return {'missing_keys': [], 'mismatched_keys': [], 'error_msgs': [],
            'unexpected_keys': list(reader.UNUSED_POOLER_KEYS)}


def source():
    return {'roberta.pooler.dense.bias': {'shape': [1024], 'dtype': 'torch.float32', 'elements': 1024},
            'roberta.pooler.dense.weight': {'shape': [1024, 1024], 'dtype': 'torch.float32', 'elements': 1048576}}


class PoolerEngineering(Old.Engineering):
    def test_exact_unused_pooler_loading_and_raw_list_preserved(self):
        value = loading(); before = copy.deepcopy(value)
        policy = reader.validate_loading_info(value)
        self.assertEqual(value, before)
        self.assertEqual(policy['allowed_unexpected_keys'], list(reader.UNUSED_POOLER_KEYS))
        self.assertFalse(policy['head_reinitialization_allowed'])
        self.assertFalse(policy['stock_classification_forward_uses_pooler'])

    def test_any_missing_mismatch_or_load_error_refused(self):
        for key in ('missing_keys', 'mismatched_keys', 'error_msgs'):
            value = loading(); value[key] = ['classifier.out_proj.weight']
            with self.assertRaises(ValueError): reader.validate_loading_info(value)
            value = loading(); del value[key]
            with self.assertRaises(ValueError): reader.validate_loading_info(value)

    def test_extra_learned_unexpected_duplicate_or_absent_pooler_refused(self):
        for unexpected in ([], [reader.UNUSED_POOLER_KEYS[0]],
                [reader.UNUSED_POOLER_KEYS[0]] * 2,
                list(reader.UNUSED_POOLER_KEYS) + ['classifier.dense.weight'],
                [reader.UNUSED_POOLER_KEYS[0], 'roberta.encoder.layer.0.attention.self.query.weight']):
            value = loading(); value['unexpected_keys'] = unexpected
            with self.assertRaises(ValueError): reader.validate_loading_info(value)

    def test_exact_original_fp32_pooler_inventory(self):
        value = source()
        self.assertEqual(reader.validate_source_inventory(395, 356412419,
            {'torch.float32': 356412419}, value), value)

    def test_wrong_original_counts_dtypes_or_pooler_shapes_refused(self):
        for n, elements, dtypes in [(394, 356412419, {'torch.float32': 356412419}),
                (395, 355362819, {'torch.float32': 355362819}),
                (395, 356412419, {'torch.float16': 356412419})]:
            with self.assertRaises(ValueError): reader.validate_source_inventory(n, elements, dtypes, source())
        for key, field, value in [('roberta.pooler.dense.weight', 'shape', [1024, 3]),
                ('roberta.pooler.dense.bias', 'dtype', 'torch.float16'),
                ('roberta.pooler.dense.bias', 'elements', 0)]:
            wrong = source(); wrong[key][field] = value
            with self.assertRaises(ValueError): reader.validate_source_inventory(395, 356412419, {'torch.float32': 356412419}, wrong)

    def test_exact_active_classification_parameter_inventory(self):
        reader.validate_classification_inventory(393, 355362819, False, [1024, 1024], [3, 1024])
        for count, elements, pooler, dense, out in [(395, 356412419, True, [1024, 1024], [3, 1024]),
                (393, 355362818, False, [1024, 1024], [3, 1024]),
                (392, 355362819, False, [1024, 1024], [3, 1024]),
                (393, 355362819, False, [1024, 1024], [2, 1024])]:
            with self.assertRaises(ValueError): reader.validate_classification_inventory(count, elements, pooler, dense, out)


if __name__ == '__main__': unittest.main()
