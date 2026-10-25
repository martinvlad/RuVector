"""E39 publication-only contract. Scientific decisions live in frozen ROOT/scorer."""
P='experiments/sota-2026-10-22/'
E=P+'epoch39/'
KIND='REAL_FINFACT_DEV_TRANSFER_PILOT'
PHASE='dev'
ARMS=['b354_source_order','b354_native','b354_lexical','xxlarge_source_order']
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None,'benchmark_generalization_claim':False}
STATUSES={'ACCEPTED_DEV_PILOT_ONLY','REJECTED_DEV_PILOT','REJECTED_DEV_INTEGRITY'}
LIMITS={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'native_queries':12,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'calibration_worker_attempts':0,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0,'retries':0}
REMAINING=dict.fromkeys(('train','dev','calibration','confirmation','native_corpus_batches','paid_calls','GPU_calls','retries'),0)
REQUIRED_REFS={'protocol','scorer','data_access','blind_id_policy','external_data_manifest','model_assets_admission','runtime_assets'}
