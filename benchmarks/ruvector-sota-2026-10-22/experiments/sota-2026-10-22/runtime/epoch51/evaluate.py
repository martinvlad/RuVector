"""Frozen uncalibrated NLI scoring. Reads only the already decoded late Gold join."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

KIND = 'REAL_CONTRACTNLI_CONTRACT_BERT_WHOLE_SOURCE_PILOT'
LABELS = ['Entailment', 'Contradiction', 'NotMentioned']
ARMS = ['native', 'lexical', 'source_order', 'whole_source']


def canonical_relative(value):
    assert type(value) is str and value and not value.startswith('/') and '\\' not in value
    parts = value.split('/')
    assert all(part not in ('', '.', '..') for part in parts)
    assert str(Path(value)) == value
    return Path(value)


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
    assert len(rows) == 48
    groups = {arm: {} for arm in ARMS}
    for row in rows:
        arm, case = row['arm'], row['case_id']
        assert arm in ARMS and case in labels and case not in groups[arm]
        expected_windows = len(row['window_forecasts']) if arm == 'whole_source' else 1
        assert row['model_forward_calls'] == row['window_count'] == expected_windows
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
    gates = {'all_four_full_N12': True,
             'all_three_gold_classes_represented': all(metrics['native']['class_results'][c]['support'] > 0 for c in LABELS),
             'native_at_least_one_correct_per_gold_class': all(metrics['native']['class_results'][c]['correct'] > 0 for c in LABELS)}
    for control in ['lexical', 'source_order', 'whole_source']:
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
    for control in ['lexical', 'source_order', 'whole_source']:
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
                'scope': 'Four public diagnostic development source groups, checkpoint-development/model-selection exposed; descriptive intervals do not establish fresh model holdout generalization, benchmark generalization or official rank.'}}


def validate_whole_source_aggregation(rows):
    """Replay every captured window forecast and exact frozen pooling, without models."""
    assert len(rows) == 48
    whole = [r for r in rows if r['arm'] == 'whole_source']
    assert len(whole) == 12
    physical = 36
    for row in whole:
        windows = row['window_forecasts']
        assert 1 <= len(windows) <= 16
        physical += len(windows)
        captured_ids = []; covered_characters = 0; previous_end = 0
        for index, window in enumerate(windows):
            assert len(window['probabilities']) == len(window['log_probabilities']) == 3
            assert type(window['forward_seconds']) is float and math.isfinite(window['forward_seconds']) and window['forward_seconds'] >= 0
            probs, logs = scores(window['logits'])
            assert all(math.isclose(a, b, abs_tol=2e-12, rel_tol=2e-12)
                       for a, b in zip(probs, window['probabilities']))
            assert all(math.isclose(a, b, abs_tol=2e-12, rel_tol=2e-12)
                       for a, b in zip(logs, window['log_probabilities']))
            assert window['prediction'] == LABELS[max(range(3), key=lambda i: window['logits'][i])]
            e = window['evidence']
            assert e['window_index'] == index and e['window_count'] == len(windows)
            assert e['complete_source_coverage'] is True and e['all_source_units_once'] is True
            assert e['source_order_contiguous_window'] is True and e['inserted_separator'] == ''
            assert e['whole_units_unchanged'] is True and e['claim_unchanged'] is True
            assert e['numeric_date_currency_negation_audit']['source_and_premise_occurrence_counts_match'] is True
            assert e['full_source_numeric_partition_audit']['source_and_premise_occurrence_counts_match'] is True
            assert 0 < e['pair_token_count'] <= 512
            assert e['source_start'] == previous_end and e['source_end'] > previous_end
            assert e['units'] and [u['unit_id'] for u in e['units']] == e['selected_unit_ids']
            local_end = e['source_start']
            for unit in e['units']:
                assert unit['start'] == local_end and unit['end'] > local_end
                local_end = unit['end']
            assert local_end == e['source_end']
            previous_end = e['source_end']; covered_characters += e['selected_source_characters']
            assert e['selected_source_characters'] == e['source_end'] - e['source_start']
            captured_ids.extend(e['selected_unit_ids'])
        assert captured_ids == list(range(windows[0]['evidence']['source_units_total']))
        assert covered_characters == previous_end == windows[0]['evidence']['source_characters_total']
        assert len({w['evidence']['full_source_sha256'] for w in windows}) == 1
        assert len({w['evidence']['claim_sha256'] for w in windows}) == 1
        winner = max(range(len(windows)), key=lambda i: 1.0 - windows[i]['probabilities'][2])
        selected = windows[winner]
        for name in ['probabilities', 'log_probabilities', 'logits', 'prediction']:
            assert row[name] == selected[name]
        aggregate = row['evidence']['aggregation']
        assert aggregate['selected_window_index'] == winner and aggregate['all_window_count'] == len(windows)
        assert aggregate['selected_three_way_forecast_unchanged'] is True
        assert aggregate['all_source_units_once'] is True and aggregate['all_source_characters_once'] is True
        assert aggregate['no_probability_clipping_or_calibration'] is True
        assert aggregate['author_documented_aggregation'] is False
        assert math.isclose(row['forward_seconds'], math.fsum(w['forward_seconds'] for w in windows),
                            rel_tol=1e-12, abs_tol=1e-12)
    assert 48 <= physical <= 228
    return physical


def validate_runtime_receipt(raw):
    audit = raw['loading_audit']; counters = raw['counters']; net = raw['network_audit']
    assert audit['model_id'] == 'Agreemind/contractnli-bert-nda-standard'
    assert audit['model_revision'] == audit['source_revision'] == 'ac92b6b512d7a4bad7abe356750c3b916fe18649'
    assert audit['model_weight_sha256'] == 'cd4f4391ab75c22e986ecea64831af47f6008a37ddce6a56a4cb5496e41ead07'
    assert audit['learned_state_tensor_count'] == 201 and audit['source_tensor_elements'] == 109484547
    for key in ['learned_state_keys_exact', 'weights_only', 'mmap', 'assign', 'meta_constructor',
                'all_201_state_tensor_data_pointers_match_mmap_source',
                'all_original_learned_pooler_and_classifier_tensors_retained', 'FP32_CPU_eval']:
        assert audit[key] is True
    assert audit['weights_format'] == 'safetensors' and audit['safetensors_cpu_mapped'] is True
    assert audit['pair_order'] == 'hypothesis_then_premise' and audit['bert_token_type_ids_retained'] is True
    assert audit['raw_head_order'] == LABELS and audit['raw_to_typed_indices'] == [0, 1, 2]
    assert audit['unsafe_load_fallback'] is False and audit['custom_remote_code'] is False
    assert audit['removed_learned_or_nonlearned_state_keys'] == []
    assert audit['missing_keys'] == audit['unexpected_keys'] == audit['mismatched_keys'] == []
    assert audit['torch_threads'] == 2 and audit['torch_interop_threads'] == 1
    assert set(audit['nonpersistent_buffers']) == {'position_ids', 'token_type_ids'}
    for value in audit['nonpersistent_buffers'].values():
        assert value['shape'] == [1, 512] and value['dtype'] == 'int64' and value['device'] == 'cpu'
        assert value['persistent'] is False
    physical = validate_whole_source_aggregation(raw['rows'])
    assert raw['expected_physical_forwards'] == physical
    assert counters['NLI_forwards_attempted'] == counters['NLI_forwards_completed'] == physical
    assert counters['forecasts_completed'] == 48
    assert counters['native_corpus_batches_attempted'] == counters['native_corpus_batches_completed'] == counters['native_corpus_batches'] == 1
    assert counters['reader_initializations_attempted'] == counters['reader_initializations_completed'] == 1
    assert all(counters[key] == 0 for key in ['training_calls', 'calibration_calls', 'paid_API_calls', 'GPU_calls', 'semantic_gold_decodes'])
    assert counters['Node_network_operations_attempted'] == 0
    assert counters['Python_network_operations_attempted'] == counters['Python_network_operations_blocked']
    assert counters['Python_network_operations_attempted'] in (0, 1)
    assert net['all_audited_operations_denied_before_IO'] is True and net['audited_successful_network_operations'] == 0
    assert net['admissible'] is True and net['unexpected_blocked_attempts'] == 0
    assert net['blocked_optional_import_bind_probes'] == counters['Python_network_operations_attempted']
    assert net['event_counts'] == ({'socket.bind': 1} if counters['Python_network_operations_attempted'] else {})
    assert all(stage in ['reader_torch_import', 'reader_transformers_import']
               and group == {'socket.bind': 1} for stage, group in net['stage_event_counts'].items())
    assert sum(sum(group.values()) for group in net['stage_event_counts'].values()) == counters['Python_network_operations_attempted']
    assert {'socket.bind', 'socket.connect', 'socket.sendall', 'socket.recv', 'socket.accept', 'socket.getaddrinfo'} <= set(net['public_socket_wrappers_installed'])
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--admission', type=Path, required=True)
    p.add_argument('--expected-admission-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    ab = a.admission.read_bytes()
    assert sha(ab) == a.expected_admission_sha256
    admission = json.loads(ab)
    assert admission['schema_version'] == 1 and admission['epoch'] == 51 and admission['kind'] == KIND
    assert admission['mode'] == 'EVALUATE' and admission['phase'] in ('dev', 'confirmation')
    plan_raw = exact(admission['plan_ref'])
    plan = json.loads(plan_raw)
    sf_raw = exact(admission['source_freeze_ref'])
    sf = json.loads(sf_raw)
    assert plan['epoch'] == sf['epoch'] == 51 and plan['kind'] == sf['kind'] == KIND
    assert plan['phase_limits']['actual_model_forwards_maximum_per_phase'] == 228
    if admission['phase'] == 'confirmation':
        assert plan['confirmation_lineage_status'] == 'INDEPENDENTLY_QUALIFIED_HELDOUT', 'CONFIRMATION_LINEAGE_UNQUALIFIED_HOLD'
    for row in sf['files']:
        exact({'path': str(Path(plan['project_root']) / canonical_relative(row['path'])),
               'bytes': row['bytes'], 'sha256': row['sha256']})
    owner = json.loads(exact(admission['owner_ref']))
    assert owner['epoch'] == 51 and owner['generation'] == 16
    assert owner['pid'] == 162664 and owner['startticks'] == 39101510
    assert Path(plan['work_root']) == Path('/dev/shm/ruvector-sota-2026-10-22/epoch51-0e1f4181df1f')
    assert time.time() < owner['expires_unix'] and not (Path(plan['work_root']) / 'release.request').exists()
    proc = Path('/proc') / str(owner['pid'])
    stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    assert stat[0] not in ('Z', 'X') and int(stat[19]) == owner['startticks']
    st = os.stat(proc / 'fd/3')
    assert (st.st_dev, st.st_ino) == (owner['lock_device'], owner['lock_inode']) == (33, 13626)
    assert 'FLOCK' in (proc / 'fdinfo/3').read_text()
    qualification = json.loads(exact(admission['qualification_ref']))
    assert qualification['epoch'] == 51 and qualification['kind'] == KIND and qualification['phase'] == admission['phase']
    assert qualification['checks_passed'] is True and qualification['all_forecasts_complete_before_gold'] is True
    assert qualification['all_owned_processes_physically_closed'] is True
    assert qualification['plan_sha256'] == sha(plan_raw) and qualification['source_freeze_sha256'] == sha(sf_raw)
    assert qualification['raw_sha256'] == admission['raw_ref']['sha256']
    assert qualification['actual_forecasts'] == 48 and qualification['actual_native_corpus_batches'] == 1
    attempt_path = Path(plan['work_root']) / 'private' / (admission['phase'].upper() + '_EVALUATE_ATTEMPT.json')
    put(attempt_path, {'schema_version': 1, 'epoch': 51, 'kind': KIND, 'phase': admission['phase'],
                      'EVALUATE_calls': 1, 'original_vault_reads': 0,
                      'admission_sha256': sha(ab), 'automatic_retry': False})
    raw = json.loads(exact(admission['raw_ref']))
    validate_runtime_receipt(raw)  # Mandatory source/runtime/network checks before decoded Gold.
    gold = json.loads(exact(admission['joined_gold_ref']))
    assert raw['status'] == 'FORECASTS_COMPLETE_NO_GOLD' and raw['errors'] == []
    assert raw['phase'] == gold['phase'] == admission['phase']
    assert raw['plan_sha256'] == sha(plan_raw) and raw['source_freeze_sha256'] == sha(sf_raw)
    assert raw['epoch'] == gold['epoch'] == 51 and raw['kind'] == gold['kind'] == KIND
    assert gold['plan_sha256'] == sha(plan_raw) and gold['source_freeze_sha256'] == sha(sf_raw)
    assert gold['semantic_label_decodes'] == 12 and gold['label_reader_calls'] == 1
    assert gold['all_labels_decoded_after_forecasts_and_ALL_physical_closure'] is True
    ids = plan['phase_roles'][admission['phase']]['case_ids']
    assert gold['selected_ids'] == ids
    result = evaluate_rows(raw['rows'], gold['labels'], ids)
    passed = result['point_gates_passed']
    result.update({'schema_version': 1, 'epoch': 51, 'kind': KIND, 'phase': admission['phase'],
                   'status': ('PASSED_DEV_CONFIRMATION_LINEAGE_HOLD' if passed else 'REJECTED_DEV')
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
                   'scientific_scope': 'Project-unused public ContractNLI officialDEV diagnostic; checkpoint development/model-selection exposed. CF officialTEST publisher split terminology remains lineage-unqualified until independent proof. No fresh generalization/fullbenchmark/publisher score, rank or eligibility claim.',
                   'numerical_check_scope': 'Exact selected-source substring, numeric/date/currency and negation preservation only; no claim of semantic numeric proof. Retrieval miss never proves insufficient evidence.',
                   'actual_runtime_timing': raw['timing'], 'actual_runtime_resources': raw['resources'],
                   'actual_counters': raw['counters'], 'loading_audit': raw['loading_audit'],
                   'network_audit': raw['network_audit'], 'memory_snapshots': raw['memory_snapshots']})
    ref = put(a.output, result)
    print(json.dumps({'result': ref, 'status': result['status'], 'point_gates_passed': passed,
                      'correct': {k: v['correct'] for k, v in result['metrics'].items()},
                      'original_vault_reads': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
