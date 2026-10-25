"""Independent E37 engineering source, closure, resource and network checks."""
import json,math,importlib.util,sys
from pathlib import Path
from data_common import read as basic_read,require,identity,digest,finite,SOURCE_CHECKPOINT
from nli_metrics import ARMS,CONTEXTS,REUSE
KIND='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
SOURCE=SOURCE_CHECKPOINT
ROLES={'train':[],'dev':[],'calibration':[],'confirmation':[]}
ENGINEERING_GATE={'primary_required_correct':12,'each_class_required_correct':4,'accuracy_gain_at_least2_vs':'full_raw','proper_nonincrease_against':['full_raw','native_raw','lexical_verified','full_verified'],'proper_scores':['Brier','NLL'],'prospective_ceiling_rejection_if_full_raw_correct_exceeds':10,'no_native_causal_gain_claim_if_null':True}
ZERO=('Python_network_operations_attempted','Node_network_operations_attempted','CONF_input_bank_reads',
      'CONF_annotation_choices_attempted','CONF_annotation_choices_accessed','DEV_annotation_choices_attempted',
      'DEV_annotation_choices_accessed','other_role_annotation_choices_accessed','source_evidence_lists_accessed',
      'calibration_calls','generation_calls','paid_calls','GPU_calls','HTTP_requests','full104_requests',
      'TRAIN_annotation_choices_attempted','TRAIN_annotation_choices_accessed','TRAIN_input_bank_reads',
      'TRAIN_label_reads','training_steps','fits','optimizer_steps_attempted','optimizer_steps_completed',
      'backward_calls_attempted','backward_calls_completed','DEV_input_bank_reads','DEV_forward_calls_completed')
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

def source_checks(root,plan_path):
    root=Path(root).resolve();plan=read(plan_path)
    require(plan['epoch']==37 and plan['kind']==KIND and plan['source_checkpoint']==SOURCE
            and plan['actual_project']==str(root)and plan['data_roles']==ROLES,'Wrong engineering source/root/empty benchmark roles')
    require(plan['training_lineage_complete']is False and plan['probability_temperature']==1
            and plan['calibration_ids']==plan['confirmation_ids']==plan['training_ids']==[],
            'Unlicensed fit/confirmation or altered T1')
    require(plan['engineering_only']is True and plan['benchmark_accuracy']is None
            and plan['used_confirmation_identities']==[] and plan['promotion_allowed']is False,
            'Engineering cannot authorize benchmark/confirmation/promotion')
    pins=plan['pins'];by={r['path']:r for r in pins};require(len(by)==len(pins),'Duplicate source pins')
    for pin in pins:checked(root,pin)
    for key in ['engineering_inputs','engineering_oracle','proof_source','proof_policy','query_source','query_policy','model_profiles','xxlarge_weight_metadata','legacy_original_load_plan']:
        path=plan[key+'_path'];require(path in by and by[path]['sha256']==plan[key+'_sha256'],'Missing source hash pin: '+key)
    freeze=read(root/plan['source_freeze_path'],plan['source_freeze_sha256'])
    require(freeze['epoch']==37 and freeze['kind']==KIND,'Wrong frozen engineering source')
    for pin in freeze['entries']:require(by.get(pin['path'])==pin,'Freeze/plan source pin differs')
    for name in ['data_common.py','phase_audit.py','model_audit.py','nli_metrics.py','evidence_audit.py',
                 'query_audit.py','decision_proof_audit.py','certificate_audit.py','source_coverage_audit.py','lifecycle_audit.py','score_engineering.py','observe_supervisor_closure.py']:
        require('experiments/sota-2026-10-22/audit/epoch37/'+name in by,'Unfrozen independent source: '+name)
    for key,value in {'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],
        'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,
        'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}.items():
        require(plan['limits'][key]==value,'Engineering resource authorization differs: '+key)
    require(plan['raw_context_names']==CONTEXTS and plan['metric_arm_names']==ARMS and plan['readout_reuse_map']==REUSE,'Three actual contexts/five derived arms changed')
    require(plan['engineering_gate']==ENGINEERING_GATE,'Frozen engineering primary/gain/proper-score gate changed')
    from model_audit import LEGACY_PLAN_SHA,XXL_METADATA_SHA,LEGACY_FORMAT
    require(plan['source_parameter_dtype']=='F16'and plan['source_serialization_format']==LEGACY_FORMAT
        and plan['xxlarge_weight_metadata_sha256']==XXL_METADATA_SHA
        and plan['legacy_original_load_plan_sha256']==LEGACY_PLAN_SHA,'Different source dtype/serialization or unreviewed legacy header/load plan')
    from data_common import ROOT_CONTRACT_REF
    require(plan['root_contract']==ROOT_CONTRACT_REF,'Wrong root prospective contract pin');contract=read(checked(root,ROOT_CONTRACT_REF))
    require(plan['engineering_gate']==contract['gate'] and plan['probability_policy']==contract['probability_policy'],'Gate/probability root contract changed')
    metrology=read(checked(root,plan['metrics_policy']))
    require(metrology['NLL']=='UNCLIPPED_STABLE_SOURCE_LOGIT_LOGSOFTMAX_WITH_SAME_CANONICAL_CLASS_PERMUTATION'and metrology['gate_metric_binding']=={'Brier':'Brier','NLL':'NLL'},'Gate NLL binding changed')
    return plan,{'pins_verified':len(pins),'benchmark_roles_empty':True,'root_contract':ROOT_CONTRACT_REF,'metrics_policy':plan['metrics_policy'],'freeze':ref(root,root/plan['source_freeze_path'])}

def publisher(root,plan):
    """Load only the three exact source-frozen stdlib receipt modules.

    Called only after independently checking physical worker/supervisor closure.
    No publisher mutation, model, native module or tokenizer is imported.
    """
    folder=root/'experiments/sota-2026-10-22/epoch37/publication';pins={p['path']:p for p in plan['pins']}
    names=['publication_common_v1','phase_schema_v1','phase_receipts_v1']
    for name in names:
        relative=str((folder/(name+'.py')).relative_to(root))
        require(relative in pins,'Unfrozen canonical receipt dependency: '+name);checked(root,pins[relative])
    oldpath=list(sys.path);oldmodules={name:sys.modules.pop(name,None)for name in names}
    try:
        sys.path.insert(0,str(folder))
        spec=importlib.util.spec_from_file_location('phase_receipts_v1',folder/'phase_receipts_v1.py')
        module=importlib.util.module_from_spec(spec);sys.modules['phase_receipts_v1']=module;spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:]=oldpath
        for name in names:
            sys.modules.pop(name,None)
            if oldmodules[name]is not None:sys.modules[name]=oldmodules[name]

