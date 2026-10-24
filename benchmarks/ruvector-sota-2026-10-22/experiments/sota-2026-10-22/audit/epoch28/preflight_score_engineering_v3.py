"""Pure stdlib format and failure-binding tests; never runs a candidate."""
import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'score_engineering_v3.py'
ast.parse(SOURCE.read_text())
spec = importlib.util.spec_from_file_location('e28_pure_scorer_preflight', SOURCE)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)
checks = ['AST_parse']
assert scorer.metric_na()['NLL'] is None and scorer.metric_na()['Brier'] is None
assert scorer.metric_na()['benchmark_accuracy'] is None and scorer.metric_na()['proper_score_metric_computations'] == 0
checks.append('metrics_NA_without_invented_probabilities')
assert math.isclose(scorer.quantile([0., 1., 2., 3.], .95), 2.85, abs_tol=1e-12)
checks.append('latency_quantile_interpolation')
question = {'type': 'choice', 'criteria': {'Yes': 'predicate', 'No': 'not predicate'}}
valid = {'type': 'choice', 'calibrated': False, 'choice': 'Yes', 'probabilities': {'Yes': .7, 'No': .3}}
assert scorer.answer_valid(valid, question)
checks.append('original_choice_label_map_valid')
mutations = [
    ('missing_label', lambda x: x.update(probabilities={'Yes': 1.})),
    ('extra_label', lambda x: x['probabilities'].update(Other=0.)),
    ('mass', lambda x: x.update(probabilities={'Yes': .7, 'No': .7})),
    ('bool', lambda x: x.update(probabilities={'Yes': True, 'No': 0.})),
    ('choice', lambda x: x.update(choice='Other'))]
for label, mutate in mutations:
    bad = copy.deepcopy(valid)
    mutate(bad)
    assert not scorer.answer_valid(bad, question)
    checks.append('reject_choice_' + label)
assert scorer.answer_valid({'type': 'noul', 'calibrated': False, 'noul': .5,
    'probabilities': {'yes': .5, 'no': .5}}, {'type': 'noul'})
checks.append('uncalibrated_noul_kept_as_score')

with tempfile.TemporaryDirectory(prefix='scorer-preflight-', dir=HERE) as temporary:
    root = Path(temporary)

    def put(name, value):
        path = root/name
        path.write_text(json.dumps(value))
        return path

    for partial in [False, True]:
        raw = {'counters': {'native_systemOne_requests': 3}, 'requests': [], 'errors': []} if partial else None
        raw_path = root/('raw.partial.json' if partial else 'raw.json')
        if partial:
            put(raw_path.name, raw)
        execution = {'status': 'WORKER_FAILED_OR_TIMEOUT', 'exit_code': 2,
            'raw_sha256': None, 'raw_bytes': None,
            'raw_operation_counters': raw['counters'] if partial else None,
            'raw_operation_counters_source': 'raw.partial.json' if partial else 'UNKNOWN',
            'operation_counts_complete': False, 'backend_execution_since_checkpoint': 'UNKNOWN',
            'partial_raw_sha256': scorer.sha(raw_path) if partial else None,
            'partial_raw_bytes': raw_path.stat().st_size if partial else None,
            'owned_live_processes_closed': True, 'owned_live_group_members': []}
        execution_path = put('execution.json', execution)
        plan_path = put('plan.json', {'pins': []})
        args = SimpleNamespace(project=root, raw=raw_path, execution=execution_path, plan=plan_path)
        replay = scorer.preserved_failure(args, ValueError('captured incomplete execution'))
        assert replay['checks_passed'] is False and replay['engineering_qualified'] is False
        assert replay['failure_provenance_checks_passed'] is True
        assert replay['actual_API_counters'] == (raw['counters'] if partial else None)
        assert (replay['evidence']['raw'] is not None) is partial
        checks.append('preserve_' + ('known_partial_counts_not_complete' if partial else 'absent_counts_unknown_not_zero'))
        actual = {'parsed_raw_available': partial, 'operation_counts_complete': False,
            'backend_execution_since_checkpoint': 'UNKNOWN', 'errors': 0 if partial else None}
        if partial:
            actual.update(raw['counters'])
        results = {'epoch': 28, 'kind': scorer.KIND, 'engineering_qualified': False,
            'metrics': scorer.metric_na(), 'benchmark_accepted': False,
            'champion_promoted': False, 'new_submission': False, 'actual_execution': actual}
        replay_path, results_path = put('replay.json', replay), put('RESULTS.json', results)
        binding_args = SimpleNamespace(project=root, replay=replay_path, results=results_path)
        original = scorer.derive_actual_with_frozen_helper
        scorer.derive_actual_with_frozen_helper = lambda *args: (actual, {'path': 'mocked_pure_helper'})
        try:
            bound = scorer.bind(binding_args)
            assert bound['checks_passed'] is True and bound['publication_binding_checks_passed'] is True
            assert bound['evaluated_integrity_checks_passed'] is False and bound['engineering_qualified'] is False
            checks.append('binding_preserves_failed_evaluation_' + ('partial' if partial else 'absent'))
            for label, mutate in [
                ('qualification', lambda x: x.update(engineering_qualified=True)),
                ('invented_NLL', lambda x: x['metrics'].update(NLL=0.)),
                ('changed_counts', lambda x: x['actual_execution'].update(errors=9))]:
                bad = copy.deepcopy(results)
                mutate(bad)
                put('RESULTS.json', bad)
                try:
                    scorer.bind(binding_args)
                except ValueError:
                    checks.append('reject_' + label + '_' + ('partial' if partial else 'absent'))
                else:
                    raise AssertionError(label)
        finally:
            scorer.derive_actual_with_frozen_helper = original

