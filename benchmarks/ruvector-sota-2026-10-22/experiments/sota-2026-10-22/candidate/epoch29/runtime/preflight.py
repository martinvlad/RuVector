"""Reproducible stdlib/synthetic guard checks; no document/model/native calls."""
import argparse
import ast
import importlib.util
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
    launcher = load('epoch29_static_launcher', here / 'launch.py')
    C = launcher.C
    assert C.ROOT == here.parents[4]
    assert C.CANDIDATE == here.parent and C.STUDY == C.ROOT/'experiments/sota-2026-10-22/epoch29'
    assert not any(x in sys.modules for x in ('numpy', 'torch', 'transformers', 'tokenizers', 'onnxruntime'))
    checks.append('AST_Node_syntax_nested_root_and_lazy_stdlib_imports')
    with tempfile.TemporaryDirectory(prefix='runtime-guard-synthetic-', dir=args.output.parent) as temporary:
        temp = Path(temporary)
        for i, text in enumerate(['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{"a":Infinity}']):
            path = temp/('bad' + str(i) + '.json')
            path.write_text(text)
            try:
                C.read(path)
            except ValueError:
                pass
            else:
                raise AssertionError('Ambiguous/nonfinite JSON accepted')
        checks.append('duplicate_nonfinite_and_overflow_JSON_rejected')
        for relative in ('../escape', '/absolute', 'a/../b', 'a//b', 'a\\b'):
            try:
                C.checked(relative)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe source path accepted')
        (temp/'actual').mkdir()
        (temp/'link').symlink_to(temp/'actual', target_is_directory=True)
        try:
            C.no_symlink(temp/'link'/'nested')
        except ValueError:
            pass
        else:
            raise AssertionError('Symlink component accepted')
        checks.append('unsafe_paths_and_parent_symlinks_rejected')
        study = temp/'study'
        launcher.reserve(study, 'a'*64)
        reservation = C.read(study/'ATTEMPT_RESERVATION.json')
        assert reservation['owned_workers_reserved'] == 1 and reservation['before_Popen'] is True
        try:
            launcher.reserve(study, 'a'*64)
        except (RuntimeError, FileExistsError):
            pass
        else:
            raise AssertionError('Reserved attempt retried')
        checks.append('exclusive_fsynced_reservation_survives_without_worker_and_refuses_retry')
        full, partial = temp/'raw.json', temp/'raw.partial.json'
        full.write_text('{"interrupted":')
        partial.write_text('{"counters":{"native_queries_attempted":3}}')
        errors = []
        bad = launcher.load_raw_preserving_failure(full, errors)
        known = launcher.load_raw_preserving_failure(partial, errors)
        assert full.read_bytes() == b'{"interrupted":' and errors
        assert launcher.select_operation_counters(bad, known) == ({'native_queries_attempted':3}, 'raw.partial.json')
        assert launcher.select_operation_counters({}, {}) == (None, 'UNKNOWN')
        assert launcher.select_operation_counters({'counters':{'a':5}}, {'counters':{'a':3}}) == ({'a':5}, 'raw.json')
        assert launcher.completion_invariants({'counters':None}, {'expected_operation_counters':{'a':1}})['exact_frozen_operation_counts'] is False
        checks.append('malformed_final_bytes_retained_partial_observed_counts_and_absent_unknown_not_zero')
        # Exercise actual source-pin admission on synthetic metadata only.
        original = C.ROOT, C.HERE, C.CANDIDATE, C.STUDY
        C.ROOT = temp/'project'
        C.CANDIDATE = C.ROOT/'experiments/sota-2026-10-22/candidate/epoch29'
        C.HERE = C.CANDIDATE/'runtime'
        C.STUDY = C.ROOT/'experiments/sota-2026-10-22/epoch29'
        C.HERE.mkdir(parents=True)
        C.STUDY.mkdir(parents=True)
        refs = []
        for path in [*(C.HERE/x for x in ('common.py','launch.py','network_guard.py','node_guard.cjs','cpu_guard.py')),
                C.CANDIDATE/'worker.py', C.CANDIDATE/'native_identity.cjs', C.CANDIDATE/'inputs.json', C.CANDIDATE/'runtime.json']:
            path.write_text('synthetic source placeholder\n')
            refs.append({'path':str(path.relative_to(C.ROOT)),'bytes':path.stat().st_size,'sha256':C.sha(path)})
        freeze = C.STUDY/'source-freeze.json'
        freeze.write_text(json.dumps({'epoch':29,'kind':C.KIND,'source_checkpoint':C.SOURCE,'entries':refs}))
        refs.append({'path':str(freeze.relative_to(C.ROOT)),'bytes':freeze.stat().st_size,'sha256':C.sha(freeze)})
        plan = {'epoch':29,'kind':C.KIND,'source_checkpoint':C.SOURCE,'actual_project':str(C.ROOT),
            'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},
            'limits':{'owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':0,'engineering_batches':1,'paid_calls':0,'GPU_calls':0},
            'pins':refs,'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),
            'native_worker_path':str((C.CANDIDATE/'native_identity.cjs').relative_to(C.ROOT)),
            'expected_operation_counters':{'native_queries_attempted':1}}
        for key, path in [('engineering_inputs',C.CANDIDATE/'inputs.json'),('runtime_assets_lock',C.CANDIDATE/'runtime.json'),('source_freeze',freeze)]:
            plan[key+'_path'], plan[key+'_sha256'] = str(path.relative_to(C.ROOT)), C.sha(path)
        plan_path = C.STUDY/'plan.json'
        plan_path.write_text(json.dumps(plan))
        C.verify_plan(plan_path,C.sha(plan_path))
        victim = C.CANDIDATE/'worker.py'
        original_bytes = victim.read_bytes()
        victim.write_bytes(b'changed synthetic source\n')
        try:
            C.verify_plan(plan_path,C.sha(plan_path))
        except ValueError:
            pass
        else:
            raise AssertionError('Changed source pin admitted')
        victim.write_bytes(original_bytes)
        plan['data_roles']['dev'] = ['forbidden']
        plan_path.write_text(json.dumps(plan))
        try:
            C.verify_plan(plan_path,C.sha(plan_path))
        except ValueError:
            pass
        else:
            raise AssertionError('Nonempty DEV role admitted')
        C.ROOT, C.HERE, C.CANDIDATE, C.STUDY = original
        checks.append('actual_plan_gate_accepts_synthetic_closed_sources_and_rejects_tamper_or_DEV_role')
        child = subprocess.Popen([sys.executable,'-I','-B','-c',
            "import time;print('synthetic-ready',flush=True);time.sleep(30)"],
            start_new_session=True,stdout=subprocess.PIPE,text=True)
        try:
            assert child.stdout.readline() == 'synthetic-ready\n'
            identity = C.proc(child.pid)
            assert identity['pgid'] == child.pid and identity['sid'] == child.pid
            bad_identity = dict(identity,ticks=identity['ticks']+1)
            signals = []
            try:
                launcher.signal_owned_session(child,bad_identity,signal.SIGTERM,signals)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Forged startticks permitted process-group signal')
            assert child.poll() is None and signals == []
            launcher.signal_owned_session(child,identity,signal.SIGTERM,signals)
            child.wait(timeout=3)
            assert signals == ['SIGTERM'] and not launcher.group(child.pid)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=3)
            child.stdout.close()
        checks.append('owned_session_cleanup_refuses_wrong_startticks_then_terminates_only_exact_synthetic_PID_PGID_SID')
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
sock.destroy();const result=guard.diagnostics();assert.equal(result.nativeAttempted,0);assert.equal(result.nativeCompleted,0);
assert.equal(result.events.every(row=>row.stack&&row.event==='OFFLINE_FATAL_VIOLATION'),true);
process.exitCode=0;process.stdout.write(JSON.stringify({denied:result.attempts,native_initializations:0}));
'''
    env = dict(os.environ, E29_GUARD_SYNTHETIC='1')
    env.pop('NODE_OPTIONS', None)
    node = json.loads(subprocess.check_output(['node','-e',script,str(here/'node_guard.cjs')],env=env,text=True))
    assert node['denied'] == 20 and node['native_initializations'] == 0
    checks.append('Node20_DNS_TCP_UDP_HTTP_fetch_send_receive_violations_persist_with_no_native_import')
    clean_env = {k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','E29_GUARD_SYNTHETIC','E29_PROJECT','E29_OUT','E29_PLAN','E29_PLAN_SHA','E29_ADMISSION')}
    denied = subprocess.run(['node','--require',str(here/'node_guard.cjs'),'-e',"throw new Error('UNREACHABLE_NATIVE_WORK');"],env=clean_env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert denied.returncode != 0 and 'External source gate environment missing' in denied.stderr
    checks.append('Node_missing_actual_source_admission_refuses_before_main_script')
    cpu = load('epoch29_static_cpu', here/'cpu_guard.py')
    cpu_script = r'''
