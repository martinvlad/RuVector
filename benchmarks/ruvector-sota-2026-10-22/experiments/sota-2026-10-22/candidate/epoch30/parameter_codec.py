"""Deterministic lossless public learned-parameter JSON; no ML imports/pickle."""
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('e30_frozen_algorithm_for_codec', HERE / 'algorithm.py')
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def canonical_sha(value):
    return sha_bytes(canonical_bytes(value))


def _shape(shape):
    if not isinstance(shape, (list, tuple)) or not shape or any(type(x) is not int or not 1 <= x <= 50265 for x in shape):
        raise ValueError('Only exact bounded parameter shapes are allowed')
    count = math.prod(shape)
    if count > 50265 * 1024:
        raise ValueError('Parameter shape exceeds original BART tensor bound')
    return count


def manifest(name, shape, payload, *, check_finite=True):
    count = _shape(shape)
    if not isinstance(payload, bytes) or len(payload) != count * 4:
        raise ValueError('Exact float32le parameter byte length required')
    if check_finite and not all(math.isfinite(value[0]) for value in struct.iter_unpack('<f', payload)):
        raise ValueError('Nonfinite learned parameter')
    return {'name': name, 'shape': list(shape), 'dtype': 'float32le', 'numel': count,
        'bytes': len(payload), 'sha256': sha_bytes(payload)}


def encode_tensor(name, shape, payload):
    record = manifest(name, shape, payload)
    record['data_base64'] = base64.b64encode(payload).decode('ascii')
    return record


