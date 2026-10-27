"""One local original learned RoBERTa NLI reader; no initialization at import."""
import gc
import hashlib
import importlib.metadata
import json
import math
from collections import Counter
from pathlib import Path
import time

LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
RAW_TO_TYPED = (0, 2, 1)
MODEL_ID = 'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli'
MODEL_REVISION = '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed'
WEIGHT_SHA = 'a51c55cb7dc41c4c862f06a3d9c413a8aa0619222bc56f06cb6f2f5b2d3ee14a'
MODEL_FILES = {'README.md', 'config.json', 'merges.txt', 'pytorch_model.bin',
               'special_tokens_map.json', 'tokenizer_config.json', 'vocab.json'}


def require(value, code):
    if not value:
        raise ValueError(code)


def strict_state(state, expected, torch):
    """All395 learned FP32 CPU tensors must exactly match; bounded finite temporaries."""
    from guards import FINITE_CHUNK_ELEMENTS
    require(hasattr(state, 'keys') and all(type(k) is str for k in state), 'STATE_MAPPING')
    require(len(state) == len(expected) == 395 and set(state) == set(expected),
            'ALL_395_LEARNED_STATE_KEYS_EXACT')
    dtypes = Counter(); elements = 0; chunks = 0
    for key, target in expected.items():
        value = state[key]
        require(isinstance(value, torch.Tensor) and tuple(value.shape) == tuple(target.shape),
                'LEARNED_STATE_SHAPE_MISMATCH')
        require(value.dtype == torch.float32 and value.device.type == 'cpu'
                and not value.is_meta and value.is_contiguous(), 'LEARNED_STATE_FP32_CPU_CONTIGUOUS')
        flat = value.view(-1)
        for offset in range(0, flat.numel(), FINITE_CHUNK_ELEMENTS):
            require(bool(torch.isfinite(flat[offset:offset + FINITE_CHUNK_ELEMENTS]).all()),
                    'LEARNED_STATE_NONFINITE')
            chunks += 1
        elements += value.numel(); dtypes[str(value.dtype)] += 1
    for name, shape in [('roberta.pooler.dense.weight', (1024, 1024)),
                        ('roberta.pooler.dense.bias', (1024,)),
                        ('classifier.dense.weight', (1024, 1024)),
                        ('classifier.dense.bias', (1024,)),
                        ('classifier.out_proj.weight', (3, 1024)),
                        ('classifier.out_proj.bias', (3,))]:
        require(name in state and tuple(state[name].shape) == shape, 'ORIGINAL_POOLER_AND_CLASSIFIER_REQUIRED')
    require(elements == 356412419, 'ORIGINAL_ALL_TENSOR_ELEMENT_COUNT')
    return state, {'learned_state_keys_exact': True, 'learned_state_tensor_count': len(state),
                   'source_tensor_dtype_counts': dict(dtypes), 'source_tensor_elements': elements,
                   'finite_validation_chunks': chunks, 'finite_chunk_element_cap': FINITE_CHUNK_ELEMENTS,
                   'removed_learned_or_nonlearned_state_keys': [],
                   'missing_keys': [], 'unexpected_keys': [], 'mismatched_keys': []}


def construct_meta_model(config, torch, classifier_type, pooler_type):
    with torch.device('meta'):
        model = classifier_type(config)
        require(model.roberta.pooler is None, 'MODERN_CLASSIFIER_POOLER_EXPECTED_NONE')
        model.roberta.pooler = pooler_type(config)
    require(len(model.state_dict()) == 395 and all(p.is_meta for p in model.parameters()),
            'ALL_395_PARAMETERS_CONSTRUCTED_ON_META')
    return model


def materialize_nonpersistent_buffers(model, torch):
    embeddings = model.roberta.embeddings
    expected = {'position_ids': torch.arange(514, dtype=torch.int64, device='cpu').expand((1, -1)),
                'token_type_ids': torch.zeros((1, 514), dtype=torch.int64, device='cpu')}
    for name, value in expected.items():
        require(name in embeddings._non_persistent_buffers_set
                and name in embeddings._buffers, 'EXPECTED_NONPERSISTENT_EMBEDDING_BUFFER')
        embeddings.register_buffer(name, value, persistent=False)
        actual = embeddings._buffers[name]
        require(actual.device.type == 'cpu' and not actual.is_meta and actual.dtype == torch.int64
                and tuple(actual.shape) == (1, 514) and torch.equal(actual, value),
                'EXACT_CPU_NONPERSISTENT_BUFFER')
    require(all(not b.is_meta for b in model.buffers()), 'NO_META_BUFFERS_REMAIN')
    return {'position_ids': {'shape': [1, 514], 'dtype': 'int64', 'device': 'cpu',
                             'values': 'Exact arange(514), expanded to (1,514)', 'persistent': False},
            'token_type_ids': {'shape': [1, 514], 'dtype': 'int64', 'device': 'cpu',
                               'values': 'Exact all zeros', 'persistent': False}}


