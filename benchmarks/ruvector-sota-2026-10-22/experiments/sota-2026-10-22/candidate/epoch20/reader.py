"""Original FP32 three-way RoBERTa reader; imports only inside owned worker."""
from __future__ import annotations
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import common as C


def hash_tensor(h, name, value, torch):
    t = value.detach().cpu().contiguous()
    h.update(C.canonical({'name': name, 'dtype': str(t.dtype), 'shape': list(t.shape)}).encode() + b'\n')
    flat = t.reshape(-1).view(torch.uint8)
    for i in range(0, flat.numel(), 1024 * 1024): h.update(flat[i:i + 1024 * 1024].numpy().tobytes())
    h.update(b'\n')


def state_identity(model, torch):
    h = hashlib.sha256()
    for name, value in sorted(model.named_parameters()): hash_tensor(h, 'parameter:' + name, value, torch)
    for name, value in sorted(model.named_buffers()): hash_tensor(h, 'buffer:' + name, value, torch)
    return h.hexdigest()


def dtype_inventory(tensors):
    result = {}
    for _, value in tensors: result[str(value.dtype)] = result.get(str(value.dtype), 0) + value.numel()
    return result


class Reader:
    def __init__(self, folder, counters, progress=None):
        started = time.perf_counter()
        import torch
        from transformers import RobertaForSequenceClassification, RobertaTokenizerFast
        self.torch, self.counters = torch, counters
        self.progress = progress or (lambda: None)
        if importlib.metadata.version('torch') != '2.7.1+cpu' or importlib.metadata.version('transformers') != '4.52.4':
            raise ValueError('Exact reviewed CPU/Transformers distribution required')
        torch.set_num_threads(2); torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        config = C.read(Path(folder) / 'config.json')
        labels = {str(k): str(v).casefold() for k, v in config['id2label'].items()}
        if labels != {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}:
            raise ValueError('Official E0/N1/C2 raw label semantics changed')
        if (config['model_type'], config['num_hidden_layers'], config['hidden_size'], config['max_position_embeddings']) != ('roberta', 24, 1024, 514):
            raise ValueError('Frozen original RoBERTa-large architecture changed')
        self.high = RobertaTokenizerFast.from_pretrained(str(folder), local_files_only=True, trust_remote_code=False)
        self.tokenizer = self.high.backend_tokenizer
        self.tokenizer.no_padding(); self.tokenizer.no_truncation()
        token_state = json.loads(self.tokenizer.to_str())
        pair = self.tokenizer.encode('generic premise', 'generic hypothesis')
        if (token_state['model']['type'] != 'BPE' or token_state.get('padding') or token_state.get('truncation')
                or pair.ids[0] != 0 or pair.ids[-1] != 2 or pair.ids.count(2) != 3
                or any(pair.type_ids) or any(x != 1 for x in pair.attention_mask)):
            raise ValueError('Unpadded exact <s>P</s></s>H</s> RoBERTa pair required')
        self.token_receipt = {'backend_sha256': hashlib.sha256(self.tokenizer.to_str().encode()).hexdigest(),
            'type': 'RobertaTokenizerFast', 'backend_model': 'BPE', 'pair_format': '<s>P</s></s>H</s>',
            'bos_id': 0, 'eos_id': 2, 'pad_id': 1, 'all_token_type_ids': 0,
            'padding': False, 'truncation': False, 'conversion': 'Builtin exact official vocab/merges; no remote code'}
        # This is a metadata-only safe checkpoint load, not a model initialization/forward.
        weights = Path(folder) / 'pytorch_model.bin'
        with weights.open('rb') as f: zip_archive = f.read(4) == b'PK\x03\x04'
        counters['checkpoint_metadata_loads_attempted'] += 1
        self.progress()
        original = torch.load(weights, map_location='cpu', weights_only=True, mmap=zip_archive)
        if not isinstance(original, dict) or not original or any(not isinstance(t, torch.Tensor) for t in original.values()):
            raise ValueError('Exact tensor state dictionary required')
        source_inventory = dtype_inventory(original.items()); source_tensors = len(original)
        source_elements = sum(t.numel() for t in original.values())
        counters['checkpoint_metadata_loads_completed'] += 1
        del original; gc.collect()
        counters['model_initializations_attempted'] += 1
        self.progress()
        model, loading = RobertaForSequenceClassification.from_pretrained(str(folder), local_files_only=True,
            trust_remote_code=False, use_safetensors=False, weights_only=True, torch_dtype=torch.float32,
            output_loading_info=True, attn_implementation='eager')
        counters['model_initializations_completed'] += 1
        if any(loading.get(k) for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('Original builtin model did not load exact tensor keys: ' + C.canonical(loading))
        model.eval(); self.model = model
        tensors = list(model.named_parameters()) + list(model.named_buffers())
        if any(v.device.type != 'cpu' or (v.is_floating_point() and v.dtype != torch.float32) for _, v in tensors):
            raise ValueError('Every floating model parameter and buffer must be FP32 CPU')
        if any('quantized' in type(m).__module__ for m in model.modules()): raise ValueError('No precision transform permitted')
        self.state_sha = state_identity(model, torch)
        self.state = {'parameter_count': sum(t.numel() for t in model.parameters()),
            'parameter_dtype_element_counts': dtype_inventory(model.named_parameters()),
            'buffer_dtype_element_counts': dtype_inventory(model.named_buffers()),
            'all_floating_parameters_buffers_FP32': True, 'devices': ['cpu'], 'eval': not model.training,
            'state_sha256': self.state_sha, 'model_instance_token': hex(id(model)),
            'classifier_dense_shape': list(model.classifier.dense.weight.shape),
            'classifier_out_proj_shape': list(model.classifier.out_proj.weight.shape),
            'classifier_dense_bias_shape': list(model.classifier.dense.bias.shape),
            'classifier_out_proj_bias_shape': list(model.classifier.out_proj.bias.shape),
            'quantized_modules': 0, 'threads': torch.get_num_threads(), 'interop_threads': torch.get_num_interop_threads(),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled()}
        self.receipt = {'repo': C.MODEL, 'revision': C.REVISION, 'raw_id2label': {'0': 'Entailment', '1': 'NotMentioned', '2': 'Contradiction'},
            'canonical_order': list(C.ORDER), 'canonical_permutation': [0, 2, 1],
            'precision': 'ORIGINAL_CHECKPOINT_EXPLICIT_FP32_CPU_NO_QUANTIZATION',
            'load_flags': {'local_files_only': True, 'trust_remote_code': False, 'weights_only': True,
                'use_safetensors': False, 'torch_dtype': 'torch.float32', 'output_loading_info': True,
                'attn_implementation': 'eager'}, 'actual_attention_implementation': model.config._attn_implementation,
            'loading_info': loading, 'source_checkpoint_dtype_elements': source_inventory,
            'source_checkpoint_tensors': source_tensors, 'source_checkpoint_elements': source_elements,
            'source_checkpoint_metadata_safe_mmap': zip_archive, 'initialization_model_forwards': 0,
            'quantization_initializations': 0, 'pair_token_cap': 512, 'batch_size': 1, 'temperature': 1.0,
            'tokenizer': self.token_receipt, 'state_sha256': self.state_sha,
            'state_hash_recipe': 'Sorted named parameters then buffers; canonical JSON name/dtype/shape LF, contiguous tensor uint8 bytes LF',
            'initialization_wall_seconds': time.perf_counter() - started,
            'versions': {k: importlib.metadata.version(k) for k in ('torch', 'transformers', 'tokenizers', 'numpy', 'safetensors')},
            'declared_training': ['SNLI', 'MNLI', 'FEVER', 'ANLI-R1', 'ANLI-R2', 'ANLI-R3'],
            'known_ContractNLI_supervision': False, 'full_training_lineage_verified': False,
            'record_level_pretraining_overlap_verified': False, 'legal_competence_established': False}

    def forward(self, premise, hypothesis):
        start = time.perf_counter(); encoded = self.tokenizer.encode(premise, hypothesis)
        if (len(encoded.ids) > 512 or encoded.ids[0] != 0 or encoded.ids[-1] != 2
                or any(encoded.type_ids) or any(v != 1 for v in encoded.attention_mask)):
            raise ValueError('Exact complete unpadded/untruncated pair must fit512')
        values = {'input_ids': [encoded.ids], 'attention_mask': [encoded.attention_mask]}
        feed = {key: self.torch.tensor(value, dtype=self.torch.long) for key, value in values.items()}
        self.counters['nli_forward_pairs_attempted'] += 1
        self.progress()
        with self.torch.inference_mode(), self.torch.autocast('cpu', enabled=False):
            y = self.model(**feed).logits
        if list(y.shape) != [1, 3]: raise ValueError('Three original singleton logits required')
        logits = [float(x) for x in y.detach().cpu()[0].tolist()]
        raw, typed = C.distribution(logits)
        self.counters['nli_forward_pairs_completed'] += 1
        binary = {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}
        return {'premise': premise, 'hypothesis': hypothesis,
            'input_text_sha256': hashlib.sha256(C.canonical([premise, hypothesis]).encode()).hexdigest(),
            'raw_logits': logits, 'raw_probabilities': raw, 'typed_probabilities': typed,
            'typed_prediction': C.prediction(typed), 'binary_probabilities': binary,
            'binary_prediction': 'Yes' if binary['Yes'] >= .5 else 'No',
            'feed': values, 'token_type_ids_not_fed': [encoded.type_ids],
            'feed_sha256': hashlib.sha256(C.canonical(values).encode()).hexdigest(),
            'actual_tokens': len(encoded.ids), 'elapsed_seconds': time.perf_counter() - start,
            'model_state_sha256': self.state_sha, 'model_instance_token': hex(id(self.model)),
            'padding': False, 'truncation': False, 'inference_mode': True, 'cpu_autocast': False}
