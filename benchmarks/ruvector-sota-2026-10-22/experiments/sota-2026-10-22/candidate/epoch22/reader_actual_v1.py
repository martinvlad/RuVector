"""Prefreeze provenance split; loading/inference in the held reader is unchanged."""
import copy
from pathlib import Path
from reader import Reader as BaseReader, state_identity


def actual_architecture(model, source: dict) -> dict:
    """Read actual loaded structure; source storage dtype remains separate."""
    expected = {k: copy.deepcopy(v) for k, v in source.items() if k != 'torch_dtype'}
    actual = {}
    for key, value in expected.items():
        got = type(model).__name__ if key == 'architecture' else getattr(model.config, key, None)
        if type(got) is not type(value) or got != value:
            raise ValueError('Actual loaded model structure differs from qualified source config: ' + key)
        actual[key] = copy.deepcopy(got)
    labels = {str(k): str(v).casefold() for k, v in model.config.id2label.items()}
    if labels != {'0': 'entailment', '1': 'neutral', '2': 'contradiction'} or model.config.num_labels != 3:
        raise ValueError('Actual loaded model config must retain original three-class label semantics')
    actual['num_labels'] = model.config.num_labels
    return {'source_config_architecture': copy.deepcopy(source), 'architecture': actual,
            'actual_model_config_declared_dtype': str(getattr(model.config, 'torch_dtype', None)),
            'config_dtype_scope': 'Descriptive model.config value only; actual parameter/buffer inventories and original value comparison prove computation and source storage precision.'}


class Reader(BaseReader):
    def __init__(self, folder: Path, counters: dict, progress=None, *, plan: dict, output_folder: Path):
        super().__init__(folder, counters, progress, plan=plan, output_folder=output_folder)
        source = self.receipt['architecture']
        revised = actual_architecture(self.model, source)
        self.receipt.update(revised)
        self.receipt['provenance_adapter_scope'] = (
            'Only source-versus-actual architecture labels are split before measurement. '
            'No model load, parameter, tokenizer, forward, probability, context, counter, budget or gate is changed.'
        )

