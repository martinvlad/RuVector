"""Synthetic lost-Popen proof/cleanup test; never starts an ML/science worker."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
parser.add_argument('--phase',choices=('dev',),required=True)
parser.add_argument('--mode',choices=('recovered','no_proof','authority_lost','before_popen'),required=True)
parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
spec=importlib.util.spec_from_file_location('e32_lost_popen_fixture',args.runtime/'launch.py')
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L);C=L.C
saved={key:getattr(C,key) for key in ('ROOT','CANDIDATE','STUDY','SCOPE','owner_lock','admission','verify_plan','verify_runtime','dispatch_proof','load_module')}
original_argv=sys.argv[:];original_affinity=os.sched_getaffinity(0)
handlers={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM)}
real_popen=L.subprocess.Popen;children=[];attempts=[]
real_supervisor_identity=L.supervisor_identity
L.supervisor_identity=lambda:{'pid':os.getpid(),'startticks':C.proc(os.getpid())['ticks'],'pgid':os.getpgrp(),'sid':os.getsid(0)}

def lose_return(command,**kwargs):
    attempts.append(True)
    if args.mode in ('recovered','authority_lost'):
        child=real_popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)'],**kwargs)
        children.append(child)
        if args.mode=='authority_lost':return child
    raise InterruptedError('INJECTED_UNRETURNED_POPEN_WITHOUT_MODEL')

try:
    with tempfile.TemporaryDirectory(prefix='lost-popen-fixture-',dir=args.output.parent) as temporary:
        scope=Path(temporary);C.SCOPE=scope;C.ROOT=scope/'project'
        C.CANDIDATE=C.ROOT/'experiments/sota-2026-10-22/candidate/epoch32'
        C.STUDY=C.ROOT/'experiments/sota-2026-10-22/epoch32';C.STUDY.mkdir(parents=True)
        (scope/'owner.json').write_text(json.dumps({'expires_unix':time.time()+3600}))
        plan={'source_freeze_sha256':'a'*64,'pretrained_model_source_sha256':'b'*64,'model_assets_lock_sha256':'c'*64,'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),
            'inference_python':sys.executable,'expected_operation_counters':{'dev':{'NLI_forward_calls_completed':90}},'engineering_rejected_operation_counters':{'dev':{'NLI_forward_calls_completed':18}}}
        plan_path=C.STUDY/'plan.json';plan_path.write_text(json.dumps(plan))
        authority_calls=[]
        def owner_check(*args):
            authority_calls.append(True)
            if args_mode=='authority_lost' and len(authority_calls)>=3:raise RuntimeError('INJECTED_GUARDIAN_AUTHORITY_LOST')
            return {}
        args_mode=args.mode
        C.owner_lock=owner_check;C.admission=lambda *a:({},{});C.verify_plan=lambda *a:plan;C.verify_runtime=lambda *a:None
        def dispatch_mock(*unused):
            claim={'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time()}
            C.put(C.STUDY/'DISPATCH_RESERVATION.json',claim);C.put(C.STUDY/'DISPATCH_ATTEMPT.json',{'SYNTHETIC_TEST_ONLY':True})
            return claim,{}
        C.dispatch_proof=dispatch_mock
        if args.mode=='before_popen':
            def fail_before(*args):raise RuntimeError('INJECTED_SETUP_FAILURE_BEFORE_WORKER_POPEN')
            C.load_module=fail_before
        L.subprocess.Popen=lose_return
        sys.argv=[str(args.runtime/'launch.py'),'--scope',str(scope),'--phase',args.phase,'--plan',str(plan_path),
            '--admission',str(C.STUDY/'SOURCE_ADMISSION.json'),
            '--expected-plan-sha',C.sha(plan_path)]
        with contextlib.redirect_stdout(io.StringIO()):result=L.main()
        out=C.STUDY/('runs/'+args.phase);receipt=C.read(out/'execution.json')
        assert result==2 and len(attempts)==(0 if args.mode=='before_popen' else 1)
        assert receipt['status']=='WORKER_FAILED_OR_TIMEOUT' and receipt['worker_attempts_reserved']==1
        assert receipt['verified_worker_starts']==(1 if args.mode=='authority_lost' else 0)
        assert receipt['uncertain_start'] is (args.mode in ('recovered','no_proof'))
        assert receipt['worker_popen_attempted'] is (args.mode!='before_popen')
        assert receipt['worker_popen_attempts']==(0 if args.mode=='before_popen' else 1)
        assert receipt['worker_start_boundary']==('KNOWN_FAILURE_BEFORE_WORKER_POPEN' if args.mode=='before_popen' else 'WORKER_POPEN_ATTEMPTED')
        assert receipt['raw_operation_counters'] is None
        if args.mode!='authority_lost':assert receipt['exit_code'] is None
        assert receipt['raw_operation_counters_source']=='UNKNOWN' and receipt['allowed_further_phase_workers']==0
        assert (C.STUDY/(args.phase.upper()+'_ATTEMPT_RESERVATION.json')).is_file()
        if args.mode=='recovered':
            proof=receipt['recovered_preexec_child_identity'];assert proof['pid']==children[0].pid and proof['ppid']==os.getpid()
            assert receipt['worker_identity_source']=='durable_preexec_only'
            assert receipt['owned_process_closure_observation']=='OBSERVED'
            assert receipt['owned_live_group_members']==[] and receipt['owned_live_processes_closed'] is True
            assert not L.group(proof['pid'])
            cpu=C.read(out/'worker-cpu-preexec.json');cpu['process_identity']['ppid']=0
            bad=scope/'bad-proof.json';bad.write_text(json.dumps(cpu))
            try:L.recover_preexec_identity(bad)
            except RuntimeError:pass
            else:raise AssertionError('Foreign-parent preexec proof accepted')
        elif args.mode=='authority_lost':
            assert len(authority_calls)>=3 and receipt['owned_live_processes_closed'] is True
            assert receipt['worker_identity_source']=='returned_Popen' and receipt['owned_live_group_members']==[]
            assert receipt['launcher_error']['message']=='INJECTED_GUARDIAN_AUTHORITY_LOST'
        elif args.mode=='before_popen':
            assert receipt['launcher_error']['message']=='INJECTED_SETUP_FAILURE_BEFORE_WORKER_POPEN'
            assert receipt['owned_live_processes_closed'] is True and receipt['owned_live_group_members']==[]
            assert receipt['verified_worker_starts']==0 and receipt['worker_identity'] is None
        else:
            assert receipt['worker_identity_source']=='UNKNOWN' and receipt['worker_identity'] is None
            assert receipt['recovered_preexec_child_identity'] is None and receipt['recovered_preexec_exit_code'] is None
            assert receipt['owned_process_closure_observation']=='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF'
            assert receipt['owned_live_group_members'] is None and receipt['owned_live_processes_closed'] is None
        try:L.reserve(C.STUDY,'a'*64,args.phase)
        except (RuntimeError,FileExistsError):pass
        else:raise AssertionError('Uncertain phase became retryable')
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    L.supervisor_identity=real_supervisor_identity
    L.subprocess.Popen=real_popen
    for child in children:
        if child.poll() is None:child.kill();child.wait(timeout=3)
        for stream in (child.stdout,child.stderr):
            if stream:stream.close()
    for key,value in saved.items():setattr(C,key,value)
    sys.argv=original_argv
    for sig,handler in handlers.items():signal.signal(sig,handler)
    os.sched_setaffinity(0,original_affinity)
assert not any(name in sys.modules for name in ('torch','transformers','numpy','onnxruntime','tokenizers'))
report={'status':'PASS_SYNTHETIC_DETACHED_WORKER_RECOVERY_AUTHORITY_AND_UNCERTAINTY','phase':args.phase,'mode':args.mode,
    'launcher_sha256':hashlib.sha256((args.runtime/'launch.py').read_bytes()).hexdigest(),
    'cpu_guard_sha256':hashlib.sha256((args.runtime/'cpu_guard.py').read_bytes()).hexdigest(),
    'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'synthetic_Popen_API_attempts':len(attempts),'synthetic_stdlib_children':len(children),'actual_science_workers':0,
    'model_tokenizer_native_initializations':0,'data_or_choices_reads':0,'actual_capability_probes':0,
    'all_admission_gates_mocked_for_test_only':True,'no_retry_verified':True,
    'closure_scope':'UNKNOWN_PRESERVED_NOT_FABRICATED' if args.mode=='no_proof' else 'OBSERVED_CLOSED_EXACT_OWNED_SESSION'}
with args.output.open('x') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({'path':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))
