"""E36 SOURCE/FINAL local publication guards; no model/labels/external calls."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,re
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from phase_receipts_v1 import same_fact,derive_actual,phase_evidence,phase_completed,aggregate_actual,cumulative_counts,checked_ref,require_final_physical_closure
BASE_GIT_LEAVES=5423
BASE_SCOPE_TREE='cec098f9cc4d80241cd6bfecafac96107d8eecd6'
HISTORICAL_MAIN_OBSERVATION='c44d7337c0c5ad2ecd2294178475387facb96516'
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh'}
FINAL_MUTABLE=MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger'}

def leaf(path,body):
 return {'path':path,'mode':'100644','type':'blob','sha':gitsha(body),'size':len(body)}

def tuple_map(document):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Canonical Git file map required')
 require(document.get('scope',SCOPE).rstrip('/')==SCOPE.rstrip('/'),'Wrong Git scope')
 answer={}
 for item in document['files']:
  require(isinstance(item,dict) and set(TUPLE_KEYS)<=set(item),'Incomplete Git tuple')
  row={k:item[k] for k in TUPLE_KEYS};path=row['path']
  require(isinstance(path,str),'Git path must be text')
  if path.startswith(SCOPE):path=path[len(SCOPE):]
  row['path']=relative(path)
  require(row['mode']=='100644' and row['type']=='blob' and re.fullmatch('[0-9a-f]{40}',row['sha'] or '') and type(row['size']) is int and row['size']>=0 and path not in answer,'Invalid/duplicate Git tuple')
  answer[path]=row
 require(CONTROLS<=set(answer),'Original control tuples required')
 return answer

def scope_tree_sha(rows):
 root={}
 for path,row in rows.items():
  node=root;parts=relative(path).split('/')
  for part in parts[:-1]:
   require(part not in node or isinstance(node[part],dict),'Git file/directory collision')
   node=node.setdefault(part,{})
  require(parts[-1] not in node,'Git file/directory collision');node[parts[-1]]=row['sha']
 def digest(node):
  entries=[]
  for name,value in node.items():
   is_dir=isinstance(value,dict);identity=digest(value) if is_dir else value
   entries.append((name.encode()+ (b'/' if is_dir else b''),(b'40000' if is_dir else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(identity)))
  body=b''.join(value for _,value in sorted(entries))
  return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
 return digest(root)

def verify_baseline(kit,index):
 require(index.get('source_commit',BASE_COMMIT)==BASE_COMMIT,'Wrong source checkpoint')
 rows=tuple_map(index)
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original5423 Git identity required')
 for path,row in rows.items():require(leaf(path,content(kit/path))==row,'Historical Git byte drift: '+path)
 return rows

def checked_review(document,current):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Explicit exhaustive review required')
 rows={}
 for row in document['files']:
  require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Canonical review ref required')
  path=relative(row['path']);require(path not in rows,'Duplicate review path');rows[path]=row
 require(set(rows)==set(current),'Review must cover all and only four-root current files')
 for path,body in current.items():require(rows[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Review byte drift: '+path)

def checkpoint_extension(old,new,current):
 before,after=cp_rows(old),cp_rows(new)
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch36_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
 require(set(after)==set(before)|set(current),'Checkpoint must cover exactly original and current public files')
 for path,row in before.items():require(after.get(path)==row,'Historical checkpoint row changed: '+path)
 for path,body in current.items():require(after[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Current checkpoint byte mismatch: '+path)
 return before,after

def controls_at(path,fallback_kit=None):
 directory(path);names={p.name for p in path.iterdir()}
 require(names<=CONTROLS|{'hashes.json'} and {'CONTINUATION.json','ACTIVE_RUN.json'}<=names,'Unexpected control files')
 out={}
 for name in sorted(CONTROLS):
  source=path/name
  if not source.exists():require(name=='CHECKPOINT_MANIFEST.json' and fallback_kit is not None,'Missing control file');source=fallback_kit/name
  out[name]=content(source);public_text(name,out[name])
 return out

def preserve_history(before,after,mutable):
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch36_') for k in after),'Historical continuation metadata removed/new key outside E36')
 for key,value in before.items():
  if key not in mutable:require(after[key]==value,'Historical continuation field changed: '+key)
 for key in ('used_confirmation_sets','champion','epoch27_data_roles'):
  if key in before:require(after[key]==before[key],'Protected source role/champion changed: '+key)
 if 'exposed_development_sets' in mutable:
  old,new=before.get('exposed_development_sets'),after.get('exposed_development_sets')
  if isinstance(old,list):require(isinstance(new,list) and new[:len(old)]==old,'Historical exposed DEV records changed')
  elif isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()),'Historical exposed DEV map changed')
 if 'cumulative_budget_ledger' in mutable:
  old,new=before.get('cumulative_budget_ledger'),after.get('cumulative_budget_ledger')
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch36_') for k in new),'Historical budget ledger changed')

def transport_groups(changed):
 entries=[];blobs=[];groups=[];large_identities={}
 for path,body in sorted(changed.items()):
  text=public_text(path,body);entry={'path':SCOPE+path,'mode':'100644','type':'blob'}
  if len(body)>LARGE_FILE_BYTES:
   payload={'content':text,'encoding':'utf-8'};require(len(encoded(payload))<MAX_BLOB_JSON,'Blob JSON strict cap exceeded')
   identity=gitsha(body)
   if identity in large_identities:require(large_identities[identity]==body,'Refuse unequal large payloads with the same Git blob SHA')
   else:large_identities[identity]=body;blobs.append((path,body,payload))
   entry['sha']=identity
  else:entry['content']=text
  require(len(encoded({'tree_elements':[entry]}))<MAX_TREE_JSON,'Single tree entry strict cap exceeded');entries.append(entry)
 batch=[]
 for entry in entries:
  if len(encoded({'tree_elements':batch+[entry]}))>=MAX_TREE_JSON:require(batch,'Cannot fit tree entry');groups.append(batch);batch=[]
  batch.append(entry)
 if batch:groups.append(batch)
 return blobs,groups

def verify_flags(value):
 for k,v in FLAGS.items():require(same_fact(value.get(k),v),'Forbidden acceptance/promotion/rank: '+k)

def data_role_record():
 return {**copy.deepcopy(ROLES),'hypotheses':HYPOTHESES,'used_confirmation_identities':[],
  'engineering_ids':ENGINEERING_IDS,'engineering_document_ids':ENGINEERING_DOCUMENT_IDS,
  'engineering_role':ENGINEERING_ROLE,'new_benchmark_questions_exposed':0,
  'benchmark_partition_unchanged':{'exposed':325,'unreserved':74,'reserved_confirmation':24,'total':423}}

def retirement_record():
 raise ValueError('E36 has no DEV/CONF retirement; only new authored CC0 engineering IDs')

def pretrained_source_ready(root,rows,reference):
 checked_ref(root,reference,rows,MODEL_SOURCE_PATH)
 source=parse(root/MODEL_SOURCE_PATH)
 require(source.get('epoch')==36 and source.get('kind')==KIND,'Wrong current primary pretrained model source')
 expected={'repository':MODEL_REPOSITORY,'revision':MODEL_REVISION,'weights_file':MODEL_WEIGHTS['file'],
  'weights_bytes':MODEL_WEIGHTS['bytes'],'weights_sha256':MODEL_WEIGHTS['sha256'],
  'training_lineage_complete':False,'source_parameter_dtype':SOURCE_PARAMETER_DTYPE,'compute_dtype':COMPUTE_DTYPE,
  'native_id2label':{'0':'contradiction','1':'neutral','2':'entailment'},'canonical_E_C_N_from_raw':[2,0,1],
  'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[]}
 require(SOURCE_PARAMETER_DTYPE!='PENDING_STATIC_SOURCE_INSPECTION','Primary source dtype must be bound to actual static inspection before freeze')
 require(all(same_fact(source.get(k),v)for k,v in expected.items()),'Exact original xxlarge identity/order/dtype/HOLD differs')
 baseline_ref=ref(root,BASELINE_MODEL_SOURCE_PATH);checked_ref(root,baseline_ref,rows,BASELINE_MODEL_SOURCE_PATH)
 baseline=parse(root/BASELINE_MODEL_SOURCE_PATH)
 expected_baseline={**BASELINE_MODEL,'epoch':36,'kind':KIND,'training_lineage_complete':False,
  'native_id2label':{'0':'entailment','1':'neutral','2':'contradiction'},'canonical_E_C_N_to_raw':[0,2,1],
  'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[]}
 require(all(same_fact(baseline.get(k),v)for k,v in expected_baseline.items()),'Exact unchanged baseline identity/order/dtype/HOLD differs')
 require(baseline.get('metadata_admission')==BASELINE_METADATA_ADMISSION,'Exact inherited baseline source research differs')
 checked_ref(root,BASELINE_METADATA_ADMISSION,rows)
 header_ref=ref(root,XXL_WEIGHT_METADATA_PATH);checked_ref(root,header_ref,rows,XXL_WEIGHT_METADATA_PATH)
 require(header_ref==XXL_WEIGHT_METADATA_REF,'Exact actual root-inspected original metadata required')
 require(source.get('original_archive_metadata')==header_ref,'Primary original archive metadata not source-bound')
 metadata=parse(root/XXL_WEIGHT_METADATA_PATH)
 require(metadata.get('status')=='ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE'
  and metadata.get('weights')=={'bytes':MODEL_WEIGHTS['bytes'],'sha256':MODEL_WEIGHTS['sha256']}
  and metadata.get('format')==SOURCE_SERIALIZATION_FORMAT and metadata.get('source_parameter_dtype')==SOURCE_PARAMETER_DTYPE
  and type(metadata.get('metadata_pickle_count'))is int and metadata['metadata_pickle_count']==5
  and metadata.get('storage_data_ends_at_filelength')is True
  and all(type(metadata.get(k))is int and metadata[k]==0 for k in ('storage_payloads_decoded','unsafe_unpickling_calls','checkpoint_functions_invoked','ML_imports','model_tokenizer_native_calls')),
  'Unverified/unsafe original legacy metadata')
 legacy_ref=ref(root,LEGACY_LOAD_PLAN_PATH);checked_ref(root,legacy_ref,rows,LEGACY_LOAD_PLAN_PATH)
 require(legacy_ref==LEGACY_LOAD_PLAN_REF and source.get('legacy_original_load_plan')==legacy_ref,'Exact reviewed restricted legacy load plan required')
 legacy=parse(root/LEGACY_LOAD_PLAN_PATH);policy=legacy.get('future_frozen_loader_policy',{})
 expected_policy={'serialization_format':SOURCE_SERIALIZATION_FORMAT,'weights_only':True,'mmap':False,'map_location':'cpu',
  'trust_remote_code':False,'unrestricted_pickle_allowed':False,'extra_pickle_safe_globals_added':0,'ZIP_fallback_allowed':False,
  'legacy_tar_fallback_in_statics':False,'alternate_checkpoint_allowed':False,'dynamic_quantization_allowed':False,
  'compute_dtype':COMPUTE_DTYPE,'before_source_freeze_actual_torch_loads_allowed':0,'model_initializations_in_acquisition_or_static_inspection':0}
 require(all(same_fact(policy.get(k),v)for k,v in expected_policy.items()),'Restricted original legacy policy differs; no fallback allowed')
 profiles_ref=ref(root,MODEL_PROFILES_PATH);checked_ref(root,profiles_ref,rows,MODEL_PROFILES_PATH)
 profiles=parse(root/MODEL_PROFILES_PATH)
 require(profiles.get('epoch')==36 and profiles.get('kind')==KIND and profiles.get('shared_partition_model')=='b354'
  and set(profiles.get('profiles',{}))=={'b354','xxlarge'},'Exact paired model profiles required')
 for tag,sref,lock_path,directory,labels,order in (
  ('b354',baseline_ref,P+'candidate/epoch36/BASELINE_MODEL_ASSETS.json',BASELINE_MODEL_DIRECTORY,['Entailment','NotMentioned','Contradiction'],[0,2,1]),
  ('xxlarge',reference,P+'candidate/epoch36/MODEL_ASSETS.json',MODEL_DIRECTORY,['Contradiction','NotMentioned','Entailment'],[2,0,1])):
  lock_ref=ref(root,lock_path);checked_ref(root,lock_ref,rows,lock_path);profile=profiles['profiles'][tag]
  require(isinstance(profile,dict) and same_fact(profile.get('model_source'),sref) and same_fact(profile.get('model_assets_lock'),lock_ref)
   and profile.get('model_directory')==directory and same_fact(profile.get('native_label_order'),labels)
   and same_fact(profile.get('canonical_E_C_N_from_raw'),order) and profile.get('compute_dtype')==COMPUTE_DTYPE,'Paired source/asset/order profile differs: '+tag)
 require(profiles['profiles']['xxlarge'].get('original_archive_metadata')==header_ref,'Profile original archive metadata differs')
 require(profiles['profiles']['xxlarge'].get('legacy_original_load_plan')==legacy_ref,'Profile restricted legacy load plan differs')
 # This pure metadata guard never imports a reader or opens external tensors.
 return source

def check_plan(root,cont,rows,current,phase,oldrows):
 frozen=cont.get('epoch36_frozen_study');require(isinstance(frozen,dict) and set(frozen)=={'plan','source_freeze'},'Exact current source refs required')
 checked_ref(root,frozen['plan'],rows,PLAN_PATH);checked_ref(root,frozen['source_freeze'],rows,FREEZE_PATH)
 plan,freeze=parse(root/PLAN_PATH),parse(root/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==36 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Wrong current source epoch/kind/BASE')
 require(same_fact(plan.get('data_roles'),ROLES) and plan.get('hypotheses')==HYPOTHESES and plan.get('source_freeze')==frozen['source_freeze'] and plan.get('actual_project')==str(root),'Wrong frozen empty benchmark roles/hypotheses/root/freeze')
 expected={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
 require(all(same_fact(plan.get('limits',{}).get(k),v) for k,v in expected.items()),'Fixed one-phase CPU/spend limits differ')
 require(plan.get('training_lineage_complete')is TRAINING_LINEAGE_COMPLETE and plan.get('diagnostic_only')is DIAGNOSTIC_ONLY and same_fact(plan.get('probability_temperature'),1.0),'Incomplete lineage, engineering scope and frozen T1 must remain explicit')
 require(plan.get('source_serialization_format')==SOURCE_SERIALIZATION_FORMAT and plan.get('source_parameter_dtype')==SOURCE_PARAMETER_DTYPE and plan.get('compute_dtype')==COMPUTE_DTYPE,'Exact legacy source/compute format differs')
 require(plan.get('engineering_only')is True and plan.get('benchmark_accuracy')is None and plan.get('promotion_allowed')is False and plan.get('used_confirmation_identities')==[],'Engineering-only scope must remain explicit')
 require(plan.get('development_ids')==[] and plan.get('training_ids')==[] and plan.get('calibration_ids')==[] and plan.get('confirmation_ids')==[] and plan.get('engineering_ids')==ENGINEERING_IDS,'No train/DEV/calibration/CONF; exact new authored engineering IDs required')
 require(same_fact(plan.get('engineering_gate'),ENGINEERING_GATE),'Prospectively frozen nine-case/class/model-gain/proper-score gate differs')
 require(same_fact(plan.get('reader_execution_order'),MODEL_EXECUTION_ORDER) and same_fact(plan.get('model_forward_counts'),MODEL_FORWARD_COUNTS),'Paired reader ordering/forward budget differs')
 require(same_fact(plan.get('raw_arm_names'),RAW_ARM_NAMES) and same_fact(plan.get('metric_arm_names'),METRIC_ARM_NAMES) and same_fact(plan.get('raw_to_metric_arm'),RAW_TO_METRIC_ARM),'Explicit raw-to-metric alias map differs')
 require(same_fact(plan.get('arms'),ARM_NAMES) and same_fact(plan.get('proof_enabled_roles'),PROOF_ENABLED_ROLES) and same_fact(plan.get('native_queries_per_case'),NATIVE_QUERIES_PER_CASE) and same_fact(plan.get('maximum_native_queries'),TOTAL_MAX_NATIVE_QUERIES),'Frozen six-arm treatment or proof-disabled scope differs')
 require(same_fact(plan.get('retrieval_policy'),RETRIEVAL_POLICY) and same_fact(plan.get('probability_policy'),PROBABILITY_POLICY) and same_fact(plan.get('metrics_policy'),METRICS_POLICY),'Frozen policy differs')
 require(plan.get('guardian_scope')==str(OWNER_SCOPE_DIR) and plan.get('model_directory')==MODEL_DIRECTORY and plan.get('baseline_model_directory')==BASELINE_MODEL_DIRECTORY and plan.get('external_python_environment')==str(EXTERNAL_ENV_PATH) and plan.get('inference_python')==str(EXTERNAL_ENV_PATH/'bin/python') and plan.get('runtime_reuse_policy')==RUNTIME_REUSE_POLICY,'Frozen guardian/model/runtime layout differs')
 require(not any(k.startswith('dev_inputs') for k in plan),'Old DEV paths forbidden in engineering master plan')
 for key in ('engineering_inputs','engineering_oracle','numeric_oracle','xxlarge_weight_metadata','legacy_original_load_plan','model_assets_lock','baseline_model_source','baseline_model_assets_lock','model_profiles'):
  path=plan.get(key+'_path');require(path in rows and rows[path]['sha256']==plan.get(key+'_sha256'),'Frozen CC0 engineering identity missing: '+key)
 pretrained_source_ready(root,rows,plan.get('pretrained_model_source'))
 require(cont.get('epoch36_pretrained_model_source')==plan['pretrained_model_source'] and cont.get('epoch36_baseline_model_source')==plan['baseline_model_source'],'Continuation pretrained source projection differs')
 pins=plan.get('pins');require(isinstance(pins,list) and pins,'Current source pins required');indexed={}
 for row in pins:require(row['path']not in indexed,'Duplicate source pin');checked_ref(root,row);indexed[row['path']]=row
 entries=freeze.get('entries');require(isinstance(entries,list) and entries,'Source-freeze entries required');seen=set()
 for row in entries:
  path=checked_ref(root,row,rows);require(path not in seen and path in current and path not in {PLAN_PATH,FREEZE_PATH} and indexed.get(path)==row,'Invalid/unpinned source-freeze member');seen.add(path)
 if phase=='source':require(seen==set(current)-{PLAN_PATH,FREEZE_PATH},'Current source freeze omits files')
 require(indexed.get(FREEZE_PATH)==frozen['source_freeze'] and indexed.get(MODEL_SOURCE_PATH)==plan['pretrained_model_source']
  and indexed.get(BASELINE_MODEL_SOURCE_PATH)==plan['baseline_model_source'] and indexed.get(MODEL_PROFILES_PATH)==plan['model_profiles']
  and indexed.get(XXL_WEIGHT_METADATA_PATH)==ref(root,XXL_WEIGHT_METADATA_PATH)
  and indexed.get(LEGACY_LOAD_PLAN_PATH)==LEGACY_LOAD_PLAN_REF
  and indexed.get(BASELINE_METADATA_ADMISSION['path'])==BASELINE_METADATA_ADMISSION,'Current freeze/model/profile/static metadata unpinned')
 return plan

def check_phase_main(value,observed):
 require(isinstance(observed,str) and re.fullmatch('[0-9a-f]{40}',observed),'A well-formed read-only main observation is required')
 require(isinstance(value.get('main'),str) and re.fullmatch('[0-9a-f]{40}',value['main']),'Independent parent readback must retain its own point-in-time main observation')
 # Unrelated main advances independently. Its value is recorded, never a CAS gate.

def check_readback(value,phase,parent,trees):
 require(value.get('commit')==parent and(value.get('verified')is True or value.get('verified_actual_full_tree')is True or(value.get('checks_passed')is True and value.get('verified_actual_remote_readback')is True)),'Actual independent parent readback required')
 require(all(value.get(k)==v for k,v in zip(('root','bench','scope'),trees)),'Actual parent trees differ')
 parents=[value[k]for k in ('parent','sole_parent')if k in value];require(parents and all(v==parents[0]for v in parents),'Missing/conflicting actual sole parent')
 require(parent!=BASE_COMMIT,'SOURCE/FINAL must extend scoped planning/source commit')

def checked_controls(args,root,kit,current):
 phase=args.phase;bodies=controls_at(args.controls);prior=controls_at(args.priorcontrols,kit)
 oldcp,oldcont=parse(kit/'CHECKPOINT_MANIFEST.json'),parse(kit/'CONTINUATION.json')
 require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256==oldcont['checkpoint_manifest_sha256'],'Actual BASE checkpoint hash differs');check_inherited_checkpoint(oldcp);oldrows=check_history(root,oldcp)
 cp,cont,active=(loads(bodies[n])for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'));pcp,pcont,pactive=(loads(prior[n])for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 _,rows=checkpoint_extension(oldcp,cp,current);require(pcont['checkpoint_manifest_sha256']==sha(prior['CHECKPOINT_MANIFEST.json']),'Prior checkpoint hash differs')
 mutable=FINAL_MUTABLE if phase=='final'else MUTABLE;preserve_history(oldcont,cont,mutable);preserve_history(pcont,cont,mutable)
 require(cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json']) and cont['active_run']==dict(active,path='ACTIVE_RUN.json') and cont['prior_published_base_commit']==args.parent and cont.get('goal_met')is False and cont.get('official_rank')is None,'Control/hash/status/parent differs')
 owner=active.get('physical_owner',{});require(active.get('run_id')==OWNER_RUN_ID and(owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==OWNER_PIN and owner.get('expires_unix')==OWNER_EXPIRES_UNIX,'Wrong actual E36 guardian')
 require(type(active.get('native_allowed'))is int and active['native_allowed']==0 and active.get('experiments_active')is False and active.get('checkpoint_parent')==args.parent and active.get('OS_lock_held')is True,'Immediate native execution must remain closed')
 for key in ('confirmation_allowed','conditional_confirmation_allowed','conditional_train_allowed','conditional_dev_allowed'):require(type(active.get(key))is int and active[key]==0,'TRAIN/CONF allowances must remain zero')
 if phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH36_PLANNING_LEASE' and active.get('state')=='EPOCH36_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION' and active.get('work_active')is True and type(active.get('conditional_engineering_allowed'))is int and active['conditional_engineering_allowed']==1,'SOURCE conditional DEV gate differs')
  require(not any(path.startswith(E+'runs/') or path in {E+'RESULTS.json',E+'EPOCH_MANIFEST.json',E+'SOURCE_ADMISSION.json',E+'ENGINEERING_ATTEMPT_RESERVATION.json',*DISPATCH_PATHS.values()}for path in current),'Premeasurement SOURCE contains execution/admission/results')
 else:
  require(set(cp)==set(pcp) and all(cp[k]==v for k,v in pcp.items()if k!='project_files') and all(rows.get(k)==v for k,v in cp_rows(pcp).items()),'Previously published checkpoint/source changed')
  require(cont.get('epoch36_frozen_study')==pcont.get('epoch36_frozen_study'),'Published plan/freeze changed')
  require(pactive.get('state')=='EPOCH36_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION' and active.get('state')=='EPOCH36_CLOSED' and active.get('work_active')is False and type(active.get('conditional_engineering_allowed'))is int and active['conditional_engineering_allowed']==0,'FINAL current phase closure differs')
 require(same_fact(cont.get('epoch36_planning'),pcont.get('epoch36_planning')) and same_fact(cont.get('epoch36_data_roles'),data_role_record()),'Planning/frozen role history differs')
 require(same_fact(cont.get('exposed_development_sets'),oldcont.get('exposed_development_sets')),'No benchmark DEV retirement or relabeling in E36')
 plan=check_plan(root,cont,rows,current,phase,oldrows)
 if phase=='source':require(plan.get('publication_parent')==args.parent and plan.get('publication_parent_trees')==dict(zip(('root','bench','scope'),(args.expected_root,args.expected_bench,args.expected_scope))),'Actual SOURCE parent/trees must be frozen in master plan')
 else:check_final(root,rows,cont,pcont,plan)
 return bodies,prior,oldcp,cp,cont,plan,check_transport(root,oldcont,cont,rows,kit=kit)

def check_final(root,rows,cont,pcont,plan):
 m=parse(root/(E+'EPOCH_MANIFEST.json'));require(m.get('epoch')==36 and m.get('kind')==KIND and m.get('status')in FINAL_STATUSES,'Wrong engineering outcome');verify_flags(m)
 require(m.get('confirmation')==[] and m.get('used_confirmation_identities')==[] and m.get('all_slots_closed')is True and m.get('diagnostic_qualified')is False and type(m.get('engineering_passed'))is bool and m.get('readiness_qualified')is m['engineering_passed'],'Engineering-only verdict invalid')
 require(same_fact(m.get('phase_remaining'),{'train':0,'dev':0,'calibration':0,'confirmation':0,'engineering':0}),'Final phase_remaining must close every allowance')
 for key,path in [('plan',PLAN_PATH),('source_freeze',FREEZE_PATH),('results',E+'RESULTS.json'),('pretrained_model_source',MODEL_SOURCE_PATH),('baseline_model_source',BASELINE_MODEL_SOURCE_PATH),('model_profiles',MODEL_PROFILES_PATH)]:checked_ref(root,m.get(key),rows,path)
 result=parse(root/m['results']['path']);verify_flags(result)
 require(result.get('benchmark_accuracy')is None,'Engineering data cannot be a benchmark accuracy')
 for key in ('status','diagnostic_qualified','engineering_passed','readiness_qualified','actual_execution'):require(same_fact(result.get(key),m[key]),'Manifest/result differs: '+key)
 report_path=checked_ref(root,m.get('independent_report'),rows);require(report_path.startswith(P+'audit/epoch36/'),'Current independent report required')
 report=parse(root/report_path);require(report.get('epoch')==36 and report.get('kind')==KIND and report.get('checks_passed')is True and report.get('diagnostic_qualified')is False and report.get('engineering_passed')is m['engineering_passed'],'Independent final binding/verdict differs')
 evidence=phase_evidence(root,'engineering',m['plan'],rows);actual=aggregate_actual(evidence);require_final_physical_closure(actual);require(same_fact(m['actual_execution'],actual),'Actual counters/resources differ')
 refs={'raw':evidence['raw'],'execution':evidence['execution'],'results':m['results'],'pretrained_model_source':m['pretrained_model_source'],'baseline_model_source':m['baseline_model_source'],'model_profiles':m['model_profiles']}
 require(all(same_fact(report.get('evidence',{}).get(k),v)for k,v in refs.items()),'Independent evidence references differ')
 if actual['worker_attempts']:
  ap=E+'SOURCE_ADMISSION.json';ar=ref(root,ap);checked_ref(root,ar,rows,ap);admission=parse(root/ap)
  require(admission.get('epoch')==36 and admission.get('kind')==KIND and admission.get('verified_actual_remote_readback')is True and admission.get('published_source_commit')==cont['prior_published_base_commit'],'Actual SOURCE-before-engineering admission missing')
  require(admission.get('plan_sha256')==m['plan']['sha256'] and admission.get('source_freeze_sha256')==m['source_freeze']['sha256'] and admission.get('pretrained_model_source')==m['pretrained_model_source'] and admission.get('baseline_model_source')==m['baseline_model_source'] and admission.get('model_profiles_sha256')==m['model_profiles']['sha256']
   and admission.get('model_assets_lock_sha256')==plan['model_assets_lock_sha256'] and admission.get('baseline_model_assets_lock_sha256')==plan['baseline_model_assets_lock_sha256']
   and admission.get('xxlarge_weight_metadata_sha256')==plan['xxlarge_weight_metadata_sha256']
   and admission.get('legacy_original_load_plan_sha256')==plan['legacy_original_load_plan_sha256'],'Admitted source identities differ')
  require(admission.get('owner_pid')==OWNER_PIN[0] and admission.get('owner_startticks')==OWNER_PIN[1],'Current admission guardian differs')
 if m['engineering_passed']:
  require(phase_completed(evidence) and m['status']=='ACCEPTED_ENGINEERING_ADMISSION_ONLY','Positive engineering admission requires complete bounded54')
 else:require(m['status']in {'REJECTED_ENGINEERING_ADMISSION','REJECTED_ENGINEERING_INTEGRITY'},'Rejected engineering status differs')
 before,new=pcont.get('execution_observed',{}),cont.get('execution_observed',{});counts=cumulative_counts(actual)
 require(before.get('epoch35_cumulative_corpus_attempts')==32 and before.get('epoch35_cumulative_completed_corpus_batches')==30 and before.get('epoch35_cumulative_bounded_native_process_attempts')==36,'Verified explicit prior32/30/36 differs')
 require(all(same_fact(new.get(k),v)for k,v in before.items()) and all(k in before or k.startswith('epoch36_')for k in new) and same_fact(new.get('epoch36_actual_execution'),actual),'Historical execution changed/current effort missing')
 for key,value in {'epoch36_cumulative_corpus_attempts':counts['corpus_attempts'],'epoch36_cumulative_completed_corpus_batches':counts['completed_corpus_batches'],'epoch36_cumulative_bounded_native_process_attempts':counts['bounded_native_process_attempts']}.items():require(same_fact(new.get(key),value),'Cumulative count differs: '+key)
 require(same_fact(m.get('cumulative_execution'),counts) and same_fact(result.get('cumulative_execution'),counts),'Manifest/result cumulative count differs')
 oldref=pcont['rejection_ledger'];checked_ref(root,oldref,rows);newref=cont['rejection_ledger'];checked_ref(root,newref,rows,E+'REJECTION_LEDGER.json');oldledger,ledger=parse(root/oldref['path']),parse(root/newref['path'])
 for key,value in oldledger.items():require(same_fact(ledger.get(key,[])[:len(value)],value)if key=='rejections'else same_fact(ledger.get(key),value),'Historical rejection metadata changed: '+key)
 require(all(k in oldledger or k.startswith('epoch36_')for k in ledger),'New rejection key outside E36')
 budget={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
 require(same_fact(ledger.get('epoch36_budget'),budget) and same_fact(ledger.get('epoch36_actual_execution'),actual) and same_fact(ledger.get('epoch36_cumulative_execution'),counts) and same_fact(cont.get('cumulative_budget_ledger',{}).get('epoch36_budget'),budget),'Used/closed budget differs')
 decision=ledger.get('epoch36_decision',{});verify_flags(decision)
 for key,value in {'status':m['status'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed'],'results':m['results']}.items():require(same_fact(decision.get(key),value),'Decision differs: '+key)
 if m['engineering_passed']:require(ledger['rejections']==oldledger['rejections'] and ledger.get('epoch36_engineering_qualification',{}).get('results')==m['results'],'Engineering qualification record missing')
 else:require(len(ledger['rejections'])==len(oldledger['rejections'])+1 and ledger['rejections'][-1].get('epoch')==36 and ledger['rejections'][-1].get('status')==m['status'] and ledger['rejections'][-1].get('results')==m['results'] and bool(ledger['rejections'][-1].get('reason')),'Exact rejection/reason required')
 summary={**FLAGS,'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':m['results'],'status':m['status'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed'],'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
 require(same_fact(cont.get('epoch36_final'),summary),'Final continuation projection differs')
 epoch={**FLAGS,'epoch':36,'kind':KIND,'status':m['status'],'manifest':summary['manifest'],'results':m['results'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed']}
 require(same_fact(cont.get('epochs'),pcont.get('epochs',[])+[epoch]),'Append exactly one truthful summary')

def prepare(args):
 root,kit,controls,priorcontrols=map(directory,(args.project,args.kit,args.controls,args.priorcontrols));live_owner(root.parent)
 output=new_output(args.out,(root,kit,controls,priorcontrols))
 for key in ('parent','expected_main','expected_root','expected_bench','expected_scope'):require(re.fullmatch('[0-9a-f]{40}',getattr(args,key) or ''),'Exact Git SHA required: '+key)
 proof_bytes=content(args.parent_readback);parent_proof=loads(proof_bytes);check_phase_main(parent_proof,args.expected_main);check_readback(parent_proof,args.phase,args.parent,(args.expected_root,args.expected_bench,args.expected_scope))
 map_bytes=content(args.source_filemap);baseline=verify_baseline(kit,loads(map_bytes));current=walk_current(root)
 review_bytes=content(args.reviewed_files);checked_review(loads(review_bytes),current)
 bodies,prior,oldcp,cp,cont,plan,transport=checked_controls(args,root,kit,current)
 require(plan.get('publication_stage_paths',{}).get(args.phase)==str(output),'Stage placement must match frozen master plan')
 if args.prior_expected:prior_bytes=content(args.prior_expected);before=tuple_map(loads(prior_bytes))
 else:
  require(args.phase=='source','MODEL/FINAL require exact actual prior full map');before=copy.deepcopy(baseline)
  for name,body in prior.items():before[name]=leaf(name,body)
  prior_bytes=encoded({'scope':SCOPE,'files':[before[k] for k in sorted(before)]})
 for name,body in prior.items():require(before.get(name)==leaf(name,body),'Prior control tuple differs: '+name)
 expected=copy.deepcopy(baseline)
 for path,body in {**current,**bodies}.items():require(path not in baseline or path in CONTROLS,'Historical Git overwrite refused');expected[path]=leaf(path,body)
 require(all(expected.get(k)==v for k,v in before.items() if k not in CONTROLS),'Previously published source/model tuple changed')
 check_transport(root,parse(kit/'CONTINUATION.json'),cont,cp_rows(cp),set(expected),kit=kit)
 changed={path:body for path,body in {**current,**bodies}.items() if before.get(path)!=expected[path]};require(CONTROLS<=set(changed),'Three control updates required')
 blobs,groups=transport_groups(changed)
 meta={'schema_version':1,'stage':args.phase,'prior_controls_name':args.priorcontrols.name,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'source_plan_sha256':sha(content(root/PLAN_PATH)),'publication_parent':args.parent,
  'read_only_main_observation':args.expected_main,'CAS_guards':{'expected_root_tree':args.expected_root,'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,'expected_branch_sha':args.parent,'force':False},
  'source_filemap_sha256':sha(map_bytes),'prior_expected_sha256':sha(prior_bytes),'reviewed_files_sha256':sha(review_bytes),'parent_readback_sha256':sha(proof_bytes),
  'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(before),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(cp_rows(cp)),'new_epoch36_public_files':len(current),'expected_Git_leaves':len(expected),
  'changed_files':[],'old_noncontrol_tuples_preserved':True,'old_CP_metadata_preserved':True,'frozen_source_tuples_preserved':True,'inherited_archive_transport_unchanged':transport,'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[]}
 output.mkdir(mode=0o700);(output/'transport').mkdir(mode=0o700)
 for path,body in sorted(changed.items()):meta['changed_files'].append({'path':path,'bytes':len(body),'sha256':sha(body),'git_blob_sha1':gitsha(body)})
 for i,(path,body,payload) in enumerate(blobs):
  name='transport/blob-%03d.json'%i;data=encoded(payload);write(output/name,data);meta['large_blob_requests'].append({'path':path,'file':name,'bytes':len(data),'sha256':sha(data),'expected_blob_sha1':gitsha(body),'must_verify_before_tree':True})
 for i,group in enumerate(groups):
  name='transport/tree-%03d.json'%i;data=encoded({'tree_elements':group});require(len(data)<MAX_TREE_JSON,'Strict serialized tree cap');write(output/name,data);meta['create_tree_groups'].append({'file':name,'bytes':len(data),'sha256':sha(data),'entries':len(group)})
 leaves=encoded({'schema_version':1,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'files':[expected[k] for k in sorted(expected)]});write(output/'expected-leaves.json',leaves)
 meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':sha(leaves),'count':len(expected)};write(output/'metadata.json',encoded(meta,pretty=True))
 return {k:meta[k] for k in ('stage','publication_parent','old_CP_rows','new_CP_rows','expected_Git_leaves','expected_leaves','Git_mutations')}

if __name__=='__main__':
 cli=argparse.ArgumentParser()
 for name in ('project','kit','controls','priorcontrols','source-filemap','reviewed-files','parent-readback','out'):cli.add_argument('--'+name,type=Path,required=True)
 cli.add_argument('--phase',choices=('source','final'),required=True);cli.add_argument('--prior-expected',type=Path)
 for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):cli.add_argument('--'+name,required=True)
 print(json.dumps(prepare(cli.parse_args()),sort_keys=True))
