"""Epoch31 pure-standard-library fixed data identity utilities."""
import hashlib
import json
import math
from pathlib import Path

TRAIN_IDS = []
DEV_IDS = [145, 597, 191, 620, 254, 160, 384, 571]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_BYTES = 7608211
ALLOCATION_SHA = '836667dbb19ef55e02a5b0d80be11fded83f00afc3da70546ec451849bb7f66d'
SOURCE_MAP = {'Contradiction': 0, 'NotMentioned': 1, 'Entailment': 2}
NATIVE_ORDER = ['contradiction', 'not_mentioned', 'entailment']
CLASSES = ['entailment', 'contradiction', 'not_mentioned']

def require(value, message):
    if not value:
        raise ValueError(message)

def digest(value):
    return hashlib.sha256(value).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def norm(value):
    return ' '.join(value.casefold().split())

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result

def read(path, expected_sha=None, expected_bytes=None):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Absolute materialized nonsymlink path required')
    raw = path.read_bytes()
    require(expected_sha is None or digest(raw) == expected_sha, 'SHA mismatch: ' + str(path))
    require(expected_bytes is None or len(raw) == expected_bytes, 'Bytes mismatch: ' + str(path))
    return json.loads(raw, object_pairs_hook=unique_object)

def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}

def write_new(path, value):
    import os
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

def expected(role):
    require(role in ['train', 'dev'], 'Unknown role')
    return [(f'original-contractnli:train:epoch31:{role}:{did}:{hid}', did, hid)
            for did in (TRAIN_IDS if role == 'train' else DEV_IDS) for hid in HYPOTHESES]

def finite(value):
    return type(value) in (float, int) and math.isfinite(value)