import ctypes,errno,json,os,threading,subprocess
assert os.sched_getaffinity(0)=={0,1}
denied=[]
for mask in ({0,1,2},{0,1}):
 try:os.sched_setaffinity(0,mask)
 except OSError as error:assert error.errno==errno.EPERM;denied.append('main')
 else:raise AssertionError('CPU affinity escaped inherited guard')
libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
assert libc.syscall(ctypes.c_long(0x400000CB),ctypes.c_int(0),ctypes.c_ulong(0),ctypes.c_void_p(None))==-1
assert ctypes.get_errno()==errno.EPERM;denied.append('x32')
thread_result=[]
def thread():
 try:os.sched_setaffinity(0,{0,1,2})
 except OSError as error:thread_result.append((error.errno,sorted(os.sched_getaffinity(0))))
t=threading.Thread(target=thread);t.start();t.join();assert thread_result==[(errno.EPERM,[0,1])];denied.append('thread')
status={line.split(':')[0]:line.split(':',1)[1].strip() for line in open('/proc/self/status') if line.startswith(('NoNewPrivs:','Seccomp:','Seccomp_filters:','Cpus_allowed_list:'))}
assert status['NoNewPrivs']=='1' and status['Seccomp']=='2'
node_code="const fs=require('node:fs');const s=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\\n').filter(x=>/^(NoNewPrivs|Seccomp|Cpus_allowed_list):/.test(x)).map(x=>[x.split(':')[0],x.slice(x.indexOf(':')+1).trim()]));process.stdout.write(JSON.stringify(s));"
node=json.loads(subprocess.check_output(['node','-e',node_code],text=True))
assert node['NoNewPrivs']=='1' and node['Seccomp']=='2' and node['Cpus_allowed_list'] in ('0-1','0,1')
print(json.dumps({'synthetic_denied_affinity_syscalls':len(denied),'CPU_affinity':[0,1],'actual_status':status,'Node_grandchild_inherited_status':node,'native_initializations':0}))
'''
    before = os.sched_getaffinity(0)
    receipt = args.output.with_suffix('.cpu-preexec.json')
    fd = os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        cpu_result = json.loads(subprocess.check_output([sys.executable,'-I','-B','-c',cpu_script],preexec_fn=cpu.make_preexec(fd),pass_fds=(fd,),text=True))
    finally:
        os.close(fd)
    assert os.sched_getaffinity(0)==before and cpu_result['synthetic_denied_affinity_syscalls']==4
    assert C.read(receipt)['status']=='CPU_GUARD_INSTALLED_BEFORE_EXEC'
    checks.append('whole_Python_child_preexec_CPU2_seccomp_native_x32_exec_thread_inheritance_and_parent_unchanged')
    checks.append('Node_grandchild_inherits_whole_worker_CPU_guard_without_second_setaffinity_or_native_import')
    network = load('epoch29_static_python_network', here/'network_guard.py')
    counters = {'Python_network_operations_attempted':0}
    guard = network.OfflineGuard(counters,lambda event:None).install()
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    operations = [lambda:sock.bind(('127.0.0.1',0)),lambda:socket.getaddrinfo('example.invalid',80),
        lambda:sock.connect(('127.0.0.1',1)),lambda:sock.send(b'synthetic'),lambda:sock.recv(1),lambda:sock.listen(1),lambda:sock.accept()]
    for operation in operations:
        count = counters['Python_network_operations_attempted']
        try:operation()
        except RuntimeError:pass
        else:raise AssertionError('Forbidden Python networking accepted')
        assert counters['Python_network_operations_attempted']==count+1
    sock.close()
    try:guard.assert_clean()
    except RuntimeError:pass
    else:raise AssertionError('Caught failures erased persistent network flag')
    checks.append('Python7_bind_DNS_connect_send_receive_listen_accept_denials_persist')
    assert not any(x in sys.modules for x in ('numpy','torch','transformers','tokenizers','onnxruntime'))
    report={'schema_version':1,'epoch':29,'status':'PASS_STDLIB_RUNTIME_GUARD_PREFLIGHT','checks':checks,'check_count':len(checks),
        'synthetic_Node_network_denials':node['denied'],'synthetic_Python_network_denials':counters['Python_network_operations_attempted'],
        'synthetic_CPU_seccomp_denials':cpu_result['synthetic_denied_affinity_syscalls'],'CPU_child':cpu_result,
        'model_tokenizer_native_initializations':0,'actual_engineering_workers':0,'TRAIN_DEV_CONF_or_choices_reads':0,
        'scope':'Synthetic stdlib/kernel/API guards only; no runtime model import, vectors, data rows, native addon, real source admission or benchmark measurement.',
        'files':[{'path':str(f),'bytes':f.stat().st_size,'sha256':C.sha(f)} for f in sorted(here.iterdir()) if f.is_file()]}
    C.put(args.output,report)
    print(json.dumps({'check_count':len(checks),'report':str(args.output),'sha256':C.sha(args.output)}))


if __name__=='__main__':
    main()
