"""Saved-output audit with independent compact native-vector receipt replay.

No model/tokenizer/native execution and no source annotation choices are read.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch27_frozen_raw_structure_v1',
                                            HERE/'audit_raw_structure.py')
BASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)
SCHEMA = 'epoch27-native-compact-f32le-v2'
PREFIX = 'Represent this sentence for searching relevant passages: '
ABSENT = '{"present":false}'
ABSENT_SHA = hashlib.sha256(ABSENT.encode('utf-8')).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def decode_block(block, expected_rows=None):
    require(type(block) is dict and set(block) ==
            {'encoding', 'dtype', 'shape', 'bytes', 'sha256', 'data_base64'},
            'Exact once-only float32le block fields required')
    shape = block['shape']
    require(block['encoding'] == 'base64' and block['dtype'] == 'float32le'
            and type(shape) is list and len(shape) == 2
            and type(shape[0]) is int and 0 < shape[0] <= 192
            and type(shape[1]) is int and shape[1] == 384
            and (expected_rows is None or shape[0] == expected_rows), 'Invalid vector block shape')
    encoded = block['data_base64']
    require(type(encoded) is str and encoded.isascii(), 'ASCII canonical base64 required')
    raw = base64.b64decode(encoded, validate=True)
    require(base64.b64encode(raw).decode('ascii') == encoded, 'Noncanonical base64 vector block')
    require(type(block['bytes']) is int and len(raw) == block['bytes'] == shape[0]*1536
            and sha(raw) == block['sha256'], 'Vector block byte length/SHA mismatch')
    digests = []
    for index in range(shape[0]):
        row = raw[index*1536:(index+1)*1536]
        vector = struct.unpack('<384f', row)
        require(all(math.isfinite(x) for x in vector), 'Nonfinite source float32 vector')
        require(abs(math.sqrt(math.fsum(x*x for x in vector))-1) <= 1e-5,
                'Source vector not normalized real BGE output')
        digests.append(sha(row))
    return digests


def bound_file(root, relative, expected_sha):
    require(type(relative) is str and not Path(relative).is_absolute(), 'Relative evidence path required')
    path = root / relative
    require(path == path.resolve() and path.is_relative_to(root), 'Evidence outside exact project')
    raw = path.read_bytes()
    require(sha(raw) == expected_sha, 'Saved compact evidence SHA mismatch: ' + relative)
    return json.loads(raw), {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def compact_audit(raw, inputs, project):
    root = Path(project).resolve()
    evidence = raw['native_evidence']
    require(evidence['schema'] == SCHEMA
            and evidence['vector_numeric_storage'] == 'native-bundle.json only', 'Wrong compact evidence schema')
    bundle, bundle_identity = bound_file(root, evidence['bundle_path'], evidence['bundle_sha256'])
    result, result_identity = bound_file(root, evidence['result_path'], evidence['result_sha256'])
    require(bundle['schema_version'] == 3
            and bundle['vector_encoding'] == 'base64_float32le_c_order'
            and bundle['metadata_policy'] == 'insert id and vector only; metadata absent',
            'Wrong once-only numeric bundle schema')
    require(result['epoch'] == 27 and result['native'] is True
            and result['compact_schema'] == SCHEMA
            and result['bundle_sha256'] == bundle_identity['sha256']
            and evidence['receipt_spec'] == result['compact_receipt_spec'], 'Native/bundle schema binding failed')
    require(result['native_binary_sha256'] == 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
            and result['package_version'] == '0.1.33'
            and result['platform_package_version'] == '0.1.31'
            and result['binary_version'] == '2.3.0', 'Exact real native identity failed')
    expected_docs = [str(d) for d in BASE.IDS]
    require([d['document_id'] for d in bundle['documents']] == expected_docs
            and [d['document_id'] for d in result['documents']] == expected_docs,
            'Fixed ordered eight native documents failed')
    rows = {r['id']: r for r in raw['cases']}
    bank = {r['id']: r for r in inputs['records']}
    hit_count, index_vectors, query_vectors = 0, 0, 0
    for document, observed in zip(bundle['documents'], result['documents']):
        did = int(document['document_id'])
        expected_queries = [f'original-contractnli:train:epoch27:dev:{did}:{h}' for h in BASE.HYPOTHESES]
        require([q['id'] for q in document['queries']] == expected_queries
                and [q['case_id'] for q in observed['queries']] == expected_queries,
                'Fixed ordered native queries failed')
        digests = decode_block(document['vectors'])
        vector_count = len(digests)
        require(observed['initialized_vectors'] == vector_count,
                'Exact native index vector count failed')
        index_vectors += vector_count
        require(all(set(query) == {'id'} for query in document['queries']),
                'Query vector was repeated outside once-only query block')
        query_vectors += len(decode_block(document['query_vectors'], expected_rows=3))
        for query in observed['queries']:
            row, inp = rows[query['case_id']], bank[query['case_id']]
            preparation = row['document_preparation']
            require(len(preparation['units']) == vector_count
                    and preparation['chunks'] == [inp['document'][u['start']:u['end']]
                                                 for u in preparation['units']],
                    'Bundle/source literal unit alignment failed')
            require(preparation['embedding']['source_sha256s']
                    == [sha(c.encode('utf-8')) for c in preparation['chunks']],
                    'BGE indexed literal source hashes failed')
            require(preparation['embedding']['exact_query_texts']
                    == [PREFIX + bank[q]['hypothesis'] for q in expected_queries],
                    'BGE exact query-prefix/input binding failed')
            require(row['native'] == dict(query, document_id=observed['document_id'],
                    initialization_ms=observed['initialization_ms'],
                    initialized_vectors=observed['initialized_vectors']),
                    'Per-case compact native result changed or reordered')
            k = min(40, vector_count)
            hits = query['raw_hits']
            require(query['requested_k'] == len(hits) == len(query['ids']) == k
                    and len(set(query['ids'])) == k
                    and query['ids'] == [int(h['id']) for h in hits]
                    and query['native_order_used_without_replacement'] is True,
                    'Actual complete ordered native hit list failed')
            for hit in hits:
                identifier = hit['id']
                require(type(identifier) is str and identifier.isascii() and identifier.isdecimal()
                        and str(int(identifier)) == identifier and 0 <= int(identifier) < vector_count,
                        'Noncanonical native hit ID')
                index = int(identifier)
                keys = hit['raw_keys']
                require(type(keys) is list and len(set(keys)) == len(keys)
                        and {'id', 'score', 'vector'} <= set(keys) and 'metadata' not in keys
                        and set(hit) == (set(keys)-{'vector'})
                            | {'raw_keys', 'vector_receipt', 'metadata_receipt'}
                        and 'vector' not in hit and 'metadata' not in hit,
                        'Original native field presence was lost or numeric vector repeated')
                require(finite(hit['score'])
                        and ('distance' not in hit or finite(hit['distance'])),
                        'Nonfinite original native score/distance')
                require(hit['vector_receipt'] == {'source_vector_index': index, 'dimensions': 384,
                    'dtype': 'float32le', 'sha256': digests[index], 'source_sha256': digests[index],
                    'source_equal_before_stripping': True}, 'Native/source float32le vector digest failed')
                require(hit['metadata_receipt'] == {'present': False, 'canonical_json': ABSENT,
                    'sha256': ABSENT_SHA, 'source_equal_before_stripping': True},
                    'Absent native/source metadata receipt failed')
                hit_count += 1
    require(query_vectors == 24, 'Complete24native query vectors required')
    for key, expected in {'native_index_initializations_attempted': 8,
            'native_index_initializations_completed': 8, 'native_queries_attempted': 24,
            'native_queries_completed': 24, 'Node_network_operations_attempted': 0}.items():
        require(result[key] == raw['counters'][key] == expected, 'Native counter mismatch: ' + key)
    require(result['network_violations'] == [], 'Native network violation persisted')
    return {'status': 'PASS', 'schema': SCHEMA, 'source_index_vectors_hashed': index_vectors,
        'source_query_vectors_hashed': query_vectors, 'observed_native_hits_verified': hit_count,
        'source_metadata_absence_hash': ABSENT_SHA,
        'bundle': bundle_identity, 'result': result_identity,
        'scope': 'Independent saved-bundle float32 little-endian digest and source/metadata/ID/order replay. Native vectors were hashed before stripping by reviewed helper code; no model/native rerun or cosine reranking.'}


def audit(raw_path, inputs_path, execution_path, project):
    report = BASE.audit(raw_path, inputs_path, execution_path)
    raw, inputs = BASE.read(raw_path), BASE.read(inputs_path)
    try:
        report['compact_native_evidence'] = compact_audit(raw, inputs, project)
    except (KeyError, ValueError, TypeError, OverflowError, struct.error) as error:
        report['failures'].append('compact_native_evidence:' + str(error))
        report['compact_native_evidence'] = {'status': 'FAIL', 'error_type': type(error).__name__,
                                             'message': str(error)}
    report['checks'] += 1
    report['status'] = 'PASS' if not report['failures'] else 'FAIL'
    report['auditor_version'] = 2
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ['raw', 'inputs', 'execution', 'project', 'output']:
        ap.add_argument('--' + name, required=True)
    args = ap.parse_args()
    report = audit(args.raw, args.inputs, args.execution, args.project)
    with Path(args.output).open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'checks': report['checks'],
                      'failures': report['failures']}))
