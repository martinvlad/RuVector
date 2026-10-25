"""E40 frozen science constants; no input/model side effects."""
EPOCH=40
KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT'
PHASE='dev'
SOURCE='2cf5aba60a050079506a5e9aa5463f44c1efcd5a'
ROOT_CONTRACT_SHA='d0d66dc8a71bf68204463aa8b85f01bcc00217fc5c74854fe3749088e6d5a68a'
ROOT_CONTRACT_PATH='experiments/sota-2026-10-22/epoch40/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
ARMS=('tasksource_source_order','tasksource_native','tasksource_lexical','b354_source_order')
MODEL_ORDER=('b354','tasksource')
MODEL_ARMS={'b354':('b354_source_order',),'tasksource':ARMS[:3]}
CANONICAL_FROM_RAW={'b354':[1,0,2],'tasksource':[1,0,2]}
NATIVE_LABELS={'b354':('Entailment','NotMentioned','Contradiction'),'tasksource':('Entailment','NotMentioned','Contradiction')}
LABELS=('NotMentioned','Entailment','Contradiction')
PRIMARY='tasksource_native'
JOINT_CAP=512
BGE_CAP=256
MAX_UNITS=1024
