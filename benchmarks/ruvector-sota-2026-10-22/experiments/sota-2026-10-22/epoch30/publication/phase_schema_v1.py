"""Prospectively fixed E30 source/model/final publication schema."""
P='experiments/sota-2026-10-22/'
E=P+'epoch30/'
KIND='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
ROLES={'train':[237,120,187,422,464,207,294,250],
       'dev':[594,343,394,103,403,481,154,306],
       'calibration':[],'confirmation':[]}
HYPOTHESES=['nda-17','nda-7','nda-3']
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,
       'official_SOTA_verified':False,'official_rank':None}
BASE_MODEL={'repository':'facebook/bart-large-mnli',
 'revision':'d7645e127eaf1aefc7862fd59a17a5aa8558b8ce','weights_file':'pytorch_model.bin',
 'weights_bytes':1629486723,'weights_sha256':'ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17',
 'pretrained_parameter_count':407344131}
MODULES=['model.decoder.layers.10.encoder_attn.q_proj',
 'model.decoder.layers.10.encoder_attn.v_proj',
 'model.decoder.layers.11.encoder_attn.q_proj',
 'model.decoder.layers.11.encoder_attn.v_proj']
TENSORS=[item for module in MODULES for item in
 ((module+'.lora_A',[4,1024]),(module+'.lora_B',[1024,4]))]+[
 ('classification_head.dense.weight',[1024,1024]),
 ('classification_head.dense.bias',[1024]),
 ('classification_head.out_proj.weight',[3,1024]),
 ('classification_head.out_proj.bias',[3])]
ARTIFACT_PATH=E+'runs/train/trained-parameters.public.json'
ARTIFACT_CODEC='epoch30-bart-crossattn-r4-f32le-v1'
MODEL_SEAL_PATH=E+'MODEL_SEAL.json'
MODEL_SEAL_KEYS={'schema_version','epoch','kind','status','base_model_sha256',
 'parameter_artifact','train_raw','train_execution','independent_training_report',
 'source_plan','source_freeze'}
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
PHASE_RESERVATIONS={phase:E+phase.upper()+'_ATTEMPT_RESERVATION.json' for phase in ('train','dev')}
TRAINING_STEPS=24
TRAINABLE_PARAMETERS=1085443
TRAINABLE_BYTES=4341772
