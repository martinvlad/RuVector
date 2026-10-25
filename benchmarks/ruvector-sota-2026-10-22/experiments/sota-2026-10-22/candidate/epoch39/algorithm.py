"""E39 frozen science constants; no input/model side effects."""
EPOCH=39
KIND='REAL_FINFACT_DEV_TRANSFER_PILOT'
PHASE='dev'
SOURCE='74dbbcb10508ced7e0edf53a0c736f14c19a19a1'
ROOT_CONTRACT_SHA='53739509c0c324d9e10560f1e2d8edd3d1dc6f3ca619dbb5a604a4a0cc31bbda'
ROOT_CONTRACT_PATH='experiments/sota-2026-10-22/epoch39/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json'
ARMS=('b354_source_order','b354_native','b354_lexical','xxlarge_source_order')
MODEL_ORDER=('xxlarge','b354')
MODEL_ARMS={'xxlarge':('xxlarge_source_order',),'b354':ARMS[:3]}
CANONICAL_FROM_RAW={'b354':[0,2,1],'xxlarge':[2,0,1]}
NATIVE_LABELS={'b354':('true','neutral','false'),'xxlarge':('false','neutral','true')}
LABELS=('true','false','neutral')
PRIMARY='b354_native'
JOINT_CAP=248
BGE_CAP=256
MAX_UNITS=256
