"""One exact root-approved asset preparation call; no ML, case or scorer mode."""
from pathlib import Path
import hashlib, importlib.util, json, os, stat, sys, time
sys.dont_write_bytecode = True
W = Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
R = W / 'project'
PLAN_SHA = '58c71f4da390e9dc62d24ceb1bec637d5986b752e4287c5c7ff3b552431e59f4'
RUNTIME_SHA = 'e8c191e911be00a736eef7598b79d790323eb43c92d97874162214e414482bcd'
OWNER_SHA = 'f18924b1456dcf51c461181c233ff4511cd3e479982f48b109a0e4126b5c3af0'
SOURCE_ROWS = {'acquisition_source': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/runtime/acquire_assets.py', 'bytes': 17027, 'sha256': '45570f28ea4ebbfcd3ead1dc6d4672484af951d4724bceaa0b3760e29995b6b6'}, 'network_source': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/runtime/acquisition_network.py', 'bytes': 2362, 'sha256': '77fd716be0c1197de896cb99cc41caca596dd59c73257edf5dcc0ee68bf9a68b'}, 'validator_source': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/runtime/model_assets_guard.py', 'bytes': 13916, 'sha256': '040daf8aab26be76c8e86469ac747e559bd9277a6476127da8d8c1133609512f'}, 'identity_helper_source': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/asset_identity.py', 'bytes': 5638, 'sha256': 'f271c0077be23c34fbb29cfb5728d671371a4646ac9030072ec7b538eb819499'}, 'preacquisition_catalog': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/research/CLASSIC_PREACQUISITION_CATALOG.json', 'bytes': 5960, 'sha256': '6023ccec0a48a5cb4f018e8be94a236d0479454ccb92deabd7c25fadf67724d3'}, 'baseline_catalog': {'path': 'experiments/sota-2026-10-22/candidate/epoch40/MODEL_B354_ASSETS.expected.json', 'bytes': 3916, 'sha256': '30657c23de7feae478af2b951c814ff5e4be3c69c7a90c08d0f268a2172eea11'}}


def regular(path):
    path = Path(path).absolute()
    if path != path.resolve() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('CANONICAL_REGULAR_SOURCE_REQUIRED')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('NONREGULAR_SOURCE_REFUSED')
    return path


def sha(path):
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def checked_public(row):
    if set(row) != {'path', 'bytes', 'sha256'} or type(row['bytes']) is not int:
        raise ValueError('CANONICAL_SOURCE_REF_REQUIRED')
    rel = Path(row['path'])
    if rel.is_absolute() or '..' in rel.parts or '\\' in row['path']:
        raise ValueError('PUBLIC_SOURCE_PATH_REQUIRED')
    file = regular(R / rel)
    if file.stat().st_size != row['bytes'] or sha(file) != row['sha256']:
        raise ValueError('EXACT_PUBLIC_SOURCE_HASH_REQUIRED')
    return file


def owner():
    if sha(W / 'owner.json') != OWNER_SHA:
        raise ValueError('OWNER_BYTES_CHANGED')
    record = json.loads((W / 'owner.json').read_text())
    fields = Path('/proc/120232/stat').read_text().rsplit(')', 1)[1].split()
    fd = Path('/proc/120232/fd/3'); info = fd.stat()
    if int(fields[19]) != 27979422 or fields[0] in ('Z', 'X') or time.time() >= record['expires_unix'] or (W / 'release.request').exists():
        raise ValueError('CURRENT_OWNER_REQUIRED')
    if (info.st_dev, info.st_ino) != (33, 13626) or os.readlink(fd) != '/tmp/ruvector-sota-2026-10-22/exclusive.work.lock':
        raise ValueError('EXACT_OWNER_FD_REQUIRED')
    if os.sched_getaffinity(0) != {0, 1} or os.sched_getaffinity(120232) != {0, 1}:
        raise ValueError('CPU_0_1_REQUIRED')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != '4632fb06-b0ef-4df5-b72b-0e875bbad810' or Path('/proc/self/ns/pid').stat().st_ino != 4026532200:
        raise ValueError('BOOT_PID_NAMESPACE_CHANGED')
    held = False
    for line in Path('/proc/locks').read_text().splitlines():
        words = line.split()
        if len(words) >= 8 and words[1:5] == ['FLOCK', 'ADVISORY', 'WRITE', '120232']:
            a, b, inode = words[5].split(':')
            held |= (int(a, 16), int(b, 16), int(inode)) == (os.major(33), os.minor(33), 13626)
    if not held:
        raise ValueError('EXACT_OWNER_KERNEL_FLOCK_REQUIRED')


def main():
    owner()
    plan_path = W / 'MODEL_ACQUISITION_PLAN.v1.json'
    request_path = W / 'MODEL_ACQUISITION_RUNTIME_REQUEST.v1.json'
    if sha(plan_path) != PLAN_SHA or sha(request_path) != RUNTIME_SHA:
        raise ValueError('FROZEN_PLAN_RUNTIME_REQUEST_REQUIRED')
    plan = json.loads(plan_path.read_text()); request = json.loads(request_path.read_text())
    if plan['sources'] != SOURCE_ROWS or plan['runtime_request']['sha256'] != RUNTIME_SHA:
        raise ValueError('SOURCE_API_RUNTIME_BINDING_CHANGED')
    for row in SOURCE_ROWS.values():
        checked_public(row)
    for row in plan['source_package_files']:
        checked_public(row)
    for row in plan['runtime_authority_refs'].values():
        checked_public(row)
    authority = json.loads((R / plan['runtime_authority_refs']['runtime_assets_lock']['path']).read_text())
    if request != {'venv': authority['external_environment'], 'member_manifest_path': str(R / authority['python_member_manifest']['path']), 'member_manifest_sha256': authority['python_member_manifest']['sha256'], 'wheel_identity_path': str(R / authority['python_wheel_lock']['path']), 'native_asset_root': authority['native_asset_root'], 'assets': authority['assets']}:
        raise ValueError('EXACT_RUNTIME_SOURCE_AUTHORITY_REQUIRED')
    candidate = R / 'experiments/sota-2026-10-22/candidate/epoch40'
    if any(p.name == '__pycache__' or p.suffix == '.pyc' for p in candidate.rglob('*')):
        raise ValueError('PREEXISTING_BYTECODE_REFUSED')
    owner()
    entry = checked_public(SOURCE_ROWS['acquisition_source'])
    spec = importlib.util.spec_from_file_location('e40_exact_root_acquisition', entry)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.prepare_assets(plan_path, PLAN_SHA, root=R, runtime_request=request)
    if result['status'] != 'ALL18_MODEL_PAYLOADS_AND_RUNTIME_HASH_ADMITTED_NO_ML':
        raise ValueError('FULL_ASSET_PREPARATION_NOT_COMPLETE')
    print(json.dumps({'status': result['status'], 'plan_sha256': PLAN_SHA, 'profiles': sorted(result['profiles']), 'model_tokenizer_native_calls': result['model_tokenizer_native_calls'], 'case_oracle_reads': result['case_oracle_reads']}, allow_nan=False))


if __name__ == '__main__':
    main()
