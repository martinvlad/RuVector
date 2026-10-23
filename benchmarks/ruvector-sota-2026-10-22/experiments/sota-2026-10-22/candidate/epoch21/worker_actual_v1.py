"""One owned, nonretryable FP32 readiness plus optional legal-corpus process."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
import common as C
import retrieval as R


def now(): return datetime.now(timezone.utc).isoformat()


def resources():
    own = resource.getrusage(resource.RUSAGE_SELF); child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'worker_cpu_user_seconds': own.ru_utime, 'worker_cpu_system_seconds': own.ru_stime,
        'worker_peak_RSS_bytes': own.ru_maxrss * 1024, 'terminated_children_cpu_user_seconds': child.ru_utime,
        'terminated_children_cpu_system_seconds': child.ru_stime,
        'largest_terminated_child_peak_RSS_bytes': child.ru_maxrss * 1024,
        'allowed_CPU_ids': sorted(os.sched_getaffinity(0)),
        'scope': 'Process and child maxima are separate observations, never a simultaneous RSS sum.'}


def verify_assets(plan):
    model = C.read(C.checked(plan['model_assets_lock_path']))
    if model['repository'] != C.MODEL or model['revision'] != C.REVISION or len(model['assets']) != 9:
        raise ValueError('Exact nine-file official original reader required')
    bge = C.read(C.checked(plan['bge_assets_lock_path']))
    bge_rows = bge['assets'] if 'assets' in bge else bge['files']
    native = C.read(C.checked(plan['native_closure_path']))
    native_rows = ([r for package in native['packages'] for r in package['files']]
                   if 'packages' in native else native['files'])
    native_rows = [r for r in native_rows if r['path'].startswith('retrieval/node_modules/')]
    if len(native_rows) != 8: raise ValueError('Exact eight-file native node closure required')
    receipts = []
    for r in model['assets'] + bge_rows + native_rows:
        p = C.checked(r['path'])
        if p.stat().st_size != r['bytes'] or C.sha(p) != r['sha256']:
            raise ValueError('Actual public model/native asset changed: ' + r['path'])
        receipts.append({k: r[k] for k in ('path', 'bytes', 'sha256')})
    wheel_lock = C.read(C.checked(plan['wheel_lock_path']))
    if len(wheel_lock['wheels']) != 31: raise ValueError('Exact31 CPU wheels required')
    versions = {}
    for r in wheel_lock['wheels']:
        name, expected = r['filename'].split('-', 2)[:2]; version = importlib.metadata.version(name)
        if version != expected: raise ValueError('Installed distribution changed: ' + name)
        versions[name] = version
    folder = C.checked(next(r['path'] for r in model['assets'] if r['remote_path'] == 'config.json')).parent
    return folder, receipts, versions


def hypothesis(row):
    inputs = row['input']; questions = inputs['questions']
    if set(questions) != {'decision'}: raise ValueError('Exactly one supplied decision per input row')
    q = questions['decision']
    if q.get('type') != 'choice' or set(q.get('criteria', {})) != {'Yes', 'No'}:
        raise ValueError('Exact Yes/No question semantics required')
    h = q['criteria']['Yes']
    if not isinstance(h, str) or not h.strip(): raise ValueError('Whole unchanged positive hypothesis required')
    if hashlib.sha256(C.canonical(inputs).encode()).hexdigest() != row['input_sha256']:
        raise ValueError('Input-only row hash changed')
    return h


def groups(value, phase, allowlist):
    if value.get('role') != phase or len(value['records']) != 24: raise ValueError('Exact phase24 input-only records required')
    expected = {r['id']: r for r in allowlist['records']}
    if len(expected) != 24 or {r['id'] for r in value['records']} != set(expected):
        raise ValueError('Exact frozen question identity allowlist required')
    result = {}; ids = set()
    for row in value['records']:
        if set(row) != {'id', 'input', 'input_sha256'}: raise ValueError('No gold/extra input fields allowed')
        if row['id'] in ids: raise ValueError('Duplicate question ID')
        ids.add(row['id']); h = hypothesis(row); parts = row['id'].split(':')
        if len(parts) != 6 or parts[:4] != ['original-contractnli', 'train', 'epoch21', phase]:
            raise ValueError('Exact epoch21 role/question identity required')
        doc = int(parts[4]); state = row['input']['state']; allowed = expected[row['id']]
        if (doc < 0 or str(doc) != parts[4] or allowed.get('document_id', doc) != doc
                or allowed.get('source_group', 'original-contractnli:' + str(doc)) != 'original-contractnli:' + str(doc)
                or allowed['hypothesis_id'] != parts[5]
                or ('input_sha256' in allowed and allowed['input_sha256'] != row['input_sha256'])):
            raise ValueError('Exact canonical document/hypothesis/input identity required')
        if not isinstance(state, str) or not state: raise ValueError('Whole source contract required')
        if doc not in result: result[doc] = {'id': doc, 'state': state, 'questions': []}
        if result[doc]['state'] != state: raise ValueError('One exact source state per document ID')
        result[doc]['questions'].append({'id': row['id'], 'hypothesis': h, 'input_sha256': row['input_sha256']})
    if len(result) != 8 or any(len(d['questions']) != 3 for d in result.values()):
        raise ValueError('Exactly8 supplied contracts and3claims each required')
    return list(result.values())


def materialize(plan, phase):
    entry = plan['phases'][phase]; recipe = C.read(C.checked(entry['input_recipe_path']))
    builder_path = recipe['builder_path']; builder_sha = recipe['builder_sha256']
    if C.sha(C.checked(builder_path)) != builder_sha: raise ValueError('Frozen input recipe builder changed')
    builder = C.load_module('epoch21_input_only_lazy_projection', builder_path, builder_sha)
    return builder.materialize_inputs(project=C.ROOT, phase=phase,
        source_freeze_path=C.checked(plan['source_freeze_path']),
        expected_source_freeze_sha256=plan['source_freeze_sha256'])


def confirmation_capacity(plan, reader, evidence, counters):
    """Only exact already-published input text tokenization, never predictions/gold."""
    path = C.checked(plan['confirmation_capacity_inputs_path'])
    if C.sha(path) != plan['confirmation_capacity_inputs_sha256']:
        raise ValueError('Previously published input-only capacity bank changed')
    bank = C.read(path)
    allow = C.read(C.checked(plan['phases']['confirmation']['input_allowlist_path']))
    expected = {r['input_sha256']: r for r in allow['records']}
    if len(expected) != 24 or len(bank['records']) != 24 or bank['role'] != 'confirmation':
        raise ValueError('Exact unused24 input-only confirmation identities required')
    states = {}; seen = set(); order = []
    for r in allow['records']:
        doc = int(r['source_group'].split(':')[-1])
        if doc not in order: order.append(doc)
    before = dict(counters)
    for row in bank['records']:
        if set(row) != {'id', 'input', 'input_sha256'}: raise ValueError('No labels in input-only capacity bank')
        hypothesis(row); h = row['input_sha256']
        if h not in expected or h in seen: raise ValueError('Frozen confirmation input identity mismatch')
        seen.add(h); meta = expected[h]; doc = int(meta['source_group'].split(':')[-1])
        parts = row['id'].split(':')
        if len(parts) != 6 or int(parts[4]) != doc or parts[5] != meta['hypothesis_id']:
            raise ValueError('Confirmation source document/hypothesis identity changed')
        state = row['input']['state']
        if doc in states and states[doc] != state: raise ValueError('Confirmation document text disagrees')
        states[doc] = state
    if len(states) != 8 or len(order) != 8: raise ValueError('Exactly8 fixed confirmation contracts required')
    counts = []
    for doc in order:
        units = evidence.context.partition(states[doc], reader.tokenizer, evidence.bge.raw_tokenizer,
            target=128, nli_cap=160, bge_cap=256, max_units=192)
        counts.append({'document_id': doc, 'units': len(units)})
    if counters != before: raise ValueError('Capacity tokenization must execute zero model/native forwards')
    return {'scope': 'INPUT_ONLY_TOKENIZATION_CAPACITY', 'source_path': str(path.relative_to(C.ROOT)),
        'source_sha256': C.sha(path), 'document_units': counts, 'max_units': max(r['units'] for r in counts),
        'model_forwards': 0, 'annotation_choices_accessed': 0,
        'confirmation_NLI_predictions': 0, 'text_previously_published': True,
        'training_selection_on_confirmation_labels': False}


def perform(plan, phase, raw, folder, deadline, progress):
    asset_folder, assets, versions = verify_assets(plan)
    raw.update(asset_identities=assets, versions=versions); progress(); R.remaining(deadline)
    rows = C.canaries(plan); bundle = R.engineering_bundle(rows)
    raw['engineering_native_trace'] = R.native(bundle, folder, 'engineering', deadline, raw['counters'], progress)
    raw['engineering_native_trace']['native_selection_affects_NLI'] = False
    progress(); R.remaining(deadline)
    from reader_actual_v1 import Reader, state_identity
    reader = Reader(asset_folder, raw['counters'], progress, plan=plan, output_folder=folder)
    raw.update(model_provenance=reader.receipt, fp32_state=reader.state, tokenizer=reader.token_receipt)
    raw['initialization_elapsed_seconds'] = time.monotonic() - raw['_start_monotonic']
    if phase == 'confirmation':
        adm = C.read(C.STUDY / 'CONFIRMATION_ADMISSION.json')
        if (adm['expected_FP32_state_sha256'] != reader.state_sha
                or adm['expected_tokenizer_backend_sha256'] != reader.token_receipt['backend_sha256']):
            raise ValueError('Confirmation must retain actual accepted DEV model/tokenizer state')
    progress()
    for row in rows:
        R.remaining(deadline); forward = reader.forward(row['premise'], row['hypothesis'])
        raw['canary_forwards'].append({'fixture_id': row['id'], 'expected_typed_label': row['expected_typed_label'],
                                        'forward': forward}); progress()
    correct = sum(x['forward']['typed_prediction'] == x['expected_typed_label'] for x in raw['canary_forwards'])
    raw['FP32_state_after_canaries_sha256'] = state_identity(reader.model, reader.torch)
    raw['tokenizer_backend_after_canaries_sha256'] = reader.backend_identity()
    if raw['FP32_state_after_canaries_sha256'] != reader.state_sha:
        raise ValueError('Reader state changed during fixed engineering readiness')
    if raw['tokenizer_backend_after_canaries_sha256'] != reader.token_receipt['backend_sha256']:
        raise ValueError('Official operational tokenizer changed during fixed engineering readiness')
    readiness = {'passed': correct == 3, 'correct': correct, 'n': 3, 'pid': os.getpid(), 'phase': phase,
        'plan_sha256': raw['plan_sha256'], 'source_freeze_sha256': plan['source_freeze_sha256'],
        'canary_forward_receipt_sha256': hashlib.sha256(C.canonical(raw['canary_forwards']).encode()).hexdigest(),
        'fp32_state_sha256': reader.state_sha, 'tokenizer_backend_sha256': reader.token_receipt['backend_sha256'],
        'scope': 'Three already exposed public engineering examples; not benchmark performance.'}
    C.write_new(folder / 'semantic-readiness.json', readiness); raw['semantic_readiness'] = readiness; progress()
    if not readiness['passed']:
        raw['status'] = 'REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'; return
    R.remaining(deadline)
    inputs = materialize(plan, phase)
    documents = groups(inputs, phase, C.read(C.checked(plan['phases'][phase]['input_allowlist_path'])))
    raw['input_only_projection'] = {'records': len(inputs['records']), 'documents': len(documents),
        'canonical_input_document_sha256': hashlib.sha256(C.canonical(inputs).encode()).hexdigest(),
        'annotation_choices_accessed_by_worker': 0, 'phase': phase}
    evidence = R.Evidence(reader, raw['counters']); raw['BGE_provenance'] = evidence.receipt
    if phase == 'dev': raw['confirmation_capacity'] = confirmation_capacity(plan, reader, evidence, raw['counters'])
    raw['whole_pipeline_initialization_seconds'] = time.time() - raw['invocation_started_unix']; progress()
    for document in documents:
        R.remaining(deadline); started = time.perf_counter()
        state = document['state']; questions = document['questions']
        units, prelude, chunks, bundle, embedding = evidence.prepare(state, [q['hypothesis'] for q in questions])
        trace = R.native(bundle, folder, 'document-' + str(document['id']), deadline, raw['counters'], progress)
        preparation_seconds = time.perf_counter() - started
        output = {'id': document['id'], 'state': state, 'state_sha256': hashlib.sha256(state.encode()).hexdigest(),
            'source_units': units, 'document_vectors': bundle['vectors'], 'query_vectors': bundle['query_vectors'],
            'native_trace': trace, 'embedding': embedding, 'shared_definition_priority': prelude, 'questions': [],
            'document_preparation_elapsed_seconds': preparation_seconds}
        raw['documents'].append(output); progress()
        for index, q in enumerate(questions):
            question_started = time.perf_counter(); depth = min(40, len(units))
            rankings = dict(zip(C.ARMS, (trace['raw_native_output']['queries'][index]['ids'],
                R.lexical_ids(chunks, q['hypothesis'], depth), list(range(depth)))))
            answer = dict(q, rankings=rankings, arms={}); output['questions'].append(answer)
            for arm in C.ARMS:
                R.remaining(deadline)
                premise, coverage = evidence.pack(state, units, rankings[arm], q['hypothesis'], prelude)
                forward = reader.forward(premise, q['hypothesis'])
                answer['arms'][arm] = {'premise': premise, 'coverage': coverage, 'forward': forward}; progress()
            answer['all_arm_request_elapsed_seconds'] = time.perf_counter() - question_started
            answer['amortized_all_arm_request_elapsed_seconds'] = answer['all_arm_request_elapsed_seconds'] + preparation_seconds / len(questions)
            answer['amortized_latency_scope'] = 'Direct three-arm packing/reader time plus one third of this three-query document partition/BGE/native preparation; not primary-only serving.'
            raw['counters']['benchmark_questions_completed'] += 1
        output['document_elapsed_seconds'] = time.perf_counter() - started
        raw['counters']['benchmark_documents_completed'] += 1
        progress()
    raw['FP32_state_after_sha256'] = state_identity(reader.model, reader.torch)
    raw['tokenizer_backend_after_sha256'] = reader.backend_identity()
    if raw['FP32_state_after_sha256'] != reader.state_sha: raise ValueError('Reader state changed during evaluation')
    if raw['tokenizer_backend_after_sha256'] != reader.token_receipt['backend_sha256']:
        raise ValueError('Official operational tokenizer changed during evaluation')
    raw['status'] = 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'; progress()


def main():
    ap = argparse.ArgumentParser()
    for key in ('plan', 'admission'): ap.add_argument('--' + key, type=Path, required=True)
    ap.add_argument('--phase', choices=('dev', 'confirmation'), required=True)
    ap.add_argument('--expected-plan-sha', required=True); ap.add_argument('--deadline', type=float, required=True)
    args = ap.parse_args(); plan = C.require_plan(args.plan, args.expected_plan_sha)
    C.verify_admission(args.admission, args.expected_plan_sha, args.phase)
    folder = C.STUDY / 'runs' / args.phase
    until = min(args.deadline, time.time() + 5)
    while not (folder / 'attempt.json').exists() and time.time() < until: time.sleep(.01)
    attempt = C.read(folder / 'attempt.json')
    if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpgid(0)
            or attempt.get('phase') != args.phase or attempt.get('plan_sha256') != args.expected_plan_sha
            or os.getpid() != os.getpgid(0) or len(os.sched_getaffinity(0)) != 2):
        raise ValueError('Only exact reserved owned worker may import models/native')
    keys = ('model_initializations', 'checkpoint_metadata_loads', 'nli_forward_pairs', 'BGE_initializations', 'ORT_sessions',
            'BGE_forwards', 'BGE_texts', 'native_index_initializations', 'native_queries')
    counters = {name + suffix: 0 for name in keys for suffix in ('_attempted', '_completed')}
    counters.update(quantization_initializations=0, paid_API_calls=0, GPU_calls=0, native104_calls=0,
        previous_reader_forwards=0, training_calibration_fits=0, benchmark_HTTP_requests=0,
        benchmark_documents_completed=0, benchmark_questions_completed=0, BGE_forward_seconds=0.0)
    raw = {'schema_version': 1, 'epoch': 21, 'phase': args.phase, 'at': now(), 'status': 'STARTED',
        'plan_sha256': args.expected_plan_sha, '_start_monotonic': time.monotonic(),
        'invocation_started_unix': attempt['invocation_started_unix'],
        'canary_forwards': [], 'engineering_native_trace': None, 'documents': [], 'counters': counters,
        'resources': {'before_runtime': resources()}, 'cleanup': {}, 'errors': []}
    def progress(): C.replace_report(folder / 'raw.json', raw)
    progress()
    try:
        perform(plan, args.phase, raw, folder, args.deadline, progress)
        if (counters['nli_forward_pairs_completed'] not in (3, 75)
                or counters['native_queries_completed'] not in (3, 27)
                or counters['native_index_initializations_completed'] not in (1, 9)):
            raise ValueError('Unexpected scientific forward/native count')
    except BaseException as exc:
        raw['errors'].append({'type': type(exc).__name__, 'message': str(exc)})
        raw['status'] = 'FAILED_OR_INCOMPLETE_PRESERVED_EVIDENCE'
        raise
    finally:
        raw['resources']['after_runtime'] = resources()
        raw['finished_at'] = now(); raw['finished_within_deadline'] = time.time() <= args.deadline
        raw['wall_seconds_inside_worker'] = time.monotonic() - raw.pop('_start_monotonic')
        raw['cleanup']['all_native_helpers_reaped'] = all(
            not Path('/proc/' + str(C.read(p)['pid'])).exists() for p in folder.glob('native-attempt-*.json'))
        progress()


if __name__ == '__main__': main()
