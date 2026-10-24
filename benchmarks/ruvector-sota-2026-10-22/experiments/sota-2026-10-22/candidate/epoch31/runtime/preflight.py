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
    import hashlib
    import struct
    import time
    checks=[]
    def fails(call):
        try:call()
        except (ValueError,RuntimeError,FileNotFoundError,TimeoutError):return
        raise AssertionError('Negative metadata fixture was admitted')
    for i,text in enumerate(['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}','{"a":Infinity}']):
        file=temp/('bad'+str(i)+'.json');file.write_text(text);fails(lambda:C.read(file))
    for relative in ('../escape','/absolute','a/../b','a//b','a\\b'):fails(lambda:C.checked(relative))
    (temp/'real').mkdir();(temp/'link').symlink_to(temp/'real',target_is_directory=True)
    fails(lambda:C.no_symlink(temp/'link'/'child'))
    checks.append('duplicate_nonfinite_JSON_unsafe_paths_and_symlink_components_rejected')
    reserved=temp/'reservation-test';out=launcher.reserve(reserved,'a'*64,'dev')
    assert C.read(reserved/'DEV_ATTEMPT_RESERVATION.json')['owned_workers_reserved']==1
    fails(lambda:launcher.reserve(reserved,'a'*64,'dev'));fails(lambda:launcher.reserve(reserved,'a'*64,'train'))
    checks.append('sole_DEV_exclusive_fsynced_reservation_refuses_retry_and_TRAIN')
    full,partial=temp/'raw.json',temp/'raw.partial.json';full.write_text('{"interrupted":');partial.write_text('{"counters":{"attempts":3}}')
    errors=[];raw=launcher.load_raw_preserving_failure(full,errors);checkpoint=launcher.load_raw_preserving_failure(partial,errors)
    assert full.read_bytes()==b'{"interrupted":' and errors
    assert launcher.select_operation_counters(raw,checkpoint)==({'attempts':3},'raw.partial.json')
    assert launcher.select_operation_counters({}, {})==(None,'UNKNOWN')
    assert launcher.select_operation_counters({'counters':{'a':5}},checkpoint)==({'a':5},'raw.json')
    checks.append('malformed_final_bytes_and_partial_counts_preserved_absence_UNKNOWN')
    worker=load('e31_pure_worker_fixture',C.CANDIDATE/'worker.py')
    model=load('e31_pure_archived_model_fixture',C.CANDIDATE/'model.py')
    counts=worker.expected_counters('dev')
    assert counts['NLI_forward_calls_completed']==96 and counts['original_DEV_forward_calls_completed']==24 and counts['adapted_DEV_forward_calls_completed']==72
    assert counts['native_queries_completed']==24 and counts['native_index_initializations_completed']==8
    assert all(counts.get(name,0)==0 for name in C.phase_zero('dev'))
    fails(lambda:worker.expected_counters('train'))
    assert worker.A.TRAIN_DOCUMENT_IDS==() and len(worker.A.DEV_CASE_IDS)==24
    assert worker.A.ARCHIVED_TRAINING_ALGORITHM['seed']==30030
    assert model._module.A.ALGORITHM==worker.A.ARCHIVED_TRAINING_ALGORITHM
    dev_ast=ast.parse((C.CANDIDATE/'worker.py').read_text())
    dev_fn=next(x for x in dev_ast.body if isinstance(x,ast.FunctionDef) and x.name=='dev')
    calls=[x.func.attr for x in sorted((x for x in ast.walk(dev_fn) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)),key=lambda x:(x.lineno,x.col_offset))]
    assert calls.index('score_original') < calls.index('load_adaptation') < calls.index('score_adapted')
    assert not any(isinstance(x,ast.FunctionDef) and x.name=='train' for x in dev_ast.body)
    checks.append('archived_E30_algorithm_seed_model_unchanged_DEV96_ordered24_before_load_then72_active_TRAINzero')
    codec=load('e31_pure_vector_fixture',C.CANDIDATE/'vector_codec.py')
    payload=struct.pack('<384f',1,*([0]*383));block=codec.encode(payload,1)
    assert codec.decode(block)==payload
    bad=copy.deepcopy(block);bad['sha256']='0'*64;fails(lambda:codec.decode(bad))
    bad=codec.encode(struct.pack('<384f',float('nan'),*([0]*383)),1);fails(lambda:codec.decode(bad))
    bad=codec.encode(struct.pack('<384f',2,*([0]*383)),1);fails(lambda:codec.decode(bad))
    script=r'''const assert=require('node:assert/strict'),h=require(process.argv[1]),crypto=require('node:crypto');const v=new Float32Array(384);v[0]=1;const b=h.vectorBytes(v),s=crypto.createHash('sha256').update(b).digest('hex');const block={encoding:'base64',dtype:'float32le',shape:[1,384],bytes:1536,sha256:s,data_base64:b.toString('base64')};assert(h.vectorBytes(h.decode(block)[0]).equals(b));const c=h.compact({id:'0',score:0.2,vector:v},[v]);assert.equal(c.vector_receipt.source_equal_before_stripping,true);assert.throws(()=>h.compact({id:'0',score:0.2,vector:v,metadata:{}},[v]));assert.throws(()=>h.compact({id:'1',score:0.2,vector:v},[v]));assert.throws(()=>h.decode({...block,sha256:'0'.repeat(64)}));process.stdout.write('PASS');'''
    assert subprocess.check_output(['node','-e',script,str(C.CANDIDATE/'native_helper.cjs')],text=True)=='PASS'
    checks.append('lossless_f32le_Python_Node_roundtrip_hash_finite_norm_and_native_hit_source_guards_no_addon')
    evidence=load('e31_pure_source_evidence_fixture',C.CANDIDATE/'evidence.py')
    records=[]
    for did in C.DEV_IDS:
        for hid in ('nda-17','nda-7','nda-3'):
            document='Authored synthetic £2,000.50 on 2024; Δ.\nSecond authored sentence.'
            hypothesis='Authored synthetic '+hid
            payload=json.dumps({'document':document,'hypothesis':hypothesis},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
            records.append({'id':f'original-contractnli:train:epoch31:dev:{did}:{hid}','document_id':did,'hypothesis_id':hid,'document':document,'hypothesis':hypothesis,'input_sha256':hashlib.sha256(payload).hexdigest()})
    bank={'schema_version':1,'epoch':31,'role':'dev','records':records}
    assert evidence.validate_inputs(bank,'dev')==records
    bad=copy.deepcopy(bank);bad['records'][0]['choice']='Synthetic prohibited field';fails(lambda:evidence.validate_inputs(bad,'dev'))
    bad=copy.deepcopy(bank);bad['records'][0]['input_sha256']='0'*64;fails(lambda:evidence.validate_inputs(bad,'dev'))
    bad=copy.deepcopy(bank);bad['records'][0],bad['records'][1]=bad['records'][1],bad['records'][0];fails(lambda:evidence.validate_inputs(bad,'dev'))
    document=records[0]['document'];proof=evidence.provenance(document,document,{'selected_source_spans':[(0,len(document))]})
    assert [x['text'] for x in proof['numeric_literals']]==['2,000.50','2024'] and all(x['retained'] for x in proof['numeric_literals'])
    assert proof['source_text_normalized'] is False and proof['semantic_decision_override'] is False
    checks.append('authored_only_inputs_exact24_order_hash_no_gold_keys_and_UTF8_numeric_literal_provenance')
    source_root=C.ROOT
    saved_plan={key:getattr(C,key) for key in ('ROOT','HERE','CANDIDATE','STUDY')}
    try:
        C.ROOT=temp/'plan-project';C.CANDIDATE=C.ROOT/'experiments/sota-2026-10-22/candidate/epoch31';C.HERE=C.CANDIDATE/'runtime';C.HERE.mkdir(parents=True)
        C.STUDY=C.ROOT/'experiments/sota-2026-10-22/epoch31';C.STUDY.mkdir(parents=True)
        def identity(file):return {'path':str(file.relative_to(C.ROOT)),'bytes':file.stat().st_size,'sha256':C.sha(file)}
        refs=[]
        for file in [*(C.HERE/x for x in ('common.py','launch.py','network_guard.py','node_guard.cjs','cpu_guard.py')),C.CANDIDATE/'worker.py',C.CANDIDATE/'native_helper.cjs',C.CANDIDATE/'dev.json',C.CANDIDATE/'runtime.json',C.CANDIDATE/'bart-lock.json',C.STUDY/'ARCHIVED_MODEL_SEAL.json']:
            file.write_text('AUTHORED_SYNTHETIC_METADATA_NO_INPUTS_OR_TENSORS\n');refs.append(identity(file))
        for relative in [C.ORIGINAL_READER,'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json',*(f'experiments/sota-2026-10-22/candidate/epoch30/{x}' for x in ('algorithm.py','model.py','parameter_codec.py'))]:
            file=C.ROOT/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes((source_root/relative).read_bytes());refs.append(identity(file))
        freeze=C.STUDY/'source-freeze.json';freeze.write_text(json.dumps({'epoch':31,'kind':C.KIND,'source_checkpoint':C.SOURCE,'entries':refs}));refs.append(identity(freeze))
        plan={'epoch':31,'kind':C.KIND,'source_checkpoint':C.SOURCE,'actual_project':str(C.ROOT),'data_roles':{'train':[],'dev':C.DEV_IDS,'calibration':[],'confirmation':[]},'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},'pins':refs,'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),'native_worker_path':str((C.CANDIDATE/'native_helper.cjs').relative_to(C.ROOT)),'trained_parameters_path':'experiments/sota-2026-10-22/epoch30/runs/train/trained-parameters.public.json','expected_operation_counters':{'dev':{'NLI_forward_calls_completed':96}}}
        for key,file in [('dev_inputs',C.CANDIDATE/'dev.json'),('runtime_assets_lock',C.CANDIDATE/'runtime.json'),('source_freeze',freeze),('bart_assets_lock',C.CANDIDATE/'bart-lock.json'),('archived_model_seal',C.STUDY/'ARCHIVED_MODEL_SEAL.json'),('original_reader',C.ROOT/C.ORIGINAL_READER),('runtime_policy_addendum',C.ROOT/'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json')]:
            plan[key+'_path'],plan[key+'_sha256']=str(file.relative_to(C.ROOT)),C.sha(file)
        plan['archived_model_seal']=identity(C.STUDY/'ARCHIVED_MODEL_SEAL.json')
        file=C.STUDY/'plan.json';file.write_text(json.dumps(plan));C.verify_plan(file,C.sha(file),'dev')
        bad=copy.deepcopy(plan);bad['data_roles']['train']=[237];file.write_text(json.dumps(bad));fails(lambda:C.verify_plan(file,C.sha(file),'dev'))
        bad=copy.deepcopy(plan);bad['limits']['DEV_worker_attempts']=2;file.write_text(json.dumps(bad));fails(lambda:C.verify_plan(file,C.sha(file),'dev'))
        file.write_text(json.dumps(plan));fails(lambda:C.verify_plan(file,C.sha(file),'train'))
        (C.CANDIDATE/'worker.py').write_text('TAMPERED');fails(lambda:C.verify_plan(file,C.sha(file),'dev'))
        checks.append('complete_synthetic_DEV_source_plan_rejects_active_TRAIN_second_attempt_unpinned_tamper')
    finally:
        for key,value in saved_plan.items():setattr(C,key,value)
    saved={key:getattr(C,key) for key in ('ROOT','HERE','CANDIDATE','STUDY','owner_lock','verify_ref','read','proc')}
    try:
        C.ROOT=temp/'project';C.CANDIDATE=C.ROOT/'experiments/sota-2026-10-22/candidate/epoch31';C.HERE=C.CANDIDATE/'runtime'
        C.STUDY=C.ROOT/'experiments/sota-2026-10-22/epoch31';C.STUDY.mkdir(parents=True)
        def ref(file):return {'path':str(file.relative_to(C.ROOT)),'bytes':file.stat().st_size,'sha256':C.sha(file)}
        old=C.ROOT/'experiments/sota-2026-10-22/epoch30';train=old/'runs/train';train.mkdir(parents=True)
        # Explicit metadata-only mocks for immutable historical hashes: no real artifact, tensor, TRAIN raw or DEV input is opened.
        artifact={'path':str((train/'trained-parameters.public.json').relative_to(C.ROOT)),'bytes':5950520,'sha256':'46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'}
        oldplan={'path':str((old/'plan.json').relative_to(C.ROOT)),'bytes':1,'sha256':'d6c46944bbac2cb8ef65a51e68d927e10b869123004f941d56292cef1e0bd94b'}
        oldfreeze={'path':str((old/'source-freeze.json').relative_to(C.ROOT)),'bytes':1,'sha256':'179a0463338808f2d39925fe480a02c4eb144ee634044594a8c68ca51a35e14a'}
        oldraw={'path':str((train/'raw.json').relative_to(C.ROOT)),'bytes':1,'sha256':'c'*64}
        mocked={row['path']:row for row in (artifact,oldplan,oldfreeze,oldraw)}
        def synthetic_verify(row,*args,**kwargs):
            if row.get('path') in mocked:
                assert row==mocked[row['path']];return C.ROOT/row['path']
            return saved['verify_ref'](row,*args,**kwargs)
        C.verify_ref=synthetic_verify
        def no_sensitive_read(path):
            if str(Path(path).relative_to(C.ROOT)) in mocked or Path(path).name=='dev.inputs.json':raise AssertionError('Opaque/DEV body parsed')
            return saved['read'](path)
        C.read=no_sensitive_read;C.owner_lock=lambda *a:{'MOCKED_FOR_METADATA_TEST_ONLY':True}
        execution={'epoch':30,'kind':'REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC','phase':'train','status':'WORKER_COMPLETED','worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,'owned_live_processes_closed':True,'owned_live_group_members':[],'raw_operation_counters_source':'raw.json','operation_counts_complete':True,'raw_sha256':oldraw['sha256'],'raw_bytes':1,'raw_operation_counters':dict.fromkeys(('TRAIN_forward_calls_completed','backward_calls_completed','optimizer_steps_completed','training_steps'),24)}
        exe=train/'execution.json';exe.write_text(json.dumps(execution))
        seal={'schema_version':1,'epoch':31,'kind':C.KIND,'status':'ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED','source_checkpoint':C.SOURCE,'parameter_artifact':artifact,'train_raw':oldraw,'train_execution':ref(exe),'original_source_plan':oldplan,'original_source_freeze':oldfreeze,'historical_training_epoch':30,'historical_training_document_ids':C.HISTORICAL_TRAIN_IDS,'data_roles':{'train':[],'dev':C.DEV_IDS,'calibration':[],'confirmation':[]},'hypotheses':['nda-17','nda-7','nda-3']}
        report={'schema_version':1,'epoch':30,'kind':'REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC','train_integrity_passed':True,'evidence':{key:seal[value] for key,value in {'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution','plan':'original_source_plan','freeze':'original_source_freeze'}.items()}}
        reportfile=C.ROOT/'experiments/sota-2026-10-22/audit/epoch30/train-integrity.json';reportfile.parent.mkdir(parents=True);reportfile.write_text(json.dumps(report));seal['independent_training_report']=ref(reportfile)
        sealfile=C.STUDY/'ARCHIVED_MODEL_SEAL.json';sealfile.write_text(json.dumps(seal))
        plan={'trained_parameters_path':artifact['path'],'source_freeze_sha256':'f'*64,'archived_model_seal':ref(sealfile),'archived_model_seal_sha256':ref(sealfile)['sha256']}
        admission={'epoch':31,'kind':C.KIND,'phase':'dev','scope':'benchmarks/ruvector-sota-2026-10-22/','verified_actual_remote_readback':True,'plan_sha256':'a'*64,'source_freeze_sha256':'f'*64,'published_source_commit':'b'*40,'archived_model_seal':plan['archived_model_seal'],'parameter_artifact':artifact}
        admissionfile=C.STUDY/'SOURCE_ADMISSION.json';admissionfile.write_text(json.dumps(admission));C.admission(admissionfile,plan,'a'*64,'dev')
        checks.append('SOURCE_archived15key_gate_opaque_hash_mocks_preserves_historical_E30_ref_chain_before_DEVbody')
        def rewrite(steps=24,integrity=True):
            execution['raw_operation_counters']['training_steps']=steps;exe.write_text(json.dumps(execution));seal['train_execution']=ref(exe)
            report['evidence']['execution']=seal['train_execution'];report['train_integrity_passed']=integrity;reportfile.write_text(json.dumps(report));seal['independent_training_report']=ref(reportfile)
            sealfile.write_text(json.dumps(seal));plan['archived_model_seal']=ref(sealfile);admission['archived_model_seal']=ref(sealfile);admissionfile.write_text(json.dumps(admission))
        rewrite(23);fails(lambda:C.admission(admissionfile,plan,'a'*64,'dev'))
        rewrite(24,False);fails(lambda:C.admission(admissionfile,plan,'a'*64,'dev'))
        rewrite();C.admission(admissionfile,plan,'a'*64,'dev')
        bad=copy.deepcopy(admission);bad['verified_actual_remote_readback']=False;admissionfile.write_text(json.dumps(bad));fails(lambda:C.admission(admissionfile,plan,'a'*64,'dev'))
        admissionfile.write_text(json.dumps(admission));fails(lambda:C.admission(admissionfile,plan,'a'*64,'train'))
        checks.append('archived_gate_rejects23steps_false_independent_integrity_unverified_SOURCE_and_currentTRAIN')
        C.read=saved['read'];plan['archived_model_seal_sha256']=plan['archived_model_seal']['sha256']
        claim={'schema_version':1,'epoch':31,'kind':C.KIND,'phase':'dev','plan_sha256':'a'*64,'source_freeze_sha256':plan['source_freeze_sha256'],'archived_model_seal_sha256':plan['archived_model_seal_sha256'],'admission_sha256':C.sha(admissionfile),'kernel_boot_id':C.BOOT_ID,'pid_namespace_inode':C.PIDNS_INODE,'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time(),'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
        claimfile=C.STUDY/'DISPATCH_RESERVATION.json';claimfile.write_text(json.dumps(claim))
        attempt={**claim,'pid':os.getpid(),'startticks':17,'pgid':os.getpid(),'sid':os.getpid(),'verified_launcher_start':True,'uncertain_launcher_start':False}
        C.proc=lambda pid:{'pid':pid,'ticks':17,'pgid':pid,'sid':pid}
        attemptfile=C.STUDY/'DISPATCH_ATTEMPT.json';attemptfile.write_text(json.dumps(attempt));C.dispatch_proof(plan,'a'*64,admissionfile,0)
        for key,value in [('startticks',18),('plan_sha256','0'*64),('sid',0),('uncertain_launcher_start',True)]:
            bad={**attempt,key:value};attemptfile.write_text(json.dumps(bad));fails(lambda:C.dispatch_proof(plan,'a'*64,admissionfile,0))
        attemptfile.write_text(json.dumps(attempt));attemptfile.unlink();fails(lambda:C.dispatch_proof(plan,'a'*64,admissionfile,0))
        bad={**claim,'dispatch_monotonic_seconds':time.monotonic()-601};claimfile.write_text(json.dumps(bad));fails(lambda:C.dispatch_proof(plan,'a'*64,admissionfile,0))
        checks.append('detached_dispatch_source_clocks_PIDticks_PGIDSID_gate_rejects_uncertain_missing_expired_no_retry')
    finally:
        for key,value in saved.items():setattr(C,key,value)
    child=subprocess.Popen([sys.executable,'-I','-B','-c',"import time;print('ready',flush=True);time.sleep(30)"],start_new_session=True,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline()=='ready\n';identity=C.proc(child.pid);signals=[]
        fails(lambda:launcher.signal_owned_session(child,dict(identity,ticks=identity['ticks']+1),signal.SIGTERM,signals))
        assert child.poll() is None;launcher.signal_owned_session(child,identity,signal.SIGTERM,signals);child.wait(timeout=3)
        assert signals==['SIGTERM'] and not launcher.group(child.pid)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=3)
        child.stdout.close()
    checks.append('physical_owned_PIDticks_PGIDSID_signal_gate_wrong_identity_refused_exact_child_closed')
    return checks


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent
    for file in here.parent.rglob('*.py'):ast.parse(file.read_text(),filename=str(file))
    subprocess.run(['node','--check',str(here/'node_guard.cjs')],check=True)
    launcher=load('e31_static_launcher',here/'launch.py');C=launcher.C
    assert C.ROOT==here.parents[4] and C.CANDIDATE==here.parent
    assert not any(x in sys.modules for x in ('torch','transformers','numpy','onnxruntime','tokenizers'))
    checks=['AST_Node_syntax_nestedROOT_and_stdlib_only_imports']
    with tempfile.TemporaryDirectory(prefix='e31-source-fixtures-',dir=args.output.parent) as temporary:
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
    env = dict(os.environ, E31_GUARD_SYNTHETIC='1')
    env.pop('NODE_OPTIONS', None)
    node = json.loads(subprocess.check_output(['node','-e',script,str(here/'node_guard.cjs')],env=env,text=True))
    assert node['denied'] == 20 and node['native_initializations'] == 0
    checks.append('Node20_DNS_TCP_UDP_HTTP_fetch_send_receive_violations_persist_with_no_native_import')
    clean_env = {k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','E31_GUARD_SYNTHETIC','E31_PROJECT','E31_OUT','E31_PLAN','E31_PLAN_SHA','E31_ADMISSION')}
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
    network=load('e31_static_network',here/'network_guard.py')
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
    report={'schema_version':1,'epoch':31,'status':'PASS_SOURCE_ONLY_RUNTIME_GUARD_PREFLIGHT','checks':checks,'check_count':len(checks),
        'synthetic_Node_network_denials':node['denied'],'synthetic_Python_network_denials':counters['Python_network_operations_attempted'],
        'synthetic_CPU_seccomp_denials':cpu_result['synthetic_denied_affinity_syscalls'],'CPU_child':cpu_result,
        'actual_capability_probes':0,'actual_engineering_or_science_workers':0,'model_tokenizer_native_initializations':0,
        'TRAIN_DEV_CONF_inputs_choices_or_model_weights_reads':0,
        'scope':'Explicit synthetic archived-source/dispatch metadata with fixed historical identity mocks and mocked ownership only. No genuine admission, input projection, model/tensor decode, dataset choices or dependency capability probe.',
        'files':[{'path':str(file),'bytes':file.stat().st_size,'sha256':C.sha(file)} for file in sorted(here.iterdir()) if file.is_file()]}
    C.put(args.output,report);print(json.dumps({'checks':len(checks),'path':str(args.output),'sha256':C.sha(args.output)}))


if __name__=='__main__':main()
