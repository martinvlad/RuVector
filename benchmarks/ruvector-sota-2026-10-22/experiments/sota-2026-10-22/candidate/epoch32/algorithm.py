"""Frozen metadata identities; standard library only, no model initialization."""
KIND='REAL_NATIVE_TASKSOURCE_PRETRAINED_NLI_DIAGNOSTIC'
SOURCE='f8bcbc4ca7ec31c6732159cad60a6e223f93c539'
DEV_DOCUMENT_IDS=(557,184,34,404,578,246,242,448)
HYPOTHESIS_IDS=('nda-17','nda-7','nda-3')
ENG_DOCUMENT_IDS=tuple(range(-32001,-32007,-1))
ENG_CASE_IDS=tuple(f'epoch32:cc0:engineering:{i}' for i in range(1,7))
DEV_CASE_IDS=tuple(f'original-contractnli:train:epoch32:dev:{d}:{h}' for d in DEV_DOCUMENT_IDS for h in HYPOTHESIS_IDS)
LABELS_NATIVE=('Entailment','NotMentioned','Contradiction')
LABELS_CANONICAL=('Entailment','Contradiction','NotMentioned')
REPOSITORY='sileod/deberta-v3-large-tasksource-nli'
REVISION='212de447184bda8fb9415a2e5697846864ddf304'
WEIGHT_SHA='534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc'
WEIGHT_BYTES=1740312738
MODEL_DIRECTORY='/workspace/ruvector-e32-reader-assets/tasksource-212de447'
ARMS=('actual_native','lexical','positional')
