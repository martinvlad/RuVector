"""Admitted CPU BART LoRA training/inference. Import uses stdlib only.

The stock E27 safe loader supplies the exact original2020 MNLI checkpoint.
Current E30 source/model admissions authorize the phase; the historical asset
lock is used only as a byte-identity envelope, never as execution permission.
No parity/warmup forward is performed: B=0 and frozen tensor identity establish
the initial zero effective delta without spending an unaccounted model call.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = _load('e30_model_fixed_algorithm', 'algorithm.py')
P = _load('e30_model_parameter_codec', 'parameter_codec.py')


def _diagnostic(value):
    return value if math.isfinite(value) else {'nonfinite_number': repr(value)}


def _lora_type(torch):
    class FrozenBaseLoRALinear(torch.nn.Module):
        def __init__(self, original, generator):
            super().__init__()
            if (type(original).__name__ != 'Linear' or original.in_features != 1024
                    or original.out_features != 1024):
                raise ValueError('Only exact1024x1024 original attention projections may be adapted')
            self.base = original
            self.lora_A = torch.nn.Parameter(torch.empty((4, 1024), dtype=torch.float32, device='cpu'))
            self.lora_B = torch.nn.Parameter(torch.zeros((1024, 4), dtype=torch.float32, device='cpu'))
            torch.nn.init.uniform_(self.lora_A, a=-1 / 32, b=1 / 32, generator=generator)
            self.enabled, self.scale = False, 2.0

        def forward(self, value):
            baseline = self.base(value)
            if not self.enabled:
                return baseline
            delta = torch.nn.functional.linear(
                torch.nn.functional.linear(value, self.lora_A), self.lora_B)
            return baseline + delta * self.scale
    return FrozenBaseLoRALinear


class LegalBartAdapter:
    def __init__(self, original_reader_module, model_directory, asset_lock,
                 phase, counters, progress):
        if phase not in ('train', 'dev'):
            raise ValueError('Only fixed train/dev phases exist')
        self.phase, self.counters, self.progress = phase, counters, progress
        self.original_valid_count, self.adapted_valid_count, self.step_index = 0, 0, 0
        self.B_gradient_steps = {name: [] for name in A.MODULES}
        self.B_gradient_max = {name: 0.0 for name in A.MODULES}
        self.adapters, self.optimizer, self.loaded_artifact = {}, None, None
        counters['BART_initializations_attempted'] += 1
        progress({'event': 'ORIGINAL_BART_INITIALIZATION_BEFORE', 'phase': phase})
        started = time.perf_counter()
        self.reader = original_reader_module.FrozenBartReader(model_directory, asset_lock,
            max_pair_tokens=512, attention='sdpa')
        counters['BART_initializations_completed'] += 1
        self.torch, self.model, self.tokenizer = self.reader.torch, self.reader.model, self.reader.tokenizer
        self.decisions = original_reader_module.decisions
        self.model.eval()
        self.model.config.use_cache = False
        self.pretrained = dict(self.model.named_parameters())
        if sum(parameter.numel() for parameter in self.pretrained.values()) != A.BASE_MODEL['pretrained_parameter_count']:
            raise ValueError('Exact original unique pretrained parameter count changed')
        for parameter in self.pretrained.values():
            parameter.requires_grad_(False)
        self.head = {name: self.pretrained[name] for name in A.HEAD_NAMES}
        self.original_head = {name: parameter.detach().clone() for name, parameter in self.head.items()}
        self.original_head_manifest = self._manifest(self.head, A.HEAD_NAMES)
        self.runtime_checks = {'safe_original_loader': self.reader.runtime_checks,
            'initialization_seconds': time.perf_counter() - started,
            'original_head_manifest': self.original_head_manifest,
            'no_head_reinitialization': True, 'full_model_warmup_or_parity_forwards': 0}
        if phase == 'train':
            self.frozen_before = self._frozen_manifest()
            self._inject_lora()
            for parameter in self.head.values():
                parameter.requires_grad_(True)
            self.initial_trainable = self._manifest(self.trainable, [name for name, _shape in A.EXPECTED_TENSORS])
            for adapter in self.adapters.values():
                adapter.enabled = True
            self._verify_parameter_roles(training=True)
            counters['optimizer_initializations_attempted'] += 1
            self.optimizer = self.torch.optim.AdamW(list(self.trainable.values()), lr=1e-4,
                betas=(0.9, 0.999), eps=1e-8, weight_decay=0.01, foreach=False, fused=False,
                amsgrad=False, maximize=False, capturable=False, differentiable=False)
            counters['optimizer_initializations_completed'] += 1
        else:
            self.frozen_before, self.initial_trainable, self.trainable = None, None, {}
            self._verify_parameter_roles(training=False, before_injection=True)
        progress({'event': 'ORIGINAL_BART_INITIALIZATION_AFTER', 'phase': phase,
            'original_parameter_count': A.BASE_MODEL['pretrained_parameter_count'],
            'trainable_parameters': A.TRAINABLE_COUNT if phase == 'train' else 0})

    def _bytes(self, parameter):
        if parameter.device.type != 'cpu' or parameter.dtype != self.torch.float32:
            raise ValueError('Only CPU float32 parameter data may be serialized')
        # CPU x86_64 is fixed by the kernel guard. Explicit little-endian
        # conversion preserves every actual float32 bit, including signed zero.
        return parameter.detach().contiguous().numpy().astype('<f4', copy=False).tobytes(order='C')

    def _manifest(self, parameters, names):
        result = []
        for name in names:
            parameter = parameters[name]
            if not bool(self.torch.isfinite(parameter).all()):
                raise ValueError('Nonfinite actual parameter: ' + name)
            # Vectorized finiteness avoids407million Python scalar checks while
            # preserving a full byte hash for every frozen pretrained tensor.
            result.append(P.manifest(name, tuple(parameter.shape), self._bytes(parameter), check_finite=False))
        return result

    def _frozen_manifest(self):
        names = sorted(name for name in self.pretrained if name not in A.HEAD_NAMES)
        result = self._manifest(self.pretrained, names)
        if sum(record['numel'] for record in result) != A.FROZEN_COUNT:
            raise ValueError('Original frozen pretrained scalar count changed')
        return result

    def _inject_lora(self):
        if self.adapters:
            raise ValueError('LoRA modules may be injected only once')
        self.counters['LoRA_initializations_attempted'] += 1
        self.torch.manual_seed(A.SEED)
        generator = self.torch.Generator(device='cpu')
        generator.manual_seed(A.SEED)
        wrapper = _lora_type(self.torch)
        for name in A.MODULES:
            parent_name, attribute = name.rsplit('.', 1)
            parent = self.model.get_submodule(parent_name)
            original = getattr(parent, attribute)
            adapter = wrapper(original, generator)
            setattr(parent, attribute, adapter)
            self.adapters[name] = adapter
        self.model.eval()
        ordered = {}
        for name in A.MODULES:
            ordered[name + '.lora_A'] = self.adapters[name].lora_A
            ordered[name + '.lora_B'] = self.adapters[name].lora_B
        ordered.update(self.head)
        self.trainable = ordered
        if list(ordered) != [name for name, _shape in A.EXPECTED_TENSORS]:
            raise ValueError('Exact learned parameter order changed')
        for (name, shape), (observed_name, parameter) in zip(A.EXPECTED_TENSORS, ordered.items()):
            if name != observed_name or tuple(parameter.shape) != shape:
                raise ValueError('Exact LoRA/head tensor names or shapes changed')
        if sum(parameter.numel() for parameter in ordered.values()) != A.TRAINABLE_COUNT:
            raise ValueError('Exact1085443 learned parameter count changed')
        if sum(parameter.numel() for parameter in self.model.parameters()) != A.BASE_MODEL['pretrained_parameter_count'] + 32768:
            raise ValueError('Unexpected parameter added/replaced during attention adaptation')
        self.counters['LoRA_initializations_completed'] += 1

    def _verify_parameter_roles(self, training, before_injection=False):
        if self.model.training or any(module.training for module in self.model.modules()):
            raise ValueError('All model modules must remain in eval mode, including gradient-enabled TRAIN')
        for name, parameter in self.pretrained.items():
            expected = training and name in A.HEAD_NAMES
            if parameter.requires_grad != expected:
                raise ValueError('Wrong original pretrained requires_grad role: ' + name)
            if name not in A.HEAD_NAMES and parameter.grad is not None:
                raise ValueError('A frozen pretrained tensor accumulated a gradient')
        if not before_injection:
            for adapter in self.adapters.values():
                if adapter.scale != 2.0 or adapter.lora_A.requires_grad != training or adapter.lora_B.requires_grad != training:
                    raise ValueError('Wrong fixed LoRA scale/gradient role')

    def _features(self, premise, hypothesis, receipt):
        if not isinstance(premise, str) or not premise.strip() or not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError('Complete nonempty source premise and hypothesis required')
        self.counters['pair_tokenizations_attempted'] += 1
        self.progress({'event': 'TRUE_PAIR_TOKENIZATION_BEFORE', 'phase': self.phase})
        full = self.tokenizer(premise, hypothesis, add_special_tokens=True, padding=False,
            truncation=False, return_attention_mask=False, return_token_type_ids=False)
        ids = full['input_ids']
        if not isinstance(ids, list) or not 0 < len(ids) <= 512:
            raise ValueError('Whole packed native BART pair exceeds512; no hidden truncation')
        features = self.tokenizer(premise, hypothesis, add_special_tokens=True, padding=False,
            truncation='only_first', max_length=512, return_tensors='pt',
            return_attention_mask=True, return_token_type_ids=False)
        if (set(features) != {'input_ids', 'attention_mask'}
                or tuple(features['input_ids'].shape) != (1, len(ids))
                or features['input_ids'][0].tolist() != ids
                or features['attention_mask'][0].tolist() != [1] * len(ids)):
            raise ValueError('Actual true-pair IDs/mask differ from complete source packing')
        self.counters['pair_tokenizations_completed'] += 1
        receipt.update(pair_tokens=len(ids), full_pair_tokens=len(ids), max_pair_tokens=512,
            premise_truncated=False, hypothesis_truncated=False, truncation='only_first',
            native_pair_input_ids_sha256=P.canonical_sha(ids),
            premise_sha256=hashlib.sha256(premise.encode('utf-8')).hexdigest(),
            hypothesis_sha256=hashlib.sha256(hypothesis.encode('utf-8')).hexdigest())
        return {key: value.to(device='cpu') for key, value in features.items()}

    def _forward(self, features, category, receipt):
        self.counters['NLI_forward_calls_attempted'] += 1
        self.counters[category + '_forward_calls_attempted'] += 1
        self.progress({'event': 'NLI_FORWARD_BEFORE', 'category': category})
        output = self.model(**features, use_cache=False)
        self.counters['NLI_forward_calls_completed'] += 1
        self.counters[category + '_forward_calls_completed'] += 1
        logits = output.logits
        receipt['actual_logits_shape'] = list(logits.shape)
        if tuple(logits.shape) != (1, 3):
            raise ValueError('Actual BART output is not one complete three-way head')
        values = [float(value) for value in logits[0].detach().cpu().tolist()]
        receipt['raw_logits_diagnostic'] = [_diagnostic(value) for value in values]
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Actual BART produced a nonfinite logit')
        receipt.update(self.decisions(values))
        self.progress({'event': 'NLI_FORWARD_AFTER', 'category': category})
        return logits

    def score_original(self, premise, hypothesis, receipt):
        if self.phase != 'dev' or self.loaded_artifact is not None or self.adapters:
            raise ValueError('Original DEV forwards must precede any learned-parameter load/injection')
        if self.original_valid_count >= 24:
            raise ValueError('Original DEV forward slot cap reached')
        started = time.perf_counter()
        current = self._manifest(self.head, A.HEAD_NAMES)
        if current != self.original_head_manifest:
            raise ValueError('Original pretrained classifier changed before baseline evidence')
        self._verify_parameter_roles(training=False, before_injection=True)
        receipt['state_receipt'] = {'state': 'original', 'head_manifest_sha256': P.canonical_sha(current),
            'LoRA_injected': False, 'learned_parameters_loaded': False,
            'verification_seconds': time.perf_counter() - started}
        started = time.perf_counter()
        features = self._features(premise, hypothesis, receipt)
        with self.torch.inference_mode():
            self._forward(features, 'original_DEV', receipt)
        receipt['latency_seconds'] = time.perf_counter() - started
        self.original_valid_count += 1
        return receipt

    def score_adapted(self, premise, hypothesis, receipt):
        if self.phase != 'dev' or self.loaded_artifact is None or self.original_valid_count != 24:
            raise ValueError('Sealed learned state and completed original24 are required')
        if self.adapted_valid_count >= 72:
            raise ValueError('Adapted DEV forward slot cap reached')
        started = time.perf_counter()
        self._verify_parameter_roles(training=False)
        current = self._manifest(self.trainable, [name for name, _shape in A.EXPECTED_TENSORS])
        if current != self.loaded_trainable_manifest or any(not adapter.enabled for adapter in self.adapters.values()):
            raise ValueError('Exact sealed LoRA/head state changed or is not active')
        receipt['state_receipt'] = {'state': 'adapted', 'parameter_artifact_sha256': self.loaded_artifact['sha256'],
            'trainable_manifest_sha256': P.canonical_sha(current), 'LoRA_enabled': True, 'LoRA_scale': 2.0,
            'verification_seconds': time.perf_counter() - started}
        started = time.perf_counter()
        features = self._features(premise, hypothesis, receipt)
        with self.torch.inference_mode():
            self._forward(features, 'adapted_DEV', receipt)
        receipt['latency_seconds'] = time.perf_counter() - started
        self.adapted_valid_count += 1
        return receipt

    def train_step(self, case_id, premise, hypothesis, native_target_index, receipt):
        if (self.phase != 'train' or self.optimizer is None or self.step_index >= 24
                or case_id != A.TRAIN_CASE_IDS[self.step_index]
                or type(native_target_index) is not int or native_target_index not in (0, 1, 2)):
            raise ValueError('Exactly one fixed ordered TRAIN epoch is allowed')
        self._verify_parameter_roles(training=True)
        if any(not adapter.enabled for adapter in self.adapters.values()):
            raise ValueError('Intended attention adapters were disabled during training')
        receipt.update(case_id=case_id, step=self.step_index + 1,
            target_role='Exact selected TRAIN choice consumed locally; individual target not published',
            optimizer_configuration=A.ALGORITHM['optimizer'], model_eval=True, class_weights=None)
        started = time.perf_counter()
        self.optimizer.zero_grad(set_to_none=True)
        features = self._features(premise, hypothesis, receipt)
        with self.torch.enable_grad():
            logits = self._forward(features, 'TRAIN', receipt)
            target = self.torch.tensor([native_target_index], dtype=self.torch.long, device='cpu')
            loss = self.torch.nn.functional.cross_entropy(logits, target, weight=None,
                reduction='mean', label_smoothing=0.0)
            observed_loss = float(loss.detach().cpu())
            receipt['loss_diagnostic'] = _diagnostic(observed_loss)
            if not math.isfinite(observed_loss):
                raise ValueError('Nonfinite unweighted TRAIN cross entropy')
            receipt['unweighted_cross_entropy'] = observed_loss
            self.counters['backward_calls_attempted'] += 1
            self.progress({'event': 'TRAIN_BACKWARD_BEFORE', 'case_id': case_id})
            loss.backward()
            self.counters['backward_calls_completed'] += 1
            for parameter in self.trainable.values():
                if parameter.grad is None or not bool(self.torch.isfinite(parameter.grad).all()):
                    raise ValueError('Missing/nonfinite intended trainable gradient')
            receipt['LoRA_B_gradients'] = []
            for name in A.MODULES:
                self.counters['LoRA_B_gradient_checks_attempted'] += 1
                gradient = self.adapters[name].lora_B.grad.detach()
                count = int(self.torch.count_nonzero(gradient).cpu())
                l2 = float(self.torch.linalg.vector_norm(gradient.to(dtype=self.torch.float64)).cpu())
                if not math.isfinite(l2):
                    raise ValueError('Nonfinite actual attention B gradient norm')
                receipt['LoRA_B_gradients'].append({'module': name,
                    'finite': True, 'nonzero_entries': count, 'l2_norm': l2})
                if count > 0:
                    self.B_gradient_steps[name].append(self.step_index + 1)
                    self.B_gradient_max[name] = max(self.B_gradient_max[name], l2)
                self.counters['LoRA_B_gradient_checks_completed'] += 1
            self._verify_parameter_roles(training=True)
            self.counters['gradient_clips_attempted'] += 1
            norm = self.torch.nn.utils.clip_grad_norm_(list(self.trainable.values()), max_norm=1.0,
                error_if_nonfinite=True, foreach=False)
            self.counters['gradient_clips_completed'] += 1
            receipt['gradient_global_norm_before_clip'] = float(norm.detach().cpu())
            if not math.isfinite(receipt['gradient_global_norm_before_clip']):
                raise ValueError('Nonfinite gradient clipping norm')
            self.counters['optimizer_steps_attempted'] += 1
            self.progress({'event': 'OPTIMIZER_STEP_BEFORE', 'case_id': case_id})
            self.optimizer.step()
            self.counters['optimizer_steps_completed'] += 1
            self.counters['training_steps'] += 1
        self.step_index += 1
        current = self._manifest(self.trainable, [name for name, _shape in A.EXPECTED_TENSORS])
        receipt.update(trainable_manifest_sha256_after_step=P.canonical_sha(current),
            all_trainable_parameters_finite=True, step_seconds=time.perf_counter() - started)
        self.progress({'event': 'TRAIN_STEP_COMPLETED', 'case_id': case_id, 'step': self.step_index})
        return receipt

    def _effective_deltas(self, include_training_gradients=False):
        records = []
        with self.torch.no_grad():
            for name in A.MODULES:
                adapter = self.adapters[name]
                delta = (adapter.lora_B @ adapter.lora_A) * adapter.scale
                if not bool(self.torch.isfinite(delta).all()):
                    raise ValueError('Nonfinite effective attention adaptation')
                record = {'module': name, 'shape': [1024, 1024], 'scale': 2.0,
                    'sha256': hashlib.sha256(self._bytes(delta)).hexdigest(),
                    'l2_norm': float(self.torch.linalg.vector_norm(delta).cpu()),
                    'max_abs': float(delta.abs().max().cpu()),
                    'nonzero_entries': int(self.torch.count_nonzero(delta).cpu())}
                if include_training_gradients:
                    if not self.B_gradient_steps[name] or not self.B_gradient_max[name] > 0:
                        raise ValueError('Intended attention B tensor never had a nonzero finite training gradient')
                    record.update(B_nonzero_gradient_steps=self.B_gradient_steps[name],
                        max_B_gradient_l2=self.B_gradient_max[name])
                records.append(record)
        return records

    def export_artifact(self, path, source_plan_sha256, training_inputs_sha256):
        if self.phase != 'train' or self.step_index != 24:
            raise ValueError('Partial or missing TRAIN updates may never produce a DEV artifact')
        self._verify_parameter_roles(training=True)
        self.optimizer.zero_grad(set_to_none=True)
        after = self._frozen_manifest()
        if after != self.frozen_before:
            raise ValueError('A frozen original pretrained parameter changed during adaptation')
        names = [name for name, _shape in A.EXPECTED_TENSORS]
        learned = self._manifest(self.trainable, names)
        changes = [{'name': current['name'], 'before_sha256': initial['sha256'],
            'after_sha256': current['sha256'], 'changed': current['sha256'] != initial['sha256']}
            for initial, current in zip(self.initial_trainable, learned)]
        if not all(record['changed'] for record in changes):
            raise ValueError('An intended LoRA/head tensor did not change; no mechanism substitution')
        proof = {'parameter_count': A.FROZEN_COUNT, 'tensor_count': len(after),
            'before_after': [{**{key: old[key] for key in ('name', 'shape', 'dtype', 'numel', 'bytes')},
                'sha256_before': old['sha256'], 'sha256_after': new['sha256']}
                for old, new in zip(self.frozen_before, after)], 'all_bit_unchanged': True,
            'aggregate_before_sha256': P.canonical_sha(self.frozen_before), 'aggregate_after_sha256': P.canonical_sha(after)}
        value = {'schema_version': 1, 'epoch': 30, 'kind': A.KIND, 'codec': A.CODEC,
            'base_model': A.BASE_MODEL, 'algorithm': A.ALGORITHM,
            'source_plan_sha256': source_plan_sha256, 'training_inputs_sha256': training_inputs_sha256,
            'training_steps': 24, 'trainable_parameter_count': A.TRAINABLE_COUNT,
            'tensors': [P.encode_tensor(name, tuple(self.trainable[name].shape), self._bytes(self.trainable[name])) for name in names],
            'original_head_manifest': self.original_head_manifest,
            'initial_trainable_manifest': self.initial_trainable, 'trainable_changes': changes,
            'frozen_pretrained_proof': proof, 'effective_lora_delta': self._effective_deltas(include_training_gradients=True)}
        self.counters['parameter_artifacts_write_attempted'] += 1
        self.progress({'event': 'COMPLETE_LEARNED_PARAMETER_ARTIFACT_BEFORE'})
        reference = P.write_artifact(path, value)
        self.counters['parameter_artifacts_write_completed'] += 1
        self.progress({'event': 'COMPLETE_LEARNED_PARAMETER_ARTIFACT_AFTER', 'sha256': reference['sha256']})
        return reference, {'original_head_manifest': self.original_head_manifest,
            'trainable_changes': changes, 'frozen_pretrained_proof': proof,
            'effective_lora_delta': value['effective_lora_delta'], 'training_steps': self.step_index}

    def load_adaptation(self, path, expected_sha256, expected_source_plan_sha256, expected_train_inputs_sha256):
        if self.phase != 'dev' or self.original_valid_count != 24 or self.loaded_artifact is not None or self.adapters:
            raise ValueError('Sealed artifact load is permitted only once AFTER all original native24 outputs')
        self.counters['parameter_artifacts_load_attempted'] += 1
        self.progress({'event': 'SEALED_PARAMETERS_LOAD_BEFORE'})
        payload = Path(path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError('Learned artifact differs from actual Git MODEL seal')
        value = json.loads(payload)
        decoded = P.validate_artifact(value)
        if value['source_plan_sha256'] != expected_source_plan_sha256 or value['training_inputs_sha256'] != expected_train_inputs_sha256:
            raise ValueError('Learned parameters came from another TRAIN source/input identity')
        if value['original_head_manifest'] != self.original_head_manifest:
            raise ValueError('Fresh original head differs from exact TRAIN starting head')
        actual_frozen = self._frozen_manifest()
        if P.canonical_sha(actual_frozen) != value['frozen_pretrained_proof']['aggregate_before_sha256']:
            raise ValueError('Fresh original backbone differs from exact sealed TRAIN backbone')
        self._inject_lora()
        initial = self._manifest(self.trainable, [name for name, _shape in A.EXPECTED_TENSORS])
        if initial != value['initial_trainable_manifest']:
            raise ValueError('Deterministic LoRA initialization/original head identity changed')
        with self.torch.no_grad():
            for (name, shape), raw in zip(A.EXPECTED_TENSORS, decoded):
                source = self.torch.frombuffer(bytearray(raw), dtype=self.torch.float32).reshape(shape)
                self.trainable[name].copy_(source)
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        for adapter in self.adapters.values():
            adapter.enabled = True
        self.model.eval()
        self._verify_parameter_roles(training=False)
        expected_manifest = [{key: record[key] for key in ('name', 'shape', 'dtype', 'numel', 'bytes', 'sha256')}
            for record in value['tensors']]
        self.loaded_trainable_manifest = self._manifest(self.trainable, [name for name, _shape in A.EXPECTED_TENSORS])
        geometry = [{key: record[key] for key in ('module', 'shape', 'scale', 'sha256', 'l2_norm', 'max_abs', 'nonzero_entries')}
            for record in value['effective_lora_delta']]
        if self.loaded_trainable_manifest != expected_manifest or self._effective_deltas() != geometry:
            raise ValueError('Actual applied factor/head/effective-delta identity differs from sealed bytes')
        self.loaded_artifact = {'path': str(path), 'bytes': len(payload), 'sha256': expected_sha256}
        self.counters['parameter_artifacts_load_completed'] += 1
        self.progress({'event': 'SEALED_PARAMETERS_APPLIED', 'sha256': expected_sha256})
        return {'artifact': self.loaded_artifact, 'original_head_manifest': self.original_head_manifest,
            'applied_trainable_manifest': self.loaded_trainable_manifest,
            'effective_lora_delta': value['effective_lora_delta'], 'original_baseline_outputs_completed_before_load': 24}
