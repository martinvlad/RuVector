"""Freeze exact historical sources and one preselected FP32 typed-reader study."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import time
from datetime import datetime, timezone

P = 'experiments/sota-2026-10-22/'
SOURCE = '0c4392bb8b13a901dc416882f850230c1075fb6a'
LEASE = '9a995890a3cde61f3457cb405d712f67bf5555df'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def canonical_dir(path):
    p = Path(path).absolute()
    assert p == p.resolve() and p.is_dir()
    assert not any(x.is_symlink() for x in [p, *p.parents])
    return p


def identity(root, name):
    assert isinstance(name, str) and name and '\\' not in name
    assert not PurePosixPath(name).is_absolute()
    assert not any(x in ('', '.', '..') for x in name.split('/'))
    p = root / name
    assert p == p.resolve() and p.is_relative_to(root)
    assert not any(x.is_symlink() for x in [p, *p.parents])
    assert stat.S_ISREG(p.lstat().st_mode)
    return {'path': name, 'bytes': p.stat().st_size, 'sha256': digest(p)}


def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())


def build(args):
    root, kit, scope = map(canonical_dir, (args.project, args.kit, args.scope))
    manifest_pins = {'CHECKPOINT_MANIFEST.json': '96f7cb566db59102b79bd9d9b6f935e642a930b8014887e879349bc84dc4a74b', 'KIT_MANIFEST.json': 'b5dc6bab62ea0c93e02dedc6ac688ac12fdf3b8f0bc73e0ac705c7486e9ecdd4', 'BASE_PUBLIC_MANIFEST.json': '0db67a018ad5fd9deba1cfb0bd8897537a330dd2353f169e6e387e86e09fce7a', 'BASE_DOWNLOADS.json': 'cc42558737c7a5a826fb3b600ecd269b2e75dd39703cf43377422fb02c7e4912'}
    for filename, want in manifest_pins.items(): assert digest(kit / filename) == want, filename
    owner = json.loads((scope / 'owner.json').read_text())
    assert time.time() + 1800 < owner['expires_unix']
    os.kill(owner['pid'], 0)
    assert Path('/proc/' + str(owner['pid']) + '/stat').read_text().split()[2] != 'Z'
    spec_name = P + 'epoch21/PLAN_SPEC.json'
    spec = json.loads((root / spec_name).read_text())
    helper_path = root / spec['publication_helper']['path']
    assert identity(root, spec['publication_helper']['path']) == spec['publication_helper']
    mod_spec = importlib.util.spec_from_file_location('reviewed20public', helper_path)
    helper = importlib.util.module_from_spec(mod_spec); mod_spec.loader.exec_module(helper)
    current = helper.walk_current(root)
    freeze_name, plan_name = (P + 'epoch21/' + n for n in ('candidate-source-freeze.json', 'plan.json'))
    for name in (freeze_name, plan_name): assert not os.path.lexists(root / name)
    for name in current:
        assert not name.startswith(P + 'epoch21/runs/')
        assert name not in {P + 'epoch21/' + n for n in
                           ('NATIVE_ADMISSION.json', 'CONFIRMATION_ADMISSION.json', 'RESULTS.json',
                            'USED_IDENTITIES.json', 'EPOCH_MANIFEST.json')}
        assert not name.endswith(('/inputs.dev.json', '/inputs.confirmation.json',
                                  '/gold.dev.json', '/gold.confirmation.json'))
    historical = {}
    for filename in ('CHECKPOINT_MANIFEST.json', 'KIT_MANIFEST.json'):
        for r in json.loads((kit / filename).read_text())['project_files']:
            row = {k: r[k] for k in ('path', 'bytes', 'sha256')}
            assert row['path'] not in historical or historical[row['path']] == row
            historical[row['path']] = row
    base = {r['path']: r for r in json.loads((kit / 'BASE_PUBLIC_MANIFEST.json').read_text())['files']}
    for name in json.loads((kit / 'BASE_DOWNLOADS.json').read_text())['paths']:
        row = {k: base[name][k] for k in ('path', 'bytes', 'sha256')}
        assert name not in historical or historical[name] == row
        historical[name] = row
    assert len(historical) == 3092 and not set(historical).intersection(current)
    for name, row in historical.items(): assert identity(root, name) == row, name
    rows = [identity(root, n) for n in sorted(set(historical) | set(current))]
    refs = {key: identity(root, name) for key, name in spec['references'].items()}
    by_path = {r['path']: r for r in rows}
    for row in refs.values(): assert by_path.get(row['path']) == row
    assert spec['limits'] == {'threads': 2, 'interop_threads': 1, 'seconds_per_batch': 600,
        'worker_attempts': 2, 'native_batches': 2, 'candidate_configs': 1, 'paid_calls': 0, 'GPU_calls': 0}
    assert spec['train'] == [] and spec['calibration'] == []
    snapshot = {'schema_version': 1, 'epoch': 21, 'at': datetime.now(timezone.utc).isoformat(),
        'source_checkpoint': SOURCE, 'planning_lease_commit': LEASE, 'files': rows,
        'historical_sources': len(historical), 'new_public_sources': len(current),
        'model_native_calls_before_freeze': 0, 'new_legal_case_or_annotation_choices_parsed': 0,
        'scope': 'All exact restored CP/KIT/BASE source plus stable new public source/protocol/role/preparation bytes. Exact external reader/native/BGE/wheel assets are separately verified. Lazy legal inputs and gold are not yet materialized.'}
    write_new(root / freeze_name, snapshot)
    frozen = identity(root, freeze_name)
    plan = {'schema_version': 1, 'epoch': 21, 'study_id': 'native-deberta-v3-fp32-typed-e21',
        'source_checkpoint': SOURCE, 'planning_lease_commit': LEASE,
        'actual_project': str(root), 'inference_python': str(root / 'retrieval/.venv/bin/python'),
        'lease_expires_unix': owner['expires_unix'], 'pins': rows + [frozen],
        'limits': spec['limits'], 'train': [], 'calibration': [], 'phases': spec['phases'],
        'source_freeze_path': freeze_name, 'source_freeze_sha256': frozen['sha256'],
        'candidate_configs': 1, 'model_precision': 'Original FP16-stored learned tensors loaded explicitly FP32; source bytes unchanged; no quantization.',
        'source_model_storage_precision': '394 learned FP16 tensors and one I64 position buffer; exact pinned safetensors header required.',
        'benchmark_scope': 'Licensed original ContractNLI transfer diagnostic with matched same-model retrieval controls; no official JevBench, full LegalBench or ClaimBench placement.',
        'semantic_gate': 'The three fixed exposed engineering canaries must all pass in each owned process before any new legal source-case parse; canaries excluded from benchmark metrics.',
        'confirmation_gate': 'Only exact frozen reserved project-model-unused CONF24, after independent DEV acceptance and full-cost runtime admission; never train/select on CONF labels.',
        'phase_counter_caps': {'NLI_forwards': 75, 'native_queries': 27, 'native_indexes': 9},
        'price_plan': {'new_paid_API_GPU_USD': 0, 'remaining_authorized_paid_USD': 0},
        'champion': 'SubmittedNative104/RRF10 unchanged', 'promotion_allowed': False,
        'new_submission_allowed': False, 'official_score': None, 'official_rank': None}
    for key, row in refs.items():
        plan[key + '_path'] = row['path']; plan[key + '_sha256'] = row['sha256']
    write_new(root / plan_name, plan)
    return {'source_files': len(rows), 'plan_pins': len(rows) + 1,
            'snapshot': frozen, 'plan': identity(root, plan_name), 'native_calls': 0}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ('project', 'kit', 'scope'): ap.add_argument('--' + name, type=Path, required=True)
    print(json.dumps(build(ap.parse_args())))
