"""Pinned typed threeway NLI, singleton/no-padding/no-truncation, with frozen policy tokens."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import numpy as np

REPO = 'Xenova/DeBERTa-v3-base-mnli-fever-anli'
REVISION = '72a1ce83a0144efaf828b3c3844320a61197a53d'


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def label_indices(config):
    mapping = {str(value).casefold(): int(key) for key, value in config['id2label'].items()}
    if set(mapping) != {'entailment', 'neutral', 'contradiction'} or sorted(mapping.values()) != [0, 1, 2]:
        raise ValueError('Expected exact threeway entailment/neutral/contradiction model labels')
    return mapping


def threeway_probabilities(logits, mapping):
    values = np.asarray(logits, dtype=np.float64)
    if values.shape != (1, 3) or not np.isfinite(values).all():
        raise ValueError('Expected finite singleton threeway logits')
    distribution = np.exp(values[0] - values[0].max())
    distribution /= distribution.sum()
    return {'Entailment': float(distribution[mapping['entailment']]),
            'Contradiction': float(distribution[mapping['contradiction']]),
            'NotMentioned': float(distribution[mapping['neutral']])}


def probabilities(logits, mapping):
    typed = threeway_probabilities(logits, mapping)
    return {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}


class SingletonNli:
    def __init__(self, folder, policy_tokenizer_file, counters):
        import onnxruntime as ort
        import tokenizers
        from tokenizers import Tokenizer
        folder = Path(folder)
        self.counters = counters
        self.config = json.loads((folder / 'config.json').read_text())
        self.label_indices = label_indices(self.config)
        # The inherited epoch6 packer sees the exact old tokenizer. Only the new
        # decoder uses this model's tokenizer, with an independent raw pair guard.
        self.tokenizer = Tokenizer.from_file(str(policy_tokenizer_file))
        self.model_tokenizer = Tokenizer.from_file(str(folder / 'tokenizer.json'))
        for tokenizer in (self.tokenizer, self.model_tokenizer):
            tokenizer.no_truncation()
            tokenizer.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(folder / 'onnx/model_quantized.onnx'),
                                           sess_options=options, providers=['CPUExecutionProvider'])
        self.inputs = {item.name for item in self.session.get_inputs()}
        if not {'input_ids', 'attention_mask'} <= self.inputs <= {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Unsupported actual threeway NLI feed names')
        self.receipt = {'repo': REPO, 'revision': REVISION,
                        'model_sha256': sha(folder / 'onnx/model_quantized.onnx'),
                        'tokenizer_sha256': sha(folder / 'tokenizer.json'),
                        'policy_tokenizer_sha256': sha(policy_tokenizer_file),
                        'config_sha256': sha(folder / 'config.json'),
                        'label_indices': self.label_indices, 'hidden_size': self.config['hidden_size'],
                        'layers': self.config['num_hidden_layers'], 'classes': 3,
                        'typed_order': ['Entailment', 'Contradiction', 'NotMentioned'],
                        'mapping': 'Yes=P(entailment);No=P(contradiction)+P(neutral)',
                        'onnxruntime': ort.__version__, 'tokenizers': tokenizers.__version__,
                        'numpy': np.__version__, 'provider': 'CPUExecutionProvider', 'threads': 2,
                        'batch_size': 1, 'padding': False, 'truncation': False,
                        'pair_token_cap': 512, 'temperature': 1.0,
                        'training_or_calibration_fit': False,
                        'source_policy': 'Exact frozen epoch6 source/packer/tokenizer; new model tokenizer only in decoder'}

    def decode(self, premise, hypothesis):
        encoded = self.model_tokenizer.encode(premise, hypothesis)
        policy_tokens = len(self.tokenizer.encode(premise, hypothesis).ids)
        if len(encoded.ids) > 512 or policy_tokens > 512:
            raise ValueError('Complete joint premise and whole claim exceed512 in model or policy tokenizer; no clipping')
        if any(item != 1 for item in encoded.attention_mask):
            raise ValueError('Threeway singleton inference must be unpadded')
        arrays = {'input_ids': np.asarray([encoded.ids], dtype=np.int64),
                  'attention_mask': np.asarray([encoded.attention_mask], dtype=np.int64),
                  'token_type_ids': np.asarray([encoded.type_ids], dtype=np.int64)}
        feed = {key: value for key, value in arrays.items() if key in self.inputs}
        self.counters['nli_forward_pairs_attempted'] += 1
        self.counters['nli_input_tokens_attempted'] += len(encoded.ids)
        started = time.perf_counter()
        try:
            logits = np.asarray(self.session.run(None, feed)[0], dtype=np.float64)
            decoded = probabilities(logits, self.label_indices)
            self.counters['nli_forward_pairs_completed'] += 1
            self.counters['nli_input_tokens_completed'] += len(encoded.ids)
        finally:
            self.counters['nli_forward_wall_seconds'] += time.perf_counter() - started
        trace = {'input_tokens': len(encoded.ids), 'raw_tokens': len(encoded.ids),
                 'used_tokens': len(encoded.ids), 'actual_model_pair_tokens': len(encoded.ids),
                 'frozen_epoch6_policy_pair_tokens': policy_tokens,
                 'batch_size': 1, 'padding_tokens': 0, 'truncated': False,
                 'input_ids': encoded.ids, 'attention_mask': encoded.attention_mask,
                 'token_type_ids': encoded.type_ids, 'logits': logits[0].tolist(),
                 'model_repo': REPO, 'model_revision': REVISION,
                 'raw_label_indices': dict(self.label_indices),
                 'typed_order': ['Entailment', 'Contradiction', 'NotMentioned'],
                 'temperature': 1.0,
                 'nli_probabilities': {name: threeway_probabilities(logits, self.label_indices)[
                     {'entailment': 'Entailment', 'contradiction': 'Contradiction', 'neutral': 'NotMentioned'}[name]]
                                      for name in self.label_indices},
                 'raw_threeway_probabilities': threeway_probabilities(logits, self.label_indices),
                 'canonical_logits_E_C_N': [float(logits[0, self.label_indices[name]])
                                            for name in ('entailment', 'contradiction', 'neutral')],
                 'input_text_sha256': hashlib.sha256(json.dumps({'premise': premise, 'hypothesis': hypothesis},
                                                                ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
                 'mapping': 'Yes=P(entailment);No=P(contradiction)+P(neutral);full threeway softmax,T1',
                 'pool': 'One unchanged epoch6 joint evidence premise; no per-chunk maximum',
                 'elapsed_ms': (time.perf_counter() - started) * 1000}
        return decoded, trace
