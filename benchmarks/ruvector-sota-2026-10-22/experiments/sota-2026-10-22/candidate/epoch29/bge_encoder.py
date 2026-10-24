"""One local BGE-small CPU session, explicit 256-token document truncation.

Module import is standard-library only. Construct only after external source
admission, complete runtime hashes and inherited kernel CPU guard verification.
"""
import hashlib
import math
from pathlib import Path
import sys
import time

BATCH_SIZE, DIMENSIONS, MAX_TOKENS = 8, 384, 256
MODEL_SHA = '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35'
TOKENIZER_SHA = 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'


class DocumentEncoder:
    def __init__(self, root, counters, progress):
        self.counters, self.progress = counters, progress
        counters['BGE_initializations_attempted'] += 1
        progress({'event': 'BGE_INITIALIZATION_BEFORE'})
        # These imports are intentionally confined to the admitted constructor.
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        if (np.__version__, ort.__version__) != ('2.2.6', '1.22.1'):
            raise ValueError('Exact CPU NumPy/ORT versions required')
        import tokenizers
        if any(name in sys.modules for name in ('torch', 'transformers')):
            counters['Torch_imports'] = int('torch' in sys.modules)
            raise RuntimeError('Unrequested Torch/NLI library import during BGE-only construction')
        if tokenizers.__version__ != '0.21.4':
            raise ValueError('Exact tokenizer version required')
        self.np = np
        folder = Path(root) / 'models/bge-small-en-v1.5'
        counters['tokenizer_initializations_attempted'] += 1
        self.tokenizer = Tokenizer.from_file(str(folder / 'tokenizer.json'))
        if (self.tokenizer.token_to_id('[PAD]'), self.tokenizer.token_to_id('[CLS]'),
                self.tokenizer.token_to_id('[SEP]')) != (0, 101, 102):
            raise ValueError('Pinned BGE tokenizer special IDs changed')
        counters['tokenizer_initializations_completed'] += 1
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
        counters['ORT_sessions_attempted'] += 1
        self.session = ort.InferenceSession(str(folder / 'model.onnx'), sess_options=options,
            providers=['CPUExecutionProvider'])
        counters['ORT_sessions_completed'] += 1
        self.input_names = {entry.name for entry in self.session.get_inputs()}
        if self.input_names != {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Unexpected original BGE ONNX inputs')
        counters['BGE_initializations_completed'] += 1
        self.receipt = {'repository': 'Xenova/bge-small-en-v1.5',
            'revision': 'ea104dacec62c0de699686887e3f920caeb4f3e3', 'model_sha256': MODEL_SHA,
            'tokenizer_sha256': TOKENIZER_SHA, 'numpy': np.__version__, 'onnxruntime': ort.__version__,
            'tokenizers': tokenizers.__version__, 'providers': self.session.get_providers(),
            'intra_op_threads': 2, 'inter_op_threads': 1, 'max_tokens': MAX_TOKENS,
            'pooling': 'CLS', 'output_dimensions': DIMENSIONS, 'batch_size': BATCH_SIZE,
            'query_prefix': '', 'one_session': True, 'one_tokenizer': True,
            'full_document_identity_is_not_full_token_attention': True,
            'truncation': 'right single-sequence longest_first to256 including CLS/SEP, explicitly recorded',
            'no_warmup': True, 'CPU_only': True}
        progress({'event': 'BGE_INITIALIZATION_AFTER'})

    def encode(self, texts, on_document):
        np, vectors = self.np, []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            self.tokenizer.no_padding()
            self.tokenizer.no_truncation()
            self.counters['tokenizer_full_encoding_calls_attempted'] += 1
            self.counters['tokenizer_full_texts_attempted'] += len(batch)
            self.progress({'event': 'FULL_TOKENIZATION_BEFORE', 'start': start, 'texts': len(batch)})
            raw = self.tokenizer.encode_batch(batch)
            self.counters['tokenizer_full_encoding_calls_completed'] += 1
            self.counters['tokenizer_full_texts_completed'] += len(batch)
            self.tokenizer.enable_truncation(max_length=MAX_TOKENS, strategy='longest_first', direction='right')
            self.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
            self.counters['tokenizer_capped_encoding_calls_attempted'] += 1
            self.counters['tokenizer_capped_texts_attempted'] += len(batch)
            used = self.tokenizer.encode_batch(batch)
            self.counters['tokenizer_capped_encoding_calls_completed'] += 1
            self.counters['tokenizer_capped_texts_completed'] += len(batch)
            diagnostics = []
            for original, actual in zip(raw, used):
                count = sum(actual.attention_mask)
                ids = actual.ids[:count]
                expected = original.ids if len(original.ids) <= MAX_TOKENS else original.ids[:MAX_TOKENS - 1] + [original.ids[-1]]
                if (ids != expected or not 2 <= count <= MAX_TOKENS
                        or ids[0] != 101 or ids[-1] != 102
                        or actual.attention_mask != [1] * count + [0] * (len(actual.ids) - count)
                        or any(value != 0 for value in actual.ids[count:])):
                    raise ValueError('Actual BGE truncation/padding differs from declared right-prefix policy')
                truncated = len(original.ids) > MAX_TOKENS
                self.counters['BGE_truncated_texts'] += int(truncated)
                diagnostics.append({'raw_tokens': len(original.ids), 'used_tokens': count,
                    'truncated': truncated, 'max_tokens': MAX_TOKENS, 'used_token_ids': ids,
                    'used_attention_mask': actual.attention_mask, 'padded_token_ids': actual.ids,
                    'padded_tokens': len(actual.ids) - count, 'truncation_direction': 'right',
                    'full_input_bytes_are_hashed_but_tokens_after256_are_not_attended': True})
            feed = {'input_ids': np.asarray([value.ids for value in used], dtype=np.int64),
                'attention_mask': np.asarray([value.attention_mask for value in used], dtype=np.int64),
                'token_type_ids': np.asarray([value.type_ids for value in used], dtype=np.int64)}
            self.counters['BGE_forward_calls_attempted'] += 1
            self.counters['BGE_texts_attempted'] += len(batch)
            self.progress({'event': 'BGE_FORWARD_BEFORE', 'start': start, 'texts': len(batch)})
            started = time.perf_counter()
            output = self.session.run(None, feed)[0]
            seconds = time.perf_counter() - started
            self.counters['BGE_forward_calls_completed'] += 1
            self.counters['BGE_texts_completed'] += len(batch)
            self.counters['BGE_forward_seconds'] += seconds
            if output.ndim != 3 or output.shape[0] != len(batch) or output.shape[2] != DIMENSIONS:
                raise ValueError('Unexpected genuine BGE output shape')
            pooled = output[:, 0, :]
            if not np.isfinite(pooled).all():
                raise ValueError('Nonfinite genuine BGE CLS output')
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            if np.any(norms <= 0):
                raise ValueError('Zero genuine BGE CLS norm')
            normalized = (pooled / norms).astype('<f4')
            if not np.isfinite(normalized).all():
                raise ValueError('Nonfinite normalized genuine BGE embedding')
            for offset, (vector, diagnostic) in enumerate(zip(normalized, diagnostics)):
                norm = math.sqrt(math.fsum(float(value) * float(value) for value in vector))
                if abs(norm - 1) > 1e-5:
                    raise ValueError('Normalized actual BGE vector norm mismatch')
                diagnostic.update(BGE_batch_forward_seconds=seconds,
                    BGE_batch_start=start, BGE_batch_texts=len(batch), actual_vector_norm=norm,
                    vector_sha256=hashlib.sha256(vector.tobytes(order='C')).hexdigest())
                on_document(start + offset, diagnostic)
            vectors.append(normalized)
            self.progress({'event': 'BGE_FORWARD_AFTER', 'start': start, 'texts': len(batch)})
        matrix = np.concatenate(vectors, axis=0)
        if matrix.shape != (len(texts), DIMENSIONS) or matrix.dtype != np.dtype('<f4'):
            raise ValueError('Exact actual float32 matrix closure failed')
        return matrix.tobytes(order='C')
