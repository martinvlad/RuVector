"""One source-admitted CPU2 corpus batch, native retrieval and 36 typed NLI forecasts."""
import argparse
import base64
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
KIND = 'REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT'
ARMS = ('native', 'lexical', 'source_order')
LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
BGE_PREFIX = 'Represent this sentence for searching relevant passages: '


def require(value, code):
    if not value:
        raise ValueError(code)


def no_symlink(path):
    path = Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
            'ABSOLUTE_NONSYMLINK_PATH_REQUIRED')
    return path


def verify_file(ref):
    require(type(ref) is dict and type(ref.get('bytes')) is int
            and re.fullmatch(r'[0-9a-f]{64}', ref.get('sha256', '')), 'EXACT_FILE_REFERENCE')
    path = no_symlink(ref['path']); require(path.is_file(), 'REFERENCE_REGULAR_FILE')
    require(path.stat().st_size == ref['bytes'], 'REFERENCE_BYTE_SIZE')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            digest.update(block)
    require(digest.hexdigest() == ref['sha256'], 'REFERENCE_SHA256')
    return path


def parse_ref(ref):
    return json.loads(verify_file(ref).read_bytes())


def put(path, value):
    path = no_symlink(path); data = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    f = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        require(os.write(f, data) == len(data), 'COMPLETE_RESULT_WRITE'); os.fsync(f)
    finally:
        os.close(f)
    d = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY); os.fsync(d); os.close(d)
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def proc(pid):
    p = Path('/proc') / str(pid)
    try:
        f = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'startticks': int(f[19]), 'state': f[0],
                'pgid': int(f[2]), 'sid': int(f[3])}
    except FileNotFoundError:
        return None


def admit(args):
    require(sorted(os.sched_getaffinity(0)) == [0, 1], 'EXACT_CPU_AFFINITY')
    pp = no_symlink(args.plan); require(pp.stat().st_size <= 1048576, 'PLAN_BYTE_CAP')
    pb = pp.read_bytes(); require(hashlib.sha256(pb).hexdigest() == args.expected_plan_sha256,
                                 'FROZEN_PLAN_SHA256')
    plan = json.loads(pb); require(plan['schema_version'] == 1 and plan['epoch'] == 48
                                  and plan['kind'] == KIND, 'PLAN_KIND_EPOCH')
    require(plan['dataset_revision'] == 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
            'EXACT_DATASET_REVISION')
    ap = no_symlink(args.admission); ab = ap.read_bytes()
    require(hashlib.sha256(ab).hexdigest() == args.expected_admission_sha256,
            'ROOT_SCI_ADMISSION_SHA256')
    a = json.loads(ab)
    require(a['schema_version'] == 1 and a['epoch'] == 48 and a['kind'] == KIND
            and a['phase'] == args.phase and a['allowed'] is True
            and a['plan_sha256'] == args.expected_plan_sha256
            and re.fullmatch(r'[0-9a-f]{40}', a['source_commit'])
            and re.fullmatch(r'[0-9a-f]{64}', a['source_freeze_sha256'])
            and re.fullmatch(r'[0-9a-f]{64}', a['worker_slot_token'])
            and a['native_batch_ordinal'] == (1 if args.phase == 'dev' else 2),
            'ROOT_EXACT_PHASE_SCI_ADMISSION')
    source_refs = a['source_files']; require(type(source_refs) is list and source_refs,
                                            'SOURCE_FILES_REQUIRED')
    names = set()
    for ref in source_refs:
        p = verify_file(ref)
        if p.parent == HERE:
            names.add(p.name)
    require({'worker.py', 'reader.py', 'packing.py', 'native_helper.cjs'} <= names,
            'ALL_RUNTIME_SOURCE_FILES_FROZEN')
    owner = parse_ref(a['owner']); current = proc(owner['pid'])
    require(owner['epoch'] == 48 and owner['generation'] == 13 and current
            and current['startticks'] == owner['startticks'] and current['state'] not in ('Z', 'X')
            and time.time() < owner['expires_unix'], 'CURRENT_SCOPED_OWNER')
    lock = os.stat(owner['lock']); fd = os.stat(Path('/proc') / str(owner['pid']) / 'fd/3')
    require((lock.st_dev, lock.st_ino) == (fd.st_dev, fd.st_ino)
            == (owner['lock_device'], owner['lock_inode']), 'ORIGINAL_LOCK_INODE')
    info = (Path('/proc') / str(owner['pid']) / 'fdinfo/3').read_text()
    require('FLOCK' in info and str(owner['pid']) in info and ':' + str(owner['lock_inode']) in info,
            'CURRENT_OWNER_KERNEL_FLOCK')
    data = parse_ref(a['data_admission'])
    require(data['epoch'] == 48 and data['kind'] == KIND and data['phase'] == args.phase
            and data['plan_sha256'] == args.expected_plan_sha256
            and data['source_freeze_sha256'] == a['source_freeze_sha256']
            and data['features'] == a['features'] and data['private_features'] == a['features']
            and data['status'] == 'READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT'
            and data['errors'] == [] and data['semantic_gold_values_decoded'] == 0,
            'DATA_ADMISSION_EXACT_FEATURE_BINDING')
    require(a['features']['bytes'] <= 8388608, 'FEATURE_BANK_BYTE_CAP')
    features = parse_ref(a['features'])
    if args.phase == 'confirmation':
        accept = parse_ref(a['independent_DEV_acceptance'])
        require(accept['checks_passed'] is True and accept['dev_passed'] is True
                and accept['plan_sha256'] == args.expected_plan_sha256,
                'CONF_REQUIRES_INDEPENDENT_FROZEN_DEV_ACCEPTANCE')
    return plan, a, features


