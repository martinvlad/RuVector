"""Once-only post-ALL-fence600s and actual stable-Z0 supervisor observer."""
import argparse
import importlib.util
import os
from pathlib import Path
import time


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m);return m


def evaluate(C,H,plan):
    scope=C.ROOT/'experiments/sota-2026-10-22/epoch47'
    paths={'dispatch_attempt':scope/'DISPATCH_ATTEMPT.json','reservation':scope/'DISPATCH_RESERVATION.json',
           'execution':scope/'runs/dev/execution.json','completion':scope/'SUPERVISOR_COMPLETION.json'}
    values={k:C.read(p)for k,p in paths.items()};evidence={k:C.ref(p)for k,p in paths.items()}
    d,r,e,c=(values[k]for k in('dispatch_attempt','reservation','execution','completion'))
    C.require(all(x['plan_sha256']==plan['_plan_sha']for x in values.values()),'CLOSURE_PLAN_MISMATCH')
    C.require(d['returned_handle'] is True and d['supervisor_identity'] is not None,'UNKNOWN_SUPERVISOR_POPEN')
    C.require(e['worker_popen_attempted'] is False or e['worker_returned_handle'] is True,
              'UNKNOWN_WORKER_POPEN_NO_GOLD')
    identity=d['supervisor_identity']
    C.require(c['supervisor_identity']==e['supervisor_identity']==identity,'SUPERVISOR_IDENTITY_CAPTURE')
    groups={identity['pgid'],identity['sid']}
    if e.get('worker_identity'):groups.update([e['worker_identity']['pgid'],e['worker_identity']['sid']])
    first=H.terminal(identity['pid'],identity['startticks'],require_wait_zero=True)
    C.require(first.get('absent') is False,'ABSENT_SUPERVISOR_EXIT_UNKNOWN_NO_GOLD')
    first_groups=H.groups_closed(groups)
    # Recheck every source, owner, reservation and physical resource fence.
    C.admit(str(scope/'plan.json'),plan['_plan_sha'],plan['_dispatch_admission_path'])
    C.require(os.readlink('/proc/self/ns/pid')==C.owner_fence(plan)['PID_namespace'],'OBSERVER_NAMESPACE')
    for k,p in paths.items():C.require(C.ref(p)==evidence[k],'CLOSURE_EVIDENCE_CHANGED')
    second=H.terminal(identity['pid'],identity['startticks'],require_wait_zero=True)
    second_groups=H.groups_closed(groups)
    worker_groups=set()
    if e.get('worker_identity'):worker_groups.update([e['worker_identity']['pgid'],e['worker_identity']['sid']])
    worker_members=H.groups_closed(worker_groups)
    C.require(worker_members==[],'OWNED_WORKER_GROUP_NOT_EMPTY')
    C.require(first==second,'SUPERVISOR_CHANGED_AFTER_SOURCE_FENCE')
    observed=time.monotonic()
    bound=observed-r['dispatch_monotonic_seconds']
    C.require(0<=bound<=600,'WHOLE_BATCH_PHYSICAL_BOUND_EXCEEDED')
    return {'schema_version':1,'epoch':47,'kind':C.KIND,'phase':'dev',
        'source_plan_sha256':plan['_plan_sha'],'physical_closure_passed':True,
        'physical_supervisor_closed':True,'unknown_physical_ownership':False,
        'owned_worker_group_members':worker_members,
        'kernel_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'pid_namespace_inode':os.stat('/proc/self/ns/pid').st_ino,
        'evidence':evidence,'physical_supervisor_absent':False,'observed_supervisor_state':'Z',
        'observed_supervisor_exit_wait_status':0,
        'supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE',
        'supervisor_identity':identity,'supervisor_terminal_proof':second,
        'owned_process_group_ids':sorted(groups),'first_group_fence':first_groups,
        'final_group_fence':second_groups,'owned_live_processes_closed':True,
        'observed_closed_by_monotonic_seconds':observed,
        'dispatch_monotonic_seconds':r['dispatch_monotonic_seconds'],
        'whole_batch_physical_upper_bound_seconds':bound,
        'model_or_tokenizer_or_native_or_gold_calls':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--admission',required=True);args=p.parse_args()
    root=Path('/tmp/ruvector-sota-2026-10-22/epoch47-143d1a78ea73/project')
    C=load('e47_observer_common',root/'experiments/sota-2026-10-22/runtime/epoch47/common.py')
    plan=C.admit(args.plan,args.plan_sha256,args.admission)
    H=C.load_module('e47_closure_metadata',root/'experiments/sota-2026-10-22/audit/epoch47/closure_metadata.py')
    result=evaluate(C,H,plan)
    C.put(root/'experiments/sota-2026-10-22/epoch47/SUPERVISOR_OBSERVED_CLOSURE.json',result)
    print('PHYSICAL_CLOSURE_PASS_STABLE_Z0_WITHIN600')


if __name__=='__main__':main()
