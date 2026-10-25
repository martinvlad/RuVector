"""E38 SOURCE/FINAL local publication guards; no model/labels/external calls."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,hashlib,json,re
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from phase_receipts_v1 import same_fact,derive_actual,phase_evidence,phase_completed,aggregate_actual,cumulative_counts,checked_ref,require_final_physical_closure
BASE_GIT_LEAVES=5959
BASE_SCOPE_TREE='21ae92a2e7028752379071753cd4aba0ae54fc00'
HISTORICAL_MAIN_OBSERVATION='c44d7337c0c5ad2ecd2294178475387facb96516'
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh'}
FINAL_MUTABLE=MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger'}
RESOURCE_POLICY_SOURCE_PATH=E+'preparation/dispatch_once.py'
MINIMUM_WORKSPACE_FREE_BYTES=16777216
AUDIT_PROTOCOL_PATH=P+'audit/epoch38/protocol.json'

def audit_protocol_ready(root,rows=None):
 reference=ref(root,AUDIT_PROTOCOL_PATH);checked_ref(root,reference,rows,AUDIT_PROTOCOL_PATH);protocol=parse(root/AUDIT_PROTOCOL_PATH)
 expected={'schema_version':1,'epoch':38,'kind':KIND,'phase':'engineering','source_checkpoint':BASE_COMMIT,'data_roles':ROLES,
  'engineering_only':True,'benchmark_accuracy':None,'promotion_allowed':False,'training_lineage_complete':False,'official_eligibility':'HOLD',
  'engineering_case_ids':ENGINEERING_IDS,'raw_contexts':RAW_CONTEXT_NAMES,'metric_arms':METRIC_ARM_NAMES,'arm_to_measured_context':READOUT_REUSE_MAP,
  'primary':PRIMARY_ARM,'engineering_gate':ENGINEERING_GATE,'probability_policy':PROBABILITY_POLICY,'actual_NLI_forwards':36,
  'final_derived_forecasts':60,'used_confirmation_identities':[],'root_contract':ROOT_CONTRACT_REF,'metrics_policy':METRICS_POLICY_REF}
 require(all(same_fact(protocol.get(k),v)for k,v in expected.items()),'Independent ROOT protocol criteria, readout reuse or empty benchmark roles differ')
 checked_ref(root,ROOT_CONTRACT_REF,rows,ROOT_CONTRACT_PATH);frozen_metrics_policy(root,rows)
 for key in ('candidate_protocol','core_source_manifest','core_source_ready','scorer_source_ready_v1'):checked_ref(root,protocol.get(key),rows)
 require(protocol.get('model_assets_expected')==MODEL_ASSETS_EXPECTED_REF and protocol.get('model_assets_validator')==ref(root,MODEL_ASSETS_VALIDATOR_PATH)and protocol.get('real_model_assets_guard_receipt')==real_model_assets_guard_ready(root,rows),'Protocol real complete asset guard/catalog/source bindings differ')
 return protocol

def frozen_metrics_policy(root,rows=None):
 reference=ref(root,METRICS_POLICY_PATH);checked_ref(root,reference,rows,METRICS_POLICY_PATH)
 require(reference==METRICS_POLICY_REF,'Exact independently reviewed metrology source changed')
 policy=parse(root/METRICS_POLICY_PATH)
 require(policy.get('epoch')==38 and policy.get('kind')==KIND and policy.get('gate_metric_binding')=={'Brier':'Brier','NLL':'NLL'}
  and policy.get('NLL')=='UNCLIPPED_STABLE_SOURCE_LOGIT_LOGSOFTMAX_WITH_SAME_CANONICAL_CLASS_PERMUTATION'
  and policy.get('NLL_clipping_floor_diagnostic_only')==1e-12 and policy.get('acceptance_roundoff_tolerance')==1e-12
  and policy.get('no_confidence_fitting')is True and policy.get('no_calibrated_posterior_claim')is True
  and policy.get('probability_policy')=='SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION','Gate NLL must remain stable/unclipped with identical class permutation; clipped NLL diagnostic only')
 return reference

def frozen_retrieval_policy(root,rows=None):
 refs={name:ref(root,path)for name,path in (('query_policy',QUERY_POLICY_PATH),('context_policy',CONTEXT_POLICY_PATH))}
 for name,row in refs.items():checked_ref(root,row,rows)
 query=parse(root/QUERY_POLICY_PATH);context=parse(root/CONTEXT_POLICY_PATH)
 require(all(doc.get('epoch')==38 and doc.get('kind')==KIND for doc in (query,context)),'Current source query/context policies required')
 require(all(query.get(k)is False for k in ('truncation','rewriting','label_access'))and query.get('policy')=='unchanged-original-query-numeric-source-v1','Original hypothesis must remain unchanged and label blind')
 require(context.get('policy')=='rank-prefix-until-source-constraint-coverage-v1'and same_fact(context.get('raw_contexts'),RAW_CONTEXT_NAMES)
  and same_fact(context.get('arms'),ARM_NAMES)and same_fact(context.get('readout_reuse_map'),READOUT_REUSE_MAP)
  and context.get('partition_model')=='xxlarge'and context.get('BGE_source')==P+'candidate/epoch3/models.py'
  and context.get('root_contract_sha256')==ROOT_CONTRACT_REF['sha256'],'Exact source context policy/ROOT contract differs')
 return refs

def real_model_assets_guard_ready(root,rows=None):
 """Read only the actual complete-validator receipt; never call its code here.
 A selector/unit fixture cannot admit SOURCE. Root must call the same full
 C.verify_model_assets on all real payloads once, after source review.
 """
 expected={key:ref(root,path)for key,path in (
  ('common_source',P+'candidate/epoch38/runtime/common.py'),('validator_source',MODEL_ASSETS_VALIDATOR_PATH),
  ('identity_helper_source',MODEL_ASSETS_IDENTITY_HELPER_PATH),('expected_catalog',MODEL_ASSETS_EXPECTED_PATH),
  ('public_model_assets_lock',P+'candidate/epoch38/MODEL_ASSETS.json'))}
 for row in expected.values():checked_ref(root,row,rows)
 require(expected['expected_catalog']==MODEL_ASSETS_EXPECTED_REF,'Separate original expected a65 catalog required')
 admission_ref=ref(root,REAL_MODEL_ASSETS_GUARD_RECEIPT_PATH);checked_ref(root,admission_ref,rows);require(admission_ref==REAL_MODEL_ASSETS_GUARD_RECEIPT_REF,'Exact actual one-call b9be full REAL guard admission required; fixture or invented receipt cannot substitute');admission=parse(root/admission_ref['path'])
 scalar={'schema_version':1,'epoch':38,'source_checkpoint':BASE_COMMIT,
  'status':'PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE','function':'C.verify_model_assets','function_calls':1,
  'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0}
 require(all(same_fact(admission.get(k),v)for k,v in scalar.items()),'Actual single complete REAL asset guard admission required; no stubs/cases/ML')
 require(all(admission.get(k)==v for k,v in expected.items()),'Real guard envelope source/expected/public lock references changed')
 result=admission.get('result');require(isinstance(result,dict)and set(result)=={'xxlarge'},'One original XXL actual guard result required');leaf=result['xxlarge']
 required={'schema_version':1,'epoch':38,'kind':KIND,'source_checkpoint':BASE_COMMIT,
  'status':'ALL_FIVE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES','validator_function':'model_assets_guard.validate_model_assets',
  'repository':MODEL_REPOSITORY,'revision':MODEL_REVISION,'model_directory':MODEL_DIRECTORY,
  'directory_inventory':sorted(['config.json','tokenizer_config.json','LICENSE','spm.model','pytorch_model.bin','asset-lock.json']),
  'actual_payload_files_verified':5,'ordinary_Git_payloads_verified':3,'canonical_LFS_pointers_verified':2,
  'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,'network_calls':0}
 require(isinstance(leaf,dict)and all(same_fact(leaf.get(k),v)for k,v in required.items()),'Complete same-validator five-real-payload result required')
 require(all(leaf.get(k)==v for k,v in expected.items()),'Guard result source refs do not match the envelope/current source')
 direct=leaf.get('external_direct_lock',{});public=expected['public_model_assets_lock']
 require(direct=={'path':MODEL_DIRECTORY+'/asset-lock.json','bytes':public['bytes'],'sha256':public['sha256'],'byte_identical_to_public':True},'Actual external/public lock byte equality required')
 catalogue=parse(root/MODEL_ASSETS_EXPECTED_PATH).get('files');materialized=parse(root/public['path']).get('files');files=leaf.get('files')
 names={'config.json','tokenizer_config.json','LICENSE','spm.model','pytorch_model.bin'}
 require(all(isinstance(v,list)and len(v)==5 and all(isinstance(row,dict)for row in v)and {row.get('path')for row in v}==names for v in (catalogue,materialized,files)),'All five original source/observed/scanned identities required')
 declarations={r['path']:r for r in catalogue};observed={r['path']:r for r in materialized};total=ordinary=lfs=0
 for scanned in files:
  name=scanned['path'];declaration=declarations[name];actual=observed[name];typed=set(declaration)&{'upstream_sha256','metadata_body_sha256'}
  require(len(typed)==1,'Expected catalog needs explicit Git-body or LFS-payload type');key=next(iter(typed));is_raw=key=='metadata_body_sha256';digest=declaration[key];size=declaration['bytes'];upstream=declaration['upstream_git_blob_sha1']
  require(type(size)is int and size>=0 and isinstance(digest,str)and re.fullmatch('[0-9a-f]{64}',digest)and isinstance(upstream,str)and re.fullmatch('[0-9a-f]{40}',upstream),'Typed expected source identity malformed')
  require(type(actual.get('bytes'))is int and actual['bytes']==size and actual.get('sha256')==digest and actual.get('source_url')==declaration['source_url']and actual.get('upstream_git_blob_sha1')==upstream,'Materialized lock must match independently declared source')
  facts={'bytes':size,'source_url':declaration['source_url'],'payload_sha256':digest,'upstream_git_object_sha1':upstream,
   'representation':'RAW_GIT_BLOB_PAYLOAD'if is_raw else'CANONICAL_GIT_LFS_POINTER_WITH_SEPARATE_SHA256_PAYLOAD',
   'raw_payload_git_blob_sha1_required':is_raw,'payload_size_and_SHA256_verified':True,'raw_payload_git_sha1_verified':is_raw,
   'LFS_pointer_SHA1_compared_to_payload_SHA1':False,'actual_payload_bytes_hashed':size,'actual_payload_sha256':digest,
   'actual_ordinary_payload_git_blob_sha1':upstream if is_raw else None,'actual_full_payload_scan':True,
   'payload_git_SHA1_computed':is_raw,'LFS_payload_git_SHA1_not_required':not is_raw}
  require(all(same_fact(scanned.get(k),v)for k,v in facts.items()),'Every actual full scan/type/Git-vs-LFS proof must match exact source: '+name)
  if not is_raw:
   pointer=('version https://git-lfs.github.com/spec/v1\noid sha256:'+digest+'\nsize '+str(size)+'\n').encode('ascii')
   require(gitsha(pointer)==upstream and scanned.get('upstream_lfs_pointer_bytes')==len(pointer)and scanned.get('upstream_lfs_pointer_sha256')==sha(pointer)and scanned.get('upstream_lfs_pointer_git_sha1')==upstream,'Canonical LFS pointer identity must be separate from expanded payload identity')
  total+=size;ordinary+=int(is_raw);lfs+=int(not is_raw)
 require(ordinary==3 and lfs==2 and type(leaf.get('actual_payload_bytes_hashed'))is int and leaf['actual_payload_bytes_hashed']==total,'Actual complete five-file scan byte totals differ')
 return admission_ref

def frozen_resource_policy(root,rows=None):
 """Read the exact source literal; never import or invoke dispatch."""
 source=ref(root,RESOURCE_POLICY_SOURCE_PATH);checked_ref(root,source,rows,RESOURCE_POLICY_SOURCE_PATH)
 tree=ast.parse(content(root/RESOURCE_POLICY_SOURCE_PATH).decode('utf-8'))
 matches=[n.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='RESOURCE_POLICY'for t in n.targets)]
 require(len(matches)==1 and isinstance(matches[0],ast.Dict),'One literal dispatch RESOURCE_POLICY required')
 policy=ast.literal_eval(matches[0]);required={'cgroup_hard_limit_bytes','source_F16_payload_bytes','target_F32_payload_bytes','exact_source_plus_target_payload_bytes',
  'conservative_simultaneous_source_heap_plus_F32_payload_bytes','additional_runtime_activation_reserve_bytes','minimum_reclaim_adjusted_headroom_bytes','reclaimable_filecache_policy','one_reader_only','observed_E36_largest_child_peak_RSS_bytes','minimum_workspace_free_bytes'}
 require(type(policy)is dict and set(policy)==required and all(type(v)is int and v>0 for k,v in policy.items()if k not in {'reclaimable_filecache_policy','one_reader_only'})
  and type(policy['reclaimable_filecache_policy'])is str and policy['one_reader_only']is True,'Exact inert typed resource-policy shape required')
 require(policy['one_reader_only']is True and policy['observed_E36_largest_child_peak_RSS_bytes']==8255184896 and policy['minimum_workspace_free_bytes']==MINIMUM_WORKSPACE_FREE_BYTES
  and policy['cgroup_hard_limit_bytes']==17179869184 and policy['source_F16_payload_bytes']==3133830150 and policy['target_F32_payload_bytes']==6267660300
  and policy['source_F16_payload_bytes']+policy['target_F32_payload_bytes']==policy['exact_source_plus_target_payload_bytes']==9401490450
  and policy['conservative_simultaneous_source_heap_plus_F32_payload_bytes']==9401874294
  and policy['additional_runtime_activation_reserve_bytes']==2147483648
  and policy['conservative_simultaneous_source_heap_plus_F32_payload_bytes']+policy['additional_runtime_activation_reserve_bytes']==policy['minimum_reclaim_adjusted_headroom_bytes']==11549357942,
  'Exact reviewed single-reader legacy payload plus2GiB reserve arithmetic required')
 require(policy['reclaimable_filecache_policy']=='max(0,min(max(0,file-shmem),active_file+inactive_file)-file_dirty-file_writeback)','Shmem/dirty/writeback may not count as reclaimable')
 return policy

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
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original5959 Git identity required')
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
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch38_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
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
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch38_') for k in after),'Historical continuation metadata removed/new key outside E38')
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
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch38_') for k in new),'Historical budget ledger changed')

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
 raise ValueError('E38 has no DEV/CONF retirement; only new authored CC0 engineering IDs')

def pretrained_source_ready(root,rows,reference):
 checked_ref(root,reference,rows,MODEL_SOURCE_PATH);source=parse(root/MODEL_SOURCE_PATH)
 expected={'epoch':38,'kind':KIND,'repository':MODEL_REPOSITORY,'revision':MODEL_REVISION,'weights_file':MODEL_WEIGHTS['file'],
  'weights_bytes':MODEL_WEIGHTS['bytes'],'weights_sha256':MODEL_WEIGHTS['sha256'],'training_lineage_complete':False,
  'source_parameter_dtype':SOURCE_PARAMETER_DTYPE,'source_serialization_format':SOURCE_SERIALIZATION_FORMAT,'compute_dtype':COMPUTE_DTYPE,'native_id2label':{'0':'contradiction','1':'neutral','2':'entailment'},
  'canonical_E_C_N_from_raw':[2,0,1],'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[]}
 require(all(same_fact(source.get(k),v)for k,v in expected.items()),'Exact original single-XXL identity/order/dtype/HOLD differs')
 header=ref(root,XXL_WEIGHT_METADATA_PATH);checked_ref(root,header,rows,XXL_WEIGHT_METADATA_PATH);require(header==XXL_WEIGHT_METADATA_REF and source.get('original_archive_metadata')==header,'Exact historical original weight metadata required')
 meta=parse(root/XXL_WEIGHT_METADATA_PATH)
 require(meta.get('status')=='ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE'and meta.get('format')==SOURCE_SERIALIZATION_FORMAT
  and meta.get('weights')=={'bytes':MODEL_WEIGHTS['bytes'],'sha256':MODEL_WEIGHTS['sha256']}
  and meta.get('source_parameter_dtype')=='F16'and meta.get('state_tensor_count')==782 and meta.get('floating_state_tensor_elements')==1566915075
  and meta.get('metadata_pickle_count')==5 and meta.get('storage_data_ends_at_filelength')is True
  and all(type(meta.get(k))is int and meta[k]==0 for k in ('storage_payloads_decoded','unsafe_unpickling_calls','checkpoint_functions_invoked','ML_imports','model_tokenizer_native_calls')),
  'Original metadata/legacy F16 shape must be the previously inspected exact source')
 legacy=ref(root,LEGACY_LOAD_PLAN_PATH);checked_ref(root,legacy,rows,LEGACY_LOAD_PLAN_PATH);require(legacy==LEGACY_LOAD_PLAN_REF and source.get('legacy_original_load_plan')==legacy,'Exact historical restricted legacy plan required')
 policy=parse(root/LEGACY_LOAD_PLAN_PATH).get('future_frozen_loader_policy',{})
 expected_load={'serialization_format':SOURCE_SERIALIZATION_FORMAT,'weights_only':True,'mmap':False,'map_location':'cpu','trust_remote_code':False,
  'unrestricted_pickle_allowed':False,'extra_pickle_safe_globals_added':0,'ZIP_fallback_allowed':False,'legacy_tar_fallback_in_statics':False,
  'alternate_checkpoint_allowed':False,'dynamic_quantization_allowed':False,'compute_dtype':'F32','before_source_freeze_actual_torch_loads_allowed':0,'model_initializations_in_acquisition_or_static_inspection':0}
 require(all(same_fact(policy.get(k),v)for k,v in expected_load.items()),'Restricted legacy load policy differs')
 profile_ref=ref(root,MODEL_PROFILES_PATH);checked_ref(root,profile_ref,rows,MODEL_PROFILES_PATH);profiles=parse(root/MODEL_PROFILES_PATH)
 require(profiles.get('epoch')==38 and profiles.get('kind')==KIND and profiles.get('shared_partition_model')=='xxlarge'and set(profiles.get('profiles',{}))=={'xxlarge'},'Exactly one XXL profile required')
 profile=profiles['profiles']['xxlarge'];lock_path=P+'candidate/epoch38/MODEL_ASSETS.json';lock_ref=ref(root,lock_path);checked_ref(root,lock_ref,rows,lock_path)
 for key,value in {'model_source':reference,'model_assets_lock':lock_ref,'model_directory':MODEL_DIRECTORY,'native_label_order':['Contradiction','NotMentioned','Entailment'],
  'canonical_E_C_N_from_raw':[2,0,1],'compute_dtype':'F32','original_archive_metadata':header,'legacy_original_load_plan':legacy}.items():require(same_fact(profile.get(key),value),'Single-XXL profile differs: '+key)
 admission=source.get('metadata_admission')
 require(isinstance(admission,dict),'Historic licence/lineage admission reference required');checked_ref(root,admission,rows)
 return source

def check_plan(root,cont,rows,current,phase,oldrows):
 frozen=cont.get('epoch38_frozen_study');require(isinstance(frozen,dict)and set(frozen)=={'plan','source_freeze'},'Exact current source refs required')
 checked_ref(root,frozen['plan'],rows,PLAN_PATH);checked_ref(root,frozen['source_freeze'],rows,FREEZE_PATH);plan,freeze=parse(root/PLAN_PATH),parse(root/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==38 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Wrong current source epoch/kind/BASE')
 require(same_fact(plan.get('data_roles'),ROLES)and plan.get('hypotheses')==HYPOTHESES and plan.get('source_freeze')==frozen['source_freeze']and plan.get('actual_project')==str(root),'Wrong frozen roles/hypotheses/root/freeze')
 expected={'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0}
 require(all(same_fact(plan.get('limits',{}).get(k),v)for k,v in expected.items()),'Fixed one-phase CPU/spend limits differ')
 require(plan.get('training_lineage_complete')is False and plan.get('diagnostic_only')is True and same_fact(plan.get('probability_temperature'),1.0),'Lineage/HOLD/raw T1 scope must remain explicit')
 require(plan.get('source_serialization_format')==SOURCE_SERIALIZATION_FORMAT and plan.get('source_parameter_dtype')=='F16'and plan.get('compute_dtype')=='F32','Exact original legacy source/compute format differs')
 resource=ref(root,RESOURCE_POLICY_SOURCE_PATH);checked_ref(root,resource,rows);require(same_fact(plan.get('host_admission_policy'),frozen_resource_policy(root,rows))and plan.get('resource_policy_source')==resource,'Frozen dispatcher resource source/policy differs')
 protocol=audit_protocol_ready(root,rows);protocol_ref=ref(root,AUDIT_PROTOCOL_PATH)
 require(plan.get('protocol')==protocol_ref and plan.get('protocol_path')==AUDIT_PROTOCOL_PATH and plan.get('protocol_sha256')==protocol_ref['sha256']and protocol['candidate_protocol']==ref(root,plan['audit_protocol_path']),'Independent/candidate protocol aliases differ')
 require(plan.get('primary')==PRIMARY_ARM and plan.get('root_contract')==ROOT_CONTRACT_REF and same_fact(plan.get('engineering_gate'),ENGINEERING_GATE)and same_fact(plan.get('probability_policy'),PROBABILITY_POLICY),'Root contract/gate/probability policy changed')
 require(plan.get('engineering_only')is True and plan.get('benchmark_accuracy')is None and plan.get('promotion_allowed')is False and plan.get('used_confirmation_identities')==[],'No benchmark acceptance/identity authorization')
 require(all(plan.get(k)==[]for k in ('training_ids','development_ids','calibration_ids','confirmation_ids'))and plan.get('engineering_ids')==ENGINEERING_IDS,'No benchmark-role case or different engineering IDs')
 require(same_fact(plan.get('arms'),ARM_NAMES)and same_fact(plan.get('raw_context_names'),RAW_CONTEXT_NAMES)and same_fact(plan.get('metric_arm_names'),METRIC_ARM_NAMES)
  and same_fact(plan.get('readout_reuse_map'),READOUT_REUSE_MAP)and plan.get('actual_NLI_forwards')==36 and plan.get('final_derived_forecasts')==60,'Three measured contexts/five derived arms reuse differs')
 require(same_fact(plan.get('reader_execution_order'),MODEL_EXECUTION_ORDER)and same_fact(plan.get('model_forward_counts'),MODEL_FORWARD_COUNTS),'Exactly one original XXL36-readout reader required')
 require(same_fact(plan.get('proof_enabled_roles'),PROOF_ENABLED_ROLES)and same_fact(plan.get('retrieval_policy'),frozen_retrieval_policy(root,rows))and same_fact(plan.get('metrics_policy'),frozen_metrics_policy(root,rows)),'Frozen proof/retrieval/metric policy differs')
 require(plan.get('native_queries_per_case')==1 and plan.get('maximum_native_queries')==12 and plan.get('guardian_scope')==str(OWNER_SCOPE_DIR)
  and plan.get('model_directory')==MODEL_DIRECTORY and plan.get('external_python_environment')==str(EXTERNAL_ENV_PATH)and plan.get('inference_python')==str(EXTERNAL_ENV_PATH/'bin/python')and plan.get('runtime_reuse_policy')==RUNTIME_REUSE_POLICY,'Frozen native/runtime/model layout differs')
 require(not any(k.startswith('dev_inputs')or k.startswith('baseline_model')for k in plan),'No DEV or second model paths in E38')
 for key in ('engineering_inputs','engineering_oracle','numeric_oracle','xxlarge_weight_metadata','legacy_original_load_plan','resource_policy_source','model_assets_lock','model_profiles','root_contract','model_assets_expected','model_assets_validator','real_model_assets_guard_receipt'):
  path=plan.get(key+'_path');require(path in rows and rows[path]['sha256']==plan.get(key+'_sha256'),'Missing frozen identity: '+key)
 require(plan.get('model_assets_expected')==MODEL_ASSETS_EXPECTED_REF and plan.get('model_assets_validator')==ref(root,MODEL_ASSETS_VALIDATOR_PATH)and plan.get('real_model_assets_guard_receipt')==real_model_assets_guard_ready(root,rows),'Plan complete unstubbed actual guard receipt and sources required')
 pretrained_source_ready(root,rows,plan.get('pretrained_model_source'));require(cont.get('epoch38_pretrained_model_source')==plan['pretrained_model_source'],'Continuation model source projection differs')
 pins=plan.get('pins');require(isinstance(pins,list)and pins,'Current source pins required');indexed={}
 for row in pins:require(row['path']not in indexed,'Duplicate source pin');checked_ref(root,row);indexed[row['path']]=row
 entries=freeze.get('entries');require(isinstance(entries,list)and entries,'Freeze entries required');seen=set()
 for row in entries:
  path=checked_ref(root,row,rows);require(path not in seen and path in current and path not in {PLAN_PATH,FREEZE_PATH}and indexed.get(path)==row,'Invalid/unpinned freeze entry');seen.add(path)
 if phase=='source':require(seen==set(current)-{PLAN_PATH,FREEZE_PATH},'SOURCE freeze omits or includes extras')
 for path,row in [(FREEZE_PATH,frozen['source_freeze']),(MODEL_SOURCE_PATH,plan['pretrained_model_source']),(MODEL_PROFILES_PATH,plan['model_profiles']),
  (XXL_WEIGHT_METADATA_PATH,XXL_WEIGHT_METADATA_REF),(LEGACY_LOAD_PLAN_PATH,LEGACY_LOAD_PLAN_REF),(ROOT_CONTRACT_PATH,ROOT_CONTRACT_REF),(RESOURCE_POLICY_SOURCE_PATH,resource),(AUDIT_PROTOCOL_PATH,protocol_ref),(MODEL_ASSETS_EXPECTED_PATH,MODEL_ASSETS_EXPECTED_REF),(MODEL_ASSETS_VALIDATOR_PATH,plan['model_assets_validator']),(REAL_MODEL_ASSETS_GUARD_RECEIPT_PATH,plan['real_model_assets_guard_receipt'])]:require(indexed.get(path)==row,'Required model/protocol/resource source not pinned: '+path)
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
 owner=active.get('physical_owner',{});require(active.get('run_id')==OWNER_RUN_ID and(owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==OWNER_PIN and owner.get('expires_unix')==OWNER_EXPIRES_UNIX,'Wrong actual E38 guardian')
 require(type(active.get('native_allowed'))is int and active['native_allowed']==0 and active.get('experiments_active')is False and active.get('checkpoint_parent')==args.parent and active.get('OS_lock_held')is True,'Immediate native execution must remain closed')
 for key in ('confirmation_allowed','conditional_confirmation_allowed','conditional_train_allowed','conditional_dev_allowed'):require(type(active.get(key))is int and active[key]==0,'TRAIN/CONF allowances must remain zero')
 if phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH38_PLANNING_LEASE' and active.get('state')=='EPOCH38_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION' and active.get('work_active')is True and type(active.get('conditional_engineering_allowed'))is int and active['conditional_engineering_allowed']==1,'SOURCE conditional DEV gate differs')
  require(not any(path.startswith(E+'runs/') or path in {E+'RESULTS.json',E+'EPOCH_MANIFEST.json',E+'SOURCE_ADMISSION.json',E+'ENGINEERING_ATTEMPT_RESERVATION.json',*DISPATCH_PATHS.values()}for path in current),'Premeasurement SOURCE contains execution/admission/results')
 else:
  require(set(cp)==set(pcp) and all(cp[k]==v for k,v in pcp.items()if k!='project_files') and all(rows.get(k)==v for k,v in cp_rows(pcp).items()),'Previously published checkpoint/source changed')
  require(cont.get('epoch38_frozen_study')==pcont.get('epoch38_frozen_study'),'Published plan/freeze changed')
  require(pactive.get('state')=='EPOCH38_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION' and active.get('state')=='EPOCH38_CLOSED' and active.get('work_active')is False and type(active.get('conditional_engineering_allowed'))is int and active['conditional_engineering_allowed']==0,'FINAL current phase closure differs')
 require(same_fact(cont.get('epoch38_planning'),pcont.get('epoch38_planning')) and same_fact(cont.get('epoch38_data_roles'),data_role_record()),'Planning/frozen role history differs')
 require(same_fact(cont.get('exposed_development_sets'),oldcont.get('exposed_development_sets')),'No benchmark DEV retirement or relabeling in E38')
 plan=check_plan(root,cont,rows,current,phase,oldrows)
 if phase=='source':require(plan.get('publication_parent')==args.parent and plan.get('publication_parent_trees')==dict(zip(('root','bench','scope'),(args.expected_root,args.expected_bench,args.expected_scope))),'Actual SOURCE parent/trees must be frozen in master plan')
 else:check_final(root,rows,cont,pcont,plan)
 return bodies,prior,oldcp,cp,cont,plan,check_transport(root,oldcont,cont,rows,kit=kit)

def check_final(root,rows,cont,pcont,plan):
 m=parse(root/(E+'EPOCH_MANIFEST.json'));require(m.get('epoch')==38 and m.get('kind')==KIND and m.get('status')in FINAL_STATUSES,'Wrong engineering outcome');verify_flags(m)
 require(m.get('confirmation')==[] and m.get('used_confirmation_identities')==[] and m.get('all_slots_closed')is True and m.get('diagnostic_qualified')is False and type(m.get('engineering_passed'))is bool and m.get('readiness_qualified')is m['engineering_passed'],'Engineering-only verdict invalid')
 require(same_fact(m.get('phase_remaining'),{'train':0,'dev':0,'calibration':0,'confirmation':0,'engineering':0}),'Final phase_remaining must close every allowance')
 for key,path in [('plan',PLAN_PATH),('source_freeze',FREEZE_PATH),('results',E+'RESULTS.json'),('pretrained_model_source',MODEL_SOURCE_PATH),('model_profiles',MODEL_PROFILES_PATH),('model_assets_expected',MODEL_ASSETS_EXPECTED_PATH),('model_assets_validator',MODEL_ASSETS_VALIDATOR_PATH),('real_model_assets_guard_receipt',REAL_MODEL_ASSETS_GUARD_RECEIPT_PATH),('original_archive_metadata',XXL_WEIGHT_METADATA_PATH),('legacy_original_load_plan',LEGACY_LOAD_PLAN_PATH)]:checked_ref(root,m.get(key),rows,path)
 result=parse(root/m['results']['path']);verify_flags(result)
 require(result.get('benchmark_accuracy')is None,'Engineering data cannot be a benchmark accuracy')
 for key in ('status','diagnostic_qualified','engineering_passed','readiness_qualified','actual_execution'):require(same_fact(result.get(key),m[key]),'Manifest/result differs: '+key)
 report_path=checked_ref(root,m.get('independent_report'),rows);require(report_path.startswith(P+'audit/epoch38/'),'Current independent report required')
 report=parse(root/report_path);require(report.get('epoch')==38 and report.get('kind')==KIND and report.get('checks_passed')is True and report.get('diagnostic_qualified')is False and report.get('engineering_passed')is m['engineering_passed'],'Independent final binding/verdict differs')
 evidence=phase_evidence(root,'engineering',m['plan'],rows);actual=aggregate_actual(evidence);require_final_physical_closure(actual);require(same_fact(m['actual_execution'],actual),'Actual counters/resources differ')
 refs={'raw':evidence['raw'],'execution':evidence['execution'],'results':m['results'],'pretrained_model_source':m['pretrained_model_source'],'model_profiles':m['model_profiles'],'original_archive_metadata':m['original_archive_metadata'],'legacy_original_load_plan':m['legacy_original_load_plan']}
 require(all(same_fact(report.get('evidence',{}).get(k),v)for k,v in refs.items()),'Independent evidence references differ')
 if actual['worker_attempts']:
  ap=E+'SOURCE_ADMISSION.json';ar=ref(root,ap);checked_ref(root,ar,rows,ap);admission=parse(root/ap)
  require(admission.get('epoch')==38 and admission.get('kind')==KIND and admission.get('verified_actual_remote_readback')is True and admission.get('published_source_commit')==cont['prior_published_base_commit'],'Actual SOURCE-before-engineering admission missing')
  require(admission.get('plan_sha256')==m['plan']['sha256'] and admission.get('source_freeze_sha256')==m['source_freeze']['sha256'] and admission.get('pretrained_model_source')==m['pretrained_model_source'] and admission.get('model_profiles_sha256')==m['model_profiles']['sha256']
   and admission.get('model_assets_lock_sha256')==plan['model_assets_lock_sha256']
   and admission.get('xxlarge_weight_metadata_sha256')==plan['xxlarge_weight_metadata_sha256']
   and admission.get('legacy_original_load_plan_sha256')==plan['legacy_original_load_plan_sha256'],'Admitted source identities differ')
  require(admission.get('owner_pid')==OWNER_PIN[0] and admission.get('owner_startticks')==OWNER_PIN[1],'Current admission guardian differs')
 if m['engineering_passed']:
  require(phase_completed(evidence) and m['status']=='ACCEPTED_ENGINEERING_ADMISSION_ONLY','Positive engineering admission requires complete bounded36 readouts/60 derived forecasts')
 else:require(m['status']in {'REJECTED_ENGINEERING_ADMISSION','REJECTED_ENGINEERING_INTEGRITY'},'Rejected engineering status differs')
 before,new=pcont.get('execution_observed',{}),cont.get('execution_observed',{});counts=cumulative_counts(actual)
 require(before.get('epoch37_cumulative_corpus_attempts')is None and before.get('epoch37_cumulative_completed_corpus_batches')is None and before.get('epoch37_cumulative_bounded_native_process_attempts')==38,'Preserve E37 UNKNOWN actual corpus totals and known separate outer38')
 require(all(same_fact(new.get(k),v)for k,v in before.items()) and all(k in before or k.startswith('epoch38_')for k in new) and same_fact(new.get('epoch38_actual_execution'),actual),'Historical execution changed/current effort missing')
 for key,value in {'epoch38_cumulative_corpus_attempts':counts['corpus_attempts'],'epoch38_cumulative_completed_corpus_batches':counts['completed_corpus_batches'],'epoch38_cumulative_bounded_native_process_attempts':counts['bounded_native_process_attempts'],'epoch38_verified_corpus_attempts_lower_bound':counts['verified_corpus_attempts_lower_bound'],'epoch38_verified_completed_corpus_batches_lower_bound':counts['verified_completed_corpus_batches_lower_bound']}.items():require(same_fact(new.get(key),value),'Cumulative count differs: '+key)
 require(same_fact(m.get('cumulative_execution'),counts) and same_fact(result.get('cumulative_execution'),counts),'Manifest/result cumulative count differs')
 oldref=pcont['rejection_ledger'];checked_ref(root,oldref,rows);newref=cont['rejection_ledger'];checked_ref(root,newref,rows,E+'REJECTION_LEDGER.json');oldledger,ledger=parse(root/oldref['path']),parse(root/newref['path'])
 for key,value in oldledger.items():require(same_fact(ledger.get(key,[])[:len(value)],value)if key=='rejections'else same_fact(ledger.get(key),value),'Historical rejection metadata changed: '+key)
 require(all(k in oldledger or k.startswith('epoch38_')for k in ledger),'New rejection key outside E38')
 budget={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
 require(same_fact(ledger.get('epoch38_budget'),budget) and same_fact(ledger.get('epoch38_actual_execution'),actual) and same_fact(ledger.get('epoch38_cumulative_execution'),counts) and same_fact(cont.get('cumulative_budget_ledger',{}).get('epoch38_budget'),budget),'Used/closed budget differs')
 decision=ledger.get('epoch38_decision',{});verify_flags(decision)
 for key,value in {'status':m['status'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed'],'results':m['results']}.items():require(same_fact(decision.get(key),value),'Decision differs: '+key)
 if m['engineering_passed']:require(ledger['rejections']==oldledger['rejections'] and ledger.get('epoch38_engineering_qualification',{}).get('results')==m['results'],'Engineering qualification record missing')
 else:require(len(ledger['rejections'])==len(oldledger['rejections'])+1 and ledger['rejections'][-1].get('epoch')==38 and ledger['rejections'][-1].get('status')==m['status'] and ledger['rejections'][-1].get('results')==m['results'] and bool(ledger['rejections'][-1].get('reason')),'Exact rejection/reason required')
 summary={**FLAGS,'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':m['results'],'status':m['status'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed'],'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
 require(same_fact(cont.get('epoch38_final'),summary),'Final continuation projection differs')
 epoch={**FLAGS,'epoch':38,'kind':KIND,'status':m['status'],'manifest':summary['manifest'],'results':m['results'],'diagnostic_qualified':False,'engineering_passed':m['engineering_passed'],'readiness_qualified':m['engineering_passed']}
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
  'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(before),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(cp_rows(cp)),'new_epoch38_public_files':len(current),'expected_Git_leaves':len(expected),
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
