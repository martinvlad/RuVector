"""Fixed document-crossfitted annotation proxy and residual three-way readout."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch10_features', HERE / 'features.py')
FEATURES = importlib.util.module_from_spec(spec); spec.loader.exec_module(FEATURES)
ARMS = ('ruvector_top2', 'lexical_top2', 'positional_first2')
ALGORITHM = {'optimizer': 'full_batch_Adam_float64', 'steps': 400, 'learning_rate': .03,
             'beta1': .9, 'beta2': .999, 'epsilon': 1e-8, 'residual_l2': .1,
             'scale_floor': .1, 'final_gradient_norm_max': 1e-3,
             'final_vs_initial_objective_tolerance': 1e-8,
             'auxiliary': 'weighted_binary_logistic_annotation_overlap+L2;3documentOOFfits+oneallTRAINfit',
             'target': 'any positive annotated source-character overlap; no annotation=>0; NOT sufficiency/absence proof',
             'decision': 'canonical_centered_raw_logits+linear_residual(role_features,OOF_aux_probability)',
             'folds': '24groups sortedbySHA256(fullsource),3contiguous8groupfolds; heldoutdoc excluded from auxnorm/fit',
             'sample_weight': 'Eachquestion total1 across3views; eachview1/3',
             'calibration': False, 'threshold_fit': False, 'early_stop': False}


class FitFailure(ValueError):
    def __init__(self, message, diagnostics):
        super().__init__(message); self.diagnostics = diagnostics


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def softmax(logits):
    a = np.asarray(logits, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 3 or not np.isfinite(a).all():
        raise ValueError('Finite threeway logits required')
    e = np.exp(a - a.max(axis=1, keepdims=True)); return e / e.sum(axis=1, keepdims=True)


def sigmoid(values):
    a = np.asarray(values, dtype=np.float64)
    return np.exp(-np.logaddexp(0., -a))


def collect(records, allowlist, annotations):
    if (allowlist.get('role') != 'train' or allowlist.get('queries') != 72 or allowlist.get('document_groups') != 24
            or tuple(allowlist.get('threeway_classes', [])) != FEATURES.CLASSES):
        raise ValueError('Exact TRAIN72/24-group contract required')
    admitted = {x['id']: x for x in allowlist['records']}
    annotation_rows = annotations['records']
    evidence = {x['id']: x for x in annotation_rows}
    if (annotations.get('role') != 'train' or annotations.get('queries') != 72 or len(evidence) != 72
            or len(annotation_rows) != 72 or set(evidence) != set(admitted)
            or len(records) != 72 or len(admitted) != 72 or {x['id'] for x in records} != set(admitted)):
        raise ValueError('Exact TRAIN-only identity set required for records and annotations')
    result = []
    for row in sorted(records, key=lambda x: x['id']):
        expected, annotation = admitted[row['id']], evidence[row['id']]
        if (row.get('split') != 'train' or row['input_sha256'] != expected['input_sha256']
                or hashlib.sha256(canonical(row['input'])).hexdigest() != expected['input_sha256']
                or row['source_group'] != expected['source_group']
                or row['provenance']['hypothesis_id'] != expected['hypothesis_id']):
            raise ValueError('Unknown/non-TRAIN or changed input/source identity')
        state = row['input']['state']; state_sha = hashlib.sha256(state.encode()).hexdigest()
        label = row['evaluation']['original_threeway_label']
        if label not in FEATURES.CLASSES or row['evaluation']['gold'] != ('Yes' if label == 'Entailment' else 'No'):
            raise ValueError('Original three-way and binary labels disagree')
        if (annotation['input_sha256'] != expected['input_sha256'] or annotation['source_group'] != row['source_group']
                or annotation['original_threeway_label'] != label or annotation['source_document_sha256'] != state_sha):
            raise ValueError('TRAIN annotation source/target identity mismatch')
        gold = annotation['evidence_spans']
        if any(len(pair) != 2 or any(type(v) is not int for v in pair) or not 0 <= pair[0] < pair[1] <= len(state) for pair in gold):
            raise ValueError('Invalid source annotation offsets')
        if label == 'NotMentioned' and gold:
            raise ValueError('NotMentioned source has no positive evidence spans in this contract')
        hypothesis = row['input']['questions']['decision']['criteria']['Yes']
        diagnostic = row['response']['diagnostics']['decision']
        if diagnostic['source_state_sha256'] != state_sha:
            raise ValueError('Cached source text differs')
        for arm in ARMS:
            obs = diagnostic['arms'][arm]; trace = obs['decoding']; raw_logits = trace['logits']
            logits = [float(raw_logits[i]) for i in (0, 2, 1)]
            if (trace['typed_head_state'] != 'TRAIN_COLLECTION' or trace['typed_head_feature_names'] != list(FEATURES.FEATURE_NAMES)
                    or trace['typed_head_canonical_logits'] != logits or obs['hypothesis'] != hypothesis):
                raise ValueError('Only exact raw E0/N1/C2 TRAIN-collection traces accepted')
            spans = obs['coverage']['selected_source_spans']
            if any(len(pair) != 2 or any(type(v) is not int for v in pair) or not 0 <= pair[0] < pair[1] <= len(state) for pair in spans):
                raise ValueError('Invalid selected source spans')
            if obs['premise'] != '\n\n'.join(state[a:b] for a, b in spans):
                raise ValueError('Cached premise differs from selected source offsets')
            features = FEATURES.extract(obs['premise'], hypothesis, logits)
            if features != trace['typed_head_features']:
                raise ValueError('Inference-only features do not replay')
            overlap = float(any(max(a, c) < min(b, d) for a, b in spans for c, d in gold))
            result.append({'id': row['id'], 'source_group': row['source_group'], 'source_text_sha256': state_sha,
                           'input_sha256': expected['input_sha256'], 'arm': arm, 'weight': 1 / 3,
                           'original_threeway_label': label, 'canonical_logits': logits,
                           'features': features, 'annotation_overlap_target': overlap})
    if len({x['source_group'] for x in result}) != 24 or {x['original_threeway_label'] for x in result} != set(FEATURES.CLASSES):
        raise ValueError('Expected24groups and all3classes; no fallback')
    return result


def objective(weights, x, base, y, sample_weight):
    scores = base + x @ weights
    maximum = scores.max(axis=1)
    nll = maximum + np.log(np.exp(scores - maximum[:, None]).sum(axis=1)) - scores[np.arange(len(y)), y]
    loss = float(sample_weight @ nll / sample_weight.sum() + .5 * ALGORITHM['residual_l2'] * np.square(weights).sum())
    delta = softmax(scores); delta[np.arange(len(y)), y] -= 1
    grad = x.T @ (delta * sample_weight[:, None]) / sample_weight.sum() + ALGORITHM['residual_l2'] * weights
    return loss, grad


def aux_objective(weights, x, target, sample_weight):
    scores = x @ weights
    nll = np.logaddexp(0., scores) - target * scores
    loss = float(sample_weight @ nll / sample_weight.sum() + .5 * ALGORITHM['residual_l2'] * np.square(weights).sum())
    grad = x.T @ ((sigmoid(scores) - target) * sample_weight) / sample_weight.sum() + ALGORITHM['residual_l2'] * weights
    return loss, grad


def normalize_fit(raw, sample_weight):
    mean = np.average(raw, weights=sample_weight, axis=0)
    scale = np.maximum(np.sqrt(np.average(np.square(raw - mean), weights=sample_weight, axis=0)), ALGORITHM['scale_floor'])
    mean[0] = 0.; scale[0] = 1.
    return mean, scale


def optimize(shape, fn, stage):
    weights = np.zeros(shape, dtype=np.float64); m = np.zeros_like(weights); v = np.zeros_like(weights)
    initial, initial_gradient = fn(weights); history = []
    if not np.isfinite(initial) or not np.isfinite(initial_gradient).all():
        raise FitFailure('Nonfinite initial objective; no retry', {'stage': stage, 'steps_completed': 0,
                         'initial_objective': float(initial) if np.isfinite(initial) else str(initial),
                         'history': [], 'last_finite_weights': weights.tolist(), 'failure_position': 'initial_objective'})
    last_finite_weights = weights.copy()
    for step in range(1, ALGORITHM['steps'] + 1):
        loss, gradient = fn(weights)
        if not np.isfinite(loss) or not np.isfinite(gradient).all():
            raise FitFailure('Nonfinite fixed optimizer; no retry', {'stage': stage, 'step': step,
                             'steps_completed': step - 1, 'initial_objective': initial, 'history': history,
                             'last_finite_weights': last_finite_weights.tolist(),
                             'failure_position': 'objective_or_gradient', 'fixed_acceptance_criteria_passed': False})
        m = ALGORITHM['beta1'] * m + (1 - ALGORITHM['beta1']) * gradient
        v = ALGORITHM['beta2'] * v + (1 - ALGORITHM['beta2']) * np.square(gradient)
        weights -= ALGORITHM['learning_rate'] * (m / (1 - ALGORITHM['beta1'] ** step)) / (np.sqrt(v / (1 - ALGORITHM['beta2'] ** step)) + ALGORITHM['epsilon'])
        history.append({'step': step, 'objective_before_step': loss, 'gradient_norm_before_step': float(np.linalg.norm(gradient))})
        if not np.isfinite(weights).all():
            raise FitFailure('Nonfinite fixed optimizer update; no retry', {'stage': stage, 'step': step,
                             'steps_completed': step, 'initial_objective': initial, 'history': history,
                             'last_finite_weights': last_finite_weights.tolist(), 'failure_position': 'weight_update',
                             'fixed_acceptance_criteria_passed': False})
        last_finite_weights = weights.copy()
    final, gradient = fn(weights); norm = float(np.linalg.norm(gradient))
    diagnostic = {'stage': stage, 'initial_objective': initial,
                  'final_objective': float(final) if np.isfinite(final) else str(final),
                  'final_gradient_norm': norm if np.isfinite(norm) else str(norm),
                  'steps_completed': ALGORITHM['steps'], 'history': history,
                  'last_finite_weights': last_finite_weights.tolist(),
                  'fixed_acceptance_criteria_passed': bool(np.isfinite(final) and np.isfinite(norm) and np.isfinite(weights).all()
                     and final <= initial + ALGORITHM['final_vs_initial_objective_tolerance'] and norm <= ALGORITHM['final_gradient_norm_max'])}
    if not diagnostic['fixed_acceptance_criteria_passed']:
        raise FitFailure('Fixed objective/gradient acceptance failed; no fallback/extra steps', diagnostic)
    return weights, diagnostic


def fit_aux(raw, target, sample_weight, stage):
    mean, scale = normalize_fit(raw, sample_weight); x = (raw - mean) / scale
    try:
        weights, diagnostic = optimize((raw.shape[1],), lambda w: aux_objective(w, x, target, sample_weight), stage)
    except FitFailure as failure:
        failure.diagnostics['normalization'] = {'mean': mean.tolist(), 'scale': scale.tolist(),
                                               'fit_examples': len(raw), 'fit_total_weight': float(sample_weight.sum())}
        raise
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': weights.tolist(), 'fit_diagnostics': diagnostic}


def predict_aux(model, raw):
    return sigmoid(((np.asarray(raw) - np.asarray(model['mean'])) / np.asarray(model['scale'])) @ np.asarray(model['weights']))


def parameters_digest(a):
    fields = ('class_order', 'feature_names', 'mean', 'scale', 'weights', 'auxiliary_final', 'auxiliary_folds', 'fold_assignment', 'oof_probabilities')
    return hashlib.sha256(canonical({k: a[k] for k in fields})).hexdigest()


def fit(records, allowlist, config_sha256, allowlist_sha256, model_identity, annotations, annotations_sha256):
    examples = collect(records, allowlist, annotations)
    raw = np.asarray([x['features'] for x in examples], dtype=np.float64)
    base = np.asarray([x['canonical_logits'] for x in examples], dtype=np.float64); base -= base.mean(axis=1, keepdims=True)
    y = np.asarray([FEATURES.CLASSES.index(x['original_threeway_label']) for x in examples])
    target = np.asarray([x['annotation_overlap_target'] for x in examples]); sw = np.asarray([x['weight'] for x in examples])
    if raw.shape != (216, len(FEATURES.FEATURE_NAMES)) or not np.isfinite(raw).all():
        raise ValueError('Expected216finite TRAIN views')
    group_sources = {}
    for x in examples:
        old = group_sources.setdefault(x['source_group'], x['source_text_sha256'])
        if old != x['source_text_sha256']:
            raise ValueError('One document group must have one fullsource hash')
    groups = sorted(group_sources, key=lambda g: (group_sources[g], str(g)))
    assignment = {g: i // 8 for i, g in enumerate(groups)}
    oof = np.full(len(raw), np.nan); folds = []
    final_aux = None; active_stage = None; main_normalization = None
    try:
        for fold in range(3):
            held = np.asarray([assignment[x['source_group']] == fold for x in examples]); fitted = ~held
            active_stage = {'stage': 'coverage_fold_' + str(fold), 'training_groups': [g for g in groups if assignment[g] != fold], 'heldout_groups': [g for g in groups if assignment[g] == fold]}
            model = fit_aux(raw[fitted], target[fitted], sw[fitted], 'coverage_fold_' + str(fold))
            oof[held] = predict_aux(model, raw[held])
            model.update(fold=fold, training_groups=[g for g in groups if assignment[g] != fold], heldout_groups=[g for g in groups if assignment[g] == fold], training_examples=int(fitted.sum()), heldout_examples=int(held.sum()))
            folds.append(model)
        if not np.isfinite(oof).all():
            raise ValueError('Every TRAINview must get exactly one heldout-document aux probability')
        active_stage = {'stage': 'coverage_allTRAIN', 'training_groups': groups, 'heldout_groups': []}
        final_aux = fit_aux(raw, target, sw, 'coverage_allTRAIN')
        augmented = np.column_stack((raw, oof)); mean, scale = normalize_fit(augmented, sw); x = (augmented - mean) / scale
        active_stage = {'stage': 'threeway_residual_OOFcoverage', 'training_groups': groups, 'heldout_groups': []}
        main_normalization = {'mean': mean.tolist(), 'scale': scale.tolist()}
        weights, diagnostic = optimize((x.shape[1], 3), lambda w: objective(w, x, base, y, sw), 'threeway_residual_OOFcoverage')
        artifact = {'schema_version': 1, 'state': 'FROZEN', 'class_order': list(FEATURES.CLASSES),
                    'feature_names': list(FEATURES.FEATURE_NAMES), 'config_sha256': config_sha256,
                    'train_allowlist_sha256': allowlist_sha256, 'annotations_sha256': annotations_sha256,
                    'model_identity': model_identity, 'feature_source_sha256': sha(HERE / 'features.py'), 'trainer_source_sha256': sha(__file__),
                    'algorithm': ALGORITHM, 'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': weights.tolist(),
                    'auxiliary_final': final_aux, 'auxiliary_folds': folds, 'fold_assignment': assignment,
                    'oof_probabilities': oof.tolist(), 'training_questions': 72, 'training_document_groups': 24,
                    'training_arm_examples': 216, 'training_total_weight': float(sw.sum()), 'training_examples': examples,
                    'training_class_question_counts': {c: sum(r['evaluation']['original_threeway_label'] == c for r in records) for c in FEATURES.CLASSES},
                    'fit_diagnostics': diagnostic, 'fit_boundary': 'TRAIN72 only; no DEV/CONF fit, normalization, thresholds or calibration',
                    'auxiliary_limits': 'Annotation overlap is a weak training proxy, NOT sufficiency/absence proof. Decisionhead trains on OOF auxiliary probabilities; inference uses allTRAIN auxiliary fit, a disclosed distribution shift.'}
        artifact['parameters_sha256'] = parameters_digest(artifact); return artifact
    except FitFailure as failure:
        failure.diagnostics["completed_auxiliary_fits"] = folds + ([final_aux] if final_aux is not None else [])
        failure.diagnostics['pipeline_progress'] = {'active_stage': active_stage, 'fold_assignment': assignment,
            'oof_probabilities': [float(value) if np.isfinite(value) else None for value in oof],
            'main_normalization': main_normalization, 'completed_auxiliary_count': len(folds) + int(final_aux is not None)}
        raise



class FrozenHead:
    def __init__(self, a, config_sha256, allowlist_sha256, model_identity):
        if (a.get('state') != 'FROZEN' or a.get('config_sha256') != config_sha256 or a.get('train_allowlist_sha256') != allowlist_sha256
                or a.get('model_identity') != model_identity or a.get('class_order') != list(FEATURES.CLASSES)
                or a.get('feature_names') != list(FEATURES.FEATURE_NAMES) or a.get('algorithm') != ALGORITHM
                or a.get('feature_source_sha256') != sha(HERE / 'features.py') or a.get('trainer_source_sha256') != sha(__file__)
                or a.get('parameters_sha256') != parameters_digest(a)):
            raise ValueError('Frozen source/config/parameter integrity mismatch')
        self.artifact = a; self.mean = np.asarray(a['mean']); self.scale = np.asarray(a['scale']); self.weights = np.asarray(a['weights'])
        width = len(FEATURES.FEATURE_NAMES)
        if self.mean.shape != (width + 1,) or self.scale.shape != (width + 1,) or self.weights.shape != (width + 1, 3):
            raise ValueError('Invalid decision-head dimensions')
        models = a['auxiliary_folds'] + [a['auxiliary_final']]
        if len(models) != 4 or a.get('training_questions') != 72 or a.get('training_document_groups') != 24 or a.get('training_arm_examples') != 216 or abs(a.get('training_total_weight', 0) - 72) > 1e-9:
            raise ValueError('Invalid TRAIN/fold contract')
        for model in models:
            if np.asarray(model['mean']).shape != (width,) or np.asarray(model['scale']).shape != (width,) or np.asarray(model['weights']).shape != (width,):
                raise ValueError('Invalid auxiliary dimensions')
        for model in a['auxiliary_folds']:
            if len(model['training_groups']) != 16 or len(model['heldout_groups']) != 8 or set(model['training_groups']) & set(model['heldout_groups']):
                raise ValueError('Crossfit document exclusion violated')
        for mean, scale, weights in [(self.mean, self.scale, self.weights)] + [(np.asarray(m['mean']), np.asarray(m['scale']), np.asarray(m['weights'])) for m in models]:
            if not all(np.isfinite(v).all() for v in (mean, scale, weights)) or np.any(scale <= 0) or mean[0] != 0 or scale[0] != 1:
                raise ValueError('Invalid fitted statistics/weights')
        for d in [a['fit_diagnostics']] + [m['fit_diagnostics'] for m in models]:
            if (len(d['history']) != ALGORITHM['steps'] or d.get('fixed_acceptance_criteria_passed') is not True
                    or not np.isfinite(d['final_objective']) or not np.isfinite(d['final_gradient_norm'])
                    or d['final_gradient_norm'] > ALGORITHM['final_gradient_norm_max']
                    or d['final_objective'] > d['initial_objective'] + ALGORITHM['final_vs_initial_objective_tolerance']):
                raise ValueError('Missing frozen acceptance evidence for one of five fits')

    def coverage(self, features):
        return float(predict_aux(self.artifact['auxiliary_final'], np.asarray(features)))

    def predict(self, features, canonical_logits):
        raw = np.asarray(features, dtype=np.float64); base = np.asarray(canonical_logits, dtype=np.float64)
        if raw.shape != (len(FEATURES.FEATURE_NAMES),) or base.shape != (3,) or not np.isfinite(raw).all() or not np.isfinite(base).all():
            raise ValueError('Invalid inference-only feature/logit input')
        augmented = np.r_[raw, self.coverage(raw)]
        distribution = softmax((base - base.mean() + ((augmented - self.mean) / self.scale) @ self.weights)[None, :])[0]
        return {c: float(distribution[i]) for i, c in enumerate(FEATURES.CLASSES)}
