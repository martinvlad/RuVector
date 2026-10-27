"""Source-frozen E56 metadata reporting only; no model, data, scorer, network or Git execution.

Preserve raw counters and independently derived actual operations separately.
Report frozen gate verdicts and observed context percentiles without changing
runtime source or any score. An optional independently audited retrieval DEV
pilot reference is present only when an actual separately frozen pilot ran.
"""
import hashlib
import json
import math
import os
from pathlib import Path

W = Path(__file__).resolve().parent
R = W / 'project'
P = 'experiments/sota-2026-10-22/epoch56/'
A = 'experiments/sota-2026-10-22/audit/epoch56/'
ROOTS = (P, A, 'experiments/sota-2026-10-22/runtime/epoch56/')
BASE = 'ffdd0699f3254c5dd09437533d38111a8521c920'
KIND = 'REAL_NATIVE_SOURCE_FRAGMENT_CAPACITY_QUALIFICATION'

def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + '\n').encode()

def ref(path, project=False):
    raw = path.read_bytes()
    return {'path': path.relative_to(R).as_posix() if project else str(path),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def checked(row, project=False):
    path = R / row['path'] if project else Path(row['path'])
    assert path.is_file() and not path.is_symlink()
    raw = path.read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    return json.loads(raw)

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as out:
        out.write(encoded(value)); out.flush(); os.fsync(out.fileno())
    return ref(path, path.is_relative_to(R))

def percentile(values, q):
    assert values and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values)
    ordered = sorted(values); at = q * (len(ordered) - 1)
    lo, hi = math.floor(at), math.ceil(at)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (at - lo)

