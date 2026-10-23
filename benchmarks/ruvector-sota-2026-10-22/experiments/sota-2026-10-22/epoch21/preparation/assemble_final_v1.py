"""Assemble reporting artifacts from one sealed independently rejected DEV run.

No models, tokenizer parsers, original annotations, rescoring or new admission.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.util
import json
import os

P = 'experiments/sota-2026-10-22/'
SOURCE = '0c4392bb8b13a901dc416882f850230c1075fb6a'
PUBLISHED = '43d9cc4230d1fcb3eb0e2758c1980af24f72bbb3'
DEV = [303, 176, 113, 186, 485, 512, 219, 520]
CONF = [308, 159, 284, 501, 267, 494, 261, 313]


def body(path):
    path = Path(path).absolute()
    assert path == path.resolve() and path.is_file()
    assert not any(x.is_symlink() for x in [path, *path.parents])
    return path.read_bytes()


def read(path): return json.loads(body(path))


def identity(root, name):
    path = root / name
    assert path.resolve().is_relative_to(root)
    data = body(path)
    return {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def save(root, name, value):
    path = root / name
    assert path == path.resolve() and not os.path.lexists(path)
    with path.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    return identity(root, name)


def main():
    ap = argparse.ArgumentParser()
    for n in ('project', 'kit', 'identity-report', 'analysis-report'):
        ap.add_argument('--' + n, type=Path, required=True)
    a = ap.parse_args(); root = a.project.absolute()
    assert root == root.resolve()
    def get(n): return read(root / (P + n))
    def ref(n): return identity(root, P + n)
    def put(n, v): return save(root, P + 'epoch21/' + n, v)
    audit = get('audit/epoch21/acceptance-rejection.dev.json')
    raw = get('epoch21/runs/dev/raw.json'); execution = get('epoch21/runs/dev/execution.json')
    gold = get('audit/epoch21/gold.dev.json'); slots = get('epoch21/CLOSED_SLOTS.json')
    old = read(a.kit / 'CONTINUATION.json')
    assert ref('epoch21/plan.json')['sha256'] == '22650c8d7fc569e45c5a1129b58b8db5feabac2f105b9227648088e9d6f8b6ba'
    assert ref('audit/epoch21/acceptance-rejection.dev.json')['sha256'] == '56063f53d0ed44267c04e9798eb592d7342f73e37a90ffbf6c2d15eab3199170'
    assert ref('epoch21/runs/dev/raw.json')['sha256'] == 'ed86bc69cdf6627e5ef10909ca49771d1da72c95fa360173c71cc175af1fd03f'
    assert audit['checks_passed'] is True and audit['status'] == 'REJECTED_DEV_GATE'
    assert audit['engineering_qualified'] is True and audit['accepted_for_confirmation'] is False
    assert audit['runtime_gate_passed'] is True and audit['metrics']['passed'] is False
    assert raw['status'] == 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE' and raw['errors'] == []
    assert execution['raw_sha256'] == ref('epoch21/runs/dev/raw.json')['sha256']
    assert execution['worker_exit_code'] == 0 and execution['error'] is None
    assert execution['elapsed_seconds'] <= 600 and execution['CPU_affinity'] == [0, 1]
    assert all(execution['cleanup'][k] is True for k in ('worker_exited', 'all_native_helpers_exited', 'process_group_empty'))
    assert slots['all_slots_closed'] is True
    assert [d['id'] for d in raw['documents']] == DEV
    assert [d['document_id'] for d in raw['confirmation_capacity']['document_units']] == CONF
    c = raw['counters']
    assert (c['nli_forward_pairs_completed'], c['native_queries_completed'], c['native_index_initializations_completed']) == (75, 27, 9)
    assert c['benchmark_documents_completed'] == 8 and c['benchmark_questions_completed'] == 24
    assert gold['annotation_choices_accessed'] == 24 and gold['other_role_annotation_choices_accessed'] == 0
    for n in ('epoch21/runs/confirmation', 'epoch21/CONFIRMATION_ADMISSION.json',
              'legal-transfer/epoch21/inputs.confirmation.json', 'audit/epoch21/gold.confirmation.json'):
        assert not os.path.lexists(root / (P + n))
    evidence = {k: ref(n) for k, n in {
        'independent_acceptance': 'audit/epoch21/acceptance-rejection.dev.json',
        'independent_tokenizer_replay': 'audit/epoch21/tokenizer-feed-replay.dev.json',
        'independent_postprediction_gold': 'audit/epoch21/gold.dev.json',
        'raw': 'epoch21/runs/dev/raw.json', 'execution': 'epoch21/runs/dev/execution.json',
        'plan': 'epoch21/plan.json', 'source_freeze': 'epoch21/candidate-source-freeze.json',
        'closed_slots': 'epoch21/CLOSED_SLOTS.json',
        'postrun_source_process': 'epoch21/reviews/postrun-dev-source-process-independent-v1.json',
        'source_publication_readback': 'epoch21/reviews/source-publication-remote-independent-v1.json',
        'publisher_status': 'epoch21/preparation/publisher-status.json',
        'benchmark_refresh': 'legal-transfer/epoch21/benchmark-refresh.json'}.items()}
    for key, path in [('postrun_identities', a.identity_report), ('post_hoc_context_diagnosis', a.analysis_report)]:
        path = path.absolute(); assert path.is_relative_to(root)
        evidence[key] = identity(root, path.relative_to(root).as_posix())
    actual = {
        'worker_attempts': 1, 'verified_worker_starts': 1, 'completed_native_corpus_batches': 1,
        'NLI_forward_pairs_attempted': c['nli_forward_pairs_attempted'], 'NLI_forward_pairs_completed': c['nli_forward_pairs_completed'],
        'engineering_NLI_pairs': 3, 'legal_matched_arm_NLI_pairs': 72,
        'native_index_initializations': c['native_index_initializations_completed'], 'native_searches_completed': c['native_queries_completed'],
        'engineering_native_searches': 3, 'legal_native_searches': 24,
        'model_initializations': c['model_initializations_completed'], 'BGE_initializations': c['BGE_initializations_completed'],
        'BGE_forwards': c['BGE_forwards_completed'], 'BGE_texts': c['BGE_texts_completed'],
        'DEV_documents': 8, 'DEV_questions': 24, 'DEV_annotation_choices_after_seal': 24,
        'CONF_worker_attempts': 0, 'CONF_NLI_pairs': 0, 'CONF_annotation_choices': 0,
        'CONF_capacity_text_tokenization_documents': 8, 'TRAIN_calibration_fits': c['training_calibration_fits'],
        'quantization_initializations': c['quantization_initializations'], 'benchmark_HTTP_requests': c['benchmark_HTTP_requests'],
        'paid_API_calls': c['paid_API_calls'], 'GPU_calls': c['GPU_calls'],
        'CPU_affinity': execution['CPU_affinity'], 'wall_seconds_including_init_cleanup': execution['elapsed_seconds'],
        'user_seconds': execution['user_seconds'], 'system_seconds': execution['system_seconds'],
        'peak_RSS_bytes': execution['peak_RSS_bytes'], 'resource_scope': execution['resource_scope'],
        'errors': len(raw['errors']), 'owned_live_processes_closed': True,
        'all_unused_slots_closed': True, 'allowed_further_epoch21_attempts': 0}
    roles = {
        'TRAIN': [], 'calibration': [], 'DEV_inputs_projected': True, 'DEV_document_ids': DEV,
        'DEV_questions': 24, 'DEV_annotation_choices': 24,
        'DEV_retirement_statement': 'Epoch21 original ContractNLI DEV documents [303,176,113,186,485,512,219,520], all24 query inputs and normalized identities, are permanently exposed DEV; never fresh confirmation.',
        'confirmation_retired': False, 'confirmation_model_consumed': False,
        'confirmation_annotation_choices_used': 0, 'confirmation_NLI_forward_pairs': 0,
        'confirmation_capacity_input_text_tokenization_documents': 8,
        'confirmation_capacity_did_not_use_labels_or_neural_predictions': True,
        'confirmation_document_ids_reserved_unused': CONF,
        'original_train_partition_before': {'exposed': 229, 'unreserved': 170, 'reserved': 24},
        'original_train_partition_after': {'exposed': 237, 'unreserved': 162, 'reserved': 24},
        'all_prior_exposed_DEV_forever': True}
    failure = ('Frozen all-class gate fails: native Contradiction0/4. Each of four typed/binary matched-control accuracy gains is1, below required2. All proper-score and runtime gates pass but cannot override rejection.')
    next_priority = ('Changing the pretrained typed reader alone did not resolve native legal contradiction decisions. '
        'Use the saved epoch21 clause/context diagnosis to preselect one materially new predicate/scope-preserving evidence packing hypothesis with matched same-reader controls. '
        'Do not rerun these exposed24 as fresh confirmation or repeat an unchanged reader/packing grid. '
        'Freeze a new source/role protocol before any future unused DEV; preserve unused confirmation labels and submitted native104; zero paid budget remains.')
    uncertainty = [
        'One preselected reader, eight new DEV contracts and24 questions; no confirmation execution. Different DEV documents prevent a direct reader comparison to epoch20.',
        'Matched-reader retrieval diagnostics are not a direct native104 comparison, full LegalBench score, JevBench rank, ClaimBench score or official SOTA.',
        'Native made no correct contradiction decision on four cases. Saved feed/context differences are descriptive, not official evidence sufficiency annotations or a proven causal remedy.',
        'The immutable official model card declares training lineage and MIT licensing; exact training corpus revisions and record-level pretraining overlap remain unknown.',
        'Reserved confirmation input texts were already public and tokenized only for capacity. Zero confirmation neural predictions or annotation choices; do not claim previously unseen input text.',
        'Original corpus JSON annotation fields enter memory during logical role-only input projection; logical access controls do not establish OS label isolation.',
        'Reported request latency covers all three matched arms, not primary-only serving. Peak RSS is largest reaped-child high-water, not simultaneous aggregate memory.',
        'A premeasurement exec transport disconnection recovered before any worker. Source/asset hashes, absent interrupted draft and same exact kernel lock were reverified before resuming; no uncertain external mutation was retried.',
        'Official publisher result/rank and sealed JevBench scorer remain unverified; full licensed ClaimBench data/scoring/submission access remains unverified.']
    at = datetime.now(timezone.utc).isoformat()
    result = {'schema_version': 1, 'epoch': 21, 'at': at, 'status': audit['status'],
        'checks_passed': True, 'engineering_qualified': True, 'benchmark_accepted': False,
        'evidence': evidence, 'actual_execution': actual, 'engineering_metrics': audit['engineering'],
        'matched_DEV_metrics': audit['metrics'], 'latency': audit['latency'],
        'runtime_forecast': audit['runtime_forecast'], 'actual_resources': audit['actual_resources'],
        'primary_failure': failure, 'uncertainty': uncertainty,
        'legacy_arm_name_disclosure': 'ruvector_top2, same_nli_lexical_top2 and same_nli_positional_first2 are legacy identifiers, not literal two-unit contexts. Frozen arms scan ranked anchors under the same512-token pair budget and shared definition priority.',
        'official_score': None, 'official_rank': None, 'champion_promoted': False, 'new_submission': False}
    results_ref = put('RESULTS.json', result)
    inputs = get('legal-transfer/epoch21/inputs.dev.json')
    used = {'schema_version': 1, 'epoch': 21, 'status': 'ACTUAL_DEV_EXPOSED_CONF_NEURAL_AND_LABEL_UNUSED',
        'actual_worker_attempts': 1, 'data_roles': roles,
        'DEV_used_identities': [{k: r[k] for k in ('id', 'input_sha256')} for r in inputs['records']],
        'source_input_projection': ref('legal-transfer/epoch21/inputs.dev.json'),
        'used_confirmation_identities_this_epoch': [], 'fresh_confirmation_predictions': [],
        'confirmation_capacity_only': raw['confirmation_capacity'], 'prior_unused_confirmation_banks': old['unused_confirmation_sets'],
        'prior_used_confirmation_sets_remain_DEV_forever': get('epoch20/USED_IDENTITIES.json')['prior_used_confirmation_sets_remain_DEV_forever'],
        'identity_audit': evidence['postrun_identities'], 'no_train_calibrate_or_select_on_confirmation_labels': True}
    assert len(used['DEV_used_identities']) == 24
    used_ref = put('USED_IDENTITIES.json', used)
    ledger = copy.deepcopy(get('epoch20/REJECTION_LEDGER.json'))
    rejection = {'epoch': 21, 'kind': 'ORIGINAL_FP16_TO_FP32_TYPED_DEBERTA_NATIVE_MATCHED_EVIDENCE_DEV',
        'status': audit['status'], 'accepted': False, 'n': 24,
        'typed_metrics': audit['metrics']['typed_metrics'], 'binary_metrics': audit['metrics']['binary_metrics'],
        'all_pairwise_accuracy_gates_pass': False, 'all_pairwise_proper_score_gates_pass': True,
        'all_class_gate_pass': False, 'runtime_gate_passed': True, 'reason': failure,
        'independent_report': evidence['independent_acceptance'], 'actual_execution': actual,
        'confirmation_unused': True, 'champion_replaced': False}
    ledger['rejections'].append(rejection); ledger['epoch21_decision'] = rejection
    ledger['next_research_priority'] = next_priority; ledger['used_identity_manifest'] = used_ref
    ledger_ref = put('REJECTION_LEDGER.json', ledger)
    cumulative = copy.deepcopy(old['execution_observed'])
    for k in ('native_corpus_batches', 'native_corpus_batches_completed', 'native_corpus_attempts_including_failed_request'):
        cumulative[k] += 1
    cumulative['engineering_NLI_pair_forwards'] += 3; cumulative['engineering_native_searches'] += 3
    cumulative.update(epoch21_local_corpus_NLI_pair_forwards=72, epoch21_bounded_worker_attempts=1,
        cumulative_bounded_native_process_attempts_including_qualification=22)
    cumulative['epoch21_note'] = 'One completed local native corpus attempt,3engineering+72legal NLI pairs,0HTTP/paid/GPU calls. Prior HTTP/train/qualification counters retained.'
    manifest = {'schema_version': 1, 'epoch': 21, 'kind': rejection['kind'], 'created_at': at,
        'finished_at': at, 'status': audit['status'], 'checks_passed': True,
        'source_checkpoint': SOURCE, 'published_premeasurement_commit': PUBLISHED,
        'engineering_qualified': True, 'benchmark_accepted': False, 'accepted': False,
        'actual_execution': actual, 'all_slots_closed': True, 'data_roles': roles,
        'cumulative_execution': cumulative, 'evidence': evidence, 'results': results_ref,
        'used_identities': used_ref, 'rejection_ledger': ledger_ref,
        'model_repository': 'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli',
        'model_revision': 'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7',
        'model_precision': 'Original394 learned FP16 tensors explicitly converted to FP32 CPU; all learned values exact, one original I64 position buffer exact; all loading errors empty; no quantization or head initialization.',
        'model_state_sha256': audit['model_state_sha256'],
        'source_licenses': {'reader': 'MIT declared in immutable official card/API; no separate LICENSE asset.',
            'data': 'Original Stanford ContractNLI train CC-BY-4.0, exact source revision and attribution retained.',
            'engineering': 'Three exposed authored CC0 canaries, excluded from corpus metrics.'},
        'frozen_scorer': ref('audit/epoch21/protocol.json'), 'frozen_replay': ref('audit/epoch21/replay.py'),
        'next_research_priority': next_priority, 'uncertainty': uncertainty,
        'champion': 'SubmittedNative104/RRF10 unchanged', 'champion_promoted': False,
        'publisher_submission_allowed': False, 'new_submission_or_author_email': False,
        'official_score': None, 'official_rank': None, 'official_SOTA_verified': False,
        'automation_disable_condition_met': False,
        'host_work_lock_release': 'Pending final checkpoint CAS and independent actual remote readback.'}
    manifest_ref = put('EPOCH_MANIFEST.json', manifest)
    spec = get('epoch21/PLAN_SPEC.json'); h = spec['publication_helper']; assert identity(root, h['path']) == h
    ms = importlib.util.spec_from_file_location('reviewed21publication', root / h['path'])
    helper = importlib.util.module_from_spec(ms); ms.loader.exec_module(helper)
    current = helper.walk_current(root)
    sources = {'schema_version': 1, 'epoch': 21, 'kind': 'IMMUTABLE_RESEARCH_ARTIFACTS_THROUGH_FINAL_ASSEMBLY',
        'source_checkpoint': SOURCE, 'published_source_commit': PUBLISHED,
        'historical_and_frozen_source': evidence['source_freeze'],
        'all_new_public_artifacts_through_assembly': [identity(root, n) for n in sorted(current)],
        'external_asset_identities': ref('legal-transfer/epoch21/model-assets.lock.json'),
        'actual_full_predictions': evidence['raw'], 'immutable_epoch_manifest': manifest_ref,
        'excluded': 'Self-referential SOURCE_MANIFEST; external model/runtime/cache bytes; private/raw mail/pages. Later independent final reviews are pinned by final CHECKPOINT_MANIFEST.',
        'model_native_calls_by_assembler': 0, 'original_annotation_json_reads_by_assembler': 0}
    source_ref = put('SOURCE_MANIFEST.json', sources)
    print(json.dumps({'manifest': manifest_ref, 'results': results_ref, 'used_identities': used_ref,
        'source_manifest': source_ref, 'rejection_ledger': ledger_ref, 'new_native_model_calls': 0}))


if __name__ == '__main__': main()