def encode_block(matrix):
    require(matrix.ndim == 2 and matrix.shape[1] == 384 and 1 <= matrix.shape[0] <= 1024,
            'BGE_MATRIX_SHAPE')
    b = matrix.astype('<f4', copy=False).tobytes(order='C')
    return {'encoding': 'base64', 'dtype': 'float32le', 'shape': list(matrix.shape),
            'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
            'data_base64': base64.b64encode(b).decode('ascii')}


def embed_documents(plan, bank, counters, progress, deadline):
    for key in ('bge_model', 'bge_tokenizer'):
        verify_file(plan[key])
    for name in ('onnxruntime', 'tokenizers', 'numpy'):
        require(importlib.metadata.version(name) == plan['runtime_versions'][name],
                'BGE_RUNTIME_VERSION')
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    options = ort.SessionOptions(); options.intra_op_num_threads = 2; options.inter_op_num_threads = 1
    counters['BGE_initializations_attempted'] += 1; progress('BGE_INITIALIZE_BEFORE')
    started = time.monotonic()
    raw_tokenizer = Tokenizer.from_file(plan['bge_tokenizer']['path'])
    raw_tokenizer.no_padding(); raw_tokenizer.no_truncation()
    tokenizer = Tokenizer.from_file(plan['bge_tokenizer']['path'])
    tokenizer.enable_truncation(max_length=256, strategy='longest_first')
    tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
    session = ort.InferenceSession(plan['bge_model']['path'], sess_options=options,
                                  providers=['CPUExecutionProvider'])
    require(session.get_providers() == ['CPUExecutionProvider'], 'BGE_CPU_ONLY_PROVIDER')
    inputs = {x.name for x in session.get_inputs()}
    counters['BGE_initializations_completed'] += 1
    receipt = {'model_sha256': plan['bge_model']['sha256'],
               'tokenizer_sha256': plan['bge_tokenizer']['sha256'],
               'intra_op_threads': 2, 'inter_op_threads': 1, 'provider': 'CPUExecutionProvider',
               'explicit_embedding_only_truncation_cap': 256,
               'initialization_seconds': time.monotonic() - started}
    def embed(texts):
        vectors = []; audit = []
        for start in range(0, len(texts), 8):
            deadline(); batch = texts[start:start + 8]
            raw = raw_tokenizer.encode_batch(batch); used = tokenizer.encode_batch(batch)
            feed = {'input_ids': np.asarray([x.ids for x in used], dtype=np.int64),
                    'attention_mask': np.asarray([x.attention_mask for x in used], dtype=np.int64),
                    'token_type_ids': np.asarray([x.type_ids for x in used], dtype=np.int64)}
            counters['BGE_forward_calls_attempted'] += 1; counters['BGE_texts_attempted'] += len(batch)
            progress('BGE_FORWARD_BEFORE'); value = session.run(None, {k: v for k, v in feed.items()
                                                                     if k in inputs})[0][:, 0, :]
            require(value.shape == (len(batch), 384) and bool(np.isfinite(value).all()),
                    'ACTUAL_BGE_FINITE_OUTPUT')
            norms = np.linalg.norm(value, axis=1, keepdims=True); require(bool((norms > 0).all()),
                                                                       'BGE_NONZERO_OUTPUT')
            vectors.append((value / norms).astype(np.float32))
            counters['BGE_forward_calls_completed'] += 1; counters['BGE_texts_completed'] += len(batch)
            for text, full, actual in zip(batch, raw, used):
                consumed = [i for i, flag in zip(actual.ids, actual.attention_mask) if flag]
                require(len(consumed) <= 256, 'BGE_CONSUMED_TOKEN_CAP')
                audit.append({'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                              'full_token_count': len(full.ids), 'consumed_token_count': len(consumed),
                              'embedding_only_truncation': len(full.ids) > len(consumed)})
            progress('BGE_FORWARD_COMPLETE')
        return np.concatenate(vectors), audit
    bundle = {'schema_version': 1, 'epoch': 48, 'kind': KIND, 'phase': bank['role'],
              'plan_sha256': plan['_sha256'], 'documents': []}; audits = {}
    for doc in bank['documents']:
        group = [x for x in bank['cases'] if x['document_id'] == doc['document_id']]
        unit_vectors, unit_audit = embed([x['sentence'] for x in doc['evidence']])
        query_vectors, query_audit = embed([BGE_PREFIX + x['claim'] for x in group])
        bundle['documents'].append({'document_id': doc['document_id'],
                                    'vectors': encode_block(unit_vectors),
                                    'query_vectors': encode_block(query_vectors),
                                    'queries': [{'case_id': x['id']} for x in group]})
        audits[str(doc['document_id'])] = {'units': unit_audit, 'queries': query_audit}
    del session, tokenizer, raw_tokenizer; gc.collect(); deadline()
    return bundle, receipt, audits


