"""Actual source/asset/version admission, without a model or native import."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def checked(path, directory=False):
    p = Path(path).absolute()
    assert p == p.resolve() and not any(x.is_symlink() for x in [p, *p.parents])
    assert p.is_dir() if directory else p.is_file()
    return p


def main():
    os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    ap = argparse.ArgumentParser()
    for n in ('project', 'plan', 'out'): ap.add_argument('--' + n, type=Path, required=True)
    a = ap.parse_args(); root = checked(a.project, True); path = checked(a.plan)
    out = a.out.absolute()
    assert out == out.resolve() and not os.path.lexists(out)
    assert not any(x.is_symlink() for x in [out, *out.parents])
    assert out.parent == root / 'experiments/sota-2026-10-22/epoch21/preparation'
    p = json.loads(path.read_text()); assert p['actual_project'] == str(root)
    protocol = json.loads(checked(root / p['audit_protocol_path']).read_text())
    assert sha(root / p['audit_protocol_path']) == p['audit_protocol_sha256']
    model = json.loads(checked(root / p['model_assets_lock_path']).read_text())
    assert protocol['model']['repository'] == model['repository']
    assert protocol['model']['revision'] == model['revision']
    assert protocol['model']['assets'] == model['assets']
    launcher = checked(root / p['candidate_launcher_path'])
    assert sha(launcher) == p['candidate_launcher_sha256']
    python = p['inference_python']
    run = subprocess.run([python, '-B', str(launcher), '--plan', str(path),
        '--check-plan', '--verify-assets'], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert run.returncode == 0, run.stderr.decode()
    actual = json.loads(run.stdout)
    assert actual['status'] == 'FULL_UNMOCKED_SOURCE_PLAN_PASS'
    assert actual['native_execution_admitted'] is False
    assert actual['asset_verification']['model_native_imports'] == 0
    assert actual['asset_verification']['files'] == 19
    assert actual['asset_verification']['versions'] == 31
    # Read distribution METADATA only. This catches a scorer/runtime mismatch
    # before exposing legal cases or importing a neural framework.
    code = ('import importlib.metadata as m,json,sys;'
            'names=json.loads(sys.argv[1]);'
            'print(json.dumps({n:m.version(n) for n in names},sort_keys=True))')
    expected = protocol['model']['versions']
    q = subprocess.run([python, '-B', '-I', '-c', code, json.dumps(sorted(expected))],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=root)
    assert q.returncode == 0, q.stderr.decode()
    observed = json.loads(q.stdout); assert observed == expected, (observed, expected)
    v = {'schema_version': 1, 'epoch': 21, 'at': datetime.now(timezone.utc).isoformat(),
         'status': 'ACTUAL_FULL_SOURCE_ASSET_AND_PROTOCOL_VERSION_ADMISSION_PASS',
         'checks_passed': True, 'plan_sha256': sha(path), 'actual_launcher': p['candidate_launcher_path'],
         'actual_plan_asset_check': actual, 'declared_protocol_versions': expected,
         'actual_metadata_only_versions': observed, 'model_native_imports': 0,
         'fresh_legal_inputs_or_annotation_choices_parsed': 0, 'runtime_admission_to_execute': False,
         'instruction': 'Publication plus exact independent remote readback and fresh scoped-lock proof are still required before a single owned phase.'}
    with out.open('x') as f:
        json.dump(v, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'status': v['status'], 'checks_passed': True, 'pins': actual['pins'],
                      'actual_protocol_versions': observed, 'model_native_calls': 0}))


if __name__ == '__main__': main()
