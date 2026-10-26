"""Bounded ZIP and pickle OPCODE metadata inspection; never executes pickle or Torch."""
import argparse
import ast
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import pickletools
import re
import struct
import zipfile

EXPECTED_BYTES = 1425814813
EXPECTED_SHA = 'a51c55cb7dc41c4c862f06a3d9c413a8aa0619222bc56f06cb6f2f5b2d3ee14a'
INTEGER_OPS = {'BININT', 'BININT1', 'BININT2', 'INT', 'LONG', 'LONG1', 'LONG4'}
STRING_OPS = {'BINUNICODE', 'SHORT_BINUNICODE', 'UNICODE', 'STRING'}
MEMO_OPS = {'BINPUT', 'LONG_BINPUT', 'PUT'}


def sha_file(path):
    out = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            out.update(block)
    return out.hexdigest()


def ref(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha_file(path)}


def require(value, code):
    if not value:
        raise ValueError(code)


def tuple_ints(ops, start):
    values = []; index = start
    while index < len(ops):
        op, arg, _ = ops[index]
        if op.name in MEMO_OPS:
            index += 1; continue
        if op.name in INTEGER_OPS:
            require(type(arg) is int, 'SCALAR_INTEGER_METADATA')
            values.append(arg)
        elif op.name in ('TUPLE', 'TUPLE1', 'TUPLE2', 'TUPLE3'):
            if op.name != 'TUPLE':
                require(len(values) == int(op.name[-1]), 'TUPLE_METADATA_ARITY')
            return values, index + 1
        else:
            raise ValueError('UNEXPECTED_SHAPE_METADATA_OPCODE')
        index += 1
    raise ValueError('SHAPE_METADATA_UNTERMINATED')


