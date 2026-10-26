"""Owner-bound burned SOURCE slot; exactly one supervisor Popen, no retry."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--plan",required=True)
    parser.add_argument("--plan-sha256",required=True);parser.add_argument("--admission",required=True)
    args=parser.parse_args()
    root=Path('/tmp/ruvector-sota-2026-10-22/epoch45-c5608a638ecd/project')
    source=root/'experiments/sota-2026-10-22/runtime/epoch45/common.py'
    spec=importlib.util.spec_from_file_location('e45_dispatch_common',source)
    C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
    plan=C.admit(args.plan,args.plan_sha256,args.admission)
    host=C.host_admission(plan)
    scope=root/'experiments/sota-2026-10-22/epoch45'
    C.require(not(scope/'DISPATCH_ATTEMPT.json').exists() and
              not(scope/'DISPATCH_RESERVATION.json').exists(), 'DISPATCH_ALREADY_RESERVED_NO_RERUN')
    C.require(os.sched_getaffinity(0)=={0,1},'DISPATCH_CPU_AFFINITY')
    dispatch_started=time.monotonic()
    C.put(scope/'DISPATCH_RESERVATION.json',{'schema_version':1,'epoch':45,'kind':C.KIND,'phase':'dev',
        'plan_sha256':args.plan_sha256,'worker_slot_reservation':plan['worker_slot_reservation'],
        'dispatch_monotonic_seconds':dispatch_started,'dispatch_unix':time.time(),
        'reservation_is_execution_count':False,'further_worker_invocations_allowed':False})
    state={'schema_version':1,'epoch':45,'kind':C.KIND,'phase':'dev','plan_sha256':args.plan_sha256,
        'supervisor_popen_attempted':False,'returned_handle':False,'supervisor_identity':None,
        'dispatch_monotonic_seconds':dispatch_started,
        'worker_slot_reservation':plan['worker_slot_reservation'],'errors':[]}
    state['host_admission']=host
    external=C.W/'dispatch-logs';external.mkdir(mode=0o700)
    stdout=(external/'supervisor.stdout').open('xb');stderr=(external/'supervisor.stderr').open('xb')
    try:
        command=[plan['python_executable'],'-I','-B',str(C.HERE/'launch.py'),'--plan',args.plan,
            '--plan-sha256',args.plan_sha256,'--admission',args.admission]
        state['supervisor_popen_attempted']=True
        process=subprocess.Popen(command,cwd=C.W,env=C.child_env(plan),stdout=stdout,stderr=stderr,
            start_new_session=True,close_fds=True)
        state['returned_handle']=True;identity=C.proc(process.pid)
        C.require(identity and identity['pgid']==process.pid and identity['sid']==process.pid,
                  'SUPERVISOR_SESSION_IDENTITY')
        state['supervisor_identity']=C.stable_identity(identity)
        # Deliberately no wait/poll/reap: independent observer requires actual Z0.
    except BaseException as error:
        state['errors'].append({'code':'DISPATCH_FAILED_UNKNOWN_CAPABILITY_CONSUMED','type':type(error).__name__})
    finally:
        stdout.close();stderr.close();C.put(scope/'DISPATCH_ATTEMPT.json',state)
    print(__import__('json').dumps(state,sort_keys=True))
    return 0 if state['returned_handle'] and not state['errors'] else 1


if __name__=='__main__':raise SystemExit(main())
