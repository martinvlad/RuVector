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
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch31'
CANDIDATE = HERE.parent
SOURCE = 'b27d0c39ed3102cd16ba616b1225b7684b76851b'
KIND = 'REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
OWNER_PID, OWNER_TICKS, LOCK_INODE = 87763, 19114443, 13626
OWNER_EXPIRY = 1792874642.5127344
BOOT_ID = '4632fb06-b0ef-4df5-b72b-0e875bbad810'
PIDNS_INODE, LOCK_DEVICE, LOCK_FD, OWNER_GENERATION = 4026532200, 33, 3, 1
BINARY = 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
BASE_MODEL_SHA = 'ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17'
ORIGINAL_READER = 'experiments/sota-2026-10-22/candidate/epoch27/reader/bart_reader.py'
ORIGINAL_READER_SHA = '4101d071c04aced320a902d7b84cb1fd1c30d474683201637150e486ede8b1d9'
PHASES = ('dev',)
TRAIN_IDS = []
HISTORICAL_TRAIN_IDS = [237, 120, 187, 422, 464, 207, 294, 250]
DEV_IDS = [145, 597, 191, 620, 254, 160, 384, 571]
ZERO = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
        'TRAIN_label_reads', 'TRAIN_forward_calls_attempted', 'TRAIN_forward_calls_completed', 'TRAIN_contexts_completed',
        'CONF_input_bank_reads', 'CONF_annotation_choices_attempted', 'CONF_annotation_choices_accessed',
        'DEV_annotation_choices_attempted', 'DEV_annotation_choices_accessed',
        'other_role_annotation_choices_accessed', 'source_evidence_lists_accessed',
        'calibration_calls', 'generation_calls', 'paid_calls', 'GPU_calls', 'HTTP_requests', 'full104_requests')


def phase_zero(phase):
    if phase not in PHASES:
        raise ValueError('Only the archived-state DEV phase is admitted')
    names = ('TRAIN_forward_calls', 'optimizer_initializations', 'backward_calls', 'optimizer_steps',
             'gradient_clips', 'LoRA_B_gradient_checks', 'parameter_artifacts_write')
    return ZERO + ('TRAIN_input_bank_reads', 'TRAIN_annotation_choices_attempted',
        'TRAIN_annotation_choices_accessed', 'fits', 'training_steps') + tuple(
        name + suffix for name in names for suffix in ('_attempted', '_completed'))


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
    owner = read(ROOT.parent / 'owner.json')
    row = proc(OWNER_PID)
    if (owner.get('pid') != OWNER_PID or owner.get('startticks') != OWNER_TICKS
            or owner.get('lock_inode') != LOCK_INODE or owner.get('expires_unix') != OWNER_EXPIRY
            or owner.get('kernel_boot_id')!=BOOT_ID or owner.get('PID_namespace')!=f'pid:[{PIDNS_INODE}]'
            or owner.get('generation')!=OWNER_GENERATION
            or not row or row['ticks'] != OWNER_TICKS or row['state'] in ('Z', 'X')
            or time.time() >= OWNER_EXPIRY or (ROOT.parent / 'release.request').exists()):
        raise ValueError('Guardian dead/reused/released/expired or lease changed')
    lock = ROOT.parent.parent / 'exclusive.work.lock'
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