def assert_assigned_storage(model, source, torch):
    current = model.state_dict()
    require(len(current) == 395 and set(current) == set(source), 'POST_ASSIGN_ALL_395_KEYS')
    require(all(value.dtype == torch.float32 and value.device.type == 'cpu' and not value.is_meta
                and value.data_ptr() == source[key].data_ptr()
                for key, value in current.items()), 'ASSIGN_MUST_SHARE_EVERY_ORIGINAL_TENSOR_STORAGE')
    require(all(not p.is_meta for p in model.parameters()), 'NO_META_PARAMETERS_REMAIN')
    return {'all_395_state_tensor_data_pointers_match_mmap_source': True,
            'all_original_learned_pooler_and_classifier_tensors_retained': True}


def stable_scores(raw_logits):
    require(len(raw_logits) == 3 and all(type(v) is float and math.isfinite(v)
                                       for v in raw_logits), 'FINITE_THREE_CLASS_LOGITS')
    logits = [raw_logits[i] for i in RAW_TO_TYPED]
    maximum = max(logits)
    normalizer = maximum + math.log(math.fsum(math.exp(v - maximum) for v in logits))
    log_probs = [v - normalizer for v in logits]
    probs = [math.exp(v) for v in log_probs]
    require(all(math.isfinite(v) for v in log_probs) and abs(math.fsum(probs) - 1) <= 1e-12,
            'STABLE_SOFTMAX_CHECK')
    winner = max(range(3), key=lambda i: probs[i])
    return {'logits': logits, 'log_probabilities': log_probs, 'probabilities': probs,
            'prediction': LABELS[winner]}


