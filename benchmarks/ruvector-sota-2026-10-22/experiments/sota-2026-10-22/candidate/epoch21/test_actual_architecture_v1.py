"""Pure actual-versus-source config attribution faults; no neural imports."""
import copy
from types import SimpleNamespace
import unittest
import sys
import reader
from reader_actual_v1 import actual_architecture
from test_source_contract import config


def model_fixture():
    source = reader.validate_config(config())
    values = {k: copy.deepcopy(v) for k, v in source.items() if k != 'architecture'}
    values['id2label'] = {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}
    values['num_labels'] = 3
    values['torch_dtype'] = 'descriptive-loaded-config-dtype'
    model = type('DebertaV2ForSequenceClassification', (), {})()
    model.config = SimpleNamespace(**values)
    return model, source


class Provenance(unittest.TestCase):
    def test_actual_structure_comes_from_model_and_dtype_is_separate(self):
        model, source = model_fixture(); before = copy.deepcopy(source)
        result = actual_architecture(model, source)
        self.assertEqual(source, before)
        self.assertEqual(result['source_config_architecture']['torch_dtype'], 'float16')
        self.assertNotIn('torch_dtype', result['architecture'])
        self.assertEqual(result['actual_model_config_declared_dtype'], 'descriptive-loaded-config-dtype')
        self.assertEqual(result['architecture']['num_labels'], 3)

    def test_changed_actual_structure_or_boolean_alias_rejected(self):
        for key, value in [('hidden_size', 768), ('num_hidden_layers', 12), ('type_vocab_size', False),
                           ('relative_attention', False), ('pos_att_type', ['p2c'])]:
            model, source = model_fixture(); setattr(model.config, key, value)
            with self.assertRaises(ValueError): actual_architecture(model, source)

    def test_different_actual_class_rejected(self):
        model, source = model_fixture()
        other = SimpleNamespace(config=model.config)
        with self.assertRaises(ValueError): actual_architecture(other, source)

    def test_actual_class_labels_must_remain_original(self):
        for field, value in [('num_labels', 2), ('id2label', {'0':'neutral','1':'entailment','2':'contradiction'})]:
            model, source = model_fixture(); setattr(model.config, field, value)
            with self.assertRaises(ValueError): actual_architecture(model, source)

    def test_no_framework_imports(self):
        for name in ('torch', 'transformers', 'numpy', 'tokenizers', 'safetensors', 'onnxruntime'):
            self.assertNotIn(name, sys.modules)


if __name__ == '__main__': unittest.main()