def decode_tensor(record, expected_name, expected_shape):
    if (not isinstance(record, dict) or set(record) != {'name', 'shape', 'dtype', 'numel', 'bytes', 'sha256', 'data_base64'}
            or record.get('name') != expected_name or record.get('shape') != list(expected_shape)
            or record.get('dtype') != 'float32le' or type(record.get('numel')) is not int
            or record['numel'] != math.prod(expected_shape) or type(record.get('bytes')) is not int
            or record['bytes'] != record['numel'] * 4
            or not isinstance(record.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
        raise ValueError('Unexpected learned tensor name/shape/type/count')
    payload = base64.b64decode(record['data_base64'], validate=True)
    if base64.b64encode(payload).decode('ascii') != record['data_base64']:
        raise ValueError('Noncanonical parameter base64')
    checked = manifest(expected_name, expected_shape, payload)
    if any(record[key] != value for key, value in checked.items()):
        raise ValueError('Learned tensor bytes/hash mismatch')
    return payload


def validate_artifact(value):
    required = {'schema_version', 'epoch', 'kind', 'codec', 'base_model', 'algorithm',
        'source_plan_sha256', 'training_inputs_sha256', 'training_steps', 'trainable_parameter_count',
        'tensors', 'original_head_manifest', 'initial_trainable_manifest', 'trainable_changes',
        'frozen_pretrained_proof', 'effective_lora_delta'}
    if (not isinstance(value, dict) or set(value) != required or value.get('schema_version') != 1
            or value.get('epoch') != 30 or value.get('kind') != A.KIND or value.get('codec') != A.CODEC
            or value.get('base_model') != A.BASE_MODEL or value.get('algorithm') != A.ALGORITHM
            or value.get('training_steps') != 24 or value.get('trainable_parameter_count') != A.TRAINABLE_COUNT):
        raise ValueError('Wrong fixed public learned-parameter artifact header')
    for key in ('source_plan_sha256', 'training_inputs_sha256'):
        if not isinstance(value.get(key), str) or not re.fullmatch('[0-9a-f]{64}', value[key]):
            raise ValueError('Missing exact source/training input identity')
    tensors = value['tensors']
    if not isinstance(tensors, list) or len(tensors) != 12:
        raise ValueError('Exactly12 ordered learned tensors required')
    decoded = [decode_tensor(record, name, shape) for record, (name, shape) in zip(tensors, A.EXPECTED_TENSORS)]
    if sum(map(len, decoded)) != A.PARAMETER_BYTES or sum(record['numel'] for record in tensors) != A.TRAINABLE_COUNT:
        raise ValueError('Exact1085443 float32 learned scalar closure failed')
    heads = value['original_head_manifest']
    if not isinstance(heads, list) or len(heads) != 4:
        raise ValueError('Exact original trained-head identity required')
    for record, name, shape in zip(heads, A.HEAD_NAMES, A.HEAD_SHAPES):
        if (set(record) != {'name', 'shape', 'dtype', 'numel', 'bytes', 'sha256'} or record['name'] != name
                or record['shape'] != list(shape) or record['dtype'] != 'float32le'
                or record['numel'] != math.prod(shape) or record['bytes'] != math.prod(shape) * 4
                or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise ValueError('Original pretrained head manifest changed')
    proof = value['frozen_pretrained_proof']
    if (proof.get('parameter_count') != A.FROZEN_COUNT or proof.get('all_bit_unchanged') is not True
            or proof.get('tensor_count') != len(proof.get('before_after', []))
            or proof.get('aggregate_before_sha256') != proof.get('aggregate_after_sha256')):
        raise ValueError('Complete unchanged frozen-parameter proof required')
    if sum(record['numel'] for record in proof['before_after']) != A.FROZEN_COUNT:
        raise ValueError('Frozen parameter scalar count differs')
    frozen_names = set()
    for record in proof['before_after']:
        if (record['name'] in frozen_names or record['name'] in A.HEAD_NAMES
                or record['dtype'] != 'float32le' or record['numel'] != math.prod(record['shape'])
                or record['bytes'] != record['numel'] * 4
                or record['sha256_before'] != record['sha256_after']
                or not re.fullmatch('[0-9a-f]{64}', record['sha256_before'])):
            raise ValueError('Frozen tensor changed or is duplicated')
        frozen_names.add(record['name'])
    if [record['name'] for record in proof['before_after']] != sorted(frozen_names):
        raise ValueError('Frozen parameter proof order must be canonical by name')
    before = [{**{key: record[key] for key in ('name', 'shape', 'dtype', 'numel', 'bytes')},
        'sha256': record['sha256_before']} for record in proof['before_after']]
    after = [{**{key: record[key] for key in ('name', 'shape', 'dtype', 'numel', 'bytes')},
        'sha256': record['sha256_after']} for record in proof['before_after']]
    if canonical_sha(before) != proof['aggregate_before_sha256'] or canonical_sha(after) != proof['aggregate_after_sha256']:
        raise ValueError('Frozen parameter proof aggregate hash mismatch')
    initial = value['initial_trainable_manifest']
    if not isinstance(initial, list) or len(initial) != 12:
        raise ValueError('Exact initial factor/head identities required')
    for record, (name, shape) in zip(initial, A.EXPECTED_TENSORS):
        if (record.get('name') != name or record.get('shape') != list(shape)
                or record.get('dtype') != 'float32le' or record.get('numel') != math.prod(shape)
                or record.get('bytes') != math.prod(shape) * 4
                or not re.fullmatch('[0-9a-f]{64}', record.get('sha256', ''))):
            raise ValueError('Initial factor/head manifest mismatch')
        if name.endswith('.lora_B') and record['sha256'] != sha_bytes(bytes(math.prod(shape) * 4)):
            raise ValueError('Initial effective LoRA delta was not exactly zero')
        if name in A.HEAD_NAMES and record['sha256'] != heads[A.HEAD_NAMES.index(name)]['sha256']:
            raise ValueError('Existing pretrained classifier was reinitialized')
    changes = value['trainable_changes']
    if len(changes) != 12 or [record['name'] for record in changes] != [name for name, _shape in A.EXPECTED_TENSORS]:
        raise ValueError('Exact trainable change receipts required')
    for record, tensor, init in zip(changes, tensors, initial):
        if (record.get('changed') is not True or record['before_sha256'] == record['after_sha256']
                or record['after_sha256'] != tensor['sha256'] or record['before_sha256'] != init['sha256']):
            raise ValueError('Every intended trainable tensor must have changed')
    deltas = value['effective_lora_delta']
    if len(deltas) != 4 or [record['module'] for record in deltas] != list(A.MODULES):
        raise ValueError('All four intended attention adaptations required')
    for record in deltas:
        if (record['shape'] != [1024, 1024] or record['scale'] != 2.0 or record['nonzero_entries'] <= 0
                or not math.isfinite(record['l2_norm']) or record['l2_norm'] <= 0
                or not math.isfinite(record['max_abs']) or record['max_abs'] <= 0
                or not isinstance(record.get('B_nonzero_gradient_steps'), list)
                or not record['B_nonzero_gradient_steps']
                or record['B_nonzero_gradient_steps'] != sorted(set(record['B_nonzero_gradient_steps']))
                or any(type(step) is not int or not 1 <= step <= 24 for step in record['B_nonzero_gradient_steps'])
                or not math.isfinite(record.get('max_B_gradient_l2', float('nan'))) or record['max_B_gradient_l2'] <= 0
                or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise ValueError('Effective trained attention delta is absent/nonfinite')
    if len(canonical_bytes(value)) > MAX_ARTIFACT_BYTES:
        raise ValueError('Public parameter artifact exceeds frozen8MiB cap')
    return decoded


def write_artifact(path, value):
    validate_artifact(value)
    payload = canonical_bytes(value)
    with Path(path).open('xb') as target:
        target.write(payload)
        target.flush()
        import os
        os.fsync(target.fileno())
    return {'path': str(path), 'bytes': len(payload), 'sha256': sha_bytes(payload)}
