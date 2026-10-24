"""One admitted BGE/native document-identity engineering worker; no NLI/fit."""
import argparse
import hashlib
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
import traceback

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('epoch29_identity_runtime', HERE / 'runtime/common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
V = C.load_module('epoch29_lossless_vectors', HERE / 'vector_codec.py')
BANK_SHA = 'ced6f3969f72f4f07da570f42ed62d439e5db1b440393688e8496acde731f4c3'
POSITIVE = {
    **{key: 1 for key in ('BGE_initializations_attempted', 'BGE_initializations_completed',
        'ORT_sessions_attempted', 'ORT_sessions_completed', 'tokenizer_initializations_attempted',
        'tokenizer_initializations_completed', 'native_helper_starts_attempted', 'native_helper_starts_completed',
        'native_binary_loads_attempted', 'native_binary_loads_completed',
        'native_index_initializations_attempted', 'native_index_initializations_completed',
        'native_version_calls_attempted', 'native_version_calls_completed')},
    **{key: 33 for key in ('tokenizer_full_encoding_calls_attempted', 'tokenizer_full_encoding_calls_completed',
        'tokenizer_capped_encoding_calls_attempted', 'tokenizer_capped_encoding_calls_completed',
        'BGE_forward_calls_attempted', 'BGE_forward_calls_completed')},
    **{key: 262 for key in ('tokenizer_full_texts_attempted', 'tokenizer_full_texts_completed',
        'tokenizer_capped_texts_attempted', 'tokenizer_capped_texts_completed', 'BGE_texts_attempted',
        'BGE_texts_completed', 'native_queries_attempted', 'native_queries_completed',
        'dense_queries_attempted', 'dense_queries_completed', 'document_records_completed', 'query_records_completed')},
    'native_insertions_attempted': 261, 'native_insertions_completed': 261,
    'native_len_calls_attempted': 2, 'native_len_calls_completed': 2,
    'dense_cosines_attempted': 68121, 'dense_cosines_completed': 68121,
    'native_hits_retained': 4192, 'dense_hits_retained': 4192, 'native_hit_source_validations': 4453}


def status(pid):
    result, observed, races = {}, [], []
    try:
        for line in Path('/proc/' + str(pid) + '/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                name, value, _unit = line.split()
                result[name.rstrip(':') + '_bytes'] = int(value) * 1024
            elif line.startswith(('Threads:', 'Cpus_allowed_list:', 'NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:')):
                key, value = line.split(':', 1)
                result[key] = value.strip()
        tasks = list((Path('/proc') / str(pid) / 'task').iterdir())
    except FileNotFoundError:
        tasks = []
    for task in sorted(tasks, key=lambda path: int(path.name)):
        try:
            for line in (task / 'status').read_text().splitlines():
                if line.startswith('Cpus_allowed_list:'):
                    literal = line.split(':', 1)[1].strip()
                    cpus = set()
                    for item in literal.split(','):
                        ends = item.split('-')
                        cpus.update(range(int(ends[0]), int(ends[-1]) + 1))
                    observed.append({'tid': int(task.name), 'Cpus_allowed_list': literal,
                        'observed_affinity_within_CPU0_1': bool(cpus) and cpus <= {0, 1}})
                    break
        except FileNotFoundError:
            races.append(int(task.name))
    result.update(observed_thread_affinities=observed, thread_status_disappearance_races=races,
        observability_scope='Current read-only task snapshots; total OS threads need not equal2.')
    if any(not row['observed_affinity_within_CPU0_1'] for row in observed):
        error = RuntimeError('Observed thread outside kernel CPU0,1 policy')
        error.observed_process_status = result
        raise error
    return result


def atomic_checkpoint(raw, out):
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
    try:
        pending = out / 'raw.partial.pending.json'
        with pending.open('x', encoding='utf-8') as target:
            json.dump(raw, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
        os.replace(pending, out / 'raw.partial.json')
        directory = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def node_receipts(out, counters, *, fatal=True):
    path = out / 'node-progress.jsonl'
    rows = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if rows:
            for key in ('Node_network_operations_attempted', 'native_binary_loads_attempted', 'native_binary_loads_completed'):
                counters[key] = rows[-1][key]
    if fatal and counters['Node_network_operations_attempted']:
        raise RuntimeError('Persistent native public-network-API violation')
    return rows


def loaded_onnx_libraries(lock):
    members = C.read(C.checked(lock['wheel_members_reference_path']))
    allowed = {str(C.ROOT / 'retrieval/.venv' / row['path']): row for row in members}
    paths = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
             if line.split() and line.split()[-1].startswith('/')}
    observed = []
    for name in sorted(paths):
        if '.so' not in name or not any(marker in name for marker in ('onnxruntime', 'numpy', 'tokenizers')):
            continue
        row = allowed.get(name)
        if row is None or Path(name).stat().st_size != row['bytes'] or C.sha(Path(name)) != row['sha256']:
            raise ValueError('Actual loaded BGE runtime library differs from pinned installed wheel member')
        observed.append({'path': str(Path(name).relative_to(C.ROOT)), 'bytes': row['bytes'], 'sha256': row['sha256']})
    if not any('onnxruntime_pybind11_state' in row['path'] for row in observed):
        raise ValueError('Actual original ONNX CPU binding was not observed mapped')
    return observed


def native(bundle, out, args, raw, progress):
    counters = raw['counters']
    source, target = out / 'native-bundle.json', out / 'native-result.json'
    C.put(source, bundle)
    raw['vector_bundle'] = {'path': str(source.relative_to(C.ROOT)), 'bytes': source.stat().st_size, 'sha256': C.sha(source)}
    process = identity = None
    stdout = stderr = b''
    with tempfile.TemporaryDirectory(prefix='ruvector-e29-identity-', dir=C.ROOT.parent) as scratch:
        raw['native_scratch'] = {'path': scratch, 'outside_public_project': True}
        command = ['node', '--require=' + str(HERE / 'runtime/node_guard.cjs'),
            str(HERE / 'native_identity.cjs'), str(source), str(target)]
        counters['native_helper_starts_attempted'] += 1
        progress({'event': 'NATIVE_HELPER_POPEN_BEFORE', 'argv': command})
        started = time.perf_counter()
        try:
            # The entire Python worker was kernel-pinned before exec. This child
            # inherits that seccomp policy; no second sched_setaffinity is used.
            process = subprocess.Popen(command, cwd=scratch, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            counters['native_helper_starts_completed'] += 1
            identity = C.proc(process.pid)
            if not identity or identity['pgid'] != os.getpgrp() or identity['sid'] != os.getsid(0):
                raise ValueError('Native helper escaped exact owned worker session')
            C.put(out / 'native-attempt.json', {'pid': process.pid, 'identity': identity, 'argv': command,
                'bundle_sha256': C.sha(source), 'source_sha256': C.sha(HERE / 'native_identity.cjs'),
                'CPU_policy': 'Inherited whole-Python-worker seccomp/NNP; no additional affinity rewrite'})
            stdout, stderr = process.communicate(timeout=min(60, C.remaining(args.deadline)))
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.output or b'', error.stderr or b''
            raise
        finally:
            if process is not None and process.poll() is None:
                current = C.proc(process.pid)
                if not identity or not current or current['ticks'] != identity['ticks']:
                    raise RuntimeError('Cannot prove exact native child PID/ticks for cleanup')
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate(timeout=1)
            (out / 'native.stdout').write_bytes(stdout)
            (out / 'native.stderr').write_bytes(stderr)
            raw['native_child_closed'] = process is None or process.poll() is not None
            raw['native_child_exit_code'] = process.returncode if process is not None else None
            raw['Node_guard_events'] = node_receipts(out, counters, fatal=False)
            log = out / 'native-progress.jsonl'
            if log.exists():
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                if rows:
                    for key, value in rows[-1].items():
                        if key.startswith('native_') and type(value) is int:
                            counters[key] = value
            raw['native_helper_wall_seconds'] = time.perf_counter() - started
            files = []
            for path in sorted(Path(scratch).rglob('*')):
                C.no_symlink(path)
                if path.is_file():
                    files.append({'path': str(path.relative_to(scratch)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)})
            raw['native_scratch']['files_before_owned_cleanup'] = files
        if process.returncode != 0:
            failure = Path(str(target) + '.failure.json')
            if failure.exists():
                raw['native_failure_ref'] = {'path': str(failure.relative_to(C.ROOT)), 'bytes': failure.stat().st_size, 'sha256': C.sha(failure)}
            raise RuntimeError('Actual native identity helper failed; complete stderr/failure receipt retained')
    raw['native_scratch']['removed_after_child_exit'] = not Path(scratch).exists()
    result = C.read(target)
    raw['native_result'] = {'path': str(target.relative_to(C.ROOT)), 'bytes': target.stat().st_size, 'sha256': C.sha(target)}
    if (result.get('kind') != C.KIND or result.get('epoch') != 29 or result.get('native') is not True
            or result.get('bundle_sha256') != C.sha(source) or result.get('native_binary_sha256') != C.BINARY_SHA
            or result.get('package_version') != '0.1.33' or result.get('platform_package_version') != '0.1.31'
            or result.get('binary_version') != '2.3.0' or result.get('helper_pid') != process.pid
            or result.get('compact_schema') != 'epoch29-native-document-identity-f32le-v1'
            or len(result['queries']) != 262):
        raise ValueError('Actual source/native/bundle version receipt mismatch')
    for key, value in result.items():
        if key.startswith('native_') and type(value) is int:
            counters[key] = value
    node_receipts(out, counters)
    progress({'event': 'NATIVE_HELPER_CLOSED', 'helper_pid': process.pid})
    return result


def perform(raw, plan, args, progress, offline, runtime):
    counters = raw['counters']
    path = C.checked(plan['engineering_inputs_path'])
    if plan['engineering_inputs_sha256'] != BANK_SHA or C.sha(path) != BANK_SHA:
        raise ValueError('Wrong fixed document-identity bank')
    bank = C.read(path)
    if (bank.get('epoch') != 29 or bank.get('kind') != C.KIND
            or bank.get('normalization') != 'casefold+split/join whitespace'
            or bank.get('roles') != {'train': [], 'dev': [], 'calibration': [], 'confirmation': []}
            or len(bank['documents']) != 261 or bank['query']['document_id'] != 548
            or bank['excluded_protected_alias_document_ids'] != []):
        raise ValueError('Only exact old-exposed261 plus retired known query548 allowed')
    rows = bank['documents'] + [bank['query']]
    corpus_ids = [row['document_id'] for row in bank['documents']]
    if (corpus_ids != sorted(set(corpus_ids)) or 548 in corpus_ids
            or set(corpus_ids + [548]) & set(bank['protected_document_ids'])):
        raise ValueError('Protected or repeated document entered model input bank')
    texts = []
    for offset, row in enumerate(rows):
        if set(row) != {'document_id', 'normalized_text', 'normalized_document_sha256',
                'source_document_sha256', 'source_utf8_bytes', 'bge_input_sha256', 'bge_input_utf8_bytes'}:
            raise ValueError('Unexpected field in document-only engineering record')
        text = row['normalized_text']
        model_text = V.bge_text(text)
        if (not isinstance(text, str) or not text or text != ' '.join(text.casefold().split())
                or V.text_sha(text) != row['normalized_document_sha256']
                or V.text_sha(model_text) != row['bge_input_sha256']
                or len(model_text.encode('utf-8')) != row['bge_input_utf8_bytes']):
            raise ValueError('Authoritative full normalized hash or separate BGE canonical input changed')
        texts.append(model_text)
        raw['documents'].append({key: row[key] for key in row if key != 'normalized_text'})
        raw['documents'][-1].update(vector_row=offset,
            normalized_text_input_ref={'path': plan['engineering_inputs_path'], 'sha256': BANK_SHA,
                'document_id': row['document_id']})
    raw['source_bank'] = {'path': plan['engineering_inputs_path'], 'bytes': path.stat().st_size, 'sha256': BANK_SHA,
        'source_sha256': bank['source_sha256'], 'authoritative_normalization': bank['normalization'],
        'model_input_canonicalization': 'NFKC(authoritative normalized_text).casefold(); whitespace separators preserved',
        'protected_document_ids': bank['protected_document_ids'], 'excluded_protected_alias_document_ids': []}
    raw['engineering_input_bank_reads'] = 1
    progress({'event': 'ALL_ENGINEERING_DOCUMENT_IDENTITIES_VALIDATED_BEFORE_MODEL'})
    encoder_module = C.load_module('epoch29_admitted_document_bge', HERE / 'bge_encoder.py')
    started = time.perf_counter()
    encoder = encoder_module.DocumentEncoder(C.ROOT, counters, progress)
    raw['BGE'] = dict(encoder.receipt, initialization_seconds=time.perf_counter() - started)
    raw['actual_loaded_BGE_runtime_libraries'] = loaded_onnx_libraries(runtime)
    def completed(offset, diagnostic):
        raw['documents'][offset].update(diagnostic)
        counters['document_records_completed'] += 1
    payload = encoder.encode(texts, completed)
    offline.assert_clean()
    document_ids = corpus_ids + [548]
    block = V.encode_matrix(payload, len(document_ids))
    actual_bytes, vectors = V.decode_matrix(block)
    if actual_bytes != payload:
        raise ValueError('Actual model vector bits changed during lossless encoding')
    for offset, (row, vector) in enumerate(zip(raw['documents'], vectors)):
        expected = hashlib.sha256(payload[offset * 1536:(offset + 1) * 1536]).hexdigest()
        if row['vector_sha256'] != expected or len(vector) != 384:
            raise ValueError('Actual model row and lossless vector digest differ')
    bundle = {'schema_version': 3, 'epoch': 29, 'kind': C.KIND,
        'vector_encoding': 'base64_float32le_c_order', 'document_ids': document_ids,
        'corpus_document_ids': corpus_ids, 'vectors': block,
        'provenance': [{key: row[key] for key in ('document_id', 'source_document_sha256',
            'normalized_document_sha256', 'bge_input_sha256')} for row in raw['documents']]}
    result = native(bundle, args.out, args, raw, progress)
    for offset, (row, observed) in enumerate(zip(rows, result['queries'])):
        C.remaining(args.deadline)
        document_id = row['document_id']
        exclude = document_id if document_id in corpus_ids else None
        if observed['document_id'] != document_id or observed['exclude_document_id'] != exclude:
            raise ValueError('Native result mapped to another input document')
        record = {'query_id': 'document:' + str(document_id), 'document_id': document_id,
            'exclude_document_id': exclude, 'normalized_document_sha256': row['normalized_document_sha256'],
            'native': observed, 'dense': None}
        raw['queries'].append(record)
        counters['dense_queries_attempted'] += 1
        progress({'event': 'EXACT_DENSE_COSINE_BEFORE', 'document_id': document_id})
        started = time.perf_counter()
        top, count = V.dense_top16(vectors[offset], corpus_ids, vectors[:261], exclude, counters)
        counters['dense_queries_completed'] += 1
        counters['dense_hits_retained'] += len(top)
        record['dense'] = {'top16': top, 'candidate_count': count,
            'elapsed_seconds': time.perf_counter() - started,
            'method': 'math.fsum float64 cosine of exact float32 input bits; self excluded before dots; numeric document ID tie'}
        aliases = [item['document_id'] for item in bank['documents']
            if item['document_id'] != exclude and item['normalized_document_sha256'] == row['normalized_document_sha256']]
        ann_hits = [value for value in observed['filtered_top16_ids'] if value in aliases]
        dense_hits = [value['document_id'] for value in top if value['document_id'] in aliases]
        record.update(authoritative_alias_document_ids=aliases,
            native_confirmed_alias_ids=ann_hits, dense_confirmed_alias_ids=dense_hits,
            native_status='CONFIRMED_NORMALIZED_ALIAS' if ann_hits else 'UNRESOLVED',
            dense_status='CONFIRMED_NORMALIZED_ALIAS' if dense_hits else 'UNRESOLVED', near_pairs=[])
        counters['query_records_completed'] += 1
        offline.assert_clean()
        progress({'event': 'DOCUMENT_IDENTITY_QUERY_COMPLETED', 'document_id': document_id})
    raw['status'] = 'COMPLETED_NATIVE_DOCUMENT_IDENTITY_AWAITING_INDEPENDENT_REPLAY'


def main():
    parser = argparse.ArgumentParser()
    for key in ('plan', 'admission', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    if args.out.absolute() != C.STUDY / 'runs/engineering' or args.out.resolve() != args.out.absolute():
        raise ValueError('Unsafe document-identity output directory')
    C.no_symlink(args.out)
    started = time.monotonic()
    raw = {'schema_version': 1, 'epoch': 29, 'kind': C.KIND, 'source_checkpoint': C.SOURCE,
        'status': 'INITIALIZING', 'plan_sha256': args.expected_plan_sha,
        'worker_pid': os.getpid(), 'worker_identity': C.proc(os.getpid()),
        'documents': [], 'queries': [], 'errors': [], 'vector_bundle': None, 'native_result': None,
        'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []},
        'benchmark_generalization_claim': False, 'benchmark_accuracy': None, 'benchmark_NLL': None,
        'benchmark_Brier': None, 'proper_metric_computations': 0, 'champion_promoted': False,
        'held_parameter_adaptation': 'Original E29 TRAIN/DEV allocation remains HOLD, all16 IDs retired; this engineering task does not resume that fit.',
        'identity_policy': 'Exact full normalized hash is authoritative. ANN/dense misses are UNRESOLVED, never CLEAN. The one known positive is finite engineering evidence, not general recall.',
        'internal_scope': 'Genuine BGE-small 256-token CLS embeddings and original native2.3.0 cosine index. Full-document hashing is not full-document token attention. No NLI/Torch/fits.',
        'counters': {**dict.fromkeys(C.ZERO, 0), **dict.fromkeys(POSITIVE, 0),
            'BGE_truncated_texts': 0, 'native_self_hits_observed': 0, 'BGE_forward_seconds': 0.0}}
    stream = (args.out / 'progress.jsonl').open('xb')
    def progress(event):
        line = {'at_unix': time.time(), 'elapsed_seconds': time.monotonic() - started,
            'event': event, 'counters': dict(raw['counters']), 'process': status(os.getpid())}
        stream.write((json.dumps(line, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
        atomic_checkpoint(raw, args.out)
    offline = C.load_module('epoch29_python_network_policy', HERE / 'runtime/network_guard.py').OfflineGuard(raw['counters'], progress).install()
    def stop(signum, frame):
        raise TimeoutError('Bounded document-identity stop signal: ' + str(signum))
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGALRM, stop)
    code = 0
    try:
        C.remaining(args.deadline)
        signal.setitimer(signal.ITIMER_REAL, max(.001, C.remaining(args.deadline) - 7))
        observed = status(os.getpid())
        if (os.sched_getaffinity(0) != {0, 1} or observed.get('NoNewPrivs') != '1' or observed.get('Seccomp') != '2'):
            raise ValueError('Whole-worker kernel CPU0,1/NNP/seccomp required before ORT import')
        if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
            raise ValueError('Unknown exact source plan identity')
        provisional = C.read(args.plan)
        admission, owner = C.admission(args.admission, provisional, args.expected_plan_sha)
        plan = C.verify_plan(args.plan, args.expected_plan_sha)
        runtime = C.verify_runtime(plan)
        if any(plan['expected_operation_counters'].get(key) != value for key, value in POSITIVE.items()):
            raise ValueError('Plan does not bind the exact fixed document-identity operation counts')
        attempt = args.out / 'attempt.json'
        while not attempt.exists():
            C.remaining(args.deadline)
            if time.monotonic() - started > 10:
                raise ValueError('Outer exact worker identity was not sealed')
            time.sleep(.01)
        identity, current = C.read(attempt), C.proc(os.getpid())
        if (identity.get('pid') != os.getpid() or identity.get('pgid') != os.getpid()
                or identity.get('sid') != os.getpid() or identity.get('startticks') != current['ticks']
                or current['pgid'] != os.getpid() or current['sid'] != os.getpid()):
            raise ValueError('Exact owned worker PID/ticks/session missing')
        cpu_path = args.out / 'worker-cpu-preexec.json'
        raw.update(admission=admission, owner_lock=owner, runtime_assets=runtime,
            source_freeze_sha256=plan['source_freeze_sha256'], CPU_policy_before_ORT=observed,
            worker_cpu_guard_preexec=C.read(cpu_path),
            worker_cpu_guard_preexec_artifact={'path': str(cpu_path.relative_to(C.ROOT)),
                'bytes': cpu_path.stat().st_size, 'sha256': C.sha(cpu_path)})
        progress({'event': 'ALL_SOURCE_RUNTIME_OWNER_AND_CPU_GATES_BEFORE_ORT'})
        perform(raw, plan, args, progress, offline, runtime)
        C.verify_plan(args.plan, args.expected_plan_sha)
        C.verify_runtime(plan)
        C.owner_lock(admission)
        C.remaining(args.deadline)
        offline.assert_clean()
        if any(name in sys.modules for name in ('torch', 'transformers')):
            raise RuntimeError('Unrequested Torch/NLI import occurred')
        if any(raw['counters'][key] != value for key, value in POSITIVE.items()) or any(raw['counters'][key] for key in C.ZERO):
            raise ValueError('Exact genuine BGE/native/dense/zero-forbidden count closure failed')
        if raw['errors'] or not raw.get('native_child_closed'):
            raise ValueError('Native child cleanup or raw errors remain')
    except BaseException as error:
        raw['status'] = 'FAILED_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()})
        if hasattr(error, 'observed_process_status'):
            raw['CPU_affinity_violation_snapshot'] = error.observed_process_status
        code = 2
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        raw.update(completed_at=datetime.now(timezone.utc).isoformat(),
            wall_seconds_including_initialization_cleanup=time.monotonic() - started,
            Python_network_violations=offline.violations,
            resources={'CPU_affinity': sorted(os.sched_getaffinity(0)), 'worker': status(os.getpid()),
                'worker_user_seconds': own.ru_utime, 'worker_system_seconds': own.ru_stime,
                'worker_peak_RSS_bytes': own.ru_maxrss * 1024, 'child_user_seconds': child.ru_utime,
                'child_system_seconds': child.ru_stime, 'largest_child_peak_RSS_bytes': child.ru_maxrss * 1024,
                'memory_scope': 'Separate observed high-water values, not aggregate simultaneous RSS.'})
        try:
            progress({'event': 'WORKER_FINAL', 'status': raw['status'], 'errors': raw['errors']})
        except BaseException as error:
            raw['status'] = 'FAILED_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
            raw['errors'].append({'stage': 'final_progress_checkpoint', 'type': type(error).__name__, 'message': str(error)})
            code = 2
        pending = args.out / 'raw.partial.pending.json'
        if pending.is_file():
            raw['leftover_partial_checkpoint'] = {'path': str(pending.relative_to(C.ROOT)),
                'bytes': pending.stat().st_size, 'sha256': C.sha(pending), 'retained_without_overwrite': True}
        C.put(args.out / 'raw.json', raw)
        stream.close()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
