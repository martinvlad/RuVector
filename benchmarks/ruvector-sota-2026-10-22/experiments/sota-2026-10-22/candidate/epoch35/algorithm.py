"""Frozen metadata identities; standard library only, no model initialization."""
KIND='ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS'
SOURCE='4d51073072c428b58685e5498337bfdece6aac9b'
DEV_DOCUMENT_IDS=()
HYPOTHESIS_IDS=tuple(f'e35-h{i:02}' for i in range(1,13))
ENG_DOCUMENT_IDS=tuple(range(-35001,-35013,-1))
ENG_CASE_IDS=tuple(f'epoch35:cc0:numeric-scope:{i:02}' for i in range(1,13))
DEV_CASE_IDS=()
LABELS_NATIVE=('Entailment','NotMentioned','Contradiction')
LABELS_CANONICAL=('Entailment','Contradiction','NotMentioned')
REPOSITORY='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
WEIGHT_BYTES=870182606
MODEL_DIRECTORY='/workspace/ruvector-e35-reader-assets/moritz-b3546ea6'
ARMS=('actual_native','native_original','lexical','positional')
