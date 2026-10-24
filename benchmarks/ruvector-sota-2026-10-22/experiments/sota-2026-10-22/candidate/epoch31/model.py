"""Thin source-pinned E30 model adapter; no artifact relabel or retraining."""
import hashlib
import importlib.util
from pathlib import Path

LEGACY = Path(__file__).resolve().parent.parent/'epoch30'
EXPECTED = {'model.py':'d2aa6ea5e1507458d454f76c7643bbeb2d25ca1620588939ec45823f168939fd',
    'algorithm.py':'a6db5363122add0f3fde2ed2dc2667fa94e349f3d4f9dffb8bca54f3927a3fa9',
    'parameter_codec.py':'03dc310a14acdf23e9494ba5d41b58f644e7d137177c344f5d4e012cdc03b42e'}
for name, digest in EXPECTED.items():
    if hashlib.sha256((LEGACY/name).read_bytes()).hexdigest()!=digest:
        raise ValueError('Archived model/codec/training source changed: '+name)
_spec=importlib.util.spec_from_file_location('epoch31_frozen_training30_model',LEGACY/'model.py')
_module=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_module)
LegalBartAdapter = _module.LegalBartAdapter
