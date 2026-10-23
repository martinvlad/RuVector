"""Original DeBERTa-v3 NLI FP16 checkpoint, explicit FP32 stock CPU inference."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time
import common as C
import checkpoint as K

TOKENIZER_QUALIFIED_SHA = 'a2b2ae8ced43b5dd84518c55b06f8c6d6c51b6240b835886433a094eb6d7f7bd'
TOKENIZER_QUALIFIED_BYTES = 4551531


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


def validate_config(config):
    labels = {str(k): str(v).casefold() for k, v in config['id2label'].items()}
    if labels != {'0': 'entailment', '1': 'neutral', '2': 'contradiction'}:
        raise ValueError('Official E0/N1/C2 raw label semantics changed')
    expected = {'model_type': 'deberta-v2', 'num_hidden_layers': 24, 'hidden_size': 1024,
        'num_attention_heads': 16, 'max_position_embeddings': 512, 'vocab_size': 128100,
        'type_vocab_size': 0, 'relative_attention': True, 'position_biased_input': False,
        'pooler_hidden_size': 1024, 'pooler_hidden_act': 'gelu', 'torch_dtype': 'float16'}
    if (any(type(config.get(k)) is not type(v) or config.get(k) != v for k, v in expected.items())
            or config.get('pos_att_type') != ['p2c', 'c2p']):
        raise ValueError('Frozen original DeBERTa-v3-large architecture changed')
    return dict(expected, pos_att_type=['p2c', 'c2p'], architecture='DebertaV2ForSequenceClassification')


def validate_pair(ids, mask, segments, sequence_ids):
    if (not isinstance(ids, list) or not ids or len(ids) > 512 or ids[0] != 1 or ids[-1] != 2
            or len(mask) != len(ids) or len(segments) != len(ids) or len(sequence_ids) != len(ids)
            or any(type(v) is not int or v < 0 or v >= 128100 for v in ids)
            or any(type(v) is not int or v != 1 for v in mask)
            or any(type(v) is not int or v not in (0, 1) for v in segments)
            or any(v is not None and (type(v) is not int or v not in (0, 1)) for v in sequence_ids)):
        raise ValueError('Exact complete unpadded/untruncated DeBERTa singleton pair required')
    if sequence_ids[0] is not None or sequence_ids[-1] is not None:
        raise ValueError('Original CLS and final SEP must be source special tokens')
    # The pair template, rather than token-ID counts, identifies inserted SEP:
    # literal source text could itself contain a named special token.
    first_b = next((i for i, value in enumerate(sequence_ids) if value == 1), len(ids) - 1)
    boundary = first_b - 1
    if (boundary < 1 or ids[boundary] != 2 or sequence_ids[boundary] is not None
            or segments != [0] * first_b + [1] * (len(ids) - first_b)
            or any(v not in (0, None) for v in sequence_ids[1:boundary])
            or any(v not in (1, None) for v in sequence_ids[first_b:-1])):
        raise ValueError('Exact official CLS/P/SEP/H/SEP template and segment IDs required')


def write_backend(folder, text):
    folder = Path(folder)
    if (folder != folder.resolve() or folder.parent != C.STUDY / 'runs'
            or folder.name not in ('dev', 'confirmation')
            or any(x.is_symlink() for x in [folder, *folder.parents])):
        raise ValueError('Exact owned phase backend-output directory required')
    path = folder / 'tokenizer-backend.json'
    with path.open('x') as f: f.write(text); f.flush(); os.fsync(f.fileno())
    return {'actual_backend_json_path': str(path.relative_to(C.ROOT)),
        'actual_backend_json_bytes': path.stat().st_size, 'actual_backend_json_sha256': C.sha(path)}


class Reader:
    def __init__(self, folder, counters, progress=None, *, plan, output_folder):
        started = time.perf_counter()
        self.counters, self.progress = counters, progress or (lambda: None)
        folder = Path(folder)
        header_path = C.checked(plan['model_header_path'])
        if C.sha(header_path) != plan['model_header_sha256']:
            raise ValueError('Frozen original checkpoint header proof changed')
        counters['checkpoint_metadata_loads_attempted'] += 1; self.progress()
        source = K.inspect(folder / 'model.safetensors', verify_asset=False)
        K.compare_frozen_header(source, C.read(header_path))
        counters['checkpoint_metadata_loads_completed'] += 1
        import torch
        from safetensors import safe_open
        from transformers import DebertaV2ForSequenceClassification, DebertaV2TokenizerFast
        self.torch = torch
        if importlib.metadata.version('torch') != '2.7.1+cpu' or importlib.metadata.version('transformers') != '4.52.4':
            raise ValueError('Exact reviewed CPU/Transformers distribution required')
        torch.set_num_threads(2); torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        architecture = validate_config(C.read(folder / 'config.json'))
        original_tokenizer_text = (folder / 'tokenizer.json').read_text()
        original_tokenizer = json.loads(original_tokenizer_text)
        if (original_tokenizer['model']['type'] != 'Unigram' or len(original_tokenizer['model']['vocab']) != 128000
                or original_tokenizer.get('truncation') !=
                {'direction': 'Right', 'max_length': 512, 'strategy': 'LongestFirst', 'stride': 0}
                or original_tokenizer.get('padding') is not None):
            raise ValueError('Exact original Unigram source and declared truncation configuration required')
        self.high = DebertaV2TokenizerFast.from_pretrained(str(folder), local_files_only=True, trust_remote_code=False)
        self.tokenizer = self.high.backend_tokenizer
        self.tokenizer.no_padding(); self.tokenizer.no_truncation()
        backend_text = self.tokenizer.to_str(); token_state = json.loads(backend_text)
        if (hashlib.sha256(backend_text.encode()).hexdigest() != TOKENIZER_QUALIFIED_SHA
                or len(backend_text.encode()) != TOKENIZER_QUALIFIED_BYTES):
            raise ValueError('Actual stock fast backend differs from the one frozen source-JSON parser qualification')
        pair = self.tokenizer.encode('generic premise', 'generic hypothesis')
        validate_pair(pair.ids, pair.attention_mask, pair.type_ids, pair.sequence_ids)
        if token_state['model']['type'] != 'Unigram' or token_state.get('padding') or token_state.get('truncation'):
            raise ValueError('Operational official Unigram backend must disable padding and truncation')
        backend = write_backend(output_folder, backend_text)
        self.token_receipt = dict(backend,
            backend_sha256=hashlib.sha256(backend_text.encode()).hexdigest(),
            original_tokenizer_json_sha256=hashlib.sha256(original_tokenizer_text.encode()).hexdigest(),
            original_declared_truncation=original_tokenizer['truncation'], original_declared_padding=None,
            original_asset_bytes_unchanged=True, type='DebertaV2TokenizerFast', backend_model='Unigram',
            qualified_source_parser_backend_sha256=TOKENIZER_QUALIFIED_SHA,
            qualified_source_parser_backend_bytes=TOKENIZER_QUALIFIED_BYTES,
            pair_format='[CLS]P[SEP]H[SEP]', cls_id=1, sep_id=2, pad_id=0, unk_id=3, mask_id=128000,
            token_type_policy='Explicit official premise/special0 then hypothesis/finalSEP1 IDs are fed and saved.',
            type_vocab_size=0, learned_segment_embeddings=False, token_type_ids_fed=True,
            padding=False, truncation=False,
            conversion='Exact pinned tokenizer.json loaded by builtin DebertaV2TokenizerFast; no SentencePiece conversion or remote code.')
        counters['model_initializations_attempted'] += 1; self.progress()
        model, loading = DebertaV2ForSequenceClassification.from_pretrained(str(folder), local_files_only=True,
            trust_remote_code=False, use_safetensors=True, weights_only=True, torch_dtype=torch.float32,
            output_loading_info=True, attn_implementation='eager')
        counters['model_initializations_completed'] += 1
        compatibility = K.validate_loading_info(loading)
        model.eval(); self.model = model
        tensors = list(model.named_parameters()) + list(model.named_buffers())
        if any(v.device.type != 'cpu' or (v.is_floating_point() and v.dtype != torch.float32) for _, v in tensors):
            raise ValueError('Every floating model parameter and buffer must compute in FP32 CPU')
        if any('quantized' in type(m).__module__ for m in model.modules()): raise ValueError('No quantization permitted')
        if model.deberta.embeddings.token_type_embeddings is not None:
            raise ValueError('Original type_vocab0 model must have no learned segment embeddings')
        parameter_values = dict(model.named_parameters())
        if sorted(parameter_values) != source['source_parameter_names']:
            raise ValueError('All source floating keys must equal all actual named trained parameters')
        rows = []
        position = None
        with safe_open(str(folder / 'model.safetensors'), framework='pt', device='cpu') as original:
            if sorted(original.keys()) != sorted(source['tensor_metadata']):
                raise ValueError('Safe-open source key set differs from pinned header')
            for name in source['source_parameter_names']:
                old, loaded = original.get_tensor(name), parameter_values[name]
                if old.dtype != torch.float16 or loaded.dtype != torch.float32 or loaded.device.type != 'cpu':
                    raise ValueError('Exact original FP16 to loaded FP32 CPU parameters required')
                equal = torch.equal(old.to(dtype=torch.float32), loaded.detach())
                row = {'name': name, 'source_dtype': 'F16', 'source_shape': list(old.shape),
                    'elements': old.numel(), 'loaded_dtype': str(loaded.dtype), 'loaded_device': loaded.device.type,
                    'equal_after_FP32_conversion': equal}
                rows.append(row)
                if not equal: raise ValueError('Original trained parameter values not loaded exactly: ' + name)
            old_position = original.get_tensor(K.POSITION_KEY)
            actual_position = dict(model.named_buffers()).get(K.POSITION_KEY)
            embeddings = model.deberta.embeddings
            if (old_position.dtype != torch.int64 or list(old_position.shape) != [1, 512]
                    or not torch.equal(old_position, torch.arange(512, dtype=torch.int64).reshape(1, 512))
                    or actual_position is None or not torch.equal(old_position, actual_position)
                    or 'position_ids' not in embeddings._non_persistent_buffers_set):
                raise ValueError('Original nonlearned position buffer must equal exact actual nonpersistent arange512')
            position = {'name': K.POSITION_KEY, 'source_dtype': 'I64', 'source_shape': [1, 512],
                'values_equal_arange512': True, 'equals_actual_buffer': True, 'actual_persistent': False,
                'source_bytes_sha256': source['source_position_buffer']['source_bytes_sha256'],
                'scope': 'Original integer buffer equals the stock registered buffer; no trained parameter exclusion.'}
        verified = K.validate_parameter_rows(rows, source)
        self.state_sha = state_identity(model, torch)
        elements = sum(t.numel() for t in model.parameters())
        head_shapes = {'pooler_dense_weight_shape': list(model.pooler.dense.weight.shape),
            'pooler_dense_bias_shape': list(model.pooler.dense.bias.shape),
            'classifier_weight_shape': list(model.classifier.weight.shape),
            'classifier_bias_shape': list(model.classifier.bias.shape)}
        if (elements != K.FLOAT_ELEMENTS or len(parameter_values) != source['source_parameter_tensor_count']
                or head_shapes != {'pooler_dense_weight_shape': [1024, 1024], 'pooler_dense_bias_shape': [1024],
                                   'classifier_weight_shape': [3, 1024], 'classifier_bias_shape': [3]}):
            raise ValueError('Exact complete original trained pooler/classifier inventory required')
        self.state = dict(head_shapes, parameter_count=elements, parameter_tensor_count=len(parameter_values),
            parameter_dtype_element_counts=dtype_inventory(model.named_parameters()),
            buffer_dtype_element_counts=dtype_inventory(model.named_buffers()),
            all_floating_parameters_buffers_FP32=True, devices=['cpu'], eval=not model.training,
            state_sha256=self.state_sha, model_instance_token=hex(id(model)), quantized_modules=0,
            threads=torch.get_num_threads(), interop_threads=torch.get_num_interop_threads(),
            deterministic_algorithms=torch.are_deterministic_algorithms_enabled())
        self.receipt = {'repo': C.MODEL, 'revision': C.REVISION,
            'raw_id2label': {'0': 'Entailment', '1': 'NotMentioned', '2': 'Contradiction'},
            'canonical_order': list(C.ORDER), 'canonical_permutation': [0, 2, 1],
            'precision': 'ORIGINAL_FP16_STORAGE_EXPLICIT_FP32_CPU_INFERENCE_NO_QUANTIZATION',
            'architecture': architecture, 'load_flags': {'local_files_only': True, 'trust_remote_code': False,
                'weights_only': True, 'use_safetensors': True, 'torch_dtype': 'torch.float32',
                'output_loading_info': True, 'attn_implementation': 'eager'},
            'actual_attention_implementation': model.config._attn_implementation, 'loading_info': loading,
            'loading_compatibility': compatibility, 'parameter_loading_verification': verified,
            'position_buffer': position, 'source_checkpoint_header_path': plan['model_header_path'],
            'source_checkpoint_header_sha256': plan['model_header_sha256'],
            'source_checkpoint_raw_header_sha256': source['header_sha256'],
            'source_checkpoint_dtype_elements': {'torch.float16': K.FLOAT_ELEMENTS, 'torch.int64': 512},
            'source_checkpoint_tensors': source['source_tensor_count'],
            'source_checkpoint_elements': K.FLOAT_ELEMENTS + 512,
            'source_floating_parameter_elements': K.FLOAT_ELEMENTS, 'source_nonlearned_integer_elements': 512,
            'source_checkpoint_metadata_inspection': 'Stdlib safetensors header JSON and original I64 bytes; no unpickling.',
            'source_parameter_access': 'safetensors.safe_open(framework=pt,device=cpu), exact F16-to-F32 values compared for every named parameter.',
            'initialization_model_forwards': 0,
            'quantization_initializations': 0, 'pair_token_cap': 512, 'batch_size': 1, 'temperature': 1.0,
            'tokenizer': self.token_receipt, 'state_sha256': self.state_sha,
            'state_hash_recipe': 'Sorted named parameters then buffers; canonical JSON name/dtype/shape LF, contiguous tensor uint8 bytes LF',
            'initialization_wall_seconds': time.perf_counter() - started,
            'versions': {k: importlib.metadata.version(k) for k in ('torch', 'transformers', 'tokenizers', 'numpy', 'safetensors', 'sentencepiece')},
            'declared_training': ['MultiNLI', 'FEVER-NLI', 'ANLI-R1', 'ANLI-R2', 'ANLI-R3', 'LingNLI', 'WANLI'],
            'known_ContractNLI_supervision': False, 'full_training_lineage_verified': False,
            'record_level_pretraining_overlap_verified': False, 'legal_competence_established': False}

    def backend_identity(self):
        return hashlib.sha256(self.tokenizer.to_str().encode()).hexdigest()

    def forward(self, premise, hypothesis):
        start = time.perf_counter(); encoded = self.tokenizer.encode(premise, hypothesis)
        validate_pair(encoded.ids, encoded.attention_mask, encoded.type_ids, encoded.sequence_ids)
        values = {'input_ids': [encoded.ids], 'attention_mask': [encoded.attention_mask],
                  'token_type_ids': [encoded.type_ids]}
        high = self.high(premise, hypothesis, truncation=False, padding=False, return_attention_mask=True,
                         return_token_type_ids=True)
        if any(high.get(k) != values[k][0] for k in values):
            raise ValueError('Exact operational backend feeds must equal whole official high-level pair feeds')
        feed = {key: self.torch.tensor(value, dtype=self.torch.long) for key, value in values.items()}
        self.counters['nli_forward_pairs_attempted'] += 1; self.progress()
        with self.torch.inference_mode(), self.torch.autocast('cpu', enabled=False):
            y = self.model(**feed).logits
        if list(y.shape) != [1, 3] or y.dtype != self.torch.float32: raise ValueError('Three original FP32 singleton logits required')
        logits = [float(x) for x in y.detach().cpu()[0].tolist()]
        raw, typed = C.distribution(logits)
        self.counters['nli_forward_pairs_completed'] += 1
        binary = {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}
        return {'premise': premise, 'hypothesis': hypothesis,
            'input_text_sha256': hashlib.sha256(C.canonical([premise, hypothesis]).encode()).hexdigest(),
            'raw_logits': logits, 'raw_probabilities': raw, 'typed_probabilities': typed,
            'typed_prediction': C.prediction(typed), 'binary_probabilities': binary,
            'binary_prediction': 'Yes' if binary['Yes'] >= .5 else 'No', 'feed': values,
            'feed_sha256': hashlib.sha256(C.canonical(values).encode()).hexdigest(),
            'actual_tokens': len(encoded.ids), 'elapsed_seconds': time.perf_counter() - start,
            'model_state_sha256': self.state_sha, 'model_instance_token': hex(id(self.model)),
            'padding': False, 'truncation': False, 'inference_mode': True, 'cpu_autocast': False,
            'feed_dtype': 'torch.int64', 'feed_device': 'cpu', 'raw_logit_dtype': 'torch.float32',
            'original_high_level_feed_equal': True}

