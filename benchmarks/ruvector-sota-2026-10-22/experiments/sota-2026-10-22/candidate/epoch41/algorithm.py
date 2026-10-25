"""E41 fixed same-model context-window experiment; no input/model side effects."""
EPOCH=41
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PHASE='dev'
SOURCE='7a40daab6ad7caf9310f678813bfef42f907bd17'
ROOT_CONTRACT_SHA='fef319ea3f05753a59fffebd9c0ed94692bc1175b105eb99331b3ac515b9b207'
ROOT_CONTRACT_PATH='experiments/sota-2026-10-22/epoch41/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
ARMS=('tasksource_native_two_windows','tasksource_lexical_two_windows','tasksource_source_order_two_windows')
MODEL_ORDER=('tasksource',)
MODEL_ARMS={'tasksource':ARMS}
CANONICAL_FROM_RAW={'tasksource':[1,0,2]}
NATIVE_LABELS={'tasksource':('Entailment','NotMentioned','Contradiction')}
LABELS=('NotMentioned','Entailment','Contradiction')
PRIMARY=ARMS[0]
JOINT_CAP=512
BGE_CAP=256
MAX_UNITS=1024
WINDOWS_PER_ARM=2
