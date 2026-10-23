"""Reporting-only immutable assembly after one sealed, independently rejected DEV run.
Does not import models/tokenizers/native code, read original annotations, fit,
rescore predictions, change source, or execute/authorize another phase.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

P = 'experiments/sota-2026-10-22/'
OLD = '01c42365b8d79c968ea4f49120a5c1d71b9e0687'
PUBLISHED = '9c79f7d65c7182f9139d1d558acfb9f4ef9d1fad'
DEV_IDS = [470, 423, 109, 418, 613, 580, 167, 393]
CONF_IDS = [308, 159, 284, 501, 267, 494, 261, 313]


def read(path):
    path = Path(path)
    assert path.absolute() == path.resolve()
    assert not any(x.is_symlink() for x in [path, *path.parents])
    return json.loads(path.read_text())


def ref(root, name):
    path = root / name
    assert path == path.resolve() and path.is_relative_to(root)
    b = path.read_bytes()
    return {'path': name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def write(root, name, value):
    path = root / name
    assert not path.exists() and not path.is_symlink()
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    return ref(root, name)


def main():
    ap = argparse.ArgumentParser()
    for n in ('project', 'kit', 'identity-report', 'analysis-report'):
        ap.add_argument('--' + n, type=Path, required=True)
    a = ap.parse_args(); root = a.project.resolve()
    assert root == a.project.absolute()
    def get(n): return read(root / (P + n))
    def identity(n): return ref(root, P + n)
    def save(n, v): return write(root, P + 'epoch20/' + n, v)
    audit = get('audit/epoch20/acceptance-rejection.dev.json')
    raw = get('epoch20/runs/dev/raw.json')
    execution = get('epoch20/runs/dev/execution.json')
    gold = get('audit/epoch20/gold.dev.json')
    closure = get('epoch20/CLOSED_SLOTS.json')
    plan = get('epoch20/plan.json')
    old_cont = read(a.kit / 'CONTINUATION.json')
    assert ref(root, P + 'epoch20/plan.json')['sha256'] == '71a57839575aada391bb544a61d3b03902f3bb6ab28c9a1d455efdefb99bf7ba'
    assert audit['checks_passed'] is True and audit['status'] == 'REJECTED_DEV_GATE'
    assert audit['engineering_qualified'] is True and audit['runtime_gate_passed'] is True
    assert audit['accepted_for_confirmation'] is False
    assert audit['metrics']['checks']['all_three_classes_correct_at_least_once'] is False
    assert raw['status'] == 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE' and raw['errors'] == []
    assert raw['counters']['nli_forward_pairs_completed'] == 75
    assert raw['counters']['native_queries_completed'] == 27
    assert raw['counters']['native_index_initializations_completed'] == 9
    assert [r['id'] for r in raw['documents']] == DEV_IDS
    assert [r['document_id'] for r in raw['confirmation_capacity']['document_units']] == CONF_IDS
    assert execution['raw_sha256'] == identity('epoch20/runs/dev/raw.json')['sha256']
    assert all(execution['cleanup'][k] is True for k in
               ('worker_exited', 'all_native_helpers_exited', 'process_group_empty'))
    assert execution['elapsed_seconds'] <= 600 and execution['CPU_affinity'] == [0, 1]
    assert closure['all_slots_closed'] is True
    for n in ('epoch20/runs/confirmation', 'epoch20/CONFIRMATION_ADMISSION.json',
              'legal-transfer/epoch20/inputs.confirmation.json', 'audit/epoch20/gold.confirmation.json'):
        assert not (root / (P + n)).exists()
    assert gold['annotation_choices_accessed'] == 24 and gold['other_role_annotation_choices_accessed'] == 0
    assert gold['labels_used_for_model_fit_calibration_selection'] is False
    reports = [a.identity_report, a.analysis_report]
    for path in reports:
        assert path.is_relative_to(root) and path.is_file()
    at = datetime.now(timezone.utc).isoformat()
    evidence = {k: identity(n) for k, n in {
        'independent_acceptance': 'audit/epoch20/acceptance-rejection.dev.json',
        'independent_tokenizer_replay': 'audit/epoch20/tokenizer-feed-replay.dev.json',
        'independent_postprediction_gold': 'audit/epoch20/gold.dev.json',
        'raw': 'epoch20/runs/dev/raw.json',
        'execution': 'epoch20/runs/dev/execution.json',
        'plan': 'epoch20/plan.json',
        'source_freeze': 'epoch20/candidate-source-freeze.json',
        'closed_slots': 'epoch20/CLOSED_SLOTS.json',
        'postrun_source_process': 'epoch20/reviews/postrun-dev-source-process-independent-v1.json',
        'source_publication_readback': 'epoch20/reviews/source-publication-remote-independent-v1.json',
        'publisher_status': 'epoch20/preparation/publisher-status.json',
        'benchmark_refresh': 'legal-transfer/epoch20/benchmark-refresh.json',
    }.items()}
    evidence['postrun_identities'] = ref(root, str(a.identity_report.relative_to(root)))
    evidence['independent_failure_analysis'] = ref(root, str(a.analysis_report.relative_to(root)))
    actual = {
        'worker_attempts': 1, 'verified_worker_starts': 1, 'completed_native_corpus_batches': 1,
        'NLI_forward_pairs_attempted': 75, 'NLI_forward_pairs_completed': 75,
        'engineering_NLI_pairs': 3, 'legal_matched_arm_NLI_pairs': 72,
        'native_index_initializations': 9, 'native_searches_completed': 27,
        'engineering_native_searches': 3, 'legal_native_searches': 24,
        'model_initializations': 1, 'BGE_initializations': 1, 'BGE_forwards': 26, 'BGE_texts': 143,
        'DEV_documents': 8, 'DEV_questions': 24, 'DEV_annotation_choices_after_seal': 24,
        'CONF_worker_attempts': 0, 'CONF_NLI_pairs': 0, 'CONF_annotation_choices': 0,
        'CONF_capacity_text_tokenization_documents': 8,
        'TRAIN_calibration_fits': 0, 'quantization_initializations': 0,
        'benchmark_HTTP_requests': 0, 'paid_API_calls': 0, 'GPU_calls': 0,
        'CPU_affinity': execution['CPU_affinity'],
        'wall_seconds_including_init_cleanup': execution['elapsed_seconds'],
        'user_seconds': execution['user_seconds'], 'system_seconds': execution['system_seconds'],
        'peak_RSS_bytes': execution['peak_RSS_bytes'], 'resource_scope': execution['resource_scope'],
        'errors': 0, 'owned_live_processes_closed': True, 'all_unused_slots_closed': True,
        'allowed_further_epoch20_attempts': 0,
    }
    next_priority = (
        'Freeze a genuinely new typed-contradiction/context hypothesis using this now-exposed DEV diagnostic. '
        'The saved analysis already found two retained-restriction misclassifications and two whole-unit exclusions; '
        'do not repeat that diagnostic or infer a proven causal remedy from it. Preserve predicate/scope clauses '
        'within matched budgets and evaluate a preselected licensed typed reader or context method in a new study. '
        'The candidate must pass '
        'all-class DEV gates before any unused confirmation. Do not retest this unchanged reader/configuration '
        'or tune on confirmation labels; preserve the native104 champion and zero-paid budget.'
    )
    uncertainty = [
        'One preselected original FP32 reader, three matched evidence arms, eight development documents and 24 questions; no fresh confirmation was executed.',
        'Native evidence selection gains are local matched-reader DEV results, not a direct native104 comparison, full LegalBench score, JevBench rank, ClaimBench score or official SOTA.',
        'The primary reader missed all four contradiction cases. Saved feeds can distinguish observed evidence/prediction differences but do not alone identify a causal remedy.',
        'Training lineage is declared by the pinned model card; exact pretraining dataset revisions and record-level contamination remain unknown.',
        'The fixed reserved confirmation input text was tokenized for capacity only; zero confirmation neural predictions and zero annotation choices were used.',
        'Latency covers this CPU2 diagnostic. Three-arm request and document-amortized timings are not primary-only serving latency; RSS is a process high-water, not a simultaneous aggregate.',
        'Official matching publisher result/rank, sealed JevBench 300-question scorer and complete licensed ClaimBench data/scoring/submission access remain unverified.',
    ]
    roles = {
        'TRAIN': [], 'calibration': [], 'DEV_inputs_projected': True,
        'DEV_document_ids': DEV_IDS, 'DEV_questions': 24, 'DEV_annotation_choices': 24,
        'DEV_retirement_statement': 'Epoch20 original ContractNLI DEV documents [470,423,109,418,613,580,167,393], all 24 query inputs and normalized identities, are permanently exposed DEV; never reuse as fresh confirmation.',
        'confirmation_retired': False, 'confirmation_model_consumed': False,
        'confirmation_annotation_choices_used': 0, 'confirmation_NLI_forward_pairs': 0,
        'confirmation_capacity_input_text_tokenization_documents': 8,
        'confirmation_capacity_source_previously_published': True,
        'confirmation_capacity_did_not_use_labels_or_neural_predictions': True,
        'confirmation_document_ids_reserved_unused': CONF_IDS,
        'original_train_partition_before': {'exposed': 221, 'unreserved': 178, 'reserved': 24},
        'original_train_partition_after': {'exposed': 229, 'unreserved': 170, 'reserved': 24},
        'all_prior_exposed_DEV_forever': True,
    }
    result = {
        'schema_version': 1, 'epoch': 20, 'at': at, 'status': audit['status'],
        'checks_passed': True, 'engineering_qualified': True, 'benchmark_accepted': False,
        'evidence': evidence, 'actual_execution': actual, 'engineering_metrics': audit['engineering'],
        'matched_DEV_metrics': audit['metrics'], 'latency': audit['latency'],
        'runtime_forecast': audit['runtime_forecast'], 'actual_resources': audit['actual_resources'],
        'primary_failure': 'Frozen all-class gate: primary Contradiction correct0/4. Every accuracy-gain/proper-score comparison and the runtime gate passed; acceptance still fails.',
        'post_hoc_observations_not_causal_proof': 'The four contradiction errors occur in three documents. Two literal restriction-containing units were retained but misclassified; two other restriction-containing units were omitted by the frozen whole-unit packing budget. On one shared restriction, positional context predicts contradiction while native context predicts neutral. These are observed feed differences, not official evidence sufficiency annotations or a proven remedy.',
        'arm_display_names': {'ruvector_top2': 'native RuVector evidence', 'same_nli_lexical_top2': 'matched lexical evidence', 'same_nli_positional_first2': 'matched positional evidence'},
        'legacy_arm_name_disclosure': 'Names are historical identifiers, not literal two-unit retrieval; all arms use the same frozen 512-token pair/context budget and shared priority context.',
        'uncertainty': uncertainty, 'official_score': None, 'official_rank': None,
        'champion_promoted': False, 'new_submission': False,
    }
    results_ref = save('RESULTS.json', result)
    inputs = get('legal-transfer/epoch20/inputs.dev.json')
    used = {
        'schema_version': 1, 'epoch': 20, 'status': 'ACTUAL_DEV_EXPOSED_CONF_NEURAL_AND_LABEL_UNUSED',
        'actual_worker_attempts': 1, 'data_roles': roles,
        'DEV_used_identities': [{k: r[k] for k in ('id', 'input_sha256') if k in r} for r in inputs['records']],
        'source_input_projection': identity('legal-transfer/epoch20/inputs.dev.json'),
        'used_confirmation_identities_this_epoch': [], 'fresh_confirmation_predictions': [],
        'confirmation_capacity_only': raw['confirmation_capacity'],
        'prior_unused_confirmation_banks': old_cont['unused_confirmation_sets'],
        'prior_used_confirmation_sets_remain_DEV_forever': get('epoch19/USED_IDENTITIES.json')['prior_used_confirmation_sets_remain_DEV_forever'],
        'identity_audit': evidence['postrun_identities'], 'no_train_calibrate_or_select_on_confirmation_labels': True,
    }
    assert len(used['DEV_used_identities']) == 24
    used_ref = save('USED_IDENTITIES.json', used)
    ledger = copy.deepcopy(get('epoch19/REJECTION_LEDGER.json'))
    rejection = {
        'epoch': 20, 'kind': 'ORIGINAL_FP32_TYPED_READER_NATIVE_MATCHED_EVIDENCE_DEV',
        'status': audit['status'], 'accepted': False,
        'primary_typed_correct': 10, 'lexical_typed_correct': 5, 'positional_typed_correct': 6,
        'primary_binary_correct': 12, 'lexical_binary_correct': 8, 'positional_binary_correct': 10,
        'n': 24, 'Contradiction_correct': 0, 'Contradiction_n': 4,
        'all_pairwise_accuracy_and_proper_score_gates_pass': True,
        'runtime_gate_passed': True, 'reason': result['primary_failure'],
        'independent_report': evidence['independent_acceptance'], 'actual_execution': actual,
        'confirmation_unused': True, 'champion_replaced': False,
    }
    ledger['rejections'].append(rejection); ledger['epoch20_decision'] = rejection
    ledger['next_research_priority'] = next_priority; ledger['used_identity_manifest'] = used_ref
    ledger_ref = save('REJECTION_LEDGER.json', ledger)
    cumulative = copy.deepcopy(old_cont['execution_observed'])
    for k in ('native_corpus_batches', 'native_corpus_batches_completed', 'native_corpus_attempts_including_failed_request'):
        cumulative[k] += 1
    cumulative['engineering_NLI_pair_forwards'] += 3
    cumulative['engineering_native_searches'] += 3
    cumulative.update(epoch20_local_corpus_NLI_pair_forwards=72, epoch20_bounded_worker_attempts=1,
                      cumulative_bounded_native_process_attempts_including_qualification=21)
    cumulative['epoch20_note'] = 'One completed local native corpus attempt, zero HTTP/paid/GPU requests; three engineering pairs plus72matched legal pair forwards. Prior HTTP/train diagnostics remain unchanged.'
    manifest = {
        'schema_version': 1, 'epoch': 20, 'kind': rejection['kind'], 'created_at': at,
        'finished_at': at, 'status': audit['status'], 'checks_passed': True,
        'source_checkpoint': OLD, 'published_premeasurement_commit': PUBLISHED,
        'engineering_qualified': True, 'benchmark_accepted': False, 'accepted': False,
        'actual_execution': actual, 'all_slots_closed': True, 'data_roles': roles,
        'cumulative_execution': cumulative, 'evidence': evidence,
        'results': results_ref, 'used_identities': used_ref, 'rejection_ledger': ledger_ref,
        'model_repository': 'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli',
        'model_revision': '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed',
        'model_precision': 'Original FP32; exact two unused pretraining pooler keys only, all classification-forward parameters loaded, no head initialization or quantization.',
        'model_state_sha256': audit['model_state_sha256'],
        'source_licenses': {'reader': 'MIT declared in immutable official card/API; no separate LICENSE asset.',
                            'data': 'Original Stanford ContractNLI train, CC-BY-4.0, pinned source revision and attribution retained.',
                            'engineering': 'Three exposed authored CC0 engineering canaries; excluded from corpus metrics.'},
        'frozen_scorer': identity('audit/epoch20/protocol_pooler_v1.json'),
        'frozen_replay': identity('audit/epoch20/replay_pooler_v1.py'),
        'next_research_priority': next_priority, 'uncertainty': uncertainty,
        'champion': 'SubmittedNative104/RRF10 unchanged', 'champion_promoted': False,
        'publisher_submission_allowed': False, 'new_submission_or_author_email': False,
        'official_score': None, 'official_rank': None, 'official_SOTA_verified': False,
        'automation_disable_condition_met': False,
        'host_work_lock_release': 'Pending final checkpoint CAS publication and independent actual remote readback.',
    }
    manifest_ref = save('EPOCH_MANIFEST.json', manifest)
    spec = get('epoch20/PLAN_SPEC.json'); helper_path = root / spec['publication_helper']['path']
    assert ref(root, spec['publication_helper']['path']) == spec['publication_helper']
    mod = importlib.util.spec_from_file_location('reviewed_final20_public', helper_path)
    helper = importlib.util.module_from_spec(mod); mod.loader.exec_module(helper)
    current = helper.walk_current(root)
    source_manifest = {
        'schema_version': 1, 'epoch': 20, 'kind': 'EXACT_IMMUTABLE_RESEARCH_ARTIFACTS_THROUGH_FINAL_REPORT_ASSEMBLY',
        'source_checkpoint': OLD, 'published_source_commit': PUBLISHED,
        'historical_and_frozen_source': evidence['source_freeze'],
        'all_new_public_artifacts_through_assembly': [ref(root, n) for n in sorted(current)],
        'external_asset_identities': identity('legal-transfer/epoch20/model-assets.lock.json'),
        'actual_full_predictions': evidence['raw'], 'immutable_epoch_manifest': manifest_ref,
        'excluded': 'This self-referential manifest; external model/runtime/cache bytes; private/raw mail/pages. Later independent final publication reviews are separately pinned in final CHECKPOINT_MANIFEST.',
        'model_native_calls_by_assembler': 0, 'original_annotation_json_reads_by_assembler': 0,
    }
    source_ref = save('SOURCE_MANIFEST.json', source_manifest)
    print(json.dumps({'status': audit['status'], 'manifest': manifest_ref,
                      'results': results_ref, 'used_identities': used_ref, 'source_manifest': source_ref,
                      'rejection_ledger': ledger_ref, 'actual_worker_attempts': 1, 'CONF_attempts': 0}))


if __name__ == '__main__': main()

