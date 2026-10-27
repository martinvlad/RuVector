"""Inert invented scoring/runtime metadata and AST tests; no main, data, Gold or models."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location('e50_inert_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

E = load('evaluate'); P = load('phase_runner'); L = load('launch_phase_once')


def receipt():
    audit = {'model_id': 'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli',
        'model_revision': '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed',
        'source_revision': '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed',
        'model_weight_sha256': 'a51c55cb7dc41c4c862f06a3d9c413a8aa0619222bc56f06cb6f2f5b2d3ee14a',
        'learned_state_tensor_count': 395, 'source_tensor_elements': 356412419,
        'unsafe_load_fallback': False, 'custom_remote_code': False,
        'removed_learned_or_nonlearned_state_keys': [], 'missing_keys': [], 'unexpected_keys': [],
        'mismatched_keys': [], 'torch_threads': 2, 'torch_interop_threads': 1,
        'nonpersistent_buffers': {key: {'shape': [1, 514], 'dtype': 'int64', 'device': 'cpu', 'persistent': False}
                                  for key in ['position_ids', 'token_type_ids']}}
    for key in ['learned_state_keys_exact', 'weights_only', 'mmap', 'assign', 'meta_constructor',
                'all_395_state_tensor_data_pointers_match_mmap_source',
                'all_original_learned_pooler_and_classifier_tensors_retained', 'FP32_CPU_eval']:
        audit[key] = True
    counters = dict.fromkeys(['NLI_forwards_attempted', 'NLI_forwards_completed', 'forecasts_completed'], 36)
    counters.update(dict.fromkeys(['native_corpus_batches_attempted', 'native_corpus_batches_completed',
                                  'native_corpus_batches', 'reader_initializations_attempted',
                                  'reader_initializations_completed'], 1))
    counters.update(dict.fromkeys(['training_calls', 'calibration_calls', 'paid_API_calls', 'GPU_calls',
        'semantic_gold_decodes', 'Node_network_operations_attempted', 'Python_network_operations_attempted',
        'Python_network_operations_blocked'], 0))
    network = {'all_audited_operations_denied_before_IO': True, 'audited_successful_network_operations': 0,
        'admissible': True, 'unexpected_blocked_attempts': 0, 'blocked_optional_import_bind_probes': 0,
        'event_counts': {}, 'stage_event_counts': {}, 'public_socket_wrappers_installed':
        ['socket.bind', 'socket.connect', 'socket.sendall', 'socket.recv', 'socket.accept', 'socket.getaddrinfo']}
    return {'loading_audit': audit, 'counters': counters, 'network_audit': network}


class AdapterTests(unittest.TestCase):
    def test_all_schemas_new_epoch_kind_and_owner_lease(self):
        for name in ['phase_runner', 'evaluate', 'launch_phase_once']:
            source = (HERE / (name + '.py')).read_text(); tree = ast.parse(source)
            self.assertIn('REAL_CONTRACTNLI_ROBERTA_FAITHFUL_MMAP_TRANSFER_PILOT', source)
            self.assertIn('158817', source); self.assertIn('38479788', source)
            self.assertNotIn("['generation'] == 13", source)
            self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom)) and
                any(x in ast.unparse(n) for x in ['torch', 'transformers', 'onnxruntime', 'packing', 'reader'])
                for n in ast.walk(tree)))
            self.assertTrue(any(isinstance(n, ast.If) and '__name__' in ast.unparse(n.test) for n in tree.body))

    def test_both_outer_phases_have_separate_once_journals_and_ordinal(self):
        self.assertEqual(L.phase_spec('dev'), {'phase': 'dev', 'prefix': 'DEV', 'native_batch_ordinal': 1})
        self.assertEqual(L.phase_spec('confirmation'), {'phase': 'confirmation', 'prefix': 'CONF', 'native_batch_ordinal': 2})
        with self.assertRaises(AssertionError): L.phase_spec('unknown')
        source = (HERE / 'launch_phase_once.py').read_text()
        self.assertIn("parser.add_argument('--phase', choices=['dev', 'confirmation'], required=True)", source)
        self.assertIn("plan['phase_slots'][phase]['token']", source)
        self.assertIn("acceptance['checks_passed'] is True and acceptance['dev_passed'] is True", source)
        self.assertIn("ad['confirmation_materialization_authorized'] is True", source)
        self.assertIn("acceptance['plan_sha256'] == intent['plan_ref']['sha256']", source)
        self.assertIn("intent['argv'].count('--phase') == 1", source)
        for name in ['OUTER_LAUNCH_ATTEMPT.v1.json', 'SUPERVISOR_STARTED.actual.v1.json',
                     'PHYSICAL_CLOSURE.actual.v1.json', 'OUTER_EXECUTION.actual.v1.json']:
            self.assertIn("prefix + '_" + name + "'", source)
        self.assertNotIn("phase='dev'", source)
        self.assertNotIn("W / 'runs/dev'", source)
        self.assertNotIn("W / 'private-run/dev'", source)

    def test_source_paths_canonical_and_traversal_rejected(self):
        for module in [P, E]:
            self.assertEqual(module.canonical_relative('experiments/a.py'), Path('experiments/a.py'))
            for value in ['', '/absolute', '../x', 'a/../b', 'a//b', './x', 'a\\b']:
                with self.assertRaises(AssertionError, msg=value): module.canonical_relative(value)

    def test_faithful_runtime_required_before_gold(self):
        self.assertTrue(E.validate_runtime_receipt(receipt()))
        for key in ['mmap', 'assign', 'meta_constructor', 'all_original_learned_pooler_and_classifier_tensors_retained']:
            raw = receipt(); raw['loading_audit'][key] = False
            with self.assertRaises(AssertionError, msg=key): E.validate_runtime_receipt(raw)
        source = (HERE / 'evaluate.py').read_text()
        self.assertLess(source.index('validate_runtime_receipt(raw)  # Mandatory'),
                        source.index("gold = json.loads(exact(admission['joined_gold_ref']))"))

    def test_only_one_denied_import_probe_is_distinguished(self):
        raw = receipt(); raw['counters']['Python_network_operations_attempted'] = 1
        raw['counters']['Python_network_operations_blocked'] = 1
        raw['network_audit'].update(blocked_optional_import_bind_probes=1,
            event_counts={'socket.bind': 1}, stage_event_counts={'reader_transformers_import': {'socket.bind': 1}})
        self.assertTrue(E.validate_runtime_receipt(raw))
        for stage in ['nli_forecasts', 'bge_initialization_and_embedding']:
            bad = copy.deepcopy(raw); bad['network_audit']['stage_event_counts'] = {stage: {'socket.bind': 1}}
            with self.assertRaises(AssertionError): E.validate_runtime_receipt(bad)
        raw['network_audit']['audited_successful_network_operations'] = 1
        with self.assertRaises(AssertionError): E.validate_runtime_receipt(raw)

    def test_invented_score_recomputation_and_ablation_gates(self):
        ids = []; labels = {}; rows = []
        for doc in [901, 902, 903, 904]:
            for index, hyp in enumerate(['nda-1', 'nda-10', 'nda-16']):
                ident = str(doc) + ':' + hyp; ids.append(ident); labels[ident] = E.LABELS[index]
                logits = [-2.0, -2.0, -2.0]; logits[index] = 2.0
                probs, logs = E.scores(logits)
                for arm in E.ARMS:
                    rows.append({'case_id': ident, 'document_id': doc, 'hypothesis_id': hyp, 'arm': arm,
                        'logits': logits, 'probabilities': probs, 'log_probabilities': logs,
                        'prediction': E.LABELS[index], 'elapsed_seconds': .25})
        result = E.evaluate_rows(rows, labels, ids)
        self.assertEqual([result['metrics'][x]['correct'] for x in E.ARMS], [12, 12, 12])
        self.assertFalse(result['point_gates_passed'])  # Equal controls cannot pass frozen two-correct gain.
        self.assertEqual(result['descriptive_uncertainty']['seed'], 48)
        bad = copy.deepcopy(rows); bad[0]['probabilities'] = [1.0, 0.0, 0.0]
        with self.assertRaises(AssertionError): E.evaluate_rows(bad, labels, ids)

    def test_one_shot_and_layered_deadlines_preserved(self):
        runner = (HERE / 'phase_runner.py').read_text(); outer = (HERE / 'launch_phase_once.py').read_text()
        for text in ['start + 570', 'elapsed >= 580', 'elapsed >= 600', 'no_retry_after_any_failure']:
            self.assertIn(text, runner)
        for text in ['elapsed >= 590', 'elapsed >= 595', 'elapsed >= 600', 'automatic_retry=False',
                     'all_owned_experiment_processes_physically_closed', 'FDSize', 'statm']:
            self.assertIn(text, outer)
        for name in ['BLIS_NUM_THREADS', 'MKL_DYNAMIC', 'OMP_THREAD_LIMIT', 'RAYON_NUM_THREADS',
                     'UV_THREADPOOL_SIZE', 'VECLIB_MAXIMUM_THREADS']:
            self.assertIn(name, runner); self.assertIn(name, outer)
        self.assertNotIn('0a56e084a7a70e2153ee00f82e6b652abbdc23dfde55bd78b70c08a7d70cf8ea', outer)
        self.assertNotIn('a6769974cdb1aae98c8deec30e6b0ff985dc5c7da7a93f1d66bd91d5feb740a3', outer)


if __name__ == '__main__':
    unittest.main()
