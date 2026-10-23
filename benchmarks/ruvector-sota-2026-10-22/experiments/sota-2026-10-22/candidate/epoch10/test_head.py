"""Synthetic contracts/math only; no real source inputs, model sessions or native calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value

HEAD = module('epoch10_test_head', HERE / 'head.py')
MODELS = module('epoch10_test_models', HERE / 'models.py')
RUNTIME = module('epoch10_test_runtime', HERE / 'runtime.py')


def dataset():
    records, allowed, annotations = [], [], []
    canonical_logits = [0.8, -0.4, 0.1]
    for group in range(24):
        state = f'Receiving Party may share copies. Receiving Party shall not use information. Agreement {group} ends in24 months.'
        descriptions = [('Receiving Party may share copies.', 'Entailment', 0, state.index('Receiving Party shall')),
                        ('Receiving Party may use information.', 'Contradiction', state.index('Receiving Party shall'), state.index('Agreement')),
                        ('Information may be verbally conveyed.', 'NotMentioned', state.index('Agreement'), len(state))]
        for index, (claim, label, start, end) in enumerate(descriptions):
            identity = f'synthetic-{group}-{index}'; hypothesis_id = f'hypothesis-{index}'; source_group = f'group-{group}'
            inp = {'state': state, 'questions': {'decision': {'type': 'choice', 'criteria': {'Yes': claim, 'No': 'No.'}}}}
            input_sha = hashlib.sha256(HEAD.canonical(inp)).hexdigest(); state_sha = hashlib.sha256(state.encode()).hexdigest()
            premise = state[start:end]
            trace = {'typed_head_state': 'TRAIN_COLLECTION', 'typed_head_feature_names': list(HEAD.FEATURES.FEATURE_NAMES),
                     'typed_head_canonical_logits': canonical_logits, 'logits': [0.8, 0.1, -0.4],
                     'typed_head_features': HEAD.FEATURES.extract(premise, claim, canonical_logits)}
            observation = {'premise': premise, 'hypothesis': claim, 'coverage': {'selected_source_spans': [[start, end]]}, 'decoding': trace}
            records.append({'id': identity, 'split': 'train', 'source_group': source_group, 'input': inp,
                            'input_sha256': input_sha, 'provenance': {'hypothesis_id': hypothesis_id},
                            'evaluation': {'original_threeway_label': label, 'gold': 'Yes' if label == 'Entailment' else 'No'},
                            'response': {'diagnostics': {'decision': {'source_state_sha256': state_sha,
                                                                       'arms': {arm: copy.deepcopy(observation) for arm in HEAD.ARMS}}}}})
            allowed.append({'id': identity, 'input_sha256': input_sha, 'source_group': source_group, 'hypothesis_id': hypothesis_id})
            annotations.append({'id': identity, 'input_sha256': input_sha, 'source_group': source_group, 'hypothesis_id': hypothesis_id,
                                'original_threeway_label': label, 'evidence_spans': [] if label == 'NotMentioned' else [[start, end]],
                                'evidence_span_ids': [], 'source_document_sha256': state_sha, 'source_annotation_sha256': 'synthetic-only'})
    allowlist = {'role': 'train', 'queries': 72, 'document_groups': 24, 'threeway_classes': list(HEAD.FEATURES.CLASSES), 'records': allowed}
    return records, allowlist, {'role': 'train', 'queries': 72, 'document_groups': 24, 'records': annotations}


def fit(rows, allow, annotations):
    return HEAD.fit(rows, allow, 'config', 'allowlist', {'model': 'synthetic'}, annotations, 'synthetic-annotations')


class HeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.allowlist, cls.annotations = dataset()
        cls.artifact = fit(cls.records, cls.allowlist, cls.annotations)

    def test_five_fixed_fits_weights_and_threeway_support(self):
        artifact = self.artifact
        diagnostics = [artifact['fit_diagnostics']] + [m['fit_diagnostics'] for m in artifact['auxiliary_folds']] + [artifact['auxiliary_final']['fit_diagnostics']]
        self.assertEqual(len(diagnostics), 5)
        for d in diagnostics:
            self.assertEqual(len(d['history']), 400)
            self.assertLessEqual(d['final_objective'], d['initial_objective'] + 1e-8)
            self.assertLessEqual(d['final_gradient_norm'], 1e-3)
        self.assertAlmostEqual(artifact['training_total_weight'], 72)
        for identity in {x['id'] for x in artifact['training_examples']}:
            self.assertAlmostEqual(sum(x['weight'] for x in artifact['training_examples'] if x['id'] == identity), 1)
        head = HEAD.FrozenHead(artifact, 'config', 'allowlist', {'model': 'synthetic'})
        p = head.predict(artifact['training_examples'][0]['features'], [0.8, -0.4, 0.1])
        self.assertEqual(set(p), set(HEAD.FEATURES.CLASSES)); self.assertAlmostEqual(sum(p.values()), 1)
        self.assertTrue(all(value > 0 for value in p.values()))

    def test_document_crossfit_norm_and_predictions_exclude_heldout(self):
        examples = self.artifact['training_examples']; raw = np.asarray([x['features'] for x in examples]); sw = np.asarray([x['weight'] for x in examples])
        for model in self.artifact['auxiliary_folds']:
            fit_mask = np.asarray([x['source_group'] in model['training_groups'] for x in examples])
            held_mask = ~fit_mask
            self.assertEqual(int(fit_mask.sum()), 144); self.assertEqual(int(held_mask.sum()), 72)
            self.assertFalse(set(model['training_groups']) & set(model['heldout_groups']))
            mean, scale = HEAD.normalize_fit(raw[fit_mask], sw[fit_mask])
            np.testing.assert_allclose(mean, model['mean'], atol=0, rtol=0); np.testing.assert_allclose(scale, model['scale'], atol=0, rtol=0)
            np.testing.assert_allclose(HEAD.predict_aux(model, raw[held_mask]), np.asarray(self.artifact['oof_probabilities'])[held_mask], atol=0, rtol=0)
        self.assertIn('distribution shift', self.artifact['auxiliary_limits'])

    def test_auxiliary_target_is_annotation_overlap_not_label_or_sufficiency(self):
        rows, allow, ann = dataset(); ann['records'][0]['evidence_spans'] = [[1, 2]]
        examples = HEAD.collect(rows, allow, ann)
        selected = [x for x in examples if x['id'] == rows[0]['id']]
        self.assertTrue(all(x['annotation_overlap_target'] == 1 for x in selected))
        ann['records'][0]['evidence_spans'] = [[len(rows[0]['input']['state']) - 2, len(rows[0]['input']['state']) - 1]]
        self.assertTrue(all(x['annotation_overlap_target'] == 0 for x in HEAD.collect(rows, allow, ann) if x['id'] == rows[0]['id']))
        self.assertEqual(ann['records'][0]['original_threeway_label'], 'Entailment')

    def test_dev_confirmation_unknown_input_annotation_and_feature_changes_rejected(self):
        for mutation in ('dev', 'confirmation', 'id', 'input', 'annotation', 'offset', 'feature'):
            rows, allow, ann = dataset()
            if mutation in ('dev', 'confirmation'): rows[0]['split'] = mutation
            elif mutation == 'id': rows[0]['id'] = 'not-in-train'
            elif mutation == 'input': rows[0]['input']['state'] += 'Changed.'
            elif mutation == 'annotation': ann['records'][0]['source_document_sha256'] = 'changed'
            elif mutation == 'offset': ann['records'][0]['evidence_spans'] = [[-1, 2]]
            else: rows[0]['response']['diagnostics']['decision']['arms']['ruvector_top2']['decoding']['typed_head_features'][4] += .1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): HEAD.collect(rows, allow, ann)
        # Exact schema names of the frozen sidecar, synthetic values only.
        self.assertIn('source_document_sha256', self.annotations['records'][0]); self.assertNotIn('source_text_sha256', self.annotations['records'][0])

    def test_logit_offset_invariance_and_role_binding(self):
        first = HEAD.FEATURES.extract('Receiving Party shall not share copies except when permitted.', 'Receiving Party may share copies.', [1, 2, 3])
        second = HEAD.FEATURES.extract('Receiving Party shall not share copies except when permitted.', 'Receiving Party may share copies.', [11, 12, 13])
        self.assertEqual(first, second)
        feature = dict(zip(HEAD.FEATURES.FEATURE_NAMES, first))
        self.assertGreater(feature['matching_role_negation_fraction'], 0); self.assertGreater(feature['exception_fraction'], 0)
        mismatch = dict(zip(HEAD.FEATURES.FEATURE_NAMES, HEAD.FEATURES.extract('Disclosing Party may share copies.', 'Receiving Party may share copies.', [1, 2, 3])))
        self.assertGreater(mismatch['role_mismatch_fraction'], 0)

    def test_both_convex_objective_gradients_by_finite_difference(self):
        rng = np.random.default_rng(72); x = rng.normal(size=(7, 4)); sw = np.arange(1., 8.)
        w = rng.normal(size=(4, 3)) * .1; base = rng.normal(size=(7, 3)); y = np.arange(7) % 3
        _, grad = HEAD.objective(w, x, base, y, sw)
        for index in ((0, 0), (1, 2), (3, 1)):
            plus = w.copy(); minus = w.copy(); plus[index] += 1e-6; minus[index] -= 1e-6
            numerical = (HEAD.objective(plus, x, base, y, sw)[0] - HEAD.objective(minus, x, base, y, sw)[0]) / 2e-6
            self.assertAlmostEqual(numerical, grad[index], places=7)
        w = rng.normal(size=4) * .1; target = np.arange(7) % 2; _, grad = HEAD.aux_objective(w, x, target, sw)
        for index in range(4):
            plus = w.copy(); minus = w.copy(); plus[index] += 1e-6; minus[index] -= 1e-6
            numerical = (HEAD.aux_objective(plus, x, target, sw)[0] - HEAD.aux_objective(minus, x, target, sw)[0]) / 2e-6
            self.assertAlmostEqual(numerical, grad[index], places=7)

    def test_forced_late_stage_failure_retains_four_auxiliary_histories(self):
        original = HEAD.optimize
        def fail_main(shape, fn, stage):
            if stage == 'threeway_residual_OOFcoverage':
                raise HEAD.FitFailure('Synthetic injected late-stage failure', {'stage': stage, 'history': [], 'steps_completed': 0})
            return original(shape, fn, stage)
        with patch.object(HEAD, 'optimize', fail_main):
            with self.assertRaises(HEAD.FitFailure) as captured: fit(self.records, self.allowlist, self.annotations)
        d = captured.exception.diagnostics
        self.assertEqual(len(d['completed_auxiliary_fits']), 4)
        self.assertTrue(all(len(m['fit_diagnostics']['history']) == 400 for m in d['completed_auxiliary_fits']))
        self.assertEqual(d['pipeline_progress']['completed_auxiliary_count'], 4)
        self.assertTrue(all(v is not None for v in d['pipeline_progress']['oof_probabilities']))
        self.assertIsNotNone(d['pipeline_progress']['main_normalization'])

    def test_nonfinite_optimizer_failure_preserves_partial_state(self):
        calls = []
        def objective(w):
            calls.append(1)
            return (float('nan'), np.ones_like(w)) if len(calls) == 4 else (float(np.square(w - 1).sum()), 2 * (w - 1))
        with self.assertRaises(HEAD.FitFailure) as captured: HEAD.optimize((2,), objective, 'synthetic_nonfinite')
        d = captured.exception.diagnostics
        self.assertEqual(d['steps_completed'], 2); self.assertEqual(len(d['history']), 2)
        self.assertEqual(len(d['last_finite_weights']), 2); HEAD.canonical(d)

    def test_artifact_tampering_and_class_mapping(self):
        for field in ('weights', 'class_order', 'trainer_source_sha256'):
            changed = copy.deepcopy(self.artifact)
            if field == 'weights': changed[field][0][0] += .1
            elif field == 'class_order': changed[field] = list(reversed(changed[field]))
            else: changed[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError): HEAD.FrozenHead(changed, 'config', 'allowlist', {'model': 'synthetic'})
        calls = []
        def decode(premise, hypothesis):
            calls.append(1); return {}, {'logits': [0., 5., -5.]}
        base = SimpleNamespace(label_indices={'entailment': 0, 'neutral': 1, 'contradiction': 2}, tokenizer=object(), receipt={}, decode=decode)
        reader = MODELS.TypedNli(base); binary, trace = reader.decode('Agreement term.', 'Oral information.')
        self.assertGreater(trace['raw_threeway_probabilities']['NotMentioned'], .99); self.assertGreater(binary['No'], .99)
        reader.head_state = 'FIT_FAILED'
        with self.assertRaises(ValueError): reader.decode('Source.', 'Claim.')
        self.assertEqual(len(calls), 1)


class RuntimeStateTests(unittest.TestCase):
    def engine(self, directory):
        rows, allow, annotations = dataset()
        reader = RUNTIME.CandidateEngine.__new__(RUNTIME.CandidateEngine)
        reader.config = json.loads((HERE / 'config.json').read_text())
        reader.training_contract_path = directory / 'contract.json'; reader.training_contract_path.write_text('{"synthetic":true}')
        reader.config['training_contract_sha256'] = HEAD.sha(reader.training_contract_path)
        reader.training_source_path = directory / 'train72.jsonl'; reader.training_source_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        reader.config['training_source_sha256'] = HEAD.sha(reader.training_source_path)
        reader.training_annotations_path = directory / 'annotations.json'; reader.training_annotations_path.write_text(json.dumps(annotations))
        reader.config['training_annotations_sha256'] = HEAD.sha(reader.training_annotations_path)
        reader.train_allowlist = allow; reader.head_state = 'TRAIN_COLLECTION'; reader._fit_attempted = False
        reader.fitted_head_path = None; reader.fitted_head_sha256 = None; reader.receipt = {}
        base = SimpleNamespace(label_indices={'entailment': 0, 'neutral': 1, 'contradiction': 2}, tokenizer=object(), receipt={})
        reader.nli = MODELS.TypedNli(base)
        return reader

    def test_fit_once_freeze_finalize_and_no_refit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); reader = self.engine(directory); target = directory / 'frozen-head.json'
            receipt = reader.fit_from_records(dataset()[0], target)
            self.assertEqual(receipt['head_state'], 'FROZEN'); self.assertEqual(reader.finalize()['artifact_sha256'], HEAD.sha(target))
            self.assertEqual(reader.nli.head_state, 'FROZEN'); self.assertEqual(len(json.loads(target.read_text())['cached_training_replay']), 216)
            with self.assertRaises(ValueError): reader.fit_from_records(dataset()[0], directory / 'second-head.json')

    def test_failed_fit_no_artifact_or_fallback_and_cached_label_tamper(self):
        for mutation in ('split', 'gold'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); reader = self.engine(directory); rows = dataset()[0]
                if mutation == 'split': rows[0]['split'] = 'dev'
                else: rows[0]['evaluation'] = {'original_threeway_label': 'NotMentioned', 'gold': 'No'}
                target = directory / 'never-created.json'
                with self.assertRaises(ValueError): reader.fit_from_records(rows, target)
                self.assertFalse(target.exists()); self.assertEqual(reader.head_state, 'FIT_FAILED')
                self.assertFalse(reader.receipt['fit_failure']['DEV_or_confirmation_permitted'])
                with self.assertRaises(ValueError): reader.predict('Source.', {})


if __name__ == '__main__': unittest.main()
