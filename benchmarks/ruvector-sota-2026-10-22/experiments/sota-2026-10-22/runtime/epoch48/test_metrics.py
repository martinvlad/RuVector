"""Authored arithmetic/guard fixtures only; no benchmark data or model runtime."""
import copy
import json
import math
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
M = runpy.run_path(str(HERE / 'evaluate.py'), run_name='e48_fixture_metrics')
S = runpy.run_path(str(HERE / 'phase_runner.py'), run_name='e48_fixture_supervisor')


def fixture(control_errors=2):
    ids = ['authored-fixture:' + str(i) for i in range(12)]
    labels = {case: M['LABELS'][i % 3] for i, case in enumerate(ids)}
    rows = []
    for i, case in enumerate(ids):
        for arm in M['ARMS']:
            winner = i % 3 if arm == 'native' or i >= control_errors else (i + 1) % 3
            logits = [8.0 if j == winner else 0.0 for j in range(3)]
            probs, logs = M['scores'](logits)
            rows.append({'case_id': case, 'document_id': 1000 + i // 3,
                         'hypothesis_id': 'authored-' + str(i % 3), 'arm': arm,
                         'logits': logits, 'probabilities': probs, 'log_probabilities': logs,
                         'prediction': M['LABELS'][winner], 'elapsed_seconds': float(i + 1)})
    return ids, labels, rows


def rejected(call):
    try:
        call()
    except AssertionError:
        return
    raise AssertionError('Invalid fixture should have failed closed')


def main():
    cases = []
    p, logs = M['scores']([-1000.0, 0.0, -1.0])
    assert p[0] == 0.0 and -logs[0] > 1000 and math.isfinite(-logs[0])
    cases.append('unclipped_stable_NLL_even_when_probability_underflows')
    ids, labels, rows = fixture(2)
    result = M['evaluate_rows'](rows, labels, ids)
    assert result['point_gates_passed'] and result['metrics']['native']['correct'] == 12
    assert result['metrics']['lexical']['correct'] == 10
    assert result['metrics']['native']['latency_seconds']['p50'] == 6.5
    assert math.isclose(result['metrics']['native']['latency_seconds']['p95'], 11.45)
    cases.append('two_correct_gain_and_proper_scores_with_linear_quantiles')
    ids, labels, rows = fixture(1)
    assert not M['evaluate_rows'](rows, labels, ids)['point_gates_passed']
    cases.append('one_correct_gain_fails_frozen_acceptance')
    duplicate = copy.deepcopy(rows)
    duplicate[3] = copy.deepcopy(duplicate[0])
    rejected(lambda: M['evaluate_rows'](duplicate, labels, ids))
    cases.append('duplicate_case_cannot_inflate_N')
    inconsistent = copy.deepcopy(rows)
    inconsistent[0]['probabilities'][0] = .5
    rejected(lambda: M['evaluate_rows'](inconsistent, labels, ids))
    cases.append('inconsistent_captured_probability_fails')
    original = S['os'].killpg
    try:
        def gone(*args):
            raise ProcessLookupError('authored race')
        S['os'].killpg = gone
        S['signal_owned_group'](999999, 15)
        def denied(*args):
            raise PermissionError('authored non-race error')
        S['os'].killpg = denied
        try:
            S['signal_owned_group'](999999, 15)
        except PermissionError:
            pass
        else:
            raise AssertionError('Only a disappeared owned group may be ignored')
    finally:
        S['os'].killpg = original
    cases.append('only_own_group_disappearance_is_ignored_no_signal_sent')
    print(json.dumps({'checks_passed': True, 'authored_fixtures': len(cases), 'cases': cases,
                      'benchmark_cases_read': 0, 'model_tokenizer_native_initializations': 0,
                      'actual_signals_sent': 0, 'scope': 'Source arithmetic and lifecycle guard fixtures, not benchmark results.'}))


if __name__ == '__main__':
    main()
