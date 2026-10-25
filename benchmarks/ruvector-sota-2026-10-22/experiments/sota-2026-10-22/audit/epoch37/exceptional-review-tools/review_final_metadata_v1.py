"""Final read-only exception-metadata audit; no scientific/runtime/scorer calls."""
import hashlib
import json
from pathlib import Path
import runpy

OWN = Path('/workspace/ruvector-e37-acceptance-audit')
M = runpy.run_path(str(OWN / 'bind_blocked_metadata_v1.py'), run_name='pure_metadata_comparator_dependency')
R, E, A = M['ROOT'], M['E'], M['A']
read, ref, checked, canonical = M['read'], M['ref'], M['checked'], M['canonical']

def ownref(path):
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def main():
    result = read(E + 'RESULTS.json')
    replay = read(A + 'qualification-replay.json')
    info = M['compare'](replay, result)
    assert ref(E + 'RESULTS.json') == {'path': E + 'RESULTS.json', 'bytes': 8702,
        'sha256': '8c56aebf8ab13547e88cf98e535ea843a84f0b1acf37cf591e34915b99ffd95e'}
    binding_rel = A + 'exceptional-metadata-binding-independent-v1.json'
    assert ref(binding_rel)['sha256'] == 'c4b7d946866c8b0e1ec5d22b91a6c946df61e02ab59659d0d6206fc4526da58b'
    binding = read(binding_rel)
    assert binding['binding_scope'] == 'EXCEPTION_ONLY_METADATA_IDENTITY'
    assert binding['checks_passed'] is binding['publication_binding_checks_passed'] is True
    assert binding['frozen_evaluation_checks_passed'] is False
    assert binding['evidence']['results'] == ref(E + 'RESULTS.json')
    assert binding['evidence']['qualification_replay'] == ref(A + 'qualification-replay.json')
    for row in binding['evidence'].values():
        checked(row)
    for name in ('source_review', 'protocol', 'supplement_consistency_review', 'independent_preworker_resolution', 'future_source_guard_review', 'frozen_evaluation', 'frozen_observer'):
        checked(info[name])
    source_review = read(info['source_review']['path'])
    assert source_review['checks_passed'] is True and source_review['exceptional_source_only'] is True
    assert source_review['scientific_authorization'] == 0
    for row in source_review['files']:
        checked(row)
    for row in source_review['frozen_pure_publication_dependencies']:
        checked(row)
    future = read(info['future_source_guard_review']['path'])
    assert future['checks_passed'] is future['future_source_only'] is True
    assert future['applied_to_frozen_E37'] is future['E37_retry_authorized'] is False
    assert len(future['approved_public_source_entries']) == 15
    for row in future['approved_public_source_entries']:
        checked(row)
    future_ready_rel = E + 'future-source-review/asset-identity-fix/READY.v1.json'
    assert ref(future_ready_rel)['sha256'] == future['ready']['sha256']
    assert ref(future_ready_rel)['bytes'] == future['ready']['bytes']
    future_ready = ref(future_ready_rel)
    assert future['actual_model_payload_reads_current_guard_model_native_tokenizer_actual12_EVALUATE_BIND_newdispatch_or_external_mutations_by_auditor'] == 0
    learn = read(E + 'LEARNINGS.json')
    used = read(E + 'USED_CONFIRMATION_IDENTITIES.json')
    plan = read(E + 'plan.json')
    ids = plan['engineering_ids']
    assert len(ids) == len(set(ids)) == 12
    assert learn['status'] == used['status'] == info['status'] == 'EXCEPTIONAL_BLOCKED_CHECKPOINT'
    assert learn['scientific_status'] == result['status'] == 'REJECTED_ENGINEERING_INTEGRITY'
    assert learn['scientific_acceptance'] is False
    assert learn['measured_accuracy'] is learn['proper_scores'] is None
    assert learn['measured_identities'] == used['actual_measured_identities'] == []
    assert learn['planned_source_exposed_engineering_identities_forever'] == used['engineering_publicly_exposed_identities'] == used['planned_engineering_identities'] == ids
    assert learn['used_confirmation_identities'] == used['used_confirmation_identities'] == []
    assert used['train'] == used['dev'] == used['calibration'] == used['confirmation'] == []
    assert used['benchmark_partition_unchanged'] == {'exposed': 325, 'unused': 74, 'protected': 24}
    assert learn['captured_NLI_forward_count'] == 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'
    assert used['engineering_candidate_execution_counts'] == 'UNKNOWN_NO_RAW_RECEIPT'
    assert learn['future_source_review'] == info['future_source_guard_review']
    assert learn['supplement'] == info['independent_preworker_resolution']
    assert learn['supplement_consistency_review'] == info['supplement_consistency_review']
    assert learn['budget_authorized_future_paid_GPU'] == 0
    assert 'unstubbed full real-asset guard admission' in ' '.join(learn['future_steps_proposed_not_executed'])
    assert 'No E37 retry' in ' '.join(learn['future_steps_proposed_not_executed'])
    assert info['cumulative_scope']['epoch37_xxlarge_reader_initialization_attempts'] is None
    previous = json.loads((R.parent / 'controls-source/CONTINUATION.json').read_bytes())
    obs = previous['execution_observed']
    assert info['cumulative_scope']['known_prior_corpus_attempts'] == obs['epoch36_cumulative_corpus_attempts'] == 33
    assert info['cumulative_scope']['known_prior_completed_corpus_batches'] == obs['epoch36_cumulative_completed_corpus_batches'] == 31
    assert info['cumulative_scope']['bounded_outer_process_attempts'] == obs['epoch36_cumulative_bounded_native_process_attempts'] + info['verified_launcher_starts'] == 38
    assert info['cumulative_scope']['legacy_dedicated_qualification_attempts'] == obs['native_qualification_attempts'] == 6
    checked(previous['rejection_ledger'])
    oldledger = read(previous['rejection_ledger']['path'])
    ledger = read(E + 'REJECTION_LEDGER.json')
    assert ledger['rejections'][:-1] == oldledger['rejections']
    assert all(canonical(ledger[k]) == canonical(v) for k, v in oldledger.items() if k != 'rejections')
    assert ledger['rejections'][-1]['epoch'] == 37 and ledger['rejections'][-1]['results'] == ref(E + 'RESULTS.json')
    budget = ledger['epoch37_budget']
    assert budget['logical_dispatch_slots_burned'] == 1
    assert budget['actual_internal_counts'] == 'UNKNOWN' and budget['all_unspent_slots_permanently_closed'] is True
    assert all(type(budget[k]) is int and budget[k] == 0 for k in ('workers_remaining', 'native_corpus_batches_remaining', 'confirmation_remaining', 'paid_GPU_remaining'))
    supplement = read(info['independent_preworker_resolution']['path'])
    for row in supplement['evidence'].values():
        checked(row)
    for name in supplement['source_failure_boundary']['known_missing_canonical_paths']:
        assert not (R / name).exists()
    assert not (R / (E + 'SOURCE_MANIFEST.json')).exists()
    assert not (R / (E + 'EPOCH_MANIFEST.json')).exists()
    tools = []
    for name in ('review_supplement_v1.py', 'review_exception_sources_v1.py', 'bind_blocked_metadata_v1.py', 'review_final_metadata_v1.py'):
        row = ownref(OWN / name)
        tools.append({'source': row, 'public_target': A + 'exceptional-review-tools/' + name,
                      'scope': 'Read-only metadata/source review evidence; no science, scorer, host or external mutation authorization.'})
    report = {
        'schema_version': 1, 'epoch': 37, 'kind': result['kind'],
        'status': 'APPROVED_EXCEPTIONAL_BLOCKED_METADATA_PUBLICATION_ONLY',
        'checks_passed': True, 'exceptional_checkpoint_publication_allowed': True,
        'engineering_passed': False, 'readiness_qualified': False, 'diagnostic_qualified': False,
        'frozen_evaluation_checks_passed': False, 'scientific_status': result['status'],
        'publication_binding_checks_passed': True, 'scientific_authorization': 0,
        'results': ref(E + 'RESULTS.json'), 'binding': ref(binding_rel),
        'independent_preworker_resolution': info['independent_preworker_resolution'],
        'exceptional_source_review': info['source_review'], 'exceptional_protocol': info['protocol'],
        'supplement_consistency_review': info['supplement_consistency_review'],
        'future_source_guard_review': info['future_source_guard_review'],
        'future_reviewed_source_count': 15, 'future_ready': future_ready,
        'used_identities': ref(E + 'USED_CONFIRMATION_IDENTITIES.json'),
        'learnings': ref(E + 'LEARNINGS.json'), 'rejection_ledger': ref(E + 'REJECTION_LEDGER.json'),
        'every_original_frozen_replay_field_unchanged': True, 'original_replay_field_count': len(replay),
        'frozen_physical_closure_passed': False, 'frozen_unknown_physical_ownership': True,
        'separate_source_bound_preworker_resolution_supported': True,
        'supervisor_absent': False, 'direct_FD_entries': None, 'FD_enumeration': 'DENIED_EACCES',
        'observed_launcher_exit_code': None,
        'captured_internal_operation_counts': 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT',
        'source_inference': 'Pinned launcher212 guard traceback precedes reservation220 and sole worker Popen263; this inference is distinct from missing empirical receipts and never replaces frozen observer/evaluation outcomes.',
        'logical_dispatch_slots_burned': 1, 'verified_outer_launcher_starts': 1,
        'all_remaining_scientific_retry_paid_GPU_slots': 0,
        'accuracy': None, 'proper_scores': None, 'new_native_result': None,
        'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
        'official_SOTA_verified': False, 'official_rank': None,
        'training_or_model_selection_calibration_and_official_eligibility': 'HOLD',
        'source_exposed_engineering_ids_count': 12, 'used_confirmation_identities': [],
        'benchmark_partition_unchanged_declared_history': {'exposed': 325, 'unused': 74, 'protected': 24},
        'prior_rejection_history_preserved': True,
        'learnings_and_future_direction_consistent': True,
        'future_repair_applied_or_executed': False,
        'public_reviewer_comparator_source_whitelist': tools,
        'remaining_publication_steps': [
            'Root copies this exact final report and any approved exact reviewer-source snapshots BEFORE final SOURCE_MANIFEST/EPOCH_MANIFEST. No later project additions or edits are permitted.',
            'New manifests and controls must retain the reviewed failed scientific status, false frozen closure/integrity, null captured counts, zero remaining slots and complete historical source/checkpoint identities.',
            'Main independent auditor must verify exact sealed manifests, full controls/stage/transport tuples and all source-history preservation before root invokes the scoped publisher.',
            'Root may publish only against exact a93 source-parent CAS, forcefalse, dedicated branch, durable write-ahead journal and read-only main. Uncertain mutation stops.',
            'Independent actual remote full-tree/control/commit readback is required before physical guardian release; this report is not that readback or a release receipt.'
        ],
        'limits': [
            'The scientific quality gate was not evaluated. Rejected integrity and lack of readouts do not establish that the certificate algorithm succeeded or failed on these cases.',
            'No actual12 candidate inputs, oracle content, protected benchmark identities, model/tokenizer assets or runtime inference were opened or invoked for this review.',
            'Scoped kernel closure is based on retained exact captures/source, not a new process probe or a claim that all arbitrary detached processes are absent.',
            'Known prior33 corpus attempts/31completions remain lower bounds. E37 internal/corpus/model operations and resources remain UNKNOWN; only one outer launcher is counted separately.',
            'Declared officialHTTP894/2 scope is preserved from the reviewed exceptional protocol; no official API result/rank refresh was performed by this audit.',
            'Future source fixtures are source-only evidence, not proof of an actual complete guard admission, model eligibility, benchmark improvement or generalization.'
        ],
        'audit_actions': {'pure_stdlib_metadata_hash_comparison': True,
            'new_model_tokenizer_native_runtime_calls': 0, 'scorer_EVALUATE_calls': 0,
            'scorer_BIND_calls': 0, 'host_or_proc_probes': 0, 'Git_or_external_calls': 0,
            'root_project_writes': 0},
        'reviewer_source': ownref(Path(__file__))
    }
    target = OWN / 'EXCEPTION_FINAL_PUBLICATION_REVIEW_v1.json'
    with target.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(ownref(target)))

if __name__ == '__main__':
    main()
