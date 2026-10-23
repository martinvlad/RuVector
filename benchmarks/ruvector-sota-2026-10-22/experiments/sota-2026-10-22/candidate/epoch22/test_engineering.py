"""Pure/generic protocol fault tests. Never import models, BGE or native code."""
import copy
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import common as C
import retrieval as R
import worker_actual_v1 as worker
import reader
import launch_actual_v1 as launch


def input_fixture():
    records = []; allow = []
    for doc in range(8):
        for hyp in ('nda-17', 'nda-7', 'nda-3'):
            rowid = f'original-contractnli:train:epoch22:dev:{doc}:{hyp}'
            value = {'state': f'Generic supplied source {doc}.', 'questions': {'decision': {
                'type': 'choice', 'criteria': {'Yes': hyp, 'No': 'not ' + hyp}}}}
            records.append({'id': rowid, 'input': value,
                'input_sha256': hashlib.sha256(C.canonical(value).encode()).hexdigest()})
            allow.append({'id': rowid, 'document_id': doc, 'hypothesis_id': hyp,
                          'source_group': f'original-contractnli:{doc}'})
    return {'schema_version': 1, 'role': 'dev', 'records': records}, {'records': allow}


class Engineering(unittest.TestCase):
    def test_imports_do_not_initialize_model_frameworks(self):
        for key in ('torch', 'transformers', 'numpy', 'onnxruntime', 'tokenizers'):
            self.assertNotIn(key, sys.modules)

    def test_raw_E_N_C_maps_to_canonical_E_C_N(self):
        raw, typed = C.distribution([1., 2., 3.])
        self.assertEqual([typed[x] for x in C.ORDER], [raw[0], raw[2], raw[1]])
        self.assertEqual(C.prediction(typed), 'Contradiction')
        self.assertAlmostEqual(math.fsum(typed.values()), 1.)

    def test_nonfinite_or_wrong_dimension_logits_refused(self):
        for logits in ([1, 2], [1, 2, 3, 4], [math.nan, 1, 2], [math.inf, 1, 2]):
            with self.assertRaises(ValueError): C.distribution(logits)

    def test_tie_order_is_frozen(self):
        self.assertEqual(C.prediction(dict(zip(C.ORDER, [1 / 3] * 3))), 'Entailment')

    def test_stable_softmax_large_offsets(self):
        a, _ = C.distribution([10001., 10002., 10003.])
        b, _ = C.distribution([1., 2., 3.])
        self.assertEqual(a, b)

    def test_three_fixed_native_engineering_vectors(self):
        rows = [{'premise': 'The lamp is on.', 'hypothesis': 'The lamp is on.'},
                {'premise': 'The lamp is not on.', 'hypothesis': 'The lamp is on.'},
                {'premise': 'The box is blue.', 'hypothesis': 'The lamp is on.'}]
        bundle = R.engineering_bundle(rows)
        self.assertEqual(bundle['vectors'][0][:5], [1, 1, 0, 0, 0])
        self.assertEqual(bundle['vectors'][1][:5], [1, 1, 1, 0, 0])
        self.assertTrue(all(len(x) == 384 for x in bundle['vectors'] + bundle['query_vectors']))
        self.assertEqual([x['full_cosine_order'] for x in R.reference(**{
            'vectors': bundle['vectors'], 'queries': bundle['query_vectors']})], [[0, 1, 2]] * 3)

    def test_lexical_uses_jaccard_and_source_ties(self):
        self.assertEqual(R.lexical_ids(['a b z z', 'a b', 'a'], 'a b', 3), [1, 0, 2])
        self.assertEqual(R.lexical_ids(['a', 'a'], 'a', 2), [0, 1])

    def test_exact_input_rows_group_to_literal_document_IDs(self):
        value, allow = input_fixture(); docs = worker.groups(value, 'dev', allow)
        self.assertEqual([d['id'] for d in docs], list(range(8)))
        self.assertTrue(all(type(d['id']) is int and len(d['questions']) == 3 for d in docs))

    def test_label_fields_in_input_records_refused(self):
        value, allow = input_fixture(); value['records'][0]['gold'] = 'Yes'
        with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)

    def test_duplicate_missing_and_extra_query_IDs_refused(self):
        for fault in ('duplicate', 'missing', 'extra'):
            value, allow = input_fixture()
            if fault == 'duplicate': value['records'][1] = copy.deepcopy(value['records'][0])
            if fault == 'missing': value['records'].pop()
            if fault == 'extra': value['records'][0]['id'] += ':extra'
            with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)

    def test_frozen_document_or_hypothesis_swap_refused(self):
        for key, val in [('document_id', 300), ('hypothesis_id', 'nda-other'), ('source_group', 'original-contractnli:300')]:
            value, allow = input_fixture(); allow['records'][0][key] = val
            with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)

    def test_noncanonical_decimal_document_ID_refused(self):
        value, allow = input_fixture(); before = value['records'][0]['id']
        after = before.replace(':0:', ':00:'); value['records'][0]['id'] = after; allow['records'][0]['id'] = after
        with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)

    def test_changed_whole_text_and_prebound_hash_refused(self):
        value, allow = input_fixture(); value['records'][0]['input']['state'] += ' changed'
        with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)
        value, allow = input_fixture(); allow['records'][0]['input_sha256'] = '0' * 64
        with self.assertRaises(ValueError): worker.groups(value, 'dev', allow)

    def test_unsafe_and_symlink_source_members_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'ok').write_text('x'); (root / 'link').symlink_to(root / 'ok')
            self.assertEqual(C.checked('ok', root), root / 'ok')
            for name in ('../ok', './ok', '/ok', 'a//ok', 'a\\ok', 'link'):
                with self.assertRaises(ValueError): C.checked(name, root)

    def test_real_generic_kernel_lock_admission_and_released_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / 'scope' / 'project'; project.mkdir(parents=True)
            lock = root / 'exclusive.work.lock'; fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                state = Path('/proc/' + str(os.getpid()) + '/stat').read_text().rsplit(')', 1)[1].split()
                value = {'owner_pid': os.getpid(), 'owner_start_ticks': int(state[19]),
                         'lock_inode': os.fstat(fd).st_ino, 'lock_path': str(lock)}
                with patch.object(C, 'ROOT', project):
                    C.verify_owner_lock(value)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    with self.assertRaises(ValueError): C.verify_owner_lock(value)
            finally: os.close(fd)

    def test_report_updates_preserve_exclusive_original_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.json'; C.write_new(path, {'a': 1})
            with self.assertRaises(FileExistsError): C.write_new(path, {'a': 2})
            C.replace_report(path, {'a': 3}); self.assertEqual(C.read(path), {'a': 3})

    def test_confirmation_capacity_binds_all_inputs_and_forbids_forward_counters(self):
        value, allow = input_fixture(); value['role'] = 'confirmation'
        for row, meta in zip(value['records'], allow['records']):
            row['id'] = row['id'].replace(':epoch22:dev:', ':epoch18:confirmation:')
            meta['id'] = meta['id'].replace(':dev:', ':confirmation:')
            meta['input_sha256'] = row['input_sha256']
        class Context:
            def partition(self, state, nli, bge, **kwargs): return [None]
        evidence = SimpleNamespace(context=Context(), bge=SimpleNamespace(raw_tokenizer=None))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); C.write_new(root / 'bank.json', value); C.write_new(root / 'allow.json', allow)
            plan = {'confirmation_capacity_inputs_path': 'bank.json', 'confirmation_capacity_inputs_sha256': C.sha(root / 'bank.json'),
                    'phases': {'confirmation': {'input_allowlist_path': 'allow.json'}}}
            with patch.object(C, 'ROOT', root), patch.object(C, 'checked', side_effect=lambda name: root / name):
                capacity = worker.confirmation_capacity(plan, SimpleNamespace(tokenizer=None), evidence, {})
                self.assertEqual(capacity['document_units'], [{'document_id': i, 'units': 1} for i in range(8)])
                self.assertEqual(capacity['max_units'], 1)
                counters = {'NNI': 0}
                class BadContext:
                    def partition(self, *args, **kwargs): counters['NNI'] += 1; return [None]
                evidence.context = BadContext()
                with self.assertRaises(ValueError): worker.confirmation_capacity(plan, SimpleNamespace(tokenizer=None), evidence, counters)
                changed = copy.deepcopy(allow); changed['records'][0]['input_sha256'] = '0' * 64
                C.replace_report(root / 'allow.json', changed)
                evidence.context = Context()
                with self.assertRaises(ValueError): worker.confirmation_capacity(plan, SimpleNamespace(tokenizer=None), evidence, {})


if __name__ == '__main__': unittest.main()
