"""Metadata-only E54 reporting. No inference, dataset, network or Git calls.

Run once after independent physical closure and acceptance/rejection. Percentiles
use sorted observations with linear interpolation at q*(n-1).
"""
import hashlib
import json
import math
import os
from pathlib import Path

W = Path(__file__).resolve().parent
R = W / 'project'
P = 'experiments/sota-2026-10-22/epoch54/'
A = 'experiments/sota-2026-10-22/audit/epoch54/'
ROOTS = (P, A, 'experiments/sota-2026-10-22/runtime/epoch54/')
BASE = '6187205840a9f77db9ab80e97e30be7b222e461e'
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
    assert raw['epoch'] == outer['epoch'] == audit['epoch'] == 54
    assert audit['independent_review_complete'] is True
    assert audit['all_owned_processes_closed'] is True
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
    common = {'schema_version': 1, 'epoch': 54, 'kind': KIND,
              'source_checkpoint': BASE, 'actual_SOURCE_commit': source['commit'],
              'native104_champion_preserved': True, 'candidate_promoted': False,
              'benchmark_accepted': False, 'benchmark_generalization_claim': False,
              'official_goal_verified': False, 'official_rank': None,
              'publisher_submission_authorized': False, 'new_submission': False,
              'used_confirmation_identities': []}
    result = {**common, 'status': audit['status'],
              'engineering_qualified': audit['engineering_qualified'],
              'classification_accuracy': None, 'Brier': None, 'NLL': None,
              'quality_metric_scope': 'No semantic labels or typed NLI forwards; no benchmark-quality measurement.',
              'actual_execution': raw['counters'], 'errors': raw['errors'],
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
              'all_remaining_epoch54_scientific_slots_closed': True,
              'model_and_data_qualification': config['qualification'],
              'official_refresh': config['official_refresh']}
    outputs = [write(R / (P + 'RESULTS.json'), result)]
    used = {**common, 'roles': {'train': [], 'development': [], 'calibration': [],
                              'fresh_confirmation': []},
            'engineering_fixture_ref': raw.get('fixture_ref'),
            'engineering_query_ids': sorted({x['case_id'] for x in rows}),
            'engineering_identity_scope': 'Newly authored CC0 engineering inputs; never benchmark confirmation.',
            'inherited_used_identities': oldcont['epoch53_final']['used_identities'],
            'inherited_used_confirmation': oldcont['epoch53_final']['used_confirmation'],
            'new_public_FinQA_example_exclusions': config['FinQA_exclusions'],
            'all_historical_roles_and_protected_confirmation_preserved': True}
    outputs.append(write(R / (P + 'USED_IDENTITIES.json'), used))
    outputs.append(write(R / (P + 'USED_CONFIRMATION.json'),
                         {**used, 'confirmation_payloads_features_or_labels_read': False}))
    priority = ('Preserve SubmittedNative104. E54 is a real native source-fragment capacity '
                'engineering qualification on authored CC0 fixtures, not a semantic or benchmark '
                'improvement. Preserve its actual branch outcomes and errors; do not rerun this '
                'fixture suite as a benchmark grid. Stronger-model quality work requires new '
                'source-licensed data/scorer access plus qualified training and test-nonuse '
                'provenance. FinNLI access/license remains author-mediated; no contact was sent. '
                'Do not repeat unchanged FinNLI access probes or ModernBERT lineage-card checks '
                'without new access or provenance evidence. '
                'FinQA requires a program-generation/numerical decision design, source rights '
                'qualification and conservative retirement of README examples/filing aliases. '
                'DOC17 remains project-unused publisher-development-exposed DEV; existing '
                'confirmation stays UNQUALIFIED_HOLD and unused. No promotion, new publisher '
                'submission or paid/GPU budget is authorized. Official success still requires '
                'a matching publisher result/rank and eligibility.')
    learning = {**common, 'status': audit['status'], 'engineering_qualified': audit['engineering_qualified'],
                'actual_quality_measured': False, 'next_research_priority': priority,
                'engineering_branch_gates': raw.get('engineering_branch_gates')}
    learning_ref = write(R / (P + 'LEARNINGS.json'), learning); outputs.append(learning_ref)
    ledger = checked(config['initial_rejection_ledger'], True)
    assert not any(x['epoch'] == 54 for x in ledger['rejections'])
    ledger['rejections'].append({**common, 'status': audit['status'],
        'engineering_qualified': audit['engineering_qualified'],
        'reason': 'Engineering qualification cannot accept benchmark quality; candidate promotion remains ineligible.',
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
        {'schema_version': 1, 'epoch': 54, 'kind': KIND, 'source_checkpoint': BASE,
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
