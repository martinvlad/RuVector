"""Independent pure metadata comparator. Not a scorer EVALUATE or BIND."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4/project')
OUT = Path('/workspace/ruvector-e37-acceptance-audit')
P = 'experiments/sota-2026-10-22/'
E = P + 'epoch37/'
A = P + 'audit/epoch37/'

def loads(body):
    def pairs(items):
        result = {}
        for k, v in items:
            assert k not in result, 'Duplicate metadata key'
            result[k] = v
        return result
    def invalid(value):
        raise ValueError('Nonfinite metadata number')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def ref(rel):
    assert rel and not rel.startswith('/') and all(p not in ('', '.', '..') for p in rel.split('/'))
    path = ROOT / rel
    assert path.is_file() and not any(p.is_symlink() for p in (path, *path.parents))
    body = path.read_bytes()
    return {'path': rel, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def read(rel):
    return loads((ROOT / rel).read_bytes())

def checked(row):
    assert set(row) == {'path', 'bytes', 'sha256'} and ref(row['path']) == row

def compare(replay, result):
    assert set(result) == set(replay) | {'exceptional_blocked_checkpoint'}, 'Only one exceptional metadata addition permitted'
    assert all(canonical(result[k]) == canonical(v) for k, v in replay.items()), 'Every original replay field must remain unchanged'
    assert result['status'] == 'REJECTED_ENGINEERING_INTEGRITY'
    assert result['checks_passed'] is result['engineering_passed'] is result['readiness_qualified'] is False
    assert result['actual_NLI_forwards'] is result['final_derived_forecasts'] is result['engineering_metrics'] is None
    info = result['exceptional_blocked_checkpoint']
    assert info['status'] == 'EXCEPTIONAL_BLOCKED_CHECKPOINT'
    assert info['source_commit'] == 'a93a1d6922c8a14f356461fb383846157816c70b'
    assert info['frozen_evaluated_integrity_checks_passed'] is info['frozen_physical_closure_passed'] is False
    assert info['frozen_unknown_physical_ownership'] is True
    assert info['exceptional_preworker_physical_resolution_passed'] is True
    assert info['internal_operation_counts'] == 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'
    assert info['actual_worker_start_status'] == 'UNKNOWN_NO_CAPTURED_EXECUTION'
    for k in ('actual_NLI_forwards', 'final_derived_forecasts', 'corpus_batches_attempted', 'corpus_batches_completed', 'model_initializations', 'actual_resources'):
        assert info[k] is None, 'Never replace captured UNKNOWN with zero or inference'
    assert type(info['logical_dispatch_slots_burned']) is int and info['logical_dispatch_slots_burned'] == 1
    assert type(info['verified_launcher_starts']) is int and info['verified_launcher_starts'] == 1
    assert info['remaining_slots'] and all(type(x) is int and x == 0 for x in info['remaining_slots'].values())
    assert info['used_confirmation_identities'] == []
    for k in ('benchmark_accepted', 'champion_promoted', 'new_submission', 'official_SOTA_verified'):
        assert info[k] is False
    assert info['official_rank'] is None
    assert info['cumulative_scope']['current_corpus_attempts'] is None
    assert info['cumulative_scope']['current_completed_corpus_batches'] is None
    return info

def main():
    frozen = ref(A + 'qualification-replay.json')
    assert frozen == {'path': A + 'qualification-replay.json', 'bytes': 4856,
                      'sha256': '883f5374ff9e976ccb6b880075dbdf4a00cd452fa2af040a477097bf7f686c73'}
    replay, result = read(frozen['path']), read(E + 'RESULTS.json')
    info = compare(replay, result)
    for name in ('protocol', 'source_review', 'independent_preworker_resolution', 'future_source_guard_review', 'frozen_evaluation', 'frozen_observer'):
        checked(info[name])
    assert info['frozen_evaluation'] == frozen
    assert info['independent_preworker_resolution']['sha256'] == 'd8164d037fe1cbdaebd17bc649dd6409625e12edb799d6ac86a8ec9238925db8'
    source_review = read(info['source_review']['path'])
    assert source_review['checks_passed'] is True and source_review['exceptional_source_only'] is True
    assert source_review['scientific_authorization'] == 0
    for row in source_review['files']:
        checked(row)
    observer = read(info['frozen_observer']['path'])
    assert observer['physical_closure_passed'] is False and observer['unknown_physical_ownership'] is True
    assert observer['physical_supervisor_closed'] is True and observer['physical_supervisor_absent'] is False
    # Label-free public identity accounting; no actual12 inputs or oracle payloads.
    plan = read(E + 'plan.json')
    used = read(E + 'USED_CONFIRMATION_IDENTITIES.json')
    assert used['engineering_publicly_exposed_identities'] == plan['engineering_ids']
    assert len(used['engineering_publicly_exposed_identities']) == 12
    assert used['used_confirmation_identities'] == used['train'] == used['dev'] == used['calibration'] == used['confirmation'] == []
    assert used['engineering_candidate_execution_counts'] == 'UNKNOWN_NO_RAW_RECEIPT'
    assert used['actual_oracle_labels_read_by_scorer'] == 0
    previous_cont = loads((ROOT.parent / 'controls-source/CONTINUATION.json').read_bytes())
    previous_ref = previous_cont['rejection_ledger']
    checked(previous_ref)
    old_ledger = read(previous_ref['path'])
    ledger = read(E + 'REJECTION_LEDGER.json')
    assert ledger['rejections'][:-1] == old_ledger['rejections']
    assert ledger['rejections'][-1]['epoch'] == 37
    assert ledger['rejections'][-1]['scientific_status'] == replay['status']
    assert ledger['rejections'][-1]['results'] == ref(E + 'RESULTS.json')
    assert ledger['epoch37_exceptional_blocked_checkpoint'] == info
    assert all(canonical(ledger[k]) == canonical(v) for k, v in old_ledger.items() if k != 'rejections')
    report = {
        'schema_version': 1, 'epoch': 37, 'kind': result['kind'],
        'binding_scope': 'EXCEPTION_ONLY_METADATA_IDENTITY', 'checks_passed': True,
        'publication_binding_checks_passed': True, 'frozen_evaluation_checks_passed': False,
        'engineering_passed': False, 'readiness_qualified': False,
        'scientific_authorization': 0, 'scorer_EVALUATE_invocations': 0, 'scorer_BIND_invocations': 0,
        'every_original_replay_field_preserved': True, 'original_replay_field_count': len(replay),
        'exact_new_metadata_fields': ['exceptional_blocked_checkpoint'],
        'frozen_physical_closure_passed': False, 'frozen_unknown_physical_ownership': True,
        'internal_operation_counts': 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT',
        'logical_dispatch_slots_burned': 1, 'remaining_scientific_retry_paid_GPU_slots': 0,
        'used_confirmation_identities': [], 'exposed_engineering_identity_count': 12,
        'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
        'official_SOTA_verified': False, 'official_rank': None, 'accuracy': None,
        'prior_rejection_history_preserved': True,
        'evidence': {'qualification_replay': frozen, 'results': ref(E + 'RESULTS.json'),
                     'frozen_observer': info['frozen_observer'],
                     'source_review': info['source_review'],
                     'independent_preworker_resolution': info['independent_preworker_resolution'],
                     'used_identities': ref(E + 'USED_CONFIRMATION_IDENTITIES.json'),
                     'rejection_ledger': ref(E + 'REJECTION_LEDGER.json')},
        'scope_limits': [
            'This is a stdlib equality/hash/metadata audit, not the frozen scientific scorer BIND or a new EVALUATE.',
            'Captured runtime operations remain UNKNOWN; the retained source traceback supports only a separately scoped pre-worker inference.',
            'No actual12 case content, original labels, model/tokenizer/native, host probe, network or Git action is performed.',
            'Actual publication stage and external readback remain separate required reviews.'
        ],
        'reviewer_source': {'path': str(Path(__file__)), 'bytes': Path(__file__).stat().st_size,
                            'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    }
    target = OUT / 'EXCEPTION_ONLY_METADATA_BINDING_v1.json'
    with target.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'path': str(target), 'bytes': target.stat().st_size,
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
