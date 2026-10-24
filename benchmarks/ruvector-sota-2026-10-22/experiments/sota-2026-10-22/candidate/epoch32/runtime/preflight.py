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


def metadata_checks(C,launcher,temp):
    import copy,hashlib,math,struct,time
    checks=[]
    def fails(call):
        try:call()
        except (ValueError,RuntimeError,FileNotFoundError,TimeoutError):return
        raise AssertionError('Negative fixture admitted')
    for i,text in enumerate(['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}','{"a":Infinity}']):
        file=temp/('bad'+str(i)+'.json');file.write_text(text);fails(lambda:C.read(file))
    for rel in ('../escape','/absolute','a/../b','a//b','a\\b'):fails(lambda:C.checked(rel))
    (temp/'real').mkdir();(temp/'link').symlink_to(temp/'real',target_is_directory=True);fails(lambda:C.no_symlink(temp/'link'/'child'))
    checks.append('ambiguous_nonfinite_JSON_unsafe_paths_and_symlink_components_rejected')
    source_root=C.ROOT;candidate=C.CANDIDATE
    reader=load('e32_pure_readout',candidate/'model.py');worker=load('e32_pure_worker',candidate/'worker.py')
    result=reader.decisions([math.log(2),math.log(3),math.log(5)])
    assert all(abs(a-b)<1e-15 for a,b in zip(result['probabilities_E_C_N'],[.2,.5,.3]))
    assert result['native_typed_argmax']=='Contradiction' and result['native_binary_probabilities_Yes_No']=={'Yes':result['probabilities_E_N_C'][0],'No':sum(result['probabilities_E_N_C'][1:])}
    assert reader.decisions([0,4,4])['native_typed_argmax']=='NotMentioned'
    assert reader.decisions([0,0,-10000])['native_binary_decision']=='No'
    assert reader.decisions([1000,0,-1000])['probabilities_E_C_N']==[1.,0.,0.]
    for values in ([0,1],[float('nan'),0,0],[0,float('inf'),0],[True,0,0]):fails(lambda:reader.decisions(values))
    checks.append('native_ENC_softmax_ECN_permutation_neutral_mass_exactties_extremes_and_nonfinite_rejection')
    def safe_bytes(header,payload):
        text=json.dumps(header,separators=(',',':')).encode();return struct.pack('<Q',len(text))+text+payload
    small=temp/'authored-header.bytes';small.write_bytes(safe_bytes({'synthetic':{'dtype':'F32','shape':[3,2],'data_offsets':[0,24]}},b'\0'*24))
    header,receipt=reader.safe_header(small);assert header['synthetic']['shape']==[3,2] and receipt['data_bytes']==24
    small.write_bytes(safe_bytes({'synthetic':{'dtype':'F32','shape':[3,2],'data_offsets':[1,25]}},b'\0'*24));fails(lambda:reader.safe_header(small))
    small.write_bytes(safe_bytes({'synthetic':{'dtype':'F16','shape':[3,2],'data_offsets':[0,12]}},b'\0'*12));fails(lambda:reader.safe_header(small))
    checks.append('tiny_authored_safe_header_offsets_bytes_dtype_guard_no_safetensors_or_model_import')
    full,refusal=worker.expected_counters(True),worker.expected_counters(False)
    assert full['NLI_forward_calls_completed']==90 and refusal['NLI_forward_calls_completed']==18
    assert full['corpus_batches_attempted']==2 and refusal['corpus_batches_attempted']==1
    assert full['native_index_initializations_completed']==14 and full['native_queries_completed']==30
    assert refusal['native_index_initializations_completed']==6 and refusal['native_queries_completed']==6
    assert full['model_initializations_completed']==refusal['model_initializations_completed']==1
    assert all(full.get(k,0)==refusal.get(k,0)==0 for k in C.phase_zero('dev'))
    checks.append('full90_vs_ENG18_exactcounts_two_corpora_oneworker_frozenstate_noTRAIN_CONF')
    evidence=load('e32_pure_evidence',candidate/'evidence.py')
    bank=C.read(candidate/'engineering.inputs.json');records=evidence.validate_inputs(bank,'engineering')
    assert len(records)==6 and len({r['document_id'] for r in records})==6
    bad=copy.deepcopy(bank);bad['records'][0]['choice']='forbidden';fails(lambda:evidence.validate_inputs(bad,'engineering'))
    bad=copy.deepcopy(bank);bad['records'][0]['document']+='tamper';fails(lambda:evidence.validate_inputs(bad,'engineering'))
    proof=evidence.provenance(records[2]['document'],records[2]['document'],{'selected_source_spans':[(0,len(records[2]['document']))]})
    assert [row['text'] for row in proof['numeric_literals']]==['12'] and proof['semantic_decision_override'] is False
    checks.append('authored_CC0_inputs_exact_hash_order_oraclekey_exclusion_UTF8_numeric_source_proof')
    codec=load('e32_pure_vector',candidate/'vector_codec.py');payload=struct.pack('<384f',1,*([0]*383));block=codec.encode(payload,1)
    assert codec.decode(block)==payload
    bad=copy.deepcopy(block);bad['sha256']='0'*64;fails(lambda:codec.decode(bad))
    script=r'''const assert=require('node:assert/strict'),h=require(process.argv[1]),crypto=require('node:crypto');const v=new Float32Array(384);v[0]=1;const b=h.vectorBytes(v),s=crypto.createHash('sha256').update(b).digest('hex');const block={encoding:'base64',dtype:'float32le',shape:[1,384],bytes:1536,sha256:s,data_base64:b.toString('base64')};assert(h.vectorBytes(h.decode(block)[0]).equals(b));assert(h.compact({id:'0',score:.2,vector:v},[v]).vector_receipt.source_equal_before_stripping);assert.throws(()=>h.compact({id:'0',score:.2,vector:v,metadata:{}},[v]));assert.throws(()=>h.compact({id:'1',score:.2,vector:v},[v]));assert.throws(()=>h.decode({...block,sha256:'0'.repeat(64)}));process.stdout.write('PASS');'''
    assert subprocess.check_output(['node','-e',script,str(candidate/'native_helper.cjs')],text=True)=='PASS'
    checks.append('Python_Node_lossless_f32_source_hit_metadata_identity_no_native_addon')
    # Gate authored expectations after18 synthetic readouts only; no real model/input used.
    saved_worker={key:getattr(worker.C,key) for key in ('ROOT','checked')}
    try:
        worker.C.ROOT=source_root;worker.C.checked=lambda relative:source_root/relative
        corpus={'cases':[]}
        for record in records:
            expected=C.read(candidate/'engineering.oracle.json')['expected_labels'][record['id']]
            logits={'Entailment':[8,0,0],'NotMentioned':[0,8,0],'Contradiction':[0,0,8]}[expected]
            corpus['cases'].append({'id':record['id'],'arms':{arm:{'reader':{**reader.decisions(logits),'actual_logits_shape':[1,3],'pair_tokens':10,'full_pair_tokens':10,'max_pair_tokens':512,'hidden_truncation':False},'joint_pair_tokens':10,'context':{'source_provenance':{'selected_source_provenance':[{'authored_synthetic':True}],'semantic_decision_override':False}}} for arm in ('actual_native','lexical','positional')}})
        oracle=candidate/'engineering.oracle.json';plan={'engineering_oracle_path':str(oracle.relative_to(source_root)),'engineering_oracle_sha256':C.sha(oracle)}
        raw={'counters':dict.fromkeys(full,0),'corpora':{'engineering':corpus,'dev':None}}
        assert worker.engineering_gate(raw,plan,lambda event:None) is True
        raw['corpora']['engineering']['cases'][0]['arms']['actual_native']['reader']['native_typed_argmax']='NotMentioned'
        assert worker.engineering_gate(raw,plan,lambda event:None) is False and raw['corpora']['dev'] is None
        # Optional arm semantic errors do not silently become an additional admission gate.
        raw['corpora']['engineering']['cases'][0]['arms']['actual_native']['reader']['native_typed_argmax']='Entailment'
        raw['corpora']['engineering']['cases'][0]['arms']['lexical']['reader']['native_typed_argmax']='NotMentioned'
        assert worker.engineering_gate(raw,plan,lambda event:None) is True
        checks.append('authored_engineering_native6_gate_after18_readouts_refusal_noDEV_lex_semantics_diagnostic')
    finally:
        for key,value in saved_worker.items():setattr(worker.C,key,value)
    reserve=temp/'reservation';launcher.reserve(reserve,'a'*64,'dev');fails(lambda:launcher.reserve(reserve,'a'*64,'dev'));fails(lambda:launcher.reserve(reserve,'a'*64,'train'))
    fullraw=temp/'raw.json';partial=temp/'raw.partial.json';fullraw.write_text('{"interrupted":');partial.write_text('{"counters":{"attempts":2}}');errors=[]
    f=launcher.load_raw_preserving_failure(fullraw,errors);p=launcher.load_raw_preserving_failure(partial,errors)
    assert errors and fullraw.read_text()=='{"interrupted":' and launcher.select_operation_counters(f,p)==({'attempts':2},'raw.partial.json') and launcher.select_operation_counters({}, {})==(None,'UNKNOWN')
    assert not all(launcher.completion_invariants({'engineering_gate':None,'corpora':None}, {'engineering_rejected_operation_counters':{'dev':refusal}},'dev').values())
    checks.append('exclusive_worker_reservation_malformed_final_partial_UNKNOWN_and_null_early_gate_preserved')
    saved={key:getattr(C,key) for key in ('ROOT','HERE','CANDIDATE','STUDY','owner_lock','proc','read','sha')}
    try:
        C.ROOT=temp/'project';C.CANDIDATE=C.ROOT/'experiments/sota-2026-10-22/candidate/epoch32';C.HERE=C.CANDIDATE/'runtime';C.HERE.mkdir(parents=True)
        C.STUDY=C.ROOT/'experiments/sota-2026-10-22/epoch32';C.STUDY.mkdir(parents=True)
        def identity(file):return {'path':str(file.relative_to(C.ROOT)),'bytes':file.stat().st_size,'sha256':C.sha(file)}
        refs=[]
        for name in ('runtime/common.py','runtime/launch.py','runtime/network_guard.py','runtime/node_guard.cjs','runtime/cpu_guard.py','worker.py','model.py','algorithm.py','evidence.py','context_engine.py','vector_codec.py','native_helper.cjs','MODEL_ASSETS.json','runtime.json','dev.inputs.json','engineering.inputs.json','engineering.oracle.json'):
            file=C.CANDIDATE/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('AUTHORED_SOURCE_METADATA_NO_REAL_INPUTS_OR_TENSORS');refs.append(identity(file))
        for name in ('PRETRAINED_MODEL_SOURCE.json','research/METADATA_ADMISSION.json'):
            file=C.CANDIDATE/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes((candidate/name).read_bytes());refs.append(identity(file))
        policy=C.ROOT/'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json';policy.parent.mkdir(parents=True,exist_ok=True)
        # Fixed inherited policy identity is mocked only for this source-plan fixture, no real archived source body is opened.
        policy.write_text('SYNTHETIC_POLICY_METADATA');policy_sha='c4b3c3243ac089d5966e394f3ead60f57a15f59cc24b496960334124c14dbacd'
        C.sha=lambda file:policy_sha if Path(file)==policy else saved['sha'](file);refs.append(identity(policy))
        freeze=C.STUDY/'source-freeze.json';freeze.write_text(json.dumps({'epoch':32,'kind':C.KIND,'source_checkpoint':C.SOURCE,'entries':refs}));refs.append(identity(freeze))
        plan={'epoch':32,'kind':C.KIND,'source_checkpoint':C.SOURCE,'actual_project':str(C.ROOT),'guardian_scope':str(C.SCOPE),'external_python_environment':str(C.VENV),'model_directory':str(C.MODEL),'data_roles':{'train':[],'dev':C.DEV_IDS,'calibration':[],'confirmation':[]},'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},'pins':refs,'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),'native_worker_path':str((C.CANDIDATE/'native_helper.cjs').relative_to(C.ROOT)),'expected_operation_counters':{'dev':full},'engineering_rejected_operation_counters':{'dev':refusal}}
        for key,file in [('source_freeze',freeze),('runtime_assets_lock',C.CANDIDATE/'runtime.json'),('model_assets_lock',C.CANDIDATE/'MODEL_ASSETS.json'),('pretrained_model_source',C.CANDIDATE/'PRETRAINED_MODEL_SOURCE.json'),('dev_inputs',C.CANDIDATE/'dev.inputs.json'),('engineering_inputs',C.CANDIDATE/'engineering.inputs.json'),('engineering_oracle',C.CANDIDATE/'engineering.oracle.json'),('runtime_policy_addendum',policy)]:plan[key+'_path'],plan[key+'_sha256']=str(file.relative_to(C.ROOT)),C.sha(file)
        plan['pretrained_model_source']=identity(C.CANDIDATE/'PRETRAINED_MODEL_SOURCE.json');planfile=C.STUDY/'plan.json';planfile.write_text(json.dumps(plan));plansha=C.sha(planfile)
        dev=C.ROOT/plan['dev_inputs_path'];dev_reads=[];original_sha=C.sha
        def sha_no_dev(file):
            if Path(file)==dev:dev_reads.append('sha');raise AssertionError('DEV body opened before gate')
            return original_sha(file)
        C.sha=sha_no_dev;C.verify_plan(planfile,plansha,'dev');assert not dev_reads
        C.owner_lock=lambda *args:{'EXPLICIT_MOCK':True}
        admission={'epoch':32,'kind':C.KIND,'phase':'dev','scope':'benchmarks/ruvector-sota-2026-10-22/','verified_actual_remote_readback':True,'plan_sha256':plansha,'source_freeze_sha256':plan['source_freeze_sha256'],'published_source_commit':'b'*40,'pretrained_model_source':plan['pretrained_model_source'],'model_assets_lock_sha256':plan['model_assets_lock_sha256']}
        admissionfile=C.STUDY/'SOURCE_ADMISSION.json';admissionfile.write_text(json.dumps(admission));C.admission(admissionfile,plan,plansha,'dev');assert not dev_reads
        bad=copy.deepcopy(admission);bad['verified_actual_remote_readback']=False;admissionfile.write_text(json.dumps(bad));fails(lambda:C.admission(admissionfile,plan,plansha,'dev'));admissionfile.write_text(json.dumps(admission))
        checks.append('complete_synthetic_plan_SOURCE_model_binding_externalpaths_corpus2_and_DEVbody_deferred')
        claim={'schema_version':1,'epoch':32,'kind':C.KIND,'phase':'dev','plan_sha256':plansha,'source_freeze_sha256':plan['source_freeze_sha256'],'pretrained_model_source_sha256':plan['pretrained_model_source_sha256'],'model_assets_lock_sha256':plan['model_assets_lock_sha256'],'admission_sha256':C.sha(admissionfile),'kernel_boot_id':C.BOOT_ID,'pid_namespace_inode':C.PIDNS_INODE,'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time(),'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
        claimfile=C.STUDY/'DISPATCH_RESERVATION.json';claimfile.write_text(json.dumps(claim));attempt={**claim,'pid':os.getpid(),'startticks':17,'pgid':os.getpid(),'sid':os.getpid(),'verified_launcher_start':True,'uncertain_launcher_start':False}
        C.proc=lambda pid:{'pid':pid,'ticks':17,'pgid':pid,'sid':pid};attemptfile=C.STUDY/'DISPATCH_ATTEMPT.json';attemptfile.write_text(json.dumps(attempt));C.dispatch_proof(plan,plansha,admissionfile,0)
        for key,value in [('startticks',18),('model_assets_lock_sha256','0'*64),('sid',0),('uncertain_launcher_start',True)]:
            attemptfile.write_text(json.dumps({**attempt,key:value}));fails(lambda:C.dispatch_proof(plan,plansha,admissionfile,0))
        attemptfile.unlink();fails(lambda:C.dispatch_proof(plan,plansha,admissionfile,0))
        claimfile.write_text(json.dumps({**claim,'dispatch_monotonic_seconds':time.monotonic()-601}));fails(lambda:C.dispatch_proof(plan,plansha,admissionfile,0))
        checks.append('new_source_asset_dispatch_binding_PIDticks_PGIDSID_uncertainty_expiry_refuse_retry')
    finally:
        for key,value in saved.items():setattr(C,key,value)
    child=subprocess.Popen([sys.executable,'-I','-B','-c',"import time;print('ready',flush=True);time.sleep(30)"],start_new_session=True,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline()=='ready\n';identity=C.proc(child.pid);signals=[]
        fails(lambda:launcher.signal_owned_session(child,dict(identity,ticks=identity['ticks']+1),signal.SIGTERM,signals))
        assert child.poll() is None;launcher.signal_owned_session(child,identity,signal.SIGTERM,signals);child.wait(timeout=3);assert signals==['SIGTERM'] and not launcher.group(child.pid)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=3)
        child.stdout.close()
    checks.append('owned_session_signal_exactPIDticks_negative_positive_cleanup')
    return checks


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent
    for file in here.parent.rglob('*.py'):ast.parse(file.read_text(),filename=str(file))
    subprocess.run(['node','--check',str(here/'node_guard.cjs')],check=True)
    launcher=load('e32_static_launcher',here/'launch.py');C=launcher.C
    assert C.ROOT==here.parents[4] and C.CANDIDATE==here.parent
    assert not any(x in sys.modules for x in ('torch','transformers','numpy','onnxruntime','tokenizers'))
    checks=['AST_Node_syntax_nestedROOT_and_stdlib_only_imports']
    with tempfile.TemporaryDirectory(prefix='e32-source-fixtures-',dir=args.output.parent) as temporary:
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
    env = dict(os.environ, E32_GUARD_SYNTHETIC='1')
    env.pop('NODE_OPTIONS', None)
    node = json.loads(subprocess.check_output(['node','-e',script,str(here/'node_guard.cjs')],env=env,text=True))
    assert node['denied'] == 20 and node['native_initializations'] == 0
    checks.append('Node20_DNS_TCP_UDP_HTTP_fetch_send_receive_violations_persist_with_no_native_import')
    clean_env = {k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','E32_GUARD_SYNTHETIC','E32_PROJECT','E32_OUT','E32_PLAN','E32_PLAN_SHA','E32_ADMISSION')}
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
    network=load('e32_static_network',here/'network_guard.py')
    assert network.literal_capability_bind(socket.AF_INET6,socket.SOCK_STREAM,0,('::1',0))
    rejected=[('::1',False),('::1',1),('localhost',0),('127.0.0.1',0),('::',0),('::1',0,0,0),['::1',0]]
    class Host(str):pass
    rejected.append((Host('::1'),0))
    assert all(not network.literal_capability_bind(socket.AF_INET6,socket.SOCK_STREAM,0,value) for value in rejected)
    assert not network.literal_capability_bind(socket.AF_INET,socket.SOCK_STREAM,0,('::1',0))
    assert not network.literal_capability_bind(socket.AF_INET6,socket.SOCK_DGRAM,0,('::1',0))
    checks.append('exact_capability_tuple_family_type_port_predicate_only_no_actual_probe')
    caprow={'event':'socket.bind','allowed':True,'family':10,'socket_type':1,'protocol':0,'address':"('::1', 0)",'stack':['synthetic'],
        'source_provenance':{'path':str(C.VENV/'lib/python3.12/site-packages/urllib3/util/connection.py'),
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
    report={'schema_version':1,'epoch':32,'status':'PASS_SOURCE_ONLY_RUNTIME_GUARD_PREFLIGHT','checks':checks,'check_count':len(checks),
        'synthetic_Node_network_denials':node['denied'],'synthetic_Python_network_denials':counters['Python_network_operations_attempted'],
        'synthetic_CPU_seccomp_denials':cpu_result['synthetic_denied_affinity_syscalls'],'CPU_child':cpu_result,
        'actual_capability_probes':0,'actual_engineering_or_science_workers':0,'model_tokenizer_native_initializations':0,
        'TRAIN_DEV_CONF_inputs_choices_or_model_weights_reads':0,
        'scope':'Explicit synthetic archived-source/dispatch metadata with fixed historical identity mocks and mocked ownership only. No genuine admission, input projection, model/tensor decode, dataset choices or dependency capability probe.',
        'files':[{'path':str(file),'bytes':file.stat().st_size,'sha256':C.sha(file)} for file in sorted(here.iterdir()) if file.is_file()]}
    C.put(args.output,report);print(json.dumps({'checks':len(checks),'path':str(args.output),'sha256':C.sha(args.output)}))


if __name__=='__main__':main()
