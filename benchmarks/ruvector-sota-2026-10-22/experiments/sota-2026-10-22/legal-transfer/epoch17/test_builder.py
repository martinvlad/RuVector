"""Pure engineering fixtures; no original benchmark cases or choices are parsed."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch17_builder', HERE / 'build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def fixture():
    old = {'id': 'original-contractnli:train:epoch16:confirmation:308:nda-17',
           'document_id': 308, 'hypothesis_id': 'nda-17', 'source_group': 'original-contractnli:308',
           'input_sha256': 'a' * 64, 'normalized_input_sha256': 'b' * 64,
           'normalized_document_sha256': 'c' * 64}
    record = {'selection': {'document_id': 308, 'role': 'confirmation'},
              **{k: old[k] for k in ('hypothesis_id', 'input_sha256', 'normalized_input_sha256',
                                     'normalized_document_sha256')}}
    allow = {k: v for k, v in old.items() if k not in ('document_id', 'normalized_document_sha256')}
    return old, record, allow


class BuilderTests(unittest.TestCase):
    def test_fixed_id_draw_metadata_only(self):
        with patch.object(b, 'read', wraps=b.read) as reads:
            _, registry, selected = b.selection_metadata()
        self.assertEqual([r['document_id'] for r in selected[:8]], b.DEV_IDS)
        self.assertEqual([r['document_id'] for r in selected[8:]], b.CONF_IDS)
        self.assertEqual(len(registry['excluded_document_ids']), 205)
        self.assertTrue(all('original-train' not in str(args[0]) for args, _ in reads.call_args_list))

    def test_real_origin_verification_metadata_only(self):
        with patch.object(b, 'read', wraps=b.read) as reads:
            reuse = b.verify_reuse_origin(HERE.parents[3])
        self.assertEqual(len(reuse['records']), 24)
        self.assertTrue(all('inputs-only' not in str(args[0]) and not str(args[0]).endswith('.jsonl')
                            for args, _ in reads.call_args_list))

    def test_exact_unused_conf_origin_allowed(self):
        old, record, allow = fixture()
        b.reject_prior_collision('confirmation', record, [(b.ORIGIN_ALLOW_PATH, allow)], {'records': [old]})

    def test_conf_alias_elsewhere_is_rejected(self):
        old, record, allow = fixture()
        with self.assertRaises(ValueError):
            b.reject_prior_collision('confirmation', record,
                [(b.ORIGIN_ALLOW_PATH, allow), ('experiments/sota-2026-10-22/legal-transfer/epoch15/dev-allowlist.json', allow)],
                {'records': [old]})

    def test_dev_cannot_reuse_reserved_conf(self):
        old, record, allow = fixture()
        with self.assertRaises(ValueError):
            b.reject_prior_collision('dev', record, [(b.ORIGIN_ALLOW_PATH, allow)], {'records': [old]})

    def test_changed_source_input_norm_doc_or_hypothesis_fails_exact_reuse(self):
        old, record, allow = fixture()
        for key in ('hypothesis_id', 'input_sha256', 'normalized_input_sha256', 'normalized_document_sha256'):
            changed = copy.deepcopy(record)
            changed[key] = 'tampered'
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.reject_prior_collision('confirmation', changed, [(b.ORIGIN_ALLOW_PATH, allow)], {'records': [old]})
        changed = copy.deepcopy(record)
        changed['selection']['document_id'] = 999
        with self.assertRaises(ValueError):
            b.reject_prior_collision('confirmation', changed, [], {'records': [old]})

    def test_missing_freeze_rejected_before_corpus_parse(self):
        with patch.object(b, 'read', side_effect=AssertionError('No source parse permitted')):
            with self.assertRaises(PermissionError):
                b.validate_inputs(Path('/nonexistent/source.json'), HERE.parents[3], None, None)

    def test_freeze_must_bind_current_builder_and_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            here = root / 'data'
            here.mkdir()
            for name in b.FREEZE_MEMBERS:
                (here / name).write_text('fixture')
            receipt = root / 'freeze.json'
            b.write_new(receipt, {'source_checkpoint': b.PARENT, 'files': [
                {'path': str((here / n).relative_to(root)), 'bytes': 7, 'sha256': b.sha(here / n)}
                for n in b.FREEZE_MEMBERS]})
            with patch.object(b, 'HERE', here):
                b.verify_source_freeze(receipt, b.sha(receipt), root)
                (here / 'build.py').write_text('changed')
                with self.assertRaises(PermissionError):
                    b.verify_source_freeze(receipt, b.sha(receipt), root)

    def test_confirmation_gate_before_source_or_labels(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(b, 'validate_inputs',
                side_effect=AssertionError('Source reached before gates')):
            with self.assertRaises(FileNotFoundError):
                b.materialize('confirmation', Path('/no-source'), Path(temp), None, 'f' * 64, True)

    def test_confirmation_requires_current_pid_and_passing_bound_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'experiments/sota-2026-10-22/epoch17'
            (root / 'runs/confirmation').mkdir(parents=True)
            (root / 'runs/development').mkdir()
            files = {'plan.json': {'lazy_confirmation': {'source_freeze_sha256': 'f' * 64}},
                     'runs/development/development-comparison.json': {'frozen_development_gate_passed': True},
                     'runtime-admission.json': {'allowed': True}}
            for name, value in files.items():
                b.write_new(root / name, value)
            plan_sha = b.sha(root / 'plan.json')
            b.write_new(root / 'confirmation-selection-lock.json', {'plan_sha256': plan_sha,
                'development_comparison_sha256': b.sha(root / 'runs/development/development-comparison.json'),
                'runtime_admission_sha256': b.sha(root / 'runtime-admission.json')})
            for name in ('attempt', 'popen-attempt'):
                b.write_new(root / ('runs/confirmation/' + name + '.json'),
                    {'phase': 'confirmation', 'source_plan_sha256': plan_sha, 'pid': 777, 'pgid': 777})
            with patch.object(b.os, 'getpid', return_value=777), patch.object(b.os, 'getpgrp', return_value=777):
                b.verify_confirmation_worker(Path(temp), 'f' * 64)
                with self.assertRaises(PermissionError):
                    b.verify_confirmation_worker(Path(temp), '0' * 64)
            with patch.object(b.os, 'getpid', return_value=888), patch.object(b.os, 'getpgrp', return_value=888):
                with self.assertRaises(PermissionError):
                    b.verify_confirmation_worker(Path(temp), 'f' * 64)

    def test_synthetic_role_choices_only_and_original_threeway_preserved(self):
        # These invented fixture labels are not benchmark observations.
        class ForbiddenChoices(dict):
            def __getitem__(self, key):
                if key == 'annotation_sets':
                    raise AssertionError('Other-role choices were accessed')
                return super().__getitem__(key)
        docs = {1: {'id': 1, 'file_name': 'synthetic', 'annotation_sets': [{'annotations': {
            h: {'choice': label} for h, label in zip(b.HYPOTHESES, b.LABELS)}}]},
            2: ForbiddenChoices(id=2)}
        prepared = []
        for identifier, role in ((1, 'dev'), (2, 'confirmation')):
            for h in b.HYPOTHESES:
                prepared.append({'selection': {'document_id': identifier, 'role': role,
                    'document_rank': 0, 'document_draw_key': 'synthetic'}, 'hypothesis_id': h,
                    'input': {'state': 'Invented fixture.', 'questions': {}}, 'input_sha256': 'a' * 64,
                    'normalized_input_sha256': 'b' * 64, 'normalized_document_sha256': 'c' * 64})
        with tempfile.TemporaryDirectory() as temp, patch.object(b, 'HERE', Path(temp)), \
                patch.object(b, 'validate_inputs', return_value=({}, docs, prepared, {})):
            b.write_new(Path(temp) / 'document-selection.json', {'fixture': True})
            receipt = b.materialize('dev', None, None, None, 'f' * 64, True)
            rows = [json.loads(line) for line in (Path(temp) / 'development24.jsonl').read_text().splitlines()]
            self.assertEqual([r['evaluation']['original_threeway_label'] for r in rows], list(b.LABELS))
            self.assertEqual([r['evaluation']['gold'] for r in rows], ['Yes', 'No', 'No'])
            self.assertEqual(receipt['other_role_annotation_choices_accessed'], 0)
            self.assertFalse((Path(temp) / 'confirmation24.jsonl').exists())
            with self.assertRaises(FileExistsError):
                b.materialize('dev', None, None, None, 'f' * 64, True)


if __name__ == '__main__':
    unittest.main()
