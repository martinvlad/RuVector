"""Independent saved process/budget invariants, pure and prelabel testable."""
from datetime import datetime
import math


def finite_nonnegative(value):
    assert type(value) in (int, float) and math.isfinite(value) and value >= 0
    return value


def phase_evidence(plan, phase, plan_sha, invocation, attempt, completion,
                   runtime, resources, cleanup, n_records, n_wire, n_started,
                   process_live=lambda pid: False):
    assert phase in ('development', 'confirmation')
    number = 1 if phase == 'development' else 2
    assert invocation['source_plan_sha256'] == plan_sha
    assert invocation['new_study_native_attempt'] == number
    assert invocation['lifetime_native_attempt'] == 18 + number
    assert invocation['automatic_retry'] is False
    assert 0 <= n_records <= n_wire <= n_started <= 24
    assert plan['limits']['threads'] == 2 and plan['limits']['seconds_per_batch'] == 600
    assert plan['limits']['paid_calls'] == plan['limits']['GPU_calls'] == 0
    if attempt:
        assert attempt['new_study_native_attempt'] == number
        assert attempt['lifetime_native_attempt'] == 18 + number
        assert attempt['source_plan_sha256'] == plan_sha
        assert attempt['phase'] == phase and attempt['automatic_retry'] is False
        assert type(attempt['pid']) is int and attempt['pid'] > 1
        assert attempt['pid'] == attempt['pgid'] and not process_live(attempt['pid'])
        start = finite_nonnegative(attempt['invocation_started_unix'])
        hard = finite_nonnegative(attempt['hard_cleanup_deadline_unix'])
        model = finite_nonnegative(attempt['model_deadline_unix'])
        assert start < model < hard <= plan['lease_expires_unix'] - 30
        assert hard - start <= 600
    if runtime:
        assert attempt, 'Runtime requires durable returned-PID attempt evidence'
        assert runtime['model_initialization_in_batch'] is True
        assert all(not process_live(pid) for pid in runtime['native_child_pids'])
        initialization = finite_nonnegative(runtime['phase_initialization_seconds'])
        assert initialization > 0
        engine_initialization = finite_nonnegative(runtime['receipt']['initialization_wall_seconds'])
        assert engine_initialization > 0 and initialization >= engine_initialization
        observed = datetime.fromisoformat(runtime['at']).timestamp() - start
        assert abs(initialization-observed) <= .1
        assert datetime.fromisoformat(runtime['at']).timestamp() < model
    if resources:
        allowed = resources['allowed_CPU_ids']
        assert 1 <= len(allowed) <= 2 and len(set(allowed)) == len(allowed)
        assert all(type(x) is int and x >= 0 for x in allowed)
        assert resources['configured_ORT_threads'] == resources['configured_torch_threads'] == 2
        assert resources['configured_torch_interop_threads'] == 1
        for key in ('worker_cpu_user_seconds', 'worker_cpu_system_seconds',
                    'worker_peak_RSS_bytes', 'terminated_children_cpu_user_seconds',
                    'terminated_children_cpu_system_seconds',
                    'largest_terminated_child_peak_RSS_bytes'):
            finite_nonnegative(resources[key])
    complete = bool(completion and completion['exit_code'] == 0 and completion['error'] is None)
    if completion:
        assert completion['prior_closed_attempts'] == 18 and completion['source_plan_unchanged'] is True
        assert finite_nonnegative(completion['wall_seconds_including_model_load']) <= 600
        group = completion['owned_group_cleanup']
        assert not group['live_members_after'] and group['finished_within_deadline'] is True
        if attempt:
            assert group['pgid'] == attempt['pgid']
            assert group['hard_cleanup_deadline_unix'] == hard
            assert start <= finite_nonnegative(group['finished_unix']) <= hard
        else:
            assert not runtime and n_records == n_wire == n_started == 0
            assert not complete, 'Uncertain Popen without PID receipt can never pass'
    if complete:
        assert attempt and runtime and resources and cleanup
        assert n_records == n_wire == n_started == 24
        assert cleanup['engine_close_called'] is True and cleanup['native_child_pids_absent'] is True
        assert not cleanup['cleanup_errors']
        assert runtime['phase_initialization_seconds'] < completion['wall_seconds_including_model_load']
    return complete


def counters_evidence(counters, observed, complete):
    """Observed saved rows lower-bound partial work, equal all work if complete."""
    requests = observed['requests']
    expected = {'requests': requests, 'native104_requests': requests,
                'native_core_searches': requests, 'context_partitions': requests,
                'context_packs': 3*requests, 'nli_forward_pairs': 4*requests,
                'new_reader_forward_pairs': 3*requests,
                'previous_reader_forward_pairs': requests,
                'nli_input_tokens': observed['NLI_tokens'],
                'bge_texts': observed['BGE_texts'],
                'bge_forward_batches': observed['BGE_batches']}
    for key, minimum in expected.items():
        attempted, completed = counters[key+'_attempted'], counters[key+'_completed']
        assert type(attempted) is int and type(completed) is int
        assert attempted >= completed >= minimum >= 0, key
        if complete:
            assert attempted == completed == minimum, key
    assert counters['nli_forward_pairs_attempted'] == (
        counters['new_reader_forward_pairs_attempted'] + counters['previous_reader_forward_pairs_attempted'])
    assert counters['nli_forward_pairs_completed'] == (
        counters['new_reader_forward_pairs_completed'] + counters['previous_reader_forward_pairs_completed'])
    return expected


def runtime_forecast(plan, maximum_http, initialization, at_unix):
    frozen = plan['runtime_admission']
    assert frozen['formula_id'] == '24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1'
    assert finite_nonnegative(maximum_http) > 0 and finite_nonnegative(initialization) > 0
    assert all(type(frozen[k]) is int and frozen[k] > 0
               for k in ('max_DEV_units', 'max_confirmation_units'))
    projected = (24*maximum_http*max(1., frozen['max_confirmation_units']/frozen['max_DEV_units'])
                 + 2*initialization + 60)
    return projected, projected <= 600 and plan['lease_expires_unix']-at_unix >= projected+30
