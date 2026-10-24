"""Shared independent phase/source/CPU/network checks; standard library only."""
import importlib.util
import json
import math
from pathlib import Path
import sys
from data_common import (read as basic_read,require,identity,digest,TRAIN_IDS,DEV_IDS,finite)

KIND='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
SOURCE='ccd765026806aa3d7e43e295238a741c874a46b8'
SHAS={'train':'bf1eff95845e301b56abd1a5284df0dcbbf531b952ea4dd1d89351fef845570a',
      'dev':'5e6ab03f00b6f0581057457ff2a8278113576b1f5ea699895d5126144019aaf4'}
ROLES={'train':TRAIN_IDS,'dev':DEV_IDS,'calibration':[],'confirmation':[]}
ZERO=('Python_network_operations_attempted','Node_network_operations_attempted','CONF_input_bank_reads',
      'CONF_annotation_choices_attempted','CONF_annotation_choices_accessed','DEV_annotation_choices_attempted',
      'DEV_annotation_choices_accessed','other_role_annotation_choices_accessed','source_evidence_lists_accessed',
      'calibration_calls','generation_calls','paid_calls','GPU_calls','HTTP_requests','full104_requests')

def read(path,sha=None):
    value=basic_read(path,sha)
    def visit(v):
        if type(v)is float:require(math.isfinite(v),'Nonfinite JSON number')
        elif isinstance(v,dict):
            for child in v.values():visit(child)
        elif isinstance(v,list):
            for child in v:visit(child)
    visit(value);return value

def ref(root,path):
    root,path=Path(root).resolve(),Path(path).resolve()
    require(path.is_relative_to(root),'Evidence outside project')
    return {**identity(path),'path':str(path.relative_to(root))}

def checked(root,pin):
    path=Path(root)/pin['path'];require(path==path.resolve(),'Unsafe evidence path')
    got=identity(path);require(got['bytes']==pin['bytes']and got['sha256']==pin['sha256'],'Evidence byte identity mismatch')
    return path

def source_checks(root,plan_path,phase):
    root=Path(root).resolve();plan=read(plan_path)
    require(plan['epoch']==30 and plan['kind']==KIND and plan['source_checkpoint']==SOURCE
            and plan['actual_project']==str(root)and plan['data_roles']==ROLES,'Wrong source study/roles/root')
    require(plan['train_inputs_sha256']==SHAS['train']and plan['dev_inputs_sha256']==SHAS['dev'],'Frozen input bank changed')
    pins=plan['pins'];by={r['path']:r for r in pins};require(len(by)==len(pins),'Duplicate source pins')
    for pin in pins:
        require(not Path(pin['path']).is_absolute()and '..'not in Path(pin['path']).parts,'Unsafe plan pin')
        path=root/pin['path'];require(path==path.resolve()and path.is_file(),'Missing/noncanonical source pin')
        if phase=='train'and pin['path']==plan['dev_inputs_path']:
            require(path.stat().st_size==pin['bytes'],'Deferred DEV input size changed')
        else:checked(root,pin)
    freeze=read(root/plan['source_freeze_path'],plan['source_freeze_sha256'])
    require(freeze['epoch']==30 and freeze['kind']==KIND,'Wrong source freeze')
    for row in freeze['entries']:require(by.get(row['path'])==row,'Source freeze/plan pin mismatch')
    for name in ['phase_audit.py','artifact_audit.py','nli_metrics.py','evidence_audit.py','score_train.py','score_dev.py']:
        relative='experiments/sota-2026-10-22/audit/epoch30/'+name
        require(relative in by,'Independent source dependency not frozen: '+name)
    for key,value in {'owned_workers':2,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],
                      'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':1,
                      'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}.items():
        require(plan['limits'][key]==value,'Frozen budget changed: '+key)
    return plan,{'pins_verified':len(pins),'DEV_input_bytes_deferred_in_TRAIN':phase=='train',
                 'freeze':ref(root,root/plan['source_freeze_path'])}

