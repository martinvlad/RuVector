"""One bounded acquisition of nine exact public assets; no inference or retries."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
import urllib.request

LOCK_SHA = 'fafdae110e1f0dfb97bc51e61af3d012d64be3f18236ae1addab7c56a19b5400'
REPO = 'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REV = 'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
PREFIX = 'experiments/sota-2026-10-22/'
ASSET = PREFIX + 'candidate/epoch21/assets/official-deberta-v3-large-nli/'
FILES = {'.gitattributes', 'README.md', 'config.json', 'added_tokens.json',
         'special_tokens_map.json', 'tokenizer_config.json', 'tokenizer.json',
         'spm.model', 'model.safetensors'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def safe(path):
    p = path.absolute()
    assert p == p.resolve() and not any(x.is_symlink() for x in [p, *p.parents])
    return p


def write(path, value):
    safe(path)
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())


def main():
    os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    ap = argparse.ArgumentParser()
    for n in ('project', 'metadata-cache'): ap.add_argument('--' + n, type=Path, required=True)
    a = ap.parse_args(); root = safe(a.project); cache = safe(a.metadata_cache)
    lock = root / (PREFIX + 'legal-transfer/epoch21/model-assets.lock.json')
    assert digest(lock) == LOCK_SHA
    value = json.loads(lock.read_text()); rows = value['assets']
    assert value['repository'] == REPO and value['revision'] == REV and len(rows) == 9
    assert {r['remote_path'] for r in rows} == FILES
    for r in rows:
        assert r['path'] == ASSET + r['remote_path'] and r['revision'] == REV
        assert r['source_url'] == 'https://huggingface.co/' + REPO + '/resolve/' + REV + '/' + r['remote_path']
        dst = safe(root / r['path'])
        assert not dst.exists() and not dst.with_name(dst.name + '.partial').exists()
        if r['upstream_lfs_sha256'] is None:
            src = safe(cache / r['remote_path']); b = src.read_bytes()
            assert len(b) == r['bytes'] and hashlib.sha256(b).hexdigest() == r['sha256']
            assert hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest() == r['upstream_git_blob_sha1']
        else:
            assert r['remote_path'] in ('spm.model', 'model.safetensors')
            assert r['upstream_lfs_sha256'] == r['sha256']
    assert shutil.disk_usage(root).free > sum(r['bytes'] for r in rows) + 134217728
    prep = root / (PREFIX + 'epoch21/preparation')
    out = prep / 'selected-model-acquisition-v1.json'; assert not out.exists()
    write(prep / 'selected-model-acquisition-attempt-v1.json', {
        'schema_version': 1, 'epoch': 21, 'state': 'RECORDED_BEFORE_METADATA_COPY_OR_HTTP',
        'model_lock_sha256': LOCK_SHA, 'planned_TLS_GETs': 2, 'automatic_retry': False,
        'seconds_cap': 300, 'model_native_paid_GPU_calls': 0})
    started = time.monotonic(); completed = []; attempted = 0; succeeded = 0; error = None
    def timeout(*unused): raise TimeoutError('Bounded public acquisition elapsed')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(300)
    try:
        for r in rows:
            if r['upstream_lfs_sha256'] is not None: continue
            dst = root / r['path']; dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open('xb') as f: f.write((cache / r['remote_path']).read_bytes()); f.flush(); os.fsync(f.fileno())
            assert digest(dst) == r['sha256'] and dst.stat().st_size == r['bytes']
            completed.append({'path': r['path'], 'bytes': r['bytes'], 'sha256': r['sha256'], 'mode': 'EXACT_PUBLIC_METADATA_CACHE_REHASHED'})
        write(prep / 'selected-metadata-ready-v1.json', {
            'schema_version': 1, 'epoch': 21, 'metadata_files': completed,
            'model_lock_sha256': LOCK_SHA, 'model_native_calls': 0,
            'source': 'Original immutable public metadata. The two LFS files are not claimed acquired by this receipt.'})
        for r in rows:
            if r['upstream_lfs_sha256'] is None: continue
            dst = root / r['path']; part = dst.with_name(dst.name + '.partial')
            attempted += 1; h = hashlib.sha256(); count = 0
            with urllib.request.urlopen(r['source_url'], timeout=45) as response, part.open('xb') as f:
                assert response.status == 200
                for b in iter(lambda: response.read(1048576), b''):
                    count += len(b); assert count <= r['bytes']; h.update(b); f.write(b)
                f.flush(); os.fsync(f.fileno())
            assert count == r['bytes'] and h.hexdigest() == r['sha256']
            part.rename(dst); succeeded += 1
            completed.append({'path': r['path'], 'bytes': count, 'sha256': h.hexdigest(), 'mode': 'ONE_OFFICIAL_TLS_GET_VERIFIED', 'source_url': r['source_url']})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'scope': 'Preserved partial public asset acquisition; no automatic retry. Redirect URLs, headers and exception details are excluded.'}
    finally: signal.alarm(0)
    report = {'schema_version': 1, 'epoch': 21, 'at': datetime.now(timezone.utc).isoformat(),
              'status': 'EXACT_NINE_PUBLIC_ASSETS_ACQUIRED_NO_INFERENCE' if error is None else 'ACQUISITION_FAILED_PRESERVED',
              'repository': REPO, 'revision': REV, 'source_lock_sha256': LOCK_SHA,
              'assets': completed, 'TLS_GET_attempts': attempted, 'TLS_GET_completed': succeeded,
              'elapsed_seconds': time.monotonic() - started, 'error': error, 'automatic_retry': False,
              'model_native_fit_paid_GPU_calls': 0, 'models_imported': [], 'weights_republished': False}
    write(out, report)
    print(json.dumps({'status': report['status'], 'files': len(completed),
                      'TLS_GET_attempts': attempted, 'TLS_GET_completed': succeeded,
                      'elapsed_seconds': report['elapsed_seconds'], 'receipt_sha256': digest(out)}))
    if error is not None: raise SystemExit(1)


if __name__ == '__main__': main()

