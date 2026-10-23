"""Independent saved-output numerical, wire, data, gate and resource replay.

Prepared before epoch16 gold. No model/native sessions, inference, network or fit.
Complete and partial failed phases have separate, explicit acceptance behavior.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import hashlib
import json
import math
import statistics
import math_v1 as M

PREFIX = 'It is not the case that '
ARM_KEYS = {'ruvector_top2': 'ruvector_top2', 'same_nli_lexical_top2': 'lexical_top2',
            'same_nli_positional_first2': 'positional_first2'}
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
MODEL_SHA = '821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
MODEL_REV = 'bab4bc7178836f731dcfd18c06ca9def0a137712'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def obj(path): return json.loads(Path(path).read_text())
def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
def optional_obj(path): return obj(path) if Path(path).exists() else None
def optional_rows(path): return rows(path) if Path(path).exists() else []
def text_hash(text): return hashlib.sha256(text.encode()).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def live(pid):
    path = Path('/proc', str(pid), 'stat')
    return path.exists() and path.read_text().rsplit(')', 1)[1].split()[0] not in ('Z', 'X')


def selected_response(response, arm):
    if arm == 'native104_on_ruvector_evidence': return response['baseline104_response']
    if arm == 'ruvector_top2': return response
    return response['ablation_responses'][arm]


def raw_distribution(decoding, premise, hypothesis, expected_revision, expected_model):
    assert decoding['raw_label_indices'] == {'contradiction': 0, 'entailment': 1, 'neutral': 2}
    p = M.softmax(decoding['logits'], decoding['raw_label_indices'])
    for label in M.LABELS: M.close(p[label], decoding['raw_threeway_probabilities'][label])
    assert decoding['model_revision'] == expected_revision == MODEL_REV
    assert decoding['onnx_sha256'] == expected_model == MODEL_SHA
    assert decoding['temperature'] == 1 and decoding['batch_size'] == 1
    assert not decoding['truncated'] and decoding['padding_tokens'] == 0
    n = decoding['input_tokens']
    assert decoding['raw_tokens'] == decoding['used_tokens'] == decoding['actual_model_pair_tokens'] == n <= 512
    assert len(decoding['input_ids']) == len(decoding['attention_mask']) == len(decoding['token_type_ids']) == n
    assert all(v == 1 for v in decoding['attention_mask'])
    raw = json.dumps({'premise': premise, 'hypothesis': hypothesis}, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False)
    assert text_hash(raw) == decoding['input_text_sha256']
    return p


def verify_recipe(plan, root, phase, expected, attempted):
    recipe = plan['lazy_confirmation']
    assert sha(root/recipe['source_path']) == recipe['source_sha256'] == SOURCE_SHA
    assert sha(root/recipe['builder_path']) == recipe['builder_sha256']
    assert sha(root/recipe['source_freeze_path']) == recipe['source_freeze_sha256']
    data = root/'experiments/sota-2026-10-22/legal-transfer/epoch16'
    role = 'dev' if phase == 'development' else 'confirmation'
    allow = obj(data/(role+'-input-allowlist.json'))
    identities = allow['records']
    assert len(identities) == 24 and allow['document_groups'] == 8
    assert allow['annotation_choices_accessed'] == 0 and not allow['contains_labels_or_inputs']
    assert [r['id'] for r in expected] == [r['id'] for r in identities]
    if phase == 'confirmation':
        assert attempted, 'Never inspect CONF gold without actual phase reservation'
        material = obj(data/'confirmation-materialization.json')
        assert material['annotation_choices_projected'] == 24
        assert material['other_role_annotation_choices_accessed'] == material['old_reserved_CONF48_choices_accessed'] == 0
        assert material['data_sha256'] == sha(root/plan['datasets']['confirmation'])
        assert material['builder_sha256'] == recipe['builder_sha256']
        assert material['source_sha256'] == SOURCE_SHA
        assert material['root_source_freeze_sha256'] == recipe['source_freeze_sha256']
    # The source is parsed only after an actual phase attempt. Choices below
    # are read for that role alone; oldCONF48 is never parsed.
    source = obj(root/recipe['source_path'])
    documents = {d['id']: d for d in source['documents']}
    for row, identity in zip(expected, identities):
        assert row['id'] == identity['id'] and row['source_group'] == identity['source_group']
        assert row['provenance']['hypothesis_id'] == identity['hypothesis_id']
        doc = documents[row['provenance']['document_id']]
        h = identity['hypothesis_id']
        assert row['input']['state'] == doc['text']
        assert row['input']['questions']['decision']['criteria']['Yes'] == source['labels'][h]['hypothesis']
        digest = text_hash(canonical(row['input']))
        assert digest == row['input_sha256'] == identity['input_sha256']
        assert len(doc['annotation_sets']) == 1
        gold = doc['annotation_sets'][0]['annotations'][h]['choice']
        assert row['evaluation']['original_threeway_label'] == gold
        assert row['evaluation']['gold'] == ('Yes' if gold == 'Entailment' else 'No')
    return {'role': role, 'source_gold_choices_independently_verified': 24,
            'data_SHA256': sha(root/plan['datasets'][phase]),
            'identity_allowlist_SHA256': sha(data/(role+'-input-allowlist.json')),
            'old_confirmation48_annotation_choices_read': 0}


def audit(root, plan_path, expected_plan_sha):
    s = root/'experiments/sota-2026-10-22'; study = s/'epoch16'
    assert sha(plan_path) == expected_plan_sha
    plan = obj(plan_path)
    assert plan['prior_closed_study_native_attempts'] == 17
    assert plan['limits']['threads'] == 2 and plan['limits']['seconds_per_batch'] == 600
    assert plan['limits']['paid_calls'] == plan['limits']['GPU_calls'] == 0
    for pin in plan['pins']:
        path = root/pin['path']
        assert path.is_file() and not any(p.is_symlink() for p in [path, *path.parents])
        assert sha(path) == pin['sha256'], pin['path']
    terminal = obj(study/'study-completion.json')
    attempted = [phase for phase in ('development', 'confirmation')
                 if (study/'runs'/phase/'popen-attempt.json').exists()]
    assert terminal['actual_native_attempts'] == len(attempted) <= 2
    assert terminal['lifetime_native_attempts'] == 17+len(attempted)
    assert terminal['allowed_further_attempts_in_closed_study'] == 0
    assert attempted in (['development'], ['development', 'confirmation'])
    all_binary, all_typed, all_confusions, all_classes, phases = {}, {}, {}, {}, {}
    all_intervals, all_typed_intervals, details, inputs_seen = {}, {}, [], {}
    maximum_drift = 0.; observed_counts = Counter()
    for phase in attempted:
        run = study/'runs'/phase
        invocation = obj(run/'popen-attempt.json')
        ev = {name: optional_obj(run/(name+'.json')) for name in
              ('attempt','completion','runtime','resources','cleanup','report','final-engine')}
        attempt, completion, runtime = ev['attempt'], ev['completion'], ev['runtime']
        assert invocation['source_plan_sha256'] == expected_plan_sha
        assert invocation['new_study_native_attempt'] == (1 if phase == 'development' else 2)
        if attempt:
            assert attempt['lifetime_native_attempt'] == (18 if phase == 'development' else 19)
            assert not live(attempt['pid'])
        if completion:
            assert completion['prior_closed_attempts'] == 17 and completion['source_plan_unchanged']
            assert completion['wall_seconds_including_model_load'] <= 600
            assert not completion['owned_group_cleanup']['live_members_after']
            assert completion['owned_group_cleanup']['finished_within_deadline']
        if runtime:
            assert all(not live(pid) for pid in runtime['native_child_pids'])
            assert runtime['receipt']['nli']['revision'] == MODEL_REV
            assert runtime['receipt']['nli']['model_sha256'] == MODEL_SHA
            assert runtime['phase_initialization_seconds'] > 0
            assert runtime['phase_initialization_seconds'] >= runtime['receipt']['initialization_wall_seconds']
            observed_init = datetime.fromisoformat(runtime['at']).timestamp()-attempt['invocation_started_unix']
            M.close(runtime['phase_initialization_seconds'], observed_init, tolerance=.1)
            for key, value in plan['expected_native_receipt'].items(): assert runtime['receipt'][key] == value
        if ev['resources']:
            assert len(ev['resources']['allowed_CPU_ids']) <= 2
            assert ev['resources']['configured_ORT_threads'] == 2
        complete = bool(completion and completion['exit_code'] == 0 and completion['error'] is None)
        actual, wire = optional_rows(run/'records.jsonl'), optional_rows(run/'wire.jsonl')
        events, starts = optional_rows(run/'server-audit.jsonl'), optional_rows(run/'started-requests.jsonl')
        expected_path = root/plan['datasets'][phase]
        expected = rows(expected_path) if expected_path.exists() else []
        if expected:
            recipe = verify_recipe(plan, root, phase, expected, True)
        else:
            assert phase == 'confirmation' and not complete and not actual
            recipe = {'role': 'confirmation', 'source_gold_choices_independently_verified': 0,
                      'projection_failed_before_dataset_receipt': True}
        if complete:
            assert len(actual) == len(expected) == len(wire) == len(events) == len(starts) == 24
            assert sum(r['elapsed_s'] for r in actual)+runtime['phase_initialization_seconds'] <= completion['wall_seconds_including_model_load']+.1
            assert ev['cleanup']['engine_close_called'] and ev['cleanup']['native_child_pids_absent']
            assert not ev['cleanup']['cleanup_errors']
            assert sha(run/'records.jsonl') == ev['report']['records_sha256']
            assert sha(run/'wire.jsonl') == ev['report']['wire_sha256']
        assert len(actual) <= len(wire) <= len(starts) <= 24
        assert [r['id'] for r in starts] == [r['id'] for r in expected[:len(starts)]]
        assert [r['id'] for r in actual] == [r['id'] for r in expected[:len(actual)]]
        wire_map = {r['id']: r for r in wire}; assert len(wire_map) == len(wire)
        start_map = {r['id']: r for r in starts}; assert len(start_map) == len(starts)
        for event, w in zip(events, wire):
            assert event['status'] == w['status']
            for side in ('request','response'):
                assert text_hash(w[side]) == w[side+'_sha256'] == event[side+'_sha256']
        if complete: assert all(w['status'] == 200 for w in wire) and all(e['ok'] for e in events)
        binary_rows = {arm: [] for arm in M.BINARY_ARMS}
        typed_rows = {arm: [] for arm in M.TYPED_ARMS}
        confusion = {arm: Counter() for arm in M.TYPED_ARMS}
        class_counts = Counter({label: 0 for label in M.LABELS}); groups = []
        for e, row in zip(expected, actual):
            assert e['id'] == row['id'] and e['input'] == row['input'] and e['evaluation'] == row['evaluation']
            w = wire_map[row['id']]; st = start_map[row['id']]
            assert w['status'] == 200 and json.loads(w['request']) == row['input']
            assert json.loads(w['response']) == row['response'] and st['request'] == w['request']
            assert st['request_sha256'] == w['request_sha256']
            M.close(row['elapsed_s'], w['elapsed_s'])
            response = row['response']; d = response['diagnostics']['decision']
            h = row['input']['questions']['decision']['criteria']['Yes']; q = PREFIX+h
            usage = response['usage']
            assert usage['paid_calls'] == 0 and usage['nli_singleton_pairs'] == 6
            assert usage['native_requests'] == usage['native_core_searches'] == 1
            assert usage['semantic_control_extra_forwards'] == 0
            raw_positive, pooled = {}, {}
            for name, key in ARM_KEYS.items():
                arm = d['arms'][key]
                assert 'decoding' not in arm and arm['hypothesis'] == h and arm['counterclaim'] == q
                p = raw_distribution(arm['positive_decoding'], arm['premise'], h, plan['expected_nli_revision'], plan['expected_nli_sha256'])
                negative = raw_distribution(arm['counterclaim_decoding'], arm['premise'], q, plan['expected_nli_revision'], plan['expected_nli_sha256'])
                raw_positive[name] = p; pooled[name] = M.mirrored_pool(p, negative)
                assert arm['pooling']['counterclaim_prefix'] == PREFIX
                for label in M.LABELS: M.close(arm['pooled_threeway_probabilities'][label], pooled[name][label])
                for label, value in M.binary(pooled[name]).items(): M.close(arm['pooled_binary_probabilities'][label], value)
                for decoding in (arm['positive_decoding'], arm['counterclaim_decoding']):
                    fingerprint = decoding['input_text_sha256']
                    z = decoding['logits']
                    if fingerprint in inputs_seen:
                        maximum_drift = max(maximum_drift, max(abs(a-b) for a,b in zip(z, inputs_seen[fingerprint])))
                    else: inputs_seen[fingerprint] = z
                    observed_counts['NLI_pairs_in_scored_requests'] += 1
                    observed_counts['NLI_tokens_in_scored_requests'] += decoding['input_tokens']
            typed_probabilities = dict(pooled)
            typed_probabilities['same_nli_native_raw_h'] = raw_positive['ruvector_top2']
            gold = row['evaluation']['gold']; gold_typed = row['evaluation']['original_threeway_label']
            assert gold == ('Yes' if gold_typed == 'Entailment' else 'No')
            class_counts[gold_typed] += 1; groups.append(row['source_group'])
            proof = {'id': row['id'], 'phase': phase, 'source_group': row['source_group'],
                     'gold_binary': gold, 'gold_typed': gold_typed, 'arms': {}}
            for arm in M.BINARY_ARMS:
                answer = selected_response(response, arm)['answers']['decision']
                probability = M.distribution(answer['probabilities'], ['Yes','No'])
                assert answer['choice'] == M.prediction(probability)
                scored = M.row_score(probability, gold, ['Yes','No'])
                binary_rows[arm].append(scored)
                proof['arms'][arm] = {'binary_probabilities': probability, **scored}
                if arm in M.TYPED_ARMS:
                    typed = typed_probabilities[arm]
                    for label in M.LABELS: M.close(answer['typed_probabilities'][label], typed[label])
                    assert answer['typed_prediction'] == M.prediction(typed)
                    for label, value in M.binary(typed).items(): M.close(probability[label], value)
                    score = M.row_score(typed, gold_typed, M.LABELS)
                    typed_rows[arm].append(score)
                    confusion[arm][gold_typed+'->'+M.prediction(typed)] += 1
                    proof['arms'][arm].update(typed_probabilities=typed, typed_correct=score['correct'],
                                              typed_prediction=M.prediction(typed))
            for key, candidate_key in [('same_nli_native_raw_h','ruvector_top2'),
                                       ('same_nli_lexical_raw_h','same_nli_lexical_top2'),
                                       ('same_nli_positional_raw_h','same_nli_positional_first2')]:
                answer = response['semantic_ablation_responses'][key]['answers']['decision']
                for label in M.LABELS: M.close(answer['typed_probabilities'][label], raw_positive[candidate_key][label])
            embedding = d['retrieval']['embedding']
            observed_counts['BGE_texts_in_scored_requests'] += embedding['actual_embedded_texts']
            observed_counts['BGE_batches_in_scored_requests'] += embedding['chunks']['model_batches']+embedding['query']['model_batches']
            observed_counts['native_searches_in_scored_requests'] += 1
            details.append(proof)
        metrics = {arm: M.summary(values) for arm, values in binary_rows.items()}
        typed_metrics = {arm: M.summary(values) for arm, values in typed_rows.items()}
        for arm, values in typed_metrics.items():
            values['by_class'] = {label: {'n': class_counts[label],
                'correct': confusion[arm].get(label+'->'+label, 0)} for label in M.LABELS}
        all_binary[phase], all_typed[phase] = metrics, typed_metrics
        all_classes[phase], all_confusions[phase] = dict(class_counts), {k: dict(v) for k,v in confusion.items()}
        if complete:
            assert len(set(groups)) == 8 and all(groups.count(g) == 3 for g in set(groups))
            published = obj(run/(phase+'-comparison.json'))
            for kind, values in [('metrics',metrics),('typed_metrics',typed_metrics)]:
                assert set(published[kind]) == set(values)
                for arm, v in values.items():
                    for key in ('n','correct','brier','nll','strict_valid','errors'): M.close(v[key],published[kind][arm][key])
                    if kind == 'typed_metrics': assert v['by_class'] == published[kind][arm]['by_class']
            assert published['typed_confusions'] == all_confusions[phase]
            all_intervals[phase] = M.paired_intervals(binary_rows, groups)
            all_typed_intervals[phase] = M.paired_intervals(typed_rows, groups)
        phases[phase] = {'complete': complete, 'actual_scored_records': len(actual),
            'wire_requests': len(wire), 'started_requests': len(starts),
            'wire_HTTP_errors': sum(w['status'] != 200 for w in wire), 'recipe': recipe,
            'resources': ev['resources'], 'completion': completion, 'runtime': runtime,
            'terminal_engine': ev['final-engine'], 'latency': None if not actual else {
                'p50': statistics.median(r['elapsed_s'] for r in actual),
                'p95': M.latency_percentile([r['elapsed_s'] for r in actual], .95),
                'max': max(r['elapsed_s'] for r in actual), 'scope':'Whole all-arm HTTP; not primary-only deployment'}}
    dev, checks = M.point_gate(all_binary['development'], all_typed['development'],
        all_classes['development'], all_confusions['development']['ruvector_top2'], True)
    dev = bool(dev and phases['development']['complete'])
    if phases['development']['complete']:
        assert dev == terminal['development_gate_passed']
        assert dev == obj(study/'runs/development/development-comparison.json')['frozen_development_gate_passed']
    admission = optional_obj(study/'runtime-admission.json')
    if admission:
        frozen = plan['runtime_admission']; phase = phases['development']
        assert frozen['formula_id'] == admission['formula_id'] == '24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1'
        initialization = phase['runtime']['phase_initialization_seconds']
        forecast = 24*phase['latency']['max']*max(1,frozen['max_confirmation_units']/frozen['max_DEV_units'])+2*initialization+60
        M.close(forecast, admission['projected_confirmation_seconds'])
        M.close(initialization, admission['DEV_initialization_seconds'])
        M.close(phase['latency']['max'], admission['max_DEV_HTTP_seconds'])
        remaining = plan['lease_expires_unix']-datetime.fromisoformat(admission['at']).timestamp()
        assert admission['allowed'] == (forecast <= 600 and remaining >= forecast+30)
    confirmation, confirmation_checks = False, None
    if 'confirmation' in attempted:
        assert dev and admission and admission['allowed']
        lock = obj(study/'confirmation-selection-lock.json')
        assert lock['plan_sha256'] == expected_plan_sha
        assert lock['development_comparison_sha256'] == sha(study/'runs/development/development-comparison.json')
        assert lock['runtime_admission_sha256'] == sha(study/'runtime-admission.json')
        assert lock['at'] <= obj(study/'runs/confirmation/attempt.json')['at']
        if phases['confirmation']['complete']:
            confirmation, confirmation_checks = M.confirmation_gate(all_binary['confirmation'],
                all_typed['confirmation'], all_classes['confirmation'], all_confusions['confirmation']['ruvector_top2'],
                all_intervals['confirmation'], all_typed_intervals['confirmation'])
    else:
        data = s/'legal-transfer/epoch16'
        assert not (data/'confirmation24.jsonl').exists() and not (data/'confirmation-materialization.json').exists()
        assert not (study/'confirmation-selection-lock.json').exists()
        assert not dev or not admission or not admission['allowed']
    assert maximum_drift < 1e-5
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'scope':'Independent saved output/wire/rawlogit/pool/gold/typed/binary/gate/CI/resource replay; separate source/vector replay required. No inference.',
        'plan_SHA256':expected_plan_sha,'status':terminal['status'],'metrics':all_binary,
        'typed_metrics':all_typed,'typed_confusions':all_confusions,'gold_class_counts':all_classes,
        'DEV_gate_passed':dev,'DEV_gate_checks':checks,'internal_confirmation_gate_passed':confirmation,
        'confirmation_gate_checks':confirmation_checks,'confirmation_consumed':'confirmation' in attempted,
        'binary_paired_doc_bootstrap':all_intervals,'typed_paired_doc_bootstrap':all_typed_intervals,
        'nominal_intervals_not_familywise':True,'observed_scored_request_counts':dict(observed_counts),
        'maximum_same_input_logit_drift':maximum_drift,'runtime_admission_independently_recomputed':admission,
        'phase_evidence':phases,'rows':details,'auditor_model_native_session_fit_paid_GPU_calls':0,
        'official_score':None,'official_rank':None,'SOTA_established':False}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--plan-path',type=Path,required=True); ap.add_argument('--expected-plan-sha',required=True)
    ap.add_argument('--out',type=Path,required=True); a = ap.parse_args()
    plan = a.plan_path if a.plan_path.is_absolute() else a.project/a.plan_path
    result = audit(a.project.resolve(), plan, a.expected_plan_sha)
    raw = (json.dumps(result,indent=2)+chr(10)).encode()
    with a.out.open('xb') as f: f.write(raw)
    print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(raw).hexdigest(),
        'status':result['status'],'DEV_gate_passed':result['DEV_gate_passed'],
        'confirmation_consumed':result['confirmation_consumed'],'metrics':result['metrics'],
        'typed_metrics':result['typed_metrics']}))


if __name__ == '__main__': main()