with tempfile.TemporaryDirectory(prefix='actual-helper-regression-', dir=HERE) as temporary:
    root = Path(temporary)
    relative = 'experiments/sota-2026-10-22/epoch28/publication'
    source_publication = Path('/tmp/ruvector-sota-2026-10-22/epoch28-aa09a8d75110/project')/relative
    destination = root/relative
    destination.mkdir(parents=True)
    pins = []
    for name in ['stage_publication_v1.py', 'publication_common_v1.py']:
        path = destination/name
        path.write_bytes((source_publication/name).read_bytes())
        pins.append(scorer.identity(path, root))
    assert pins[0]['sha256'] == scorer.PUBLICATION_HELPER_SHA == '5b7d569902b5df3aeb4b4af45104c90807f97203a4ed78356bd4ab3bcb99511c'
    def save(name, value):
        path = root/name
        path.write_text(json.dumps(value))
        return path
    final, partial = root/'raw.json', root/'raw.partial.json'
    final.write_bytes(b'{"captured_interruption":')
    raw = {'epoch': 28, 'kind': scorer.KIND, 'phase': 'engineering',
        'source_checkpoint': '585c476cec6011b1db9c79147e3b0ff80124a6a3',
        'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []},
        'counters': {'native_systemOne_requests': 3}, 'requests': [], 'errors': []}
    partial.write_text(json.dumps(raw))
    execution = {'epoch': 28, 'kind': scorer.KIND, 'phase': 'engineering',
        'status': 'WORKER_FAILED_OR_TIMEOUT', 'exit_code': 2,
        'worker_attempts_reserved': 1, 'verified_worker_starts': 1, 'uncertain_start': False,
        'owned_live_processes_closed': True, 'owned_live_group_members': [],
        'wall_seconds_including_init_cleanup': 1., 'children_user_seconds': 0.,
        'children_system_seconds': 0., 'largest_child_peak_RSS_bytes': 0,
        'CPU_affinity': [0, 1], 'allowed_further_epoch28_workers': 0,
        'launcher_error': {'type': 'TimeoutError', 'message': 'captured interruption'}, 'cleanup_errors': [],
        'raw_sha256': scorer.sha(final), 'raw_bytes': final.stat().st_size,
        'partial_raw_sha256': scorer.sha(partial), 'partial_raw_bytes': partial.stat().st_size,
        'raw_operation_counters': raw['counters'], 'raw_operation_counters_source': 'raw.partial.json',
        'operation_counts_complete': False, 'backend_execution_since_checkpoint': 'UNKNOWN'}
    execution_path = save('execution.json', execution)
    plan_path = save('plan.json', {'pins': pins})
    args = SimpleNamespace(project=root, raw=partial, execution=execution_path, plan=plan_path)
    replay = scorer.preserved_failure(args, ValueError('interrupted final plus checkpoint'))
    assert replay['failure_provenance_checks_passed'] is True and replay['checks_passed'] is False
    assert replay['evidence']['unparsed_final_raw'] == scorer.identity(final, root)
    replay_path = save('replay.json', replay)
    actual, helper = scorer.derive_actual_with_frozen_helper(root, replay, raw, execution)
    assert actual['native_systemOne_requests'] == 3 and actual['operation_counts_complete'] is False
    assert actual['backend_execution_since_checkpoint'] == 'UNKNOWN'
    checks.append('actual_final_helper_retains_malformed_final_partial_discriminator')
    results = {'epoch': 28, 'kind': scorer.KIND, 'engineering_qualified': False,
        'metrics': scorer.metric_na(), 'benchmark_accepted': False,
        'champion_promoted': False, 'new_submission': False, 'actual_execution': actual}
    results_path = save('RESULTS.json', results)
    bind_args = SimpleNamespace(project=root, replay=replay_path, results=results_path)
    bound = scorer.bind(bind_args)
    assert bound['publication_binding_checks_passed'] is True
    assert bound['evaluated_integrity_checks_passed'] is False and bound['engineering_qualified'] is False
    checks.append('actual_helper_combined_scorer_malformed_final_partial_binding')
    final.write_text(json.dumps(raw))
    execution.update(raw_sha256=scorer.sha(final), raw_bytes=final.stat().st_size)
    save('execution.json', execution)
    replay['outer_execution'] = execution
    replay['evidence'].update(execution=scorer.identity(execution_path, root), unparsed_final_raw=scorer.identity(final, root))
    save('replay.json', replay)
    try:
        scorer.bind(bind_args)
    except ValueError:
        checks.append('cannot_hide_parseable_final_with_partial_selection')
    else:
        raise AssertionError('Valid final hidden behind partial')

report = {'schema_version': 1, 'epoch': 28, 'status': 'PASS_PURE_STDLIB_SCORER_PREFLIGHT',
    'scorer_source': scorer.identity(SOURCE), 'preflight_source': scorer.identity(Path(__file__).resolve()),
    'checks': checks, 'model_tokenizer_native_initializations': 0,
    'proper_metric_computations': 0, 'benchmark_annotation_reads': 0,
    'scope': 'Toy numeric formats/latency and mocked-helper metadata absence/checkpoint/publication binding only. No candidate/native execution, engineering measurement, benchmark cases or labels.'}
output = HERE/'scorer-preflight-v4.json'
with output.open('x') as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
    stream.write('\n')
print(json.dumps({'checks': len(checks), 'scorer': report['scorer_source'], 'report': scorer.identity(output)}, sort_keys=True))
