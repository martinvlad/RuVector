"""Lossless per-document BGE float32le bundle; standard library only."""
import base64
import hashlib
import math
import struct


def encode(payload, rows):
    if type(rows) is not int or not 1 <= rows <= 256 or len(payload) != rows * 384 * 4:
        raise ValueError('Exact bounded BGE384 float32 matrix required')
    return {'encoding': 'base64', 'dtype': 'float32le', 'shape': [rows, 384], 'bytes': len(payload),
        'sha256': hashlib.sha256(payload).hexdigest(), 'data_base64': base64.b64encode(payload).decode('ascii')}


def decode(block):
    if (block.get('encoding') != 'base64' or block.get('dtype') != 'float32le'
            or not isinstance(block.get('shape'), list) or len(block['shape']) != 2
            or type(block['shape'][0]) is not int or not 1 <= block['shape'][0] <= 256
            or block['shape'][1] != 384):
        raise ValueError('Wrong source BGE matrix schema')
    payload = base64.b64decode(block['data_base64'], validate=True)
    if (base64.b64encode(payload).decode('ascii') != block['data_base64']
            or len(payload) != block['shape'][0] * 1536 or len(payload) != block['bytes']
            or hashlib.sha256(payload).hexdigest() != block['sha256']):
        raise ValueError('Lossless BGE matrix identity differs')
    for offset in range(0, len(payload), 1536):
        vector = [value[0] for value in struct.iter_unpack('<f', payload[offset:offset + 1536])]
        if not all(math.isfinite(value) for value in vector) or abs(math.sqrt(math.fsum(value * value for value in vector)) - 1) > 1e-5:
            raise ValueError('Source BGE vector is not finite normalized float32')
    return payload
