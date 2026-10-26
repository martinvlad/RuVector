"""Single owner-bound dispatch and immediate frozen observer; no Gold capability."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path('/tmp/ruvector-sota-2026-10-22/epoch43-cab16abb5795/project')
SCOPE=ROOT/'experiments/sota-2026-10-22/epoch43'
W=ROOT.parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def wait_terminal(C,H,identity,deadline):
    while time.monotonic()<deadline:
        C.owner_fence();state=H.snapshot(identity['pid'])
        C.require(state is not None,'SUPERVISOR_ABSENT_EXIT_UNKNOWN')
        C.require(state['ticks']==identity['startticks'] and state['pgid']==identity['pgid']
                  and state['sid']==identity['sid'],'SUPERVISOR_IDENTITY_CHANGED')
        if state['state']=='Z':
            proof=H.terminal(identity['pid'],identity['startticks'],require_wait_zero=True)
            C.require(proof['absent'] is False and proof['known_exit_status']==0
                      and proof['terminal_resources_zero'] is True,'SUPERVISOR_EXIT_NOT_PROVED_ZERO')
            return proof
        time.sleep(0.05)
    raise RuntimeError('OUTER_OBSERVATION_DEADLINE')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True)
    parser.add_argument('--plan-sha256',required=True);parser.add_argument('--admission',required=True)
    args=parser.parse_args();started=time.monotonic();deadline=started+595
    def timeout(signum,frame):raise TimeoutError('OUTER_WHOLE_BOUND')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,595)
    result={'schema_version':1,'epoch':43,'kind':'REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT',
      'phase':'dev','plan_sha256':args.plan_sha256,'status':'FAILED_NO_GOLD',
      'dispatcher_popen_attempted':False,'dispatcher_returncode':None,
      'supervisor_identity':None,'supervisor_wait_or_reap_attempted':False,
      'observer_popen_attempted':False,'observer_returncode':None,
      'automatic_retry':False,'gold_calls':0,'errors':[]}
    C=None;child=None;streams=[];rc=1
    try:
        # Authenticate the common loader before importing executable source.
        plan_path=Path(args.plan)
        if plan_path!=SCOPE/'plan.json' or hashlib.sha256(plan_path.read_bytes()).hexdigest()!=args.plan_sha256:
            raise RuntimeError('OUTER_PLAN_IDENTITY')
        plan=json.loads(plan_path.read_text());freeze_path=ROOT/plan['source_freeze']['path']
        if hashlib.sha256(freeze_path.read_bytes()).hexdigest()!=plan['source_freeze']['sha256']:
            raise RuntimeError('OUTER_FREEZE_IDENTITY')
        pins=json.loads(freeze_path.read_text())['files']
        path=ROOT/'experiments/sota-2026-10-22/runtime/epoch43/common.py'
        row=next(r for r in pins if ROOT/r['path']==path)
        if path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise RuntimeError('OUTER_COMMON_SOURCE_IDENTITY')
        C=load('e43_outer_common',path);bound=C.admit(args.plan,args.plan_sha256,args.admission)
        C.require(os.sched_getaffinity(0)=={0,1},'OUTER_CPU_AFFINITY')
        C.require(time.monotonic()<deadline,'OUTER_PREPARATION_DEADLINE')
        C.put(SCOPE/'OUTER_RUNNER_ATTEMPT.json',{'epoch':43,'plan_sha256':args.plan_sha256,
          'worker_slot_reservation':bound['worker_slot_reservation'],'before_dispatcher_Popen':True,
          'outer_started_monotonic_seconds':started,'automatic_retry':False})
        logs=C.no_symlink(W/'outer-monitor-logs');logs.mkdir(mode=0o700,exist_ok=True)
        def command(script):
            return [bound['python_executable'],'-I','-B',str(script),'--plan',args.plan,
                    '--plan-sha256',args.plan_sha256,'--admission',args.admission]
        def launch(script,label):
            C.owner_fence();C.require(time.monotonic()<deadline,'OUTER_CHILD_DEADLINE')
            out=(logs/('outer.'+label+'.stdout')).open('xb')
            err=(logs/('outer.'+label+'.stderr')).open('xb');streams.extend([out,err])
            return subprocess.Popen(command(script),cwd=W,env=C.child_env(bound),
                                    stdout=out,stderr=err,close_fds=True)
        result['dispatcher_popen_attempted']=True
        child=launch(SCOPE/'preparation/dispatch_once.py','dispatch')
        while child.poll() is None:
            C.owner_fence();C.require(time.monotonic()<deadline,'OUTER_DISPATCH_DEADLINE');time.sleep(0.05)
        result['dispatcher_returncode']=child.returncode
        C.require(child.returncode==0,'OUTER_DISPATCH_FAILED_NO_RERUN');child=None
        dispatch=C.read(SCOPE/'DISPATCH_ATTEMPT.json')
        C.require(dispatch['returned_handle'] is True and dispatch['errors']==[]
                  and dispatch['plan_sha256']==args.plan_sha256,'OUTER_DISPATCH_IDENTITY_UNKNOWN')
        identity=dispatch['supervisor_identity'];result['supervisor_identity']=identity
        H=C.load_module('e43_outer_closure',ROOT/'experiments/sota-2026-10-22/audit/epoch43/closure_metadata.py')
        result['terminal_proof']=wait_terminal(C,H,identity,deadline)
        result['observer_popen_attempted']=True
        child=launch(ROOT/'experiments/sota-2026-10-22/audit/epoch43/observer.py','observer')
        while child.poll() is None:
            C.owner_fence();C.require(time.monotonic()<deadline,'OUTER_OBSERVER_DEADLINE');time.sleep(0.05)
        result['observer_returncode']=child.returncode
        C.require(child.returncode==0,'OUTER_OBSERVER_FAILED_NO_GOLD');child=None
        physical=C.read(SCOPE/'SUPERVISOR_OBSERVED_CLOSURE.json')
        C.require(physical['physical_closure_passed'] is True and
                  physical['source_plan_sha256']==args.plan_sha256,'OUTER_PHYSICAL_PROOF')
        result['physical_closure']=C.ref(SCOPE/'SUPERVISOR_OBSERVED_CLOSURE.json')
        result['status']='DISPATCH_AND_FROZEN_OBSERVER_CLOSED_NO_GOLD';rc=0
    except BaseException as error:
        result['errors'].append({'code':'OUTER_STAGE_FAILED_NO_RERUN','type':type(error).__name__})
    finally:
        signal.setitimer(signal.ITIMER_REAL,max(0.001,started+600-time.monotonic()))
        if child is not None and child.poll() is None:
            # Only this direct dispatcher/observer child; NEVER the supervisor or its group.
            child.terminate()
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=1)
            result['direct_child_cleanup_returncode']=child.returncode
        for stream in streams:stream.close()
        result['wall_seconds_before_capture']=time.monotonic()-started
        result['whole_outer_deadline_seconds']=600
        if result['wall_seconds_before_capture']>595:rc=1;result['status']='FAILED_NO_GOLD'
        if C is not None:C.put(SCOPE/'OUTER_RUNNER_EXECUTION.json',result)
        else:
            # Do not write an unauthenticated project; retain only sanitized stderr.
            print(json.dumps(result,sort_keys=True))
        captured=time.monotonic()
        if captured-started>600:rc=1
        signal.setitimer(signal.ITIMER_REAL,0)
        print(json.dumps({'outer_capture_fsync_returned_monotonic_seconds':captured,
              'outer_wall_including_capture_seconds':captured-started,'exit_code':rc},sort_keys=True))
    return rc


if __name__=='__main__':raise SystemExit(main())
