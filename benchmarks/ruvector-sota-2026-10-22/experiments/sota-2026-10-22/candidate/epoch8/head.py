"""Fixed train-only residual three-way head, with an immutable fitted artifact."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch8_features', HERE / 'features.py')
FEATURES = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FEATURES)
ARMS = ('ruvector_top2', 'lexical_top2', 'positional_first2')
ALGORITHM = {'optimizer': 'full_batch_Adam_float64', 'steps': 400, 'learning_rate': 0.03,
             'beta1': 0.9, 'beta2': 0.999, 'epsilon': 1e-8, 'residual_l2': 0.1,
             'scale_floor': 0.1, 'final_gradient_norm_max': 1e-3,
             'final_vs_initial_objective_tolerance': 1e-8,
             'objective': 'weighted_mean_threeway_cross_entropy+0.5*L2*sum(residual_weights**2)',
             'sample_weight': 'Each question has totalweight1; each of its3 arms hasweight1/3',
             'calibration': False, 'threshold_fit': False, 'early_stop': False}


class FitFailure(ValueError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def softmax(logits):
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all():
        raise ValueError('Finite three-way logits required')
    exp = np.exp(values - values.max(axis=1, keepdims=True))
    return exp / exp.sum(axis=1, keepdims=True)


def collect(records, allowlist):
    if (allowlist.get('role') != 'train' or allowlist.get('queries') != 72
            or allowlist.get('document_groups') != 24
            or tuple(allowlist.get('threeway_classes', [])) != FEATURES.CLASSES):
        raise ValueError('Exact TRAIN72/24group/threeway contract required')
    expected = {item['id']: item for item in allowlist['records']}
    if len(expected) != 72 or len(records) != 72 or {row['id'] for row in records} != set(expected):
        raise ValueError('Training records must exactly equal the frozen72-question allowlist')
    if len({row['source_group'] for row in records}) != 24:
        raise ValueError('Expected24 training document groups')
    examples = []
    for row in sorted(records, key=lambda item: item['id']):
        admitted = expected[row['id']]
        if row.get('split') != 'train':
            raise ValueError('DEV/confirmation or unknown split cannot enter fitting')
        if (row.get('input_sha256') != admitted['input_sha256']
                or hashlib.sha256(canonical(row['input'])).hexdigest() != admitted['input_sha256']
                or row.get('source_group') != admitted['source_group']
                or row.get('provenance', {}).get('hypothesis_id') != admitted['hypothesis_id']):
            raise ValueError('Training input or source identity differs from allowlist')
        label = row['evaluation']['original_threeway_label']
        if label not in FEATURES.CLASSES:
            raise ValueError('Unknown original three-way training class')
        if row['evaluation'].get('gold') != ('Yes' if label == 'Entailment' else 'No'):
            raise ValueError('Cached binary and original three-way training targets disagree')
        if set(row['input']['questions']) != {'decision'}:
            raise ValueError('Expected one original legal decision per training record')
        hypothesis = row['input']['questions']['decision']['criteria']['Yes']
        state = row['input']['state']
        diagnostic = row['response']['diagnostics']['decision']
        if diagnostic['source_state_sha256'] != hashlib.sha256(state.encode()).hexdigest():
            raise ValueError('Cached training source identity differs')
        for arm in ARMS:
            observation = diagnostic['arms'][arm]
            trace = observation['decoding']
            if observation['hypothesis'] != hypothesis or trace['typed_head_state'] != 'TRAIN_COLLECTION':
                raise ValueError('Only raw pre-fit TRAIN collection traces may enter fitting')
            if trace['typed_head_feature_names'] != list(FEATURES.FEATURE_NAMES):
                raise ValueError('Cached feature schema differs')
            logits = [float(value) for value in trace['typed_head_canonical_logits']]
            raw_logits = trace['logits']
            if logits != [raw_logits[1], raw_logits[0], raw_logits[2]]:
                raise ValueError('Canonical logits differ from pinnedC0/E1/N2 model output')
            spans = observation['coverage']['selected_source_spans']
            if observation['premise'] != '\n\n'.join(state[a:b] for a, b in spans):
                raise ValueError('Training premise differs from exact selected source spans')
            computed = FEATURES.extract(observation['premise'], hypothesis, logits)
            if computed != trace['typed_head_features']:
                raise ValueError('Cached inference-only features do not replay from source/logits')
            examples.append({'id': row['id'], 'source_group': row['source_group'], 'input_sha256': admitted['input_sha256'],
                             'arm': arm, 'original_threeway_label': label, 'weight': 1 / 3,
                             'canonical_logits': logits, 'features': computed})
    if {example['original_threeway_label'] for example in examples} != set(FEATURES.CLASSES):
        raise ValueError('Missing training class; no fallback or binary collapse permitted')
    return examples


def objective(weights, x, base, y, sample_weight):
    logits = base + x @ weights
    logsum = logits.max(axis=1) + np.log(np.exp(logits - logits.max(axis=1, keepdims=True)).sum(axis=1))
    nll = logsum - logits[np.arange(len(y)), y]
    loss = float(sample_weight @ nll / sample_weight.sum() + 0.5 * ALGORITHM['residual_l2'] * np.square(weights).sum())
    difference = softmax(logits)
    difference[np.arange(len(y)), y] -= 1
    gradient = x.T @ (difference * sample_weight[:, None]) / sample_weight.sum() + ALGORITHM['residual_l2'] * weights
    return loss, gradient


def parameters_digest(artifact):
    return hashlib.sha256(canonical({name: artifact[name] for name in ('class_order', 'feature_names', 'mean', 'scale', 'weights')})).hexdigest()


def fit(records, allowlist, config_sha256, allowlist_sha256, model_identity):
    examples = collect(records, allowlist)
    raw = np.asarray([example['features'] for example in examples], dtype=np.float64)
    base = np.asarray([example['canonical_logits'] for example in examples], dtype=np.float64)
    base -= base.mean(axis=1, keepdims=True)
    y = np.asarray([FEATURES.CLASSES.index(example['original_threeway_label']) for example in examples])
    sample_weight = np.asarray([example['weight'] for example in examples], dtype=np.float64)
    if not np.isfinite(raw).all() or raw.shape != (216, len(FEATURES.FEATURE_NAMES)):
        raise ValueError('Expected216 finite arm features')
    mean = np.average(raw, weights=sample_weight, axis=0)
    variance = np.average(np.square(raw - mean), weights=sample_weight, axis=0)
    scale = np.maximum(np.sqrt(variance), ALGORITHM['scale_floor'])
    mean[0] = 0.0; scale[0] = 1.0
    x = (raw - mean) / scale
    weights = np.zeros((len(FEATURES.FEATURE_NAMES), 3), dtype=np.float64)
    m = np.zeros_like(weights); v = np.zeros_like(weights)
    initial, _ = objective(weights, x, base, y, sample_weight)
    history = []
    for step in range(1, ALGORITHM['steps'] + 1):
        loss, gradient = objective(weights, x, base, y, sample_weight)
        if not np.isfinite(loss) or not np.isfinite(gradient).all():
            raise FitFailure('Nonfinite fixed optimizer state; fitting fails closed',
                             {'stage': 'optimizer', 'reason': 'nonfinite_state', 'step_attempted': step,
                              'steps_completed': step - 1, 'initial_objective': initial if np.isfinite(initial) else None,
                              'failed_objective': loss if np.isfinite(loss) else None,
                              'failed_gradient_finite': bool(np.isfinite(gradient).all()),
                              'history': history, 'algorithm': dict(ALGORITHM)})
        m = ALGORITHM['beta1'] * m + (1 - ALGORITHM['beta1']) * gradient
        v = ALGORITHM['beta2'] * v + (1 - ALGORITHM['beta2']) * np.square(gradient)
        weights -= ALGORITHM['learning_rate'] * (m / (1 - ALGORITHM['beta1'] ** step)) / (np.sqrt(v / (1 - ALGORITHM['beta2'] ** step)) + ALGORITHM['epsilon'])
        history.append({'step': step, 'objective_before_step': loss, 'gradient_norm_before_step': float(np.linalg.norm(gradient))})
    final, gradient = objective(weights, x, base, y, sample_weight)
    gradient_norm = float(np.linalg.norm(gradient))
    if (not np.isfinite(final) or not np.isfinite(weights).all()
            or final > initial + ALGORITHM['final_vs_initial_objective_tolerance']
            or gradient_norm > ALGORITHM['final_gradient_norm_max']):
        raise FitFailure('Fixed final objective/gradient acceptance failed; no retry, fallback or extra steps',
                         {'stage': 'final_acceptance', 'reason': 'fixed_empirical_criteria_failed',
                          'steps_completed': ALGORITHM['steps'],
                          'initial_objective': initial if np.isfinite(initial) else None,
                          'final_objective': final if np.isfinite(final) else None,
                          'final_gradient_norm': gradient_norm if np.isfinite(gradient_norm) else None,
                          'parameters_finite': bool(np.isfinite(weights).all()),
                          'history': history, 'algorithm': dict(ALGORITHM)})
    artifact = {'schema_version': 1, 'state': 'FROZEN', 'class_order': list(FEATURES.CLASSES),
                'feature_names': list(FEATURES.FEATURE_NAMES), 'config_sha256': config_sha256,
                'train_allowlist_sha256': allowlist_sha256, 'model_identity': model_identity,
                'feature_source_sha256': sha(HERE / 'features.py'), 'trainer_source_sha256': sha(__file__),
                'algorithm': ALGORITHM, 'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': weights.tolist(),
                'training_questions': 72, 'training_document_groups': 24, 'training_arm_examples': 216,
                'training_total_weight': float(sample_weight.sum()), 'training_examples': examples,
                'training_class_question_counts': {name: sum(row['evaluation']['original_threeway_label'] == name for row in records) for name in FEATURES.CLASSES},
                'fit_diagnostics': {'initial_objective': initial, 'final_objective': final,
                                    'final_gradient_norm': gradient_norm, 'fixed_acceptance_criteria_passed': True,
                                    'convergence_claim': 'Empirical frozen objective/gradient criteria, not a mathematical convergence proof',
                                    'history': history, 'residual_weights_norm': float(np.linalg.norm(weights))},
                'fit_boundary': 'Exact TRAIN72 only;3 arms eachweight1/3; no DEV/CONF statistics, thresholds or calibration fit'}
    artifact['parameters_sha256'] = parameters_digest(artifact)
    return artifact


class FrozenHead:
    def __init__(self, artifact, config_sha256, allowlist_sha256, model_identity):
        if (artifact.get('state') != 'FROZEN' or artifact.get('config_sha256') != config_sha256
                or artifact.get('train_allowlist_sha256') != allowlist_sha256
                or artifact.get('model_identity') != model_identity
                or artifact.get('class_order') != list(FEATURES.CLASSES)
                or artifact.get('feature_names') != list(FEATURES.FEATURE_NAMES)
                or artifact.get('algorithm') != ALGORITHM
                or artifact.get('feature_source_sha256') != sha(HERE / 'features.py')
                or artifact.get('trainer_source_sha256') != sha(__file__)
                or artifact.get('parameters_sha256') != parameters_digest(artifact)):
            raise ValueError('Frozen head source/config/identity/schema integrity mismatch')
        self.mean = np.asarray(artifact['mean'], dtype=np.float64)
        self.scale = np.asarray(artifact['scale'], dtype=np.float64)
        self.weights = np.asarray(artifact['weights'], dtype=np.float64)
        width = len(FEATURES.FEATURE_NAMES)
        if (self.mean.shape != (width,) or self.scale.shape != (width,) or self.weights.shape != (width, 3)
                or not all(np.isfinite(item).all() for item in (self.mean, self.scale, self.weights))
                or np.any(self.scale <= 0) or self.mean[0] != 0 or self.scale[0] != 1):
            raise ValueError('Invalid fitted head dimensions or statistics')
        diagnostic = artifact.get('fit_diagnostics', {})
        if (artifact.get('training_questions') != 72 or artifact.get('training_document_groups') != 24
                or artifact.get('training_arm_examples') != 216
                or abs(artifact.get('training_total_weight', 0) - 72) > 1e-9
                or any(artifact.get('training_class_question_counts', {}).get(name, 0) < 1 for name in FEATURES.CLASSES)
                or len(diagnostic.get('history', [])) != ALGORITHM['steps']
                or diagnostic.get('fixed_acceptance_criteria_passed') is not True
                or not np.isfinite(diagnostic.get('final_gradient_norm', np.nan))
                or diagnostic['final_gradient_norm'] > ALGORITHM['final_gradient_norm_max']
                or not np.isfinite(diagnostic.get('final_objective', np.nan))
                or diagnostic['final_objective'] > diagnostic.get('initial_objective', -np.inf) + ALGORITHM['final_vs_initial_objective_tolerance']):
            raise ValueError('Fitted artifact lacks the frozen train-only fit acceptance evidence')

    def predict(self, feature_vector, canonical_logits):
        raw = np.asarray(feature_vector, dtype=np.float64)
        base = np.asarray(canonical_logits, dtype=np.float64)
        if raw.shape != self.mean.shape or base.shape != (3,) or not np.isfinite(raw).all() or not np.isfinite(base).all():
            raise ValueError('Invalid inference-only head input')
        scores = base - base.mean() + ((raw - self.mean) / self.scale) @ self.weights
        distribution = softmax(scores[None, :])[0]
        return {name: float(distribution[index]) for index, name in enumerate(FEATURES.CLASSES)}
