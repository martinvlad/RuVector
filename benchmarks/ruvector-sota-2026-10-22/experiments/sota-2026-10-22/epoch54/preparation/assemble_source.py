"""Root-only exact public-artifact adoption; no model, data or Git entrypoint."""
import hashlib
import json
import os
from pathlib import Path

W = Path(__file__).resolve().parent
R = W / 'project'
PREFIXES = tuple('experiments/sota-2026-10-22/' + x for x in
                 ('epoch54/', 'audit/epoch54/', 'runtime/epoch54/'))

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def write(path, raw):
    assert not path.exists() and not path.is_symlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())

def adopt(config):
    adopted = []
    for row in config['files']:
        source = Path(row['source']['path'])
        target = row['target']
        assert target.startswith(PREFIXES) and '..' not in Path(target).parts
        assert source.is_absolute() and source.is_file() and not source.is_symlink()
        raw = source.read_bytes()
        assert len(raw) == row['source']['bytes'] and digest(raw) == row['source']['sha256']
        raw.decode('utf-8')
        assert b'\0' not in raw
        write(R / target, raw)
        adopted.append({'path': target, 'bytes': len(raw), 'sha256': digest(raw)})
        if row.get('operational_helper'):
            assert target.startswith(PREFIXES[0] + 'publication/')
            write(W / 'publication-helpers' / Path(target).name, raw)
    return adopted

if __name__ == '__main__':
    import sys
    config = json.loads(Path(sys.argv[1]).read_text())
    result = {'epoch': 54, 'adopted': adopt(config), 'model_native_Git_calls': 0}
    write(W / config['receipt'], (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(json.dumps({'adopted_files': len(result['adopted']), 'model_native_Git_calls': 0}))
