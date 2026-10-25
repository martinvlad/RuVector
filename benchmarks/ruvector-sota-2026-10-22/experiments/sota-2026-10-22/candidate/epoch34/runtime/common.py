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
SCOPE = Path('/tmp/ruvector-sota-2026-10-22/epoch34-047dbc740dc2')
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch34'
VENV = Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL = Path('/workspace/ruvector-e34-reader-assets/moritz-b3546ea6')
CANDIDATE = HERE.parent
SOURCE = '047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
KIND = 'REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 100799, 22293151, 13626
OWNER_EXPIRY = 1792910029.5943027
BOOT_ID = '4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS_INODE, LOCK_DEVICE, LOCK_FD, OWNER_GENERATION = 4026532200, 33, 3, 1
BINARY = 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
PHASES = ('dev',)
TRAIN_IDS = []
DEV_IDS = [434,367,247,377,220,457,169,449]
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'TRAIN_label_reads', 'TRAIN_forward_calls_attempted', 'TRAIN_forward_calls_completed', 'TRAIN_contexts_completed',
        'CONF_input_bank_reads', 'CONF_annotation_choices_attempted', 'CONF_annotation_choices_accessed',
        'DEV_annotation_choices_attempted', 'DEV_annotation_choices_accessed',
        'other_role_annotation_choices_accessed', 'source_evidence_lists_accessed',
        'calibration_calls', 'generation_calls', 'paid_calls', 'GPU_calls', 'HTTP_requests', 'full104_requests')


def phase_zero(phase):
    if phase!='dev':raise ValueError('Only combined engineering then DEV phase exists')
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
    path=verify_ref(plan['pretrained_model_source'])
    if path!=CANDIDATE/'PRETRAINED_MODEL_SOURCE.json':raise ValueError('Wrong model source metadata path')
    value=read(path)
    expected={'epoch':34,'kind':KIND,'repository':'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli',
        'revision':'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7','weights_file':'model.safetensors',
        'weights_bytes':870182606,'weights_sha256':'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b',
        'source_parameter_dtype':'F16','compute_dtype':'F32','training_lineage_complete':False,'native_id2label':{'0':'entailment','1':'neutral','2':'contradiction'},
        'canonical_E_C_N_to_raw':[0,2,1],'confirmation':[],'promotion_allowed':False,'official_eligibility':'HOLD'}
    if any(not same(value.get(k),v) for k,v in expected.items()):raise ValueError('Different model/head or overstated eligibility')
    verify_ref(value['metadata_admission'])
    if value['metadata_admission']['sha256']!='f91cdaf0fd0c6af7c5ccab3b62c43bbcc90ea8bc7180cb4b343da01bb2b567d7':raise ValueError('Different original source research')
    return value


def admission(path,plan,plan_sha,phase):
    if phase!='dev' or Path(path).absolute()!=STUDY/'SOURCE_ADMISSION.json':raise ValueError('Only SOURCE-bound combined phase admitted')
    value=read(path)
    if (value.get('epoch')!=34 or value.get('kind')!=KIND or value.get('phase')!='dev'
            or value.get('scope')!='benchmarks/ruvector-sota-2026-10-22/' or value.get('verified_actual_remote_readback') is not True
            or value.get('plan_sha256')!=plan_sha or value.get('source_freeze_sha256')!=plan['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}',value.get('published_source_commit',''))
            or not same(value.get('pretrained_model_source'),plan['pretrained_model_source'])
            or value.get('model_assets_lock_sha256')!=plan['model_assets_lock_sha256']):raise ValueError('Actual current SOURCE/model asset readback required')
    source_model(plan)
    return value,owner_lock(value)


