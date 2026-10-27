"""One exact local contract-domain BERT three-way reader; no initialization at import."""
import gc
import hashlib
import importlib.metadata
import json
import math
from collections import Counter
from pathlib import Path
import time

LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
RAW_TO_TYPED = (0, 1, 2)
MODEL_ID = 'Agreemind/contractnli-bert-nda-standard'
MODEL_REVISION = 'ac92b6b512d7a4bad7abe356750c3b916fe18649'
WEIGHT_SHA = 'cd4f4391ab75c22e986ecea64831af47f6008a37ddce6a56a4cb5496e41ead07'
MODEL_FILES = {'README.md', 'config.json', 'model.safetensors', 'tokenizer.json',
               'special_tokens_map.json', 'tokenizer_config.json', 'vocab.txt'}


def require(value, code):
    if not value:
        raise ValueError(code)


def validate_encoding(value, pair):
    """Check original tokenizer fields; do not synthesize or rewrite any token IDs."""
    require(type(value) is dict and set(value) == {'input_ids', 'attention_mask', 'token_type_ids'}
            and type(value['input_ids']) is list and value['input_ids']
            and type(value['attention_mask']) is list
            and type(value['token_type_ids']) is list
            and len(value['attention_mask']) == len(value['input_ids'])
            and all(type(i) is int and 0 <= i < 30522 for i in value['input_ids'])
            and all(type(x) is int and x == 1 for x in value['attention_mask'])
            and len(value['token_type_ids']) == len(value['input_ids'])
            and all(type(x) is int and x in (0, 1) for x in value['token_type_ids'])
            and (set(value['token_type_ids']) == {0, 1} if pair
                 else set(value['token_type_ids']) == {0}),
            'TOKENIZER_WHOLE_PAIR_CAPTURE' if pair else 'TOKENIZER_CAPACITY_SINGLE_CAPTURE')
    ids = value['input_ids']; types = value['token_type_ids']
    require(ids[0] == 101 and ids[-1] == 102,
            'PINNED_BERT_SPECIAL_TOKEN_BOUNDARIES')
    if pair:
        at = types.index(1)
        require(at >= 3 and ids[at - 1] == 102
                and types == [0] * at + [1] * (len(types) - at)
                and len(types) - at >= 2, 'PINNED_BERT_GENUINE_SOURCE_PAIR_SEGMENTS')
    return value


def strict_state(state, expected, torch):
    """All201 learned FP32 CPU tensors must exactly match; bounded finite temporaries."""
    from guards import FINITE_CHUNK_ELEMENTS
    require(hasattr(state, 'keys') and all(type(k) is str for k in state), 'STATE_MAPPING')
    require(len(state) == len(expected) == 201 and set(state) == set(expected),
            'ALL_201_LEARNED_STATE_KEYS_EXACT')
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
    for name, shape in [('bert.pooler.dense.weight', (768, 768)),
                        ('bert.pooler.dense.bias', (768,)),
                        ('classifier.weight', (3, 768)),
                        ('classifier.bias', (3,))]:
        require(name in state and tuple(state[name].shape) == shape, 'ORIGINAL_POOLER_AND_CLASSIFIER_REQUIRED')
    require(elements == 109484547, 'ORIGINAL_ALL_TENSOR_ELEMENT_COUNT')
    return state, {'learned_state_keys_exact': True, 'learned_state_tensor_count': len(state),
                   'source_tensor_dtype_counts': dict(dtypes), 'source_tensor_elements': elements,
                   'finite_validation_chunks': chunks, 'finite_chunk_element_cap': FINITE_CHUNK_ELEMENTS,
                   'removed_learned_or_nonlearned_state_keys': [],
                   'missing_keys': [], 'unexpected_keys': [], 'mismatched_keys': []}


def construct_meta_model(config, torch, classifier_type):
    with torch.device('meta'):
        model = classifier_type(config)
    require(model.bert.pooler is not None, 'ORIGINAL_BERT_POOLER_REQUIRED')
    require(len(model.state_dict()) == 201 and all(p.is_meta for p in model.parameters()),
            'ALL_201_PARAMETERS_CONSTRUCTED_ON_META')
    return model


def materialize_nonpersistent_buffers(model, torch):
    embeddings = model.bert.embeddings
    expected = {'position_ids': torch.arange(512, dtype=torch.int64, device='cpu').expand((1, -1)),
                'token_type_ids': torch.zeros((1, 512), dtype=torch.int64, device='cpu')}
    for name, value in expected.items():
        require(name in embeddings._non_persistent_buffers_set
                and name in embeddings._buffers, 'EXPECTED_NONPERSISTENT_EMBEDDING_BUFFER')
        embeddings.register_buffer(name, value, persistent=False)
        actual = embeddings._buffers[name]
        require(actual.device.type == 'cpu' and not actual.is_meta and actual.dtype == torch.int64
                and tuple(actual.shape) == (1, 512) and torch.equal(actual, value),
                'EXACT_CPU_NONPERSISTENT_BUFFER')
    require(all(not b.is_meta for b in model.buffers()), 'NO_META_BUFFERS_REMAIN')
    return {'position_ids': {'shape': [1, 512], 'dtype': 'int64', 'device': 'cpu',
                             'values': 'Exact arange(512), expanded to (1,512)', 'persistent': False},
            'token_type_ids': {'shape': [1, 512], 'dtype': 'int64', 'device': 'cpu',
                               'values': 'Exact all zeros', 'persistent': False}}


