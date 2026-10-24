"""Seal source readiness after completed metadata-only asset acquisition.

No model deserialization, ML/tokenizer/native imports, DEV bank reads or worker.
The public MODEL_ASSETS is a byte-identical copy of the actual model asset lock.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--static-receipt', required=True, type=Path)
    parser.add_argument('--model-directory', default='models/bart-large-mnli-d7645e')
    args = parser.parse_args()
    project = args.project.absolute()
    base = project / 'experiments/sota-2026-10-22'
    candidate, preparation = base / 'candidate/epoch27', base / 'epoch27/preparation'
    model = project / args.model_directory
    assert project.resolve() == project and model.resolve() == model and model.is_relative_to(project / 'models')
    lock_path = model / 'asset-lock.json'
    lock = json.loads(lock_path.read_text())
    assert lock['repository'] == 'facebook/bart-large-mnli'
    assert lock['revision'] == 'd7645e127eaf1aefc7862fd59a17a5aa8558b8ce'
    assert lock['original_bin_only'] is True and len(lock['files']) == 8
    assert lock['model_initializations'] == lock['tokenizer_initializations'] == 0
    assert lock['reader_contract']['raw_labels'] == ['C', 'N', 'E']
    assert lock['reader_contract']['canonical_permutation'] == [2, 0, 1]
    public = candidate / 'MODEL_ASSETS.json'
    if public.exists():
        assert public.read_bytes() == lock_path.read_bytes()
    else:
        with public.open('xb') as target:
            target.write(lock_path.read_bytes())
            target.flush()
            os.fsync(target.fileno())
    assert public.read_bytes() == lock_path.read_bytes()
    runtime = json.loads((preparation / 'runtime-restoration.json').read_text())
    static = json.loads(args.static_receipt.read_text())
    assert static['status'] == 'STATIC_AND_SYNTHETIC_GUARDS_PASS'
    assert static['ML_model_tokenizer_native_initializations'] == static['DEV_source_or_annotation_reads'] == static['benchmark_workers'] == 0
    for row in static['validated_sources']:
        path = project / row['path']
        assert path.resolve() == path and path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    assert runtime['verified_wheel_members'] == 17498 and runtime['official_CPU_wheels'] == 31

    def identity(path):
        assert path.resolve() == path and path.is_file()
        return {'path': str(path.relative_to(project)), 'bytes': path.stat().st_size, 'sha256': digest(path)}

    owned = [candidate / name for name in ('common.py', 'worker.py', 'native.cjs',
        'evidence.py', 'network_guard.py', 'RAW_SCHEMA.json', 'MODEL_ASSETS.json')]
    helpers = sorted(preparation.glob('*.py'))
    reader = candidate / 'reader/bart_reader.py'
    assert reader.is_file()
    report = {'schema_version': 1, 'epoch': 27,
        'scope': 'SOURCE_READY_FOR_IMMUTABLE_REMOTE_PUBLICATION_NOT_EXECUTION',
        'diagnostic_only': True, 'source_checkpoint': '6e4ad4ab0b6a09a6a1083335ed0401637227d17f',
        'owned_candidate_sources': [identity(path) for path in owned],
        'owned_preparation_sources': [identity(path) for path in helpers],
        'reader_source': identity(reader), 'static_validation': identity(args.static_receipt),
        'runtime_restoration': identity(preparation / 'runtime-restoration.json'),
        'runtime_assets_lock': identity(preparation / 'runtime-assets.lock.json'),
        'wheel_members': identity(project / runtime['wheel_members_reference_path']),
        'runtime_versions_metadata_only': runtime['python_expected_versions'],
        'model_asset_public_copy': identity(public),
        'model_asset_public_copy_equals_actual_local_asset_lock': True,
        'reader_contract': lock['reader_contract'], 'license_provenance': lock['license_provenance'],
        'source_lineage_limits': lock['source_lineage_limits'],
        'limits': {'worker_attempts': 1, 'native_indexes': 8, 'native_queries': 24,
            'NLI_model_initializations': 1, 'NLI_forward_pairs': 72, 'maximum_pair_tokens': 512,
            'worker_seconds': 585, 'outer_seconds_including_cleanup': 600,
            'CPU_affinity': [0, 1], 'threads': 2, 'interop': 1, 'UV_THREADPOOL_SIZE': 1},
        'performed_model_tokenizer_native_initializations': 0,
        'performed_DEV_source_or_annotation_reads': 0, 'actual_benchmark_worker_starts': 0,
        'CONF_allowed': False, 'fit_or_calibration_allowed': False,
        'promotion_or_benchmark_acceptance_allowed': False,
        'prediction_policy': 'Full original MNLI native C/N/E head softmax T=1; canonical E/C/N permutation2,0,1; native-logit argmax tie order; no context heuristic override.',
        'raw_schema': identity(candidate / 'RAW_SCHEMA.json'),
        'remaining_gate': 'Root immutable remote source readback admission plus independent actual-source review before one reserved real DEV-only worker; root controls launch and sealed-output label join.'}
    for path, value in ((candidate / 'PREPARATION.json', report),
                        (preparation / 'SOURCE_READY.json', report)):
        with path.open('x') as target:
            json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
    print(json.dumps({'status': report['scope'], 'preparation': identity(candidate / 'PREPARATION.json'),
        'source_ready': identity(preparation / 'SOURCE_READY.json')}))


if __name__ == '__main__':
    main()