def publisher(root,plan):
    folder=Path(root)/'experiments/sota-2026-10-22/epoch30/publication';pins={r['path']:r for r in plan['pins']}
    for name in ['phase_receipts_v1.py','publication_common_v1.py','phase_schema_v1.py']:
        path=folder/name;relative=str(path.relative_to(root));require(relative in pins,'Unpinned publication receipt dependency')
        checked(root,pins[relative])
    old=list(sys.path)
    try:
        sys.path.insert(0,str(folder));spec=importlib.util.spec_from_file_location('e30_frozen_phase_receipts',folder/'phase_receipts_v1.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:sys.path[:]=old
    return module

def physical_closure(execution):
    require(execution['status']=='WORKER_COMPLETED'and execution['exit_code']==0
            and execution['worker_attempts_reserved']==execution['verified_worker_starts']==1
            and execution['uncertain_start']is False,'Incomplete/uncertain phase worker')
    require(execution['owned_live_processes_closed']is True and execution['owned_live_group_members']==[],
            'Owned phase processes not closed')
    require(execution['launcher_error']is None and not execution['cleanup_errors']
            and execution['stdout_stderr_capture_completed']is True,'Unexpected outer error/capture failure')
    require(execution['CPU_affinity']==[0,1]and 0<execution['wall_seconds_including_init_cleanup']<=600
            and execution['source_plan_unchanged']is True,'Phase CPU/wall/source budget failed')
    owner=execution['worker_identity'];remaining=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            f=(path/'stat').read_text().rsplit(')',1)[1].split()
            if int(f[2])==owner['pgid']or int(f[3])==owner['sid']:remaining.append(int(path.name))
        except (OSError,ValueError,IndexError):pass
    require(not remaining,'Physical phase group/session remains')
    return {'worker_identity':owner,'remaining_owned_members':remaining}

def network_checks(root,raw):
    count=raw['counters']['Python_literal_loopback_capability_binds_allowed'];events=raw['Python_network_events']
    require(type(count)is int and 0<=count<=1 and len(events)==count,'Capability exception count mismatch')
    expected_path=str(Path(root)/'retrieval/.venv/lib/python3.12/site-packages/urllib3/util/connection.py')
    for row in events:
        require(row['event']=='socket.bind'and row['allowed']is True and row['family']==10
                and row['socket_type']==1 and row['protocol']==0 and row['address']=="('::1', 0)",
                'Unapproved network event')
        source=row['source_provenance']
        require(source=={'path':expected_path,'sha256':'2633bbdb69731e5ccb5cf4e4afd65605d86c7979cc5633126f50c92d5ad74a74',
                         'function':'_has_ipv6','line':127},'Capability source provenance mismatch')
        require(identity(Path(expected_path))['sha256']==source['sha256']and row['stack'],'Capability caller source changed')
        require(row['bind_outcome']in['SUCCESS','ERROR']and row['close_outcome']=='SUCCESS'
                and row['file_descriptor_after_close']==-1
                and finite(row['monotonic_seconds'])and finite(row['close_monotonic_seconds'])
                and row['close_monotonic_seconds']>=row['monotonic_seconds'],'Capability socket outcome/closure incomplete')
    require(not raw['Python_network_violations'],'Persistent forbidden Python network operation')
    require(all(e['Node_network_operations_attempted']==0 for e in raw['Node_guard_events']),
            'Persistent forbidden Node network operation')
    return {'allowed_capability_binds':count,'forbidden_network_operations':0,'scope':'Public API interposition, not OS network isolation'}

def phase_integrity(root,raw,execution,plan,phase):
    physical=physical_closure(execution)
    require(raw['epoch']==30 and raw['kind']==KIND and raw['phase']==phase
            and raw['source_checkpoint']==SOURCE and raw['data_roles']==ROLES,'Wrong raw phase/source/roles')
    require(raw['status']==('COMPLETED_TRAIN_AWAITING_INDEPENDENT_MODEL_SEAL'if phase=='train'
                           else'COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN'),'Incomplete raw phase')
    require(raw['plan_sha256']==execution['plan_sha256']and raw['source_freeze_sha256']==plan['source_freeze_sha256'],
            'Phase plan/freeze binding changed')
    require(raw['errors']==[]and raw['native_child_closed']is True and raw['native_child_exit_code']==0,'Unexpected phase/native error')
    counts=raw['counters'];require(counts==execution['raw_operation_counters'],'Raw/outer counters differ')
    for key,value in plan['expected_operation_counters'][phase].items():
        require(type(counts.get(key))is int and counts[key]==value,'Fixed actual phase counter mismatch: '+key)
    for key in ZERO:require(counts.get(key)==0,'Forbidden actual phase operation: '+key)
    guard=raw['worker_cpu_guard_preexec'];require(guard==execution['worker_cpu_guard_preexec'],'CPU guard receipt mismatch')
    require(raw['worker_cpu_guard_preexec_artifact']==execution['worker_cpu_guard_preexec_artifact'],'CPU guard artifact ref mismatch')
    require(read(checked(root,raw['worker_cpu_guard_preexec_artifact']))==guard,'Actual CPU guard artifact differs')
    require(guard['status']=='CPU_GUARD_INSTALLED_BEFORE_EXEC'and guard['CPU_affinity']==[0,1]
            and guard['denied_syscalls']==[203,1073742027]and guard['denial_errno']==1,'Wrong kernel CPU guard')
    st=guard['actual_proc_status'];require(st['NoNewPrivs']=='1'and st['Seccomp']=='2'and st['Cpus_allowed_list']=='0-1','CPU guard not actually installed')
    def visit(v):
        if isinstance(v,dict):
            for thread in v.get('observed_thread_affinities',[]):
                require(thread['observed_affinity_within_CPU0_1']is True,'Observed thread escaped CPU budget')
            for child in v.values():visit(child)
        elif isinstance(v,list):
            for child in v:visit(child)
    visit(raw.get('resources',{}));visit(raw.get('CPU_policy_before_model_import',{}))
    require(not raw.get('CPU_affinity_violation_snapshot'),'CPU affinity violation retained')
    require(raw['native_scratch']['removed_after_child_exit']is True,'Native storage scratch not closed')
    return {'physical_closure':physical,'network_policy':network_checks(root,raw),'CPU_affinity':[0,1],
            'opaque_native_internals':'UNKNOWN; actual API counts and observed threads only'}