def assert_assigned_storage(model, source, torch):
    current = model.state_dict()
    require(len(current) == 201 and set(current) == set(source), 'POST_ASSIGN_ALL_201_KEYS')
    require(all(value.dtype == torch.float32 and value.device.type == 'cpu' and not value.is_meta
                and value.data_ptr() == source[key].data_ptr()
                for key, value in current.items()), 'ASSIGN_MUST_SHARE_EVERY_ORIGINAL_TENSOR_STORAGE')
    require(all(not p.is_meta for p in model.parameters()), 'NO_META_PARAMETERS_REMAIN')
    return {'all_201_state_tensor_data_pointers_match_mmap_source': True,
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
    winner = max(range(3), key=lambda i: logits[i])
    return {'logits': logits, 'log_probabilities': log_probs, 'probabilities': probs,
            'prediction': LABELS[winner]}


class Reader:
    def __init__(self, plan, counters, progress, check_deadline, verify_file, network_stage):
        started = time.monotonic(); self.counters = counters; self.progress = progress
        self.check_deadline = check_deadline; self.model = None; self.tokenizer = None
        self.tokenization_stage = 'fragmentation'
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
        weight = next(x for x in assets if x['file'] == 'model.safetensors')
        require(weight['sha256'] == WEIGHT_SHA and weight['bytes'] == 437961724,
                'ORIGINAL_MODEL_WEIGHT_IDENTITY')
        config = json.loads((folder / 'config.json').read_bytes())
        expected = {'model_type': 'bert', 'hidden_size': 768, 'num_hidden_layers': 12,
                    'num_attention_heads': 12, 'max_position_embeddings': 512,
                    'vocab_size': 30522, 'type_vocab_size': 2}
        require(all(config.get(k) == v for k, v in expected.items())
                and config['architectures'] == ['BertForSequenceClassification']
                and config['id2label'] == {'0': 'Entailment', '1': 'Contradiction', '2': 'NotMentioned'}
                and config['label2id'] == {'Entailment': 0, 'Contradiction': 1, 'NotMentioned': 2},
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
            from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast
            from safetensors.torch import load_file
        finally:
            network_stage('reader_initialization')
        self.torch = torch
        torch.set_num_threads(2); torch.set_num_interop_threads(1)
        require(torch.get_num_threads() == 2 and torch.get_num_interop_threads() == 1,
                'READER_TWO_COMPUTE_THREADS')
        counters['reader_initializations_attempted'] += 1; progress('READER_INITIALIZE_BEFORE')
        cfg = BertConfig.from_dict(config)
        require(cfg._name_or_path == config.get('_name_or_path', ''), 'SOURCE_CONFIG_REVISION_PRESERVED')
        snapshot('READER_BEFORE_META_CONSTRUCTOR', True)
        self.model = construct_meta_model(cfg, torch, BertForSequenceClassification)
        snapshot('READER_AFTER_META_CONSTRUCTOR')
        snapshot('READER_BEFORE_MMAP_LOAD', True)
        state = load_file(str(folder / 'model.safetensors'), device='cpu')
        snapshot('READER_AFTER_MMAP_LOAD')
        state, audit = strict_state(state, self.model.state_dict(), torch)
        progress('READER_ALL_201_FINITE_VALIDATED')
        loaded = self.model.load_state_dict(state, strict=True, assign=True)
        require(not loaded.missing_keys and not loaded.unexpected_keys, 'STRICT_STATE_ASSIGN_RESULT')
        audit.update(assert_assigned_storage(self.model, state, torch))
        audit['nonpersistent_buffers'] = materialize_nonpersistent_buffers(self.model, torch)
        del state; gc.collect()
        self.model.eval()
        require(not self.model.training and all(p.dtype == torch.float32 and p.device.type == 'cpu'
                                                for p in self.model.parameters()), 'FP32_CPU_EVAL_MODEL')
        snapshot('READER_AFTER_STRICT_ASSIGN_AND_BUFFERS')
        self.tokenizer = BertTokenizerFast.from_pretrained(str(folder), local_files_only=True)
        require(self.tokenizer.vocab_size == 30522, 'TOKENIZER_VOCABULARY')
        counters['reader_initializations_completed'] += 1
        self.audit = {**audit, 'model_id': MODEL_ID, 'model_revision': MODEL_REVISION, 'model_weight_sha256': WEIGHT_SHA,
                      'weights_only': True, 'weights_format': 'safetensors', 'safetensors_cpu_mapped': True,
                      'mmap': True, 'assign': True, 'meta_constructor': True,
                      'source_revision': MODEL_REVISION, 'source_configuration_unchanged': True,
                      'memory_snapshots': self.memory_audit, 'unsafe_load_fallback': False, 'custom_remote_code': False,
                      'raw_head_order': list(LABELS), 'pair_order': 'hypothesis_then_premise',
                      'bert_token_type_ids_retained': True,
                      'capacity_encoding_is_scalar_only': True,
                      'genuine_nonempty_pair_required_for_every_model_packet': True,
                      'pair_fields_revalidated_at_every_forward_boundary': True,
                      'fragment_catalog_uses_original_genuine_pairs_all_frozen_claims': True,
                      'fragment_pair_tokenization_cap': 12000,
                      'packing_pair_tokenization_cap': 24000,
                      'global_pair_tokenization_cap': 36000,
                      'canonical_typed_order': list(LABELS), 'raw_to_typed_indices': list(RAW_TO_TYPED),
                      'FP32_CPU_eval': True, 'torch_threads': torch.get_num_threads(),
                      'torch_interop_threads': torch.get_num_interop_threads(),
                      'initialization_seconds': time.monotonic() - started}
        progress('READER_INITIALIZE_COMPLETE'); check_deadline()

    def hypothesis_pair_capacity(self, claim):
        """Return a scalar only: hypothesis single length plus BERT's one extra pair SEP.

        This is a lower bound for a nonempty source pair, never an inference packet.
        The pinned original tokenizer's single template is CLS A SEP and its pair
        template is CLS A SEP B SEP. All actual source proposals are separately
        encoded as genuine nonempty pairs and checked against the exact512 cap.
        """
        require(type(claim) is str and bool(claim.strip()), 'CAPACITY_NONEMPTY_WHOLE_CLAIM')
        self.check_deadline(); self.counters['reader_capacity_tokenizations'] += 1
        value = dict(self.tokenizer(claim, add_special_tokens=True, truncation=False,
                                    padding=False, return_attention_mask=True,
                                    return_token_type_ids=True))
        validate_encoding(value, pair=False)
        # Exact original BERT templates, verified from immutable tokenizer metadata.
        require(self.tokenizer.num_special_tokens_to_add(pair=False) == 2
                and self.tokenizer.num_special_tokens_to_add(pair=True) == 3,
                'PINNED_BERT_SINGLE_PAIR_SPECIAL_TOKEN_COUNTS')
        return len(value['input_ids']) + 1

    def set_tokenization_stage(self, stage):
        require(stage in ('fragmentation', 'packing'), 'FROZEN_TOKENIZATION_STAGE')
        self.tokenization_stage = stage

    def tokenize(self, premise, claim):
        require(type(premise) is str and bool(premise.strip())
                and type(claim) is str and bool(claim.strip()),
                'GENUINE_NONEMPTY_HYPOTHESIS_SOURCE_PAIR_REQUIRED')
        self.check_deadline()
        stage = getattr(self, 'tokenization_stage', 'packing')
        require(stage in ('fragmentation', 'packing'), 'FROZEN_TOKENIZATION_STAGE')
        key = 'reader_' + stage + '_pair_tokenizations'
        stage_cap = 12000 if stage == 'fragmentation' else 24000
        require(self.counters.get(key, 0) < stage_cap, 'FROZEN_STAGE_PAIR_TOKENIZATION_CAP')
        require(self.counters['reader_pair_tokenizations'] < 36000, 'FROZEN_GLOBAL_PAIR_TOKENIZATION_CAP')
        self.counters[key] = self.counters.get(key, 0) + 1
        self.counters['reader_pair_tokenizations'] += 1
        value = self.tokenizer(claim, premise, add_special_tokens=True, truncation=False,
                               padding=False, return_attention_mask=True,
                               return_token_type_ids=True)
        result = validate_encoding(dict(value), pair=True)
        self.counters[key + '_completed'] = self.counters.get(key + '_completed', 0) + 1
        self.counters['reader_pair_tokenizations_completed'] = self.counters.get('reader_pair_tokenizations_completed', 0) + 1
        return result

    def score(self, tokens):
        self.check_deadline()
        # Recheck at the physical forward boundary: capacity scalars, single packets,
        # missing/fabricated fields or invalid segments never reach model construction.
        validate_encoding(tokens, pair=True)
        self.counters['reader_forward_pair_validations'] += 1
        require(0 < len(tokens['input_ids']) <= 512, 'MODEL_PAIR_TOKEN_CAP')
        torch = self.torch
        feed = {k: torch.tensor([v], dtype=torch.int64, device='cpu') for k, v in tokens.items()}
        require(self.counters['NLI_forwards_attempted'] < 324, 'PHYSICAL_FORWARD_CAP_324')
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
