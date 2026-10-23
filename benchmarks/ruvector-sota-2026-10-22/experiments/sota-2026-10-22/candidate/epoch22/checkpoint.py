"""Pure exact safetensors metadata and nonlearned position-buffer qualification."""
import hashlib
import json
import math
from pathlib import Path
import struct
import common as C

ASSET_SHA = 'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
ASSET_BYTES = 870182606
FLOAT_ELEMENTS = 435064835
POSITION_KEY = 'deberta.embeddings.position_ids'
HEAD_SHAPES = {'pooler.dense.weight': [1024, 1024], 'pooler.dense.bias': [1024],
               'classifier.weight': [3, 1024], 'classifier.bias': [3]}
BYTES_PER_ELEMENT = {'F16': 2, 'I64': 8}


def no_duplicates(pairs):
    answer = {}
    for key, value in pairs:
        if key in answer: raise ValueError('Duplicate safetensors header key')
        answer[key] = value
    return answer


def validate_header(header, payload_bytes):
    if not isinstance(header, dict) or type(payload_bytes) is not int or payload_bytes < 1:
        raise ValueError('Exact safetensors object/payload required')
    tensors = {k: v for k, v in header.items() if k != '__metadata__'}
    if not tensors: raise ValueError('Source tensor inventory is empty')
    dtype_counts, dtype_elements, intervals, floating = {}, {}, [], []
    for name, row in sorted(tensors.items()):
        if (not isinstance(name, str) or not name or not isinstance(row, dict)
                or set(row) != {'dtype', 'shape', 'data_offsets'}):
            raise ValueError('Exact safetensors tensor metadata required')
        dtype, shape, offsets = row['dtype'], row['shape'], row['data_offsets']
        if (dtype not in BYTES_PER_ELEMENT or not isinstance(shape, list) or not shape
                or any(type(n) is not int or n <= 0 for n in shape)
                or not isinstance(offsets, list) or len(offsets) != 2
                or any(type(n) is not int or n < 0 for n in offsets)):
            raise ValueError('Exact positive integer tensor shape and offsets required')
        elements = math.prod(shape)
        if offsets[1] - offsets[0] != elements * BYTES_PER_ELEMENT[dtype] or offsets[1] > payload_bytes:
            raise ValueError('Tensor byte interval disagrees with dtype/shape')
        if name == POSITION_KEY:
            if dtype != 'I64' or shape != [1, 512]: raise ValueError('Exact original I64 position buffer required')
        elif dtype != 'F16': raise ValueError('Every original learned parameter must be source FP16')
        else: floating.append(name)
        dtype_counts[dtype] = dtype_counts.get(dtype, 0) + 1
        dtype_elements[dtype] = dtype_elements.get(dtype, 0) + elements
        intervals.append((offsets[0], offsets[1], name))
    if POSITION_KEY not in tensors or dtype_counts.get('I64') != 1:
        raise ValueError('Only the exact single original nonlearned I64 position buffer is permitted')
    if dtype_elements != {'I64': 512, 'F16': FLOAT_ELEMENTS}:
        raise ValueError('Exact original FP16 learned-element and I64 buffer inventory required')
    cursor = 0
    for start, end, _ in sorted(intervals):
        if start != cursor: raise ValueError('Tensor intervals must cover the source payload without gaps or overlap')
        cursor = end
    if cursor != payload_bytes: raise ValueError('Trailing/unaccounted tensor payload bytes')
    for name, shape in HEAD_SHAPES.items():
        if tensors.get(name, {}).get('shape') != shape or tensors[name]['dtype'] != 'F16':
            raise ValueError('All original trained pooler/classifier head shapes required')
    return {'tensor_metadata': tensors, 'source_tensor_count': len(tensors),
            'source_parameter_tensor_count': len(floating), 'source_parameter_names': sorted(floating),
            'source_dtype_tensor_counts': dtype_counts, 'source_dtype_element_counts': dtype_elements,
            'source_floating_parameter_elements': FLOAT_ELEMENTS, 'source_integer_buffer_elements': 512,
            'trained_head_shapes': HEAD_SHAPES, 'safetensors_metadata': header.get('__metadata__')}


