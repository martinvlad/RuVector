"""Synthetic TRAIN-only fit boundaries; no ONNX, native calls or real data."""
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


HEAD = module('epoch8_test_head', HERE / 'head.py')
MODELS = module('epoch8_test_models', HERE / 'models.py')
RUNTIME = module('epoch8_test_runtime', HERE / 'runtime.py')


def dataset():
    state = 'Receiving Party may share copies. Receiving Party shall not use information. Agreement ends in24 months.'
    descriptions = [('Party may share copies.', 'Entailment', 0, state.index('Receiving Party shall')),
                    ('Party may use information.', 'Contradiction', state.index('Receiving Party shall'), state.index('Agreement')),
                    ('Information may be verbally conveyed.', 'NotMentioned', state.index('Agreement'), len(state))]
    records, allowed = [], []
    canonical_logits = [0.8, -0.4, 0.1]
    for group in range(24):
        for index, (claim, label, start, end) in enumerate(descriptions):
            identity = f'synthetic-{group}-{index}'
            hypothesis_id = f'hypothesis-{index}'
            inp = {'state': state, 'questions': {'decision': {'type': 'choice', 'criteria': {'Yes': claim, 'No': 'No.'}}}}
            input_sha = hashlib.sha256(HEAD.canonical(inp)).hexdigest()
            premise = state[start:end]
            trace = {'typed_head_state': 'TRAIN_COLLECTION', 'typed_head_feature_names': list(HEAD.FEATURES.FEATURE_NAMES),
                     'typed_head_canonical_logits': canonical_logits, 'logits': [-0.4, 0.8, 0.1],
                     'typed_head_features': HEAD.FEATURES.extract(premise, claim, canonical_logits)}
            observation = {'premise': premise, 'hypothesis': claim, 'coverage': {'selected_source_spans': [[start, end]]}, 'decoding': trace}
            records.append({'id': identity, 'split': 'train', 'source_group': f'group-{group}', 'input': inp,
                            'input_sha256': input_sha, 'provenance': {'hypothesis_id': hypothesis_id},
                            'evaluation': {'original_threeway_label': label, 'gold': 'Yes' if label == 'Entailment' else 'No'},
                            'response': {'diagnostics': {'decision': {'source_state_sha256': hashlib.sha256(state.encode()).hexdigest(),
                                                                       'arms': {arm: copy.deepcopy(observation) for arm in HEAD.ARMS}}}}})
            allowed.append({'id': identity, 'input_sha256': input_sha, 'source_group': f'group-{group}', 'hypothesis_id': hypothesis_id})
    allowlist = {'role': 'train', 'queries': 72, 'document_groups': 24, 'threeway_classes': list(HEAD.FEATURES.CLASSES), 'records': allowed}
    return records, allowlist


class HeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.allowlist = dataset()
        cls.artifact = HEAD.fit(cls.records, cls.allowlist, 'config', 'allowlist', {'model': 'synthetic'})

    def test_fixed_fit_objective_gradient_weights_and_threeway_support(self):
        artifact = self.artifact
        diagnostic = artifact['fit_diagnostics']
        self.assertEqual(len(diagnostic['history']), 400)
        self.assertLessEqual(diagnostic['final_objective'], diagnostic['initial_objective'] + 1e-8)
        self.assertLessEqual(diagnostic['final_gradient_norm'], 1e-3)
        self.assertAlmostEqual(artifact['training_total_weight'], 72)
        self.assertEqual(len(artifact['training_examples']), 216)
        head = HEAD.FrozenHead(artifact, 'config', 'allowlist', {'model': 'synthetic'})
        probabilities = head.predict(artifact['training_examples'][0]['features'], [0.8, -0.4, 0.1])
        self.assertEqual(set(probabilities), set(HEAD.FEATURES.CLASSES))
        self.assertTrue(all(value > 0 for value in probabilities.values()))
        self.assertAlmostEqual(sum(probabilities.values()), 1)

    def test_dev_confirmation_unknown_ids_input_changes_and_missing_classes_rejected(self):
        for mutation in ('dev', 'confirmation', 'id', 'input', 'missing_class', 'feature'):
            rows = copy.deepcopy(self.records)
            if mutation in ('dev', 'confirmation'):
                rows[0]['split'] = mutation
            elif mutation == 'id':
                rows[0]['id'] = 'not-in-train-contract'
            elif mutation == 'input':
                rows[0]['input']['state'] += 'Changed source.'
            elif mutation == 'missing_class':
                for row in rows:
                    row['evaluation']['original_threeway_label'] = 'Entailment'
                    row['evaluation']['gold'] = 'Yes'
            else:
                rows[0]['response']['diagnostics']['decision']['arms']['ruvector_top2']['decoding']['typed_head_features'][4] += 0.1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                HEAD.collect(rows, self.allowlist)

    def test_record_ids_and_input_order_do_not_enter_fit_features(self):
        rows, allow = copy.deepcopy(self.records), copy.deepcopy(self.allowlist)
        replacements = {row['id']: 'renamed-' + row['id'] for row in rows}
        for row in rows:
            row['id'] = replacements[row['id']]
        for row in allow['records']:
            row['id'] = replacements[row['id']]
        artifact = HEAD.fit(list(reversed(rows)), allow, 'config', 'allowlist', {'model': 'synthetic'})
        np.testing.assert_allclose(artifact['weights'], self.artifact['weights'], rtol=0, atol=1e-12)
        np.testing.assert_allclose(artifact['mean'], self.artifact['mean'], rtol=0, atol=1e-12)

    def test_logit_offset_invariance_and_deontic_features(self):
        first = HEAD.FEATURES.extract('Party shall not use copies except when permitted.', 'Party may use copies.', [1, 2, 3])
        second = HEAD.FEATURES.extract('Party shall not use copies except when permitted.', 'Party may use copies.', [11, 12, 13])
        self.assertEqual(first, second)
        self.assertEqual(first[HEAD.FEATURES.FEATURE_NAMES.index('premise_negation')], 1)
        self.assertEqual(first[HEAD.FEATURES.FEATURE_NAMES.index('premise_exception')], 1)

    def test_optimizer_failure_preserves_all_fixed_step_diagnostics(self):
        with patch.dict(HEAD.ALGORITHM, {'final_gradient_norm_max': 0.0}):
            with self.assertRaises(HEAD.FitFailure) as captured:
                HEAD.fit(self.records, self.allowlist, 'config', 'allowlist', {'model': 'synthetic'})
        diagnostic = captured.exception.diagnostics
        self.assertEqual(diagnostic['steps_completed'], 400)
        self.assertEqual(len(diagnostic['history']), 400)
        self.assertGreater(diagnostic['final_gradient_norm'], 0)

    def test_artifact_parameter_source_and_class_mapping_tamper_rejected(self):
        for field in ('weights', 'class_order', 'trainer_source_sha256'):
            changed = copy.deepcopy(self.artifact)
            if field == 'weights':
                changed[field][0][0] += 0.1
            elif field == 'class_order':
                changed[field] = list(reversed(changed[field]))
            else:
                changed[field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                HEAD.FrozenHead(changed, 'config', 'allowlist', {'model': 'synthetic'})

    def test_neutral_is_preserved_and_failed_state_blocks_before_base(self):
        calls = []
        def decode(premise, hypothesis):
            calls.append((premise, hypothesis))
            return {}, {'logits': [-5.0, 0.0, 5.0]}
        base = SimpleNamespace(label_indices={'contradiction': 0, 'entailment': 1, 'neutral': 2},
                               tokenizer=object(), receipt={}, decode=decode)
        reader = MODELS.TypedNli(base)
        binary, trace = reader.decode('Agreement term.', 'Oral information.')
        self.assertLess(binary['Yes'], 0.01)
        self.assertGreater(trace['raw_threeway_probabilities']['NotMentioned'], 0.99)
        self.assertGreater(binary['No'], 0.99)
        reader.head_state = 'FIT_FAILED'
        with self.assertRaises(ValueError):
            reader.decode('Source.', 'Claim.')
        self.assertEqual(len(calls), 1)


class RuntimeStateTests(unittest.TestCase):
    def engine(self, directory):
        reader = RUNTIME.CandidateEngine.__new__(RUNTIME.CandidateEngine)
        reader.config = json.loads((HERE / 'config.json').read_text())
        reader.training_contract_path = directory / 'contract.json'
        reader.training_contract_path.write_text('{"synthetic":true}')
        reader.config['training_contract_sha256'] = HEAD.sha(reader.training_contract_path)
        reader.training_source_path = directory / 'train72.jsonl'
        reader.training_source_path.write_text(''.join(json.dumps(row) + '\n' for row in dataset()[0]))
        reader.config['training_source_sha256'] = HEAD.sha(reader.training_source_path)
        reader.train_allowlist = dataset()[1]
        reader.head_state = 'TRAIN_COLLECTION'; reader._fit_attempted = False
        reader.fitted_head_path = None; reader.fitted_head_sha256 = None; reader.receipt = {}
        base = SimpleNamespace(label_indices={'contradiction': 0, 'entailment': 1, 'neutral': 2}, tokenizer=object(), receipt={})
        reader.nli = MODELS.TypedNli(base)
        return reader

    def test_fit_once_freeze_finalize_and_no_refit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); reader = self.engine(directory)
            target = directory / 'frozen-head.json'
            receipt = reader.fit_from_records(dataset()[0], target)
            self.assertEqual(receipt['head_state'], 'FROZEN')
            self.assertEqual(reader.finalize()['artifact_sha256'], HEAD.sha(target))
            self.assertEqual(reader.nli.head_state, 'FROZEN')
            self.assertTrue(reader.nli.receipt['typed_readout_training_fit'])
            self.assertEqual(len(json.loads(target.read_text())['cached_training_replay']), 216)
            with self.assertRaises(ValueError):
                reader.fit_from_records(dataset()[0], directory / 'second-head.json')

    def test_failed_fit_has_no_artifact_and_no_fallback_prediction(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); reader = self.engine(directory)
            records = dataset()[0]; records[0]['split'] = 'dev'
            target = directory / 'never-created.json'
            with self.assertRaises(ValueError):
                reader.fit_from_records(records, target)
            self.assertFalse(target.exists())
            self.assertEqual(reader.head_state, 'FIT_FAILED')
            self.assertFalse(reader.receipt['fit_failure']['DEV_or_confirmation_permitted'])
            with self.assertRaises(ValueError):
                reader.predict('Source.', {})

    def test_cached_label_tamper_rejected_against_train_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); reader = self.engine(directory)
            records = dataset()[0]
            records[0]['evaluation'] = {'original_threeway_label': 'NotMentioned', 'gold': 'No'}
            with self.assertRaises(ValueError):
                reader.fit_from_records(records, directory / 'never-created.json')
            self.assertEqual(reader.head_state, 'FIT_FAILED')


if __name__ == '__main__':
    unittest.main()
