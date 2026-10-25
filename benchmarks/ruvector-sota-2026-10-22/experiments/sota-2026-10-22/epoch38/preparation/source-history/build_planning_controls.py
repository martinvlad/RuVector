from pathlib import Path
import json,copy,hashlib,os,time
W=Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f');D=W/'controls-lease';D.mkdir(mode=0o700)
P='experiments/sota-2026-10-22/'
source='7c50ba99848f6a13707eeec6c4947291a8478e5c'
prior=json.loads((W/'remote-current/CONTINUATION.json').read_text());oldactive=json.loads((W/'remote-current/ACTIVE_RUN.json').read_text());owner=json.loads((W/'owner.json').read_text())
assert prior['active_run']['work_active']is False and oldactive['work_active']is False and prior['goal_met']is False
assert hashlib.sha256((W/'remote-current/CHECKPOINT_MANIFEST.json').read_bytes()).hexdigest()==prior['checkpoint_manifest_sha256']=='c44f3d83ccc36288c1e144d06a1b10ca68c94ae952241cb44bfe402b7f15184a'
assert owner['run_id']==W.name and owner['expires_unix']>time.time()
active={'schema_version':1,'epoch':38,'run_id':W.name,'state':'EPOCH38_PLANNING_LEASE','work_active':True,'experiments_active':False,
 'checkpoint_parent':source,'scope':owner['scope'],'physical_owner':owner,'physical_guardian_directory':str(W),'isolated_project':str(W/'project'),
 'OS_lock_held':True,'OS_lock_release_pending':True,'native_allowed':0,'conditional_train_allowed':0,'conditional_dev_allowed':0,
 'conditional_engineering_allowed':0,'confirmation_allowed':0,'conditional_confirmation_allowed':0,
 'instruction':'Source preparation and cryptographic real-asset admission only. No model/tokenizer/native/candidate-case/scorer measurements before a reviewed frozen SOURCE commit and independent actual readback. New epoch38 only; never retry burned epoch37. No paid/GPU/TRAIN/DEV/calibration/CONF/promotion/new submission.'}
cont=copy.deepcopy(prior);cont['active_run']={**active,'path':'ACTIVE_RUN.json'};cont['prior_published_base_commit']=source
cont['epoch38_planning']={'epoch':38,'status':'SOURCE_PREPARATION_ONLY_NO_SCIENTIFIC_AUTHORIZATION','source_checkpoint':source,
 'scientific_authorization':0,'prepared_root_contract':{'path':P+'epoch38/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json','bytes':6846,'sha256':'226cd756b41c881e5131a175a470ac06c96ed158ffd9c5bc216d42b3cac41a67'},
 'hypothesis':'First real measured test of the generic source-bound numeric certificate mechanism with original stronger XXL typed-NLI reader and native coverage-preserving evidence on twelve new CC0 financial constraint compositions with distractors. Matched same-model full/native raw and lexical/full verified controls. Engineering only, no benchmark generalization.',
 'full_real_asset_guard_status':'LOCALLY_PASSED_ONCE_PENDING_DURABLE_SOURCE_FREEZE_INDEPENDENT_REVIEW','full_real_asset_guard_completed':True,
 'planned_limits':{'one_worker':1,'one_native_corpus':1,'CPU_threads':2,'seconds_total_init_cleanup':600,'real_NLI_readouts':36,'derived_forecasts':60,'native_queries':12,'fits_TRAIN_DEV_calibration_CONFIRMATION':0,'paid_GPU_calls':0,'retry':0},
 'training':[],'development':[],'calibration':[],'confirmation':[],'used_confirmation_identities':[],
 'model_lineage_and_eligibility':'HOLD','benchmark_accuracy':None,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,
 'preserve_E37_unknown_tail_and_frozen_false_rejection':True}
allowed={'active_run','prior_published_base_commit','epoch38_planning'}
assert all(cont[k]==v for k,v in prior.items()if k not in allowed)and set(cont)==set(prior)|{'epoch38_planning'}
assert cont['next_research_priority']==prior['next_research_priority']and cont['champion']==prior['champion']
def put(p,b):
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
for name,obj in [('CONTINUATION.json',cont),('ACTIVE_RUN.json',active)]:put(D/name,(json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode())
put(D/'CHECKPOINT_MANIFEST.json',(W/'remote-current/CHECKPOINT_MANIFEST.json').read_bytes())
review={'source_commit':source,'all_prior_fields_except_active_prior_and_new_epoch38_planning_identical':True,'CP_unchanged':True,
 'scientific_authorization':0,'controls':{n:{'bytes':(D/n).stat().st_size,'sha256':hashlib.sha256((D/n).read_bytes()).hexdigest()}for n in ['CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json']}}
put(W/'planning-controls-build-proof.json',(json.dumps(review,indent=2)+'\n').encode())
for directory in(D,W):
 fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(review))