def archive_seal(provisional, value):
    ref = value.get('archived_model_seal')
    target = verify_ref(ref)
    if target != STUDY/'ARCHIVED_MODEL_SEAL.json':
        raise ValueError('Wrong canonical archived model seal')
    seal = read(target)
    keys = {'schema_version','epoch','kind','status','source_checkpoint','parameter_artifact',
        'train_raw','train_execution','independent_training_report','original_source_plan',
        'original_source_freeze','historical_training_epoch','historical_training_document_ids','data_roles','hypotheses'}
    if (set(seal)!=keys or not same(seal.get('schema_version'),1) or seal.get('epoch')!=31
            or seal.get('kind')!=KIND or seal.get('status')!='ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED'
            or seal.get('source_checkpoint')!=SOURCE or seal.get('historical_training_epoch')!=30
            or not same(seal.get('historical_training_document_ids'),HISTORICAL_TRAIN_IDS)
            or not same(seal.get('data_roles'),{'train':[],'dev':DEV_IDS,'calibration':[],'confirmation':[]})
            or seal.get('hypotheses')!=['nda-17','nda-7','nda-3']
            or not same(ref,provisional['archived_model_seal'])
            or not same(value.get('parameter_artifact'),seal['parameter_artifact'])):
        raise ValueError('Wrong immutable archived E30 model/current DEV lineage')
    exact = {'parameter_artifact':ROOT/'experiments/sota-2026-10-22/epoch30/runs/train/trained-parameters.public.json',
        'train_raw':ROOT/'experiments/sota-2026-10-22/epoch30/runs/train/raw.json',
        'train_execution':ROOT/'experiments/sota-2026-10-22/epoch30/runs/train/execution.json',
        'original_source_plan':ROOT/'experiments/sota-2026-10-22/epoch30/plan.json',
        'original_source_freeze':ROOT/'experiments/sota-2026-10-22/epoch30/source-freeze.json'}
    for key in ('parameter_artifact','train_raw','train_execution','independent_training_report','original_source_plan','original_source_freeze'):
        file=verify_ref(seal[key])
        if key in exact and file!=exact[key]:raise ValueError('Wrong archived lineage path: '+key)
        if key=='independent_training_report' and not file.is_relative_to(ROOT/'experiments/sota-2026-10-22/audit/epoch30'):
            raise ValueError('Historical independent TRAIN report outside exact E30 audit scope')
    if (seal['parameter_artifact']['bytes']!=5950520
            or seal['parameter_artifact']['sha256']!='46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'
            or seal['original_source_plan']['sha256']!='d6c46944bbac2cb8ef65a51e68d927e10b869123004f941d56292cef1e0bd94b'
            or seal['original_source_freeze']['sha256']!='179a0463338808f2d39925fe480a02c4eb144ee634044594a8c68ca51a35e14a'
            or seal['parameter_artifact']['path']!=provisional['trained_parameters_path']):
        raise ValueError('Archived model was substituted or relabelled')
    execution=read(checked(seal['train_execution']['path']))
    counts=execution.get('raw_operation_counters')
    if (execution.get('epoch')!=30 or execution.get('kind')!='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
            or execution.get('phase')!='train' or execution.get('status')!='WORKER_COMPLETED'
            or not same(execution.get('worker_attempts_reserved'),1)
            or not same(execution.get('verified_worker_starts'),1) or execution.get('uncertain_start') is not False
            or execution.get('owned_live_processes_closed') is not True or execution.get('owned_live_group_members')!=[]
            or execution.get('raw_operation_counters_source')!='raw.json' or execution.get('operation_counts_complete') is not True
            or execution.get('raw_sha256')!=seal['train_raw']['sha256'] or execution.get('raw_bytes')!=seal['train_raw']['bytes']
            or not isinstance(counts,dict) or any(type(counts.get(k)) is not int or counts[k]!=24
                for k in ('TRAIN_forward_calls_completed','backward_calls_completed','optimizer_steps_completed','training_steps'))):
        raise ValueError('Historical closed complete24-update TRAIN proof required')
    report=read(checked(seal['independent_training_report']['path']))
    if (report.get('epoch')!=30 or report.get('kind')!='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
            or report.get('train_integrity_passed') is not True):
        raise ValueError('Historical independent TRAIN integrity gate required')
    for report_key,seal_key in {'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution',
            'plan':'original_source_plan','freeze':'original_source_freeze'}.items():
        if not same(report.get('evidence',{}).get(report_key),seal[seal_key]):
            raise ValueError('Historical TRAIN report/ref lineage differs')
    return seal


def admission(path, provisional, plan_sha, phase):
    if phase!='dev' or Path(path).absolute()!=STUDY/'SOURCE_ADMISSION.json':
        raise ValueError('E31 admits only one fresh SOURCE-bound DEV phase')
    value=read(path)
    if (value.get('epoch')!=31 or value.get('kind')!=KIND or value.get('phase')!='dev'
            or value.get('scope')!='benchmarks/ruvector-sota-2026-10-22/'
            or value.get('verified_actual_remote_readback') is not True
            or value.get('plan_sha256')!=plan_sha or value.get('source_freeze_sha256')!=provisional['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}',value.get('published_source_commit',''))):
        raise ValueError('Actual current SOURCE readback required before DEV input')
    archive_seal(provisional,value)  # Opaque artifact/TRAIN raw hashes; never tensor/label decode.
    return value,owner_lock(value)



