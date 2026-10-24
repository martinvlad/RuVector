"""Synthetic source/guard checks only; no DEV bank, ML or native imports."""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import re
import struct


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = args.project / 'experiments/sota-2026-10-22'
    candidate = base / 'candidate/epoch27'
    checks = []
    for path in sorted(candidate.rglob('*.py')):
        ast.parse(path.read_text(), filename=str(path))
    for path in sorted((base / 'epoch27/preparation').glob('*.py')):
        ast.parse(path.read_text(), filename=str(path))
    checks.append('all_owned_and_reader_python_AST_valid')
    subprocess.run(['node', '--check', str(candidate / 'native.cjs')], check=True)
    checks.append('native_helper_node_syntax_valid_without_import')
    compact_script = r'''
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const helper=require(process.argv[1]);
const vector=Array.from({length:384},(_,i)=>Math.fround((i-192)/1024));
const bytes=Buffer.alloc(1536);for(let i=0;i<384;i++)bytes.writeFloatLE(vector[i],i*4);
const block={encoding:'base64',dtype:'float32le',shape:[1,384],bytes:1536,
  sha256:crypto.createHash('sha256').update(bytes).digest('hex'),data_base64:bytes.toString('base64')};
const decoded=helper.decodeBlock(block,1);
assert.deepEqual(Array.from(decoded[0]),vector);
assert.throws(()=>helper.decodeBlock({...block,sha256:'a'.repeat(64)}));
assert.throws(()=>helper.decodeBlock({...block,shape:[2,384]}));
assert.throws(()=>helper.decodeBlock({...block,data_base64:block.data_base64+'!'}));
const signBytes=Buffer.from(bytes);signBytes.writeFloatLE(-0,0);
const signBlock={...block,data_base64:signBytes.toString('base64'),sha256:crypto.createHash('sha256').update(signBytes).digest('hex')};
assert.equal(Object.is(helper.decodeBlock(signBlock)[0][0],-0),true);
const hit={id:'0',score:0.875,vector:Object.fromEntries(vector.map((x,i)=>[String(i),x]))};
const compact=helper.compactHit(hit,[vector]);
assert.equal(compact.id,'0');assert.equal(compact.score,0.875);
assert.deepEqual(compact.raw_keys,['id','score','vector']);
assert.equal('vector' in compact,false);
assert.equal(compact.vector_receipt.dimensions,384);
assert.equal(compact.vector_receipt.sha256,compact.vector_receipt.source_sha256);
assert.equal(compact.metadata_receipt.present,false);
assert.equal(compact.metadata_receipt.sha256,crypto.createHash('sha256').update('{"present":false}').digest('hex'));
const wrong=structuredClone(hit);wrong.vector['2']=0;assert.throws(()=>helper.compactHit(wrong,[vector]));
const missing=structuredClone(hit);delete missing.vector['383'];assert.throws(()=>helper.compactHit(missing,[vector]));
const extra=structuredClone(hit);extra.vector.extra=0;assert.throws(()=>helper.compactHit(extra,[vector]));
for(const metadata of [null,{},false])assert.throws(()=>helper.compactHit({...hit,metadata},[vector]));
assert.throws(()=>helper.compactHit({...hit,id:'00'},[vector]));
assert.throws(()=>helper.compactHit({...hit,score:Infinity},[vector]));
const other=structuredClone(hit);other.vector['3']=0.1;assert.throws(()=>helper.compactHit(other,[vector]));
assert.equal(Object.keys(require.cache).some(p=>p.includes('ruvector.node')),false);
const dns=require('node:dns'),net=require('node:net');
const rejected=[()=>dns.lookup('example.invalid',()=>{}),()=>dns.resolveMx('example.invalid',()=>{}),
 ()=>dns.resolveTxt('example.invalid',()=>{}),()=>dns.resolveCaa('example.invalid',()=>{}),
 ()=>dns.promises.resolveTxt('example.invalid'),()=>new dns.Resolver().resolveMx('example.invalid',()=>{}),
 ()=>new dns.promises.Resolver().resolveTxt('example.invalid'),
 ()=>net.connect(1,'127.0.0.1'),()=>new net.Server().listen(0),
 ()=>require('node:dgram').createSocket('udp4'),()=>require('node:http').request('http://example.invalid'),
 ()=>require('node:https').request('https://example.invalid'),()=>fetch('https://example.invalid')];
const socket=new net.Socket();
rejected.push(()=>socket.write('synthetic'),()=>socket.read(1),()=>socket.end());
for(const operation of rejected){const before=helper.offlineDiagnostics().attempts;assert.throws(operation);assert.equal(helper.offlineDiagnostics().attempts,before+1);}
socket.destroy();
const policy=helper.offlineDiagnostics();assert.equal(policy.attempts,rejected.length);
assert.equal(policy.violations.length,rejected.length);assert.equal(policy.violations.every(v=>v.stack&&v.event),true);
process.stdout.write(JSON.stringify({vector_sha256:compact.vector_receipt.sha256,metadata_sha256:compact.metadata_receipt.sha256,native_imports:0,node_synthetic_denied:policy.attempts}));
'''
    compact = json.loads(subprocess.check_output(['node', '-e', compact_script,
        str(candidate / 'native.cjs')], text=True))
    exact = b''.join(struct.pack('<f', (i - 192) / 1024) for i in range(384))
    assert compact['vector_sha256'] == hashlib.sha256(exact).hexdigest()
    assert compact['metadata_sha256'] == hashlib.sha256(b'{"present":false}').hexdigest()
    assert compact['native_imports'] == 0
    checks.append('lossless_base64_f32le_decode_crosslanguage_digest_signed_zero_and_malformed_block_rejections')
    checks.append('compact_native_source_equality_f32le_digest_absent_metadata_and_malformed_rejections_no_native_import')
    checks.append('Node_callback_and_promise_Resolver_DNS_connect_send_recv_listen_HTTP_UDP_fetch_denied_persistent_stdout_retained')
    worker = load('static_epoch27_worker', candidate / 'worker.py')
    evidence = load('static_epoch27_evidence', candidate / 'evidence.py')
    network = load('static_epoch27_network', candidate / 'network_guard.py')
    checks.append('worker_import_is_ML_tokenizer_native_lazy')
    reader = load('static_epoch27_bart_reader', candidate / 'reader/bart_reader.py')
    assert reader.MODEL_REPOSITORY == 'facebook/bart-large-mnli'
    assert reader.MODEL_REVISION == 'd7645e127eaf1aefc7862fd59a17a5aa8558b8ce'
    checks.append('official_original_BART_reader_module_import_is_ML_tokenizer_lazy')
    assert not any(name in sys.modules for name in ('torch', 'transformers', 'tokenizers', 'onnxruntime', 'numpy'))
    class SyntheticMatrix:
        dtype = 'float32'
        shape = (1, 384)
        def astype(self, dtype, copy):
            assert dtype == '<f4' and copy is False
            return self
        def tobytes(self, order):
            assert order == 'C'
            return exact
    encoded = worker.vector_block(SyntheticMatrix())
    assert encoded['shape'] == [1, 384] and encoded['bytes'] == 1536
    assert encoded['sha256'] == compact['vector_sha256']
    import base64
    assert base64.b64decode(encoded['data_base64'], validate=True) == exact
    checks.append('worker_stores_actual_float32le_C_order_bytes_without_numeric_precision_change')
    text = 'Café signed -12.50 in 2024. It paid +.75 and −2,345.25, then 2025; also +0.5%.'
    matches = [m.group() for m in evidence.NUMBER.finditer(text)]
    assert matches == ['-12.50', '2024', '+.75', '−2,345.25', '2025', '+0.5'], matches
    receipt = evidence.provenance(text, text, {'selected_source_spans': [[0, len(text)]]})
    assert receipt['numeric_literals_retained'] == 6 and receipt['numeric_literals_omitted'] == 0
    assert receipt['selected_source_provenance'][0]['source_byte_end'] == len(text.encode('utf-8'))
    assert receipt['semantic_decision_override'] is False
    try:
        evidence.provenance(text, text.replace('2024', '2026'), {'selected_source_spans': [[0, len(text)]]})
    except ValueError:
        pass
    else:
        raise AssertionError('Rewritten source must be rejected')
    checks.append('literal_signed_decimal_year_punctuation_UTF8_and_no_rewrite')
    class SyntheticHF:
        def __call__(self, text, text_pair=None, add_special_tokens=True, **kwargs):
            offsets = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
            ids = list(range(10, 10 + len(offsets)))
            if text_pair is not None:
                pair_offsets = [(m.start(), m.end()) for m in re.finditer(r'\S+', text_pair)]
                ids += list(range(100, 100 + len(pair_offsets)))
                offsets += pair_offsets
            if add_special_tokens:
                ids = [1] + ids + [2] + ([3] if text_pair is not None else [])
                offsets = [(0, 0)] + offsets + [(0, 0)] + ([(0, 0)] if text_pair is not None else [])
            return {'input_ids': ids, 'offset_mapping': offsets}
    adapter = evidence.PairTokenizer(SyntheticHF())
    assert len(adapter.encode('two words', add_special_tokens=False).ids) == 2
    assert len(adapter.encode('two words', 'one').ids) == 6
    assert adapter.encode('café offset', add_special_tokens=False).offsets == [(0, 4), (5, 11)]
    context = load('static_exact_context22', base / 'candidate/epoch22/context.py')
    document = 'Agreement between café and vendor. Price -12.50 in 2024; provided the date is 2025.\n\nThe office has blue folders.'
    units = context.partition(document, adapter, adapter)
    assert units[0]['start'] == 0 and units[-1]['end'] == len(document)
    assert all(a['end'] == b['start'] for a, b in zip(units, units[1:]))
    prelude = context.select_prelude(document, units, adapter)
    premise, packed = context.pack(document, units, list(range(len(units))), 'A synthetic hypothesis.',
        adapter, rank_depth=min(40, len(units)), prelude=prelude)
    assert packed['joint_pair_tokens'] == len(adapter.encode(premise, 'A synthetic hypothesis.').ids)
    evidence.provenance(document, premise, packed)
    checks.append('HF_pair_adapter_special_tokens_offsets_and_exact_epoch22_group_pack')
    launcher = load('static_epoch27_launcher', base / 'epoch27/preparation/launch_dev.py')
    with tempfile.TemporaryDirectory(prefix='e27-synthetic-reservation-', dir=args.output.parent) as temp:
        study = Path(temp)
        launcher.reserve(study, 'a' * 64)
        try:
            launcher.reserve(study, 'a' * 64)
        except (AssertionError, FileExistsError):
            pass
        else:
            raise AssertionError('Second reservation must fail without worker creation')
        broken = study / 'truncated-raw.json'
        broken.write_text('{"cases":[')
        failures = []
        assert launcher.load_raw_preserving_failure(broken, failures) == {}
        assert failures[0]['stage'] == 'raw_read_or_parse' and broken.read_text() == '{"cases":['
    expected = {'NLI_model_initializations': 1, 'NLI_model_initializations_completed': 1,
        'NLI_forward_pairs_attempted': 72, 'NLI_forward_pairs_completed': 72,
        'NLI_forward_calls_attempted': 72, 'NLI_forward_calls_completed': 72,
        'NLI_forwards': 72, 'DEV_pairs_completed': 72, 'DEV_cases_completed': 24,
        'native_helper_starts': 1, 'native_index_initializations_attempted': 8,
        'native_index_initializations_completed': 8, 'native_queries_attempted': 24,
        'native_queries_completed': 24, 'BGE_initializations_attempted': 1,
        'BGE_initializations_completed': 1, 'ORT_sessions_attempted': 1, 'ORT_sessions_completed': 1}
    synthetic_raw = {'status': 'COMPLETED_DEV_DIAGNOSTIC_AWAITING_INDEPENDENT_SCORER',
        'cases': [{'arms': {arm: {'reader': {}} for arm in ('actual_native', 'lexical', 'positional')}} for i in range(24)],
        'counters': {**dict.fromkeys(worker.ZERO, 0), **expected},
        'errors': [], 'Python_network_violations': [], 'allowed_local_bind_events': []}
    assert all(launcher.completion_invariants(synthetic_raw).values())
    synthetic_raw['counters']['NLI_forwards'] = 73
    assert launcher.completion_invariants(synthetic_raw)['exact_operation_counts'] is False
    checks.append('one_attempt_reservation_retry_blocked_and_72_24_8_counter_closure')
    checks.append('truncated_raw_retained_and_recorded_without_blocking_failure_seal')
    valid = [(socket.AF_INET, ('127.0.0.1', 0)),
             (socket.AF_INET6, ('::1', 0)), (socket.AF_INET6, ('::1', 0, 0, 0))]
    class Nonliteral(str):
        pass
    invalid = [(socket.AF_INET, (Nonliteral('127.0.0.1'), 0)),
        (socket.AF_INET6, (Nonliteral('::1'), 0)),
        (socket.AF_INET, ('127.0.0.2', 0)), (socket.AF_INET, ('localhost', 0)),
        (socket.AF_INET, ('0.0.0.0', 0)), (socket.AF_INET, ('127.0.0.1', True)),
        (socket.AF_INET, ('127.0.0.1', 0, 0)), (socket.AF_INET6, ('::1', 0, 0, 1)),
        (socket.AF_INET6, ('::', 0)), (socket.AF_INET6, ('::1', 0, True, 0)),
        (socket.AF_INET6, ('::1', 0, 0, 0, 0)), (socket.AF_UNIX, '/tmp/unix-not-allowed')]
    assert all(network.literal_loopback_bind(*pair) for pair in valid)
    assert not any(network.literal_loopback_bind(*pair) for pair in invalid)
    checks.append('literal_loopback_exact_str_host_family_tuple_port_flow_scope_strict')
    counters = {'Python_network_operations_attempted': 0, 'Python_literal_loopback_binds_allowed': 0}
    events = []
    guard = network.OfflineGuard(counters, events.append).install()
    for family, address in valid:
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.bind(address)
        except OSError:
            pass
        finally:
            sock.close()
    assert counters['Python_literal_loopback_binds_allowed'] == 3
    assert counters['Python_network_operations_attempted'] == 0
    assert all(row['bind_outcome'] in ('SUCCESS', 'ERROR') and row['stack'] for row in guard.events)
    assert all({'monotonic_seconds', 'family', 'socket_type', 'protocol', 'address'} <= row.keys() for row in guard.events)
    checks.append('actual_local_bind_outcomes_recorded_without_connect')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    forbidden = [lambda: socket.getaddrinfo('example.invalid', 80),
                 lambda: sock.connect(('127.0.0.1', 1)),
                 lambda: sock.bind(('0.0.0.0', 0)),
                 lambda: sock.send(b'synthetic'), lambda: sock.recv(1),
                 lambda: sock.listen(1), lambda: sock.accept()]
    for operation in forbidden:
        before = counters['Python_network_operations_attempted']
        try:
            operation()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Forbidden operation escaped')
        assert counters['Python_network_operations_attempted'] == before + 1
    sock.close()
    assert len(guard.violations) == len(forbidden)
    try:
        guard.assert_clean()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Caught forbidden exceptions must remain fatal')
    checks.append('DNS_connect_nonloopback_send_recv_listen_accept_denied_and_persistent')
    assert not any(name in sys.modules for name in ('torch', 'transformers', 'tokenizers', 'onnxruntime', 'numpy'))
    report = {'schema_version': 1, 'epoch': 27, 'status': 'STATIC_AND_SYNTHETIC_GUARDS_PASS',
        'checks': checks, 'check_count': len(checks), 'ML_model_tokenizer_native_initializations': 0,
        'DEV_source_or_annotation_reads': 0, 'benchmark_workers': 0,
        'synthetic_allowed_local_binds': counters['Python_literal_loopback_binds_allowed'],
        'synthetic_forbidden_operations_refused': counters['Python_network_operations_attempted'],
        'Node_synthetic_forbidden_operations_refused': compact['node_synthetic_denied'],
        'validated_sources': [{'path': str(p.relative_to(args.project)), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted([*candidate.rglob('*.py'), candidate / 'native.cjs',
                             *(base / 'epoch27/preparation').glob('*.py')])],
        'owned_python_files': [{'path': str(p.relative_to(args.project)), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(candidate.glob('*.py'))]}
    with args.output.open('x') as target:
        json.dump(report, target, indent=2)
        target.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
