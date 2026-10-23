"""Pure source/config/feed corruption tests; no runtime model or tokenizer imports."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import common as C
import checkpoint as K
import reader


def synthetic_header():
    shapes = copy.deepcopy(K.HEAD_SHAPES)
    shapes['deberta.synthetic.filler'] = [K.FLOAT_ELEMENTS - sum(__import__('math').prod(s) for s in shapes.values())]
    tensors = {}; offset = 0
    for name, shape in sorted(shapes.items()):
        end = offset + __import__('math').prod(shape) * 2
        tensors[name] = {'dtype': 'F16', 'shape': shape, 'data_offsets': [offset, end]}; offset = end
    tensors[K.POSITION_KEY] = {'dtype': 'I64', 'shape': [1, 512], 'data_offsets': [offset, offset + 4096]}
    return tensors, offset + 4096


def pair():
    return [1, 101, 102, 2, 201, 202, 2], [1] * 7, [0, 0, 0, 0, 1, 1, 1], [None, 0, 0, None, 1, 1, None]


def config():
    return {'model_type': 'deberta-v2', 'num_hidden_layers': 24, 'hidden_size': 1024,
        'num_attention_heads': 16, 'max_position_embeddings': 512, 'vocab_size': 128100,
        'type_vocab_size': 0, 'relative_attention': True, 'position_biased_input': False,
        'pooler_hidden_size': 1024, 'pooler_hidden_act': 'gelu', 'torch_dtype': 'float16',
        'pos_att_type': ['p2c', 'c2p'],
        'id2label': {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}}


class SourceContract(unittest.TestCase):
    def test_no_model_runtime_imports(self):
        for key in ('torch', 'transformers', 'tokenizers', 'numpy', 'safetensors', 'onnxruntime'):
            self.assertNotIn(key, sys.modules)

    def test_complete_synthetic_inventory_is_metadata_only(self):
        header, size = synthetic_header(); got = K.validate_header(header, size)
        self.assertEqual(got['source_dtype_element_counts'], {'F16': K.FLOAT_ELEMENTS, 'I64': 512})
        self.assertEqual(got['source_parameter_names'], sorted(set(header) - {K.POSITION_KEY}))

    def test_header_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"same":1,"same":2}', object_pairs_hook=K.no_duplicates)

    def test_wrong_head_shape_rejected_even_if_offsets_cover(self):
        header, size = synthetic_header(); header['classifier.weight']['shape'] = [1, 3072]
        with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_missing_position_buffer_rejected(self):
        header, size = synthetic_header(); del header[K.POSITION_KEY]
        with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_nonlearned_exception_cannot_hide_learned_tensor(self):
        header, size = synthetic_header(); header['classifier.bias']['dtype'] = 'I64'
        with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_extra_integer_buffer_rejected(self):
        header, size = synthetic_header(); header['other.position_ids'] = dict(header[K.POSITION_KEY])
        with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_float_storage_transformation_rejected(self):
        header, size = synthetic_header(); header['classifier.bias']['dtype'] = 'F32'
        with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_overlap_gap_and_trailing_payload_rejected(self):
        for kind in ('overlap', 'gap', 'trailing'):
            header, size = synthetic_header()
            if kind == 'overlap': header[K.POSITION_KEY]['data_offsets'][0] -= 2
            if kind == 'gap': header[K.POSITION_KEY]['data_offsets'][0] += 2
            if kind == 'trailing': size += 1
            with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_boolean_dimension_or_offset_rejected(self):
        for field in ('shape', 'data_offsets'):
            header, size = synthetic_header(); header['classifier.bias'][field][0] = True
            with self.assertRaises(ValueError): K.validate_header(header, size)

    def test_frozen_header_cannot_change(self):
        header, size = synthetic_header(); frozen = K.validate_header(header, size)
        self.assertTrue(K.compare_frozen_header(frozen, copy.deepcopy(frozen)))
        changed = copy.deepcopy(frozen); changed['source_parameter_names'].pop()
        with self.assertRaises(ValueError): K.compare_frozen_header(changed, frozen)

    def test_all_four_loading_lists_must_be_empty(self):
        clean = {k: [] for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')}
        self.assertFalse(K.validate_loading_info(clean)['head_reinitialization_allowed'])
        for key in clean:
            changed = copy.deepcopy(clean); changed[key] = ['classifier.weight']
            with self.assertRaises(ValueError): K.validate_loading_info(changed)
        for key in clean:
            changed = copy.deepcopy(clean); del changed[key]
            with self.assertRaises(ValueError): K.validate_loading_info(changed)

    def test_every_parameter_value_equality_and_complete_keyset_required(self):
        header, size = synthetic_header(); source = K.validate_header(header, size)
        rows = [{'name': name, 'source_dtype': 'F16', 'source_shape': header[name]['shape'],
                 'elements': __import__('math').prod(header[name]['shape']), 'loaded_dtype': 'torch.float32',
                 'loaded_device': 'cpu', 'equal_after_FP32_conversion': True}
                for name in source['source_parameter_names']]
        self.assertEqual(K.validate_parameter_rows(rows, source)['compared_elements'], K.FLOAT_ELEMENTS)
        for kind in ('missing', 'duplicate', 'reorder', 'unequal', 'wrongdtype', 'wrongdevice', 'wrongshape', 'nondict'):
            bad = copy.deepcopy(rows)
            if kind == 'missing': bad.pop()
            if kind == 'duplicate': bad[1] = copy.deepcopy(bad[0])
            if kind == 'reorder': bad.reverse()
            if kind == 'unequal': bad[0]['equal_after_FP32_conversion'] = False
            if kind == 'wrongdtype': bad[0]['loaded_dtype'] = 'torch.float16'
            if kind == 'wrongdevice': bad[0]['loaded_device'] = 'cuda'
            if kind == 'wrongshape': bad[0]['source_shape'] = [1]
            if kind == 'nondict': bad[0] = None
            with self.assertRaises(ValueError): K.validate_parameter_rows(bad, source)

    def test_official_architecture_and_raw_labels_required(self):
        self.assertEqual(reader.validate_config(config())['architecture'], 'DebertaV2ForSequenceClassification')
        for key, value in [('id2label', {'0': 'neutral', '1': 'entailment', '2': 'contradiction'}),
                           ('model_type', 'roberta'), ('type_vocab_size', 2), ('type_vocab_size', False),
                           ('torch_dtype', 'float32'), ('position_biased_input', True)]:
            changed = config(); changed[key] = value
            with self.assertRaises(ValueError): reader.validate_config(changed)

    def test_official_pair_segments_and_mask(self):
        reader.validate_pair(*pair())

    def test_pair_clipping_padding_segments_and_boolean_aliases_rejected(self):
        for kind in ('CLS', 'SEP', 'mask', 'segments', 'maskbool', 'idbool', 'seqbool', 'length', 'missingboundary'):
            ids, mask, segments, seq = pair()
            if kind == 'CLS': ids[0] = 0
            if kind == 'SEP': ids[-1] = 0
            if kind == 'mask': mask[1] = 0
            if kind == 'segments': segments[3] = 1
            if kind == 'maskbool': mask[1] = True
            if kind == 'idbool': ids[1] = True
            if kind == 'seqbool': seq[1] = False
            if kind == 'length': ids = [1] + [9] * 511 + [2]; mask = [1] * 513; segments = [0] * 513; seq = [None] * 513
            if kind == 'missingboundary': seq[3] = 0
            with self.assertRaises(ValueError): reader.validate_pair(ids, mask, segments, seq)

    def test_literal_source_special_token_does_not_use_naive_SEP_count(self):
        ids, mask, segments, seq = pair(); ids[1] = 2
        reader.validate_pair(ids, mask, segments, seq)

    def test_backend_output_is_owned_phase_and_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            study = Path(tmp) / 'study'; folder = study / 'runs/dev'; folder.mkdir(parents=True)
            text = '{"original":"operational-source-json"}'
            with patch.object(C, 'STUDY', study), patch.object(C, 'ROOT', Path(tmp)):
                row = reader.write_backend(folder, text)
                self.assertEqual(row['actual_backend_json_sha256'], hashlib.sha256(text.encode()).hexdigest())
                self.assertEqual((folder/'tokenizer-backend.json').read_text(), text)
                with self.assertRaises(FileExistsError): reader.write_backend(folder, text)
                with self.assertRaises(ValueError): reader.write_backend(study/'other', text)


if __name__ == '__main__': unittest.main()

