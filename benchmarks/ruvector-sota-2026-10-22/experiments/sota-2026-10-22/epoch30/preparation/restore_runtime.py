"""Restore fresh runtime from individually verified frozen epoch26 wheel members.

The frozen member receipt is reused by hash, avoiding a duplicate 4.6 MB manifest.
Every one of the 17,498 source and destination members is actually SHA256 checked.
No ML/native/tokenizer import, source case parse, inference, pip hook or network.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

MEMBER_REFERENCE = 'experiments/sota-2026-10-22/epoch26/preparation/runtime-members/python-wheel-members.json'
MEMBER_SHA = '87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'
WHEEL_LOCK = 'experiments/sota-2026-10-22/epoch17/preparation/python-wheel-identities.json'
WHEEL_SHA = '6689210699a4171b54a38f8d14edba78c4b4b6390c76b6b05293a32f1ea2b8de'
ASSET_REFERENCE = 'experiments/sota-2026-10-22/epoch26/preparation/runtime-assets.lock.json'
ASSET_SHA = '0229a75ce29f70d2fbed3c2b99abd756a48d0c02eac393985c7b90fea1e4032f'


def main():
    parser = argparse.ArgumentParser()
    for name in ('project', 'public-cache', 'wheel-cache'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    project = args.project.absolute()
    study = project / 'experiments/sota-2026-10-22/epoch30'
    helper = project / 'experiments/sota-2026-10-22/epoch22/preparation/restore_public_runtime_cache_v1.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '328cb60925c97e54f460f7c64ec5d12cd1d2c4d3062a3aaaa7812fbd2d362c20'
    spec = importlib.util.spec_from_file_location('frozen_public_runtime_helpers', helper)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    for path in (project, args.public_cache, args.wheel_cache):
        h.no_symlink(path)
    for relative, digest in ((MEMBER_REFERENCE, MEMBER_SHA), (WHEEL_LOCK, WHEEL_SHA),
                             (ASSET_REFERENCE, ASSET_SHA)):
        assert h.digest(project / relative) == digest
    members = json.loads((project / MEMBER_REFERENCE).read_text())
    assert len(members) == 17498 and len({row['path'] for row in members}) == 17498
    wheels = json.loads((project / WHEEL_LOCK).read_text())['wheels']
    assert len(wheels) == 31
    for row in wheels:
        assert h.identity(args.wheel_cache / row['filename'], row)
    wheel_names = {row['filename'] for row in wheels}
    assets = json.loads((project / ASSET_REFERENCE).read_text())
    assert len(assets['assets']) == 10
    for row in assets['assets']:
        h.link_asset(args.public_cache / row['path'], project / row['path'], row)
    venv = project / 'retrieval/.venv'
    assert not venv.exists()
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True)
    linked = 0
    for row in members:
        relative = h.relative(row['path'])
        assert row['wheel'] in wheel_names
        old = args.public_cache / 'retrieval/.venv' / relative
        new = venv / relative
        assert new.is_relative_to(venv) and h.identity(old, row)
        h.no_symlink(new)
        assert not new.exists()
        new.parent.mkdir(parents=True, exist_ok=True)
        os.link(old, new, follow_symlinks=False)
        assert h.identity(new, row)
        linked += 1
    packages = ['torch', 'transformers', 'safetensors', 'numpy', 'tokenizers', 'onnxruntime']
    query = 'import importlib.metadata as m,json;print(json.dumps({x:m.version(x) for x in ' + repr(packages) + '}))'
    versions = json.loads(subprocess.check_output([str(venv / 'bin/python'), '-B', '-I', '-c', query], text=True))
    assets['python_expected_versions'] = {key: versions[key] for key in ('numpy', 'onnxruntime', 'tokenizers')}
    h.put(study / 'preparation/runtime-assets.lock.json', assets)
    report = {'schema_version': 1, 'epoch': 30,
        'status': 'FRESH_CPU_RUNTIME_FROM_FULLY_VERIFIED_PUBLIC_BYTES',
        'public_assets': 10, 'official_CPU_wheels': 31, 'verified_wheel_members': linked,
        'byte_identical_hardlinks': linked, 'official_zip_extractions': 0,
        'wheel_lock_path': WHEEL_LOCK, 'wheel_lock_sha256': WHEEL_SHA,
        'wheel_members_reference_path': MEMBER_REFERENCE, 'wheel_members_receipt_sha256': MEMBER_SHA,
        'source_and_destination_all_member_SHA256_verified': True,
        'frozen_reference_binds_prior_official_wheel_RECORD_validation': True,
        'python_expected_versions': versions, 'inference_python': str(venv / 'bin/python'),
        'BGE_NLI_native_tokenizer_fit_paid_GPU_network_calls': 0,
        'wall_seconds': time.monotonic() - started, 'torch_instantiated': False,
        'old_environment_not_blindly_reused': True, 'duplicate_member_manifest_created': False}
    h.put(study / 'preparation/runtime-restoration.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
