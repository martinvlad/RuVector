"""Invented metadata/packing/state-validation fixtures; no actual models or benchmark labels."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import math
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import guards
import worker

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packing
import reader


def fake_tokens(premise, claim):
    count = len(premise.split()) + len(claim.split()) + 4
    return {'input_ids': list(range(count)), 'attention_mask': [1] * count}


class FakeTensor:
    """Only shape/type/device metadata; finite slices never allocate model storage."""
    next_pointer = 0
    def __init__(self, shape, dtype='float32', values=None, finite=True, meta=False, pointer=None):
        self.shape = tuple(shape); self.dtype = dtype; self.values = values; self.finite = finite
        self.is_meta = meta; self.device = SimpleNamespace(type='meta' if meta else 'cpu')
        FakeTensor.next_pointer += 1; self.pointer = FakeTensor.next_pointer if pointer is None else pointer
    def numel(self): return math.prod(self.shape)
    def is_contiguous(self): return True
    def is_floating_point(self): return self.dtype == 'float32'
    def view(self, shape): return FakeTensor((self.numel(),), self.dtype, self.values, self.finite, self.is_meta, self.pointer)
    def __getitem__(self, key):
        return FakeTensor((max(0, min(key.stop, self.numel()) - key.start),),
                          self.dtype, None, self.finite, self.is_meta, self.pointer)
    def unsqueeze(self, axis): return FakeTensor((1, *self.shape), self.dtype, self.values, self.finite)
    def expand(self, shape): return self.unsqueeze(0)
    def data_ptr(self): return self.pointer


class FakeTruth:
    def __init__(self, value): self.value = value
    def all(self): return self.value


class FakeDevice:
    def __enter__(self): FakeTorch.mode = 'meta'
    def __exit__(self, *args): FakeTorch.mode = 'cpu'


class FakeTorch:
    Tensor = FakeTensor; int64 = 'int64'; float32 = 'float32'; mode = 'cpu'; finite_sizes = []
    @staticmethod
    def device(name):
        assert name == 'meta'; return FakeDevice()
    @staticmethod
    def arange(size, dtype, device='cpu'): return FakeTensor((size,), dtype, tuple(range(size)))
    @staticmethod
    def zeros(shape, dtype, device='cpu'): return FakeTensor(shape, dtype, tuple(0 for _ in range(math.prod(shape))))
    @staticmethod
    def equal(a, b): return a.shape == b.shape and a.dtype == b.dtype and a.values == b.values
    @staticmethod
    def isfinite(a):
        FakeTorch.finite_sizes.append(a.numel()); return FakeTruth(a.finite)


MODEL_SHAPES = json.loads((HERE / 'model_contract.json').read_text())['state_shapes']


def fake_state(meta=False):
    return {key: FakeTensor(shape, meta=meta) for key, shape in MODEL_SHAPES.items()}


class FakeEmbeddings:
    def __init__(self):
        self._buffers = {key: FakeTensor((1, 514), 'int64', meta=True)
                         for key in ('position_ids', 'token_type_ids')}
        self._non_persistent_buffers_set = set(self._buffers)
    def register_buffer(self, name, value, persistent):
        assert persistent is False; self._buffers[name] = value


class FakeClassifier:
    def __init__(self, config):
        assert FakeTorch.mode == 'meta'
        self.state = {key: val for key, val in fake_state(meta=True).items()
                      if not key.startswith('roberta.pooler.')}
        self.roberta = SimpleNamespace(pooler=None, embeddings=FakeEmbeddings())
    def state_dict(self):
        return {**self.state, **(self.roberta.pooler.state if self.roberta.pooler else {})}
    def parameters(self): return self.state_dict().values()
    def buffers(self): return self.roberta.embeddings._buffers.values()


class FakePooler:
    def __init__(self, config):
        assert FakeTorch.mode == 'meta'
        self.state = {key: value for key, value in fake_state(meta=True).items()
                      if key.startswith('roberta.pooler.')}


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

    def test_all_395_keys_pooler_head_and_bounded_finite_checks(self):
        expected = fake_state(meta=True); state = fake_state(); FakeTorch.finite_sizes = []
        clean, audit = reader.strict_state(state, expected, FakeTorch)
        self.assertIs(clean, state)
        self.assertEqual(audit['learned_state_tensor_count'], 395)
        self.assertEqual(audit['source_tensor_elements'], 356412419)
        self.assertGreater(len(FakeTorch.finite_sizes), 395)
        self.assertLessEqual(max(FakeTorch.finite_sizes), guards.FINITE_CHUNK_ELEMENTS)
        self.assertEqual(sum(FakeTorch.finite_sizes), 356412419)
        for edit in ['missing_pooler', 'extra', 'head_shape', 'nonfinite', 'wrong_dtype', 'meta', 'legacy_buffer']:
            state = fake_state()
            if edit == 'missing_pooler': del state['roberta.pooler.dense.weight']
            if edit == 'extra': state['unexpected'] = FakeTensor((1,))
            if edit == 'head_shape': state['classifier.out_proj.weight'] = FakeTensor((2, 1024))
            if edit == 'nonfinite': state['classifier.out_proj.bias'].finite = False
            if edit == 'wrong_dtype': state['classifier.out_proj.bias'].dtype = 'float16'
            if edit == 'meta': state['classifier.out_proj.bias'] = FakeTensor((3,), meta=True)
            if edit == 'legacy_buffer': state['roberta.embeddings.position_ids'] = FakeTensor((1, 514), 'int64')
            with self.assertRaises(ValueError, msg=edit): reader.strict_state(state, expected, FakeTorch)

    def test_meta_constructor_keeps_original_pooler_and_exact_cpu_buffers(self):
        model = reader.construct_meta_model({}, FakeTorch, FakeClassifier, FakePooler)
        self.assertEqual(len(model.state_dict()), 395)
        self.assertTrue(all(x.is_meta for x in model.parameters()))
        receipt = reader.materialize_nonpersistent_buffers(model, FakeTorch)
        self.assertEqual(set(receipt), {'position_ids', 'token_type_ids'})
        self.assertEqual(model.roberta.embeddings._buffers['position_ids'].values, tuple(range(514)))
        self.assertEqual(set(model.roberta.embeddings._buffers['token_type_ids'].values), {0})
        self.assertTrue(all(not x.is_meta for x in model.buffers()))

    def test_assigned_storage_requires_alias_for_every_original_tensor(self):
        state = fake_state()
        model = SimpleNamespace(state_dict=lambda: state, parameters=lambda: state.values())
        self.assertTrue(reader.assert_assigned_storage(model, state, FakeTorch)[
            'all_395_state_tensor_data_pointers_match_mmap_source'])
        different = dict(state); different['roberta.pooler.dense.bias'] = FakeTensor((1024,))
        with self.assertRaisesRegex(ValueError, 'SHARE_EVERY'):
            reader.assert_assigned_storage(model, different, FakeTorch)

    def test_network_audit_always_denies_optional_probe_and_unknown_events(self):
        counters = {'Python_network_operations_attempted': 0, 'Python_network_operations_blocked': 0}
        audit = guards.NetworkAudit(counters); audit.set_stage('reader_torch_import')
        with self.assertRaisesRegex(RuntimeError, 'FORBIDDEN'): audit('socket.bind', ('PRIVATE_HOST',))
        self.assertTrue(audit.receipt()['admissible'])
        self.assertNotIn('PRIVATE_HOST', json.dumps(audit.receipt()))
        audit.set_stage('nli_forecasts')
        with self.assertRaises(RuntimeError): audit('socket.connect', ('PRIVATE_HOST',))
        self.assertFalse(audit.receipt()['admissible'])
        self.assertEqual(counters['Python_network_operations_blocked'], 2)
        self.assertEqual(audit.receipt()['audited_successful_network_operations'], 0)

    def test_public_socket_wrappers_deny_before_original_calls(self):
        class FakeSocket:
            def bind(self, *args): raise AssertionError('ORIGINAL_BIND_MUST_NOT_EXECUTE')
            def sendall(self, *args): raise AssertionError('ORIGINAL_SEND_MUST_NOT_EXECUTE')
        fake = SimpleNamespace(socket=FakeSocket)
        counters = {'Python_network_operations_attempted': 0, 'Python_network_operations_blocked': 0}
        audit = guards.NetworkAudit(counters)
        with patch.dict(sys.modules, {'socket': fake}): audit.install_socket_guards()
        with self.assertRaises(RuntimeError): FakeSocket().bind('PRIVATE_HOST')
        with self.assertRaises(RuntimeError): FakeSocket().sendall(b'PRIVATE_BYTES')
        self.assertEqual(audit.receipt()['event_counts'], {'socket.bind': 1, 'socket.sendall': 1})

    def test_headroom_preflight_fails_closed_including_unlimited_unknown(self):
        for value in [None, -1, guards.MIN_HEADROOM_BYTES - 1]:
            with self.assertRaises(ValueError): guards.require_headroom({'headroom_bytes': value})
        guards.require_headroom({'headroom_bytes': guards.MIN_HEADROOM_BYTES})

    def test_hash_streaming_chunk_cap_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            target = Path(folder) / 'fake.bin'; payload = b'x' * (guards.HASH_CHUNK_BYTES + 17)
            target.write_bytes(payload); sizes = []; original = worker.os.read
            def capture(fd, size): sizes.append(size); return original(fd, size)
            ref = {'path': str(target), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            with patch.object(worker.os, 'read', capture): self.assertEqual(worker.verify_file(ref), target)
            self.assertTrue(sizes); self.assertLessEqual(max(sizes), 1024 ** 2)
            alias = Path(folder) / 'alias'; alias.symlink_to(target)
            with self.assertRaises(ValueError): worker.verify_file({**ref, 'path': str(alias)})

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
        self.assertEqual(keywords, {'map_location': 'cpu', 'weights_only': True, 'mmap': True})
        assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == 'load_state_dict']
        self.assertEqual(len(assigns), 1)
        self.assertEqual({k.arg: ast.literal_eval(k.value) for k in assigns[0].keywords}, {'strict': True, 'assign': True})
        self.assertFalse(any(isinstance(n, ast.Import) and any(a.name == 'torch' for a in n.names)
                             for n in tree.body))

    def test_no_framework_imported_by_source_or_inert_tests(self):
        self.assertFalse(any(name == 'torch' or name.startswith('torch.') or name == 'transformers'
                             or name == 'onnxruntime' for name in sys.modules))
        tree = ast.parse((HERE / 'worker.py').read_text())
        main = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'main')
        calls = [(n.lineno, n.func.id) for n in ast.walk(main) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id in ('Reader', 'embed_documents', 'run_native')]
        self.assertEqual([name for _, name in sorted(calls)], ['Reader', 'embed_documents', 'run_native'])

    def test_isolated_worker_help_imports_only_stdlib_guard(self):
        import subprocess
        result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'worker.py'), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--expected-plan-sha256', result.stdout)

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
        bank = {'schema_version': 1, 'epoch': 50, 'kind': packing.KIND, 'role': 'dev',
                'source_archive_sha256': archive, 'documents': docs, 'cases': cases}
        self.assertEqual(len(packing.validate_features(bank, 'dev', docids, ids, archive)), 4)
        bad = copy.deepcopy(bank); bad['cases'][0]['choice'] = 'secret'
        with self.assertRaisesRegex(ValueError, 'FEATURE_CASE_KEYS'):
            packing.validate_features(bad, 'dev', docids, ids, archive)
        bad = copy.deepcopy(bank); bad['documents'][0]['evidence'][0]['sentence'] = 'changed'
        with self.assertRaises(ValueError): packing.validate_features(bad, 'dev', docids, ids, archive)


if __name__ == '__main__':
    unittest.main()