class Reader:
    def __init__(self, plan, counters, progress, check_deadline, verify_file, network_stage):
        started = time.monotonic(); self.counters = counters; self.progress = progress
        self.check_deadline = check_deadline; self.model = None; self.tokenizer = None
        from guards import memory_snapshot, require_headroom
        self.memory_audit = []
        def snapshot(stage, enforce=False):
            value = memory_snapshot(); self.memory_audit.append({'stage': stage, **value})
            progress(stage)
            if enforce: require_headroom(value)
            check_deadline()
        snapshot('READER_BEFORE_LARGE_ASSET_HASH', True)
        folder = Path(plan['model_directory'])
        require(folder.is_absolute() and not folder.is_symlink(), 'MODEL_DIRECTORY')
        require(plan['model_id'] == MODEL_ID and plan['model_revision'] == MODEL_REVISION,
                'EXACT_MODEL_REPOSITORY_AND_REVISION')
        assets = plan['model_assets']
        require({x['file'] for x in assets} == MODEL_FILES and len(assets) == 7,
                'EXACT_SEVEN_ORIGINAL_MODEL_ASSETS')
        for item in assets:
            require(Path(item['path']) == folder / item['file'], 'MODEL_ASSET_LOCATION')
            verify_file(item)
        weight = next(x for x in assets if x['file'] == 'pytorch_model.bin')
        require(weight['sha256'] == WEIGHT_SHA and weight['bytes'] == 1425814813,
                'ORIGINAL_MODEL_WEIGHT_IDENTITY')
        config = json.loads((folder / 'config.json').read_bytes())
        expected = {'model_type': 'roberta', 'hidden_size': 1024, 'num_hidden_layers': 24,
                    'num_attention_heads': 16, 'max_position_embeddings': 514,
                    'vocab_size': 50265, 'type_vocab_size': 1}
        require(all(config.get(k) == v for k, v in expected.items())
                and config['architectures'] == ['RobertaForSequenceClassification']
                and config['id2label'] == {'0': 'entailment', '1': 'neutral', '2': 'contradiction'},
                'EXACT_NATIVE_LEARNED_HEAD_CONFIGURATION')
        for name, version in plan['runtime_versions'].items():
            require(importlib.metadata.version(name) == version, 'RUNTIME_DISTRIBUTION_VERSION')
        check_deadline(); progress('READER_IMPORT_BEFORE')
        network_stage('reader_torch_import')
        try:
            import torch
        finally:
            network_stage('reader_initialization')
        network_stage('reader_transformers_import')
        try:
            from transformers import RobertaConfig, RobertaForSequenceClassification, RobertaTokenizerFast
            from transformers.models.roberta.modeling_roberta import RobertaPooler
        finally:
            network_stage('reader_initialization')
        self.torch = torch
        torch.set_num_threads(2); torch.set_num_interop_threads(1)
        require(torch.get_num_threads() == 2 and torch.get_num_interop_threads() == 1,
                'READER_TWO_COMPUTE_THREADS')
        counters['reader_initializations_attempted'] += 1; progress('READER_INITIALIZE_BEFORE')
        cfg = RobertaConfig.from_dict(config)
        require(cfg._name_or_path == config.get('_name_or_path', ''), 'SOURCE_CONFIG_REVISION_PRESERVED')
        snapshot('READER_BEFORE_META_CONSTRUCTOR', True)
        self.model = construct_meta_model(cfg, torch, RobertaForSequenceClassification, RobertaPooler)
        snapshot('READER_AFTER_META_CONSTRUCTOR')
        snapshot('READER_BEFORE_MMAP_LOAD', True)
        state = torch.load(folder / 'pytorch_model.bin', map_location='cpu', weights_only=True, mmap=True)
        snapshot('READER_AFTER_MMAP_LOAD')
        state, audit = strict_state(state, self.model.state_dict(), torch)
        progress('READER_ALL_395_FINITE_VALIDATED')
        loaded = self.model.load_state_dict(state, strict=True, assign=True)
        require(not loaded.missing_keys and not loaded.unexpected_keys, 'STRICT_STATE_ASSIGN_RESULT')
        audit.update(assert_assigned_storage(self.model, state, torch))
        audit['nonpersistent_buffers'] = materialize_nonpersistent_buffers(self.model, torch)
        del state; gc.collect()
        self.model.eval()
        require(not self.model.training and all(p.dtype == torch.float32 and p.device.type == 'cpu'
                                                for p in self.model.parameters()), 'FP32_CPU_EVAL_MODEL')
        snapshot('READER_AFTER_STRICT_ASSIGN_AND_BUFFERS')
        self.tokenizer = RobertaTokenizerFast.from_pretrained(str(folder), local_files_only=True)
        require(self.tokenizer.vocab_size == 50265, 'TOKENIZER_VOCABULARY')
        counters['reader_initializations_completed'] += 1
        self.audit = {**audit, 'model_id': MODEL_ID, 'model_revision': MODEL_REVISION, 'model_weight_sha256': WEIGHT_SHA,
                      'weights_only': True, 'mmap': True, 'assign': True, 'meta_constructor': True,
                      'source_revision': MODEL_REVISION, 'source_configuration_unchanged': True,
                      'memory_snapshots': self.memory_audit, 'unsafe_load_fallback': False, 'custom_remote_code': False,
                      'raw_head_order': ['Entailment', 'Neutral', 'Contradiction'],
                      'canonical_typed_order': list(LABELS), 'raw_to_typed_indices': list(RAW_TO_TYPED),
                      'FP32_CPU_eval': True, 'torch_threads': torch.get_num_threads(),
                      'torch_interop_threads': torch.get_num_interop_threads(),
                      'initialization_seconds': time.monotonic() - started}
        progress('READER_INITIALIZE_COMPLETE'); check_deadline()

    def tokenize(self, premise, claim):
        self.check_deadline(); self.counters['reader_pair_tokenizations'] += 1
        value = self.tokenizer(premise, claim, add_special_tokens=True, truncation=False,
                               padding=False, return_attention_mask=True,
                               return_token_type_ids=False)
        require(set(value) == {'input_ids', 'attention_mask'}
                and type(value['input_ids']) is list and value['input_ids']
                and len(value['attention_mask']) == len(value['input_ids'])
                and all(type(i) is int and 0 <= i < 50265 for i in value['input_ids'])
                and all(x == 1 for x in value['attention_mask']), 'TOKENIZER_WHOLE_PAIR_CAPTURE')
        return dict(value)

    def score(self, tokens):
        self.check_deadline()
        require(0 < len(tokens['input_ids']) <= 512, 'MODEL_PAIR_TOKEN_CAP')
        torch = self.torch
        feed = {k: torch.tensor([v], dtype=torch.int64, device='cpu') for k, v in tokens.items()}
        self.counters['NLI_forwards_attempted'] += 1; self.progress('NLI_FORWARD_BEFORE')
        started = time.monotonic()
        with torch.inference_mode():
            output = self.model(**feed).logits
        require(tuple(output.shape) == (1, 3) and output.dtype == torch.float32
                and bool(torch.isfinite(output).all()), 'ACTUAL_FP32_THREE_CLASS_OUTPUT')
        raw = [float(x) for x in output[0].detach().to(torch.float64).cpu().tolist()]
        self.counters['NLI_forwards_completed'] += 1; self.progress('NLI_FORWARD_COMPLETE')
        value = stable_scores(raw); value['forward_seconds'] = time.monotonic() - started
        self.check_deadline(); return value

    def close(self):
        self.model = None; self.tokenizer = None; gc.collect()
        return {'reader_inprocess_references_released': True,
                'scope': 'Owned worker physical termination and descendant closure are verified by outer dispatch.'}
