"""E42 fixed same-model context-window experiment; no input/model side effects."""
EPOCH=42
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PHASE='dev'
SOURCE='222874558c0b696f92824e5fce3775494877f821'
ROOT_CONTRACT_SHA='83e7117e336a12497c994aea25f273e3f80456df6373c5d97510ac2936ffd6e2'
ROOT_CONTRACT_PATH='experiments/sota-2026-10-22/epoch42/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
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