def live_owned_group(owner):
    remaining=[]
    if owner is None:return remaining
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            f=(path/'stat').read_text().rsplit(')',1)[1].split()
            if int(f[2])==owner['pgid']or int(f[3])==owner['sid']:remaining.append(int(path.name))
        except (OSError,ValueError,IndexError):pass
    return remaining

def physical_ownership_closure(execution):
    """Closure alone, independent of runtime success or complete counters.

    Failed/partial/UNKNOWN captures must survive to canonical factual projection.
    Success/36-readout eligibility is checked separately before metrics.
    """
    require(execution['owned_live_processes_closed']is True and execution['owned_live_group_members']==[],
            'Owned phase physical closure not established')
    owner=execution.get('worker_identity')
    if owner is None:
        require(execution.get('verified_worker_starts')==0,'Missing identity for a known started worker')
    else:
        require(type(owner)is dict and all(type(owner.get(k))is int and owner[k]>0 for k in ['pgid','sid']),
                'Invalid captured worker process-group identity')
    remaining=live_owned_group(owner)
    require(not remaining,'Physical phase group/session remains')
    return {'worker_identity':owner,'remaining_owned_members':remaining}

def physical_closure(execution,full):
    physical=physical_ownership_closure(execution)
    require(execution['status']=='WORKER_COMPLETED'
            and execution['exit_code']==0
            and execution['worker_attempts_reserved']==execution['verified_worker_starts']==1
            and execution['uncertain_start']is False,'Incomplete/uncertain phase worker')
    require(execution['launcher_error']is None and not execution['cleanup_errors']
            and execution['stdout_stderr_capture_completed']is True,'Unexpected outer error/capture failure')
    require(execution['CPU_affinity']==[0,1]and 0<execution['wall_seconds_including_init_cleanup']<=600
            and execution['source_plan_unchanged']is True,'Phase CPU/wall/source budget failed')
    return physical

