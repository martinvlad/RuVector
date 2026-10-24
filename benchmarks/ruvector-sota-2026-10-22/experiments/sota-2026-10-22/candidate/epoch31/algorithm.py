"""E31 inference identities; E30 training recipe remains immutable provenance."""
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / 'epoch30'
OLD_ALGORITHM_SHA = 'a6db5363122add0f3fde2ed2dc2667fa94e349f3d4f9dffb8bca54f3927a3fa9'
if hashlib.sha256((LEGACY/'algorithm.py').read_bytes()).hexdigest() != OLD_ALGORITHM_SHA:
    raise ValueError('Exact archived training algorithm source required')
_spec = importlib.util.spec_from_file_location('epoch31_archived_training30_algorithm', LEGACY/'algorithm.py')
_archived = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_archived)
KIND = 'REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
TRAIN_DOCUMENT_IDS = ()
DEV_DOCUMENT_IDS = (145, 597, 191, 620, 254, 160, 384, 571)
HISTORICAL_TRAIN_DOCUMENT_IDS = _archived.TRAIN_DOCUMENT_IDS
HYPOTHESIS_IDS = _archived.HYPOTHESIS_IDS
DEV_CASE_IDS = tuple(f'original-contractnli:train:epoch31:dev:{document}:{hypothesis}'
    for document in DEV_DOCUMENT_IDS for hypothesis in HYPOTHESIS_IDS)
ARCHIVED_TRAINING_ALGORITHM = _archived.ALGORITHM
ARCHIVED_SOURCE_PLAN_SHA = 'd6c46944bbac2cb8ef65a51e68d927e10b869123004f941d56292cef1e0bd94b'
ARCHIVED_TRAIN_INPUTS_SHA = 'bf1eff95845e301b56abd1a5284df0dcbbf531b952ea4dd1d89351fef845570a'
ARTIFACT_SHA = '46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'
ARTIFACT_BYTES = 5950520
BASE_MODEL = _archived.BASE_MODEL
INFERENCE_CONTRACT = {'original_native_forwards_before_artifact_tensor_decode':24,
    'adapted_native_lexical_positional_forwards':72,'BART_initializations':1,
    'BGE_initializations':1,'native_indexes':8,'native_queries':24,
    'training_steps':0,'fits':0,'calibration_calls':0,'generation_calls':0,
    'full104_requests':0,'paid_calls':0,'GPU_calls':0,
    'precision':'CPU float32','temperature':1.0,
    'scope':'First held-out measurement of one fixed E30 learned state; no new backbone or quality claim.'}
