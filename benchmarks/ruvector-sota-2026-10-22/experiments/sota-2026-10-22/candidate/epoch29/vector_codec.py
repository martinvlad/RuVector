"""Lossless float32 evidence and exact dense cosine; standard library only."""
import base64
import hashlib
import json
import math
import struct
import unicodedata

DIMENSIONS = 384
MAX_ROWS = 262


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def bge_text(authoritative_normalized_text):
    # This is a model-input canonicalization, NOT the historical alias oracle.
    # Separators remain present; never concatenate all words into a single UNK.
    return unicodedata.normalize('NFKC', authoritative_normalized_text).casefold()


def encode_matrix(payload, rows):
    if type(rows) is not int or not 1 <= rows <= MAX_ROWS or len(payload) != rows * DIMENSIONS * 4:
        raise ValueError('Exact bounded float32le matrix shape required')
    return {'encoding': 'base64', 'dtype': 'float32le', 'shape': [rows, DIMENSIONS],
        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
        'data_base64': base64.b64encode(payload).decode('ascii')}


def decode_matrix(block):
    if (not isinstance(block, dict) or block.get('encoding') != 'base64' or block.get('dtype') != 'float32le'
            or not isinstance(block.get('shape'), list) or len(block['shape']) != 2
            or type(block['shape'][0]) is not int or not 1 <= block['shape'][0] <= MAX_ROWS
            or block['shape'][1] != DIMENSIONS):
        raise ValueError('Wrong exact float32le matrix schema')
    payload = base64.b64decode(block['data_base64'], validate=True)
    if (base64.b64encode(payload).decode('ascii') != block['data_base64']
            or len(payload) != block['shape'][0] * DIMENSIONS * 4 or block['bytes'] != len(payload)
            or hashlib.sha256(payload).hexdigest() != block['sha256']):
        raise ValueError('Noncanonical or mismatched matrix bytes/hash')
    rows = [tuple(x[0] for x in struct.iter_unpack('<f', payload[i:i + DIMENSIONS * 4]))
            for i in range(0, len(payload), DIMENSIONS * 4)]
    for row in rows:
        if not all(math.isfinite(value) for value in row):
            raise ValueError('Nonfinite actual float32 embedding')
        norm = math.sqrt(math.fsum(value * value for value in row))
        if abs(norm - 1) > 1e-5:
            raise ValueError('Actual BGE embeddings must be normalized')
    return payload, rows


def dense_top16(query, corpus_ids, corpus_rows, exclude_document_id, counters):
    """Exhaust every NONSELF pair; no ANN, vector quantization or cached row."""
    query_norm = math.sqrt(math.fsum(value * value for value in query))
    if not query_norm:
        raise ValueError('Zero query norm')
    values = []
    for document_id, vector in zip(corpus_ids, corpus_rows):
        if document_id == exclude_document_id:
            continue
        counters['dense_cosines_attempted'] += 1
        denominator = query_norm * math.sqrt(math.fsum(value * value for value in vector))
        cosine = math.fsum(a * b for a, b in zip(query, vector)) / denominator
        if not math.isfinite(cosine) or not -1.000000000001 <= cosine <= 1.000000000001:
            raise ValueError('Nonfinite/out-of-range exact dense cosine')
        counters['dense_cosines_completed'] += 1
        values.append({'document_id': document_id, 'cosine': cosine})
    values.sort(key=lambda row: (-row['cosine'], row['document_id']))
    return values[:16], len(values)


def canonical_json_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
        sort_keys=True, allow_nan=False).encode('utf-8')).hexdigest()