def supervisor_closure(root,evidence):
    """Verify frozen independent proof and reject a currently live known supervisor.

    A terminal Z/X tail may be closed while still present. Its intended exit
    code is never promoted to an observed launcher status.
    """
    pin=evidence.get('supervisor_observed_closure')
    require(pin is not None and pin['path']=='experiments/sota-2026-10-22/epoch37/SUPERVISOR_OBSERVED_CLOSURE.json',
            'Actual independent supervisor closure proof required before gold')
    proof=read(checked(root,pin))
    plan_path=root/'experiments/sota-2026-10-22/epoch37/plan.json'
    require(proof.get('schema_version')==1 and proof.get('epoch')==37 and proof.get('kind')==KIND and proof.get('phase')=='engineering'
            and proof.get('source_plan_sha256')==identity(plan_path)['sha256']
            and proof.get('kernel_boot_id')=='4632fb06-b0ef-4df5-b72b-0e875bbad810' and proof.get('pid_namespace_inode')==4026532200,'Independent closure plan/source/boot/namespace mismatch before raw parsing')
    execution_pin=proof.get('execution');require(execution_pin is not None and execution_pin['path']=='experiments/sota-2026-10-22/epoch37/runs/engineering/execution.json','Actual known execution closure reference required')
    actual_execution=read(checked(root,execution_pin))
    require(actual_execution['plan_sha256']==proof['source_plan_sha256'] and actual_execution.get('supervisor_identity')==proof.get('supervisor_identity'),'Closure identity differs from actual execution supervisor')
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
    capture=raw['native_backend_capture'];attempted_roles=['engineering']
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
                and guard_rows[-1]['phase']=='engineering'and guard_rows[-1]['role']==helper['role']
                and all(type(guard_rows[-1][k])is int for k in('Node_network_operations_attempted',
                        'native_binary_loads_attempted','native_binary_loads_completed'))
                and guard_rows[-1]['Node_network_operations_attempted']==0
                and guard_rows[-1]['native_binary_loads_attempted']==guard_rows[-1]['native_binary_loads_completed']==1,
                'Complete actual native Node-guard source/pid/counters differ')
    return {'native_backend_counter_capture_complete':True,'captured_helper_count':len(attempted_roles)}

def admission_check(raw,plan):
    require(raw['admission']['pretrained_model_source']==plan['pretrained_model_source']
            and raw['admission']['model_assets_lock_sha256']==plan['model_assets_lock_sha256']
            and raw['admission']['model_profiles_sha256']==plan['model_profiles_sha256']
            and raw['admission']['xxlarge_weight_metadata_sha256']==plan['xxlarge_weight_metadata_sha256']
            and raw['admission']['legacy_original_load_plan_sha256']==plan['legacy_original_load_plan_sha256']
            and raw['admission']['verified_actual_remote_readback']is True,'Source-bound primary/baseline assets or original archive metadata not admitted')
    return {'status':'PASS_SINGLE_READER_ASSETS_PROFILES_AND_ORIGINAL_ARCHIVE_ADMISSION',
        'xxlarge_weight_metadata_sha256':plan['xxlarge_weight_metadata_sha256'],
        'legacy_original_load_plan_sha256':plan['legacy_original_load_plan_sha256']}

