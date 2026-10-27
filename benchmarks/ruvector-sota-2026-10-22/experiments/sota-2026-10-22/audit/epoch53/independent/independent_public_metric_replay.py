"""Audit captured public DEV forecasts and scorer rows; no private payload or inference."""
import hashlib
import json
import math
import os
from pathlib import Path
import random
from collections import Counter

Q = Path('/dev/shm/ruvector-e53-audit')
W = Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34')
R = W / 'project'
P = R / 'experiments/sota-2026-10-22/epoch53'
A = R / 'experiments/sota-2026-10-22/audit/epoch53'
ARMS = ('native', 'lexical', 'source_order', 'whole_source')
CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')


def read(p):
    assert 'private' not in p.parts and 'private-run' not in p.parts
    return json.loads(p.read_bytes())


def ref(p):
    b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def close(a, b):
    assert math.isclose(a, b, rel_tol=2e-12, abs_tol=2e-12), (a, b)


def qtile(v, p):
    v = sorted(v)
    at = (len(v) - 1) * p
    lo, hi = math.floor(at), math.ceil(at)
    return v[lo] + (v[hi] - v[lo]) * (at - lo)


def main():
    rawp = W / 'runs/dev/raw.json'
    resultp = P / 'evaluation/DEV_RESULTS.json'
    raw, result = read(rawp), read(resultp)
    assert ref(rawp)['sha256'] == 'f6eb5f89824aa0baa6ae162f79b01f3fca542ed67797464b8a4bc10f0dd36acf'
    assert ref(resultp)['sha256'] == '4873f60cbe19d3c64ba15a70ee0f935e12268f3c8a30e8cf8c00101c5699dff9'
    plan = read(P / 'plan.json')
    expected = plan['phase_roles']['dev']['case_ids']
    assert len(expected) == 12 and len(set(expected)) == 12
    assert raw['status'] == 'FORECASTS_COMPLETE_NO_GOLD' and not raw['errors']
    assert result['epoch'] == 53 and result['phase'] == 'dev'
    assert result['checks_passed'] is True and result['EVALUATE_calls'] == 1
    assert result['original_vault_reads'] == result['new_model_or_native_calls'] == 0
    assert result['actual_counters'] == raw['counters']
    assert result['actual_runtime_timing'] == raw['timing']
    assert result['actual_runtime_resources'] == raw['resources']
    assert result['raw_ref'] == ref(rawp)
    assert result['used_confirmation_identities'] == []
    gold = {r['case_id']: r['gold'] for r in result['metrics']['native']['rows']}
    assert set(gold) == set(expected) and all(v in CLASSES for v in gold.values())
    rows = {a: {} for a in ARMS}
    for r in raw['rows']:
        a, case = r['arm'], r['case_id']
        assert a in ARMS and case in expected and case not in rows[a]
        logits = r['logits']
        assert len(logits) == 3 and all(math.isfinite(x) for x in logits)
        peak = max(logits)
        shifted = [x - peak for x in logits]
        log_z = math.log(math.fsum(math.exp(x) for x in shifted))
        logs = [x - log_z for x in shifted]
        probabilities = [math.exp(x) for x in logs]
        for x, y in zip(probabilities, r['probabilities']):
            close(x, y)
        for x, y in zip(logs, r['log_probabilities']):
            close(x, y)
        pred = CLASSES[max(range(3), key=lambda i: logits[i])]
        assert pred == r['prediction']
        target = CLASSES.index(gold[case])
        rows[a][case] = dict(case_id=case, document_id=r['document_id'],
            hypothesis_id=r['hypothesis_id'], gold=gold[case], prediction=pred,
            correct=int(pred == gold[case]),
            Brier=math.fsum((p-float(i == target))**2 for i,p in enumerate(probabilities)),
            NLL=-logs[target], probability_of_gold=probabilities[target],
            elapsed_seconds=r['elapsed_seconds'])
    summaries = {}
    for a in ARMS:
        assert set(rows[a]) == set(expected)
        observed = result['metrics'][a]
        assert observed['N'] == 12
        for rr in observed['rows']:
            own = rows[a][rr['case_id']]
            assert set(rr) == set(own)
            for k,v in own.items():
                close(v, rr[k]) if type(v) is float else None
                if type(v) is not float:
                    assert rr[k] == v
        ordered = [rows[a][i] for i in expected]
        correct = sum(r['correct'] for r in ordered)
        assert observed['correct'] == correct
        close(observed['accuracy'], correct / 12)
        for name in ('Brier', 'NLL'):
            close(observed[name], math.fsum(r[name] for r in ordered) / 12)
        for name,p in (('p50', .5), ('p95', .95)):
            close(observed['latency_seconds'][name], qtile([r['elapsed_seconds'] for r in ordered],p))
        classes = {c: dict(support=sum(r['gold'] == c for r in ordered),
                          correct=sum(r['gold'] == c and r['correct'] for r in ordered)) for c in CLASSES}
        assert observed['class_results'] == classes
        summaries[a] = {k:v for k,v in observed.items() if k != 'rows'}
        summaries[a]['prediction_distribution'] = dict(Counter(r['prediction'] for r in ordered))
    gates = dict(all_four_full_N12=True,
                 all_three_gold_classes_represented=all(summaries['native']['class_results'][c]['support'] > 0 for c in CLASSES),
                 native_at_least_one_correct_per_gold_class=all(summaries['native']['class_results'][c]['correct'] > 0 for c in CLASSES))
    for control in ARMS[1:]:
        gates[control+':native_gain_at_least_two_correct'] = summaries['native']['correct'] >= summaries[control]['correct']+2
        for metric in ('Brier','NLL'):
            gates[control+':native_'+metric+'_nonincrease'] = summaries['native'][metric] <= summaries[control][metric]
    assert gates == result['gate_checks']
    assert all(gates.values()) is result['point_gates_passed'] is result['dev_passed'] is False
    docs = sorted({r['document_id'] for r in rows['native'].values()})
    assert len(docs) == 4
    grouped = {d:[i for i in expected if rows['native'][i]['document_id'] == d] for d in docs}
    assert all(len(v) == 3 for v in grouped.values())
    rng = random.Random(48)
    draws = [[rng.choice(docs) for _ in docs] for _ in range(256)]
    for control in ARMS[1:]:
        for metric,field in (('accuracy','correct'),('Brier','Brier'),('NLL','NLL')):
            deltas = []
            for draw in draws:
                selected = [i for d in draw for i in grouped[d]]
                deltas.append(math.fsum(rows['native'][i][field]-rows[control][i][field] for i in selected)/12)
            reported = result['descriptive_uncertainty']['native_minus_control'][control][metric]
            close(reported['p025'], qtile(deltas,.025))
            close(reported['p975'], qtile(deltas,.975))
    g = read(A / 'GOLD_JOIN_REPORT.json')
    ga = read(A / 'ROOT_GOLD_ADMISSION.json')
    assert g['status'] == 'GOLD_JOIN_COMPLETE_AFTER_ALL_PHYSICAL_CLOSURE'
    assert g['semantic_label_decodes'] == g['decode_attempted_tokens'] == 12
    assert g['label_reader_calls'] == g['late_custodian_function_calls'] == 1
    assert g['semantic_decode_count_uncertain'] is False and g['errors'] == []
    assert result['joined_gold_ref'] == g['joined_gold']
    assert ga['qualification_ref'] == result['qualification_ref'] == ref(Q/'DEV_RUNTIME_QUALIFICATION_INDEPENDENT.v1.json')
    assert result['plan_sha256'] == raw['plan_sha256'] == ref(P/'plan.json')['sha256']
    assert result['source_freeze_sha256'] == raw['source_freeze_sha256'] == ref(P/'SOURCE_FREEZE.json')['sha256']
    native_times = [q['elapsed_seconds'] for d in raw['native_result']['documents'] for q in d['queries']]
    assert len(native_times) == 12 and all(math.isfinite(x) and x >= 0 for x in native_times)
    for target in (171887,171888,171895):
        assert not (Path('/proc')/str(target)).exists()
    report = dict(schema_version=1, epoch=53, kind=result['kind'], phase='dev',
        checks_passed=True, runtime_qualified=True, dev_passed=False, accepted=False,
        all_owned_processes_physically_closed=True, all_forecasts_complete_before_gold=True,
        plan_sha256=raw['plan_sha256'], source_freeze_sha256=raw['source_freeze_sha256'],
        raw_sha256=ref(rawp)['sha256'], actual_forecasts=48,
        actual_model_forward_calls=108, actual_native_corpus_batches=1,
        scored_result=ref(resultp), runtime_qualification=ref(Q/'DEV_RUNTIME_QUALIFICATION_INDEPENDENT.v1.json'),
        Gold_report=ref(A/'GOLD_JOIN_REPORT.json'), independent_replay_source=ref(Path(__file__)),
        metrics=summaries, gate_checks=gates,
        failed_frozen_gates=[k for k,v in gates.items() if not v],
        descriptive_uncertainty=result['descriptive_uncertainty'],
        all48_public_scored_rows_raw_logits_predictions_gold_loss_time_independently_recomputed=True,
        all_four_document_cluster_256_seed48_bootstrap_intervals_independently_recomputed=True,
        native_query_component_seconds=dict(N=12,p50=qtile(native_times,.5),p95=qtile(native_times,.95),
            scope='Search await plus all returned-hit validation/result assembly, excludes common stages/cleanup; not pure search or end-to-end/publisher latency.'),
        latency_scope='Per-arm packing/tokenization plus all NLI forwards only; common catalog/BGE/index/reader init and cleanup excluded. Inclusive outer78.33164212299744s remains separate.',
        actual_worker_resources=raw['resources'],
        actual_catalog_scope=dict(original_units=286,final_shared_units=286,overcapacity_groups=0,coalesced_boundaries=0,
            actual_oversized_source_fragmentation_exercised=False,
            scope='Real execution checked all original units against all three claims and kept all units unchanged. Oversized fragmentation/coalescing behavior remains invented-fixture evidence only.'),
        observed_error_direction='Native and lexical each predict Entailment10/Contradiction2/NotMentioned0; whole-source predicts Entailment9/Contradiction3/NotMentioned0. Each misses all7 NotMentioned and1 Contradiction gold cases. Source-order predicts NotMentioned11/Entailment1 and is8of12 correct. Causal mechanism is not established.',
        decision='Reject frozen E53 candidate: native4of12 ties lexical and whole-source, loses to source-order8of12; proper-score and per-class gates fail. Preserve SubmittedNative104; no promotion, confirmation, second batch or publisher submission.',
        evidence_scope='Four public officialDEV documents, project-unused before this epoch but checkpoint-development/model-selection exposed. No fresh benchmark generalization, official score/rank or eligibility claim.',
        current_DEV_whole_groups_all17_hypotheses_and_aliases_forever=[39,205,582,9],
        remaining_project_unused_officialDEV_metadata_group=[17],
        confirmation_lineage_status='UNQUALIFIED_HOLD',used_confirmation_identities=[],
        native104_champion_preserved=True,official_goal_verified=False,
        new_model_native_DATA_Gold_join_EVALUATE_main_calls_by_auditor=0,
        labels_used_for_independent_arithmetic='Only already scored public DEV_RESULTS.rows gold fields after qualified closure; no private features/vault/joined label payload reads.',
        paid_GPU_training_calibration_calls=0,allowed_further_epoch53_attempts=0)
    p = Q / 'DEV_ACCEPTANCE_AND_REJECTION_INDEPENDENT.v1.json'
    b = (json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    fd = os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(b);f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(report=ref(p),decision=report['decision'],failed_gates=len(report['failed_frozen_gates']))))


if __name__ == '__main__':
    main()
