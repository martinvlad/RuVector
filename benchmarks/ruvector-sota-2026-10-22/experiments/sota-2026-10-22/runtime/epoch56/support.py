"""E56 engineering support adapted from reviewed E53 worker; no initialization at import."""
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
from inherited_guards import HASH_CHUNK_BYTES, NetworkAudit, memory_snapshot, require_headroom
from native_accounting import NativeSnapshotLedger, expected_totals
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
    digest = hashlib.sha256(); descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(before.st_size == ref['bytes'], 'REFERENCE_BYTE_SIZE')
        count = 0
        while True:
            block = os.read(descriptor, HASH_CHUNK_BYTES)
            if not block: break
            count += len(block); digest.update(block)
        after = os.fstat(descriptor)
        require(count == ref['bytes'] and (before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino,
                after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'REFERENCE_UNCHANGED_DURING_STREAM_HASH')
    finally:
        os.close(descriptor)
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
    require(counters['BGE_initializations_attempted'] == 0, 'ONE_BGE_INITIALIZATION')
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
            require(counters['BGE_forward_calls_attempted'] < 64 and counters['BGE_texts_attempted'] + len(batch) <= 268, 'FROZEN_BGE_OPERATION_CAP')
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
    bundle = {'schema_version': 1, 'epoch': 56, 'kind': KIND, 'phase': bank['role'],
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
    output = external / 'native-result.json'; identity = process = value = None
    ledger = NativeSnapshotLedger(counters, expected_totals(plan, bundle))
    state.update(native_counter_accounting=ledger.receipt(),
                 inflight_native_call_outcome_uncertain=True,
                 native_progress_capture_path=str(external / 'native-progress.jsonl'))
    require(counters.get('native_corpus_batches_attempted',0) == 0, 'ONE_NATIVE_BATCH')
    counters['native_corpus_batches_attempted'] = counters.get('native_corpus_batches_attempted',0) + 1; progress('NATIVE_HELPER_START_BEFORE')
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
        state['transport_exception_active_at_capture'] = sys.exc_info()[0] is not None
        try:
            ledger.capture(external / 'native-progress.jsonl')
            state['last_native_counter_capture'] = ledger.last_row
            if (process is not None and process.returncode == 0
                    and not state['transport_exception_active_at_capture']):
                value = json.loads(output.read_bytes())
                require(value['schema_version'] == 1 and value['epoch'] == 56 and value['kind'] == KIND
                        and value['phase'] == bundle['phase'] and value['stage'] == 'COMPLETE'
                        and value['errors'] == [] and identity is not None
                        and value['helper_pid'] == identity['pid']
                        and value['bundle_sha256'] == source['sha256']
                        and value['helper_source_sha256'] == hashlib.sha256((HERE / 'native_helper.cjs').read_bytes()).hexdigest()
                        and value['plan_sha256'] == plan['_sha256'], 'NATIVE_COMPLETE_RECEIPT')
                ledger.finalize(value)
        except Exception as exc:
            code = str(exc)
            state['native_accounting_capture_error'] = {'type':type(exc).__name__,
                'code':code if re.fullmatch('[A-Z0-9_]{1,120}',code) else 'NATIVE_CAPTURE_VALIDATION_FAILED'}
        state['native_counter_accounting'] = ledger.receipt()
        state['inflight_native_call_outcome_uncertain'] = ledger.receipt()['inflight_native_call_outcome_uncertain']
        put(external / 'native-process-closure.json', state)
    require(process is not None and process.returncode == 0, 'NATIVE_HELPER_FAILED')
    require(state['native_counter_accounting']['qualified'] is True
            and state['inflight_native_call_outcome_uncertain'] is False,
            'NATIVE_PARENT_ACCOUNTING_QUALIFIED')
    # Expected totals are validation only: never add or fill them into Counter.
    counters['native_corpus_batches_completed'] = counters.get('native_corpus_batches_completed',0) + 1
    counters['native_corpus_batches'] = counters.get('native_corpus_batches',0) + 1; progress('NATIVE_HELPER_COMPLETE')
    return value, state

KIND = 'REAL_NATIVE_SOURCE_FRAGMENT_CAPACITY_QUALIFICATION'
BGE_PREFIX = 'Represent this sentence for searching relevant passages: '
HERE = Path(__file__).resolve().parent
