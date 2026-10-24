"""Postrun epoch27 integrity/rejection replay from already sealed outputs only.

Never opens annotated source, initializes ML/native code, or adjusts a gate.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch27-0471ff09d550/project')
EPOCH = ROOT/'experiments/sota-2026-10-22/epoch27'
CANONICAL = ROOT/'experiments/sota-2026-10-22/audit/epoch27'
HERE = Path(__file__).resolve().parent
CLASSES = ['entailment', 'contradiction', 'not_mentioned']
ARMS = ['actual_native', 'lexical', 'positional']
DEV = [609, 380, 592, 454, 559, 515, 349, 223]
HYP = ['nda-17', 'nda-7', 'nda-3']


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path, canonical=False):
    return {'path': str(path.relative_to(ROOT)) if canonical else str(path),
            'bytes': path.stat().st_size, 'sha256': sha(path)}


def audit():
    checks = []

    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
        if not passed:
            raise ValueError('Acceptance integrity failure: ' + name)

    results = read(EPOCH/'RESULTS.json')
    scorer = read(HERE/'scorer-result.json')
    raw = read(EPOCH/'runs/dev/raw.json')
    execution = read(EPOCH/'execution.json')
    structure = read(HERE/'raw-structure-audit.json')
    closure = read(HERE/'postrun-closure-before-gold.json')
    seal = read(HERE/'auditor-output-seal.json')
    plan = read(EPOCH/'plan.json')
    check('exact_canonical_RESULTS_identity', identity(EPOCH/'RESULTS.json', True) == {
        'path': 'experiments/sota-2026-10-22/epoch27/RESULTS.json', 'bytes': 54461,
        'sha256': '9c8e849e2fc1e4a854486fd2cae45de116f12108d303ffdb4677707cf13d3845'})
    for name in ['scorer-result.json', 'raw-structure-audit.json',
                 'postrun-closure-before-gold.json', 'auditor-output-seal.json',
                 'frozen-plan-review.json', 'timing-interpretation.json',
                 'postrun-diagnostic-report.json']:
        check('canonical_copy_exact:' + name, (CANONICAL/name).read_bytes() == (HERE/name).read_bytes())
    for key, path in [('raw', EPOCH/'runs/dev/raw.json'), ('execution', EPOCH/'execution.json'),
                      ('source_plan', EPOCH/'plan.json'), ('source_freeze', EPOCH/'source-freeze.json'),
                      ('raw_structure_audit', CANONICAL/'raw-structure-audit.json'),
                      ('scorer_result', CANONICAL/'scorer-result.json')]:
        check('canonical_RESULTS_binding:' + key, results[key] == identity(path, True))
    check('plan_exact_unchanged', sha(EPOCH/'plan.json') == 'd05797f5c3e69ea535b8075a67f8d0f66267e5d15aaed933e4b1916fbf2e0511')
    check('sourcefreeze_exact_unchanged', sha(EPOCH/'source-freeze.json') == 'aeef02fae8c0db8a90265dc66b0875e7892770a4fe4329daf340a18856db647c')
    for row in plan['pins']:
        path = ROOT/row['path']
        check('frozen_source_pin:' + row['path'], path.stat().st_size == row['bytes'] and sha(path) == row['sha256'])
    check('canonical_metrics_verbatim_frozen_scorer', results['metrics'] == scorer['metrics'])
    check('canonical_paired_differences_verbatim', results['paired_descriptive_differences'] == scorer['paired_descriptive_differences'])
    check('canonical_gates_verbatim', results['predeclared_descriptive_diagnostic_checks'] == scorer['predeclared_descriptive_diagnostic_checks'])
    check('exact_roles_no_confirmation', results['data_roles'] == plan['data_roles'] == {
        'train': [], 'dev': DEV, 'calibration': [], 'confirmation': []})
    check('exactly24_once_join_no_other_roles', results['annotation_choices_accessed'] == scorer['annotation_choices_accessed'] == 24
          and results['other_role_annotation_choices_accessed'] == scorer['other_role_annotation_choices_accessed'] == 0
          and read(HERE/'postrun-diagnostic-report.json')['annotation_choices_join_invocations'] == 1)
    check('original_source_never_opened_by_this_wrapper', True)
    check('complete_structural_and_closure_audits', structure['status'] == 'PASS' and structure['checks'] == 2937
          and structure['failures'] == [] and closure['owned_group_or_session_members'] == []
          and seal['all24cases_complete'] is True and seal['all72finite_predictions_validated'] is True
          and seal['annotation_choices_accessed_before_seal'] == 0 and seal['owned_group_closed'] is True)
    check('sealed_raw_inputs_execution_unchanged', seal['raw'] == identity(EPOCH/'runs/dev/raw.json')
          and seal['inputs'] == identity(EPOCH/'data/dev.inputs.json')
          and seal['execution'] == identity(EPOCH/'execution.json'))
    check('worker_helper_physically_absent', not Path('/proc/76977').exists() and not Path('/proc/76982').exists())
    group = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == 76977 or int(fields[3]) == 76977:
                group.append(int(entry.name))
        except (OSError, ValueError, IndexError):
            pass
    check('owned_group_session_physically_empty', group == [])
    check('single_successful_closed_CPU2_worker', execution['status'] == 'WORKER_COMPLETED'
          and execution['exit_code'] == 0 and execution['worker_attempts_reserved'] == execution['verified_worker_starts'] == 1
          and execution['CPU_affinity'] == [0, 1] and execution['owned_live_processes_closed'] is True
          and execution['owned_live_group_members'] == [] and 0 < execution['wall_seconds_including_init_cleanup'] <= 600
          and execution['launcher_error'] is None and execution['cleanup_errors'] == [])
    check('all_attempts_closed_no_retry', results['all_attempt_slots_closed'] is True
          and results['automatic_retry'] is False and execution['allowed_further_epoch27_workers'] == 0)
    for key, value in raw['counters'].items():
        check('canonical_counter:' + key, results['actual_execution'][key] == value)
    check('counter_aliases_scopes', results['actual_execution']['DEV_corpora'] == 8
          and plan['limits']['native_corpus_batches'] == 1
          and results['actual_execution']['BGE_forwards'] == raw['counters']['BGE_forwards_completed'] == 84
          and results['actual_execution']['BGE_texts'] == raw['counters']['BGE_texts_completed'] == 603
          and results['actual_execution']['native_index_initializations'] == 8
          and results['actual_execution']['native_searches_completed'] == 24)
    check('runtime_aliases_exact', results['actual_execution']['wall_seconds_including_init_cleanup'] == execution['wall_seconds_including_init_cleanup']
          and results['actual_execution']['peak_RSS_bytes'] == execution['largest_child_peak_RSS_bytes']
          and results['actual_execution']['resource_scope'] == execution['memory_scope'])
    check('all_errors_empty', raw['errors'] == results['raw_errors'] == []
          and results['outer_launcher_error'] is None and results['outer_cleanup_errors'] == [])
    expected = [f'original-contractnli:train:epoch27:dev:{d}:{h}' for d in DEV for h in HYP]
    check('fixed_ordered24_cases', [c['id'] for c in raw['cases']] == expected)
    replay = {}
    for arm in ARMS:
        saved = scorer['metrics'][arm]
        check(arm + ':denominator_fixed24', saved['n'] == len(saved['cases']) == 24 and [c['id'] for c in saved['cases']] == expected)
        correct = 0
        nll, brier = [], []
        counts = {gold: {'n': 0, 'correct': 0} for gold in CLASSES}
        confusion = {gold: {pred: 0 for pred in CLASSES} for gold in CLASSES}
        for case, observed in zip(saved['cases'], raw['cases']):
            gold = case['gold']  # Already exposed sealed scorer output, never source JSON.
            reader = observed['arms'][arm]['reader']
            p, pred = reader['probabilities'], reader['prediction']
            check(case['id'] + ':' + arm + ':sealed_prediction_probability_identity', case['probabilities'] == p and case['prediction'] == pred)
            good = int(pred == gold)
            correct += good
            counts[gold]['n'] += 1
            counts[gold]['correct'] += good
            confusion[gold][pred] += 1
            nll.append(-math.log(max(p[gold], 1e-12)))
            brier.append(math.fsum((p[label]-int(label == gold))**2 for label in CLASSES))
        replay[arm] = {'correct': correct, 'NLL': math.fsum(nll)/24, 'Brier': math.fsum(brier)/24, 'by_class': counts}
        check(arm + ':independent_saved_probability_loss_replay', correct == saved['correct']
              and abs(replay[arm]['NLL']-saved['NLL_clipped_1e-12']) <= 1e-12
              and abs(replay[arm]['Brier']-saved['Brier']) <= 1e-12
              and confusion == saved['confusion_matrix']
              and all(counts[k]['n'] == saved['by_class'][k]['n'] and counts[k]['correct'] == saved['by_class'][k]['correct'] for k in CLASSES))
    native = replay['actual_native']
    gates = {'every_gold_class_present': all(native['by_class'][k]['n'] > 0 for k in CLASSES),
             'native_at_least_one_correct_per_class': all(native['by_class'][k]['correct'] > 0 for k in CLASSES),
             'raw_errors_empty': not raw['errors']}
    for control in ['lexical', 'positional']:
        gates[control + ':native_at_least2more_correct'] = native['correct'] >= replay[control]['correct']+2
        gates[control + ':Brier_nonincrease'] = native['Brier'] <= replay[control]['Brier']+1e-12
        gates[control + ':NLL_nonincrease'] = native['NLL'] <= replay[control]['NLL']+1e-12
    failed = sorted(k for k, passed in gates.items() if not passed)
    check('independent_frozen_gates_match_all_canonical_outputs', gates == scorer['predeclared_descriptive_diagnostic_checks'] == results['predeclared_descriptive_diagnostic_checks'])
    check('exact_two_rejections_retained', failed == ['native_at_least_one_correct_per_class', 'positional:native_at_least2more_correct'])
    check('integrity_PASS_distinct_from_diagnostic_rejection', not all(gates.values())
          and scorer['descriptive_diagnostic_checks_pass'] is False and results['diagnostic_qualified'] is False
          and results['status'] == 'REJECTED_DEV_DIAGNOSTIC')
    check('permanent_no_promotion_submission_rank_or_CONF', all(results[k] is False for k in ['benchmark_accepted', 'champion_promoted', 'new_submission', 'official_SOTA_verified'])
          and results['official_rank'] is None and results['confirmation_ids'] == []
          and scorer['confirmation'] == [] and plan['confirmation_execution_allowed'] is False)
    return {'schema_version': 1, 'epoch': 27, 'status': 'AUDITED_REJECTED_DEV_DIAGNOSTIC',
        'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': True,
        'check_count': len(checks), 'checks': checks, 'failures': [],
        'diagnostic_qualified': False, 'diagnostic_failed_checks': failed,
        'predeclared_descriptive_diagnostic_checks': gates,
        'metrics': {arm: {k: v for k, v in scorer['metrics'][arm].items() if k not in ['cases', 'per_document']} for arm in ARMS},
        'actual_execution': results['actual_execution'],
        'counter_provenance': {'DEV_corpora': '8 source documents, one native corpus batch; never8batches',
            'native_document_indexes': 8, 'native_queries': 24, 'NLI_forward_pairs': 72,
            'allowed_literal_local_binds': 1, 'forbidden_network_operations': 0,
            'source_choice_join_invocations': 1, 'unique_selected_choices': 24,
            'posthoc_distinct_evidence_lists': 4, 'other_role_choices_or_evidence': 0},
        'interpretation': 'Integrity/runtime/source validation PASS, but native15/24 vs lexical12/24 and positional14/24 fails contradiction0/4 and positional gain1<2. All three arms predict zero contradictions; lower proper scores do not waive either frozen failure.',
        'retrieval_scope': 'Actual BGE ANN only; candidate has no RRF fusion. Frozen protocol legacy RRF phrase is superseded by precise plan/source interpretation, without source mutation. Submitted native104/RRF10 retained.',
        'latency_scope': 'Reader interval includes full score_pair tokenization/tensor preparation/model/logit extraction/softmax; no isolated-kernel claim. Wholeworker204.039830041s includes all matched arms, native/BGE/init/cleanup; RSS is largest child high-water.',
        'statistical_scope': '8document groups×3correlated hypotheses. Prior10/24 or11/24 uses different banks and cannot establish paired improvement or population superiority.',
        'confirmation_HOLD': 'Exact full submitted104 comparator absent; later publisher reselection and foundation overlap unresolved. CONF=[] regardless descriptive result.',
        'posthoc_scope': 'Four already-scored C cases only; evidence coverage is outcome-conditioned DEV description, does not change gates, and cannot prove semantic sufficiency or sole head causation.',
        'annotation_choices_accessed': 24, 'new_annotation_choice_reads_by_wrapper': 0,
        'source_annotated_JSON_opened_by_wrapper': False,
        'model_tokenizer_native_calls_by_wrapper': 0,
        'confirmation': [], 'benchmark_accepted': False, 'champion_promoted': False,
        'new_submission': False, 'official_SOTA_established': False, 'official_rank': None,
        'evidence': {**{name: identity(path, True) for name, path in [
            ('RESULTS', EPOCH/'RESULTS.json'), ('raw', EPOCH/'runs/dev/raw.json'),
            ('execution', EPOCH/'execution.json'), ('plan', EPOCH/'plan.json'),
            ('source_freeze', EPOCH/'source-freeze.json'), ('scorer_result', CANONICAL/'scorer-result.json'),
            ('raw_structure_audit', CANONICAL/'raw-structure-audit.json')]},
            'posthoc_evidence_coverage': identity(HERE/'posthoc-contradiction-evidence-coverage.json'),
            'acceptance_wrapper_source': identity(Path(__file__).resolve())}}


if __name__ == '__main__':
    result = audit()
    output = HERE/'acceptance-rejection.json'
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'checks_passed': result['checks_passed'],
        'check_count': result['check_count'], 'diagnostic_qualified': result['diagnostic_qualified'],
        'diagnostic_failed_checks': result['diagnostic_failed_checks'], 'report': identity(output)}, sort_keys=True))
