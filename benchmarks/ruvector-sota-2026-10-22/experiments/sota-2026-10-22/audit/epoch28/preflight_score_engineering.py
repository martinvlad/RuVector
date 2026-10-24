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
SOURCE = HERE/'score_engineering.py'
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

report = {'schema_version': 1, 'epoch': 28, 'status': 'PASS_PURE_STDLIB_SCORER_PREFLIGHT',
    'scorer_source': scorer.identity(SOURCE), 'preflight_source': scorer.identity(Path(__file__).resolve()),
    'checks': checks, 'model_tokenizer_native_initializations': 0,
    'proper_metric_computations': 0, 'benchmark_annotation_reads': 0,
    'scope': 'Toy numeric formats/latency and mocked-helper metadata absence/checkpoint/publication binding only. No candidate/native execution, engineering measurement, benchmark cases or labels.'}
output = HERE/'scorer-preflight-v2.json'
with output.open('x') as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
    stream.write('\n')
print(json.dumps({'checks': len(checks), 'scorer': report['scorer_source'], 'report': scorer.identity(output)}, sort_keys=True))
