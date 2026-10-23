"""Pinned typed threeway NLI, singleton/no-padding/no-truncation, with frozen policy tokens."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import numpy as np

REPO = 'Xenova/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION = 'a70e12f8244efae07cf6fdfa935df30e3ac4a060'


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
    def __init__(self, folder, policy_tokenizer_file, counters, *, model_path, precision):
        import onnxruntime as ort
        import tokenizers
        from tokenizers import Tokenizer
        folder = Path(folder)
        if precision not in ('FP32', 'INT8_TRAIN_DIAGNOSTIC'):
            raise ValueError('Only fixed FP32 primary or TRAIN-only INT8 diagnostic is permitted')
        self.precision = precision
        self.counter_prefix = 'nli_fp32' if precision == 'FP32' else 'nli_int8_diagnostic'
        self.counters = counters
        for suffix in ('forward_pairs_attempted', 'forward_pairs_completed', 'input_tokens_attempted', 'input_tokens_completed'):
            self.counters.setdefault(self.counter_prefix + '_' + suffix, 0)
        self.counters.setdefault(self.counter_prefix + '_forward_wall_seconds', 0.0)
        self.model_path = Path(model_path)
        self.model_sha256 = sha(self.model_path)
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
        self.session = ort.InferenceSession(str(self.model_path),
                                           sess_options=options, providers=['CPUExecutionProvider'])
        self.inputs = {item.name for item in self.session.get_inputs()}
        if not {'input_ids', 'attention_mask'} <= self.inputs <= {'input_ids', 'attention_mask', 'token_type_ids'}:
            raise ValueError('Unsupported actual threeway NLI feed names')
        self.receipt = {'repo': REPO, 'revision': REVISION,
                        'model_sha256': self.model_sha256, 'precision': precision,
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
        self.counters[self.counter_prefix + '_forward_pairs_attempted'] += 1
        self.counters[self.counter_prefix + '_input_tokens_attempted'] += len(encoded.ids)
        started = time.perf_counter()
        try:
            logits = np.asarray(self.session.run(None, feed)[0], dtype=np.float64)
            decoded = probabilities(logits, self.label_indices)
            self.counters['nli_forward_pairs_completed'] += 1
            self.counters['nli_input_tokens_completed'] += len(encoded.ids)
            self.counters[self.counter_prefix + '_forward_pairs_completed'] += 1
            self.counters[self.counter_prefix + '_input_tokens_completed'] += len(encoded.ids)
        finally:
            elapsed = time.perf_counter() - started
            self.counters['nli_forward_wall_seconds'] += elapsed
            self.counters[self.counter_prefix + '_forward_wall_seconds'] += elapsed
        trace = {'precision': self.precision, 'onnx_sha256': self.model_sha256, 'input_tokens': len(encoded.ids), 'raw_tokens': len(encoded.ids),
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


def paired_fidelity(fp32, int8):
    """Compare saved paired traces only; no fit, threshold or precision selection."""
    for field in ('input_ids', 'attention_mask', 'token_type_ids', 'input_text_sha256', 'raw_label_indices'):
        if fp32[field] != int8[field]:
            raise ValueError('FP32/INT8 comparisons require identical semantic input/feed: ' + field)
    if fp32['precision'] != 'FP32' or int8['precision'] != 'INT8_TRAIN_DIAGNOSTIC':
        raise ValueError('Invalid fixed precision comparison')
    a = np.asarray(fp32['canonical_logits_E_C_N'], dtype=np.float64)
    b = np.asarray(int8['canonical_logits_E_C_N'], dtype=np.float64)
    if a.shape != (3,) or b.shape != (3,) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Saved paired logits must be finite E/C/N triples')
    pa = np.asarray([fp32['raw_threeway_probabilities'][k] for k in ('Entailment', 'Contradiction', 'NotMentioned')])
    pb = np.asarray([int8['raw_threeway_probabilities'][k] for k in ('Entailment', 'Contradiction', 'NotMentioned')])
    if not (np.isfinite(pa).all() and np.isfinite(pb).all() and np.all(pa >= 0) and np.all(pb >= 0)
            and abs(pa.sum() - 1) <= 1e-10 and abs(pb.sum() - 1) <= 1e-10):
        raise ValueError('Saved paired probabilities must be normalized finite distributions')
    canonical = ('Entailment', 'Contradiction', 'NotMentioned')
    typed_a = min(canonical, key=lambda k: (-fp32['raw_threeway_probabilities'][k], k))
    typed_b = min(canonical, key=lambda k: (-int8['raw_threeway_probabilities'][k], k))
    def binary(p):
        return 'Yes' if p[0] > p[1] + p[2] else 'No'
    m = .5 * (pa + pb)
    def kl(p, q):
        mask = p > 0
        return float(np.sum(p[mask] * (np.log(p[mask]) - np.log(q[mask]))))
    centered = (a - a.mean()) - (b - b.mean())
    return {'input_text_sha256': fp32['input_text_sha256'], 'identical_feed_tokens': len(fp32['input_ids']),
            'raw_logits_max_absolute_difference': float(np.max(np.abs(a-b))),
            'raw_logits_RMS_difference': float(np.sqrt(np.mean((a-b)**2))),
            'centered_logits_max_absolute_difference': float(np.max(np.abs(centered))),
            'typed_probability_max_absolute_difference': float(np.max(np.abs(pa-pb))),
            'typed_probability_L1_difference': float(np.sum(np.abs(pa-pb))),
            'Jensen_Shannon_divergence_nats': .5 * (kl(pa,m) + kl(pb,m)),
            'FP32_typed_decision': typed_a, 'INT8_typed_decision': typed_b,
            'typed_decision_agrees': typed_a == typed_b,
            'FP32_binary_decision': binary(pa), 'INT8_binary_decision': binary(pb),
            'binary_decision_agrees': binary(pa) == binary(pb),
            'source_original_fidelity_established': False,
            'scope': 'Co-located FP32 and INT8 exports at the same converter repository revision. Exact upstream weight commit and conversion derivation remain unverified; no causal quantization or benchmark-generalization conclusion.'}
