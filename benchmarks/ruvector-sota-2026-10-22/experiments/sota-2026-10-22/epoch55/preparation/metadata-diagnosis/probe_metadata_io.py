"""Root-authorized, stdlib-only pre-science I/O diagnosis. No automatic retry.

Executes exactly the six frozen version lookups. Matching suffix opens remain
denied before OS I/O. A separate later source/plan must select any remedy.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'source'))
from io_guard import DeniedOpenAudit, path_fingerprint
from inherited_guards import NetworkAudit

VERSIONS = {'numpy': '2.2.6', 'onnxruntime': '1.22.1', 'safetensors': '0.5.3',
            'tokenizers': '0.21.4', 'torch': '2.7.1+cpu', 'transformers': '4.52.4'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    a = p.parse_args()
    if sorted(os.sched_getaffinity(0)) != [0, 1]:
        raise ValueError('CPU_AFFINITY_0_1')
    out = Path(a.out)
    if not out.is_absolute() or out.exists() or out.is_symlink():
        raise ValueError('NEW_ABSOLUTE_OUTPUT')
    started = time.monotonic()
    counters = Counter()
    network = NetworkAudit(counters)
    sys.addaudithook(network)
    network.install_socket_guards()
    guard = DeniedOpenAudit(counters, maximum_events=32)
    sys.addaudithook(guard)
    paths = [{'sys_path_index': i, **path_fingerprint(x)} for i, x in enumerate(sys.path) if x]
    rows = []
    for package, version in VERSIONS.items():
        if time.monotonic() - started > 10:
            raise ValueError('METADATA_DIAGNOSIS_TEN_SECOND_BOUND')
        guard.set_stage('metadata.version:' + package)
        try:
            actual = importlib.metadata.version(package)
            rows.append({'package': package, 'expected_version': version,
                         'observed_version': actual, 'matches': actual == version})
        except BaseException as exc:
            rows.append({'package': package, 'expected_version': version,
                         'observed_version': None, 'matches': False,
                         'exception_type': type(exc).__name__})
    value = {'schema_version': 1, 'epoch': 55,
             'kind': 'STDLIB_METADATA_DENIED_OPEN_DIAGNOSIS_ONLY',
             'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'guard_source_sha256': hashlib.sha256((HERE/'source/io_guard.py').read_bytes()).hexdigest(),
             'versions': rows, 'sys_path_fingerprints': paths, 'denied_open_audit': guard.receipt(),
             'interpreter_base_prefix_sha256': hashlib.sha256(os.fsencode(sys.base_prefix)).hexdigest(),
             'interpreter_executable_sha256': hashlib.sha256(os.fsencode(sys.executable)).hexdigest(),
             'network_audit': network.receipt(),
             'CPU_affinity': sorted(os.sched_getaffinity(0)),
             'wall_seconds': time.monotonic()-started,
             'max_RSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'actual_tokenizer_model_BGE_native_calls': 0, 'native_corpus_batches': 0,
             'Gold_train_calibration_paid_GPU_calls': 0,
             'scope': 'New E55 metadata-only reproduction. This cannot prove E54 event targets retroactively.',
             'imported_runtime_modules': sorted(set(sys.modules) & {'numpy','torch','onnxruntime','tokenizers','transformers','safetensors'})}
    if value['imported_runtime_modules']:
        raise ValueError('NO_SCIENTIFIC_RUNTIME_IMPORTS_IN_PROBE')
    b = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    fd = os.open(out, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd,b) != len(b):
            raise ValueError('COMPLETE_PROBE_RESULT')
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps({'path': str(out), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}))


if __name__ == '__main__':
    main()
