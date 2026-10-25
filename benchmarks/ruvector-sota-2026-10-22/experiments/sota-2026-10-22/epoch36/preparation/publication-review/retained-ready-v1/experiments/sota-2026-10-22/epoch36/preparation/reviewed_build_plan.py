"""E36 source-only master freeze. No inference, label join, fitting or network.
All authored CC0 texts/oracles and execution/scoring/publication source freeze
before the sole bounded engineering phase; inherited benchmark roles stay empty.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
P='experiments/sota-2026-10-22/'
SOURCE='d73fcce4c45f7d8f6f1c5bfbf3599ceddf560be3'
KIND='ENGINEERING_PAIRED_READER_SOURCE_COVERAGE'
DEFAULT_SCOPE=Path('/workspace/ruvector-epoch36-d73fcce4c45f')
GUARDIAN_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch36-d73fcce4c45f')
EXTERNAL_ENV=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL_DIRECTORY=Path('/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd')
BASELINE_MODEL_DIRECTORY=Path('/workspace/ruvector-e36-reader-assets/moritz-b3546ea6')
INHERITED_DEPENDENCY_CATALOGUE_SHA256='93436a8a006e496566aefc6fccc58263652a8aebc5eaedd1f9434e5655192da1'

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def inherited_context_dependencies(root):
 expected={P+'candidate/epoch6/context.py':'28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2',P+'candidate/epoch15/context.py':'9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'}
 rows=[exact_ref(root,name)for name in expected]
 if any(row['sha256']!=expected[row['path']]for row in rows):raise ValueError('Transitive source-context dependency changed')
 return rows

def inherited_source_dependencies(root):
 path=P+'candidate/epoch36/research/SOURCE_DEPENDENCIES.json'
 manifest=exact_ref(root,path)
 if manifest['sha256']!=INHERITED_DEPENDENCY_CATALOGUE_SHA256:raise ValueError('Reviewed inherited dependency catalogue changed')
 source=json.loads((root/path).read_text())
 expected={P+'candidate/epoch3/models.py',P+'candidate/epoch6/context.py',P+'candidate/epoch15/context.py',P+'candidate/epoch35/research/MODEL_SOURCE_ADMISSION.json',P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 if source.get('epoch')!=36 or source.get('actual_source_commit')!=SOURCE or source.get('status')!='EXACT_INHERITED_SOURCE_DEPENDENCIES_VERIFIED_BEFORE_FREEZE' or source.get('actual_model_tokenizer_native_calls')!=0:raise ValueError('Wrong inherited source verification scope')
 rows=source.get('dependencies')
 if not isinstance(rows,list)or len(rows)!=5 or {r['path']for r in rows}!=expected:raise ValueError('Exact five active inherited source dependencies required')
 result=[]
 for row in rows:
  actual=exact_ref(root,row['path']);data=(root/row['path']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if any(actual[k]!=row[k]for k in ('path','bytes','sha256'))or blob!=row['actual_Git_blob_sha1']:raise ValueError('Inherited source Git/byte identity changed: '+row['path'])
  result.append(actual)
 return result

def write_new(path,value):
 with path.open('x',encoding='utf-8')as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def validate_operation_budgets(counter_table,schema):
 ops={'engineering':counter_table.get('engineering')}
 if not isinstance(ops,dict)or set(ops)!={'engineering'}or not isinstance(ops['engineering'],dict)or not ops['engineering']or any(not isinstance(k,str)or type(v)is not int or v<0 for k,v in ops['engineering'].items()):raise ValueError('Exact engineering-only counter table required')
 budget={'NLI_forward_calls_attempted':54,'NLI_forward_calls_completed':54,'NLI_readouts_completed':54,
  'ENGINEERING_forward_calls_attempted':54,'ENGINEERING_forward_calls_completed':54,'ENGINEERING_contexts_completed':54,
  'DEV_forward_calls_attempted':0,'DEV_forward_calls_completed':0,
  'native_queries_attempted':9,'native_queries_completed':9,'corpus_batches_attempted':1,'corpus_batches_completed':1,
  'native_index_initializations_attempted':9,'native_index_initializations_completed':9,
  'native_helper_starts_attempted':1,'native_helper_starts_completed':1,'native_binary_loads_attempted':1,'native_binary_loads_completed':1,
  'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_len_calls_attempted':18,'native_len_calls_completed':18,
  'model_initializations_attempted':2,'model_initializations_completed':2,'tokenizer_initializations_attempted':2,'tokenizer_initializations_completed':2,
  'BGE_initializations_attempted':1,'BGE_initializations_completed':1,'engineering_oracle_reads':1,
  'engineering_oracle_expected_labels_accessed':9,'engineering_native_predictions_compared':9,
  'full_source_contexts_completed':18,'two_group_contexts_completed':36,'native_complete_unitset_cases_verified':9,
  'model_unloads_attempted':2,'model_unloads_completed':2,'sequential_model_lifecycles_completed':2}
 for prefix in ('NLI_capped_pair_tokenizer_calls','NLI_full_pair_tokenizer_calls','pair_tokenizations'):
  for suffix in ('attempted','completed'):budget[prefix+'_'+suffix]=54
 for prefix in ('ORT_sessions',):
  for suffix in ('attempted','completed'):budget[prefix+'_'+suffix]=1
 budget['ENGINEERING_input_bank_reads']=1
 for key in ('paid_calls','GPU_calls','HTTP_requests','Node_network_operations_attempted','Python_network_operations_attempted',
  'training_steps','fits','calibration_calls','generation_calls','full104_requests','source_evidence_lists_accessed','other_role_annotation_choices_accessed',
  'backward_calls_attempted','backward_calls_completed','optimizer_initializations_attempted','optimizer_initializations_completed','optimizer_steps_attempted','optimizer_steps_completed',
  'gradient_clips_attempted','gradient_clips_completed','parameter_artifacts_load_attempted','parameter_artifacts_load_completed','parameter_artifacts_write_attempted','parameter_artifacts_write_completed'):
  budget[key]=0
 for profile,n in [('b354',18),('xxlarge',36)]:
  for suffix in ('model_initializations_attempted','model_initializations_completed','tokenizer_initializations_attempted','tokenizer_initializations_completed','model_unloads_attempted','model_unloads_completed'):budget[profile+'_'+suffix]=1
  for suffix in ('forward_calls_attempted','forward_calls_completed','readouts_completed'):budget[profile+'_'+suffix]=n
 if any(type(ops['engineering'].get(k))is not int or ops['engineering'][k]!=v for k,v in budget.items()):raise ValueError('Frozen paired-reader54/9/2 lifecycle budget differs')
 if any(v!=0 for k,v in ops['engineering'].items() if k.startswith(('TRAIN_','DEV_','CONF_'))):raise ValueError('No benchmark-role operation allowed')
 if counter_table.get('engineering_rejected')!=ops['engineering']:raise ValueError('No conditional second corpus path in E36')
 if schema.TOTAL_MAX_NLI_FORWARD_CALLS!=54 or schema.TOTAL_MAX_NATIVE_QUERIES!=9:raise ValueError('Schema budget differs')
 return ops

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch36');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh E36 workspace required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if(study/'plan.json').exists()or(study/'source-freeze.json').exists():raise ValueError('Master plan/freeze already exist; no overwrite')
 candidate=P+'candidate/epoch36/';assets=P+'epoch36/preparation/runtime-assets.lock.json'
 paths={'engineering_inputs':candidate+'engineering.inputs.json','engineering_oracle':candidate+'engineering.oracle.json','audit_protocol':candidate+'ENGINEERING_PROTOCOL.json','numeric_oracle':candidate+'NUMERIC_ORACLE.json','runtime_assets_lock':assets,'model_assets_lock':candidate+'MODEL_ASSETS.json','pretrained_model_source':schema.MODEL_SOURCE_PATH,'baseline_model_source':schema.BASELINE_MODEL_SOURCE_PATH,'baseline_model_assets_lock':candidate+'BASELINE_MODEL_ASSETS.json','model_profiles':schema.MODEL_PROFILES_PATH,'xxlarge_weight_metadata':schema.XXL_WEIGHT_METADATA_PATH,'legacy_original_load_plan':schema.LEGACY_LOAD_PLAN_PATH,'inherited_source_dependencies':candidate+'research/SOURCE_DEPENDENCIES.json','proof_source':candidate+'proof.py','proof_policy':candidate+'PROOF_POLICY.json','query_source':candidate+'query.py','query_policy':candidate+'QUERY_POLICY.json','source_context':candidate+'source_context.py','runtime_reuse_verification':common.RUNTIME_REUSE_VERIFICATION_PATH,'BGE_source':P+'candidate/epoch3/models.py','runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 required=list(paths.values())+[candidate+n for n in('worker.py','native_helper.cjs','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[P+'audit/epoch36/protocol.json',args.scorer]
 for name in required:exact_ref(root,name)
 for name in('source_parent','source_root','source_bench','source_scope'):
  if not re.fullmatch('[0-9a-f]{40}',getattr(args,name)):raise ValueError('Exact actual source-parent/tree SHA required')
 if not args.scorer.startswith(P+'audit/epoch36/')or not args.scorer.endswith('.py'):raise ValueError('Current independent scorer source required')
 publication.pretrained_source_ready(root,None,exact_ref(root,schema.MODEL_SOURCE_PATH))
 counter_table=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'))
 if counter_table.get('epoch')!=36 or counter_table.get('kind')!=KIND:raise ValueError('Counter epoch/kind differs')
 ops=validate_operation_budgets(counter_table,schema)
 inference_python=EXTERNAL_ENV/'bin/python'
 if(not inference_python.is_file()or not inference_python.resolve().is_file()or any(p.is_symlink()for p in inference_python.parents)or inference_python.resolve()!=Path(sys.executable).resolve()or Path(sys.prefix).absolute()!=EXTERNAL_ENV):raise ValueError('Use exact hash-verified read-only E33 venv Python with lexical executable path')
 for directory in (MODEL_DIRECTORY,BASELINE_MODEL_DIRECTORY):
  if directory.is_symlink()or any(p.is_symlink()for p in directory.parents):raise ValueError('Symlink assets forbidden')
 lock=common.parse(root/assets);dependencies=[]
 for key in('wheel_lock','native_closure','BGE_source'):
  row=exact_ref(root,lock[key+'_path'])
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Runtime dependency changed: '+key)
  dependencies.append(row)
 member_ref=lock['python_member_manifest'];row=exact_ref(root,member_ref['path'])
 if row!=member_ref:raise ValueError('Python member manifest changed')
 members=common.parse(root/member_ref['path'])
 if not isinstance(members,list)or len({r['path']for r in members})!=len(members):raise ValueError('Runtime members must be unique-path list')
 common.validate_runtime_member_aliases(lock,row,len(members));dependencies.append(row)
 reuse_ref=exact_ref(root,common.RUNTIME_REUSE_VERIFICATION_PATH)
 common.validate_runtime_reuse_receipt(lock,reuse_ref,common.parse(root/reuse_ref['path']));dependencies.append(reuse_ref)
 source_dependencies=inherited_source_dependencies(root);dependencies+=source_dependencies
 context_dependencies=inherited_context_dependencies(root)
 baseline_metadata=exact_ref(root,schema.BASELINE_METADATA_ADMISSION['path'])
 if baseline_metadata!=schema.BASELINE_METADATA_ADMISSION:raise ValueError('Exact inherited baseline source admission changed')
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
 if not any(r['path'].endswith('reviewed_build_plan.py')for r in entries):raise ValueError('Reviewed builder must be public source')
 if any('/runs/'in r['path']or r['path'].endswith('/SOURCE_ADMISSION.json')or r['path']in set(schema.DISPATCH_PATHS.values())|set(schema.PHASE_RESERVATIONS.values())for r in entries):raise ValueError('Execution/admission exists before freeze')
 freeze={'schema_version':1,'epoch':36,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'engineering_ids':schema.ENGINEERING_IDS,'entries':entries,'inherited_context_dependencies':context_dependencies,'inherited_source_dependencies':source_dependencies,'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],'rule':'All reviewed current source, new authored CC0 engineering inputs/oracles, independent scorer, reused runtime verification, pretrained source/license/asset identities frozen before one engineering-only worker. Paired original readers, exact full-source admission and unchanged E34 two-group controls/original hypotheses with rawT1, no proof/fit/calibration/TRAIN/DEV/CONF/retry/full104/benchmark or new submission. Engineering labels join once only after all54 readouts; no benchmark generalization claim.'}
 summary={'source_files':len(entries),'TRAIN_cases':0,'engineering_cases':9,'engineering_role':schema.ENGINEERING_ROLE,'engineering_model_forwards':54,'DEV_cases':0,'calibration_cases':0,'confirmation_cases':0,'total_max_model_forwards':54,'engineering_native_queries':9,'total_max_native_queries':9,'native_corpus_batches':1,'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'models_native_label_joins_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,schema.FREEZE_PATH);pins={r['path']:r for r in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':36,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'guardian_scope':str(GUARDIAN_SCOPE),'publication_parent':args.source_parent,'publication_parent_trees':dict(zip(('root','bench','scope'),(args.source_root,args.source_bench,args.source_scope))),'publication_stage_paths':{'source':str(args.source_stage.absolute()),'final':str(args.final_stage.absolute())},'created_at':datetime.now(timezone.utc).isoformat(),'hypothesis':'Test a new original xxlarge three-way reader and full-source coverage on nine new short fictional CC0 engineering sources3/class. Compare xxlarge and b354 on identical exact full-source premises, and preserve matched xxlarge native/lexical/positional E34 two-group controls plus b354 native-two. A single actual native query per case supplies shared source-unit rankings; complete unique native unitset coverage admits full-source reading when the exact original pair fits512 separately under both tokenizers. No source rewrite, clipping, fallback or retrieval-miss absence inference. Run b354 then prove its reader/tokenizer weakrefs dead before xxlarge; retain RSS without claiming allocator release. All54 scalar forecasts precede one9-label join. No empirical selection, fitting, proof/solver override, calibration, benchmark roles, promotion or general-strength/eligibility claim.','data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'engineering_ids':schema.ENGINEERING_IDS,'training_ids':[],'development_ids':[],'calibration_ids':[],'confirmation_ids':[],'engineering_only':True,'benchmark_accuracy':None,'promotion_allowed':False,'used_confirmation_identities':[],'training_lineage_complete':schema.TRAINING_LINEAGE_COMPLETE,'diagnostic_only':schema.DIAGNOSTIC_ONLY,'probability_temperature':1.0,'raw_probability_temperature':1.0,'final_probability_policy':'UNCHANGED_RAW_T1_PROOF_DISABLED_ALL_ROLES','probability_policy':schema.PROBABILITY_POLICY,'metrics_policy':schema.METRICS_POLICY,'retrieval_policy':schema.RETRIEVAL_POLICY,'protocol':exact_ref(root,P+'audit/epoch36/protocol.json'),'protocol_path':P+'audit/epoch36/protocol.json','protocol_sha256':exact_ref(root,P+'audit/epoch36/protocol.json')['sha256'],'scorer':exact_ref(root,args.scorer),'source_freeze':freeze_ref,'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],'pretrained_model_source':exact_ref(root,schema.MODEL_SOURCE_PATH),'baseline_model_source':exact_ref(root,schema.BASELINE_MODEL_SOURCE_PATH),'model_profiles':exact_ref(root,schema.MODEL_PROFILES_PATH),'engineering_role':schema.ENGINEERING_ROLE,'engineering_gate':schema.ENGINEERING_GATE,'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'native_queries_per_case':1,'maximum_native_queries':9,'proof_enabled_roles':schema.PROOF_ENABLED_ROLES,'raw_same_model_ablation':'Every retained rawT1 output is scored, zero extra model calls, no posthoc selection','source_parameter_dtype':schema.SOURCE_PARAMETER_DTYPE,'source_serialization_format':schema.SOURCE_SERIALIZATION_FORMAT,'compute_dtype':schema.COMPUTE_DTYPE,'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(inference_python),'external_python_environment':str(EXTERNAL_ENV),'runtime_reuse_policy':common.RUNTIME_REUSE_POLICY,'model_directory':str(MODEL_DIRECTORY),'baseline_model_directory':str(BASELINE_MODEL_DIRECTORY),'reader_execution_order':schema.MODEL_EXECUTION_ORDER,'model_forward_counts':schema.MODEL_FORWARD_COUNTS,'expected_operation_counters':ops,'counter_table':exact_ref(root,candidate+'EXPECTED_COUNTERS.json'),'phase_limits':{'engineering':{'engineering_NLI_forward_calls':54,'xxlarge_NLI_forward_calls':36,'b354_NLI_forward_calls':18,'conditional_DEV_NLI_forward_calls':0,'total_max_NLI_forward_calls':54,'engineering_native_queries':9,'conditional_DEV_native_queries':0,'total_max_native_queries':9,'optimizer_steps':0}},'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},'pins':[pins[k]for k in sorted(pins)],**schema.FLAGS,'confirmation':[],'CPU_scope':'Kernel affinity0,1 plus narrow affinity-denial guard before model/native import; observed threads retained.','network_scope':'Frozen API interposition with inherited source-bound urllib3 IPv6 loopback capability probe only; no communication/listening/DNS allowance. Opaque compiled internal calls UNKNOWN.','host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_workspace_free_bytes':16777216,'policy':'Verify owner/source/external assets/actual host before single reservation; reservation burns sole engineering batch, no retry.'}}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 plan['engineering_rejected_operation_counters']=ops
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true')
 for name in('source-parent','source-root','source-bench','source-scope'):cli.add_argument('--'+name,required=True)
 for name in('source-stage','final-stage'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))
