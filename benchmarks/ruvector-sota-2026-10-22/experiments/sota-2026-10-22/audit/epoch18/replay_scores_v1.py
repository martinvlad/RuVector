"""Independent saved-output numerical, wire, data, gate and resource replay.

Prepared before epoch18 gold. No model/native sessions, inference, network or fit.
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
import importlib.util
import process_v1 as P
import math_v1 as M

ARM_KEYS = {'ruvector_top2': 'ruvector_top2', 'same_nli_lexical_top2': 'lexical_top2',
            'same_nli_positional_first2': 'positional_first2'}
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
MODEL_SHA = '821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
MODEL_REV = 'bab4bc7178836f731dcfd18c06ca9def0a137712'
NEW_REV = '2b65bccdedcead4bc685988bcc30153d4922a789'
NEW_SHA = 'cc41eeb065c6ab3f7e88f8dab756334abb1f77a1136fec8cf02442143934c253'
NEW_SPM = '5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17'
NEW_CONFIG = '617f9d0b46fe934497a5aab5b44b1b343a751c0c43fec3e56e26b21e76b77c60'


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


def raw_distribution(decoding, premise, hypothesis, new_reader, runtime_receipt=None):
    mapping = ({'contradiction':0,'neutral':1,'entailment':2} if new_reader
               else {'contradiction':0,'entailment':1,'neutral':2})
    assert decoding['raw_label_indices'] == mapping
    probability = M.softmax(decoding['logits'], mapping)
    M.distribution(decoding['raw_threeway_probabilities'], M.LABELS, M.INTERNAL_TOL)
    for label in M.LABELS: M.close(probability[label], decoding['raw_threeway_probabilities'][label])
    assert decoding['model_revision'] == (NEW_REV if new_reader else MODEL_REV)
    if new_reader:
        assert decoding['model_repo'] == 'microsoft/deberta-v2-xlarge-mnli'
        assert decoding['original_checkpoint_sha256'] == NEW_SHA
        assert decoding['tokenizer_sha256'] == NEW_SPM and decoding['config_sha256'] == NEW_CONFIG
        assert decoding['precision'] == 'TORCH_DYNAMIC_QINT8_LINEAR_FP32_REMAINDER_FBGEMM'
        assert decoding['raw_logit_dtype'] == 'float32'
        assert decoding['actual_model_inputs'] == ['input_ids','attention_mask','token_type_ids']
        assert decoding['typed_order'] == list(M.LABELS)
        assert decoding['canonical_logits_E_C_N'] == [decoding['logits'][mapping[x]] for x in ('entailment','contradiction','neutral')]
        assert runtime_receipt
        receipt = runtime_receipt['new_reader']
        assert decoding['quantized_weight_state_sha256'] == receipt['quantized_weight_state_sha256']
        assert decoding['converted_tokenizer_backend_sha256'] == receipt['tokenizer']['converted_backend_sha256']
    else:
        assert decoding['onnx_sha256'] == MODEL_SHA
        assert decoding['actual_graph_inputs'] == ['attention_mask','input_ids']
    assert decoding['temperature'] == 1 and decoding['batch_size'] == 1
    assert not decoding['truncated'] and decoding['padding_tokens'] == 0
    n = decoding['input_tokens']
    assert type(n) is int and 0 < n <= 512
    assert decoding['raw_tokens'] == decoding['used_tokens'] == decoding['actual_model_pair_tokens'] == n
    assert len(decoding['input_ids']) == len(decoding['attention_mask']) == len(decoding['token_type_ids']) == n
    assert all(type(v) is int and v >= 0 for v in decoding['input_ids'])
    assert all(type(v) is int and v == 1 for v in decoding['attention_mask'])
    assert all(type(v) is int and v in (0,1) for v in decoding['token_type_ids'])
    raw = json.dumps({'premise':premise,'hypothesis':hypothesis}, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False)
    assert text_hash(raw) == decoding['input_text_sha256']
    return probability


def verify_reader_receipt(receipt):
    new = receipt['new_reader']
    assert new['repo'] == 'microsoft/deberta-v2-xlarge-mnli' and new['revision'] == NEW_REV
    assert new['original_checkpoint_sha256'] == NEW_SHA
    assert new['tokenizer_sha256'] == NEW_SPM and new['config_sha256'] == NEW_CONFIG
    assert new['label_indices'] == {'contradiction':0,'neutral':1,'entailment':2}
    assert new['loaded_parameter_dtypes_before_quantization'] == ['torch.float32']
    assert new['device'] == 'cpu' and new['threads'] == 2 and new['interop_threads'] == 1
    assert new['deterministic_algorithms'] and not new['training_or_calibration_fit']
    assert new['model_initializations'] == new['quantization_initializations'] == 1
    assert new['initialization_model_forwards'] == 0
    assert new['versions'] == {'torch':'2.7.1+cpu','transformers':'4.52.4','sentencepiece':'0.2.0',
           'tokenizers':'0.21.4','safetensors':'0.5.3','protobuf':'5.29.5'}
    assert new['batch_size'] == 1 and new['temperature'] == 1 and new['pair_token_cap'] == 512
    assert not new['padding'] and not new['truncation']
    assert new['hidden_size'] == 1536 and new['layers'] == 24
    assert new['quantized_linear_count'] == len(new['quantized_linear_modules']) > 0
    assert len(new['quantized_weight_state_sha256']) == 64
    assert all(x['weight_dtype']=='torch.qint8' for x in new['quantized_linear_modules'])
    assert len({x['name'] for x in new['quantized_linear_modules']}) == new['quantized_linear_count']
    previous = receipt['previous_reader']
    assert previous['revision'] == MODEL_REV and previous['model_sha256'] == MODEL_SHA
    assert previous['label_indices'] == {'contradiction':0,'entailment':1,'neutral':2}
    assert previous['provider'] == 'CPUExecutionProvider' and previous['threads'] == 2
    assert previous['onnxruntime'] == '1.22.1' and previous['tokenizers'] == '0.21.4'
    assert previous['numpy'] == '2.2.6' and previous['precision'] == 'OFFICIAL_QUINT8_AVX2'
    assert receipt['bge']['provider'] == 'CPUExecutionProvider' and receipt['bge']['threads'] == 2
    assert receipt['bge']['onnxruntime'] == '1.22.1'
    return True


def source_evaluator(root):
    path = root/'experiments/sota-2026-10-22/benchmark/evaluate.py'
    spec = importlib.util.spec_from_file_location('independent18_pinned_evaluator', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    scorer = value._load_scorer()
    assert sha(path.parent/'sources/jevbench_scoring.py') == '6aa17d212ea20a3eeb6876149367842e8462c11dcb54d73df062fb406368331e'
    assert scorer.SUM_TOL == M.SUM_TOL == 1e-3
    return value


def verify_recipe(plan, root, phase, expected, attempted):
    recipe = plan['lazy_confirmation']
    assert sha(root/recipe['source_path']) == recipe['source_sha256'] == SOURCE_SHA
    assert sha(root/recipe['builder_path']) == recipe['builder_sha256']
    assert sha(root/recipe['source_freeze_path']) == recipe['source_freeze_sha256']
    data = root/'experiments/sota-2026-10-22/legal-transfer/epoch18'
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


def verify_operational_admission(plan, root):
    assert plan['measurement_plan'] is True and plan['operational_prelabel_only'] is False
    assert plan['runtime_admission']['capacity_pending_label_free_inputs'] is False
    ref = plan['prelabel_operational_admission']
    assert ref['path'] == 'experiments/sota-2026-10-22/audit/epoch18/prelabel-operational-admission-v1.json'
    report = root/ref['path']; assert sha(report) == ref['sha256']
    value = obj(report)
    assert value['checks_passed'] is True
    assert value['status'] == 'FULL_UNMOCKED_OPERATIONAL_PRELABEL_ADMISSION_PASS'
    assert value['operational_prelabel_only'] is True and value['native_execution_admitted'] is False
    assert value['actual_full_require_plan_calls'] == 1
    assert value['original_case_inputs_or_annotation_choices_projected'] == 0
    assert value['model_native_fit_paid_GPU_calls'] == 0
    assert value['source_freeze_path'] == plan['lazy_confirmation']['source_freeze_path']
    assert value['source_freeze_sha256'] == plan['lazy_confirmation']['source_freeze_sha256']
    assert sha(root/value['source_freeze_path']) == value['source_freeze_sha256']
    assert sha(root/value['plan_path']) == value['plan_sha256']
    assert sha(root/'experiments/sota-2026-10-22/controller/epoch18/loop.py') == value['controller_source_sha256']
    assert sha(root/'experiments/sota-2026-10-22/controller/epoch3_loop.py') == value['inherited_verifier_sha256']
    pending = obj(root/value['plan_path'])
    assert pending['measurement_plan'] is False and pending['operational_prelabel_only'] is True
    assert pending['runtime_admission']['capacity_pending_label_free_inputs'] is True
    assert pending['runtime_admission']['max_DEV_units'] == pending['runtime_admission']['max_confirmation_units'] == 1
    contract_keys = ('schema_version','limits','controller_version','epoch','revision','study_id','binary_probability_policy',
                'expected_native_receipt','expected_nli_revision','expected_nli_sha256',
                'expected_new_reader_receipt','expected_previous_reader_receipt','datasets','train','calibration',
                'lazy_confirmation','actual_project','lease_expires_unix','candidate_manifest_sha256','inference_python',
                'research_plan_sha256','acceptance_contract',
                'prior_closed_study_native_attempts','new_study_native_attempt_cap',
                'new_study_native_attempts_before','prior_closed_epoch17_native_attempts')
    for key in contract_keys:
        assert pending[key] == plan[key], key
    assert pending['runtime_admission']['formula_id'] == plan['runtime_admission']['formula_id']
    contract = {key:plan[key] for key in contract_keys}
    contract['runtime_formula_id'] = plan['runtime_admission']['formula_id']
    assert text_hash(canonical(contract)) == value['operational_contract_sha256']
    pinmap = {x['path']:x['sha256'] for x in plan['pins']}
    assert len(pinmap) == len(plan['pins'])
    assert pinmap[ref['path']] == ref['sha256']
    assert pinmap[value['plan_path']] == value['plan_sha256']
    return True


def audit(root, plan_path, expected_plan_sha):
    s = root/'experiments/sota-2026-10-22'; study = s/'epoch18'
    assert sha(plan_path) == expected_plan_sha
    plan = obj(plan_path)
    assert plan['prior_closed_study_native_attempts'] == 18
    assert plan['limits']['seconds_per_decision'] == 30
    assert plan['measurement_plan'] is True and plan['operational_prelabel_only'] is False
    assert plan['prior_closed_epoch17_native_attempts'] == 0
    verify_operational_admission(plan,root)
    assert plan['binary_probability_policy'] == {'SUM_TOL':1e-3,'strict_valid':True,'renormalized':False,'normalization':'none','typed_raw_tolerance':1e-10}
    evaluator = source_evaluator(root)
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
    assert terminal['lifetime_native_attempts'] == 18+len(attempted)
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
        if runtime:
            verify_reader_receipt(runtime['receipt'])
            for key, value in plan['expected_native_receipt'].items(): assert runtime['receipt'][key] == value
        actual, wire = optional_rows(run/'records.jsonl'), optional_rows(run/'wire.jsonl')
        events, starts = optional_rows(run/'server-audit.jsonl'), optional_rows(run/'started-requests.jsonl')
        complete = bool(completion and completion['exit_code'] == 0 and completion['error'] is None)
        expected_path = root/plan['datasets'][phase]
        expected = rows(expected_path) if expected_path.exists() else []
        if expected:
            recipe = verify_recipe(plan, root, phase, expected, True)
        else:
            assert phase == 'confirmation' and not complete and not actual
            recipe = {'role': 'confirmation', 'source_gold_choices_independently_verified': 0,
                      'projection_failed_before_dataset_receipt': True}
        complete = P.phase_evidence(plan, phase, expected_plan_sha, invocation, attempt,
            completion, runtime, ev['resources'], ev['cleanup'], len(actual), len(wire), len(starts), live)
        if complete:
            assert len(actual) == len(expected) == len(wire) == len(events) == len(starts) == 24
            assert sum(r['elapsed_s'] for r in actual)+runtime['phase_initialization_seconds'] <= completion['wall_seconds_including_model_load']+.1
            assert sha(run/'records.jsonl') == ev['report']['records_sha256']
            assert sha(run/'wire.jsonl') == ev['report']['wire_sha256']
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
            h = row['input']['questions']['decision']['criteria']['Yes']
            usage = response['usage']
            assert usage['paid_calls'] == 0 and usage['nli_singleton_pairs'] == 4
            assert usage['new_reader_pairs'] == 3 and usage['previous_reader_pairs'] == 1
            assert usage['native_requests'] == usage['native_core_searches'] == 1
            typed_probabilities = {}
            for name, key in ARM_KEYS.items():
                arm = d['arms'][key]
                assert arm['hypothesis'] == h and 'counterclaim' not in arm and 'pooling' not in arm
                decodings = [(name, arm['new_decoding'], True)]
                if name == 'ruvector_top2':
                    decodings.append(('previous_reader_native_same_premise', arm['previous_decoding'], False))
                for target, decoding, is_new in decodings:
                    typed_probabilities[target] = raw_distribution(decoding, arm['premise'], h, is_new, runtime['receipt'])
                    fingerprint = (decoding['model_revision'], decoding.get('quantized_weight_state_sha256', decoding.get('onnx_sha256')), decoding['input_text_sha256'])
                    logits = decoding['logits']
                    if fingerprint in inputs_seen:
                        maximum_drift = max(maximum_drift, max(abs(a-b) for a,b in zip(logits, inputs_seen[fingerprint])))
                    else: inputs_seen[fingerprint] = logits
                    observed_counts['NLI_pairs_in_scored_requests'] += 1
                    observed_counts['new_reader_pairs_in_scored_requests' if is_new else 'previous_reader_pairs_in_scored_requests'] += 1
                    observed_counts['NLI_tokens_in_scored_requests'] += decoding['input_tokens']
            gold = row['evaluation']['gold']; gold_typed = row['evaluation']['original_threeway_label']
            assert gold == ('Yes' if gold_typed == 'Entailment' else 'No')
            class_counts[gold_typed] += 1; groups.append(row['source_group'])
            proof = {'id': row['id'], 'phase': phase, 'source_group': row['source_group'],
                     'gold_binary': gold, 'gold_typed': gold_typed, 'arms': {}}
            for arm in M.BINARY_ARMS:
                answer = selected_response(response, arm)['answers']['decision']
                source_score = evaluator.score_record({**row,'response':selected_response(response,arm)})
                probability = M.binary_wire(answer['probabilities'],source_score)
                assert answer['choice'] == M.prediction(probability)
                scored = M.row_score(probability, gold, ['Yes','No'])
                assert bool(source_score['correct']) == scored['correct']
                M.close(source_score['brier'],scored['brier']); M.close(source_score['nll'],scored['nll'])
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
                    vpub = published[kind][arm]
                    M.close(vpub['mean_brier'],v['brier']); M.close(vpub['mean_nll'],v['nll'])
                    assert vpub['strict_valid_count'] == v['strict_valid']
                    if kind == 'typed_metrics':
                        assert v['by_class'] == vpub['by_class']
                        assert vpub['gold_counts'] == dict(class_counts)
                        assert vpub['correct_by_gold'] == {x:confusion[arm].get(x+'->'+x,0) for x in M.LABELS}
                        assert vpub['prediction_counts'] == {y:sum(confusion[arm].get(x+'->'+y,0) for x in M.LABELS) for y in M.LABELS}
                        assert vpub['confusion'] == {x:{y:confusion[arm].get(x+'->'+y,0) for y in M.LABELS} for x in M.LABELS}
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
        at_unix = datetime.fromisoformat(admission['at']).timestamp()
        forecast, allowed = P.runtime_forecast(plan,phase['latency']['max'],initialization,at_unix)
        M.close(forecast, admission['projected_confirmation_seconds'])
        M.close(initialization, admission['DEV_initialization_seconds'])
        M.close(phase['latency']['max'], admission['max_DEV_HTTP_seconds'])
        remaining = plan['lease_expires_unix']-datetime.fromisoformat(admission['at']).timestamp()
        assert admission['allowed'] == allowed
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
        data = s/'legal-transfer/epoch18'
        assert not (data/'confirmation24.jsonl').exists() and not (data/'confirmation-materialization.json').exists()
        assert not (study/'confirmation-selection-lock.json').exists()
        assert not dev or not admission or not admission['allowed']
    assert maximum_drift < 1e-5
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'scope':'Independent saved output/wire/rawlogit/new900M+oldreader/gold/typed/binary/gate/CI/resource replay; separate source/vector replay required. No inference.',
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
