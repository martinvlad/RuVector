"""One frozen three-way pretrained reader plus a train-only legal residual head."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch8_model_head', HERE / 'head.py')
HEAD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HEAD)


class TypedNli:
    def __init__(self, base):
        if set(base.label_indices) != {'entailment', 'contradiction', 'neutral'}:
            raise ValueError('Three pretrained E/C/N labels required; neutral cannot be discarded')
        self.base = base
        self.tokenizer = base.tokenizer
        self.fitted_head = None
        self.head_state = 'TRAIN_COLLECTION'
        self.receipt = {**copy.deepcopy(base.receipt), 'typed_class_order': list(HEAD.FEATURES.CLASSES),
                        'typed_feature_names': list(HEAD.FEATURES.FEATURE_NAMES),
                        'typed_head_state': self.head_state,
                        'typed_mapping': 'Yes=P(Entailment);No=P(Contradiction)+P(NotMentioned)',
                        'head': 'One train-only residual multinomial legal/deontic head; no grid or threshold fit'}
        self.receipt['pretrained_backbone_training_or_calibration_fit'] = self.receipt.pop('training_or_calibration_fit', False)
        self.receipt.update(typed_readout_training_fit=False, typed_readout_fit_scope='TRAIN72 only; no fit yet in TRAIN_COLLECTION')

    def freeze(self, fitted_head, artifact_sha256):
        if self.head_state not in ('TRAIN_COLLECTION', 'FITTING') or self.fitted_head is not None:
            raise ValueError('The typed head can be frozen only once')
        self.fitted_head = fitted_head
        self.head_state = 'FROZEN'
        self.receipt.update(typed_head_state='FROZEN', fitted_head_sha256=artifact_sha256,
                            typed_readout_training_fit=True, typed_readout_fit_scope='Exact TRAIN72 only; supervised residual head, pretrained backbone unchanged')

    def decode(self, premise, hypothesis):
        if self.head_state not in ('TRAIN_COLLECTION', 'FROZEN'):
            raise ValueError('Head is fitting/failed; inference fails closed before model execution')
        raw_binary, trace = self.base.decode(premise, hypothesis)
        logits = trace['logits']
        canonical = [float(logits[self.base.label_indices[name]])
                     for name in ('entailment', 'contradiction', 'neutral')]
        features = HEAD.FEATURES.extract(premise, hypothesis, canonical)
        distribution = HEAD.softmax([canonical])[0]
        raw = {name: float(distribution[index]) for index, name in enumerate(HEAD.FEATURES.CLASSES)}
        typed = self.fitted_head.predict(features, canonical) if self.fitted_head else raw
        result = {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}
        trace.update(typed_head_state=self.head_state,
                     typed_head_feature_names=list(HEAD.FEATURES.FEATURE_NAMES),
                     typed_head_features=features, typed_head_canonical_logits=canonical,
                     raw_threeway_probabilities=raw, typed_threeway_probabilities=typed,
                     typed_mapping='Yes=P(Entailment);No=P(Contradiction)+P(NotMentioned); no class removed',
                     typed_head_fit_scope='Exact frozen TRAIN72 only; no label/ID/split/selector features')
        return result, trace