def summarize(config):
    raw = checked(config['raw'], True)
    outer = checked(config['outer'], True)
    audit = checked(config['independent_acceptance'], True)
    source = checked(config['source_receipt'], True)
    oldcont = checked(config['initial_CONT'])
    assert source['parent'] == BASE and source['phase'] == 'source'
    assert raw['epoch'] == outer['epoch'] == audit['epoch'] == 56
    assert audit['independent_review_complete'] is True
    assert audit['all_owned_processes_closed'] is True
    # Plans and queued work never establish execution.
    pilot_refset = config.get('additional_retrieval_DEV_pilot')
    pilot = None
    dev_actual = []
    dev_scored = []
    dev_reserved = []
    dev_label_only = []
    if pilot_refset is not None:
        assert set(pilot_refset) == {'results', 'independent_acceptance', 'frozen_plan'}
        pilot = checked(pilot_refset['results'], True)
        pilot_audit = checked(pilot_refset['independent_acceptance'], True)
        pilot_plan = checked(pilot_refset['frozen_plan'], True)
        assert pilot['epoch'] == pilot_audit['epoch'] == pilot_plan['epoch'] == 56
        assert pilot['actual_pilot_attempted'] is True
        assert pilot_audit['independent_review_complete'] is True
        assert pilot_audit['all_owned_processes_closed'] is True
        assert pilot_audit['actual_results_ref'] == pilot_refset['results']
        assert pilot['benchmark_generalization_claim'] is False and pilot['candidate_promoted'] is False
        assert pilot['used_confirmation_identities'] == []
        reserved = pilot['reserved_development_query_ids']
        feature_ids = pilot['actual_feature_query_ids']
        scored_ids = pilot['actual_scored_query_ids']
        label_only = pilot['label_only_exposed_query_ids']
        assert len(set(label_only)) == len(label_only) and all(type(x) is str for x in label_only)
        assert reserved == pilot_plan['selected_query_ids']
        assert len(set(reserved)) == len(reserved) and all(type(x) is str for x in reserved)
        assert len(set(feature_ids)) == len(feature_ids) and set(feature_ids) <= set(reserved)
        assert len(set(scored_ids)) == len(scored_ids) and set(scored_ids) <= set(feature_ids)
        namespace = pilot['identity_namespace']
        assert namespace == pilot_plan['identity_namespace'] and type(namespace) is str and namespace
        dev_actual = [namespace + ':' + x for x in feature_ids]
        dev_scored = [namespace + ':' + x for x in scored_ids]
        dev_reserved = [namespace + ':' + x for x in reserved]
        dev_label_only = [namespace + ':' + x for x in label_only]
    prepared_exposure = config.get('prepared_retrieval_DEV_feature_exposure')
    prep_dev = []
    if prepared_exposure is not None:
        prep = checked(prepared_exposure['receipt'], True)
        prep_plan = checked(prepared_exposure['frozen_plan'], True)
        assert prep['epoch'] == prep_plan['epoch'] == 56 and prep['mode'] == 'features'
        assert prep['status'] == 'FULL_CORPUS_AND_FIXED16_DEV_FEATURES_PREPARED_NO_GOLD'
        assert prep['semantic_gold_decodes'] == 0 and prep['query_text_rows_returned'] == 16
        assert prep['selected_query_ids'] == prep_plan['selected_query_ids']
        assert prep['identity_namespace'] == prep_plan['identity_namespace']
        prep_dev = [prep['identity_namespace'] + ':' + x for x in prep['selected_query_ids']]
    # An independently rejected runtime is retained without manufacturing metrics.
    rows = raw.get('rows', [])
    latencies = {}
    for arm in ('native', 'lexical', 'source_order', 'whole_source'):
        selected = [x for x in rows if x['arm'] == arm]
        times = [x['context_preparation_seconds'] for x in selected]
        latencies[arm] = {'completed_contexts': len(selected),
                         'p50_seconds': percentile(times, .5) if times else None,
                         'p95_seconds': percentile(times, .95) if times else None}
    unique_queries = {}
    for row in rows:
        value = row['native_query_and_hit_validation_seconds']
        if row['case_id'] in unique_queries:
            assert unique_queries[row['case_id']] == value
        unique_queries[row['case_id']] = value
    query_times = list(unique_queries.values())
    common = {'schema_version': 1, 'epoch': 56, 'kind': KIND,
              'source_checkpoint': BASE, 'actual_SOURCE_commit': source['commit'],
              'native104_champion_preserved': True, 'candidate_promoted': False,
              'benchmark_accepted': False, 'benchmark_generalization_claim': False,
              'official_goal_verified': False, 'official_rank': None,
              'publisher_submission_authorized': False, 'new_submission': False,
              'used_confirmation_identities': []}
    result = {**common, 'status': audit['status'],
              'engineering_qualified': audit['engineering_qualified'],
              'classification_accuracy': None, 'Brier': None, 'NLL': None,
              'quality_metric_scope': 'Engineering phase has no semantic labels or typed NLI forwards. A separate actual retrieval DEV pilot, if referenced, may score public relevance labels; no NLI classification or generalization follows.',
              'actual_execution_independently_derived': audit['actual_execution_independently_derived'],
              'raw_recorded_counters_unmodified': raw['counters'],
              'native_counter_accounting': audit['native_counter_accounting'],
              'independent_acceptance_or_rejection_reason': audit['reason'],
              'pre_science_metadata_preparation': config['pre_science_metadata_preparation'],
              'CLI_wall_including_supervisor_interpreter_bootstrap': checked(config['CLI_wall'], True),
              'source_frozen_reporter_executed': True,
              'errors': raw['errors'],
              'engineering_branch_gates': raw.get('engineering_branch_gates'),
              'per_arm_context_preparation_latency': latencies,
              'native_query_and_hit_validation_latency': {
                  'unique_queries': len(query_times),
                  'p50_seconds': percentile(query_times, .5) if query_times else None,
                  'p95_seconds': percentile(query_times, .95) if query_times else None},
              'percentile_definition': 'Sorted values; linear interpolation at q*(n-1).',
              'latency_scope': raw['latency_scope'],
              'worker_timing': raw['timing'], 'worker_resources': raw['resources'],
              'outer_actual_receipt': config['outer'], 'raw_actual_result': config['raw'],
              'independent_acceptance': config['independent_acceptance'],
              'fixture_ref': raw.get('fixture_ref'),
              'all_remaining_epoch56_scientific_slots_closed': True,
              'model_and_data_qualification': config['qualification'],
              'official_refresh': config['official_refresh'],
              'additional_retrieval_DEV_pilot': pilot_refset,
              'engineering_phase_classification_quality_measured': False,
              'retrieval_DEV_scored_query_count': len(dev_scored)}
    outputs = [write(R / (P + 'RESULTS.json'), result)]
    used = {**common, 'roles': {'train': [], 'development': sorted(set(dev_actual) | set(dev_label_only) | set(prep_dev)), 'calibration': [],
                              'fresh_confirmation': []},
            'engineering_fixture_ref': raw.get('fixture_ref'),
            'engineering_query_ids': sorted({x['case_id'] for x in rows}),
            'engineering_identity_scope': 'Newly authored CC0 engineering inputs; never benchmark confirmation.',
            'inherited_used_identities': oldcont['epoch55_final']['used_identities'],
            'inherited_used_confirmation': oldcont['epoch55_final']['used_confirmation'],
            'inherited_FinQA_public_exclusions_preserved': True,
            'all_historical_roles_and_protected_confirmation_preserved': True,
            'additional_retrieval_DEV_pilot': pilot_refset,
            'retrieval_DEV_actual_feature_identities': dev_actual,
            'retrieval_DEV_actual_scored_identities': dev_scored,
            'retrieval_DEV_label_only_exposed_identities': dev_label_only,
            'preparation_retrieval_DEV_feature_identities': prep_dev,
            'prepared_retrieval_DEV_feature_exposure': prepared_exposure,
            'retrieval_DEV_reserved_identities': dev_reserved,
            'retrieval_DEV_reserved_and_actual_are_separate': True}
    outputs.append(write(R / (P + 'USED_IDENTITIES.json'), used))
    outputs.append(write(R / (P + 'USED_CONFIRMATION.json'),
                         {**used, 'confirmation_payloads_features_or_labels_read': False}))
    priority = ('Preserve SubmittedNative104. E56 must retain the independent actual accounting/capacity verdict, raw counters, '
                'helper terminal/progress evidence and any failures unchanged. Native snapshot integration uses a single validated '
                'source with direct assignment, never adding expected counters as observations. Do not rerun old engineering '
                'fixtures as benchmark generalization. Any separately frozen licensed retrieval DEV pilot measures only its '
                'explicit public slice and exact scorer; model training/test-nonuse remains unqualified and it cannot establish '
                'a full-benchmark rank, NLI accuracy, fresh confirmation or promotion. E55 metadata-probe six denied opens remain '
                'historical; E54 denied targets remain unknown; all five suffix denies stay enabled. Stronger typed-reader quality '
                'work still requires new aligned licensed data/scoring access and exact training/test-nonuse provenance. Do not '
                'repeat unchanged FinNLI access or ModernBERT card probes. DOC17 remains unused publisher-development-exposed DEV; '
                'all existing confirmation is UNQUALIFIED_HOLD and unused. No new submission, paid API or GPU cap is granted. '
                'Official success requires a matching publisher result/rank and eligibility.')
    learning = {**common, 'status': audit['status'], 'engineering_qualified': audit['engineering_qualified'],
                'engineering_semantic_quality_measured': False, 'next_research_priority': priority,
                'actual_execution_independently_derived': audit['actual_execution_independently_derived'],
                'native_counter_accounting': audit['native_counter_accounting'],
                'additional_retrieval_DEV_pilot': config.get('additional_retrieval_DEV_pilot'),
                'pre_science_metadata_preparation': config['pre_science_metadata_preparation'],
                'engineering_branch_gates': raw.get('engineering_branch_gates')}
    learning_ref = write(R / (P + 'LEARNINGS.json'), learning); outputs.append(learning_ref)
    ledger = checked(config['initial_rejection_ledger'], True)
    assert not any(x['epoch'] == 56 for x in ledger['rejections'])
    ledger['rejections'].append({**common, 'status': audit['status'],
        'engineering_qualified': audit['engineering_qualified'],
        'reason': audit['reason'],
        'native_counter_accounting': audit['native_counter_accounting'],
        'actual_execution_independently_derived': audit['actual_execution_independently_derived'],
        'pre_science_metadata_preparation': config['pre_science_metadata_preparation'],
        'results': outputs[0], 'independent_acceptance': config['independent_acceptance']})
    ledger_ref = write(R / (P + 'REJECTION_LEDGER.json'), ledger); outputs.append(ledger_ref)
    return {'outputs': outputs, 'results': outputs[0], 'learning': learning_ref,
            'ledger': ledger_ref, 'next_research_priority': priority,
            'status': audit['status'], 'engineering_qualified': audit['engineering_qualified']}

