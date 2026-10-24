"""Frozen E32 pretrained tasksource NLI SOURCE/FINAL publication schema."""
P='experiments/sota-2026-10-22/'
E=P+'epoch32/'
KIND='REAL_NATIVE_TASKSOURCE_PRETRAINED_NLI_DIAGNOSTIC'
ROLES={'train':[],'dev':[557,184,34,404,578,246,242,448],'calibration':[],'confirmation':[]}
HYPOTHESES=['nda-17','nda-7','nda-3']
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None}
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
MODEL_SOURCE_PATH=P+'candidate/epoch32/PRETRAINED_MODEL_SOURCE.json'
MODEL_REPOSITORY='sileod/deberta-v3-large-tasksource-nli'
MODEL_REVISION='212de447184bda8fb9415a2e5697846864ddf304'
MODEL_WEIGHTS={'file':'model.safetensors','bytes':1740312738,'sha256':'534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc'}
PHASE_RESERVATIONS={'dev':E+'DEV_ATTEMPT_RESERVATION.json'}
FINAL_STATUSES={'DEV_DIAGNOSTIC_QUALIFIED','REJECTED_DEV_DIAGNOSTIC','ENGINEERING_REJECTED_DEV_NOT_STARTED'}
DISPATCH_PATHS={key:E+name for key,name in {'reservation':'DISPATCH_RESERVATION.json','attempt':'DISPATCH_ATTEMPT.json','completion':'SUPERVISOR_COMPLETION.json','closure':'SUPERVISOR_OBSERVED_CLOSURE.json'}.items()}
BOOT_ID='4632fb06-b0ef-4df5-b72b-0e875bbad810'
PID_NAMESPACE=4026532200
CLOSURE_KEYS={'schema_version','epoch','kind','phase','source_plan_sha256','kernel_boot_id','pid_namespace_inode','dispatch_reservation','dispatch_attempt','supervisor_completion','execution','supervisor_identity','physical_supervisor_absent','observed_supervisor_state','physical_supervisor_closed','owned_worker_group_members','unknown_physical_ownership','physical_closure_passed'}

CORPUS_RESERVATION_PATHS={role:E+'runs/dev/'+name for role,name in {'engineering':'ENGINEERING_CORPUS_ATTEMPT_RESERVATION.json','dev':'DEV_CORPUS_ATTEMPT_RESERVATION.json'}.items()}
