"""Shared independent phase/source/CPU/network checks; standard library only."""
import importlib.util
import json
import math
from pathlib import Path
import sys
from data_common import (read as basic_read,require,identity,digest,TRAIN_IDS,DEV_IDS,finite,ALLOCATION_SHA)

KIND='REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC'
SOURCE='047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
ROLES={'train':TRAIN_IDS,'dev':DEV_IDS,'calibration':[],'confirmation':[]}
ZERO=('Python_network_operations_attempted','Node_network_operations_attempted','CONF_input_bank_reads',
      'CONF_annotation_choices_attempted','CONF_annotation_choices_accessed','DEV_annotation_choices_attempted',
      'DEV_annotation_choices_accessed','other_role_annotation_choices_accessed','source_evidence_lists_accessed',
      'calibration_calls','generation_calls','paid_calls','GPU_calls','HTTP_requests','full104_requests',
      'TRAIN_annotation_choices_attempted','TRAIN_annotation_choices_accessed','TRAIN_input_bank_reads',
      'TRAIN_label_reads','training_steps','fits','optimizer_steps_attempted','optimizer_steps_completed',
      'backward_calls_attempted','backward_calls_completed')

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
    require(type(pin)is dict and set(pin)=={'path','bytes','sha256'} and type(pin['path'])is str
            and not Path(pin['path']).is_absolute()and '..'not in Path(pin['path']).parts,'Unsafe evidence reference')
    path=Path(root)/pin['path'];require(path==path.resolve()and path.is_relative_to(Path(root).resolve()),'Unsafe evidence path')
    got=identity(path);require(got['bytes']==pin['bytes']and got['sha256']==pin['sha256'],'Evidence byte identity mismatch')
    return path