def dispatch_proof(plan, plan_sha, admission_path, wait_seconds=3):
    """Bind this detached supervisor to the unique already-burned dispatch."""
    claim_path=STUDY/'DISPATCH_RESERVATION.json';claim=read(claim_path)
    expected={'schema_version':1,'epoch':31,'kind':KIND,'phase':'dev',
        'plan_sha256':plan_sha,'source_freeze_sha256':plan['source_freeze_sha256'],
        'archived_model_seal_sha256':plan['archived_model_seal_sha256'],
        'admission_sha256':sha(admission_path),'kernel_boot_id':BOOT_ID,
        'pid_namespace_inode':PIDNS_INODE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
    if any(not same(claim.get(key),value) for key,value in expected.items()):
        raise ValueError('Wrong exact pre-dispatch budget/source/namespace claim')
    for key in ('dispatch_monotonic_seconds','dispatch_unix_seconds'):
        if type(claim.get(key)) not in (int,float) or not math.isfinite(claim[key]):
            raise ValueError('Missing finite pre-dispatch clocks')
    elapsed=time.monotonic()-claim['dispatch_monotonic_seconds']
    if not 0<=elapsed<600:raise TimeoutError('Dispatch budget expired or clock from another boot')
    attempt_path=STUDY/'DISPATCH_ATTEMPT.json'
    until=min(time.monotonic()+wait_seconds,claim['dispatch_monotonic_seconds']+585)
    while not attempt_path.exists():
        if time.monotonic()>=until:raise RuntimeError('Detached dispatch identity remains uncertain; no retry')
        time.sleep(.01)
    attempt=read(attempt_path);actual=proc(os.getpid())
    if (any(not same(attempt.get(key),value) for key,value in expected.items())
            or attempt.get('dispatch_monotonic_seconds')!=claim['dispatch_monotonic_seconds']
            or attempt.get('dispatch_unix_seconds')!=claim['dispatch_unix_seconds']
            or attempt.get('pid')!=os.getpid() or not actual
            or attempt.get('startticks')!=actual['ticks']
            or attempt.get('pgid')!=os.getpid() or attempt.get('sid')!=os.getpid()
            or actual['pgid']!=os.getpid() or actual['sid']!=os.getpid()
            or attempt.get('verified_launcher_start') is not True
            or attempt.get('uncertain_launcher_start') is not False):
        raise ValueError('Detached supervisor identity/source/clock mismatch')
    return claim,attempt


def verify_ref(row, defer_contents=False):
    if (not isinstance(row, dict) or set(row) != {'path', 'bytes', 'sha256'}
            or type(row.get('bytes')) is not int or row['bytes'] < 0):
        raise ValueError('Invalid exact file reference')
    if not isinstance(row.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
        raise ValueError('Invalid exact file digest')
    target = checked(row['path'])
    if target.stat().st_size != row['bytes'] or (not defer_contents and sha(target) != row['sha256']):
        raise ValueError('Frozen bytes changed: ' + row['path'])
    return target


def verify_plan(path, expected, phase):
    if phase not in PHASES:
        raise ValueError('Unknown phase; no automatic confirmation')
    if Path(path).absolute() != STUDY / 'plan.json' or sha(path) != expected:
        raise ValueError('Wrong exact source plan identity')
    plan = read(path)
    if (plan.get('epoch') != 31 or plan.get('kind') != KIND
            or plan.get('source_checkpoint') != SOURCE or plan.get('actual_project') != str(ROOT)
            or not same(plan.get('data_roles'), {'train': TRAIN_IDS, 'dev': DEV_IDS, 'calibration': [], 'confirmation': []})):
        raise ValueError('Only the fixed disjoint TRAIN/DEV diagnostic roles admitted')
    exact = {'owned_workers': 1, 'per_phase_owned_workers': 1,
        'CPU_threads': 2, 'CPU_affinity': [0, 1], 'seconds_per_batch': 600,
        'native_corpus_batches': 1, 'TRAIN_worker_attempts': 0, 'DEV_worker_attempts': 1,
        'CONF_worker_attempts': 0, 'paid_calls': 0, 'GPU_calls': 0}
    for key, value in exact.items():
        if not same(plan['limits'].get(key), value):
            raise ValueError('Wrong fixed budget: ' + key)
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate frozen source identity')
    for row in pins:
        # The archived SOURCE admission precedes hashing the DEV input projection.
        verify_ref(row)
    for name in ('common.py', 'launch.py', 'network_guard.py', 'node_guard.cjs', 'cpu_guard.py'):
        if str((HERE / name).relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned runtime source: ' + name)
    if plan.get('worker_path') != str((CANDIDATE / 'worker.py').relative_to(ROOT)):
        raise ValueError('Wrong core worker path')
    if plan['worker_path'] not in by_path:
        raise ValueError('Unpinned core worker')
    if (plan.get('native_worker_path') != str((CANDIDATE / 'native_helper.cjs').relative_to(ROOT))
            or plan['native_worker_path'] not in by_path):
        raise ValueError('Unpinned exact native identity helper')
    by_phase = plan.get('expected_operation_counters')
    if not isinstance(by_phase, dict) or set(by_phase) != set(PHASES):
        raise ValueError('The sole fixed DEV counter contract is required')
    for expected_counters in by_phase.values():
        if (not isinstance(expected_counters, dict) or not expected_counters
                or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in expected_counters.items())):
            raise ValueError('Exact nonnegative integer phase operation budget required')
    for key in ('dev_inputs', 'runtime_assets_lock', 'source_freeze', 'archived_model_seal',
                'bart_assets_lock', 'original_reader', 'runtime_policy_addendum'):
        if by_path.get(plan[key + '_path'], {}).get('sha256') != plan[key + '_sha256']:
            raise ValueError('Missing exact input/runtime/source-freeze pin: ' + key)
    if plan['original_reader_path'] != ORIGINAL_READER or plan['original_reader_sha256'] != ORIGINAL_READER_SHA:
        raise ValueError('Only the unchanged exact original2020 BART safe loader admitted')
    if (plan['runtime_policy_addendum_path'] != 'experiments/sota-2026-10-22/audit/epoch30/runtime-policy-addendum-v1.json'
            or plan['runtime_policy_addendum_sha256'] != 'c4b3c3243ac089d5966e394f3ead60f57a15f59cc24b496960334124c14dbacd'):
        raise ValueError('Prospectively frozen narrow dependency capability policy required')
    if plan['source_freeze_path'] != str((STUDY / 'source-freeze.json').relative_to(ROOT)):
        raise ValueError('Wrong canonical source freeze')
    if (plan['archived_model_seal_path']!=str((STUDY/'ARCHIVED_MODEL_SEAL.json').relative_to(ROOT))
            or not same(plan.get('archived_model_seal'),by_path.get(plan['archived_model_seal_path']))):
        raise ValueError('Exact current archived-model seal must be plan/source pinned')
    legacy={'model.py':'d2aa6ea5e1507458d454f76c7643bbeb2d25ca1620588939ec45823f168939fd',
        'algorithm.py':'a6db5363122add0f3fde2ed2dc2667fa94e349f3d4f9dffb8bca54f3927a3fa9',
        'parameter_codec.py':'03dc310a14acdf23e9494ba5d41b58f644e7d137177c344f5d4e012cdc03b42e'}
    for name,digest in legacy.items():
        path='experiments/sota-2026-10-22/candidate/epoch30/'+name
        if by_path.get(path,{}).get('sha256')!=digest:
            raise ValueError('Exact unchanged E30 model/algorithm/codec dependency required')
    if plan.get('trained_parameters_path') != str((ROOT / 'experiments/sota-2026-10-22/epoch30/runs/train/trained-parameters.public.json').relative_to(ROOT)):
        raise ValueError('Wrong immutable trained-parameter artifact path')
    frozen = read(checked(plan['source_freeze_path']))
    if frozen.get('epoch') != 31 or frozen.get('kind') != KIND or frozen.get('source_checkpoint') != SOURCE:
        raise ValueError('Wrong source-freeze epoch/kind/checkpoint')
    entries = frozen['entries']
    if len({row['path'] for row in entries}) != len(entries):
        raise ValueError('Duplicate source-freeze entry')
    for row in entries:
        if not same(by_path.get(row['path']), row):
            raise ValueError('Source-freeze entry absent/different from exact plan pin')
    return plan


def verify_runtime(plan):
    lock = read(checked(plan['runtime_assets_lock_path']))
    assets = lock['assets']
    if len(assets) != 10 or len({row['path'] for row in assets}) != 10:
        raise ValueError('Exact original10 core/BGE assets required')
    rows = {row['path']: row for row in assets}
    required = {BINARY: BINARY_SHA,
        'models/bge-small-en-v1.5/model.onnx': '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35',
        'models/bge-small-en-v1.5/tokenizer.json': 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'}
    for path, expected in required.items():
        if rows.get(path, {}).get('sha256') != expected:
            raise ValueError('Wrong original core/BGE identity')
    if (lock.get('native_core_runtime_version') != '2.3.0'
            or lock.get('native_NPM_version') != '0.1.33'
            or lock.get('native_platform_NPM_version') != '0.1.31'
            or lock.get('python_expected_versions') != {'numpy': '2.2.6', 'onnxruntime': '1.22.1', 'tokenizers': '0.21.4',
                'torch': '2.7.1+cpu', 'transformers': '4.52.4', 'safetensors': '0.5.3'}):
        raise ValueError('Wrong frozen original runtime versions')
    for row in assets:
        verify_ref(row)
    pins = {row['path']: row for row in plan.get('pins', [])}
    for key in ('wheel_lock', 'native_closure', 'BGE_source'):
        relative, digest = lock[key + '_path'], lock[key + '_sha256']
        if pins.get(relative, {}).get('sha256') != digest or sha(checked(relative)) != digest:
            raise ValueError('Unpinned original runtime dependency: ' + key)
    reference = lock.get('wheel_members_reference_path')
    digest = lock.get('wheel_members_reference_sha256')
    if (digest != '87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'
            or lock.get('wheel_members_reference_count') != 17498
            or pins.get(reference, {}).get('sha256') != digest or sha(checked(reference)) != digest):
        raise ValueError('Wrong original installed-wheel member reference')
    members = read(checked(reference))
    if len(members) != 17498 or len({row['path'] for row in members}) != 17498:
        raise ValueError('Wrong exact17498 installed-wheel closure')
    for row in members:
        verify_ref({'path': 'retrieval/.venv/' + row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    reader_path = checked(plan['original_reader_path'])
    if pins.get(plan['original_reader_path'], {}).get('sha256') != plan['original_reader_sha256']:
        raise ValueError('Unpinned exact original BART reader')
    bart_directory = ROOT / plan['bart_model_directory']
    if plan['bart_model_directory'] != 'models/bart-large-mnli-d7645e':
        raise ValueError('Wrong original2020 BART model directory')
    public_lock = checked(plan['bart_assets_lock_path'])
    direct_lock = bart_directory / 'asset-lock.json'
    expected_lock_sha = '29eaa17d71b1b2bf2929eb0d22c370307ae2b1d47a97aa6b385e8abc363661b1'
    if (lock.get('BART_public_asset_lock_path') != plan['bart_assets_lock_path']
            or lock.get('BART_public_asset_lock_sha256') != expected_lock_sha
            or lock.get('BART_asset_lock_path') != str(direct_lock.relative_to(ROOT))
            or lock.get('BART_asset_lock_sha256') != expected_lock_sha
            or sha(public_lock) != expected_lock_sha or sha(checked(lock['BART_asset_lock_path'])) != expected_lock_sha
            or public_lock.read_bytes() != direct_lock.read_bytes()):
        raise ValueError('Exact original direct/public BART lock identity required')
    bart_assets = lock.get('BART_assets')
    original_assets = read(public_lock)['files']
    wanted = {str((bart_directory / row['path']).relative_to(ROOT)): (row['bytes'], row['sha256']) for row in original_assets}
    if (not isinstance(bart_assets, list) or len(bart_assets) != 8
            or len({row['path'] for row in bart_assets}) != 8
            or {row['path']: (row['bytes'], row['sha256']) for row in bart_assets} != wanted):
        raise ValueError('Exact original8 BART files required; no conversion/extra assets')
    for row in bart_assets:
        verify_ref(row)
    reader = load_module('epoch31_stdlib_original_bart_asset_verifier', reader_path)
    reader.verify_runtime_assets(bart_directory, public_lock)
    return lock
