"""Pure standard-library static/mutation guard checks; never ML/native init."""
import argparse
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import tempfile


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    checks = []
    for file in here.glob('*.py'):
        ast.parse(file.read_text(), filename=str(file))
    subprocess.run(['node', '--check', str(here / 'node_guard.cjs')], check=True)
    checks.append('owned_Python_AST_and_Node_syntax_without_native_import')
    worker, launcher = load('e28_static_worker', here / 'worker.py'), load('e28_static_launcher', here / 'launch_engineering.py')
    C = worker.C
    assert not any(x in sys.modules for x in ('numpy', 'torch', 'transformers', 'tokenizers', 'onnxruntime'))
    runtime = C.verify_runtime({'runtime_assets_lock_path': str((here / 'RUNTIME_ASSETS.json').relative_to(C.ROOT))})
    assert len(runtime['files']) == 17
    assert C.sha(C.checked(C.SOURCE_MAP)) == C.SOURCE_MAP_SHA
    for row in C.read(C.checked(C.SOURCE_MAP))['source_files']:
        file = C.checked(row['path'])
        assert file.stat().st_size == row['bytes'] and C.sha(file) == row['sha256']
    checks.append('all17_actual_runtime_and14_immutable_source_map_rows_hash_verified_without_loading')
    for relative in ('../escape', '/absolute', 'a/../b', 'a//b', 'a\\b'):
        try:
            C.checked(relative)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsafe frozen path accepted')
    checks.append('frozen_path_mutations_rejected')
    with tempfile.TemporaryDirectory(prefix='e28-static-', dir=args.output.parent) as temp:
        temp = Path(temp)
        launcher.reserve(temp, 'a' * 64)
        try:
            launcher.reserve(temp, 'a' * 64)
        except (AssertionError, FileExistsError):
            pass
        else:
            raise AssertionError('Second reservation accepted')
        malformed = temp / 'raw.json'
        malformed.write_text('{"requests":[')
        errors = []
        assert launcher.load_raw_preserving_failure(malformed, errors) == {}
        assert errors[0]['stage'] == 'raw_read_or_parse' and malformed.read_text() == '{"requests":['
        original = '{"state": "Ω\\nwhole state", "questions": {"decision": {"type": "noul", "instructions": "predicate"}}}\n'
        observed = []
        with (temp / 'wire').open('xb') as sink:
            target = io.StringIO()
            tee = worker.Tee(target, sink, observed, 'stdin')
            assert tee.write(original) == len(original)
            assert target.getvalue() == original
        assert (temp / 'wire').read_bytes() == original.encode('utf-8') and observed == [original]
        class BrokenWriter:
            def write(self, value):
                raise BrokenPipeError('synthetic pipe failure before acceptance')
        notices = []
        with (temp / 'broken-wire').open('xb') as sink:
            tee = worker.Tee(BrokenWriter(), sink, [], 'stdin', lambda *args: notices.append(args))
            try:
                tee.write(original)
            except BrokenPipeError:
                pass
            else:
                raise AssertionError('Injected pipe failure did not propagate')
        assert [row[0] for row in notices] == ['attempt'] and (temp / 'broken-wire').read_bytes() == b''
        prior_handler, prior_dump = signal.getsignal(signal.SIGALRM), worker.json.dump
        def stop(signum, frame):
            raise TimeoutError('synthetic stop during checkpoint write')
        def interrupted_dump(value, target, **kwargs):
            prior_dump(value, target, **kwargs)
            signal.raise_signal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, stop)
        worker.json.dump = interrupted_dump
        try:
            try:
                worker.atomic_checkpoint({'counter': 1, 'whole_utf8': 'Ω'}, temp)
            except TimeoutError:
                pass
            else:
                raise AssertionError('Pending stop was not delivered after checkpoint')
        finally:
            worker.json.dump = prior_dump
            signal.signal(signal.SIGALRM, prior_handler)
        assert json.loads((temp / 'raw.partial.json').read_text()) == {'counter': 1, 'whole_utf8': 'Ω'}
        assert not (temp / 'raw.partial.pending.json').exists()
    checks.append('one_xreservation_and_malformed_partial_raw_preserved')
    checks.append('transparent_pipe_tee_preserves_full_literal_UTF8_bytes_and_newline')
    checks.append('broken_pipe_attempt_retained_without_inventing_accepted_frame_or_backend_execution')
    checks.append('stop_signal_injected_during_checkpoint_delivered_only_after_complete_atomic_replacement')
    script = r'''
const assert=require('node:assert/strict'),guard=require(process.argv[1]);
const dns=require('node:dns'),net=require('node:net');
const operations=[()=>dns.lookup('example.invalid',()=>{}),()=>dns.resolveMx('example.invalid',()=>{}),
 ()=>dns.resolveTxt('example.invalid',()=>{}),()=>dns.resolveCaa('example.invalid',()=>{}),
 ()=>dns.promises.resolveTxt('example.invalid'),()=>new dns.Resolver().resolveMx('example.invalid',()=>{}),
 ()=>new dns.promises.Resolver().resolveTxt('example.invalid'),()=>net.connect(1,'127.0.0.1'),
 ()=>new net.Server().listen(0),()=>require('node:dgram').createSocket('udp4'),
 ()=>require('node:http').request('http://example.invalid'),()=>require('node:https').request('https://example.invalid'),
 ()=>fetch('https://example.invalid'),()=>new (require('node:dgram').Socket)('udp4'),
 ()=>require('node:dgram').Socket.prototype.bind.call({},0),
 ()=>require('node:dgram').Socket.prototype.send.call({},Buffer.from('synthetic'),1,'127.0.0.1'),
 ()=>require('node:dgram').Socket.prototype.connect.call({},1,'127.0.0.1')];
const sock=new net.Socket();operations.push(()=>sock.write('synthetic'),()=>sock.read(1),()=>sock.end());
for(const operation of operations){const before=guard.diagnostics().attempts;assert.throws(operation);assert.equal(guard.diagnostics().attempts,before+1);}
sock.destroy();const result=guard.diagnostics();
assert.equal(result.nativeAttempted,0);assert.equal(result.nativeCompleted,0);
assert.equal(result.events.every(row=>row.stack&&row.event==='OFFLINE_FATAL_VIOLATION'),true);
process.exitCode=0;process.stdout.write(JSON.stringify({denied:result.attempts,native_initializations:0}));
'''
    env = dict(os.environ, E28_GUARD_SYNTHETIC='1')
    env.pop('NODE_OPTIONS', None)
    node = json.loads(subprocess.check_output(['node', '-e', script, str(here / 'node_guard.cjs')], env=env, text=True))
    assert node['denied'] == 20 and node['native_initializations'] == 0
    checks.append('Node_all_DNS_Resolver_connect_send_receive_listen_HTTP_UDP_fetch_denied_persistently_with_zero_native_imports')
    cpu = load('e28_static_child_cpu_guard', here / 'cpu_guard.py')
    cpu_script = r'''
import ctypes,errno,json,os,threading
assert os.sched_getaffinity(0)=={0,1}
denied=[]
for mask in ({0,1,2},{0,1}):
    try:os.sched_setaffinity(0,mask)
    except OSError as error:
        assert error.errno==errno.EPERM;denied.append('main')
    else:raise AssertionError('CPU-affinity syscall escaped inherited filter')
libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
assert libc.syscall(ctypes.c_long(0x400000CB),ctypes.c_int(0),ctypes.c_ulong(0),ctypes.c_void_p(None))==-1
assert ctypes.get_errno()==errno.EPERM;denied.append('x32')
thread_result=[]
def thread():
    try:os.sched_setaffinity(0,{0,1,2})
    except OSError as error:thread_result.append((error.errno,sorted(os.sched_getaffinity(0))))
t=threading.Thread(target=thread);t.start();t.join()
assert thread_result==[(errno.EPERM,[0,1])];denied.append('inherited_thread')
values={line.split(':')[0]:line.split(':',1)[1].strip() for line in open('/proc/self/status') if line.startswith(('NoNewPrivs:','Seccomp:','Seccomp_filters:','Cpus_allowed_list:'))}
assert values['NoNewPrivs']=='1' and values['Seccomp']=='2'
print(json.dumps({'synthetic_denied_affinity_syscalls':len(denied),'CPU_affinity':sorted(os.sched_getaffinity(0)),'actual_status':values,'native_initializations':0}))
'''
    before_affinity = os.sched_getaffinity(0)
    receipt = args.output.parent / (args.output.stem + '.cpu-preexec.json')
    descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        cpu_result = json.loads(subprocess.check_output([sys.executable, '-I', '-B', '-c', cpu_script],
            preexec_fn=cpu.make_preexec(descriptor), pass_fds=(descriptor,), text=True))
    finally:
        os.close(descriptor)
    assert os.sched_getaffinity(0) == before_affinity
    installed = json.loads(receipt.read_text())
    assert installed['status'] == 'CPU_GUARD_INSTALLED_BEFORE_EXEC' and installed['CPU_affinity'] == [0, 1]
    assert cpu_result['synthetic_denied_affinity_syscalls'] == 4 and cpu_result['native_initializations'] == 0
    checks.append('isolated_child_beforeexec_seccomp_denies_native_and_x32_affinity_changes_and_inherits_across_exec_and_thread_creation')
    checks.append('CPU_policy_is_process_local_and_parent_affinity_unchanged')
    network = load('e28_static_python_network', here / 'network_guard.py')
    counters = {'Python_network_operations_attempted': 0}
    guard = network.OfflineGuard(counters, lambda event: None).install()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    operations = [lambda: sock.bind(('127.0.0.1', 0)), lambda: socket.getaddrinfo('example.invalid', 80),
        lambda: sock.connect(('127.0.0.1', 1)), lambda: sock.send(b'synthetic'), lambda: sock.recv(1),
        lambda: sock.listen(1), lambda: sock.accept()]
    for operation in operations:
        before = counters['Python_network_operations_attempted']
        try:
            operation()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Forbidden Python network API accepted')
        assert counters['Python_network_operations_attempted'] == before + 1
    sock.close()
    try:
        guard.assert_clean()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Caught network exceptions cleared fatal flag')
    checks.append('Python_all_bind_DNS_connect_send_receive_listen_accept_denied_persistent')
    assert not any(x in sys.modules for x in ('numpy', 'torch', 'transformers', 'tokenizers', 'onnxruntime'))
    report = {'schema_version': 1, 'epoch': 28, 'status': 'STATIC_MUTATION_GUARDS_PASS',
        'checks': checks, 'check_count': len(checks), 'model_tokenizer_native_initializations': 0,
        'engineering_model_workers': 0, 'DEV_CONF_source_or_annotation_reads': 0,
        'synthetic_denied_Node_API_operations': node['denied'],
        'synthetic_denied_Python_API_operations': counters['Python_network_operations_attempted'],
        'synthetic_denied_CPU_affinity_syscalls': cpu_result['synthetic_denied_affinity_syscalls'],
        'synthetic_CPU_guard_preexec_receipt': {'path': str(receipt), 'sha256': C.sha(receipt)},
        'validated_sources': [{'path': str(path.relative_to(C.ROOT)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)}
            for path in sorted([*here.glob('*.py'), here / 'node_guard.cjs', here / 'RUNTIME_ASSETS.json', here / 'RAW_SCHEMA.json'])]}
    C.put(args.output, report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