def close(config):
    approval = checked(config['independent_public_review'])
    assert approval['checks_passed'] is True and approval['public_inventory_review_passed'] is True
    target = R / (A + 'FINAL_PUBLIC_SUMMARY_AND_INVENTORY_INDEPENDENT_REVIEW.v1.json')
    source = Path(config['independent_public_review']['path'])
    with target.open('xb') as out:
        out.write(source.read_bytes()); out.flush(); os.fsync(out.fileno())
    files = sorted((ref(path, True) for prefix in ROOTS for path in (R / prefix).rglob('*')
                    if path.is_file()), key=lambda x: x['path'])
    expected = {x['path']: x for x in approval['files']}
    assert len(expected) == len(approval['files'])
    assert {x['path']: x for x in files if x['path'] != target.relative_to(R).as_posix()} == expected
    return write(R / (P + 'EPOCH_MANIFEST.json'),
        {'schema_version': 1, 'epoch': 56, 'kind': KIND, 'source_checkpoint': BASE,
         'files': files, 'no_project_additions_after_manifest': True,
         'official_goal_verified': False, 'used_confirmation_identities': [],
         'independent_public_review': ref(target, True)})

if __name__ == '__main__':
    import sys
    mode, config_path = sys.argv[1:]
    config = json.loads(Path(config_path).read_text())
    value = summarize(config) if mode == 'summarize' else close(config) if mode == 'close' else None
    assert value is not None
    print(json.dumps(value, indent=2, sort_keys=True))