def source_checks(root,plan_path,phase='dev'):
    root=Path(root).resolve();plan=read(plan_path)
    require(plan['epoch']==34 and plan['kind']==KIND and plan['source_checkpoint']==SOURCE
            and plan['actual_project']==str(root)and plan['data_roles']==ROLES,'Wrong source study/roles/root')
    require(phase=='dev','Epoch34 has no current TRAIN phase')
    require(plan['diagnostic_only']is True and plan['training_lineage_complete']is False
            and plan['probability_temperature']==1 and plan['calibration_ids']==plan['confirmation_ids']==[]
            and plan['training_ids']==[],'Overstated eligibility/current fit or altered T1 readout')
    allocation=read(root/'experiments/sota-2026-10-22/audit/epoch34/selection.json',ALLOCATION_SHA)
    require(allocation['roles']==ROLES,'Frozen allocation changed')
    pins=plan['pins'];by={r['path']:r for r in pins};require(len(by)==len(pins),'Duplicate source pins')
    for pin in pins:
        require(not Path(pin['path']).is_absolute()and '..'not in Path(pin['path']).parts,'Unsafe plan pin')
        path=root/pin['path'];require(path==path.resolve()and path.is_file(),'Missing/noncanonical source pin')
        checked(root,pin)
    require(by[plan['dev_inputs_path']]['sha256']==plan['dev_inputs_sha256'],
            'Frozen input hash differs from source pin or admitted fixed projection')
    freeze=read(root/plan['source_freeze_path'],plan['source_freeze_sha256'])
    require(freeze['epoch']==34 and freeze['kind']==KIND,'Wrong source freeze')
    for row in freeze['entries']:require(by.get(row['path'])==row,'Source freeze/plan pin mismatch')
    for name in ['phase_audit.py','model_audit.py','nli_metrics.py','evidence_audit.py','group_audit.py','query_audit.py','decision_proof_audit.py','score_dev.py',
                 'observe_supervisor_closure.py']:
        relative='experiments/sota-2026-10-22/audit/epoch34/'+name
        require(relative in by,'Independent source dependency not frozen: '+name)
    for key,value in {'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],
                      'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':0,
                      'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}.items():
        require(plan['limits'][key]==value,'Frozen budget changed: '+key)
    for key,name in [('proof_source','proof.py'),('proof_policy','PROOF_POLICY.json'),
                     ('query_source','query.py'),('query_policy','QUERY_POLICY.json')]:
        relative='experiments/sota-2026-10-22/candidate/epoch34/'+name
        require(plan[key+'_path']==relative and by[relative]['sha256']==plan[key+'_sha256'],
                'Query/proof source/policy missing from immutable source pins')
    require('experiments/sota-2026-10-22/candidate/epoch34/source_context.py' in by,'New shared source group packer not frozen')
    require(plan['raw_arm_names']==['actual_native','native_original','lexical','positional']
            and plan['metric_arm_names']==['native','native_original','lexical','positional']
            and plan['raw_to_metric_arm']=={'actual_native':'native','native_original':'native_original',
                                           'lexical':'lexical','positional':'positional'},
            'Four-arm raw-to-metric source contract differs')
    return plan,{'pins_verified':len(pins),'current_TRAIN_phase_authorized':False,
                 'freeze':ref(root,root/plan['source_freeze_path'])}

def publisher(root,plan):
    folder=Path(root)/'experiments/sota-2026-10-22/epoch34/publication';pins={r['path']:r for r in plan['pins']}
    for name in ['phase_receipts_v1.py','publication_common_v1.py','phase_schema_v1.py']:
        path=folder/name;relative=str(path.relative_to(root));require(relative in pins,'Unpinned publication receipt dependency')
        checked(root,pins[relative])
    old=list(sys.path)
    try:
        sys.path.insert(0,str(folder));spec=importlib.util.spec_from_file_location('e34_frozen_phase_receipts',folder/'phase_receipts_v1.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:sys.path[:]=old
    return module

def physical_closure(execution,full):
    require(execution['status']==('WORKER_COMPLETED'if full else'WORKER_ENGINEERING_REJECTED')
            and execution['exit_code']==(0 if full else 2)
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

def supervisor_closure(root,evidence):
    """Verify frozen independent proof and reject a currently live known supervisor.

    A terminal Z/X tail may be closed while still present. Its intended exit
    code is never promoted to an observed launcher status.
    """
    pin=evidence.get('supervisor_observed_closure')
    require(pin is not None and pin['path']=='experiments/sota-2026-10-22/epoch34/SUPERVISOR_OBSERVED_CLOSURE.json',
            'Actual independent supervisor closure proof required before gold')
    proof=read(checked(root,pin))
    require(proof==evidence['supervisor_closure_value'] and proof['physical_closure_passed']is True
            and proof['physical_supervisor_closed']is True and proof['unknown_physical_ownership']is False
            and proof['owned_worker_group_members']==[],'Supervisor/known-worker physical closure not established')
    owner=proof['supervisor_identity'];require(owner is not None,'Supervisor identity unknown')
    terminal=((proof['physical_supervisor_absent']is True and proof['observed_supervisor_state']in[None,'ABSENT'])
              or(proof['physical_supervisor_absent']is False and proof['observed_supervisor_state']in['Z','X']))
    require(terminal,'Supervisor proof does not observe absent or closed terminal identity')
    current='ABSENT_OR_ORIGINAL_IDENTITY_GONE'
    try:
        fields=(Path('/proc')/str(owner['pid'])/'stat').read_text().rsplit(')',1)[1].split()
        if int(fields[19])==owner['startticks']:
            current=fields[0];require(current in['Z','X'],'Known supervisor is still live at gold gate')
    except (FileNotFoundError,ProcessLookupError):pass
    return {'evidence':pin,'physical_closure_passed':True,
            'proof_observed_supervisor_absent':proof['physical_supervisor_absent'],
            'proof_observed_supervisor_state':proof['observed_supervisor_state'],
            'current_original_supervisor_state':current,'supervisor_exit_code_observed':None}

def network_checks(root,raw,plan):
    count=raw['counters']['Python_literal_loopback_capability_binds_allowed'];events=raw['Python_network_events']
    require(type(count)is int and 0<=count<=1 and len(events)==count,'Capability exception count mismatch')
    external=Path(plan['external_python_environment'])
    require(external.is_absolute()and external==external.resolve(),'Different noncanonical externally source-pinned CPU environment')
    expected_path=str(external/'lib/python3.12/site-packages/urllib3/util/connection.py')
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
    events=[e for role in raw['corpora'].values() if role is not None for e in role['Node_guard_events']]
    require(all(e['Node_network_operations_attempted']==0 for e in events),
            'Persistent forbidden Node network operation')
    return {'allowed_capability_binds':count,'forbidden_network_operations':0,'scope':'Public API interposition, not OS network isolation'}

def native_capture_checks(root,raw,full):
    capture=raw['native_backend_capture'];attempted_roles=['engineering','dev']if full else['engineering']
    require(capture['all_attempted_helpers_closed_and_complete']is True
            and capture['native_backend_counter_totals_complete']is True
            and capture['backend_execution_since_checkpoint']=='NOT_APPLICABLE_FINAL_RAW'
            and type(capture['helper_attempt_counter'])is int
            and type(capture['observed_helper_Popen_boundaries'])is int
            and capture['helper_attempt_counter']==capture['observed_helper_Popen_boundaries']==len(attempted_roles)
            and[helper['role']for helper in capture['helpers']]==attempted_roles,
            'Successful/refused phase requires complete final native-helper capture; closure alone cannot complete counters')
    require(capture['captured_native_counter_values']=={k:v for k,v in raw['counters'].items()if k.startswith('native_')},
            'Captured native final counters differ from raw observed counters')
    for helper in capture['helpers']:
        role=raw['corpora'][helper['role']]
        require(helper['returned_handle']is True and helper['known_child_closed']is True
                and type(helper['child_exit_code'])is int and helper['child_exit_code']==0
                and helper['final_counter_receipt_validated']is True
                and helper['final_result']==role['native_result']
                and helper['Node_guard_counter_receipt']==role['validated_Node_guard_counter_receipt'],
                'Actual source-bound helper closure/final counter receipt missing')
        checked(root,helper['final_result']);guard_path=checked(root,helper['Node_guard_counter_receipt'])
        guard_rows=[json.loads(line)for line in guard_path.read_text().splitlines()]
        native=read(checked(root,helper['final_result']))
        require(guard_rows==role['Node_guard_events']and guard_rows
                and all(row['pid']==native['helper_pid']for row in guard_rows)
                and guard_rows[-1]['event']=='NATIVE_BINARY_LOAD_AFTER'
                and guard_rows[-1]['phase']=='dev'and guard_rows[-1]['role']==helper['role']
                and all(type(guard_rows[-1][k])is int for k in('Node_network_operations_attempted',
                        'native_binary_loads_attempted','native_binary_loads_completed'))
                and guard_rows[-1]['Node_network_operations_attempted']==0
                and guard_rows[-1]['native_binary_loads_attempted']==guard_rows[-1]['native_binary_loads_completed']==1,
                'Complete actual native Node-guard source/pid/counters differ')
    return {'native_backend_counter_capture_complete':True,'captured_helper_count':len(attempted_roles)}

def phase_integrity(root,raw,execution,plan,phase,full):
    physical=physical_closure(execution,full)
    require(raw['epoch']==34 and raw['kind']==KIND and raw['phase']==phase
            and raw['source_checkpoint']==SOURCE and raw['data_roles']==ROLES,'Wrong raw phase/source/roles')
    expected_status='COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN' if full else 'ENGINEERING_REJECTED_DEV_NOT_STARTED'
    require(phase=='dev'and raw['status']==expected_status,'Incomplete raw phase')
    require(raw['plan_sha256']==execution['plan_sha256']and raw['source_freeze_sha256']==plan['source_freeze_sha256'],
            'Phase plan/freeze binding changed')
    require(raw['admission']['pretrained_model_source']==plan['pretrained_model_source']
            and raw['admission']['model_assets_lock_sha256']==plan['model_assets_lock_sha256']
            and raw['admission']['verified_actual_remote_readback']is True,'Actual pretrained SOURCE/asset admission differs')
    require(raw['errors']==[],'Unexpected phase error')
    require(set(raw['corpora'])=={'engineering','dev'} and raw['corpora']['engineering']is not None
            and (raw['corpora']['dev']is not None)==full,'Wrong engineering/DEV corpus role closure')
    capture=native_capture_checks(root,raw,full)
    for role in raw['corpora'].values():
        if role is None:continue
        require(role['native_child_closed']is True and role['native_child_exit_code']==0
                and role['native_scratch']['removed_after_child_exit']is True
                and role['native_helper_popen_attempted']is True and role['native_helper_returned_handle']is True
                and role['native_counter_capture_complete']is True,'Role native child/scratch/capture not closed')
    counts=raw['counters'];require(counts==execution['raw_operation_counters'],'Raw/outer counters differ')
    table=plan['expected_operation_counters']['dev'] if full else plan['engineering_rejected_operation_counters']['dev']
    for key,value in table.items():
        require(type(counts.get(key))is int and counts[key]==value,'Fixed actual phase counter mismatch: '+key)
    for key in ZERO:require(counts.get(key)==0,'Forbidden actual phase operation: '+key)
    for key,value in counts.items():
        if key.endswith('_attempted')and key[:-10]+'_completed'in counts:
            require(type(value)is int and value>=0 and type(counts[key[:-10]+'_completed'])is int
                    and counts[key[:-10]+'_completed']==value,'Incomplete actual API count pair: '+key)
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
    return {'physical_closure':physical,'network_policy':network_checks(root,raw,plan),'CPU_affinity':[0,1],
            'native_backend_counter_capture_complete':True,'captured_helper_count':capture['captured_helper_count'],
            'opaque_native_internals':'UNKNOWN; actual API counts and observed threads only'}
