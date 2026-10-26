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
MODEL_REVISION = '5b605abab9b75bc87ab66cfc049ef58d9d64b8ed'
WEIGHT_SHA = 'a51c55cb7dc41c4c862f06a3d9c413a8aa0619222bc56f06cb6f2f5b2d3ee14a'
MODEL_FILES = {'README.md', 'config.json', 'merges.txt', 'pytorch_model.bin',
               'special_tokens_map.json', 'tokenizer_config.json', 'vocab.json'}


def require(value, code):
    if not value:
        raise ValueError(code)


def strict_state(state, expected, torch):
    """Validate all keys/shapes before any load; only one historical exact buffer allowed."""
    require(hasattr(state, 'keys') and all(type(k) is str for k in state), 'STATE_MAPPING')
    state = dict(state); removed = []
    legacy = 'roberta.embeddings.position_ids'
    if legacy in state and legacy not in expected:
        value = state[legacy]
        require(isinstance(value, torch.Tensor) and value.dtype == torch.int64
                and tuple(value.shape) == (1, 514)
                and torch.equal(value, torch.arange(514, dtype=torch.int64).unsqueeze(0)),
                'LEGACY_POSITION_BUFFER_NOT_EXACT')
        del state[legacy]; removed.append(legacy)
    require(set(state) == set(expected), 'LEARNED_STATE_KEYS_MISSING_OR_UNEXPECTED')
    dtypes = Counter()
    for key, target in expected.items():
        value = state[key]
        require(isinstance(value, torch.Tensor) and tuple(value.shape) == tuple(target.shape),
                'LEARNED_STATE_SHAPE_MISMATCH')
        require(value.is_floating_point() and bool(torch.isfinite(value).all()),
                'LEARNED_STATE_NONFLOAT_OR_NONFINITE')
        dtypes[str(value.dtype)] += 1
    for name, shape in [('classifier.dense.weight', (1024, 1024)),
                        ('classifier.dense.bias', (1024,)),
                        ('classifier.out_proj.weight', (3, 1024)),
                        ('classifier.out_proj.bias', (3,))]:
        require(name in state and tuple(state[name].shape) == shape, 'LEARNED_CLASSIFIER_REQUIRED')
    return state, {'learned_state_keys_exact': True, 'learned_state_tensor_count': len(state),
                   'source_tensor_dtype_counts': dict(dtypes),
                   'removed_validated_nonlearned_legacy_buffers': removed,
                   'missing_keys': [], 'unexpected_keys': [], 'mismatched_keys': []}


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
    def __init__(self, plan, counters, progress, check_deadline, verify_file):
        started = time.monotonic(); self.counters = counters; self.progress = progress
        self.check_deadline = check_deadline; self.model = None; self.tokenizer = None
        folder = Path(plan['model_directory'])
        require(folder.is_absolute() and not folder.is_symlink(), 'MODEL_DIRECTORY')
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
        import torch
        from transformers import RobertaConfig, RobertaForSequenceClassification, RobertaTokenizerFast
        self.torch = torch
        torch.set_num_threads(2); torch.set_num_interop_threads(1)
        require(torch.get_num_threads() == 2 and torch.get_num_interop_threads() == 1,
                'READER_TWO_COMPUTE_THREADS')
        counters['reader_initializations_attempted'] += 1; progress('READER_INITIALIZE_BEFORE')
        cfg = RobertaConfig.from_dict(config)
        self.model = RobertaForSequenceClassification(cfg).float().cpu()
        state = torch.load(folder / 'pytorch_model.bin', map_location='cpu', weights_only=True, mmap=False)
        state, audit = strict_state(state, self.model.state_dict(), torch)
        loaded = self.model.load_state_dict(state, strict=True)
        require(not loaded.missing_keys and not loaded.unexpected_keys, 'STRICT_STATE_COPY_RESULT')
        del state; gc.collect()
        self.model.eval()
        require(not self.model.training and all(p.dtype == torch.float32 and p.device.type == 'cpu'
                                                for p in self.model.parameters()), 'FP32_CPU_EVAL_MODEL')
        self.tokenizer = RobertaTokenizerFast.from_pretrained(str(folder), local_files_only=True)
        require(self.tokenizer.vocab_size == 50265, 'TOKENIZER_VOCABULARY')
        counters['reader_initializations_completed'] += 1
        self.audit = {**audit, 'model_revision': MODEL_REVISION, 'model_weight_sha256': WEIGHT_SHA,
                      'weights_only': True, 'unsafe_load_fallback': False, 'custom_remote_code': False,
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
