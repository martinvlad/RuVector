"""Prelabel fault-injection tests of saved receipts; no processes are run."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch17_process_under_test',
                                               HERE / 'process_v1.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def receipts():
    plan = {'limits': {'threads': 2, 'seconds_per_batch': 600,
                       'paid_calls': 0, 'GPU_calls': 0},
            'lease_expires_unix': 2000,
            'runtime_admission': {
                'formula_id': '24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
                'max_DEV_units': 2, 'max_confirmation_units': 4}}
    invocation = {'source_plan_sha256': 'a' * 64,
                  'new_study_native_attempt': 1, 'lifetime_native_attempt': 19,
                  'automatic_retry': False}
    attempt = {**invocation, 'phase': 'development', 'pid': 43210, 'pgid': 43210,
               'invocation_started_unix': 1000,
               'model_deadline_unix': 1590, 'hard_cleanup_deadline_unix': 1600}
    completion = {'exit_code': 0, 'error': None, 'prior_closed_attempts': 18,
                  'source_plan_unchanged': True,
                  'wall_seconds_including_model_load': 100,
                  'owned_group_cleanup': {
                      'pgid': 43210, 'live_members_after': [],
                      'finished_within_deadline': True,
                      'hard_cleanup_deadline_unix': 1600,
                      'finished_unix': 1100}}
    runtime = {'model_initialization_in_batch': True,
               'native_child_pids': [43211], 'phase_initialization_seconds': 2,
               'receipt': {'initialization_wall_seconds': 1.5},
               'at': '1970-01-01T00:16:42+00:00'}
    resources = {'allowed_CPU_ids': [4, 5], 'configured_ORT_threads': 2,
                 'configured_torch_threads': 2,
                 'configured_torch_interop_threads': 1,
                 'worker_cpu_user_seconds': 90, 'worker_cpu_system_seconds': 2,
                 'worker_peak_RSS_bytes': 1000000,
                 'terminated_children_cpu_user_seconds': 3,
                 'terminated_children_cpu_system_seconds': 1,
                 'largest_terminated_child_peak_RSS_bytes': 400000}
    cleanup = {'engine_close_called': True, 'native_child_pids_absent': True,
               'cleanup_errors': []}
    return {'plan': plan, 'phase': 'development', 'plan_sha': 'a' * 64,
            'invocation': invocation, 'attempt': attempt,
            'completion': completion, 'runtime': runtime,
            'resources': resources, 'cleanup': cleanup,
            'n_records': 24, 'n_wire': 24, 'n_started': 24}


def counts(requests=24):
    observed = {'requests': requests, 'NLI_tokens': 123 * requests,
                'BGE_texts': 4 * requests, 'BGE_batches': 2 * requests}
    base = {'requests': requests, 'native104_requests': requests,
            'native_core_searches': requests, 'context_partitions': requests,
            'context_packs': 3 * requests, 'nli_forward_pairs': 4 * requests,
            'new_reader_forward_pairs': 3 * requests,
            'previous_reader_forward_pairs': requests,
            'nli_input_tokens': observed['NLI_tokens'],
            'bge_texts': observed['BGE_texts'],
            'bge_forward_batches': observed['BGE_batches']}
    counters = {key + suffix: value for key, value in base.items()
                for suffix in ('_attempted', '_completed')}
    return counters, observed


class ProcessEvidenceTests(unittest.TestCase):
    def test_complete24_and_confirmation_attempt20(self):
        self.assertTrue(p.phase_evidence(**receipts()))
        data = receipts()
        data['phase'] = 'confirmation'
        for key in ('invocation', 'attempt'):
            data[key]['new_study_native_attempt'] = 2
            data[key]['lifetime_native_attempt'] = 20
        data['attempt']['phase'] = 'confirmation'
        self.assertTrue(p.phase_evidence(**data))

    def test_partial_two_queries_preserves_evidence_without_acceptance(self):
        data = receipts()
        data.update(n_records=2, n_wire=2, n_started=3)
        data['completion']['exit_code'] = 1
        data['completion']['error'] = 'generic interruption'
        self.assertFalse(p.phase_evidence(**data))

    def test_initialization_failure_and_zero_queries_are_not_acceptance(self):
        data = receipts()
        data.update(runtime=None, resources=None, cleanup=None,
                    n_records=0, n_wire=0, n_started=0)
        data['completion']['exit_code'] = 1
        data['completion']['error'] = 'generic initialization failure'
        self.assertFalse(p.phase_evidence(**data))

    def test_no_pid_uncertain_mutation_is_not_acceptance_or_evidence_of_no_work(self):
        data = receipts()
        data.update(attempt=None, runtime=None, resources=None, cleanup=None,
                    n_records=0, n_wire=0, n_started=0)
        data['completion']['exit_code'] = 1
        data['completion']['error'] = 'uncertain returned PID'
        self.assertFalse(p.phase_evidence(**data))
        data['completion']['exit_code'] = 0
        data['completion']['error'] = None
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)
        data['completion']['exit_code'] = 1
        data['completion']['error'] = 'uncertain returned PID'
        data['n_started'] = 1
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)

    def test_wrong_plan_retry_phase_and_attempt_numbers_fail(self):
        for location, field, value in (
                ('invocation', 'source_plan_sha256', 'b' * 64),
                ('attempt', 'source_plan_sha256', 'b' * 64),
                ('invocation', 'automatic_retry', True),
                ('attempt', 'automatic_retry', True),
                ('invocation', 'new_study_native_attempt', 2),
                ('attempt', 'lifetime_native_attempt', 20),
                ('attempt', 'phase', 'confirmation')):
            data = receipts()
            data[location][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        data = receipts()
        data['phase'] = 'not-a-phase'
        data['attempt']['phase'] = 'not-a-phase'
        for key in ('invocation', 'attempt'):
            data[key]['new_study_native_attempt'] = 2
            data[key]['lifetime_native_attempt'] = 20
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)

    def test_record_order_partial_counts_and_complete24_fail_closed(self):
        for values in ((24, 24, 23), (25, 25, 25), (-1, 0, 0), (23, 24, 24),
                       (24, 23, 24)):
            data = receipts()
            data.update(zip(('n_records', 'n_wire', 'n_started'), values))
            with self.subTest(values=values), self.assertRaises(AssertionError):
                p.phase_evidence(**data)

    def test_two_cpu_thread_and_zero_paid_gpu_guards(self):
        for field, bad in (('allowed_CPU_ids', [1, 2, 3]),
                           ('allowed_CPU_ids', [1, 1]), ('allowed_CPU_ids', [True]),
                           ('allowed_CPU_ids', []), ('configured_ORT_threads', 3),
                           ('configured_torch_threads', 3),
                           ('configured_torch_interop_threads', 2),
                           ('worker_cpu_user_seconds', -1),
                           ('worker_peak_RSS_bytes', float('nan'))):
            data = receipts()
            data['resources'][field] = bad
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        for field, bad in (('threads', 3), ('seconds_per_batch', 601),
                           ('paid_calls', 1), ('GPU_calls', 1)):
            data = receipts()
            data['plan']['limits'][field] = bad
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.phase_evidence(**data)

    def test_deadline_init_wall_and_lease_guards(self):
        for location, field, bad in (
                ('completion', 'wall_seconds_including_model_load', 600.1),
                ('completion', 'wall_seconds_including_model_load', 1.9),
                ('attempt', 'hard_cleanup_deadline_unix', 1600.1),
                ('attempt', 'model_deadline_unix', 1600),
                ('attempt', 'invocation_started_unix', -1),
                ('runtime', 'phase_initialization_seconds', 0),
                ('runtime', 'phase_initialization_seconds', 2.2),
                ('runtime', 'at', '1970-01-01T00:26:40+00:00')):
            data = receipts()
            data[location][field] = bad
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        data = receipts()
        data['plan']['lease_expires_unix'] = 1629
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)
        data = receipts()
        data['runtime']['receipt']['initialization_wall_seconds'] = -1
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)

    def test_owned_cleanup_and_missing_complete_evidence_fail(self):
        for field, bad in (('live_members_after', [43210]),
                           ('finished_within_deadline', False),
                           ('finished_within_deadline', 'false'),
                           ('pgid', 99), ('hard_cleanup_deadline_unix', 1599),
                           ('finished_unix', 1600.1), ('finished_unix', -1)):
            data = receipts()
            data['completion']['owned_group_cleanup'][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        for field, bad in (('engine_close_called', False),
                           ('engine_close_called', 'false'),
                           ('native_child_pids_absent', False),
                           ('native_child_pids_absent', 'false'),
                           ('cleanup_errors', ['generic error'])):
            data = receipts()
            data['cleanup'][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        for field in ('attempt', 'runtime', 'resources', 'cleanup'):
            data = receipts()
            data[field] = None
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.phase_evidence(**data)
        data = receipts()
        data['completion']['source_plan_unchanged'] = 'false'
        with self.assertRaises(AssertionError):
            p.phase_evidence(**data)

    def test_actual_owned_worker_and_child_must_be_dead(self):
        data = receipts()
        for live_pid in (43210, 43211):
            with self.subTest(live_pid=live_pid), self.assertRaises(AssertionError):
                p.phase_evidence(**data, process_live=lambda pid: pid == live_pid)


class CounterEvidenceTests(unittest.TestCase):
    def test_complete_exact_four_equals_three_plus_one_per_request(self):
        counters, observed = counts()
        expected = p.counters_evidence(counters, observed, True)
        self.assertEqual(expected['nli_forward_pairs'], 96)
        self.assertEqual(expected['new_reader_forward_pairs'], 72)
        self.assertEqual(expected['previous_reader_forward_pairs'], 24)

    def test_hidden_extra_forward_warmup_is_detected_on_complete(self):
        counters, observed = counts()
        for suffix in ('_attempted', '_completed'):
            counters['nli_forward_pairs' + suffix] += 1
            counters['new_reader_forward_pairs' + suffix] += 1
        with self.assertRaises(AssertionError):
            p.counters_evidence(counters, observed, True)

    def test_partial_counters_lower_bound_saved_rows_and_preserve_extra_work(self):
        counters, observed = counts(2)
        counters['nli_forward_pairs_attempted'] += 1
        counters['new_reader_forward_pairs_attempted'] += 1
        p.counters_evidence(counters, observed, False)
        for field, bad in (('requests_completed', 1),
                           ('nli_input_tokens_completed', 0),
                           ('native_core_searches_attempted', 1),
                           ('native104_requests_completed', True)):
            changed = dict(counters)
            changed[field] = bad
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.counters_evidence(changed, observed, False)

    def test_forward_partition_mismatch_and_negative_counts_fail(self):
        for field, value in (('nli_forward_pairs_attempted', 97),
                             ('previous_reader_forward_pairs_completed', 25),
                             ('bge_texts_completed', -1)):
            counters, observed = counts()
            counters[field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                p.counters_evidence(counters, observed, False)


class RuntimeForecastTests(unittest.TestCase):
    def test_frozen_unit_ratio_init_and_sixty_second_reserve(self):
        plan = receipts()['plan']
        projected, admitted = p.runtime_forecast(plan, maximum_http=5,
                                                initialization=10, at_unix=1000)
        self.assertEqual(projected, 24 * 5 * 2 + 2 * 10 + 60)
        self.assertTrue(admitted)
        plan['runtime_admission']['max_confirmation_units'] = 1
        self.assertEqual(p.runtime_forecast(plan, 5, 10, 1000)[0], 200)

    def test_runtime_and_lease_boundaries_fail_without_retry(self):
        plan = receipts()['plan']
        projected, admitted = p.runtime_forecast(plan, 11, 10, 1000)
        self.assertEqual(projected, 608)
        self.assertFalse(admitted)
        # Exactly projected+30 seconds remaining passes; one less does not.
        plan['lease_expires_unix'] = 1350
        self.assertTrue(p.runtime_forecast(plan, 5, 10, 1000)[1])
        plan['lease_expires_unix'] = 1349
        self.assertFalse(p.runtime_forecast(plan, 5, 10, 1000)[1])

    def test_wrong_formula_zero_values_and_bad_units_fail(self):
        for maximum_http, initialization in ((0, 1), (1, 0), (-1, 1),
                                               (float('nan'), 1), (True, 1)):
            with self.assertRaises(AssertionError):
                p.runtime_forecast(receipts()['plan'], maximum_http, initialization, 1000)
        for key, value in (('formula_id', 'other'), ('max_DEV_units', 0),
                            ('max_confirmation_units', True)):
            plan = receipts()['plan']
            plan['runtime_admission'][key] = value
            with self.assertRaises(AssertionError):
                p.runtime_forecast(plan, 5, 10, 1000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