def run_native(plan, bundle, external, counters, progress, deadline, state):
    verify_file(plan['node']); verify_file(plan['native_binary'])
    source = put(external / 'native-bundle.json', bundle)
    config = put(external / 'native-config.json', {k: v for k, v in plan.items() if k != '_sha256'})
    output = external / 'native-result.json'; identity = process = None
    counters['native_corpus_batches_attempted'] += 1; progress('NATIVE_HELPER_START_BEFORE')
    command = [plan['node']['path'], str(HERE / 'native_helper.cjs'), config['path'], source['path'], str(output)]
    started = time.monotonic(); stdout = stderr = b''
    state.update(command=command, child_closed=None, exit_code=None)
    try:
        process = subprocess.Popen(command, cwd=external, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        identity = proc(process.pid); require(identity and identity['pgid'] == os.getpgrp()
                                              and identity['sid'] == os.getsid(0), 'NATIVE_CHILD_SESSION')
        state['identity'] = identity
        stdout, stderr = process.communicate(timeout=min(60, deadline()))
    finally:
        if process is not None and process.poll() is None:
            current = proc(process.pid)
            require(current and identity and current['startticks'] == identity['startticks'],
                    'NATIVE_CLEANUP_OWNED_IDENTITY')
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); stdout, stderr = process.communicate(timeout=2)
        if process is not None:
            state.update(child_closed=process.poll() is not None, exit_code=process.returncode)
        (external / 'native.stdout').write_bytes(stdout); (external / 'native.stderr').write_bytes(stderr)
        state['wall_seconds'] = time.monotonic() - started
        progress_path = external / 'native-progress.jsonl'
        if progress_path.exists():
            lines = progress_path.read_text().splitlines()
            if lines:
                latest = json.loads(lines[-1]); counters.update(latest['counters'])
                state['last_native_counter_capture'] = latest
                state['inflight_native_call_outcome_uncertain'] = any(
                    counters.get(k, 0) != counters.get(k.replace('_attempted', '_completed'), 0)
                    for k in latest['counters'] if k.endswith('_attempted'))
        put(external / 'native-process-closure.json', state)
    require(process is not None and process.returncode == 0, 'NATIVE_HELPER_FAILED')
    value = json.loads(output.read_bytes())
    require(value['schema_version'] == 1 and value['epoch'] == 48 and value['kind'] == KIND
            and value['phase'] == bundle['phase'] and value['stage'] == 'COMPLETE'
            and value['errors'] == [] and value['bundle_sha256'] == source['sha256']
            and value['helper_source_sha256'] == hashlib.sha256((HERE / 'native_helper.cjs').read_bytes()).hexdigest()
            and value['plan_sha256'] == plan['_sha256'], 'NATIVE_COMPLETE_RECEIPT')
    insertions = sum(x['vectors']['shape'][0] for x in bundle['documents'])
    expected = {'native_index_initializations_attempted': 4, 'native_index_initializations_completed': 4,
                'native_insertions_attempted': insertions, 'native_insertions_completed': insertions,
                'native_queries_attempted': 12, 'native_queries_completed': 12,
                'native_len_calls_attempted': 8, 'native_len_calls_completed': 8,
                'native_hit_source_validations': insertions * 3,
                'native_binary_loads_attempted': 1, 'native_binary_loads_completed': 1,
                'native_version_calls_attempted': 1, 'native_version_calls_completed': 1,
                'Node_network_operations_attempted': 0}
    require(all(value.get(k) == v for k, v in expected.items()), 'NATIVE_EXACT_COUNTERS')
    counters.update(expected); counters['native_corpus_batches_completed'] += 1
    counters['native_corpus_batches'] += 1; progress('NATIVE_HELPER_COMPLETE')
    return value, state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True); parser.add_argument('--expected-plan-sha256', required=True)
    parser.add_argument('--phase', choices=['dev', 'confirmation'], required=True)
    parser.add_argument('--admission', required=True); parser.add_argument('--expected-admission-sha256', required=True)
    parser.add_argument('--output', required=True); parser.add_argument('--private-run-directory', required=True)
    parser.add_argument('--deadline-monotonic-seconds', type=float, required=True)
    args = parser.parse_args(); started = time.monotonic()
    require(math.isfinite(args.deadline_monotonic_seconds)
            and 0 < args.deadline_monotonic_seconds - started <= 570, 'BOUNDED_ABSOLUTE_SOFT_DEADLINE')
    for k, v in {'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
                 'NUMEXPR_NUM_THREADS': '2', 'TOKENIZERS_PARALLELISM': 'false', 'CUDA_VISIBLE_DEVICES': '',
                 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1'}.items():
        os.environ[k] = v
    external = no_symlink(args.private_run_directory); require(external.is_dir(), 'PRIVATE_RUN_DIRECTORY')
    out = no_symlink(args.output); require(out.parent.is_dir() and not out.exists(), 'ONCE_OUTPUT_PATH')
    counters = dict.fromkeys(['Python_network_operations_attempted', 'reader_initializations_attempted',
        'reader_initializations_completed', 'reader_pair_tokenizations', 'NLI_forwards_attempted',
        'NLI_forwards_completed', 'BGE_initializations_attempted', 'BGE_initializations_completed',
        'BGE_forward_calls_attempted', 'BGE_forward_calls_completed', 'BGE_texts_attempted',
        'BGE_texts_completed', 'native_corpus_batches_attempted', 'native_corpus_batches_completed',
        'native_corpus_batches', 'forecasts_completed', 'training_calls', 'calibration_calls',
        'paid_API_calls', 'GPU_calls', 'semantic_gold_decodes'], 0)
    def deny_network(event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo',
                     'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto',
                     'socket.sendmsg', 'urllib.Request', 'http.client.connect'):
            counters['Python_network_operations_attempted'] += 1
            raise RuntimeError('PYTHON_NETWORK_FORBIDDEN')
    sys.addaudithook(deny_network)
    def deadline():
        remaining = args.deadline_monotonic_seconds - time.monotonic()
        require(remaining > 0, 'WORKER_SOFT_DEADLINE')
        return remaining
    raw = {'schema_version': 1, 'epoch': 48, 'kind': KIND, 'phase': args.phase,
           'plan_sha256': args.expected_plan_sha256, 'status': 'PARTIAL_NO_GOLD', 'rows': [],
           'counters': counters, 'timing': {}, 'resources': {}, 'errors': [], 'source_pins': {},
           'loading_audit': {}, 'native_state': {}, 'BGE_runtime': {}, 'native_result': None,
           'score_semantics': 'Stable FP64 log_softmax of observed original FP32 learned-head logits; no clipping.',
           'timing_scope': 'Per-row packing plus forward only; whole batch includes source/hash/init/BGE/native/cleanup.'}
    progress_path = external / 'worker-progress.jsonl'
    progress_fd = os.open(progress_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    def progress(event):
        row = {'event': event, 'monotonic_seconds': time.monotonic(), 'counters': dict(counters)}
        os.write(progress_fd, (json.dumps(row, allow_nan=False) + '\n').encode()); os.fsync(progress_fd)
    reader = None; rc = 2
    try:
        deadline(); plan, admission, bank = admit(args); plan['_sha256'] = args.expected_plan_sha256
        raw['source_freeze_sha256'] = admission['source_freeze_sha256']
        raw['source_pins'] = {k: admission[k] for k in ('features', 'data_admission', 'source_commit',
                                                      'source_freeze_sha256', 'source_files', 'owner')}
        put(external / 'worker-attempt.json', {'schema_version': 1, 'epoch': 48, 'kind': KIND,
            'phase': args.phase, 'identity': proc(os.getpid()), 'worker_slot_token': admission['worker_slot_token'],
            'plan_sha256': args.expected_plan_sha256, 'started_monotonic_seconds': started,
            'deadline_monotonic_seconds': args.deadline_monotonic_seconds})
        sys.path.insert(0, str(HERE)); import packing
        role = plan['phase_roles'][args.phase]
        documents = packing.validate_features(bank, args.phase, role['document_ids'], role['case_ids'],
                                              plan['source_archive_sha256'])
        counters['feature_documents_admitted'] = 4; counters['feature_cases_admitted'] = 12
        bundle, raw['BGE_runtime'], raw['embedding_audit'] = embed_documents(plan, bank, counters, progress, deadline)
        native, _ = run_native(plan, bundle, external, counters, progress, deadline, raw['native_state'])
        raw['native_result'] = native
        observed = {q['case_id']: q for d in native['documents'] for q in d['queries']}
        from reader import Reader
        reader = Reader(plan, counters, progress, deadline, verify_file); raw['loading_audit'] = reader.audit
        for case in bank['cases']:
            doc, text = documents[case['document_id']]; units = doc['evidence']; query = observed[case['id']]
            orders = {'native': query['ids'], 'lexical': packing.bm25_order(units, case['claim']),
                      'source_order': list(range(len(units)))}
            for arm in ARMS:
                deadline(); before = time.monotonic()
                tokens, evidence = packing.pack(units, case['claim'], orders[arm], reader.tokenize)
                packing_seconds = time.monotonic() - before; value = reader.score(tokens)
                raw['rows'].append({'case_id': case['id'], 'document_id': case['document_id'],
                    'hypothesis_id': case['hypothesis_id'], 'arm': arm,
                    'probabilities': value['probabilities'], 'logits': value['logits'],
                    'log_probabilities': value['log_probabilities'], 'prediction': value['prediction'],
                    'elapsed_seconds': time.monotonic() - before, 'packing_seconds': packing_seconds,
                    'forward_seconds': value['forward_seconds'], 'evidence': evidence,
                    'native_query_seconds': query['elapsed_seconds'], 'input_sha256': case['input_sha256']})
                counters['forecasts_completed'] += 1; progress('FORECAST_COMPLETE')
                partial = external / 'raw.partial.json'; temp = external / 'raw.partial.next.json'
                with temp.open('x') as f:
                    json.dump(raw, f, sort_keys=True, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
                os.replace(temp, partial)
        require(counters['NLI_forwards_attempted'] == counters['NLI_forwards_completed']
                == counters['forecasts_completed'] == 36 and counters['native_corpus_batches'] == 1,
                'EXACT_COMPLETE_BATCH')
        require(counters['Python_network_operations_attempted'] == 0
                and counters['Node_network_operations_attempted'] == 0, 'NO_EXTERNAL_RUNTIME_NETWORK')
        deadline(); raw['status'] = 'FORECASTS_COMPLETE_NO_GOLD'; rc = 0
    except BaseException as error:
        message = str(error)
        raw['errors'].append({'type': type(error).__name__,
                              'code': message if re.fullmatch(r'[A-Z0-9_]{1,120}', message)
                              else 'WORKER_FAILED_PRIVATE_DIAGNOSTIC_RETAINED'})
        (external / 'worker.exception.txt').write_text(traceback.format_exc())
        progress('WORKER_FAILED')
    finally:
        if reader is not None:
            try:
                raw['reader_state'] = reader.close()
            except BaseException as error:
                raw['errors'].append({'type': type(error).__name__, 'code': 'READER_CLEANUP_FAILED'})
                raw['status'] = 'PARTIAL_NO_GOLD'; rc = 2
        usage = resource.getrusage(resource.RUSAGE_SELF); child = resource.getrusage(resource.RUSAGE_CHILDREN)
        raw['timing'] = {'wall_seconds_including_init_and_cleanup': time.monotonic() - started,
                         'started_monotonic_seconds': started, 'completed_monotonic_seconds': time.monotonic()}
        raw['resources'] = {'cpu_affinity': sorted(os.sched_getaffinity(0)), 'compute_threads': 2,
            'reader_torch_interop_threads': 1, 'worker_user_seconds': usage.ru_utime,
            'worker_system_seconds': usage.ru_stime, 'worker_max_rss_kib': usage.ru_maxrss,
            'children_max_rss_kib': child.ru_maxrss, 'children_user_seconds': child.ru_utime,
            'children_system_seconds': child.ru_stime,
            'scope': 'SELF excludes child CPU; CHILDREN RSS is largest child high-water, not sum.'}
        for name in ('memory.current', 'memory.peak'):
            p = Path('/sys/fs/cgroup') / name
            if p.exists():
                raw['resources']['shared_cgroup_' + name.replace('.', '_')] = int(p.read_text())
        raw['resources']['cgroup_scope'] = 'Shared cgroup; not candidate incremental use; peak may predate this run.'
        progress('WORKER_CLOSED'); os.close(progress_fd); put(out, raw)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
