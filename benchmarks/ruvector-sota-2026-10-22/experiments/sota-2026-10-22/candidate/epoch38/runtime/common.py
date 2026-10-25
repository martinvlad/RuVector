"""Standard-library-only admission for one native legal parameter adaptation worker."""
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SCOPE = Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f')
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch38'
VENV = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL = Path('/workspace/ruvector-e38-reader-assets/ms-xxlarge-8f8b43dd')
CANDIDATE = HERE.parent
SOURCE = '7c50ba99848f6a13707eeec6c4947291a8478e5c'
KIND = 'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 113708, 26057675, 13626
OWNER_EXPIRY = 1792947674.8344035
BOOT_ID = '4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS_INODE, LOCK_DEVICE, LOCK_FD, OWNER_GENERATION = 4026532200, 33, 3, 1
BINARY = 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
PHASES = ('engineering',)
TRAIN_IDS = []
DEV_IDS = []
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'DEV_reads','DEV_input_bank_reads','DEV_forward_calls_attempted','DEV_forward_calls_completed','DEV_contexts_completed',
        'TRAIN_label_reads', 'TRAIN_forward_calls_attempted', 'TRAIN_forward_calls_completed', 'TRAIN_contexts_completed',
        'CONF_input_bank_reads', 'CONF_annotation_choices_attempted', 'CONF_annotation_choices_accessed',
        'DEV_annotation_choices_attempted', 'DEV_annotation_choices_accessed',
        'other_role_annotation_choices_accessed', 'source_evidence_lists_accessed',
        'calibration_calls', 'generation_calls', 'paid_calls', 'GPU_calls', 'HTTP_requests', 'full104_requests')


def phase_zero(phase):
    if phase!='engineering':raise ValueError('Only the single authored engineering phase exists')
    return ZERO + ('TRAIN_input_bank_reads','TRAIN_annotation_choices_attempted','TRAIN_annotation_choices_accessed',
        'fits','training_steps','optimizer_initializations_attempted','optimizer_initializations_completed',
        'backward_calls_attempted','backward_calls_completed','optimizer_steps_attempted','optimizer_steps_completed',
        'gradient_clips_attempted','gradient_clips_completed','parameter_artifacts_write_attempted','parameter_artifacts_write_completed',
        'parameter_artifacts_load_attempted','parameter_artifacts_load_completed','BART_initializations_attempted','BART_initializations_completed')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def no_symlink(path):
    if any(p.is_symlink() for p in (Path(path), *Path(path).parents)):
        raise ValueError('Symlink component refused')


