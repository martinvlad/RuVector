"""Create the epoch27 pre-input data source seal; hash public source, never parse it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'


def identity(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve() or path.is_symlink():
        raise ValueError('Exact absolute materialized source path required')
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--restoration-proof', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--additional-file', action='append', default=[])
    args = ap.parse_args()
    proof_identity = identity(args.restoration_proof)
    proof = json.loads(Path(args.restoration_proof).read_bytes())
    if not (proof.get('verified') is True
            and proof.get('source_head') == '6e4ad4ab0b6a09a6a1083335ed0401637227d17f'
            and proof.get('actual_Git_leaves') == 3734 and proof.get('CP_rows') == 3660
            and proof.get('CP_sha256') == '5f235008f408f70d0570478c059f41c2a603e04c77b5400c17aabd55f3b41822'
            and proof.get('all_bytes_SHA256_verified') is True):
        raise ValueError('Exact fresh restoration receipt required')
    source = identity(args.source)
    if source['bytes'] != 7608211 or source['sha256'] != SOURCE_SHA:
        raise ValueError('Original licensed source blob mismatch')
    fixed = ['selection.json', 'exposure-metadata.json', 'build_inputs.py', 'score_dev.py',
             'protocol.json', 'acceptance-principles.json', 'audit_input_identity.py',
             'audit_raw_structure.py']
    paths = [HERE / name for name in fixed] + [Path(p) for p in args.additional_file]
    if len({str(p.resolve()) for p in paths}) != len(paths):
        raise ValueError('Duplicate frozen file')
    seal = {'schema_version': 1, 'epoch': 27,
        'status': 'INDEPENDENT_DATA_SOURCE_PROTOCOL_BEFORE_INPUTS_OR_LABELS',
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'files': [identity(p) for p in paths],
        'source': source, 'root_restoration_proof': proof_identity,
        'selected_source_text_or_annotation_choices_seen_before_freeze': 0,
        'source_JSON_parsed_by_freezer': False, 'model_tokenizer_native_calls': 0,
        'not_candidate_runtime_admission': True, 'confirmation': []}
    with Path(args.output).open('x') as stream:
        json.dump(seal, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(identity(args.output), sort_keys=True))