def inspect(path, verify_asset=True):
    path = Path(path)
    if path != path.resolve() or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('Canonical original checkpoint path required')
    size = path.stat().st_size
    if size != ASSET_BYTES: raise ValueError('Original safetensors byte count changed')
    if verify_asset and C.sha(path) != ASSET_SHA: raise ValueError('Original safetensors SHA256 changed')
    with path.open('rb') as f:
        length_raw = f.read(8)
        if len(length_raw) != 8: raise ValueError('Safetensors length prefix missing')
        length = struct.unpack('<Q', length_raw)[0]
        if not 2 <= length <= min(16 * 1024 * 1024, size - 8):
            raise ValueError('Bounded complete safetensors header required')
        raw = f.read(length)
        if len(raw) != length: raise ValueError('Incomplete safetensors header')
        header = json.loads(raw, object_pairs_hook=no_duplicates)
        result = validate_header(header, size - 8 - length)
        row = result['tensor_metadata'][POSITION_KEY]
        f.seek(8 + length + row['data_offsets'][0])
        position_raw = f.read(512 * 8)
    if len(position_raw) != 4096 or list(struct.unpack('<512q', position_raw)) != list(range(512)):
        raise ValueError('Original nonlearned position buffer must be exactly arange512')
    result.update(schema_version=1, epoch=22, repository=C.MODEL, revision=C.REVISION,
                  asset_path=str(path.relative_to(C.ROOT)), asset_bytes=size, asset_sha256=ASSET_SHA,
                  header_bytes=length, header_sha256=hashlib.sha256(raw).hexdigest(),
                  source_position_buffer={'name': POSITION_KEY, 'source_dtype': 'I64', 'source_shape': [1, 512],
                    'values_equal_arange512': True, 'source_bytes_sha256': hashlib.sha256(position_raw).hexdigest()},
                  model_native_tokenizer_imports=0,
                  scope='Static original safetensors tensor metadata and nonlearned integer bytes only; no model import, tensor decode, neural forward or benchmark-input/label read.',
                  source_storage_precision='Original floating checkpoint storage is FP16; intended inference is explicit FP32, no quantization.')
    return result


def compare_frozen_header(actual, frozen):
    if actual != frozen: raise ValueError('Original safetensors metadata differs from frozen complete header proof')
    return True


def validate_loading_info(value):
    if (not isinstance(value, dict) or any(value.get(k) != [] for k in
            ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'))):
        raise ValueError('Zero missing/unexpected/mismatched/error loading keys required')
    return {'all_loading_error_lists_empty': True, 'trained_key_exclusions': [],
            'head_reinitialization_allowed': False, 'checkpoint_bytes_modified': False}


def validate_parameter_rows(rows, source):
    expected = source['source_parameter_names']
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows)
            or [r.get('name') for r in rows] != expected):
        raise ValueError('Every original learned tensor must be compared once in exact sorted order')
    count = 0
    for row in rows:
        info = source['tensor_metadata'][row['name']]
        elements = math.prod(info['shape'])
        if row != {'name': row['name'], 'source_dtype': 'F16', 'source_shape': info['shape'],
                   'elements': elements, 'loaded_dtype': 'torch.float32', 'loaded_device': 'cpu',
                   'equal_after_FP32_conversion': True}:
            raise ValueError('Exact original FP16 to FP32 value equality required for every learned tensor')
        count += elements
    if count != FLOAT_ELEMENTS: raise ValueError('Incomplete original learned-element comparison')
    return {'source_float_key_set_equals_all_named_parameters': True,
            'all_source_to_FP32_values_equal': True, 'compared_tensor_count': len(rows),
            'compared_elements': count, 'per_parameter': rows,
            'trained_key_exclusions': [], 'head_reinitialization_allowed': False}

