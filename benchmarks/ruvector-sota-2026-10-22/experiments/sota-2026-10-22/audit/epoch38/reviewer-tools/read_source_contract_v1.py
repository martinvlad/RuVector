"""E38 source/contract identity review; no candidate or scorer imports/calls."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f/project')
OWN = Path('/workspace/ruvector-e38-acceptance-audit')
P = 'experiments/sota-2026-10-22/'
E = P + 'epoch38/'
A = P + 'audit/epoch38/'

def body(rel):
    path = ROOT / rel
    assert path.is_file() and not any(p.is_symlink() for p in (path, *path.parents))
    return path.read_bytes()

def ref(rel):
    data = body(rel)
    return {'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def read(rel):
    return json.loads(body(rel))

def checked(row):
    assert set(row) == {'path', 'bytes', 'sha256'} and ref(row['path']) == row

def main():
    expected = {
        E + 'plan.json': (57728, 'aa4f4f26aa3e673b92ec9f6c96927379abe9ec22d9caa7b0b3e83948d5935b1b'),
        E + 'source-freeze.json': (35132, 'a5f44f55a63924f3a6ba2caf4f9aac4ca1c6ec4b6a87a4c3a5674068b0e9adc4'),
        A + 'protocol.json': (9238, '41f2ed352dabad1ac228b19541bf82a4d3dc116ece0c0f3d79b94f936c6c4974')}
    for path, (size, digest) in expected.items():
        assert ref(path) == {'path': path, 'bytes': size, 'sha256': digest}
    plan, freeze, protocol = (read(path) for path in expected)
    assert plan['source_checkpoint'] == freeze['source_checkpoint'] == protocol['source_checkpoint'] == '7c50ba99848f6a13707eeec6c4947291a8478e5c'
    assert len(plan['pins']) == len({v['path'] for v in plan['pins']}) == 157
    assert len(freeze['entries']) == len({v['path'] for v in freeze['entries']}) == 150
    pins = {v['path']: v for v in plan['pins']}
    assert all(pins[row['path']] == row for row in freeze['entries'])
    selected = [plan[k] for k in ('protocol', 'root_contract', 'metrics_policy', 'scorer', 'pretrained_model_source', 'model_profiles', 'model_assets_expected', 'model_assets_validator', 'real_model_assets_guard_receipt')]
    selected += [protocol[k] for k in ('core_source_manifest', 'core_source_ready', 'scorer_source_ready_v1', 'candidate_protocol')]
    for row in selected:
        checked(row)
    contract = read(plan['root_contract']['path'])
    candidate_protocol = read(protocol['candidate_protocol']['path'])
    assert plan['engineering_gate'] == protocol['engineering_gate'] == candidate_protocol['engineering_gate'] == contract['gate']
    assert plan['primary'] == protocol['primary'] == contract['primary'] == 'native_verified'
    assert plan['metric_arm_names'] == protocol['metric_arms'] == contract['arms'] == ['full_raw', 'native_raw', 'native_verified', 'lexical_verified', 'full_verified']
    assert plan['raw_context_names'] == protocol['raw_contexts'] == contract['raw_contexts'] == ['full_source', 'native_coverage', 'lexical_coverage']
    assert plan['readout_reuse_map'] == protocol['arm_to_measured_context'] == contract['arm_to_measured_context']
    assert plan['actual_NLI_forwards'] == protocol['actual_NLI_forwards'] == contract['actual_NLI_forwards'] == 36
    assert plan['final_derived_forecasts'] == protocol['final_derived_forecasts'] == contract['final_derived_forecasts'] == 60
    assert plan['data_roles'] == protocol['data_roles'] == contract['data_roles'] == dict.fromkeys(['train', 'dev', 'calibration', 'confirmation'], [])
    assert plan['used_confirmation_identities'] == protocol['used_confirmation_identities'] == []
    assert len(plan['engineering_ids']) == len(set(plan['engineering_ids'])) == 12
    assert protocol['official_eligibility'] == protocol['confirmation_eligibility'] == 'HOLD'
    assert protocol['no_benchmark_generalization_claim'] is True and plan['promotion_allowed'] is False
    assert plan['benchmark_accuracy'] is None and plan['official_rank'] is None
    assert all(plan[k] is False for k in ('benchmark_accepted', 'champion_promoted', 'new_submission', 'official_SOTA_verified'))
    metrics = read(plan['metrics_policy']['path'])
    assert metrics['NLL'] == 'UNCLIPPED_STABLE_SOURCE_LOGIT_LOGSOFTMAX_WITH_SAME_CANONICAL_CLASS_PERMUTATION'
    assert metrics['acceptance_roundoff_tolerance'] == 1e-12 and metrics['NLL_clipping_floor_diagnostic_only'] == 1e-12
    assert metrics['canonical_from_source'] == [2, 0, 1]
    assert plan['probability_policy'] == protocol['probability_policy'] == contract['probability_policy']
    assert plan['probability_policy']['calibrated_posterior_claim'] is False
    guard = read(plan['real_model_assets_guard_receipt']['path'])
    assert guard['status'] == 'PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE'
    assert guard['function'] == 'C.verify_model_assets' and guard['function_calls'] == 1
    assert guard['stubs_used'] is False and guard['monkeypatches'] == []
    assert guard['model_native_tokenizer_initializations_or_calls'] == guard['case_oracle_reads'] == 0
    assert guard['expected_catalog'] == plan['model_assets_expected']
    previous_rel = P + 'epoch37/RESULTS.json'
    assert ref(previous_rel)['sha256'] == '8c56aebf8ab13547e88cf98e535ea843a84f0b1acf37cf591e34915b99ffd95e'
    previous = read(previous_rel)
    assert previous['status'] == 'REJECTED_ENGINEERING_INTEGRITY' and previous['checks_passed'] is False
    old = previous['exceptional_blocked_checkpoint']
    assert old['internal_operation_counts'] == 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'
    assert old['model_initializations'] is old['corpus_batches_attempted'] is old['corpus_batches_completed'] is None
    assert 'cannot make cumulative unknown totals known' in protocol['historical_uncertainty_policy']
    report = {
        'schema_version': 1, 'epoch': 38,
        'status': 'SOURCE_IDENTITY_AND_FROZEN_ACCEPTANCE_CRITERIA_UNDERSTOOD_AWAIT_ACTUAL_EVIDENCE',
        'checks_passed': True, 'scope': 'Read-only contract/source metadata readiness; no execution, empirical quality or final publication approval.',
        'scientific_authorization': 0, 'actual_quality_status': None,
        'plan': ref(E + 'plan.json'), 'source_freeze': ref(E + 'source-freeze.json'),
        'audit_protocol': ref(A + 'protocol.json'), 'checked_noncase_references': selected,
        'frozen_source_entry_count': 150, 'frozen_plan_pin_count': 157,
        'all_pin_identity_closure_metadata_consistent': True,
        'all157_payload_files_rehashed_by_this_reviewer': False,
        'actual_case_inputs_or_oracle_payloads_opened': 0,
        'engineering_primary': plan['primary'], 'frozen_gate': plan['engineering_gate'],
        'raw_contexts': plan['raw_context_names'], 'metric_arms': plan['metric_arm_names'],
        'readout_reuse_map': plan['readout_reuse_map'],
        'planned_physical_readouts': 36, 'planned_derived_forecasts': 60,
        'planned_authored_classes': {'Entailment': 4, 'Contradiction': 4, 'NotMentioned': 4},
        'NLL_gate_unclipped_stable_log_softmax': True, 'roundoff_tolerance': 1e-12,
        'raw_label_order': ['Contradiction', 'NotMentioned', 'Entailment'], 'canonical_from_source': [2, 0, 1],
        'probability_policy': plan['probability_policy'], 'limits': contract['limits'],
        'real_asset_guard_receipt_bound_not_reexecuted': plan['real_model_assets_guard_receipt'],
        'E37_preserved': {'results': ref(previous_rel), 'status': previous['status'], 'scientific_integrity': False,
            'captured_corpus_and_model_totals': 'UNKNOWN_FOREVER', 'further_E37_dispatches': 0,
            'historical_corpus_attempt_lower_bound': 33, 'historical_completed_corpus_lower_bound': 31,
            'bounded_outer_attempts_before_E38': 38, 'legacy_dedicated_qualification_attempts': 6},
        'required_actual_acceptance_checks': [
            'Exact published SOURCE/admission, frozen pins and actual dispatch/execution/raw identity must bind; main auditor separately verifies actual Git stage/readback and physical closure.',
            'Read retained raw only after actual physical closure; independently replay36 exact neural logits/T1 distributions and60 same-readout derived decisions without candidate inference or extra labels.',
            'Validate full literal source/query/span/certificate provenance, source-complete typed exact constraints and both feasible true/false worlds for every neutral certificate; unsupported source must abstain.',
            'Verify all60 derived forecasts precede one12-label join, and native child/model/tokenizer/reader disposal precedes labels. Retained joined labels only; no original oracle reread.',
            'Independently recompute all five arms/case-level Brier, stable unclipped NLL, class counts, paired differences, ceiling and every fixed gate; retain losses and all12 cases.',
            'Verify one CPU0,1 worker/600s including init+cleanup, one corpus/12queries/12indexes/one native binary,36forwards,60forecasts, strict no truncation/errors/retries/paid/GPU/train/dev/calibration/CONF.',
            'Assess actual novelty and uncertainty within authored CC0 engineering scope only; potential native/lexical coverage ties do not establish causal ranking gain.',
            'Final publication privacy/history/identity review must preserve E37UNKNOWN, all licensed public metadata, no original/protected benchmark payload exposure and no benchmark or eligibility promotion.'
        ],
        'claim_boundaries': [
            'A gate pass would be authored engineering admission only, never full LegalBench/JevBench/ClaimBench standing, general reasoning strength or official SOTA.',
            'Max-mass transposition proper-score guarantee is conditional on a correct certificate against the SAME raw readout. It is neither calibrated probability evidence nor a cross-context theorem.',
            'Existing submitted native104 remains unchanged. All newly authored public cases become exposed engineering identities;74unused/24protected benchmark identities are unchanged.',
            'Source/plan counters here are prospective expectations, not observations. E37 captured totals cannot be turned into known cumulative totals by an E38 run.',
            'No pure tests duplicated, and no guard/model/tokenizer/native/candidate/case/oracle/scorer/EVALUATE/BIND/host/Git actions were executed by this reviewer.'
        ],
        'reviewer_source': {'path': str(Path(__file__)), 'bytes': Path(__file__).stat().st_size,
            'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    }
    target = OWN / 'SOURCE_ACCEPTANCE_READINESS_v1.json'
    with target.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'path': str(target), 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
