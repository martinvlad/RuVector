"""Pure negative gates and resolution-only probes; no model/native execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name('preflight.py')
SPEC = importlib.util.spec_from_file_location('epoch5_preflight', SOURCE)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def integer(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result + bytes([value]))


def scalar(number, value):
    return integer(number << 3) + integer(value)


def message(number, payload):
    return integer(number << 3 | 2) + integer(len(payload)) + payload


def value(name, element_type, dimensions):
    shape = b''.join(message(1, scalar(1, item) if isinstance(item, int)
                             else message(2, item.encode())) for item in dimensions)
    tensor = scalar(1, element_type) + message(2, shape)
    return message(1, name.encode()) + message(2, message(1, tensor))


def model(input_name='input_ids', external=False):
    graph = message(11, value(input_name, 7, ['batch', 'sequence']))
    graph += message(11, value('attention_mask', 7, ['batch', 'sequence']))
    graph += message(12, value('logits', 1, ['batch', 3]))
    if external:
        graph += message(5, message(8, b'weights') + scalar(14, 1))
    return scalar(1, 8) + message(7, graph) + message(8, scalar(2, 17))


class PurePreflightTests(unittest.TestCase):
    def test_relative_paths_reject_escape_and_aliases(self):
        for path in ('', '../x', '/tmp/x', 'a/../b', 'a//b', './x', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                gate.relative(path)
        self.assertEqual(gate.relative('a/b'), Path('a/b'))

    def test_closure_rejects_tampered_bytes_and_length(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'entry.js').write_bytes(b'original')
            item = {'path': 'entry.js', 'bytes': 8,
                    'sha256': hashlib.sha256(b'original').hexdigest()}
            self.assertEqual(gate.checked_file(root, item, True)['bytes'], 8)
            (root / 'entry.js').write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                gate.checked_file(root, item, True)
            (root / 'entry.js').write_bytes(b'original-extra')
            with self.assertRaises(ValueError):
                gate.checked_file(root, item, True)

    def test_closure_rejects_symlink_file_and_ancestor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'real').mkdir()
            (root / 'real/entry.js').write_bytes(b'x')
            (root / 'link').symlink_to('real', target_is_directory=True)
            (root / 'entry.js').symlink_to('real/entry.js')
            for path in ('entry.js', 'link/entry.js'):
                item = {'path': path, 'bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}
                with self.subTest(path=path), self.assertRaises(ValueError):
                    gate.checked_file(root, item, True)

    def test_pinned_spec_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'spec.json'
            path.write_bytes(b'{}')
            digest = hashlib.sha256(b'{}').hexdigest()
            self.assertEqual(gate.pinned_json(path, digest), {})
            path.write_bytes(b'{"changed":true}')
            with self.assertRaises(ValueError):
                gate.pinned_json(path, digest)

    def test_protobuf_rejects_truncation_and_invalid_wire(self):
        for data in (b'\x80', b'\x0a\x08short', b'\x0dxx', b'\x0f', b'\x00'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(gate.fields(data, 0, len(data)))

    def test_static_onnx_accepts_expected_feeds_without_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.onnx'
            path.write_bytes(model())
            observed = gate.inspect_onnx(path)
            self.assertEqual(observed['outputs'][0]['dimensions'][1]['value'], 3)
            self.assertEqual(observed['opsets'], [{'domain': '', 'version': 17}])
            self.assertFalse(observed['session_initialized'])
            self.assertEqual(observed['model_forwards'], 0)

    def test_static_onnx_rejects_external_tensor_and_unknown_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.onnx'
            for payload in (model(external=True), model(input_name='hidden_states')):
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    gate.inspect_onnx(path)

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_node_resolves_but_does_not_execute_throwing_packages_or_addon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / 'retrieval/node_modules'
            for name in ('@ruvector/core', 'ruvector-core-linux-x64-gnu'):
                package = modules / name
                package.mkdir(parents=True)
                (package / 'index.js').write_text("throw new Error('must never execute');")
                (package / 'package.json').write_text(json.dumps({'name': name, 'version': '0.0.0', 'main': 'index.js'}))
            (modules / 'ruvector-core-linux-x64-gnu/ruvector.node').write_bytes(b'not-an-addon')
            env = dict(os.environ)
            env.pop('NODE_OPTIONS', None)
            env.pop('NODE_PATH', None)
            result = subprocess.run([shutil.which('node'), '--no-addons', '--no-global-search-paths',
                                     '-e', gate.NODE_WITNESS, str(root)], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            witness = json.loads(result.stdout)
            self.assertEqual(witness['package_imports_executed'], 0)
            self.assertEqual(witness['native_addon_load_attempts'], 0)
            self.assertEqual(len(witness['resolved']), 2)


if __name__ == '__main__':
    unittest.main()
