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
    candidate = base / 'candidate/epoch26'
    checks = []
    for path in sorted(candidate.rglob('*.py')):
        ast.parse(path.read_text(), filename=str(path))
    for path in sorted((base / 'epoch26/preparation').glob('*.py')):
        ast.parse(path.read_text(), filename=str(path))
    checks.append('all_owned_and_reader_python_AST_valid')
    subprocess.run(['node', '--check', str(candidate / 'native.cjs')], check=True)
    checks.append('native_helper_node_syntax_valid_without_import')
    worker = load('static_epoch26_worker', candidate / 'worker.py')
    evidence = load('static_epoch26_evidence', candidate / 'evidence.py')
    network = load('static_epoch26_network', candidate / 'network_guard.py')
    checks.append('worker_import_is_ML_tokenizer_native_lazy')
    assert not any(name in sys.modules for name in ('torch', 'transformers', 'tokenizers', 'onnxruntime', 'numpy'))
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
    launcher = load('static_epoch26_launcher', base / 'epoch26/preparation/launch_dev.py')
    with tempfile.TemporaryDirectory(prefix='e26-synthetic-reservation-', dir=args.output.parent) as temp:
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
    invalid = [(socket.AF_INET, ('127.0.0.2', 0)), (socket.AF_INET, ('localhost', 0)),
        (socket.AF_INET, ('0.0.0.0', 0)), (socket.AF_INET, ('127.0.0.1', True)),
        (socket.AF_INET, ('127.0.0.1', 0, 0)), (socket.AF_INET6, ('::1', 0, 0, 1)),
        (socket.AF_INET6, ('::', 0)), (socket.AF_INET6, ('::1', 0, True, 0)),
        (socket.AF_INET6, ('::1', 0, 0, 0, 0)), (socket.AF_UNIX, '/tmp/unix-not-allowed')]
    assert all(network.literal_loopback_bind(*pair) for pair in valid)
    assert not any(network.literal_loopback_bind(*pair) for pair in invalid)
    checks.append('literal_loopback_family_tuple_port_flow_scope_strict')
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
    report = {'schema_version': 1, 'epoch': 26, 'status': 'STATIC_AND_SYNTHETIC_GUARDS_PASS',
        'checks': checks, 'check_count': len(checks), 'ML_model_tokenizer_native_initializations': 0,
        'DEV_source_or_annotation_reads': 0, 'benchmark_workers': 0,
        'synthetic_allowed_local_binds': counters['Python_literal_loopback_binds_allowed'],
        'synthetic_forbidden_operations_refused': counters['Python_network_operations_attempted'],
        'owned_python_files': [{'path': str(p.relative_to(args.project)), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(candidate.glob('*.py'))]}
    with args.output.open('x') as target:
        json.dump(report, target, indent=2)
        target.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