def dispatch_proof(plan,plan_sha,admission_path,wait_seconds=3):
    claim_path=STUDY/'DISPATCH_RESERVATION.json';claim=read(claim_path)
    expected={'schema_version':1,'epoch':34,'kind':KIND,'phase':'dev','plan_sha256':plan_sha,
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
    if phase!='dev' or Path(path).absolute()!=STUDY/'plan.json' or sha(path)!=expected:raise ValueError('Wrong one-phase plan')
    plan=read(path)
    if (plan.get('epoch')!=34 or plan.get('kind')!=KIND or plan.get('source_checkpoint')!=SOURCE
            or plan.get('actual_project')!=str(ROOT) or plan.get('guardian_scope')!=str(SCOPE)
            or plan.get('external_python_environment')!=str(VENV)
            or plan.get('model_directory')!=str(MODEL)
            or not same(plan.get('data_roles'),{'train':[],'dev':DEV_IDS,'calibration':[],'confirmation':[]})):raise ValueError('Different source/scope/fixed DEV roles')
    limits={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,
        'native_corpus_batches':2,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
    if any(not same(plan['limits'].get(k),v) for k,v in limits.items()):raise ValueError('Wrong frozen budget')
    pins=plan['pins'];by_path={row['path']:row for row in pins}
    if len(by_path)!=len(pins):raise ValueError('Duplicate pin')
    for row in pins:verify_ref(row,defer_contents=row['path']==plan['dev_inputs_path'])
    for name in ('runtime/common.py','runtime/launch.py','runtime/network_guard.py','runtime/node_guard.cjs','runtime/cpu_guard.py','worker.py','model.py','algorithm.py','evidence.py','context_engine.py','source_context.py','vector_codec.py','native_helper.cjs','proof.py','query.py'):
        if str((CANDIDATE/name).relative_to(ROOT)) not in by_path:raise ValueError('Unpinned candidate source: '+name)
    if plan['worker_path']!=str((CANDIDATE/'worker.py').relative_to(ROOT)) or plan['native_worker_path']!=str((CANDIDATE/'native_helper.cjs').relative_to(ROOT)):raise ValueError('Wrong helper/worker')
    for key in ('source_freeze','runtime_assets_lock','model_assets_lock','pretrained_model_source','engineering_inputs','engineering_oracle','dev_inputs','runtime_policy_addendum','proof_source','proof_policy','query_source','query_policy','source_context'):
        if by_path.get(plan[key+'_path'],{}).get('sha256')!=plan[key+'_sha256']:raise ValueError('Missing pin: '+key)
    if not same(plan['pretrained_model_source'],by_path[plan['pretrained_model_source_path']]):raise ValueError('Model source ref mismatch')
    for key in ('expected_operation_counters','engineering_rejected_operation_counters'):
        if set(plan.get(key,{}))!={'dev'} or not isinstance(plan[key]['dev'],dict) or any(type(v) is not int or v<0 for v in plan[key]['dev'].values()):raise ValueError('Missing conditional counter tables')
    if plan['runtime_policy_addendum_path']!='experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json' or plan['runtime_policy_addendum_sha256']!='c4b3c3243ac089d5966e394f3ead60f57a15f59cc24b496960334124c14dbacd':raise ValueError('Only inherited exact prospective literal capability policy admitted')
    source_model(plan)
    if plan['proof_source_path']!=str((CANDIDATE/'proof.py').relative_to(ROOT)) or plan['proof_policy_path']!=str((CANDIDATE/'PROOF_POLICY.json').relative_to(ROOT)):raise ValueError('Unknown proof source/policy')
    if plan['query_source_path']!=str((CANDIDATE/'query.py').relative_to(ROOT)) or plan['query_policy_path']!=str((CANDIDATE/'QUERY_POLICY.json').relative_to(ROOT)):raise ValueError('Unknown query source/policy')
    if plan['source_context_path']!=str((CANDIDATE/'source_context.py').relative_to(ROOT)):raise ValueError('Unknown mandatory-group context source')
    query_policy=read(checked(plan['query_policy_path']))
    if query_policy.get('epoch')!=34 or query_policy.get('policy')!='lexical-anchor-native-complement-v1' or query_policy.get('kind')!=KIND:raise ValueError('Unknown prospective query policy')
    policy=read(checked(plan['proof_policy_path']))
    if policy.get('epoch')!=34 or policy.get('policy')!='proof-disabled-all-roles-v1' or policy.get('confirmation')!=[] or policy.get('official_eligibility')!='HOLD' or policy.get('proof_enabled_roles')!=[]:raise ValueError('Unknown prospective proof policy')
    frozen=read(checked(plan['source_freeze_path']))
    if frozen.get('epoch')!=34 or frozen.get('kind')!=KIND or frozen.get('source_checkpoint')!=SOURCE:raise ValueError('Wrong source freeze')
    if len({r['path'] for r in frozen['entries']})!=len(frozen['entries']):raise ValueError('Duplicate source entry')
    if any(not same(by_path.get(r['path']),r) for r in frozen['entries']):raise ValueError('Changed source closure')
    return plan


def verify_model_assets(plan):
    lockfile=checked(plan['model_assets_lock_path']);lock=read(lockfile)
    if (lock.get('epoch')!=34 or lock.get('kind')!=KIND or lock.get('repository')!='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
            or lock.get('revision')!='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7' or lock.get('model_directory')!=str(MODEL)):raise ValueError('Wrong actual model materialization lock')
    no_symlink(MODEL)
    direct=MODEL/'asset-lock.json';no_symlink(direct)
    if direct.read_bytes()!=lockfile.read_bytes() or sha(lockfile)!=plan['model_assets_lock_sha256']:raise ValueError('Actual/public model lock mismatch')
    expected=read(CANDIDATE/'MODEL_ASSETS.expected.json')['files'];wanted={r['path']:r for r in expected}
    rows=lock['files']
    if len(rows)!=9 or {r['path'] for r in rows}!=set(wanted) or {p.name for p in MODEL.iterdir()}!=set(wanted)|{'asset-lock.json'}:raise ValueError('Extra/missing/repeated model assets')
    for row in rows:
        original=wanted[row['path']];file=MODEL/row['path'];no_symlink(file)
        if (not file.is_file() or file.stat().st_size!=row['bytes'] or row['bytes']!=original['bytes']
                or row.get('upstream_git_blob_sha1')!=original['upstream_git_blob_sha1']
                or row.get('source_url')!=original['source_url'] or not re.fullmatch('[0-9a-f]{64}',row.get('sha256',''))
                or sha(file)!=row['sha256']):raise ValueError('Actual model asset changed: '+row['path'])
        if original.get('upstream_sha256') and row['sha256']!=original['upstream_sha256']:raise ValueError('LFS source mismatch')
        if original.get('metadata_body_sha256') and row['sha256']!=original['metadata_body_sha256']:raise ValueError('Exact acquired metadata mismatch')
        if not original.get('upstream_sha256'):
            blob=hashlib.sha1(b'blob '+str(row['bytes']).encode()+b'\0')
            with file.open('rb') as stream:
                for data in iter(lambda:stream.read(1048576),b''):blob.update(data)
            if blob.hexdigest()!=original['upstream_git_blob_sha1']:raise ValueError('Upstream Git blob mismatch')
    return lock


def verify_runtime(plan):
    if Path(sys.prefix).absolute()!=VENV or sys.version_info[:2]!=(3,12):raise ValueError('Exact hash-verified read-only Python virtual environment required before ML')
    lock=read(checked(plan['runtime_assets_lock_path']));assets=lock['assets']
    if (lock.get('epoch')!=34 or lock.get('runtime_reuse_policy')!='HASH_VERIFIED_READ_ONLY_E33_RUNTIME'
            or lock.get('fresh_runtime_directory')!=str(VENV) or lock.get('inference_python')!=str(VENV/'bin/python')):
        raise ValueError('Current explicit read-only runtime reuse policy required')
    reuse_ref=lock.get('runtime_reuse_verification')
    if not same(reuse_ref,{'path':'experiments/sota-2026-10-22/epoch34/preparation/runtime-reuse-verification.json',
            'bytes':6556,'sha256':'d0aa0cf8ff62c4b2089998d3257694b1f6d5f1fe2c7eca2b29b4e5f1147d6b36'}):
        raise ValueError('Unknown current runtime/model source verification receipt')
    reuse=read(verify_ref(reuse_ref))
    if (reuse_ref not in plan['pins'] or reuse.get('epoch')!=34 or reuse.get('policy')!='HASH_VERIFIED_READ_ONLY_E33_RUNTIME'
            or reuse.get('all_hashes_checked') is not True or reuse.get('old_filesystem_assumed') is not False
            or reuse.get('old_model_or_runtime_files_modified') is not False
            or reuse.get('actual_model_tokenizer_native_calls')!=0 or reuse.get('paid_API_GPU_calls')!=0
            or reuse.get('python_wheel_members')!=17498 or reuse.get('model_payload_files_verified')!=9
            or reuse.get('native_BGE_project_assets_verified')!=10 or reuse.get('fresh_model_metadata_lock') is not True
            or reuse.get('runtime_environment')!=str(VENV) or reuse.get('inference_python')!=str(VENV/'bin/python')
            or reuse.get('model_directory')!=str(MODEL)
            or reuse.get('model_assets_lock',{}).get('sha256')!=plan['model_assets_lock_sha256']):
        raise ValueError('Incomplete or mismatched current runtime/model verification')
    if len(assets)!=10 or len({r['path'] for r in assets})!=10:raise ValueError('Exact original10 core/BGE assets required')
    rows={r['path']:r for r in assets}
    required={BINARY:BINARY_SHA,'models/bge-small-en-v1.5/model.onnx':'828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35','models/bge-small-en-v1.5/tokenizer.json':'d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'}
    if any(rows.get(k,{}).get('sha256')!=v for k,v in required.items()):raise ValueError('Wrong core/BGE source')
    if (lock.get('native_core_runtime_version')!='2.3.0' or lock.get('native_NPM_version')!='0.1.33' or lock.get('native_platform_NPM_version')!='0.1.31'
            or lock.get('python_expected_versions')!={'numpy':'2.2.6','onnxruntime':'1.22.1','tokenizers':'0.21.4','torch':'2.7.1+cpu','transformers':'4.52.4','safetensors':'0.5.3'}):raise ValueError('Wrong original stock runtime')
    for row in assets:verify_ref(row)
    pins={r['path']:r for r in plan['pins']}
    for key in ('wheel_lock','native_closure','BGE_source','wheel_members_reference'):
        relative,digest=lock[key+'_path'],lock[key+'_sha256']
        if pins.get(relative,{}).get('sha256')!=digest or sha(checked(relative))!=digest:raise ValueError('Unpinned runtime reference')
    if lock.get('wheel_members_reference_count')!=17498 or lock['wheel_members_reference_sha256']!='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9':raise ValueError('Wrong installed member closure')
    member_ref=lock.get('python_member_manifest')
    if not isinstance(member_ref,dict) or member_ref!=pins.get(lock['wheel_members_reference_path']) or member_ref.get('sha256')!=lock['wheel_members_reference_sha256']:raise ValueError('Runtime member dict/flat aliases differ')
    members=read(checked(lock['wheel_members_reference_path']))
    if len(members)!=17498 or len({r['path'] for r in members})!=17498:raise ValueError('Wrong installed member count')
    for row in members:
        rel=row['path']
        if not isinstance(rel,str) or PurePosixPath(rel).is_absolute() or any(x in ('','.','..') for x in rel.split('/')):raise ValueError('Unsafe external member')
        file=VENV/rel;no_symlink(file)
        if not file.is_file() or file.stat().st_size!=row['bytes'] or sha(file)!=row['sha256']:raise ValueError('External admitted wheel member changed')
    if Path(plan['external_python_environment'])!=VENV or Path(plan['inference_python'])!=VENV/'bin/python':raise ValueError('Wrong external interpreter/environment')
    verify_model_assets(plan)
    return lock


def read_json_line(line):
    return json.loads(line,object_pairs_hook=_object,parse_float=_float,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSONL')))
