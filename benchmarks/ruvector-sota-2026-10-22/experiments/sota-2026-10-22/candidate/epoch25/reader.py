"""CC0-1.0. Lazy pinned CPU Qwen3 valid-code scores; no generation or fit."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time

MODEL_ID = 'Qwen/Qwen3-0.6B'
MODEL_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
MAX_PAIR_TOKENS = 512
CODES = ('A', 'B', 'C')
LABELS = ('entailment', 'contradiction', 'not_mentioned')
PROMPT_PATH = Path(__file__).with_name('prompt.json')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


class FixedZeroShotReader:
    """Constructor is lazy. Caller owns frozen-source/admission/asset verification.

    progress(event_dict) must synchronously persist and fsync each event before
    returning. Shared counters are updated here, not again by the caller.
    deadline is the absolute wall-clock deadline for the whole owned worker.
    """
    def __init__(self, model_dir, counters, progress, deadline):
        self.model_dir = Path(model_dir)
        self.counters = counters
        self.progress = progress
        self.deadline = float(deadline)
        self.tokenizer = None
        self.model = None
        self.torch = None
        self.spec = json.loads(PROMPT_PATH.read_text())
        self.load_seconds = None
        self.code_ids = None
        self.forward_seconds = 0.0
        for key in ('NLI_model_initializations', 'NLI_model_initializations_completed',
                    'NLI_forward_pairs_attempted', 'NLI_forward_pairs_completed', 'NLI_forwards',
                    'NLI_forward_calls_attempted', 'NLI_forward_calls_completed'):
            self.counters.setdefault(key, 0)
        if not callable(progress):
            raise ValueError('Fsync progress callback is required')

    def _event(self, stage, **detail):
        self.progress({'reader_stage': stage, 'reader_counters': dict(self.counters), **detail})

    def _time(self):
        if time.time() >= self.deadline:
            raise TimeoutError('Whole-process deadline reached in reader')

    def _tokenizer(self):
        if self.tokenizer is not None:
            return
        self._time()
        self._event('BEFORE_TOKENIZER_INITIALIZATION')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        from transformers import AutoTokenizer
        cfg = json.loads((self.model_dir / 'tokenizer_config.json').read_text())
        if sha_bytes(cfg['chat_template'].encode()) != self.spec['chat_template_sha256']:
            raise ValueError('Pinned chat template changed')
        tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir),
            local_files_only=True, trust_remote_code=False)
        tokenizer.padding_side = 'left'
        ids = [tokenizer.encode(code, add_special_tokens=False) for code in CODES]
        if ids != [[self.spec['expected_token_ids'][c]] for c in CODES]:
            raise ValueError('Pinned A/B/C single-token IDs changed')
        if tokenizer.pad_token_id is None:
            raise ValueError('Pinned tokenizer must define padding token')
        self.tokenizer = tokenizer
        self.code_ids = [x[0] for x in ids]
        self._event('TOKENIZER_INITIALIZATION_COMPLETED', code_token_ids=dict(zip(CODES, self.code_ids)))

    def _render(self, context, hypothesis):
        if (not isinstance(context, str) or not isinstance(hypothesis, str)
                or not context.strip() or not hypothesis.strip()):
            raise ValueError('Nonempty evidence and hypothesis strings required')
        if len(context.encode()) > 4096 or len(hypothesis.encode()) > 2048:
            raise ValueError('Finite reader byte budget exceeded')
        self._tokenizer()
        content = json.dumps({'evidence': context, 'hypothesis': hypothesis},
            ensure_ascii=False, separators=(',', ':'))
        messages = [{'role': 'system', 'content': self.spec['system']},
                    {'role': 'user', 'content': content}]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        if not 1 <= len(ids) <= MAX_PAIR_TOKENS:
            raise ValueError('Prompt exceeds512 tokens; silent truncation forbidden')
        for code, code_id in zip(CODES, self.code_ids):
            if self.tokenizer.encode(prompt+code, add_special_tokens=False) != ids+[code_id]:
                raise ValueError('A/B/C must remain one token at actual prompt boundary')
        return prompt, ids

    def token_count(self, context, hypothesis):
        return len(self._render(context, hypothesis)[1])

    def _model(self):
        if self.model is not None:
            return
        self._time()
        if self.counters['NLI_model_initializations'] != 0:
            raise ValueError('A second model initialization is forbidden')
        os.environ['OMP_NUM_THREADS'] = '2'
        os.environ['MKL_NUM_THREADS'] = '2'
        import torch
        from transformers import AutoModelForCausalLM
        torch.set_num_threads(2)
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        if torch.get_num_threads() != 2 or torch.get_num_interop_threads() != 1:
            raise ValueError('Exact CPU torch thread bounds required')
        config = json.loads((self.model_dir/'config.json').read_text())
        if (config.get('model_type') != 'qwen3'
                or config.get('architectures') != ['Qwen3ForCausalLM']
                or config.get('vocab_size') != 151936):
            raise ValueError('Exact Qwen3 architecture required')
        self.counters['NLI_model_initializations'] += 1
        self._event('BEFORE_MODEL_INITIALIZATION', model_revision=MODEL_REVISION)
        started = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(str(self.model_dir),
            local_files_only=True, trust_remote_code=False, torch_dtype=torch.float32,
            attn_implementation='sdpa')
        model.eval()
        if any(p.device.type != 'cpu' or p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError('Every reader parameter must be FP32CPU')
        self.model, self.torch = model, torch
        self.load_seconds = time.perf_counter()-started
        self.counters['NLI_model_initializations_completed'] += 1
        self._event('MODEL_INITIALIZATION_COMPLETED', load_seconds=self.load_seconds)

    def score(self, context, hypothesis):
        prompt, ids = self._render(context, hypothesis)
        self._model()
        self._time()
        if self.counters['NLI_forward_pairs_attempted'] >= 18:
            raise ValueError('More than eighteen authored pairs forbidden')
        tensors = self.tokenizer(prompt, return_tensors='pt', truncation=False,
            add_special_tokens=False)
        if list(tensors['input_ids'].shape) != [1, len(ids)]:
            raise ValueError('Exact sequential batch-size-one required')
        self.counters['NLI_forward_pairs_attempted'] += 1
        self.counters['NLI_forward_calls_attempted'] += 1
        self._event('BEFORE_FORWARD', pair=self.counters['NLI_forward_pairs_attempted'],
            prompt_sha256=sha_bytes(prompt.encode()), token_count=len(ids))
        started = time.perf_counter()
        with self.torch.inference_mode():
            output = self.model(**tensors, use_cache=False, logits_to_keep=1,
                output_attentions=False, output_hidden_states=False, return_dict=True)
        if list(output.logits.shape) != [1, 1, 151936]:
            raise ValueError('Expected one-position full-vocabulary logits')
        selected = output.logits[0, 0, self.code_ids].to(dtype=self.torch.float64).tolist()
        if any(not math.isfinite(x) for x in selected):
            raise ValueError('Nonfinite A/B/C logits')
        peak = max(selected)
        shifted_log_normalizer = math.log(math.fsum(math.exp(x-peak) for x in selected))
        logp = [(x-peak)-shifted_log_normalizer for x in selected]
        probabilities = [math.exp(x) for x in logp]
        if (any(not math.isfinite(p) or p < 0 or p > 1 for p in probabilities)
                or abs(math.fsum(probabilities)-1) > 1e-8):
            raise ValueError('Invalid valid-code conditional softmax')
        best = max(range(3), key=lambda i: probabilities[i])
        elapsed = time.perf_counter()-started
        self.forward_seconds += elapsed
        result = {'probabilities': dict(zip(LABELS, probabilities)),
            'log_probabilities': dict(zip(LABELS, logp)),
            'conditional_valid_code_probabilities': dict(zip(CODES, probabilities)),
            'selected_logits': dict(zip(CODES, selected)),
            'prediction': LABELS[best], 'prediction_code': CODES[best],
            'token_count': len(ids), 'prompt_sha256': sha_bytes(prompt.encode()),
            'evidence_sha256': sha_bytes(context.encode()),
            'hypothesis_sha256': sha_bytes(hypothesis.encode()), 'forward_seconds': elapsed,
            'scope': 'Supplied evidence only; no corpus-wide insufficiency assertion.'}
        self.counters['NLI_forward_pairs_completed'] += 1
        self.counters['NLI_forward_calls_completed'] += 1
        self.counters['NLI_forwards'] = self.counters['NLI_forward_pairs_completed']
        self._event('FORWARD_COMPLETED', pair=self.counters['NLI_forward_pairs_completed'], result=result)
        return result

    @property
    def receipt(self):
        return {'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
            'source_weight_dtype': 'bfloat16', 'parameter_dtype': 'float32',
            'conversion': 'Exact BF16 values represented as FP32; no quantization claim.',
            'device': 'cpu', 'attention': 'sdpa', 'torch_threads': 2, 'torch_interop_threads': 1,
            'trust_remote_code': False, 'local_files_only': True, 'use_cache': False,
            'logits_to_keep': 1, 'batch_size': 1, 'maximum_pairs': 18,
            'code_to_label': dict(zip(CODES, LABELS)),
            'code_token_ids': dict(zip(CODES, self.code_ids)) if self.code_ids else None,
            'prompt_file_sha256': sha_bytes(PROMPT_PATH.read_bytes()),
            'chat_template_sha256': self.spec['chat_template_sha256'], 'enable_thinking': False,
            'max_total_prompt_tokens': MAX_PAIR_TOKENS, 'truncation': False,
            'load_seconds': self.load_seconds, 'forward_seconds': self.forward_seconds,
            'probability_semantics': 'Normalized A/B/C token scores, not calibrated legal truth probabilities.',
            'scope': 'AUTHOR_ONLY_CC0_ENGINEERING'}
