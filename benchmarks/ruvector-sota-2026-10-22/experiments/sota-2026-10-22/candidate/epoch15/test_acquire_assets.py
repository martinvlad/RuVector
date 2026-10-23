"""Import/spec boundary tests only; no downloads or model execution."""
import copy
import importlib.util
from pathlib import Path
import unittest
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch15_asset_engineering', HERE / 'acquire_assets.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


class AssetTests(unittest.TestCase):
    def test_actual_import_and_seven_selected_members(self):
        value = A.load_spec()
        A.validate_spec(value)
        self.assertEqual(len(value['assets']), 7)
        self.assertIn('onnx/model_quint8_avx2.onnx', A.MEMBERS)

    def test_other_revision_rejected(self):
        value = copy.deepcopy(A.load_spec())
        value['revision'] = '0' * 40
        with self.assertRaises(ValueError):
            A.validate_spec(value)

    def test_remote_member_path_traversal_rejected(self):
        value = copy.deepcopy(A.load_spec())
        value['assets'][0]['remote_path'] = '../config.json'
        with self.assertRaises(ValueError):
            A.validate_spec(value)

    def test_no_alternative_precision_admitted(self):
        value = copy.deepcopy(A.load_spec())
        value['assets'][-1]['remote_path'] = 'onnx/model.onnx'
        with self.assertRaises(ValueError):
            A.validate_spec(value)


if __name__ == '__main__':
    unittest.main()