def checked(relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(x in ('', '.', '..') for x in relative.split('/'))):
        raise ValueError('Unsafe frozen path')
    path = ROOT / relative
    no_symlink(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Missing/nonregular frozen file: ' + relative)
    return path


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite JSON number')
    return result


def read(path):
    no_symlink(path)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_object,
        parse_float=_float, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def put(path, value):
    path = Path(path)
    no_symlink(path)
    with path.open('x', encoding='utf-8') as target:
        json.dump(value, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        target.write('\n')
        target.flush()
        os.fsync(target.fileno())


def proc(pid):
    try:
        fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'sid': int(fields[3]), 'ticks': int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def remaining(deadline):
    value = deadline - time.time()
    if not 0 < value <= 600:
        raise TimeoutError('Invalid/expired bounded legal parameter adaptation deadline')
    return value


def owner_lock(admitted=None):
    if admitted is not None and (admitted.get('owner_pid') != OWNER_PID
            or admitted.get('owner_startticks') != OWNER_TICKS):
        raise ValueError('Wrong exact guardian admission identity')
    if (Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT_ID
            or Path('/proc/self/ns/pid').stat().st_ino!=PIDNS_INODE
            or Path('/proc/'+str(OWNER_PID)+'/ns/pid').stat().st_ino!=PIDNS_INODE):
        raise ValueError('Wrong boot/PID namespace; historical process IDs cannot be replayed')
    if admitted is not None:
        expected={'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,'owner_lock_fd':LOCK_FD,
            'owner_lock_device':LOCK_DEVICE,'owner_lock_inode':LOCK_INODE,'owner_generation':OWNER_GENERATION}
        if any(not same(admitted.get(key),value) for key,value in expected.items()):
            raise ValueError('Admission lacks exact current boot/namespace/FD/lock generation')
    owner = read(SCOPE / 'owner.json')
    row = proc(OWNER_PID)
    if (owner.get('pid') != OWNER_PID or owner.get('startticks') != OWNER_TICKS
            or owner.get('lock_inode') != LOCK_INODE or owner.get('expires_unix') != OWNER_EXPIRY
            or owner.get('kernel_boot_id')!=BOOT_ID or owner.get('PID_namespace')!=f'pid:[{PIDNS_INODE}]'
            or owner.get('generation')!=OWNER_GENERATION
            or not row or row['ticks'] != OWNER_TICKS or row['state'] in ('Z', 'X')
            or time.time() >= OWNER_EXPIRY or (SCOPE / 'release.request').exists()):
        raise ValueError('Guardian dead/reused/released/expired or lease changed')
    lock = SCOPE.parent / 'exclusive.work.lock'
    if owner.get('lock') != str(lock):
        raise ValueError('Wrong scoped lock path')
    no_symlink(lock)
    descriptor=Path(f'/proc/{OWNER_PID}/fd/{LOCK_FD}')
    descriptor_info=descriptor.stat()
    if (descriptor_info.st_dev!=LOCK_DEVICE or descriptor_info.st_ino!=LOCK_INODE
            or os.readlink(descriptor)!=str(lock)):
        raise ValueError('Exact guardian lock FD no longer identifies current scoped lock')
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_ino != LOCK_INODE or info.st_dev!=LOCK_DEVICE:
            raise ValueError('Wrong lock inode')
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        active = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) >= 8 and words[1:5] == ['FLOCK', 'ADVISORY', 'WRITE', str(OWNER_PID)]:
                a, b, c = words[5].split(':')
                active |= (int(a, 16), int(b, 16), int(c)) == target
        if not active:
            raise ValueError('Exact guardian kernel lock absent')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'owner_pid': OWNER_PID, 'owner_startticks': OWNER_TICKS,
                    'lock_inode': LOCK_INODE,'lock_device':LOCK_DEVICE,'lock_fd':LOCK_FD,
                    'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,
                    'generation':OWNER_GENERATION,'contender_denied': True}
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise ValueError('Contender unexpectedly acquired guardian lock')
    finally:
        os.close(fd)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_ref(row,defer_contents=False):
    if (not isinstance(row,dict) or set(row)!={'path','bytes','sha256'} or type(row.get('bytes')) is not int or row['bytes']<0
            or not isinstance(row.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):raise ValueError('Invalid exact file reference')
    file=checked(row['path'])
    if file.stat().st_size!=row['bytes'] or (not defer_contents and sha(file)!=row['sha256']):raise ValueError('Changed frozen bytes: '+row['path'])
    return file


def source_model(plan):
    """Bind both exact original pretrained sources; neither is benchmark-eligible."""
    pins={r['path']:r for r in plan['pins']}
    def source(key,path,expected):
        row=plan[key];file=verify_ref(row)
        if file!=CANDIDATE/path or row!=pins.get(row['path']):raise ValueError('Wrong/unfrozen source profile')
        value=read(file)
        if any(not same(value.get(k),v)for k,v in expected.items()):raise ValueError('Changed original pretrained source/profile')
        admission_ref=value.get('metadata_admission')
        if admission_ref is not None:
            verify_ref(admission_ref)
            if admission_ref!=pins.get(admission_ref['path']):raise ValueError('Unpinned original source research')
        return value
    primary=source('pretrained_model_source','PRETRAINED_MODEL_SOURCE.json',{
        'epoch':38,'kind':KIND,'repository':'microsoft/deberta-v2-xxlarge-mnli',
        'revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','weights_file':'pytorch_model.bin',
        'weights_bytes':3133958098,'weights_sha256':'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db',
        'source_parameter_dtype':'F16','compute_dtype':'F32','training_lineage_complete':False,
        'source_serialization_format':'PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES',
        'native_id2label':{'0':'contradiction','1':'neutral','2':'entailment'},
        'canonical_E_C_N_from_raw':[2,0,1],'confirmation':[],'promotion_allowed':False,'official_eligibility':'HOLD'})
    header=plan['xxlarge_weight_metadata_path']
    if header!='experiments/sota-2026-10-22/candidate/epoch38/research/XXL_ORIGINAL_WEIGHT_METADATA.json':raise ValueError('Wrong original archive metadata')
    href=pins.get(header)
    if href is None or href['sha256']!=plan['xxlarge_weight_metadata_sha256']or primary.get('original_archive_metadata')!=href:
        raise ValueError('Original archive metadata not source-pinned')
    meta=read(verify_ref(href))
    if (meta.get('schema_version')!=3 or meta.get('status')!='ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE'
            or meta.get('weights')!={'bytes':3133958098,'sha256':'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db'}
            or meta.get('format')!='PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES'
            or meta.get('metadata_pickle_count')!=5 or meta.get('storage_data_ends_at_filelength')is not True
            or meta.get('storage_payloads_decoded')!=0 or meta.get('source_parameter_dtype')!='F16'
            or meta.get('unsafe_unpickling_calls')!=0
            or meta.get('checkpoint_functions_invoked')!=0 or meta.get('ML_imports')!=0 or meta.get('model_tokenizer_native_calls')!=0):
        raise ValueError('Unverified/unsafe original archive metadata')
    load_path='experiments/sota-2026-10-22/candidate/epoch38/research/LEGACY_ORIGINAL_LOAD_PLAN.v3.json'
    load_ref=pins.get(load_path)
    if (plan.get('legacy_original_load_plan_path')!=load_path or load_ref is None
            or plan.get('legacy_original_load_plan_sha256')!=load_ref['sha256']
            or primary.get('legacy_original_load_plan')!=load_ref):raise ValueError('Unbound reviewed explicit legacy load plan')
    load_plan=read(verify_ref(load_ref));policy=load_plan.get('future_frozen_loader_policy',{})
    expected_policy={'serialization_format':'PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES','weights_only':True,
        'mmap':False,'map_location':'cpu','trust_remote_code':False,'unrestricted_pickle_allowed':False,
        'extra_pickle_safe_globals_added':0,'ZIP_fallback_allowed':False,'legacy_tar_fallback_in_statics':False,
        'alternate_checkpoint_allowed':False,'dynamic_quantization_allowed':False,'compute_dtype':'F32',
        'before_source_freeze_actual_torch_loads_allowed':0,'model_initializations_in_acquisition_or_static_inspection':0}
    if any(not same(policy.get(k),v)for k,v in expected_policy.items()):raise ValueError('Different or unsafe explicit legacy loader policy')
    profiles_file=checked(plan['model_profiles_path'])
    if profiles_file!=CANDIDATE/'MODEL_PROFILES.json'or sha(profiles_file)!=plan['model_profiles_sha256']:raise ValueError('Wrong model profiles source')
    profiles=read(profiles_file)
    if (profiles.get('epoch')!=38 or profiles.get('kind')!=KIND or profiles.get('shared_partition_model')!='xxlarge'
            or set(profiles.get('profiles',{}))!={'xxlarge'}):raise ValueError('Different exact single model profile')
    row=profiles['profiles']['xxlarge']
    if (not same(row.get('model_source'),plan['pretrained_model_source'])or row.get('model_directory')!=str(MODEL)
            or not same(row.get('model_assets_lock'),pins.get(plan['model_assets_lock_path']))
            or row.get('native_label_order')!=['Contradiction','NotMentioned','Entailment']
            or row.get('canonical_E_C_N_from_raw')!=[2,0,1]or row.get('compute_dtype')!='F32'):
        raise ValueError('Single original profile source/asset/native mapping differs')
    if (profiles['profiles']['xxlarge'].get('original_archive_metadata')!=href
            or profiles['profiles']['xxlarge'].get('legacy_original_load_plan')!=load_ref):raise ValueError('Profile original metadata/legacy policy differs')
    return primary


def admission(path,plan,plan_sha,phase):
    if phase!='engineering' or Path(path).absolute()!=STUDY/'SOURCE_ADMISSION.json':raise ValueError('Only SOURCE-bound combined phase admitted')
    value=read(path)
    if (value.get('epoch')!=38 or value.get('kind')!=KIND or value.get('phase')!='engineering'
            or value.get('scope')!='benchmarks/ruvector-sota-2026-10-22/' or value.get('verified_actual_remote_readback') is not True
            or value.get('plan_sha256')!=plan_sha or value.get('source_freeze_sha256')!=plan['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}',value.get('published_source_commit',''))
            or not same(value.get('pretrained_model_source'),plan['pretrained_model_source'])
            or value.get('model_assets_lock_sha256')!=plan['model_assets_lock_sha256']
            or value.get('model_profiles_sha256')!=plan['model_profiles_sha256']
            or value.get('xxlarge_weight_metadata_sha256')!=plan['xxlarge_weight_metadata_sha256']
            or value.get('legacy_original_load_plan_sha256')!=plan['legacy_original_load_plan_sha256']):raise ValueError('Actual current paired SOURCE/model asset readback required')
    source_model(plan)
    return value,owner_lock(value)


def dispatch_proof(plan,plan_sha,admission_path,wait_seconds=3):
    claim_path=STUDY/'DISPATCH_RESERVATION.json';claim=read(claim_path)
    expected={'schema_version':1,'epoch':38,'kind':KIND,'phase':'engineering','plan_sha256':plan_sha,
        'source_freeze_sha256':plan['source_freeze_sha256'],'pretrained_model_source_sha256':plan['pretrained_model_source_sha256'],
        'model_assets_lock_sha256':plan['model_assets_lock_sha256'],'admission_sha256':sha(admission_path),
        'kernel_boot_id':BOOT_ID,'pid_namespace_inode':PIDNS_INODE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
    if any(not same(claim.get(k),v) for k,v in expected.items()):raise ValueError('Wrong exact detached dispatch source/budget claim')
    if any(type(claim.get(k)) not in (int,float) or not math.isfinite(claim[k]) for k in ('dispatch_monotonic_seconds','dispatch_unix_seconds')):raise ValueError('Missing finite dispatch clocks')
    if not 0<=time.monotonic()-claim['dispatch_monotonic_seconds']<600:raise TimeoutError('Expired dispatch budget')
    attempt_path=STUDY/'DISPATCH_ATTEMPT.json';until=min(time.monotonic()+wait_seconds,claim['dispatch_monotonic_seconds']+585)
    while not attempt_path.exists():
        if time.monotonic()>=until:raise RuntimeError('Uncertain detached dispatch; no retry')
        time.sleep(.01)
    attempt=read(attempt_path);actual=proc(os.getpid())
    if (any(not same(attempt.get(k),v) for k,v in expected.items())
            or any(attempt.get(k)!=claim[k] for k in ('dispatch_monotonic_seconds','dispatch_unix_seconds'))
            or attempt.get('pid')!=os.getpid() or not actual or attempt.get('startticks')!=actual['ticks']
            or attempt.get('pgid')!=os.getpid() or attempt.get('sid')!=os.getpid()
            or actual['pgid']!=os.getpid() or actual['sid']!=os.getpid()
            or attempt.get('verified_launcher_start') is not True or attempt.get('uncertain_launcher_start') is not False):raise ValueError('Detached exact supervisor identity mismatch')
    return claim,attempt


def verify_plan(path,expected,phase):
    if phase!='engineering'or Path(path).absolute()!=STUDY/'plan.json'or sha(path)!=expected:raise ValueError('Wrong one-phase source plan')
    plan=read(path)
    if (plan.get('epoch')!=38 or plan.get('kind')!=KIND or plan.get('source_checkpoint')!=SOURCE
            or plan.get('actual_project')!=str(ROOT)or plan.get('guardian_scope')!=str(SCOPE)
            or plan.get('external_python_environment')!=str(VENV)or plan.get('model_directory')!=str(MODEL)
            or plan.get('source_serialization_format')!='PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES'
            or plan.get('source_parameter_dtype')!='F16'
            or not same(plan.get('data_roles'),{'train':[],'dev':[],'calibration':[],'confirmation':[]})):
        raise ValueError('Different exact paired source/scope/empty benchmark roles')
    if (plan.get('engineering_only')is not True or plan.get('benchmark_accuracy','MISSING')is not None
            or plan.get('promotion_allowed')is not False or plan.get('used_confirmation_identities')!=[]
            or any(plan.get(k)!=[] for k in('training_ids','development_ids','calibration_ids','confirmation_ids'))):
        raise ValueError('Engineering cannot fit/promote/use benchmark identities')
    limits={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,
        'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,
        'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
    if any(not same(plan['limits'].get(k),v)for k,v in limits.items()):raise ValueError('Wrong paired frozen budget')
    pins=plan['pins'];by={r['path']:r for r in pins}
    if len(by)!=len(pins):raise ValueError('Duplicate source pin')
    for row in pins:verify_ref(row)
    for name in('runtime/common.py','runtime/launch.py','runtime/network_guard.py','runtime/node_guard.cjs','runtime/cpu_guard.py',
            'worker.py','xxlarge_model.py','algorithm.py','evidence.py','context_engine.py','source_context.py','vector_codec.py',
            'native_helper.cjs','proof.py','query.py','MODEL_ASSETS.json','MODEL_ASSETS.expected.json','asset_identity.py','runtime/model_assets_guard.py','quantitative.py','CONTEXT_POLICY.json'):
        if str((CANDIDATE/name).relative_to(ROOT))not in by:raise ValueError('Unpinned paired source: '+name)
    for key in('source_freeze','runtime_assets_lock','model_assets_lock','pretrained_model_source',
            'model_profiles','xxlarge_weight_metadata','legacy_original_load_plan','engineering_inputs','engineering_oracle',
            'audit_protocol','numeric_oracle','model_assets_expected','model_assets_validator','real_model_assets_guard_receipt','runtime_policy_addendum','proof_source','proof_policy','query_source','query_policy','source_context'):
        if by.get(plan[key+'_path'],{}).get('sha256')!=plan[key+'_sha256']:raise ValueError('Missing exact source pin: '+key)
    for key in('pretrained_model_source','model_assets_expected','model_assets_validator','real_model_assets_guard_receipt'):
        if not same(plan[key],by[plan[key+'_path']]):raise ValueError('Profile ref alias differs')
    if plan['worker_path']!=str((CANDIDATE/'worker.py').relative_to(ROOT))or plan['native_worker_path']!=str((CANDIDATE/'native_helper.cjs').relative_to(ROOT)):raise ValueError('Wrong helper/worker source')
    for key in('expected_operation_counters','engineering_rejected_operation_counters'):
        if set(plan.get(key,{}))!={'engineering'}or not isinstance(plan[key]['engineering'],dict)or any(type(v)is not int or v<0 for v in plan[key]['engineering'].values()):raise ValueError('Missing fixed counter table')
    if plan['runtime_policy_addendum_path']!='experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json'or plan['runtime_policy_addendum_sha256']!='c4b3c3243ac089d5966e394f3ead60f57a15f59cc24b496960334124c14dbacd':raise ValueError('Only inherited exact prospective runtime exception admitted')
    if plan['proof_source_path']!=str((CANDIDATE/'proof.py').relative_to(ROOT))or plan['proof_policy_path']!=str((CANDIDATE/'PROOF_POLICY.json').relative_to(ROOT)):raise ValueError('Wrong proof boundary')
    if plan['query_source_path']!=str((CANDIDATE/'query.py').relative_to(ROOT))or plan['query_policy_path']!=str((CANDIDATE/'QUERY_POLICY.json').relative_to(ROOT)):raise ValueError('Wrong query source')
    if plan['source_context_path']!=str((CANDIDATE/'source_context.py').relative_to(ROOT)):raise ValueError('Wrong unchanged two-group packer')
    q=read(checked(plan['query_policy_path']));proof=read(checked(plan['proof_policy_path']))
    if q.get('epoch')!=38 or q.get('kind')!=KIND or q.get('policy')!='unchanged-original-query-numeric-source-v1':raise ValueError('Different unchanged original query policy')
    if proof.get('epoch')!=38 or proof.get('policy')!='SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'or proof.get('proof_enabled_roles')!=['engineering']or proof.get('confirmation')!=[]or proof.get('official_eligibility')!='HOLD':raise ValueError('Different prospective source certificate policy')
    root_path='experiments/sota-2026-10-22/epoch38/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
    if by.get(root_path,{}).get('sha256')!='226cd756b41c881e5131a175a470ac06c96ed158ffd9c5bc216d42b3cac41a67':raise ValueError('Root prospective contract not pinned')
    root=read(checked(root_path))
    if (plan.get('raw_context_names')!=root['raw_contexts']or plan.get('metric_arm_names')!=root['arms']
            or plan.get('readout_reuse_map')!=root['arm_to_measured_context']or plan.get('engineering_gate')!=root['gate']):
        raise ValueError('Changed prospective contexts/arms/reuse/scientific gates')
    verify_prefreeze_model_asset_receipt(plan,by)
    source_model(plan)
    frozen=read(checked(plan['source_freeze_path']))
    if frozen.get('epoch')!=38 or frozen.get('kind')!=KIND or frozen.get('source_checkpoint')!=SOURCE:raise ValueError('Wrong source freeze')
    if len({r['path']for r in frozen['entries']})!=len(frozen['entries'])or any(not same(by.get(r['path']),r)for r in frozen['entries']):raise ValueError('Changed frozen source closure')
    return plan


def verify_prefreeze_model_asset_receipt(plan,pins):
    path='experiments/sota-2026-10-22/epoch38/preparation/model-assets-guard-admission.json'
    row=pins.get(path)
    if (row is None or plan.get('real_model_assets_guard_receipt_path')!=path
            or plan.get('real_model_assets_guard_receipt_sha256')!=row['sha256']):
        raise ValueError('Unstubbed actual prefreeze model-asset guard receipt must be frozen')
    value=read(verify_ref(row))
    required={'schema_version':1,'epoch':38,'source_checkpoint':SOURCE,
        'status':'PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE',
        'function':'C.verify_model_assets','function_calls':1,'stubs_used':False,'monkeypatches':[],
        'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0}
    if any(not same(value.get(k),v)for k,v in required.items()):raise ValueError('Incomplete/incorrect actual full prefreeze guard envelope')
    result=value.get('result')
    if not isinstance(result,dict)or set(result)!={'xxlarge'}:raise ValueError('Exactly one real original-model guard result required')
    leaf=result['xxlarge']
    needed={'status':'ALL_FIVE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES','epoch':38,'kind':KIND,
        'source_checkpoint':SOURCE,'validator_function':'model_assets_guard.validate_model_assets','actual_payload_files_verified':5,
        'ordinary_Git_payloads_verified':3,'canonical_LFS_pointers_verified':2,'stubs_used':False,'monkeypatches':[],
        'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,
        'repository':'microsoft/deberta-v2-xxlarge-mnli','revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','model_directory':str(MODEL)}
    if any(not same(leaf.get(k),v)for k,v in needed.items()):raise ValueError('Incomplete full five-real-payload guard result')
    refs={'common_source':str((CANDIDATE/'runtime/common.py').relative_to(ROOT)),
        'validator_source':plan['model_assets_validator_path'],'identity_helper_source':str((CANDIDATE/'asset_identity.py').relative_to(ROOT)),
        'expected_catalog':plan['model_assets_expected_path'],'public_model_assets_lock':plan['model_assets_lock_path']}
    for key,name in refs.items():
        if value.get(key)!=pins.get(name)or leaf.get(key)!=pins.get(name):raise ValueError('Real guard source/catalog/lock no longer matches current frozen bytes: '+key)
    direct=leaf.get('external_direct_lock',{})
    if (direct.get('path')!=str(MODEL/'asset-lock.json')or direct.get('byte_identical_to_public')is not True
            or direct.get('sha256')!=plan['model_assets_lock_sha256']):raise ValueError('Real direct/public model lock identity not proven')
    source=read(checked(plan['model_assets_expected_path']));declared={r['path']:r for r in source['files']}
    files=leaf.get('files')
    if not isinstance(files,list)or len(files)!=5 or {r.get('path')for r in files}!=set(declared):raise ValueError('Exactly all five actual payload scans required')
    identities=load_module('e38_prefreeze_typed_identity_receipt',CANDIDATE/'asset_identity.py')
    for item in files:
        declaration=declared[item['path']]
        verified=identities.verify_payload_observation(declaration,item.get('actual_payload_bytes_hashed'),item.get('actual_payload_sha256'),item.get('actual_ordinary_payload_git_blob_sha1'))
        if (item.get('actual_full_payload_scan')is not True or any(not same(item.get(k),v)for k,v in verified.items())):
            raise ValueError('Missing full real payload scan or incorrect typed identity')
    return value


def verify_model_assets(plan):
    """SAME complete real validator for prefreeze root call and dispatch/worker.

    This requires the separate reviewed a65 source declaration, never the
    observed materialization lock as its own expected identity authority.
    """
    pins={r['path']:r for r in plan['pins']}
    if plan.get('epoch')!=38 or plan.get('kind')!=KIND or plan.get('source_checkpoint')!=SOURCE or plan.get('model_directory')!=str(MODEL):
        raise ValueError('Wrong exact single-model source identity')
    def bound(key,file):
        name=str(file.relative_to(ROOT));row=pins.get(name)
        if (row is None or plan.get(key+'_path')!=name or plan.get(key+'_sha256')!=row['sha256']or verify_ref(row)!=file):
            raise ValueError('Missing exact real asset validator source pin: '+key)
        if key in('model_assets_expected','model_assets_validator')and plan.get(key)!=row:raise ValueError('Canonical source reference differs from path/SHA aliases: '+key)
        return row
    expected=CANDIDATE/'MODEL_ASSETS.expected.json';expected_ref=bound('model_assets_expected',expected)
    if expected_ref['bytes']!=2112 or expected_ref['sha256']!='a65cda75fc67d2c935eac4b998fa5d3a6e375bbfbd7212dd19d998d15b016806':
        raise ValueError('Exact independently reviewed separate original source authority required')
    lock=CANDIDATE/'MODEL_ASSETS.json';lock_ref=bound('model_assets_lock',lock)
    validator=CANDIDATE/'runtime/model_assets_guard.py';bound('model_assets_validator',validator)
    helper=CANDIDATE/'asset_identity.py';helper_ref=pins.get(str(helper.relative_to(ROOT)))
    if helper_ref is None or helper_ref['sha256']!='f271c0077be23c34fbb29cfb5728d671371a4646ac9030072ec7b538eb819499'or verify_ref(helper_ref)!=helper:
        raise ValueError('Exact reviewed typed source identity helper required')
    common_ref=pins.get(str(Path(__file__).relative_to(ROOT)))
    if common_ref is None or verify_ref(common_ref)!=Path(__file__):raise ValueError('Current common wrapper must be exactly pinned before real guard')
    actual=load_module('e38_shared_real_model_assets_guard',validator)
    receipt=actual.validate_model_assets(MODEL,lock,expected,root=ROOT,public_lock_sha256=lock_ref['sha256'],
        expected_catalog_sha256=expected_ref['sha256'],epoch=38,kind=KIND,source_checkpoint=SOURCE)
    if receipt.get('ordinary_Git_payloads_verified')!=3 or receipt.get('canonical_LFS_pointers_verified')!=2:
        raise ValueError('Exact three ordinary bodies and two canonical LFS payload identities required')
    receipt['common_source']=common_ref
    return {'xxlarge':receipt}


def verify_runtime(plan):
    if Path(sys.prefix).absolute()!=VENV or sys.version_info[:2]!=(3,12):raise ValueError('Exact restored read-only external Python required')
    lock=read(checked(plan['runtime_assets_lock_path']));assets=lock['assets'];pins={r['path']:r for r in plan['pins']}
    if (lock.get('epoch')!=38 or lock.get('runtime_reuse_policy')!='HASH_VERIFIED_READ_ONLY_E33_RUNTIME'
            or lock.get('fresh_runtime_directory')!=str(VENV)or lock.get('inference_python')!=str(VENV/'bin/python')):
        raise ValueError('Wrong explicit read-only runtime reuse')
    reuse_ref=lock.get('runtime_reuse_verification')
    if (not isinstance(reuse_ref,dict)or reuse_ref.get('path')!='experiments/sota-2026-10-22/epoch38/preparation/runtime-reuse-verification.json'
            or reuse_ref!=pins.get(reuse_ref.get('path'))):raise ValueError('Missing exact current runtime-reuse receipt')
    reuse=read(verify_ref(reuse_ref))
    required={'epoch':38,'policy':'HASH_VERIFIED_READ_ONLY_E33_RUNTIME',
        'status':'ONE_PROFILE_RUNTIME_ASSETS_HASH_VERIFIED_NO_ML',
        'actual_model_native_tokenizer_paid_GPU_calls':0,'verified_wheel_members':17498,'source_checkpoint':SOURCE,
        'external_environment':str(VENV)}
    if any(not same(reuse.get(k),v)for k,v in required.items()):raise ValueError('Incomplete current single-profile runtime proof')
    profiles=reuse.get('model_profiles_verified')
    if not isinstance(profiles,dict)or set(profiles)!={'xxlarge'}:raise ValueError('Exactly one original model profile verified')
    item=profiles['xxlarge']
    if (item.get('model_directory')!=str(MODEL)or item.get('payload_files')!=5
            or item.get('model_assets_lock')!=pins.get(plan['model_assets_lock_path'])):raise ValueError('Wrong verified source profile')
    receipt_assets=reuse.get('native_BGE_assets')
    if (not isinstance(receipt_assets,list)or len(receipt_assets)!=10
            or len({r.get('path')for r in receipt_assets})!=10
            or {r.get('path'):(r.get('bytes'),r.get('sha256'))for r in receipt_assets}
               !={r.get('path'):(r.get('bytes'),r.get('sha256'))for r in assets}):
        raise ValueError('Actual current runtime receipt must bind all ten same native/BGE assets')
    original_lock=read(checked(plan['model_assets_lock_path']))
    receipt_payloads=item.get('payloads')
    if (not isinstance(receipt_payloads,list)or len(receipt_payloads)!=5
            or len({r.get('path')for r in receipt_payloads})!=5
            or {r.get('path'):(r.get('bytes'),r.get('sha256'))for r in receipt_payloads}
               !={r.get('path'):(r.get('bytes'),r.get('sha256'))for r in original_lock['files']}):
        raise ValueError('Actual single-profile runtime receipt must bind all five original payload identities')
    if len(assets)!=10 or len({r['path']for r in assets})!=10:raise ValueError('Exact ten original native/BGE assets required')
    rows={r['path']:r for r in assets}
    required_assets={BINARY:BINARY_SHA,'models/bge-small-en-v1.5/model.onnx':'828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35','models/bge-small-en-v1.5/tokenizer.json':'d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'}
    if any(rows.get(k,{}).get('sha256')!=v for k,v in required_assets.items()):raise ValueError('Changed native/BGE identities')
    if (lock.get('native_core_runtime_version')!='2.3.0'or lock.get('native_NPM_version')!='0.1.33'or lock.get('native_platform_NPM_version')!='0.1.31'
            or lock.get('python_expected_versions')!={'numpy':'2.2.6','onnxruntime':'1.22.1','tokenizers':'0.21.4','torch':'2.7.1+cpu','transformers':'4.52.4','safetensors':'0.5.3'}):raise ValueError('Wrong exact CPU runtime versions')
    for row in assets:verify_ref(row)
    for key in('wheel_lock','native_closure','BGE_source','wheel_members_reference'):
        name,digest=lock[key+'_path'],lock[key+'_sha256']
        if pins.get(name,{}).get('sha256')!=digest or sha(checked(name))!=digest:raise ValueError('Unpinned runtime reference')
    if lock.get('wheel_members_reference_count')!=17498 or lock['wheel_members_reference_sha256']!='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9':raise ValueError('Wrong installed member closure')
    member_ref=lock.get('python_member_manifest')
    if member_ref!=pins.get(lock['wheel_members_reference_path'])or member_ref.get('sha256')!=lock['wheel_members_reference_sha256']:raise ValueError('Runtime member aliases differ')
    members=read(checked(lock['wheel_members_reference_path']))
    if len(members)!=17498 or len({r['path']for r in members})!=17498:raise ValueError('Wrong member count')
    for row in members:
        name=row['path']
        if not isinstance(name,str)or PurePosixPath(name).is_absolute()or any(v in('','.','..')for v in name.split('/')):raise ValueError('Unsafe runtime member')
        file=VENV/name;no_symlink(file)
        if not file.is_file()or file.stat().st_size!=row['bytes']or sha(file)!=row['sha256']:raise ValueError('Changed original CPU wheel member')
    if Path(plan['external_python_environment'])!=VENV or Path(plan['inference_python'])!=VENV/'bin/python':raise ValueError('Wrong external interpreter')
    verify_model_assets(plan);return lock


def read_json_line(line):
    return json.loads(line,object_pairs_hook=_object,parse_float=_float,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSONL')))
