"""Frozen metadata identities; standard library only, no model initialization."""
KIND='REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC'
SOURCE='047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
DEV_DOCUMENT_IDS=(434,367,247,377,220,457,169,449)
HYPOTHESIS_IDS=('nda-17','nda-7','nda-3')
ENG_DOCUMENT_IDS=tuple(range(-32001,-32007,-1))
ENG_CASE_IDS=tuple(f'epoch32:cc0:engineering:{i}' for i in range(1,7))
DEV_CASE_IDS=tuple(f'original-contractnli:train:epoch34:dev:{d}:{h}' for d in DEV_DOCUMENT_IDS for h in HYPOTHESIS_IDS)
LABELS_NATIVE=('Entailment','NotMentioned','Contradiction')
LABELS_CANONICAL=('Entailment','Contradiction','NotMentioned')
REPOSITORY='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
WEIGHT_BYTES=870182606
MODEL_DIRECTORY='/workspace/ruvector-e34-reader-assets/moritz-b3546ea6'
ARMS=('actual_native','native_original','lexical','positional')
