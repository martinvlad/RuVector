"""One bounded source-admitted CPU DEV diagnostic: native24, fixed-head NLI72."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('epoch27_standard_library_common', HERE / 'common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'benchmark_HTTP_requests', 'benchmark_label_reads', 'TRAIN_calibration_fits',
        'CONF_worker_attempts', 'CONF_annotation_choices', 'CONF_NLI_pairs',
        'paid_API_calls', 'GPU_calls', 'fits', 'paid_calls', 'confirmation_calls',
        'generation_calls', 'generated_tokens', 'training_steps', 'optimizer_steps',
        'external_API_calls', 'train_calls', 'calibration_calls')
COUNTED = ('Python_literal_loopback_binds_allowed', 'BGE_initializations_attempted',
        'BGE_initializations_completed', 'ORT_sessions_attempted', 'ORT_sessions_completed',
        'BGE_forwards_attempted', 'BGE_forwards_completed', 'BGE_texts_attempted',
        'BGE_texts_completed', 'native_helper_starts', 'native_index_initializations_attempted',
        'native_index_initializations_completed', 'native_queries_attempted', 'native_queries_completed',
        'NLI_model_initializations', 'NLI_model_initializations_completed',
        'NLI_forward_pairs_attempted', 'NLI_forward_pairs_completed', 'NLI_forwards',
        'NLI_forward_calls_attempted', 'NLI_forward_calls_completed',
        'DEV_input_bank_reads', 'DEV_corpora', 'DEV_questions', 'DEV_pairs_completed',
        'DEV_cases_completed', 'automatically_extracted_units')
NATIVE_COUNTERS = ('native_index_initializations_attempted', 'native_index_initializations_completed',
                   'native_queries_attempted', 'native_queries_completed', 'Node_network_operations_attempted')


def vector_block(array):
    """Losslessly retain the actual float32 core input bits once, in row order."""
    if str(array.dtype) != 'float32' or len(array.shape) != 2 or array.shape[1] != 384:
        raise ValueError('Exact float32 matrix rows by384 required')
    payload = array.astype('<f4', copy=False).tobytes(order='C')
    if len(payload) != int(array.shape[0]) * 384 * 4:
        raise ValueError('Float32 matrix exact byte length mismatch')
    return {'encoding': 'base64', 'dtype': 'float32le',
        'shape': [int(array.shape[0]), 384], 'bytes': len(payload),
        'sha256': hashlib.sha256(payload).hexdigest(),
        'data_base64': base64.b64encode(payload).decode('ascii')}


def resources():
    own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'worker_user_seconds': own.ru_utime, 'worker_system_seconds': own.ru_stime,
            'worker_peak_RSS_bytes': own.ru_maxrss * 1024,
            'reaped_child_user_seconds': child.ru_utime,
            'reaped_child_system_seconds': child.ru_stime,
            'largest_reaped_child_peak_RSS_bytes': child.ru_maxrss * 1024,
            'CPU_affinity': sorted(os.sched_getaffinity(0)),
            'scope': 'Separate process high-water observations, not simultaneous RSS sum.'}


class CountedSession:
    def __init__(self, session, counters, progress):
        self.session, self.counters, self.progress = session, counters, progress

    def run(self, names, feed):
        count = len(feed['input_ids'])
        self.counters['BGE_forwards_attempted'] += 1
        self.counters['BGE_texts_attempted'] += count
        self.progress({'event': 'BGE_FORWARD_BEFORE', 'texts': count})
        started = time.perf_counter()
        result = self.session.run(names, feed)
        self.counters['BGE_forwards_completed'] += 1
        self.counters['BGE_texts_completed'] += count
        self.counters['BGE_forward_seconds'] += time.perf_counter() - started
        self.progress({'event': 'BGE_FORWARD_AFTER', 'texts': count})
        return result


def native_call(bundle, out, args, counters, progress):
    source, target = out / 'native-bundle.json', out / 'native-result.json'
    C.put(source, bundle, compact=True)
    if source.stat().st_size > 3300000:
        raise ValueError('Lossless once-only bundle exceeded prospective3.3MB bound')
    with tempfile.TemporaryDirectory(prefix='ruvector-e27-native-') as temporary:
        progress({'event': 'NATIVE_HELPER_BEFORE'})
        started = time.perf_counter()
        helper = subprocess.Popen(['node', str(HERE / 'native.cjs'), str(C.ROOT), str(source), str(target),
            str(args.plan), args.expected_plan_sha, str(args.admission), str(out / 'native-progress.jsonl')],
            cwd=temporary, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        counters['native_helper_starts'] += 1
        identity = C.proc(helper.pid)
        C.put(out / 'native-attempt.json', {'pid': helper.pid, 'pgid': os.getpgid(helper.pid),
            'worker_pid': os.getpid(), 'identity': identity, 'source_sha256': C.sha(HERE / 'native.cjs'),
            'bundle_sha256': C.sha(source), 'native_queries_scheduled': 24, 'native_indexes_scheduled': 8})
        stdout = stderr = ''
        try:
            stdout, stderr = helper.communicate(timeout=min(60, C.remaining(args.deadline)))
        finally:
            if helper.poll() is None:
                current = C.proc(helper.pid)
                if not identity or not current or identity['ticks'] != current['ticks']:
                    raise RuntimeError('Cannot prove exact native child identity for cleanup')
                helper.kill()
                helper.wait()
            (out / 'native.stdout').write_text(stdout)
            (out / 'native.stderr').write_text(stderr)
            log = out / 'native-progress.jsonl'
            if log.is_file():
                for line in log.read_text().splitlines():
                    event = json.loads(line)
                    for key in NATIVE_COUNTERS:
                        if key in event:
                            counters[key] = event[key]
        if helper.returncode != 0:
            failure = Path(str(target) + '.failure.json')
            if failure.is_file():
                C.put(out / 'native-failure.json', C.read(failure))
            raise RuntimeError('Actual native helper failed: ' + stderr[-1500:])
        result = C.read(target)
        if (result.get('native') is not True or result.get('bundle_sha256') != C.sha(source)
                or result.get('native_binary_sha256') != C.BINARY_SHA
                or result.get('package_version') != '0.1.33'
                or result.get('platform_package_version') != '0.1.31'
                or result.get('binary_version') != '2.3.0' or result.get('helper_pid') != helper.pid
                or result.get('compact_schema') != 'epoch27-native-compact-f32le-v2'
                or len(result['documents']) != 8):
            raise ValueError('Exact native helper/binary/bundle receipt mismatch')
        for key in NATIVE_COUNTERS:
            counters[key] = result[key]
        progress({'event': 'NATIVE_HELPER_AFTER', 'helper_pid': helper.pid,
                  'helper_wall_seconds': time.perf_counter() - started, 'helper_exited': True})
    return result


def perform(raw, plan, reader_module, bank, out, args, progress, offline):
    counters = raw['counters']
    evidence = C.load_module('epoch27_mechanical_evidence', HERE / 'evidence.py')
    records = evidence.validate_inputs(bank)
    counters.update(DEV_corpora=8, DEV_questions=24)
    context = C.load_module('epoch27_exact_epoch22_context', C.checked(C.CONTEXT_SOURCE), C.CONTEXT_SHA)
    # All heavy imports happen after remote admission, exact source/runtime pins,
    # exact guardian check, and durable attempt identity have been verified.
    C.remaining(args.deadline)
    counters['NLI_model_initializations'] += 1
    progress({'event': 'NLI_INITIALIZATION_BEFORE'})
    started = time.perf_counter()
    reader = reader_module.FrozenBartReader(C.ROOT / plan['reader_model_dir'],
        C.checked(plan['reader_assets_lock_path']), max_pair_tokens=512, attention='sdpa')
    counters['NLI_model_initializations_completed'] += 1
    raw['reader'] = {'repository': reader_module.MODEL_REPOSITORY,
        'revision': reader_module.MODEL_REVISION, 'source_sha256': C.sha(HERE / 'reader/bart_reader.py'),
        'initialization_seconds': time.perf_counter() - started, 'dtype': 'torch.float32',
        'device': 'cpu', 'threads': 2, 'interop_threads': 1, 'attention': 'sdpa',
        'batch_size': 1, 'max_pair_tokens': 512, 'truncation': 'only_first',
        'pair_special_tokens': 4, 'pair_budget_method': 'actual full native tokenizer pair encoding for every candidate; no fixed overhead subtraction',
        'raw_logit_order': ['contradiction', 'not_mentioned', 'entailment'],
        'canonical_probability_order': ['entailment', 'contradiction', 'not_mentioned'],
        'temperature': 1.0, 'training_lineage': 'official facebook/bart-large-mnli MNLI-trained head, 2020; later selection and foundation text overlap unknown', 'diagnostic_only': True,
        'generation': False, 'no_warmup': True, 'native_class_order': ['contradiction', 'not_mentioned', 'entailment'],
        'canonical_permutation': [2, 0, 1], 'checkpoint_weights': 'original pytorch_model.bin',
        'weights_only': True, 'use_safetensors': False, 'trust_remote_code': False}
    offline.assert_clean()
    progress({'event': 'NLI_INITIALIZATION_AFTER'})
    tokenizer = evidence.PairTokenizer(reader.tokenizer)
    models = C.load_module('epoch27_original_bge', C.checked(C.BGE_SOURCE), C.BGE_SHA)
    C.remaining(args.deadline)
    counters['BGE_initializations_attempted'] += 1
    counters['ORT_sessions_attempted'] += 1
    progress({'event': 'BGE_INITIALIZATION_BEFORE'})
    started = time.perf_counter()
    bge = models.BgeEncoder(C.ROOT)
    counters['BGE_initializations_completed'] += 1
    counters['ORT_sessions_completed'] += 1
    bge.session = CountedSession(bge.session, counters, progress)
    raw['BGE'] = dict(bge.receipt, source_path=C.BGE_SOURCE, source_sha256=C.BGE_SHA,
        initialization_seconds=time.perf_counter() - started, query_prefix=QUERY_PREFIX,
        no_warmup=True, one_session=True, actual_semantic_embeddings=True)
    progress({'event': 'BGE_INITIALIZATION_AFTER'})
    documents, bundle = {}, {'schema_version': 3, 'vector_encoding': 'base64_float32le_c_order',
        'metadata_policy': 'insert id and vector only; metadata absent', 'documents': []}
    for offset in range(0, len(records), 3):
        C.remaining(args.deadline)
        rows = records[offset:offset + 3]
        document, did = rows[0]['document'], str(rows[0]['document_id'])
        started = time.perf_counter()
        units = context.partition(document, tokenizer, bge.raw_tokenizer,
            target=128, nli_cap=160, bge_cap=256, max_units=192)
        prelude = context.select_prelude(document, units, tokenizer)
        chunks = [document[u['start']:u['end']] for u in units]
        hypotheses = [row['hypothesis'] for row in rows]
        queries = [QUERY_PREFIX + h for h in hypotheses]
        if any(len(bge.raw_tokenizer.encode(q).ids) > 256 for q in queries):
            raise ValueError('Whole BGE query over256; no clipping')
        if any(len(tokenizer.encode('', h).ids) > 512 for h in hypotheses):
            raise ValueError('Whole hypothesis over512; no clipping')
        counters['automatically_extracted_units'] += len(units)
        preparation_seconds = time.perf_counter() - started
        vectors, doc_diagnostics = bge.encode(chunks)
        query_vectors, query_diagnostics = bge.encode(queries)
        if vectors.shape != (len(chunks), 384) or query_vectors.shape != (3, 384):
            raise ValueError('Exact BGE384 vector shapes required')
        norms = [math.sqrt(math.fsum(float(x) * float(x) for x in v)) for v in [*vectors, *query_vectors]]
        if any(not math.isfinite(n) or abs(n - 1.0) > 1e-5 for n in norms):
            raise ValueError('Finite normalized real BGE embeddings required')
        documents[did] = {'units': units, 'prelude': prelude, 'chunks': chunks,
            'partition_seconds': preparation_seconds, 'embedding': {'document': doc_diagnostics,
            'queries': query_diagnostics, 'exact_query_texts': queries,
            'source_sha256s': [C.text_sha(text) for text in chunks],
            'norm_min': min(norms), 'norm_max': max(norms)}}
        bundle['documents'].append({'document_id': did, 'vectors': vector_block(vectors),
            'query_vectors': vector_block(query_vectors), 'queries': [{'id': row['id']} for row in rows]})
        progress({'event': 'DOCUMENT_EMBEDDING_COMPLETE', 'document_id': did, 'units': len(units)})
    offline.assert_clean()
    native = native_call(bundle, out, args, counters, progress)
    raw['native_evidence'] = {'schema': 'epoch27-native-compact-f32le-v2',
        'bundle_path': str((out / 'native-bundle.json').relative_to(C.ROOT)),
        'bundle_sha256': C.sha(out / 'native-bundle.json'),
        'result_path': str((out / 'native-result.json').relative_to(C.ROOT)),
        'result_sha256': C.sha(out / 'native-result.json'),
        'vector_numeric_storage': 'native-bundle.json only',
        'receipt_spec': native['compact_receipt_spec']}
    by_id = {}
    for document in native['documents']:
        for query in document['queries']:
            if query['case_id'] in by_id:
                raise ValueError('Duplicate native query receipt')
            by_id[query['case_id']] = dict(query, document_id=document['document_id'],
                initialization_ms=document['initialization_ms'], initialized_vectors=document['initialized_vectors'])
    if set(by_id) != {r['id'] for r in records}:
        raise ValueError('Native query identity closure failed')
    labels = ('entailment', 'contradiction', 'not_mentioned')
    typed = {'Entailment': 'entailment', 'Contradiction': 'contradiction', 'NotMentioned': 'not_mentioned'}
    for source in records:
        C.remaining(args.deadline)
        did, hypothesis = str(source['document_id']), source['hypothesis']
        doc = documents[did]
        observed = by_id[source['id']]
        if str(observed['document_id']) != did:
            raise ValueError('Native query mapped to wrong document index')
        lexical, scores = evidence.lexical_order(doc['chunks'], hypothesis)
        rankings = {'actual_native': observed['ids'], 'lexical': lexical[:40],
                    'positional': list(range(min(40, len(doc['units']))))}
        row = {key: source[key] for key in ('id', 'document_id', 'hypothesis_id', 'input_sha256')}
        row.update(document_sha256=C.text_sha(source['document']), hypothesis_sha256=C.text_sha(hypothesis),
            hypothesis=hypothesis, native=observed, lexical_jaccard_scores=scores,
            document_preparation=doc, arms={})
        raw['cases'].append(row)
        for arm in C.ARMS:
            C.remaining(args.deadline)
            progress({'event': 'ARM_CONTEXT_BEFORE', 'case_id': source['id'], 'arm': arm})
            started = time.perf_counter()
            premise, receipt = context.pack(source['document'], doc['units'], rankings[arm], hypothesis,
                tokenizer, pair_cap=512, rank_depth=min(40, len(doc['units'])), prelude=doc['prelude'])
            source_provenance = evidence.provenance(source['document'], premise, receipt)
            # The strengthened literal receipt is authoritative for numeric provenance;
            # the unchanged legacy mechanical regex result remains explicitly named.
            receipt['legacy_numeric_mentions'] = receipt.pop('numeric_mentions')
            receipt['legacy_numeric_mentions_retained'] = receipt.pop('numeric_mentions_retained')
            receipt['legacy_numeric_mentions_omitted'] = receipt.pop('numeric_mentions_omitted')
            receipt['source_provenance'] = source_provenance
            count = len(tokenizer.encode(premise, hypothesis).ids)
            if count != receipt['joint_pair_tokens'] or not 0 < count <= 512:
                raise ValueError('Actual true-pair context budget mismatch')
            arm_row = {'observed_ranking': rankings[arm], 'premise': premise, 'context': receipt,
                'joint_pair_tokens': count,
                'context_seconds': time.perf_counter() - started,
                'native_query_seconds': observed['query_ms'] / 1000 if arm == 'actual_native' else None,
                'reader': None, 'decision': None, 'semantic_decision_override': False}
            row['arms'][arm] = arm_row
            counters['NLI_forward_pairs_attempted'] += 1
            counters['NLI_forward_calls_attempted'] += 1
            progress({'event': 'NLI_FORWARD_BEFORE', 'case_id': source['id'], 'arm': arm})
            started = time.perf_counter()
            result = reader.score_pair(premise, hypothesis)
            latency = time.perf_counter() - started
            counters['NLI_forward_pairs_completed'] += 1
            counters['NLI_forward_calls_completed'] += 1
            counters['NLI_forwards'] += 1
            probabilities = dict(zip(labels, result['probabilities_E_C_N']))
            logits = result['raw_logits_C_N_E']
            prediction = typed[result['typed_prediction']]
            if (len(logits) != 3 or not all(math.isfinite(x) for x in logits)
                    or len(result['probabilities_E_C_N']) != 3
                    or any(not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values())
                    or abs(math.fsum(probabilities.values()) - 1) > 1e-6
                    or result['pair_tokens'] != count):
                raise ValueError('Invalid fixed native-head output or hidden input truncation')
            expected_prediction = ('contradiction', 'not_mentioned', 'entailment')[max(range(3), key=lambda i: logits[i])]
            if prediction != expected_prediction:
                raise ValueError('Fixed-head prediction must equal native-logit argmax; no override')
            arm_row['reader'] = dict(result, raw_logits=logits, probabilities=probabilities,
                prediction=prediction, token_count=count, latency_seconds=latency,
                premise_sha256=C.text_sha(premise), hypothesis_sha256=C.text_sha(hypothesis))
            arm_row['decision'] = prediction
            counters['DEV_pairs_completed'] += 1
            offline.assert_clean()
            progress({'event': 'ARM_COMPLETE', 'case_id': source['id'], 'arm': arm})
        counters['DEV_cases_completed'] += 1
    expected_counts = {'NLI_model_initializations': 1, 'NLI_model_initializations_completed': 1,
        'NLI_forward_pairs_attempted': 72, 'NLI_forward_pairs_completed': 72, 'NLI_forwards': 72,
        'NLI_forward_calls_attempted': 72, 'NLI_forward_calls_completed': 72,
        'DEV_pairs_completed': 72, 'DEV_cases_completed': 24,
        'native_helper_starts': 1, 'native_index_initializations_attempted': 8,
        'native_index_initializations_completed': 8, 'native_queries_attempted': 24,
        'native_queries_completed': 24, 'BGE_initializations_attempted': 1,
        'BGE_initializations_completed': 1, 'ORT_sessions_attempted': 1, 'ORT_sessions_completed': 1}
    if any(counters[key] != value for key, value in expected_counts.items()):
        raise ValueError('Exact one-init/72 NLI/24 native/8 index count closure failed')
    raw['status'] = 'COMPLETED_DEV_DIAGNOSTIC_AWAITING_INDEPENDENT_SCORER'


def main():
    parser = argparse.ArgumentParser()
    for key in ('plan', 'admission', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    if args.out.absolute() != C.STUDY / 'runs/dev' or args.out.resolve() != args.out.absolute():
        raise ValueError('Unsafe diagnostic output directory')
    C.no_symlink(args.out)
    started = time.perf_counter()
    raw = {'schema_version': 1, 'epoch': 27, 'phase': 'dev', 'diagnostic_only': True,
        'source_checkpoint': C.SOURCE, 'plan_sha256': args.expected_plan_sha, 'status': 'INITIALIZING',
        'cases': [], 'errors': [], 'accuracy': None, 'proper_scores': None,
        'benchmark_acceptance': False, 'champion_promoted': False, 'training_lineage': 'official facebook/bart-large-mnli MNLI-trained head, 2020; later selection and foundation text overlap unknown',
        'scope': '24 real licensed ContractNLI DEV-only diagnostic cases; no confirmation, fit, promotion or generalization claim.',
        'started_at': datetime.now(timezone.utc).isoformat(), 'worker_pid': os.getpid(),
        'worker_pgid': os.getpgid(0),
        'counters': {**dict.fromkeys(ZERO + COUNTED, 0), 'BGE_forward_seconds': 0.0}}
    fd = os.open(args.out / 'progress.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def progress(event):
        memory = {}
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                name, value, unit = line.split()
                memory[name.rstrip(':') + '_bytes'] = int(value) * 1024
        row = {'at_unix': time.time(), 'elapsed_seconds': time.perf_counter() - started,
               'worker_pid': os.getpid(), 'event': event, 'counters': dict(raw['counters']), 'memory': memory}
        payload = (json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        view = memoryview(payload)
        while view:
            size = os.write(fd, view)
            if size <= 0:
                raise RuntimeError('Cannot write durable progress')
            view = view[size:]
        os.fsync(fd)

    guard_module = C.load_module('epoch27_offline_policy', HERE / 'network_guard.py')
    offline = guard_module.OfflineGuard(raw['counters'], progress).install()
    code = 0
    progress({'event': 'WORKER_STARTED_NO_MODEL_INITIALIZED'})
    try:
        if not 0 < C.remaining(args.deadline) <= 600 or sorted(os.sched_getaffinity(0)) != [0, 1]:
            raise ValueError('Exact CPU0/1 affinity and finite process deadline required')
        # Verify actual remote admission BEFORE hashing any pinned DEV input bytes.
        if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
            raise ValueError('Unrecognized external plan identity')
        provisional = C.read(args.plan)
        admission, owner = C.verify_admission(args.admission, provisional, args.expected_plan_sha)
        plan, pins = C.require_plan(args.plan, args.expected_plan_sha)
        raw.update(admission=admission, owner_lock=owner, roles_used=plan['benchmark_roles'])
        raw['remote_admission_verified_before_DEV_read'] = True
        assets, versions, reader_module = C.verify_assets(plan)
        raw.update(runtime_assets=assets, python_versions=versions,
            input_bank_sha256=plan['inputs_sha256'], source_freeze_sha256=plan['source_freeze_sha256'])
        attempt_path = args.out / 'attempt.json'
        while not attempt_path.exists():
            C.remaining(args.deadline)
            if time.perf_counter() - started > 5:
                raise ValueError('Outer launcher did not seal exact worker identity')
            time.sleep(.01)
        attempt, current = C.read(attempt_path), C.proc(os.getpid())
        if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpid()
                or attempt.get('sid') != os.getpid() or attempt.get('startticks') != current['ticks']
                or current['pgid'] != os.getpid() or current['sid'] != os.getpid()):
            raise ValueError('Exact worker PID/startticks/process-session ownership required')
        raw['preparation_seconds'] = time.perf_counter() - started
        progress({'event': 'ADMISSION_ALL_PINS_AND_EXACT_OWNER_VERIFIED'})
        raw['counters']['DEV_input_bank_reads'] += 1
        bank = C.read(C.checked(plan['inputs_path']))
        perform(raw, plan, reader_module, bank, args.out, args, progress, offline)
        C.owner_lock(admission)
        C.remaining(args.deadline)
        offline.assert_clean()
        if any(raw['counters'][key] for key in ZERO):
            raise ValueError('Forbidden operation counter nonzero')
    except BaseException as error:
        raw['status'] = 'FAILED_DEV_DIAGNOSTIC_PROCESS'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error)})
        code = 2
    finally:
        raw.update(wall_seconds_including_initialization_cleanup=time.perf_counter() - started,
            resources=resources(), completed_at=datetime.now(timezone.utc).isoformat(),
            Python_network_events=offline.events, Python_network_violations=offline.violations)
        raw['allowed_local_bind_events'] = [event for event in offline.events if event['allowed']]
        progress({'event': 'WORKER_FINAL', 'status': raw['status'], 'errors': raw['errors']})
        C.put(args.out / 'raw.json', raw, compact=True)
        os.close(fd)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