def phase_integrity(root,raw,execution,plan):
    physical=physical_closure(execution,True)
    require(raw['epoch']==37 and raw['kind']==KIND and raw['phase']=='engineering'
            and raw['source_checkpoint']==SOURCE and raw['data_roles']==ROLES,'Wrong raw engineering source/role')
    require(raw['status']in['ENGINEERING_ADMISSION_PASSED','ENGINEERING_ADMISSION_FAILED'],
            'Only complete36 engineering readouts may be scored')
    require(raw['plan_sha256']==execution['plan_sha256']
            and raw['source_freeze_sha256']==plan['source_freeze_sha256'],'Raw/plan/freeze source changed')
    admission=admission_check(raw,plan)
    require(raw['errors']==[] and set(raw['corpora'])=={'engineering'}
            and raw['corpora']['engineering']is not None,'Unexpected error or benchmark corpus')
    require(raw['engineering_only']is True and raw['benchmark_accuracy']is None
            and raw['benchmark_accepted']is False and raw['champion_promoted']is False
            and raw['training_lineage_complete']is False and raw['used_confirmation_identities']==[]
            and raw['confirmation']==raw['calibration']==[],'Overstated raw engineering/benchmark/confirmation scope')
    capture=native_capture_checks(root,raw,True);role=raw['corpora']['engineering']
    require(role['native_child_closed']is True and role['native_child_exit_code']==0
            and role['native_scratch']['removed_after_child_exit']is True
            and role['native_helper_popen_attempted']is True and role['native_helper_returned_handle']is True
            and role['native_counter_capture_complete']is True,'Engineering native process/counters/scratch not closed')
    counts=raw['counters'];require(counts==execution['raw_operation_counters'],'Raw/outer operation counters differ')
    for key,value in plan['expected_operation_counters']['engineering'].items():
        require(type(counts.get(key))is int and counts[key]==value,'Fixed engineering operation count differs: '+key)
    for key in ZERO:require(counts.get(key)==0,'Forbidden actual operation: '+key)
    for key,value in counts.items():
        if key.endswith('_attempted')and key[:-10]+'_completed'in counts:
            require(type(value)is int and value>=0 and type(counts[key[:-10]+'_completed'])is int
                    and counts[key[:-10]+'_completed']==value,'Incomplete actual API counter pair: '+key)
    require(counts['NLI_forward_calls_completed']==counts['ENGINEERING_forward_calls_completed']==36
            and counts['native_index_initializations_completed']==counts['native_queries_completed']==12
            and counts['native_binary_loads_completed']==1,'Complete36readout/12query/12index/1load contract failed')
    require(counts['model_initializations_completed']==1 and counts['tokenizer_initializations_completed']==1
            and counts['xxlarge_forward_calls_completed']==counts['xxlarge_readouts_completed']==36
            and counts['model_unloads_completed']==counts['sequential_model_lifecycles_completed']==1
            and counts['full_source_contexts_completed']==12 and counts['coverage_contexts_completed']==24
            and counts['native_complete_unitset_cases_verified']==12 and counts['derived_forecasts_completed']==60
            and counts['source_analysis_calls_completed']==48 and counts['certificate_decisions_completed']==36
            and counts['readout_reuse_receipts_completed']==60,'Fixed one-model actual/derived/readout/context/lifecycle counts differ')
    guard=raw['worker_cpu_guard_preexec'];require(guard==execution['worker_cpu_guard_preexec'],'CPU guard receipt differs')
    require(raw['worker_cpu_guard_preexec_artifact']==execution['worker_cpu_guard_preexec_artifact'],'CPU guard source ref differs')
    require(read(checked(root,raw['worker_cpu_guard_preexec_artifact']))==guard,'CPU guard actual artifact differs')
    require(guard['status']=='CPU_GUARD_INSTALLED_BEFORE_EXEC'and guard['CPU_affinity']==[0,1]
            and guard['denied_syscalls']==[203,1073742027]and guard['denial_errno']==1,'Wrong kernel CPU guard')
    st=guard['actual_proc_status'];require(st['NoNewPrivs']=='1'and st['Seccomp']=='2'
            and st['Cpus_allowed_list']=='0-1','CPU guard not actually installed')
    def visit(v):
        if type(v)is dict:
            for thread in v.get('observed_thread_affinities',[]):
                require(thread['observed_affinity_within_CPU0_1']is True,'Observed thread escaped CPU0,1')
            for child in v.values():visit(child)
        elif type(v)is list:
            for child in v:visit(child)
    visit(raw.get('resources',{}));visit(raw.get('CPU_policy_before_model_import',{}))
    require(not raw.get('CPU_affinity_violation_snapshot'),'CPU affinity violation retained')
    resources=raw['resources'];require(resources['CPU_affinity']==[0,1]and finite(raw['wall_seconds_including_initialization_cleanup'])and 0<raw['wall_seconds_including_initialization_cleanup']<=600,'Actual inner worker wall/CPU resource budget differs')
    for key in ['worker_user_seconds','worker_system_seconds','child_user_seconds','child_system_seconds','worker_peak_RSS_bytes','largest_child_peak_RSS_bytes']:
        require(finite(resources[key])and resources[key]>=0,'Invalid actual retained resource observation: '+key)
    return {'physical_closure':physical,'source_admission':admission,'network_policy':network_checks(root,raw,plan),'CPU_affinity':[0,1],
        **capture,'opaque_native_internals':'UNKNOWN; actual API counters and observed threads only'}

