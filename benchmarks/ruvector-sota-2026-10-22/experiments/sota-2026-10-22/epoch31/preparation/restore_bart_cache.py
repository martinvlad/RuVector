"""Verify and hardlink the exact original public BART bytes; no tensor imports."""
from pathlib import Path
import hashlib, json, os, stat, time

ROOT = Path(__file__).resolve().parents[4]
STUDY = ROOT / 'experiments/sota-2026-10-22/epoch31'
PUBLIC = 'experiments/sota-2026-10-22/candidate/epoch27/MODEL_ASSETS.json'
LOCK_SHA = '29eaa17d71b1b2bf2929eb0d22c370307ae2b1d47a97aa6b385e8abc363661b1'
DONOR = Path('/tmp/ruvector-sota-2026-10-22/epoch27-0471ff09d550/project/models/bart-large-mnli-d7645e')
DEST = ROOT / 'models/bart-large-mnli-d7645e'

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): digest.update(block)
    return digest.hexdigest()

def safe(path):
    assert not any(p.is_symlink() for p in (path, *path.parents))
    assert path.is_file() and stat.S_ISREG(path.stat().st_mode)

def put_new(path, value):
    with path.open('x') as target:
        json.dump(value, target, indent=2); target.write('\n'); target.flush(); os.fsync(target.fileno())

def main():
    started = time.monotonic(); public = ROOT / PUBLIC
    safe(public); assert sha(public) == LOCK_SHA
    lock = json.loads(public.read_text()); assert len(lock['files']) == 8
    assert lock['repository'] == 'facebook/bart-large-mnli' and lock['revision'] == 'd7645e127eaf1aefc7862fd59a17a5aa8558b8ce'
    expected = {r['path'] for r in lock['files']} | {'asset-lock.json'}
    assert {p.name for p in DONOR.iterdir()} == expected
    for row in lock['files']:
        p = DONOR / row['path']; safe(p)
        assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256']
    safe(DONOR / 'asset-lock.json')
    assert (DONOR / 'asset-lock.json').read_bytes() == public.read_bytes()
    DEST.mkdir(parents=True, exist_ok=False); rows = []
    for name in sorted(expected):
        source = DONOR / name; target = DEST / name
        os.link(source, target, follow_symlinks=False); safe(target)
        assert source.stat().st_size == target.stat().st_size and sha(source) == sha(target)
        rows.append({'path': target.relative_to(ROOT).as_posix(), 'bytes': target.stat().st_size, 'sha256': sha(target)})
    assets = STUDY / 'preparation/runtime-assets.lock.json'; value = json.loads(assets.read_text())
    value['python_expected_versions'] = {'numpy':'2.2.6','onnxruntime':'1.22.1','tokenizers':'0.21.4','torch':'2.7.1+cpu','transformers':'4.52.4','safetensors':'0.5.3'}
    value.update(wheel_members_reference_path='experiments/sota-2026-10-22/epoch26/preparation/runtime-members/python-wheel-members.json', wheel_members_reference_sha256='87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9', wheel_members_reference_count=17498)
    value.update(BART_assets=[r for r in rows if not r['path'].endswith('/asset-lock.json')], BART_asset_lock_path=(DEST/'asset-lock.json').relative_to(ROOT).as_posix(), BART_asset_lock_sha256=LOCK_SHA, BART_public_asset_lock_path=PUBLIC, BART_public_asset_lock_sha256=LOCK_SHA)
    with assets.open('w') as target:
        json.dump(value, target, indent=2); target.write('\n'); target.flush(); os.fsync(target.fileno())
    report = {'epoch':31, 'status':'EXACT_ORIGINAL_BART_CACHE_VERIFIED_AND_RELOCATED', 'files':rows, 'original_public_lock':{'path':PUBLIC,'bytes':public.stat().st_size,'sha256':LOCK_SHA}, 'model_tokenizer_native_tensor_imports':0, 'network_or_download_calls':0, 'copied_model_weight_bytes':0, 'source_and_destination_all_SHA256_verified':True, 'wall_seconds':time.monotonic()-started}
    put_new(STUDY/'preparation/bart-materialization.json', report)
    for directory in (DEST, STUDY/'preparation'):
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps({'status':report['status'],'verified_files':len(rows),'weight_copy_bytes':0,'model_initializations':0,'seconds':report['wall_seconds']}))

if __name__ == '__main__': main()
