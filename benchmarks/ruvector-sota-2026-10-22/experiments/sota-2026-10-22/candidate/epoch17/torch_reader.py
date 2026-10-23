"""One official typed CPU reader. Import/load/quantize only in bounded worker.

Tokenizer construction is pure and may run prelabel. No calibration, export,
weight fitting, model warmup or hidden forward is performed by initialization.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import time

REPO = 'microsoft/deberta-v2-xlarge-mnli'
REVISION = '2b65bccdedcead4bc685988bcc30153d4922a789'
WEIGHT_SHA256 = 'cc41eeb065c6ab3f7e88f8dab756334abb1f77a1136fec8cf02442143934c253'
SPM_SHA256 = '5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17'
CONFIG_SHA256 = '617f9d0b46fe934497a5aab5b44b1b343a751c0c43fec3e56e26b21e76b77c60'
TYPED_ORDER = ['Entailment', 'Contradiction', 'NotMentioned']
PRECISION = 'TORCH_DYNAMIC_QINT8_LINEAR_FP32_REMAINDER_FBGEMM'
VERSIONS = {'torch': '2.7.1+cpu', 'transformers': '4.52.4', 'sentencepiece': '0.2.0',
            'tokenizers': '0.21.4', 'safetensors': '0.5.3', 'protobuf': '5.29.5'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def label_indices(config):
    raw = config.get('id2label', {})
    if not isinstance(raw, dict) or len(raw) != 3:
        raise ValueError('Exactly three explicit source labels required')
    mapping = {str(value).casefold(): int(key) for key, value in raw.items()}
    if set(mapping) != {'entailment', 'contradiction', 'neutral'} or sorted(mapping.values()) != [0, 1, 2]:
        raise ValueError('Invalid threeway source label identity')
    return mapping


def threeway_probabilities(logits, mapping):
    if len(logits) != 3 or any(not math.isfinite(float(x)) for x in logits):
        raise ValueError('Expected three finite raw singleton logits')
    peak = max(logits)
    values = [math.exp(float(x) - peak) for x in logits]
    mass = math.fsum(values)
    return {key: values[mapping[label]] / mass for key, label in
            zip(TYPED_ORDER, ('entailment', 'contradiction', 'neutral'))}


def typed_prediction(probabilities):
    return max(TYPED_ORDER, key=lambda label: probabilities[label])


def tokenizer_only(folder):
    """Official builtin SPM -> fast conversion; no model construction/session."""
    from transformers import DebertaV2TokenizerFast
    folder = Path(folder)
    if sha(folder / 'spm.model') != SPM_SHA256:
        raise ValueError('Official SentencePiece identity changed')
    high = DebertaV2TokenizerFast.from_pretrained(str(folder), local_files_only=True,
                                                  trust_remote_code=False)
    tokenizer = high.backend_tokenizer
    tokenizer.no_truncation()
    tokenizer.no_padding()
    for text, token_id in ((high.cls_token, high.cls_token_id), (high.sep_token, high.sep_token_id)):
        if tokenizer.token_to_id(text) != token_id:
            raise ValueError('Builtin special-token identity disagrees with converted tokenizer')
    encoded = tokenizer.encode('generic source', 'generic hypothesis')
    if (encoded.ids[0] != high.cls_token_id or encoded.ids[-1] != high.sep_token_id or
            encoded.ids.count(high.sep_token_id) != 2 or encoded.type_ids[0] != 0 or
            encoded.type_ids[-1] != 1 or any(x != 1 for x in encoded.attention_mask)):
        raise ValueError('Expected exact unpadded A0/B1 DeBERTa pair serialization')
    state = json.loads(tokenizer.to_str())
    if state['model']['type'] != 'Unigram' or state.get('truncation') or state.get('padding'):
        raise ValueError('Expected unpadded, untruncated official Unigram tokenizer')
    return tokenizer, {'spm_sha256': SPM_SHA256,
                       'converted_backend_sha256': hashlib.sha256(tokenizer.to_str().encode()).hexdigest(),
                       'cls_id': high.cls_token_id, 'sep_id': high.sep_token_id,
                       'pad_id': high.pad_token_id, 'unk_id': high.unk_token_id,
                       'pair_format': '[CLS]premise[SEP]hypothesis[SEP]',
                       'conversion': 'Builtin Transformers4.52.4 DebertaV2TokenizerFast from official SPM; no remote code'}


def _hash_tensor(digest, name, tensor, torch):
    tensor = tensor.detach().cpu().contiguous()
    meta = {'name': name, 'dtype': str(tensor.dtype), 'shape': list(tensor.shape)}
    if tensor.is_quantized:
        meta['qscheme'] = str(tensor.qscheme())
        if tensor.qscheme() in (torch.per_tensor_affine, torch.per_tensor_symmetric):
            meta.update(scale=tensor.q_scale(), zero_point=tensor.q_zero_point())
        else:
            meta['axis'] = tensor.q_per_channel_axis()
            _hash_tensor(digest, name + ':scales', tensor.q_per_channel_scales(), torch)
            _hash_tensor(digest, name + ':zero_points', tensor.q_per_channel_zero_points(), torch)
        tensor = tensor.int_repr()
    digest.update(json.dumps(meta, sort_keys=True, separators=(',', ':')).encode() + b'\n')
    flat = tensor.reshape(-1).view(torch.uint8)
    for index in range(0, flat.numel(), 1024 * 1024):
        digest.update(flat[index:index + 1024 * 1024].numpy().tobytes())
    digest.update(b'\n')


def quantized_state_identity(model, torch):
    """Canonical tensor bytes and qparams, independent of torch.save archive."""
    digest = hashlib.sha256()
    modules = []
    for name, value in sorted(model.named_parameters()):
        _hash_tensor(digest, 'parameter:' + name, value, torch)
    for name, value in sorted(model.named_buffers()):
        _hash_tensor(digest, 'buffer:' + name, value, torch)
    for name, value in sorted(model.named_modules()):
        if isinstance(value, torch.ao.nn.quantized.dynamic.Linear):
            weight, bias = value.weight(), value.bias()
            _hash_tensor(digest, 'dynamic_linear_weight:' + name, weight, torch)
            if bias is not None:
                _hash_tensor(digest, 'dynamic_linear_bias:' + name, bias, torch)
            modules.append({'name': name, 'weight_dtype': str(weight.dtype),
                            'shape': list(weight.shape), 'qscheme': str(weight.qscheme())})
    if not modules:
        raise ValueError('Fixed dynamic recipe converted zero Linear modules')
    return digest.hexdigest(), modules


class SingletonNli:
    def __init__(self, folder, counters):
        started = time.perf_counter()
        for package, version in VERSIONS.items():
            if importlib.metadata.version(package) != version:
                raise ValueError('Frozen Python runtime mismatch: ' + package)
        import torch
        from transformers import DebertaV2ForSequenceClassification
        self.torch, self.counters = torch, counters
        folder = Path(folder)
        if sha(folder / 'pytorch_model.bin') != WEIGHT_SHA256 or sha(folder / 'config.json') != CONFIG_SHA256:
            raise ValueError('Original official checkpoint/config identity changed')
        config = json.loads((folder / 'config.json').read_text())
        self.label_indices = label_indices(config)
        if self.label_indices != {'contradiction': 0, 'neutral': 1, 'entailment': 2}:
            raise ValueError('Frozen official C0/N1/E2 source mapping changed')
        if (config['num_hidden_layers'], config['hidden_size'], config['max_position_embeddings']) != (24, 1536, 512):
            raise ValueError('Frozen larger reader architecture changed')
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        if 'fbgemm' not in torch.backends.quantized.supported_engines:
            raise ValueError('Frozen fbgemm dynamic quantization backend unavailable')
        torch.backends.quantized.engine = 'fbgemm'
        self.tokenizer, token_receipt = tokenizer_only(folder)
        self.model_tokenizer = self.tokenizer
        model, loading = DebertaV2ForSequenceClassification.from_pretrained(
            str(folder), local_files_only=True, trust_remote_code=False,
            use_safetensors=False, weights_only=True, torch_dtype=torch.float32,
            output_loading_info=True)
        if any(loading.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('Official checkpoint did not load exact builtin model keys: ' + json.dumps(loading))
        model.eval()
        parameters = sum(x.numel() for x in model.parameters())
        before_dtypes = sorted({str(x.dtype) for x in model.parameters()})
        if before_dtypes != ['torch.float32'] or any(x.device.type != 'cpu' for x in model.parameters()):
            raise ValueError('Fixed prequantization FP32 CPU model required')
        eligible = sum(isinstance(x, torch.nn.Linear) for x in model.modules())
        torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8, inplace=True)
        model.eval()
        self.model = model
        state_sha, converted = quantized_state_identity(model, torch)
        if len(converted) != eligible:
            raise ValueError('Every eligible nn.Linear must be dynamically quantized')
        self.inputs = ['input_ids', 'attention_mask', 'token_type_ids']
        self.receipt = {'repo': REPO, 'revision': REVISION, 'classes': 3,
                        'original_checkpoint_sha256': WEIGHT_SHA256,
                        'original_checkpoint_storage_dtype': 'Not independently inspected; explicit load dtype FP32',
                        'tokenizer_sha256': SPM_SHA256, 'tokenizer': token_receipt,
                        'config_sha256': CONFIG_SHA256, 'label_indices': self.label_indices,
                        'typed_order': TYPED_ORDER, 'hidden_size': 1536, 'layers': 24,
                        'parameter_count_before_quantization': parameters,
                        'loaded_parameter_dtypes_before_quantization': before_dtypes,
                        'quantized_linear_count': len(converted), 'quantized_linear_modules': converted,
                        'quantized_weight_state_sha256': state_sha,
                        'quantized_state_hash_recipe': 'sorted named parameters/buffers then dynamic Linear weight/bias; canonical name/dtype/shape/qparams and exact tensor bytes, LF boundaries',
                        'quantization_recipe': 'torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True);eval;FP32 original loading;fbgemm',
                        'precision': PRECISION, 'versions': dict(VERSIONS), 'device': 'cpu',
                        'threads': torch.get_num_threads(), 'interop_threads': torch.get_num_interop_threads(),
                        'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
                        'actual_model_inputs': self.inputs, 'type_vocab_size': config['type_vocab_size'],
                        'token_type_ids_scope': 'Exact pair feed retained; source config type_vocab_size=0 uses no segment embedding',
                        'batch_size': 1, 'padding': False, 'truncation': False, 'pair_token_cap': 512,
                        'temperature': 1.0, 'training_or_calibration_fit': False,
                        'model_initializations': 1, 'quantization_initializations': 1,
                        'initialization_model_forwards': 0,
                        'initialization_wall_seconds': time.perf_counter() - started}

    def decode(self, premise, hypothesis):
        encoded = self.tokenizer.encode(premise, hypothesis)
        if len(encoded.ids) > 512 or any(x != 1 for x in encoded.attention_mask):
            raise ValueError('Exact singleton pair must fit512 without padding or clipping')
        if encoded.type_ids[0] != 0 or encoded.type_ids[-1] != 1:
            raise ValueError('Expected complete A0/B1 pair')
        torch = self.torch
        values = {'input_ids': encoded.ids, 'attention_mask': encoded.attention_mask,
                  'token_type_ids': encoded.type_ids}
        feed = {key: torch.tensor([value], dtype=torch.int64, device='cpu') for key, value in values.items()}
        for key in ('nli_forward_pairs_attempted', 'new_reader_forward_pairs_attempted'):
            self.counters[key] += 1
        self.counters['nli_input_tokens_attempted'] += len(encoded.ids)
        started = time.perf_counter()
        try:
            with torch.inference_mode():
                output = self.model(**feed).logits
            if tuple(output.shape) != (1, 3) or output.dtype != torch.float32:
                raise ValueError('Expected singleton float32 raw threeway logits')
            logits = [float(x) for x in output[0].tolist()]
            typed = threeway_probabilities(logits, self.label_indices)
            for key in ('nli_forward_pairs_completed', 'new_reader_forward_pairs_completed'):
                self.counters[key] += 1
            self.counters['nli_input_tokens_completed'] += len(encoded.ids)
        finally:
            elapsed = time.perf_counter() - started
            self.counters['nli_forward_wall_seconds'] += elapsed
        trace = {**values, 'logits': logits, 'raw_logit_dtype': 'float32',
                 'model_repo': REPO, 'model_revision': REVISION, 'precision': PRECISION,
                 'original_checkpoint_sha256': WEIGHT_SHA256,
                 'quantized_weight_state_sha256': self.receipt['quantized_weight_state_sha256'],
                 'tokenizer_sha256': SPM_SHA256, 'config_sha256': CONFIG_SHA256,
                 'converted_tokenizer_backend_sha256': self.receipt['tokenizer']['converted_backend_sha256'],
                 'raw_label_indices': dict(self.label_indices), 'typed_order': TYPED_ORDER,
                 'raw_threeway_probabilities': typed,
                 'canonical_logits_E_C_N': [logits[self.label_indices[x]] for x in ('entailment', 'contradiction', 'neutral')],
                 'input_tokens': len(encoded.ids), 'raw_tokens': len(encoded.ids), 'used_tokens': len(encoded.ids),
                 'actual_model_pair_tokens': len(encoded.ids), 'actual_model_inputs': self.inputs,
                 'batch_size': 1, 'padding_tokens': 0, 'truncated': False, 'temperature': 1.0,
                 'pair_format': '[CLS]premise[SEP]hypothesis[SEP]',
                 'input_text_sha256': hashlib.sha256(json.dumps({'premise': premise, 'hypothesis': hypothesis},
                     ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
                 'mapping': 'Yes=E;No=C+N;typed E/C/N softmaxT1;no decision fitting',
                 'elapsed_ms': elapsed * 1000}
        return {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}, trace
