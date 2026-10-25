"""E38 source-only master freeze. No model, tokenizer, native or label join."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
P='experiments/sota-2026-10-22/'
SOURCE='7c50ba99848f6a13707eeec6c4947291a8478e5c'
KIND='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f')
GUARDIAN_SCOPE=DEFAULT_SCOPE
EXTERNAL_ENV=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL_DIRECTORY=Path('/workspace/ruvector-e38-reader-assets/ms-xxlarge-8f8b43dd')

def exact_ref(root,name):
 path=root/name
 if not path.is_file()or any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 b=path.read_bytes();return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def inherited_source_dependencies(root):
 path=P+'candidate/epoch38/research/SOURCE_DEPENDENCIES.json';manifest=exact_ref(root,path);source=json.loads((root/path).read_text())
 expected={P+'candidate/epoch3/models.py',P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 if(source.get('epoch')!=38 or source.get('source_checkpoint')!=SOURCE or source.get('inactive_old_modules_imported')!=[]):raise ValueError('Wrong inherited source verification scope')
 rows=source.get('active_inherited_sources')
 if not isinstance(rows,list)or len(rows)!=2 or {r['path']for r in rows}!=expected:raise ValueError('Exactly two active inherited source dependencies required; no stale old context parser')
 result=[manifest]
 for row in rows:
  actual=exact_ref(root,row['path']);b=(root/row['path']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  if any(actual[k]!=row[k]for k in('path','bytes','sha256'))or blob!=row['actual_git_blob_sha1']:raise ValueError('Inherited Git/byte identity changed: '+row['path'])
  result.append(actual)
 return result

def write_new(path,value):
 with path.open('x',encoding='utf-8')as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)

def validate_operation_budgets(table,schema):
 operations=table.get('engineering')
 if not isinstance(operations,dict)or not operations or any(not isinstance(k,str)or type(v)is not int or v<0 for k,v in operations.items()):raise ValueError('Exact integer engineering-only fixed counter table required')
 budget={'NLI_forward_calls_attempted':36,'NLI_forward_calls_completed':36,'NLI_readouts_completed':36,
  'ENGINEERING_forward_calls_attempted':36,'ENGINEERING_forward_calls_completed':36,'ENGINEERING_contexts_completed':36,
  'derived_forecasts_completed':60,'readout_reuse_receipts_completed':60,'source_analysis_calls_attempted':48,'source_analysis_calls_completed':48,
  'certificate_decisions_attempted':36,'certificate_decisions_completed':36,'full_source_contexts_completed':12,'coverage_contexts_completed':24,
  'native_complete_unitset_cases_verified':12,'sequential_model_lifecycles_completed':1,
  'native_queries_attempted':12,'native_queries_completed':12,'corpus_batches_attempted':1,'corpus_batches_completed':1,
  'native_index_initializations_attempted':12,'native_index_initializations_completed':12,'native_len_calls_attempted':24,'native_len_calls_completed':24,
  'model_initializations_attempted':1,'model_initializations_completed':1,'tokenizer_initializations_attempted':1,'tokenizer_initializations_completed':1,
  'native_helper_starts_attempted':1,'native_helper_starts_completed':1,'native_binary_loads_attempted':1,'native_binary_loads_completed':1,
  'native_version_calls_attempted':1,'native_version_calls_completed':1,'BGE_initializations_attempted':1,'BGE_initializations_completed':1,
  'ORT_sessions_attempted':1,'ORT_sessions_completed':1,'ENGINEERING_input_bank_reads':1,'engineering_oracle_reads':1,
  'engineering_oracle_expected_labels_accessed':12,'engineering_native_predictions_compared':12,
  'model_unloads_attempted':1,'model_unloads_completed':1}
 for prefix in('NLI_capped_pair_tokenizer_calls','NLI_full_pair_tokenizer_calls','pair_tokenizations'):
  for suffix in('attempted','completed'):budget[prefix+'_'+suffix]=36
 for suffix in('model_initializations_attempted','model_initializations_completed','tokenizer_initializations_attempted','tokenizer_initializations_completed','model_unloads_attempted','model_unloads_completed'):budget['xxlarge_'+suffix]=1
 for suffix in('forward_calls_attempted','forward_calls_completed','readouts_completed'):budget['xxlarge_'+suffix]=36
 for key in('paid_calls','GPU_calls','HTTP_requests','Python_network_operations_attempted','Node_network_operations_attempted','training_steps','fits','calibration_calls','generation_calls','full104_requests',
  'source_evidence_lists_accessed','other_role_annotation_choices_accessed','backward_calls_attempted','backward_calls_completed',
  'optimizer_initializations_attempted','optimizer_initializations_completed','optimizer_steps_attempted','optimizer_steps_completed','gradient_clips_attempted','gradient_clips_completed',
  'parameter_artifacts_load_attempted','parameter_artifacts_load_completed','parameter_artifacts_write_attempted','parameter_artifacts_write_completed'):budget[key]=0
 if any(type(operations.get(k))is not int or operations[k]!=v for k,v in budget.items()):raise ValueError('Frozen one-model36-readout/12-query operation budget differs')
 if any(v!=0 for k,v in operations.items()if k.startswith(('TRAIN_','DEV_','CONF_'))):raise ValueError('Benchmark-role operations forbidden')
 if table.get('engineering_rejected',operations)!=operations:raise ValueError('No second/conditional scientific phase allowed')
 if schema.TOTAL_MAX_NLI_FORWARD_CALLS!=36 or schema.TOTAL_FINAL_FORECASTS!=60 or schema.TOTAL_MAX_NATIVE_QUERIES!=12:raise ValueError('36 actual neural readouts and60 derived forecasts must stay distinct')
 return {'engineering':operations}

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch38');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh E38 workspace required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if(study/'plan.json').exists()or(study/'source-freeze.json').exists():raise ValueError('Master plan/freeze already exist; no overwrite/replay')
 candidate=P+'candidate/epoch38/';assets=P+'epoch38/preparation/runtime-assets.lock.json'
 paths={'engineering_inputs':candidate+'engineering.inputs.json','engineering_oracle':candidate+'engineering.oracle.json','audit_protocol':candidate+'ENGINEERING_PROTOCOL.json',
  'model_assets_expected':schema.MODEL_ASSETS_EXPECTED_PATH,'model_assets_validator':schema.MODEL_ASSETS_VALIDATOR_PATH,'real_model_assets_guard_receipt':schema.REAL_MODEL_ASSETS_GUARD_RECEIPT_PATH,'numeric_oracle':candidate+'NUMERIC_ORACLE.json','metrics_policy':schema.METRICS_POLICY_PATH,'runtime_assets_lock':assets,'model_assets_lock':candidate+'MODEL_ASSETS.json',
  'pretrained_model_source':schema.MODEL_SOURCE_PATH,'model_profiles':schema.MODEL_PROFILES_PATH,'xxlarge_weight_metadata':schema.XXL_WEIGHT_METADATA_PATH,
  'legacy_original_load_plan':schema.LEGACY_LOAD_PLAN_PATH,'resource_policy_source':publication.RESOURCE_POLICY_SOURCE_PATH,'root_contract':schema.ROOT_CONTRACT_PATH,
  'inherited_source_dependencies':candidate+'research/SOURCE_DEPENDENCIES.json','proof_source':candidate+'proof.py','proof_policy':candidate+'PROOF_POLICY.json',
  'query_source':candidate+'query.py','query_policy':schema.QUERY_POLICY_PATH,'context_policy':schema.CONTEXT_POLICY_PATH,'source_context':candidate+'source_context.py',
  'runtime_reuse_verification':common.RUNTIME_REUSE_VERIFICATION_PATH,'BGE_source':P+'candidate/epoch3/models.py','runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 required=list(paths.values())+[candidate+n for n in('worker.py','native_helper.cjs','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[publication.AUDIT_PROTOCOL_PATH,args.scorer,schema.MODEL_ASSETS_IDENTITY_HELPER_PATH]
 for name in required:exact_ref(root,name)
 for name in('source_parent','source_root','source_bench','source_scope'):
  if not re.fullmatch('[0-9a-f]{40}',getattr(args,name)):raise ValueError('Exact actual source-parent/tree SHA required')
 if not args.scorer.startswith(P+'audit/epoch38/')or not args.scorer.endswith('.py'):raise ValueError('Current independent scorer source required')
 source=publication.pretrained_source_ready(root,None,exact_ref(root,schema.MODEL_SOURCE_PATH));publication.audit_protocol_ready(root)
 guard_admission=publication.real_model_assets_guard_ready(root);host_policy=publication.frozen_resource_policy(root);resource_source=exact_ref(root,publication.RESOURCE_POLICY_SOURCE_PATH)
 table=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'))
 if table.get('epoch')!=38 or table.get('kind')!=KIND:raise ValueError('Wrong counter source scope')
 ops=validate_operation_budgets(table,schema);python=EXTERNAL_ENV/'bin/python'
 if(not python.is_file()or not python.resolve().is_file()or any(p.is_symlink()for p in python.parents)
  or python.resolve()!=Path(sys.executable).resolve()or Path(sys.prefix).absolute()!=EXTERNAL_ENV):raise ValueError('Exact hash-verified read-only E33 Python/prefix required')
 if MODEL_DIRECTORY.is_symlink()or any(p.is_symlink()for p in MODEL_DIRECTORY.parents):raise ValueError('Symlink model asset directory')
 lock=common.parse(root/assets);dependencies=[]
 for key in('wheel_lock','native_closure','BGE_source'):
  row=exact_ref(root,lock[key+'_path'])
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Runtime dependency changed: '+key)
  dependencies.append(row)
 member=exact_ref(root,lock['python_member_manifest']['path'])
 if member!=lock['python_member_manifest']:raise ValueError('Python member manifest changed')
 members=common.parse(root/member['path'])
 if not isinstance(members,list)or len({r['path']for r in members})!=len(members):raise ValueError('Runtime member manifest must have unique paths')
 common.validate_runtime_member_aliases(lock,member,len(members));dependencies.append(member)
 reuse=exact_ref(root,common.RUNTIME_REUSE_VERIFICATION_PATH);common.validate_runtime_reuse_receipt(lock,reuse,common.parse(root/reuse['path']));dependencies.append(reuse)
 dependencies+=inherited_source_dependencies(root);dependencies.append(source['metadata_admission'])
 if exact_ref(root,source['metadata_admission']['path'])!=source['metadata_admission']:raise ValueError('Exact inherited model licence/lineage metadata changed')
 entries=[]
 for relative in publication.ROOTS:
  directory=root/relative
  if not directory.exists():continue
  for path in sorted(directory.rglob('*')):
   if path.is_symlink():raise ValueError('Symlink in new source tree')
   if path.is_file():
    name=path.relative_to(root).as_posix();common.public_text(name,path.read_bytes());entries.append(exact_ref(root,name))
 entries.sort(key=lambda r:r['path'])
 if len({r['path']for r in entries})!=len(entries):raise ValueError('Duplicate source member')
 if not any(r['path'].endswith('reviewed_build_plan.py')for r in entries):raise ValueError('Reviewed builder itself must be source-frozen')
 if any('/runs/'in r['path']or r['path'].endswith('/SOURCE_ADMISSION.json')or r['path']in set(schema.DISPATCH_PATHS.values())|set(schema.PHASE_RESERVATIONS.values())for r in entries):raise ValueError('Execution/admission exists before freeze')
 freeze={'schema_version':1,'epoch':38,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,
  'engineering_ids':schema.ENGINEERING_IDS,'entries':entries,'inherited_source_dependencies':dependencies,'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],
  'rule':'All reviewed current source, new authored CC0 inputs/oracles, original model/runtime/assets, exact numeric certificate/probability policy and independent scorer freeze before one source-admitted worker.36 actual neural readouts across3 physical contexts supply60 explicit reused/derived forecasts across5 arms. Proof outputs are not rawT1 or calibrated posteriors. Source closure and valid witnesses are mandatory; retrieval omissions never prove insufficient evidence. Labels join once only after all readouts/forecasts; no benchmark generalization/promotion/TRAIN/DEV/calibration/CONF/retry.'}
 summary={'source_files':len(entries),'TRAIN_cases':0,'engineering_cases':12,'engineering_role':schema.ENGINEERING_ROLE,'actual_NLI_forwards':36,
  'final_derived_forecasts':60,'DEV_cases':0,'calibration_cases':0,'confirmation_cases':0,'native_queries':12,'native_corpus_batches':1,
  'arms':schema.ARM_NAMES,'raw_context_names':schema.RAW_CONTEXT_NAMES,'readout_reuse_map':schema.READOUT_REUSE_MAP,'models_native_label_joins_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);fr=exact_ref(root,schema.FREEZE_PATH);pins={r['path']:r for r in entries+dependencies+[fr]}
 plan={'schema_version':1,'epoch':38,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'guardian_scope':str(GUARDIAN_SCOPE),
  'publication_parent':args.source_parent,'publication_parent_trees':dict(zip(('root','bench','scope'),(args.source_root,args.source_bench,args.source_scope))),
  'publication_stage_paths':{'source':str(args.source_stage.absolute()),'final':str(args.final_stage.absolute())},'created_at':datetime.now(timezone.utc).isoformat(),
  'hypothesis':'A source-complete exact-rational typed arithmetic/set certificate layer combined with original XXL raw NLI and coverage-preserving native evidence can improve new financial engineering decisions. Compare unchanged same-model full/native raw controls and matched lexical/full verified controls. One native query per source supplies shared rankings. Numerical closure and explicit compatible-world witnesses are required; no case-ID lookup, unsupported-scope certificate or retrieval-miss absence inference. Preserve raw logits/rawT1 vectors and record only a valid-certificate max-mass transposition as a derived forecast. No model strengthening, benchmark generalization or eligibility claim.',
  'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'engineering_ids':schema.ENGINEERING_IDS,'training_ids':[],'development_ids':[],'calibration_ids':[],'confirmation_ids':[],
  'engineering_only':True,'benchmark_accuracy':None,'promotion_allowed':False,'used_confirmation_identities':[],'training_lineage_complete':False,'diagnostic_only':True,
  'probability_temperature':1.0,'raw_probability_temperature':1.0,'final_probability_policy':'SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION','probability_policy':schema.PROBABILITY_POLICY,
  'metrics_policy':publication.frozen_metrics_policy(root),'retrieval_policy':publication.frozen_retrieval_policy(root),'protocol':exact_ref(root,publication.AUDIT_PROTOCOL_PATH),
  'protocol_path':publication.AUDIT_PROTOCOL_PATH,'protocol_sha256':exact_ref(root,publication.AUDIT_PROTOCOL_PATH)['sha256'],'scorer':exact_ref(root,args.scorer),
  'source_freeze':fr,'source_freeze_path':fr['path'],'source_freeze_sha256':fr['sha256'],'root_contract':schema.ROOT_CONTRACT_REF,
  'pretrained_model_source':exact_ref(root,schema.MODEL_SOURCE_PATH),'model_profiles':exact_ref(root,schema.MODEL_PROFILES_PATH),'resource_policy_source':resource_source,'model_assets_expected':schema.MODEL_ASSETS_EXPECTED_REF,'model_assets_validator':exact_ref(root,schema.MODEL_ASSETS_VALIDATOR_PATH),'real_model_assets_guard_receipt':guard_admission,
  'engineering_role':schema.ENGINEERING_ROLE,'primary':schema.PRIMARY_ARM,'engineering_gate':schema.ENGINEERING_GATE,'arms':schema.ARM_NAMES,'raw_context_names':schema.RAW_CONTEXT_NAMES,
  'metric_arm_names':schema.METRIC_ARM_NAMES,'readout_reuse_map':schema.READOUT_REUSE_MAP,'actual_NLI_forwards':36,'final_derived_forecasts':60,
  'native_queries_per_case':1,'maximum_native_queries':12,'proof_enabled_roles':schema.PROOF_ENABLED_ROLES,'source_parameter_dtype':'F16','source_serialization_format':schema.SOURCE_SERIALIZATION_FORMAT,
  'compute_dtype':'F32','worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(python),
  'external_python_environment':str(EXTERNAL_ENV),'runtime_reuse_policy':common.RUNTIME_REUSE_POLICY,'model_directory':str(MODEL_DIRECTORY),
  'reader_execution_order':schema.MODEL_EXECUTION_ORDER,'model_forward_counts':schema.MODEL_FORWARD_COUNTS,'expected_operation_counters':ops,
  'counter_table':exact_ref(root,candidate+'EXPECTED_COUNTERS.json'),'phase_limits':{'engineering':{'actual_NLI_forwards':36,'final_derived_forecasts':60,'native_queries':12,'optimizer_steps':0}},
  'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},
  'pins':[pins[k]for k in sorted(pins)],**schema.FLAGS,'confirmation':[],'CPU_scope':'Kernel affinity0,1 and source-frozen compute-thread cap before model/native imports; observed threads retained.',
  'network_scope':'Frozen API interposition; only previously source-bound urllib3 literal IPv6 loopback capability bind/close allowed. No communication/listening/DNS allowance; opaque compiled internals UNKNOWN.',
  'host_admission_policy':host_policy}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 plan['engineering_rejected_operation_counters']=ops
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':fr,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true')
 for n in('source-parent','source-root','source-bench','source-scope'):cli.add_argument('--'+n,required=True)
 for n in('source-stage','final-stage'):cli.add_argument('--'+n,type=Path,required=True)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))
