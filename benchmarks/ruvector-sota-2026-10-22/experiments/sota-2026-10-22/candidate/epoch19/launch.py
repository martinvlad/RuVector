"""Owned one-shot qualification launcher; source preflight never imports models."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import common as C


def now():return datetime.now(timezone.utc).isoformat()


def process_info(pid):
    try:
        values=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return {'pid':pid,'state':values[0],'pgid':int(values[2]),'sid':int(values[3]),'start_ticks':int(values[19])}
    except (OSError,ValueError,IndexError):return None


def alive(pid):
    value=process_info(pid)
    return bool(value and value['state']not in ('Z','X'))


def members(pgid):
    result=[]
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            value=process_info(int(p.name))
            if value and value['pgid']==pgid and value['sid']==pgid and value['state']not in ('Z','X'):result.append(value)
    return sorted(result,key=lambda x:x['pid'])


def close_owned_group(pgid,start_ticks,deadline):
    result={'pgid':pgid,'signals':[],'owned_live_before':members(pgid),'owned_live_pids':[]}
    leader=process_info(pgid)
    if leader and start_ticks is not None and leader['start_ticks']!=start_ticks:
        result.update(error='Original leader PID identity changed; refused uncertain signal',owned_live_pids=[x['pid']for x in members(pgid)])
        return result
    for sig in (signal.SIGTERM,signal.SIGKILL):
        if not members(pgid):break
        try:os.killpg(pgid,sig);result['signals'].append(signal.Signals(sig).name)
        except ProcessLookupError:break
        until=min(deadline-.05,time.time()+(.6 if sig==signal.SIGTERM else .5))
        while members(pgid)and time.time()<until:time.sleep(.02)
    result['owned_live_pids']=[x['pid']for x in members(pgid)]
    result['finished_within_deadline']=time.time()<=deadline
    return result


def launch(plan_path,admission_path):
    plan=C.require_plan(plan_path);digest=C.sha(plan_path);C.verify_admission(admission_path,digest)
    if str(Path(sys.executable).absolute())!=plan['inference_python']:raise ValueError('Exact fresh reviewed inference Python required')
    started_unix=time.time();started=time.monotonic();hard=min(started_unix+600,plan['lease_expires_unix']-30);deadline=hard-5
    if deadline-started_unix<60:raise RuntimeError('Insufficient exclusive lease; no worker attempt reserved')
    C.write_new(C.STUDY/'launch.json',{'at':now(),'plan_sha256':digest,'study_id':C.STUDY_ID,
      'qualification_worker_cap':1,'benchmark_corpora':0,'automatic_retry':False})
    folder=C.STUDY/'runs/qualification';folder.mkdir(parents=True,exist_ok=False)
    C.write_new(folder/'reservation.json',{'at':now(),'state':'PREPARED_NOT_ACTUAL_START','plan_sha256':digest})
    env=dict(os.environ)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS','UV_THREADPOOL_SIZE'):env[key]='2'
    env['TOKENIZERS_PARALLELISM']='false';env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
    affinity=sorted(os.sched_getaffinity(0))[:2]
    process=None;exit_code=None;error=None;observed_affinity=None;start_ticks=None
    cleanup={'owned_live_pids':[],'scope':'No worker PID returned; no actual process start inferred'}
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with (folder/'worker.log').open('x')as log:
        C.write_new(folder/'popen-attempt.json',{'at':now(),'state':'DURABLE_IMMEDIATELY_BEFORE_POPEN',
          'plan_sha256':digest,'qualification_worker_attempt':1,'automatic_retry':False,
          'scope':'Consumes the only process slot even if Popen fails; not proof of model/native execution'})
        try:
            command=[sys.executable,'-B',str(Path(__file__).with_name('worker.py')),'--plan',str(plan_path),
              '--expected-plan-sha',digest,'--admission',str(admission_path),'--deadline',str(deadline)]
            process=subprocess.Popen(command,cwd=C.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
              start_new_session=True,preexec_fn=lambda:os.sched_setaffinity(0,affinity))
            info=process_info(process.pid);start_ticks=info['start_ticks']if info else None
            try:observed_affinity=sorted(os.sched_getaffinity(process.pid))
            except ProcessLookupError:pass
            C.write_new(folder/'attempt.json',{'at':now(),'pid':process.pid,'pgid':process.pid,
              'start_ticks':start_ticks,'plan_sha256':digest,'qualification_worker_attempt':1,
              'invocation_started_unix':started_unix,'deadline_unix':deadline,'hard_cleanup_deadline_unix':hard,
              'automatic_retry':False,'observed_CPU_affinity':observed_affinity})
            exit_code=process.wait(timeout=max(.001,deadline-time.time()))
        except BaseException as exc:
            error=type(exc).__name__+': '+str(exc)
        finally:
            if process is not None:
                cleanup=close_owned_group(process.pid,start_ticks,hard)
                if process.returncode is None:
                    try:exit_code=process.wait(timeout=max(.001,hard-time.time()))
                    except subprocess.TimeoutExpired:error=(error or'')+'; worker not reaped by cleanup deadline'
                else:exit_code=process.returncode
    native_attempt=C.read(folder/'native-attempt.json')if (folder/'native-attempt.json').exists()else None
    raw=C.read(folder/'raw.json')if (folder/'raw.json').exists()else None
    native_pid=(native_attempt or{}).get('pid')or ((raw or{}).get('cleanup')or{}).get('native_helper_pid')
    after=resource.getrusage(resource.RUSAGE_CHILDREN);elapsed=time.monotonic()-started
    if observed_affinity is None and raw:observed_affinity=raw.get('resources',{}).get('before_runtime',{}).get('allowed_CPU_ids')
    execution={'schema_version':1,'epoch':19,'at':now(),'plan_sha256':digest,
      'qualification_worker_attempts':1,'verified_worker_starts':int(process is not None),
      'worker_pid':process.pid if process else None,'worker_pgid':process.pid if process else None,
      'native_helper_pid':native_pid,'worker_exit_code':exit_code,'error':error,'elapsed_seconds':elapsed,
      'CPU_affinity':observed_affinity,'user_seconds':after.ru_utime-before.ru_utime,
      'system_seconds':after.ru_stime-before.ru_stime,'peak_RSS_bytes':after.ru_maxrss*1024,
      'resource_scope':'Outer Linux RUSAGE_CHILDREN for this one worker and reaped descendants; peak is largest child high-water, not simultaneous RSS sum.',
      'source_plan_unchanged':C.sha(plan_path)==digest,'raw_sha256':C.sha(folder/'raw.json')if raw else None,
      'cleanup':{'worker_exited':bool(process and process.poll()is not None and not alive(process.pid)),
        'native_helper_exited':not alive(native_pid)if type(native_pid)is int else None,
        'process_group_empty':not members(process.pid)if process else None,
        'owned_live_pids':cleanup.get('owned_live_pids'),'details':cleanup},
      'benchmark_corpora':0,'benchmark_HTTP_requests':0,'new_paid_API_GPU_calls':0,
      'unspent_epoch_slots_closed':True,'allowed_further_qualification_attempts':0,'automatic_retry':False}
    good=exit_code==0 and not error and elapsed<=600 and execution['source_plan_unchanged']and all(execution['cleanup'].get(k)is True for k in ('worker_exited','native_helper_exited','process_group_empty'))
    execution['status']='COMPLETED_AWAITING_INDEPENDENT_ENGINEERING_REPLAY'if good else'FAILED_OR_INCOMPLETE_PRESERVED_EVIDENCE'
    C.write_new(folder/'execution.json',execution)
    C.write_new(C.STUDY/'study-completion.json',{'at':now(),'status':execution['status'],'qualification_worker_attempts':1,
      'verified_worker_starts':execution['verified_worker_starts'],'execution_path':str((folder/'execution.json').relative_to(C.ROOT)),
      'execution_sha256':C.sha(folder/'execution.json'),'engineering_qualified':None,'accepted':False,
      'allowed_further_qualification_attempts':0,'benchmark_corpora':0,'benchmark_HTTP_requests':0,
      'official_score':None,'official_rank':None,'champion_promoted':False})
    if not good:raise RuntimeError('Actual qualification failed; retain evidence and never retry')
    return execution


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--admission',type=Path);parser.add_argument('--check-plan',action='store_true');parser.add_argument('--verify-assets',action='store_true')
    args=parser.parse_args()
    if args.check_plan:
        plan=C.require_plan(args.plan)
        asset_summary=None
        if args.verify_assets:
            import worker
            _,model_assets,native_assets,versions=worker.verify_assets(plan)
            asset_summary={'model_assets':len(model_assets),'native_core_assets':len(native_assets),'installed_versions':len(versions),'model_native_imports':0}
        print(json.dumps({'status':'FULL_UNMOCKED_SOURCE_PLAN_PASS','plan_sha256':C.sha(args.plan),'pins':len(plan['pins']),
          'model_native_calls':0,'native_execution_admitted':False,'asset_verification':asset_summary}));return
    if not args.admission:parser.error('Actual launch requires exact late published-source admission')
    print(json.dumps({'status':launch(args.plan,args.admission)['status']}))


if __name__=='__main__':main()
