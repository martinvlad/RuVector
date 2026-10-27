"""E54 failure-only metadata reporting; no runtime, inference or scoring calls.

The published candidate and original reporter remain byte-identical. This
post-failure metadata writer states missing observations and derived counts
explicitly; it never turns the planned native experiment into executed work.
"""
import hashlib
import json
import os
from pathlib import Path

W = Path(__file__).resolve().parent
R = W / 'project'
P = 'experiments/sota-2026-10-22/epoch54/'
A = 'experiments/sota-2026-10-22/audit/epoch54/'
RT = 'experiments/sota-2026-10-22/runtime/epoch54/'
BASE = '6187205840a9f77db9ab80e97e30be7b222e461e'

def encoded(x):
    return (json.dumps(x, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()

def ref(p, project=True):
    b = p.read_bytes()
    return {'path': p.relative_to(R).as_posix() if project else str(p),
            'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def checked(row, project=True):
    p = R / row['path'] if project else Path(row['path'])
    assert p.is_file() and not p.is_symlink() and ref(p, project) == row
    return json.loads(p.read_bytes())

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as out:
        out.write(encoded(value)); out.flush(); os.fsync(out.fileno())
    return ref(p, p.is_relative_to(R))

def assemble(c):
    raw, audit = checked(c['raw']), checked(c['independent_rejection'])
    cli, outer = checked(c['CLI_wall']), checked(c['outer'])
    plan, source = checked(c['plan']), checked(c['SOURCE_receipt'])
    old = checked(c['initial_CONT'], False)
    assert audit['independent_review_complete'] is True and audit['all_owned_processes_closed'] is True
    assert audit['engineering_qualified'] is False and audit['actual_native_corpus_batches_attempted'] == 0
    assert audit['actual_native_corpus_batches_completed'] == 0 and audit['actual_worker_starts'] == 1
    assert raw['rows'] == [] and raw['fragment_catalog_audit'] == {} and raw['native_state'] == {}
    assert raw['errors'] == [{'code': 'MINIMUM_THREE_GIB_CGROUP_HEADROOM_REQUIRED', 'type': 'ValueError'}]
    assert raw['counters']['forbidden_model_or_archive_file_access_attempts'] == 6
    assert source['commit'] == audit['exact_SOURCE_commit'] and source['parent'] == BASE
    actual = {'Root_CLI_invocations': 1, 'actual_worker_starts': 1,
              'native_corpus_batches_attempted': 0, 'native_corpus_batches_completed': 0,
              **audit['actual_counts_independently_derived'], 'typed_decision_model_initializations': 0,
              'NLI_forwards': 0, 'semantic_label_decodes': 0, 'training_calls': 0,
              'calibration_calls': 0, 'paid_API_calls': 0, 'GPU_calls': 0,
              'forbidden_suffix_open_attempts': 6, 'allowed_further_epoch54_attempts': 0}
    common = {'schema_version': 1, 'epoch': 54, 'kind': plan['kind'], 'source_checkpoint': BASE,
              'actual_SOURCE_commit': source['commit'], 'status': 'REJECTED_RUNTIME_NOT_SCORED',
              'native104_champion_preserved': True, 'engineering_qualified': False,
              'benchmark_accepted': False, 'candidate_promoted': False,
              'official_goal_verified': False, 'official_rank': None, 'new_submission': False,
              'promotion_or_publisher_submission_authorized': False, 'used_confirmation_identities': []}
    result = {**common, 'actual_execution_independently_derived': actual,
              'raw_recorded_counters_unmodified': raw['counters'], 'raw_errors_unmodified': raw['errors'],
              'raw_fixture_ref': raw.get('fixture_ref'), 'raw_context_rows': 0,
              'quality_metrics': {'accuracy': None, 'Brier': None, 'NLL': None, 'p50': None, 'p95': None},
              'metric_scope': 'No tokenizer, embeddings, native retrieval or contexts ran. No accuracy, proper score, latency percentile or generalization was measured.',
              'timing': audit['timing'], 'resources': raw['resources'],
              'CLI_wall_including_supervisor_interpreter_bootstrap': cli,
              'supervisor_outer_receipt': c['outer'], 'raw_receipt': c['raw'],
              'independent_rejection': c['independent_rejection'],
              'additional_independent_rejection': c['additional_independent_rejection'],
              'shared_cgroup_at_failure': audit['shared_cgroup_at_failure'],
              'six_denied_open_attempts': audit['retained_unresolved_forbidden_open_attempts'],
              'planned_fixture_ref_not_loaded': plan['fixtures'],
              'independent_useful_step_after_failure': c['actual_cleanup'],
              'cleanup_does_not_authorize_E54_retry': True,
              'original_published_reporter_summary_mode_executed': False}
    results = write(R / (P + 'RESULTS.json'), result)
    used = {**common, 'roles': plan['roles'],
            'planned_public_engineering_fixture_ref': plan['fixtures'],
            'planned_engineering_identities_retired_without_execution': plan['roles']['engineering'],
            'actual_engineering_contexts_completed': 0, 'raw_fixture_ref': None,
            'engineer_fixture_is_never_benchmark_confirmation': True,
            'benchmark_confirmation_payloads_features_or_labels_used': False,
            'historical_used_identities': old['epoch53_final']['used_identities'],
            'historical_used_confirmation': old['epoch53_final']['used_confirmation'],
            'new_public_FinQA_example_and_filing_exclusions': c['FinQA_exclusions']}
    used_ids = write(R / (P + 'USED_IDENTITIES.json'), used)
    used_conf = write(R / (P + 'USED_CONFIRMATION.json'), used)
    priority = ('Preserve SubmittedNative104. E54 started one worker and exited before fixture loading, '
                'tokenization, BGE or native retrieval: shared-cgroup headroom2467368960B was below '
                '3221225472B. Actual native batches/tokenizer/BGE/NLI/contexts/Gold/train/paid/GPU were zero; '
                'all E54 slots remain closed. Exact duplicate public-source cleanup was performed only '
                'after rejection and never caused an E54 rerun. For a separately frozen future epoch, '
                'check actual shared-cgroup headroom before consuming a CLI slot; shared-memory filesystem '
                'availability is not a substitute. Six denied weight/archive-suffix open attempts have '
                'unrecorded targets: diagnose with narrowly scoped metadata-only evidence before admission; '
                'do not infer harmlessness or weaken the guard from a ZIP-probe hypothesis. No semantic '
                'or source-fragment capacity success was measured. DOC17 stays unused publisher-exposed '
                'DEV and confirmation remains UNQUALIFIED_HOLD. Stronger model work still requires new '
                'licensed data/scoring access and qualified training/test-nonuse lineage. Do not repeat '
                'unchanged FinNLI access or ModernBERT lineage probes. FinQA requires a program task and '
                'source-rights qualification; its README examples/filing families are DEV forever. '
                'Official success requires a matching publisher result/rank and eligibility; no promotion, '
                'new submission or paid/GPU cap is granted.')
    learn = write(R / (P + 'LEARNINGS.json'),
                  {**common, 'actual_execution': actual, 'next_research_priority': priority,
                   'root_preflight_miss': 'Filesystem free space was checked; current cgroup headroom was not checked before the one-shot launch.',
                   'actual_cleanup': c['actual_cleanup'], 'unknown_open_targets_retained': True})
    ledger = checked(c['initial_rejection_ledger'])
    assert not any(x['epoch'] == 54 for x in ledger['rejections'])
    ledger['rejections'].append({**common, 'actual_execution': actual, 'results': results,
                                'independent_rejection': c['independent_rejection'],
                                'reason': raw['errors'], 'unattributed_denied_open_attempts': 6})
    ledger_ref = write(R / (P + 'REJECTION_LEDGER.json'), ledger)
    return {'results': results, 'used_identities': used_ids, 'used_confirmation': used_conf,
            'learning': learn, 'ledger': ledger_ref, 'next_research_priority': priority,
            'actual_execution': actual, 'status': common['status']}

def close(c):
    review = checked(c['independent_public_review'], False)
    assert review['checks_passed'] is True and review['public_inventory_review_passed'] is True
    files = sorted([ref(p) for prefix in (P, A, RT) for p in (R / prefix).rglob('*') if p.is_file()], key=lambda x: x['path'])
    assert files == review['files']
    target = R / (A + 'FINAL_PUBLIC_SUMMARY_AND_INVENTORY_INDEPENDENT_REVIEW.v1.json')
    with target.open('xb') as out:
        out.write(Path(c['independent_public_review']['path']).read_bytes()); out.flush(); os.fsync(out.fileno())
    files.append(ref(target)); files.sort(key=lambda x: x['path'])
    return write(R / (P + 'EPOCH_MANIFEST.json'),
                 {'schema_version': 1, 'epoch': 54, 'source_checkpoint': BASE,
                  'kind': 'REAL_NATIVE_SOURCE_FRAGMENT_CAPACITY_QUALIFICATION',
                  'status': 'REJECTED_RUNTIME_NOT_SCORED', 'files': files,
                  'no_project_additions_after_manifest': True, 'official_goal_verified': False,
                  'used_confirmation_identities': []})

if __name__ == '__main__':
    import sys
    mode, config_path = sys.argv[1:]
    config = json.loads(Path(config_path).read_text())
    assert mode in ('assemble', 'close')
    value = assemble(config) if mode == 'assemble' else close(config)
    print(json.dumps(value, indent=2, sort_keys=True))
