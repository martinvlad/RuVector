"""One source-only original checkpoint metadata inspection; no neural imports."""
import argparse
from pathlib import Path
import json
import common as C
import checkpoint as K


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--assets-lock', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True); args = ap.parse_args()
    lock = C.read(args.assets_lock)
    if lock['repository'] != C.MODEL or lock['revision'] != C.REVISION or len(lock['assets']) != 9:
        raise ValueError('Exact selected nine-asset source lock required')
    row = next(r for r in lock['assets'] if r['remote_path'] == 'model.safetensors')
    path = C.checked(row['path'])
    if row['sha256'] != K.ASSET_SHA or row['bytes'] != K.ASSET_BYTES:
        raise ValueError('Selected original checkpoint identity changed')
    if args.out.absolute() != C.HERE / 'source-safetensors-header.json':
        raise ValueError('Exact held candidate metadata-report path required')
    report = K.inspect(path)
    C.write_new(args.out, report)
    print(json.dumps({'status': 'ORIGINAL_SAFETENSORS_STATIC_HEADER_AND_POSITION_BUFFER_PASS',
        'source_tensor_count': report['source_tensor_count'],
        'source_parameter_tensor_count': report['source_parameter_tensor_count'],
        'source_dtype_element_counts': report['source_dtype_element_counts'],
        'report_sha256': C.sha(args.out), 'model_native_tokenizer_imports': 0}))


if __name__ == '__main__': main()

