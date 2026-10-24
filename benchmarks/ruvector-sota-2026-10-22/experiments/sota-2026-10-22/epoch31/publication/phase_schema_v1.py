"""Frozen E31 archived legal adaptation SOURCE/FINAL publication schema."""
P='experiments/sota-2026-10-22/'
E=P+'epoch31/'
KIND='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
ROLES={'train':[],'dev':[145,597,191,620,254,160,384,571],'calibration':[],'confirmation':[]}
HYPOTHESES=['nda-17','nda-7','nda-3']
HISTORICAL_TRAIN_IDS=[237,120,187,422,464,207,294,250]
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None}
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
ARCHIVED_SEAL_PATH=E+'ARCHIVED_MODEL_SEAL.json'
PHASE_RESERVATIONS={'dev':E+'DEV_ATTEMPT_RESERVATION.json'}
ARTIFACT_PATH=P+'epoch30/runs/train/trained-parameters.public.json'
ARCHIVED_SEAL_KEYS={'schema_version','epoch','kind','status','source_checkpoint','parameter_artifact','train_raw','train_execution','independent_training_report','original_source_plan','original_source_freeze','historical_training_epoch','historical_training_document_ids','data_roles','hypotheses'}
ARCHIVED_SOURCE_PATHS={'parameter_artifact':ARTIFACT_PATH,'train_raw':P+'epoch30/runs/train/raw.json','train_execution':P+'epoch30/runs/train/execution.json','independent_training_report':P+'audit/epoch30/train-integrity.json','original_source_plan':P+'epoch30/plan.json','original_source_freeze':P+'epoch30/source-freeze.json'}
FINAL_STATUSES={'DEV_DIAGNOSTIC_QUALIFIED','REJECTED_DEV_DIAGNOSTIC'}

DISPATCH_PATHS={key:E+name for key,name in {'reservation':'DISPATCH_RESERVATION.json','attempt':'DISPATCH_ATTEMPT.json','completion':'SUPERVISOR_COMPLETION.json','closure':'SUPERVISOR_OBSERVED_CLOSURE.json'}.items()}
BOOT_ID='4632fb06-b0ef-4df5-b72b-0e875bbad810'
PID_NAMESPACE=4026532200
CLOSURE_KEYS={'schema_version','epoch','kind','phase','source_plan_sha256','kernel_boot_id','pid_namespace_inode','dispatch_reservation','dispatch_attempt','supervisor_completion','execution','supervisor_identity','physical_supervisor_absent','observed_supervisor_state','physical_supervisor_closed','owned_worker_group_members','unknown_physical_ownership','physical_closure_passed'}