def inspect(path):
    require(path.is_absolute() and not path.is_symlink() and path.stat().st_size == EXPECTED_BYTES,
            'KNOWN_MODEL_FILE_SIZE')
    actual_sha = sha_file(path); require(actual_sha == EXPECTED_SHA, 'KNOWN_MODEL_PAYLOAD_SHA')
    require(zipfile.is_zipfile(path), 'ACTUAL_CHECKPOINT_IS_ZIP')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist(); require(1 <= len(infos) <= 4096, 'ZIP_MEMBER_BOUND')
        require(len({x.filename for x in infos}) == len(infos), 'ZIP_NAMES_UNIQUE')
        for item in infos:
            name = PurePosixPath(item.filename)
            require(not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename,
                    'ZIP_SAFE_RELATIVE_MEMBER')
            require(not item.flag_bits & 1, 'ZIP_NOT_ENCRYPTED')
            require(item.compress_type == zipfile.ZIP_STORED and item.compress_size == item.file_size,
                    'ZIP_STORAGE_UNCOMPRESSED')
        member = next(x for x in infos if x.filename == 'archive/data.pkl')
        require(member.file_size <= 1048576, 'PICKLE_METADATA_MAX_1MIB')
        metadata = archive.read(member)
        # genops parses opcode syntax. No pickle loader, callable invocation, REDUCE,
        # BUILD, persistent ID resolution, storage construction or tensor materialization occurs.
        ops = list(pickletools.genops(metadata)); require(len(ops) <= 100000, 'OPCODE_BOUND')
        require(ops[-1][0].name == 'STOP' and ops[-1][2] + 1 == len(metadata), 'SINGLE_COMPLETE_METADATA_PICKLE')
        global_refs = sorted({arg for op, arg, _ in ops if op.name == 'GLOBAL'})
        require(global_refs == ['collections OrderedDict', 'torch FloatStorage',
                                'torch._utils _rebuild_tensor_v2'], 'EXACT_DECLARATIVE_GLOBAL_REFS')
        key_ops = [(i, arg, pos) for i, (op, arg, pos) in enumerate(ops)
                   if op.name in STRING_OPS and type(arg) is str
                   and re.fullmatch(r'(?:roberta|classifier)\..+\.(?:weight|bias)', arg)]
        require(len(key_ops) == 395 and len({x[1] for x in key_ops}) == 395,
                'EXACT_395_TENSOR_KEY_STRINGS')
        strings = {arg for op, arg, _ in ops if op.name in STRING_OPS and type(arg) is str}
        tensor_records = []
        all_storage = {x.filename: x for x in infos if x.filename.startswith('archive/data/')}
        for ordinal, (start, key, byte_position) in enumerate(key_ops):
            end = key_ops[ordinal + 1][0] if ordinal + 1 < len(key_ops) else len(ops)
            window = ops[start:end]
            pointers = [i for i, (op, _, _) in enumerate(window) if op.name == 'BINPERSID']
            require(len(pointers) == 1, 'ONE_DECLARATIVE_STORAGE_POINTER_PER_TENSOR')
            pointer = pointers[0]
            storage_names = [arg for op, arg, _ in window[:pointer]
                             if op.name in STRING_OPS and type(arg) is str and arg.isdecimal()]
            require(len(storage_names) == 1, 'ONE_STORAGE_ID_STRING')
            numels = [arg for op, arg, _ in window[:pointer] if op.name in INTEGER_OPS]
            require(len(numels) == 1 and type(numels[0]) is int, 'STORAGE_NUMEL_LITERAL')
            at = pointer + 1
            while window[at][0].name in MEMO_OPS:
                at += 1
            require(window[at][0].name in INTEGER_OPS and window[at][1] == 0, 'ZERO_STORAGE_OFFSET')
            shape, at = tuple_ints(window, at + 1)
            strides, at = tuple_ints(window, at)
            require(shape and all(type(x) is int and x > 0 for x in shape)
                    and len(shape) == len(strides), 'POSITIVE_SHAPE_AND_STRIDES')
            expected_stride = []; product = 1
            for size in reversed(shape):
                expected_stride.insert(0, product); product *= size
            require(strides == expected_stride and product == numels[0], 'CONTIGUOUS_FULL_STORAGE_SHAPE')
            name = 'archive/data/' + storage_names[0]
            require(name in all_storage and all_storage[name].file_size == product * 4,
                    'FLOAT32_STORAGE_BYTE_SIZE_MATCHES_SHAPE')
            tensor_records.append({'key': key, 'shape': shape, 'stride': strides,
                'numel': product, 'dtype_from_declared_storage': 'float32',
                'storage_member': name, 'storage_bytes': all_storage[name].file_size,
                'metadata_key_opcode_byte_position': byte_position})
        require(len({x['storage_member'] for x in tensor_records}) == len(all_storage) == 395,
                'EXACT_ONE_TO_ONE_STORAGE_MEMBERS')
        keys = {x['key'] for x in tensor_records}
        head_keys = ['classifier.dense.weight', 'classifier.dense.bias',
                     'classifier.out_proj.weight', 'classifier.out_proj.bias']
        pooler_keys = ['roberta.pooler.dense.weight', 'roberta.pooler.dense.bias']
        require(set(head_keys + pooler_keys) <= keys, 'ORIGINAL_CLASSIFIER_AND_POOLER_PRESENT')
        offsets = []
        with path.open('rb') as stream:
            for item in all_storage.values():
                stream.seek(item.header_offset); h = stream.read(30)
                values = struct.unpack('<IHHHHHIIIHH', h)
                require(values[0] == 0x04034B50, 'LOCAL_ZIP_RECORD_SIGNATURE')
                payload = item.header_offset + 30 + values[-2] + values[-1]
                require(payload + item.file_size <= path.stat().st_size, 'ZIP_PAYLOAD_OFFSET_BOUNDS')
                offsets.append(payload)
        version = archive.read('archive/version')
    return {'schema_version': 1, 'epoch': 48, 'scope': 'PURE_STRUCTURAL_METADATA_NO_MODEL_EXECUTION',
        'checkpoint': {'path': str(path), 'bytes': EXPECTED_BYTES, 'sha256': actual_sha},
        'zip': {'is_zipfile': True, 'members': len(infos), 'all_members_ZIP_STORED': True,
                'all_members_unencrypted': True, 'storage_members': len(all_storage),
                'total_uncompressed_member_bytes': sum(x.file_size for x in infos),
                'storage_payload_bytes': sum(x.file_size for x in all_storage.values()),
                'storage_data_offsets_mod64_counts': dict(Counter(str(x % 64) for x in offsets)),
                'archive_version_bytes_hex': version.hex(),
                'byteorder_member_present': any(x.filename.endswith('/byteorder') for x in infos)},
        'pickle_opcode_metadata': {'member': member.filename, 'bytes': len(metadata),
                'sha256': hashlib.sha256(metadata).hexdigest(), 'opcodes': len(ops),
                'opcode_counts': dict(Counter(op.name for op, _, _ in ops)),
                'protocols': [arg for op, arg, _ in ops if op.name == 'PROTO'],
                'declared_global_references': global_refs,
                'position_ids_key_present': 'roberta.embeddings.position_ids' in strings,
                'token_type_ids_key_present': 'roberta.embeddings.token_type_ids' in strings,
                'pickle_callables_executed': 0, 'persistent_ids_resolved': 0,
                'tensor_storage_payload_values_decoded': 0},
        'tensor_metadata': tensor_records,
        'classifier_tensors': [x for x in tensor_records if x['key'] in head_keys],
        'pooler_tensors': [x for x in tensor_records if x['key'] in pooler_keys],
        'tensor_count': len(tensor_records), 'numel_total': sum(x['numel'] for x in tensor_records),
        'torch_imports_or_loads_or_model_initializations_or_forwards': 0,
        'native_RuVector_or_BGE_or_tokenizer_calls': 0,
        'feature_Gold_or_confirmation_reads': 0,
        'format_only_mmap_eligibility': 'ZIP_STORED with exact bounded unencrypted storage offsets; actual Torch mmap load NOT executed or qualified.'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    output = Path(args.output); require(not output.exists(), 'ONCE_OUTPUT')
    result = inspect(Path(args.checkpoint))
    source = Path(__file__); result['inspection_source'] = ref(source)
    data = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    f = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.write(f, data); os.fsync(f); os.close(f)
    print(json.dumps({'output': ref(output), 'tensor_count': result['tensor_count'],
                      'numel_total': result['numel_total'], 'zip': result['zip'],
                      'classifier': result['classifier_tensors'], 'pooler': result['pooler_tensors']}))


if __name__ == '__main__':
    main()
