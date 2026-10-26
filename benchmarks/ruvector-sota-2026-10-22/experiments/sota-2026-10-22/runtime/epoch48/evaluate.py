"""Frozen uncalibrated NLI scoring. Reads only the already decoded late Gold join."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

KIND = 'REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT'
LABELS = ['Entailment', 'Contradiction', 'NotMentioned']
ARMS = ['native', 'lexical', 'source_order']


def sha(b):
    return hashlib.sha256(b).hexdigest()


def exact(ref):
    p = Path(ref['path'])
    assert p.is_absolute() and p.is_file() and not p.is_symlink()
    b = p.read_bytes()
    assert len(b) == ref['bytes'] and sha(b) == ref['sha256']
    return b


def put(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    f = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(f, 'wb', closefd=False) as stream:
            stream.write(b)
            stream.flush()
            os.fsync(f)
    finally:
        os.close(f)
    f = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(f)
    os.close(f)
    return {'path': str(p), 'bytes': len(b), 'sha256': sha(b)}


def quantile(values, q):
    values = sorted(values)
    at = (len(values) - 1) * q
    lo, hi = math.floor(at), math.ceil(at)
    return values[lo] + (values[hi] - values[lo]) * (at - lo)


def scores(typed_logits):
    assert len(typed_logits) == 3 and all(type(x) is float and math.isfinite(x) for x in typed_logits)
    maximum = max(typed_logits)
    normalizer = maximum + math.log(math.fsum(math.exp(x - maximum) for x in typed_logits))
    logs = [x - normalizer for x in typed_logits]
    return [math.exp(x) for x in logs], logs


def evaluate_rows(rows, labels, expected_ids):
    assert len(expected_ids) == len(set(expected_ids)) == 12
    assert set(labels) == set(expected_ids) and all(v in LABELS for v in labels.values())
    assert len(rows) == 36
    groups = {arm: {} for arm in ARMS}
    for row in rows:
        arm, case = row['arm'], row['case_id']
        assert arm in ARMS and case in labels and case not in groups[arm]
        probability, logs = scores(row['logits'])
        assert len(row['probabilities']) == len(row['log_probabilities']) == 3
        assert all(math.isclose(x, y, abs_tol=2e-12, rel_tol=2e-12)
                   for x, y in zip(probability, row['probabilities']))
        assert all(math.isclose(x, y, abs_tol=2e-12, rel_tol=2e-12)
                   for x, y in zip(logs, row['log_probabilities']))
        prediction = LABELS[max(range(3), key=lambda i: row['logits'][i])]
        assert prediction == row['prediction']
        elapsed = row['elapsed_seconds']
        assert type(elapsed) is float and math.isfinite(elapsed) and elapsed >= 0
        gold_index = LABELS.index(labels[case])
        brier = math.fsum((p - float(i == gold_index)) ** 2 for i, p in enumerate(probability))
        groups[arm][case] = {'case_id': case, 'document_id': row['document_id'],
                            'hypothesis_id': row['hypothesis_id'], 'gold': labels[case],
                            'prediction': prediction, 'correct': int(prediction == labels[case]),
                            'Brier': brier, 'NLL': -logs[gold_index],
                            'probability_of_gold': probability[gold_index],
                            'elapsed_seconds': elapsed}
    metrics = {}
    for arm in ARMS:
        assert set(groups[arm]) == set(expected_ids)
        ordered = [groups[arm][case] for case in expected_ids]
        metrics[arm] = {'N': 12, 'correct': sum(x['correct'] for x in ordered),
                        'accuracy': sum(x['correct'] for x in ordered) / 12,
                        'Brier': math.fsum(x['Brier'] for x in ordered) / 12,
                        'NLL': math.fsum(x['NLL'] for x in ordered) / 12,
                        'latency_seconds': {'N': 12,
                            'p50': quantile([x['elapsed_seconds'] for x in ordered], .5),
                            'p95': quantile([x['elapsed_seconds'] for x in ordered], .95),
                            'scope': 'Actual perrequest packing/tokenization and model forward; excludes shared BGE/native/index/reader initialization, queue and cleanup. Not publisher latency.'},
                        'class_results': {c: {'support': sum(x['gold'] == c for x in ordered),
                                             'correct': sum(x['gold'] == c and x['correct'] for x in ordered)}
                                          for c in LABELS}, 'rows': ordered}
    for case in expected_ids:
        assert len({groups[arm][case]['document_id'] for arm in ARMS}) == 1
        assert len({groups[arm][case]['hypothesis_id'] for arm in ARMS}) == 1
    gates = {'all_three_full_N12': True,
             'all_three_gold_classes_represented': all(metrics['native']['class_results'][c]['support'] > 0 for c in LABELS),
             'native_at_least_one_correct_per_gold_class': all(metrics['native']['class_results'][c]['correct'] > 0 for c in LABELS)}
    for control in ['lexical', 'source_order']:
        gates[control + ':native_gain_at_least_two_correct'] = metrics['native']['correct'] >= metrics[control]['correct'] + 2
        gates[control + ':native_Brier_nonincrease'] = metrics['native']['Brier'] <= metrics[control]['Brier']
        gates[control + ':native_NLL_nonincrease'] = metrics['native']['NLL'] <= metrics[control]['NLL']
    docs = sorted({x['document_id'] for x in groups['native'].values()})
    assert len(docs) == 4
    by_doc = {d: [case for case in expected_ids if groups['native'][case]['document_id'] == d] for d in docs}
    assert all(len(v) == 3 for v in by_doc.values())
    rng = random.Random(48)
    draws = [[rng.choice(docs) for _ in docs] for _ in range(256)]
    descriptive = {}
    for control in ['lexical', 'source_order']:
        deltas = {'accuracy': [], 'Brier': [], 'NLL': []}
        for draw in draws:
            ids = [case for d in draw for case in by_doc[d]]
            for name, field in [('accuracy', 'correct'), ('Brier', 'Brier'), ('NLL', 'NLL')]:
                deltas[name].append(math.fsum(groups['native'][case][field] - groups[control][case][field]
                                              for case in ids) / len(ids))
        descriptive[control] = {k: {'p025': quantile(v, .025), 'p975': quantile(v, .975)}
                                for k, v in deltas.items()}
    return {'metrics': metrics, 'gate_checks': gates, 'point_gates_passed': all(gates.values()),
            'descriptive_uncertainty': {'document_clusters': 4, 'resamples': 256, 'seed': 48,
                'native_minus_control': descriptive,
                'scope': 'Small public source-group holdout only; descriptive intervals do not establish benchmark generalization or official rank.'}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--admission', type=Path, required=True)
    p.add_argument('--expected-admission-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    ab = a.admission.read_bytes()
    assert sha(ab) == a.expected_admission_sha256
    admission = json.loads(ab)
    assert admission['schema_version'] == 1 and admission['epoch'] == 48 and admission['kind'] == KIND
    assert admission['mode'] == 'EVALUATE' and admission['phase'] in ('dev', 'confirmation')
    plan_raw = exact(admission['plan_ref'])
    plan = json.loads(plan_raw)
    sf_raw = exact(admission['source_freeze_ref'])
    sf = json.loads(sf_raw)
    assert plan['epoch'] == sf['epoch'] == 48 and plan['kind'] == sf['kind'] == KIND
    for row in sf['files']:
        exact({'path': str(Path(plan['project_root']) / row['path']),
               'bytes': row['bytes'], 'sha256': row['sha256']})
    owner = json.loads(exact(admission['owner_ref']))
    assert owner['epoch'] == 48 and owner['generation'] == 13
    assert time.time() < owner['expires_unix'] and not (Path(plan['work_root']) / 'release.request').exists()
    proc = Path('/proc') / str(owner['pid'])
    stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    assert stat[0] not in ('Z', 'X') and int(stat[19]) == owner['startticks']
    st = os.stat(proc / 'fd/3')
    assert (st.st_dev, st.st_ino) == (owner['lock_device'], owner['lock_inode']) == (33, 13626)
    assert 'FLOCK' in (proc / 'fdinfo/3').read_text()
    qualification = json.loads(exact(admission['qualification_ref']))
    assert qualification['epoch'] == 48 and qualification['kind'] == KIND and qualification['phase'] == admission['phase']
    assert qualification['checks_passed'] is True and qualification['all_forecasts_complete_before_gold'] is True
    assert qualification['all_owned_processes_physically_closed'] is True
    assert qualification['plan_sha256'] == sha(plan_raw) and qualification['source_freeze_sha256'] == sha(sf_raw)
    assert qualification['raw_sha256'] == admission['raw_ref']['sha256']
    assert qualification['actual_forecasts'] == 36 and qualification['actual_native_corpus_batches'] == 1
    attempt_path = Path(plan['work_root']) / 'private' / (admission['phase'].upper() + '_EVALUATE_ATTEMPT.json')
    put(attempt_path, {'schema_version': 1, 'epoch': 48, 'kind': KIND, 'phase': admission['phase'],
                      'EVALUATE_calls': 1, 'original_vault_reads': 0,
                      'admission_sha256': sha(ab), 'automatic_retry': False})
    raw = json.loads(exact(admission['raw_ref']))
    gold = json.loads(exact(admission['joined_gold_ref']))
    assert raw['status'] == 'FORECASTS_COMPLETE_NO_GOLD' and raw['errors'] == []
    assert raw['phase'] == gold['phase'] == admission['phase']
    assert raw['plan_sha256'] == sha(plan_raw) and raw['source_freeze_sha256'] == sha(sf_raw)
    assert raw['epoch'] == gold['epoch'] == 48 and raw['kind'] == gold['kind'] == KIND
    assert gold['plan_sha256'] == sha(plan_raw) and gold['source_freeze_sha256'] == sha(sf_raw)
    assert gold['semantic_label_decodes'] == 12 and gold['label_reader_calls'] == 1
    assert gold['all_labels_decoded_after_forecasts_and_ALL_physical_closure'] is True
    ids = plan['phase_roles'][admission['phase']]['case_ids']
    assert gold['selected_ids'] == ids
    result = evaluate_rows(raw['rows'], gold['labels'], ids)
    passed = result['point_gates_passed']
    result.update({'schema_version': 1, 'epoch': 48, 'kind': KIND, 'phase': admission['phase'],
                   'status': ('PASSED_DEV_AWAITING_UNUSED_CONFIRMATION' if passed else 'REJECTED_DEV')
                             if admission['phase'] == 'dev' else
                             ('PASSED_PUBLIC_CONFIRMATION_PUBLISHER_PROTOCOL_HOLD' if passed else 'REJECTED_CONFIRMATION'),
                   'checks_passed': True, 'dev_passed': passed if admission['phase'] == 'dev' else None,
                   'confirmation_passed': passed if admission['phase'] == 'confirmation' else None,
                   'plan_sha256': sha(plan_raw), 'source_freeze_sha256': sha(sf_raw),
                   'raw_ref': admission['raw_ref'], 'joined_gold_ref': admission['joined_gold_ref'],
                   'qualification_ref': admission['qualification_ref'], 'EVALUATE_calls': 1,
                   'original_vault_reads': 0, 'new_model_or_native_calls': 0,
                   'used_confirmation_identities': ids if admission['phase'] == 'confirmation' else [],
                   'native104_champion_preserved': True, 'official_goal_verified': False,
                   'proper_score_scope': 'Uncalibrated stable FP64 log-softmax of captured FP32 typed head logits; no clipping or fitted calibration.',
                   'scientific_scope': 'Project-unused public ContractNLI officialDEV source-group pilot. No fullbenchmark/publisher score, rank or eligibility claim.',
                   'numerical_check_scope': 'Exact selected-source substring, numeric/date/currency and negation preservation only; no claim of semantic numeric proof. Retrieval miss never proves insufficient evidence.',
                   'actual_runtime_timing': raw['timing'], 'actual_runtime_resources': raw['resources'],
                   'actual_counters': raw['counters'], 'loading_audit': raw['loading_audit']})
    ref = put(a.output, result)
    print(json.dumps({'result': ref, 'status': result['status'], 'point_gates_passed': passed,
                      'correct': {k: v['correct'] for k, v in result['metrics'].items()},
                      'original_vault_reads': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
