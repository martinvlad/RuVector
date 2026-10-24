"""Source-only metadata/API/kernel guard tests; never imports or probes a model."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def metadata_checks(C, launcher, temp):
    import copy
    checks = []
    for i, text in enumerate(['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{"a":Infinity}']):
        file = temp / ('bad' + str(i) + '.json')
        file.write_text(text)
        try:C.read(file)
        except ValueError:pass
        else:raise AssertionError('Ambiguous/nonfinite JSON admitted')
    checks.append('strict_duplicate_nonfinite_overflow_JSON_rejected')
    for relative in ('../escape','/absolute','a/../b','a//b','a\\b'):
        try:C.checked(relative)
        except ValueError:pass
        else:raise AssertionError('Unsafe frozen path admitted')
    (temp/'actual').mkdir();(temp/'link').symlink_to(temp/'actual',target_is_directory=True)
    try:C.no_symlink(temp/'link'/'child')
    except ValueError:pass
    else:raise AssertionError('Parent symlink admitted')
    checks.append('unsafe_paths_and_symlink_components_rejected')
    reserved = temp/'reservation-test'
    for phase in C.PHASES:
        out = launcher.reserve(reserved,'a'*64,phase)
        assert out == reserved/('runs/'+phase)
        assert C.read(reserved/(phase.upper()+'_ATTEMPT_RESERVATION.json'))['phase']==phase
        try:launcher.reserve(reserved,'a'*64,phase)
        except (RuntimeError,FileExistsError):pass
        else:raise AssertionError('Phase retry admitted')
    checks.append('independent_TRAIN_DEV_exclusive_fsynced_reservations_each_refuse_retry')
    full, partial = temp/'raw.json',temp/'raw.partial.json'
    full.write_text('{"interrupted":');partial.write_text('{"counters":{"attempts":3}}')
    errors=[]
    raw=launcher.load_raw_preserving_failure(full,errors)
    checkpoint=launcher.load_raw_preserving_failure(partial,errors)
    assert full.read_bytes()==b'{"interrupted":' and errors
    assert launcher.select_operation_counters(raw,checkpoint)==({'attempts':3},'raw.partial.json')
    assert launcher.select_operation_counters({}, {})==(None,'UNKNOWN')
    assert launcher.select_operation_counters({'counters':{'a':5}},checkpoint)==({'a':5},'raw.json')
    checks.append('original_malformed_final_bytes_and_partial_counts_preserved_absence_unknown')
    saved={key:getattr(C,key) for key in ('ROOT','HERE','CANDIDATE','STUDY','owner_lock','sha','read')}
    source_root=C.ROOT
    try:
        C.ROOT=temp/'project';C.CANDIDATE=C.ROOT/'experiments/sota-2026-10-22/candidate/epoch30'
        C.HERE=C.CANDIDATE/'runtime';C.STUDY=C.ROOT/'experiments/sota-2026-10-22/epoch30'
        C.HERE.mkdir(parents=True);C.STUDY.mkdir(parents=True)
        def identity(path):return {'path':str(path.relative_to(C.ROOT)),'bytes':path.stat().st_size,'sha256':C.sha(path)}
        refs=[]
        for file in [*(C.HERE/x for x in ('common.py','launch.py','network_guard.py','node_guard.cjs','cpu_guard.py')),
                C.CANDIDATE/'worker.py',C.CANDIDATE/'native_helper.cjs',C.CANDIDATE/'train.json',
                C.CANDIDATE/'dev.json',C.CANDIDATE/'runtime.json',C.CANDIDATE/'bart-lock.json']:
            file.write_text('synthetic metadata without labels or model data\n');refs.append(identity(file))
        for relative in [C.ORIGINAL_READER,'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json']:
            target=C.ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((source_root/relative).read_bytes());refs.append(identity(target))
        freeze=C.STUDY/'source-freeze.json'
        freeze.write_text(json.dumps({'epoch':30,'kind':C.KIND,'source_checkpoint':C.SOURCE,'entries':refs}))
        refs.append(identity(freeze))
        plan={'epoch':30,'kind':C.KIND,'source_checkpoint':C.SOURCE,'actual_project':str(C.ROOT),
            'data_roles':{'train':list(C.TRAIN_IDS),'dev':list(C.DEV_IDS),'calibration':[],'confirmation':[]},
            'limits':{'owned_workers':2,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],
                'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':1,'DEV_worker_attempts':1,
                'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},'pins':refs,
            'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),
            'native_worker_path':str((C.CANDIDATE/'native_helper.cjs').relative_to(C.ROOT)),
            'trained_parameters_path':str((C.STUDY/'runs/train/trained-parameters.public.json').relative_to(C.ROOT)),
            'expected_operation_counters':{'train':{'training_steps':24},'dev':{'NLI_forward_calls_completed':96}}}
        for key,file in [('train_inputs',C.CANDIDATE/'train.json'),('dev_inputs',C.CANDIDATE/'dev.json'),
                ('runtime_assets_lock',C.CANDIDATE/'runtime.json'),('source_freeze',freeze),
                ('bart_assets_lock',C.CANDIDATE/'bart-lock.json'),('original_reader',C.ROOT/C.ORIGINAL_READER),
                ('runtime_policy_addendum',C.ROOT/'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json')]:
            plan[key+'_path'],plan[key+'_sha256']=str(file.relative_to(C.ROOT)),C.sha(file)
        plan_file=C.STUDY/'plan.json';plan_file.write_text(json.dumps(plan));plan_sha=C.sha(plan_file)
        dev=C.checked(plan['dev_inputs_path']);dev_reads=[]
        def no_dev_sha(path):
            if Path(path)==dev:dev_reads.append('SHA');raise AssertionError('DEV input opened before MODEL')
            return saved['sha'](path)
        def no_dev_read(path):
            if Path(path)==dev:dev_reads.append('READ');raise AssertionError('DEV input parsed before MODEL')
            return saved['read'](path)
        C.sha,C.read=no_dev_sha,no_dev_read
        C.verify_plan(plan_file,plan_sha,'train');assert not dev_reads
        checks.append('TRAIN_plan_verification_defers_all_DEV_input_content_access')
        source={'epoch':30,'kind':C.KIND,'scope':'benchmarks/ruvector-sota-2026-10-22/',
            'verified_actual_remote_readback':True,'plan_sha256':plan_sha,'source_freeze_sha256':plan['source_freeze_sha256'],
            'published_source_commit':'a'*40,'owner_pid':84004,'owner_startticks':18294638}
        (C.STUDY/'SOURCE_ADMISSION.json').write_text(json.dumps(source))
        C.owner_lock=lambda *a: {'synthetic_mock_ownership_only':True}
        C.admission(C.STUDY/'SOURCE_ADMISSION.json',plan,plan_sha,'train')
        try:C.admission(C.STUDY/'MODEL_ADMISSION.json',plan,plan_sha,'dev')
        except FileNotFoundError:pass
        else:raise AssertionError('Missing MODEL allowed DEV')
        assert not dev_reads
        checks.append('SOURCE_admission_never_substitutes_for_missing_MODEL_before_DEV')
        train=C.STUDY/'runs/train';train.mkdir(parents=True)
        artifact=train/'trained-parameters.public.json';artifact.write_text('SYNTHETIC_OPAQUE_BYTES_NOT_TENSORS')
        train_raw=train/'raw.json';train_raw.write_text('SYNTHETIC_OPAQUE_RAW_NO_LABELS')
        execution={'epoch':30,'kind':C.KIND,'phase':'train','status':'WORKER_COMPLETED',
            'worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,
            'owned_live_processes_closed':True,'owned_live_group_members':[],
            'raw_operation_counters_source':'raw.json','operation_counts_complete':True,
            'backend_execution_since_checkpoint':'NOT_APPLICABLE_FINAL_RAW','raw_sha256':C.sha(train_raw),
            'raw_bytes':train_raw.stat().st_size,'allowed_further_phase_workers':0,
            'worker_identity':{'pid':2147483647,'pgid':2147483647,'sid':2147483647,'ticks':1},
            'raw_operation_counters':dict.fromkeys(('TRAIN_forward_calls_completed','backward_calls_completed','optimizer_steps_completed','training_steps'),24)}
        execution_file=train/'execution.json';execution_file.write_text(json.dumps(execution))
        report_file=C.ROOT/'experiments/sota-2026-10-22/audit/epoch30/fake-train-integrity.json'
        seal={'schema_version':1,'epoch':30,'kind':C.KIND,'status':'TRAINED_PARAMETER_ARTIFACT_SEALED',
            'base_model_sha256':C.BASE_MODEL_SHA,'parameter_artifact':identity(artifact),'train_raw':identity(train_raw),
            'train_execution':identity(execution_file),'source_plan':identity(plan_file),'source_freeze':identity(freeze)}
        report={'schema_version':1,'epoch':30,'kind':C.KIND,'train_integrity_passed':True,
            'evidence':{key:seal[value] for key,value in {'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution','plan':'source_plan','freeze':'source_freeze'}.items()}}
        report_file.write_text(json.dumps(report));seal['independent_training_report']=identity(report_file)
        seal_file=C.STUDY/'MODEL_SEAL.json';seal_file.write_text(json.dumps(seal))
        model={'epoch':30,'kind':C.KIND,'phase':'dev','scope':source['scope'],'verified_actual_remote_readback':True,
            'plan_sha256':plan_sha,'source_freeze_sha256':plan['source_freeze_sha256'],
            'published_source_commit':'a'*40,'published_model_commit':'b'*40,
            'source_admission_sha256':C.sha(C.STUDY/'SOURCE_ADMISSION.json'),
            'model_seal':identity(seal_file),'parameter_artifact':identity(artifact),'owner_pid':84004,'owner_startticks':18294638}
        model_file=C.STUDY/'MODEL_ADMISSION.json';model_file.write_text(json.dumps(model))
        C.admission(model_file,plan,plan_sha,'dev');assert not dev_reads
        checks.append('MODEL_gate_validates_closed_TRAIN_and_exact_independent_ref_chain_without_decoding_artifact_or_DEV')
        def rewrite_chain(execution_value, integrity):
            execution_file.write_text(json.dumps(execution_value))
            seal['train_execution']=identity(execution_file)
            report['train_integrity_passed']=integrity
            report['evidence']['execution']=seal['train_execution']
            report_file.write_text(json.dumps(report))
            seal['independent_training_report']=identity(report_file)
            seal_file.write_text(json.dumps(seal));model['model_seal']=identity(seal_file)
            model_file.write_text(json.dumps(model))
        bad_execution=copy.deepcopy(execution);bad_execution['raw_operation_counters']['training_steps']=23
        rewrite_chain(bad_execution,True)
        try:C.admission(model_file,plan,plan_sha,'dev')
        except ValueError:pass
        else:raise AssertionError('23-update TRAIN admitted as24')
        rewrite_chain(execution,False)
        try:C.admission(model_file,plan,plan_sha,'dev')
        except ValueError:pass
        else:raise AssertionError('Failed independent TRAIN integrity admitted')
        rewrite_chain(execution,True);C.admission(model_file,plan,plan_sha,'dev')
        assert not dev_reads
        checks.append('self_consistent_MODEL_rejected_for23steps_or_false_independent_TRAIN_integrity')
        bad=copy.deepcopy(model);bad['verified_actual_remote_readback']=False;model_file.write_text(json.dumps(bad))
        try:C.admission(model_file,plan,plan_sha,'dev')
        except ValueError:pass
        else:raise AssertionError('Unverified MODEL allowed DEV')
        model_file.write_text(json.dumps(model));old=artifact.read_bytes();artifact.write_bytes(b'CHANGED')
        try:C.admission(model_file,plan,plan_sha,'dev')
        except ValueError:pass
        else:raise AssertionError('Changed trained artifact admitted')
        artifact.write_bytes(old)
        assert not dev_reads
        checks.append('unverified_MODEL_or_tampered_trained_artifact_rejected_before_DEV_input')
        C.sha,C.read=saved['sha'],saved['read']
        C.verify_plan(plan_file,plan_sha,'dev')
        altered=copy.deepcopy(plan);altered['data_roles']['confirmation']=[999];plan_file.write_text(json.dumps(altered))
        try:C.verify_plan(plan_file,C.sha(plan_file),'train')
        except ValueError:pass
        else:raise AssertionError('Confirmation admitted')
        checks.append('DEV_source_pins_open_only_after_MODEL_and_confirmation_role_rejected')
    finally:
        for key,value in saved.items():setattr(C,key,value)
    child=subprocess.Popen([sys.executable,'-I','-B','-c',"import time;print('ready',flush=True);time.sleep(30)"],
        start_new_session=True,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline()=='ready\n';identity=C.proc(child.pid);signals=[]
        try:launcher.signal_owned_session(child,dict(identity,ticks=identity['ticks']+1),signal.SIGTERM,signals)
        except RuntimeError:pass
        else:raise AssertionError('Wrong startticks permitted signal')
        assert child.poll() is None
        launcher.signal_owned_session(child,identity,signal.SIGTERM,signals);child.wait(timeout=3)
        assert signals==['SIGTERM'] and not launcher.group(child.pid)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=3)
        child.stdout.close()
    checks.append('physical_owned_PID_ticks_PGID_SID_signal_gate_negative_and_positive')
    return checks


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent
    for file in here.glob('*.py'):ast.parse(file.read_text(),filename=str(file))
    subprocess.run(['node','--check',str(here/'node_guard.cjs')],check=True)
    launcher=load('e30_static_launcher',here/'launch.py');C=launcher.C
    assert C.ROOT==here.parents[4] and C.CANDIDATE==here.parent
    assert not any(x in sys.modules for x in ('torch','transformers','numpy','onnxruntime','tokenizers'))
    checks=['AST_Node_syntax_nestedROOT_and_stdlib_only_imports']
    with tempfile.TemporaryDirectory(prefix='e30-source-fixtures-',dir=args.output.parent) as temporary:
        checks.extend(metadata_checks(C,launcher,Path(temporary)))
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
    env = dict(os.environ, E30_GUARD_SYNTHETIC='1')
    env.pop('NODE_OPTIONS', None)
    node = json.loads(subprocess.check_output(['node','-e',script,str(here/'node_guard.cjs')],env=env,text=True))
    assert node['denied'] == 20 and node['native_initializations'] == 0
    checks.append('Node20_DNS_TCP_UDP_HTTP_fetch_send_receive_violations_persist_with_no_native_import')
    clean_env = {k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','E30_GUARD_SYNTHETIC','E30_PROJECT','E30_OUT','E30_PLAN','E30_PLAN_SHA','E30_ADMISSION')}
    denied = subprocess.run(['node','--require',str(here/'node_guard.cjs'),'-e',"throw new Error('UNREACHABLE_NATIVE_WORK');"],env=clean_env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert denied.returncode != 0 and 'Exact phase/source environment missing' in denied.stderr
    checks.append('Node_missing_actual_source_admission_refuses_before_main_script')
    cpu = load('epoch30_static_cpu', here/'cpu_guard.py')
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
    network=load('e30_static_network',here/'network_guard.py')
    assert network.literal_capability_bind(socket.AF_INET6,socket.SOCK_STREAM,0,('::1',0))
    rejected=[('::1',False),('::1',1),('localhost',0),('127.0.0.1',0),('::',0),('::1',0,0,0),['::1',0]]
    class Host(str):pass
    rejected.append((Host('::1'),0))
    assert all(not network.literal_capability_bind(socket.AF_INET6,socket.SOCK_STREAM,0,value) for value in rejected)
    assert not network.literal_capability_bind(socket.AF_INET,socket.SOCK_STREAM,0,('::1',0))
    assert not network.literal_capability_bind(socket.AF_INET6,socket.SOCK_DGRAM,0,('::1',0))
    checks.append('exact_capability_tuple_family_type_port_predicate_only_no_actual_probe')
    caprow={'event':'socket.bind','allowed':True,'family':10,'socket_type':1,'protocol':0,'address':"('::1', 0)",'stack':['synthetic'],
        'source_provenance':{'path':str(C.ROOT/'retrieval/.venv/lib/python3.12/site-packages/urllib3/util/connection.py'),
            'sha256':network.CAPABILITY_SOURCE_SHA,'function':'_has_ipv6','line':127},
        'bind_outcome':'ERROR','close_outcome':'SUCCESS','file_descriptor_after_close':-1}
    assert launcher.capability_invariants({'counters':{network.CAPABILITY_COUNTER:1},'Python_network_events':[caprow]})
    caprow['close_outcome']='PENDING'
    assert not launcher.capability_invariants({'counters':{network.CAPABILITY_COUNTER:1},'Python_network_events':[caprow]})
    assert not launcher.capability_invariants({'counters':{network.CAPABILITY_COUNTER:2},'Python_network_events':[]})
    checks.append('capability_receipt_rejects_unclosed_or_second_allowance_without_bind_syscall')
    counters={'Python_network_operations_attempted':0};guard=network.OfflineGuard(counters,lambda event:None).install()
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    operations=[lambda:sock.bind(('127.0.0.1',0)),lambda:socket.getaddrinfo('example.invalid',80),
        lambda:sock.connect(('127.0.0.1',1)),lambda:sock.send(b'synthetic'),lambda:sock.recv(1),lambda:sock.listen(1),lambda:sock.accept()]
    for operation in operations:
        count=counters['Python_network_operations_attempted']
        try:operation()
        except RuntimeError:pass
        else:raise AssertionError('Forbidden Python networking admitted')
        assert counters['Python_network_operations_attempted']==count+1
    sock.close()
    try:guard.assert_clean()
    except RuntimeError:pass
    else:raise AssertionError('Caught network exceptions erased fatal flag')
    assert counters[network.CAPABILITY_COUNTER]==0
    checks.append('Python7_network_denials_persist_and_no_capability_probe_executed')
    assert not any(x in sys.modules for x in ('torch','transformers','numpy','onnxruntime','tokenizers'))
    report={'schema_version':1,'epoch':30,'status':'PASS_SOURCE_ONLY_RUNTIME_GUARD_PREFLIGHT','checks':checks,'check_count':len(checks),
        'synthetic_Node_network_denials':node['denied'],'synthetic_Python_network_denials':counters['Python_network_operations_attempted'],
        'synthetic_CPU_seccomp_denials':cpu_result['synthetic_denied_affinity_syscalls'],'CPU_child':cpu_result,
        'actual_capability_probes':0,'actual_engineering_or_science_workers':0,'model_tokenizer_native_initializations':0,
        'TRAIN_DEV_CONF_inputs_choices_or_model_weights_reads':0,
        'scope':'Explicit synthetic source/MODEL metadata and mocked ownership only. No genuine admission, input projection, model/tensor decode, dataset choices or dependency capability probe.',
        'files':[{'path':str(file),'bytes':file.stat().st_size,'sha256':C.sha(file)} for file in sorted(here.iterdir()) if file.is_file()]}
    C.put(args.output,report);print(json.dumps({'checks':len(checks),'path':str(args.output),'sha256':C.sha(args.output)}))


if __name__=='__main__':main()
