"""Frozen metadata identities; standard library only, no model initialization."""
KIND='REAL_NATIVE_TYPED_MODAL_RETRIEVAL_NLI_DIAGNOSTIC'
SOURCE='0522a2c521c92c55d843d21c71495a44b43977e5'
DEV_DOCUMENT_IDS=(91,427,299,439,513,268,583,402)
HYPOTHESIS_IDS=('nda-17','nda-7','nda-3')
ENG_DOCUMENT_IDS=tuple(range(-32001,-32007,-1))
ENG_CASE_IDS=tuple(f'epoch32:cc0:engineering:{i}' for i in range(1,7))
DEV_CASE_IDS=tuple(f'original-contractnli:train:epoch33:dev:{d}:{h}' for d in DEV_DOCUMENT_IDS for h in HYPOTHESIS_IDS)
LABELS_NATIVE=('Entailment','NotMentioned','Contradiction')
LABELS_CANONICAL=('Entailment','Contradiction','NotMentioned')
REPOSITORY='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
WEIGHT_BYTES=870182606
MODEL_DIRECTORY='/workspace/ruvector-e33-reader-assets/moritz-b3546ea6'
ARMS=('actual_native','native_original','lexical','positional')
