"""E35 source-only master freeze. No inference, label join, fitting or network.
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
SOURCE='4d51073072c428b58685e5498337bfdece6aac9b'
KIND='ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS'
DEFAULT_SCOPE=Path('/workspace/ruvector-epoch35-4d51073072c4')
GUARDIAN_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch35-4d51073072c4')
EXTERNAL_ENV=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL_DIRECTORY=Path('/workspace/ruvector-e35-reader-assets/moritz-b3546ea6')

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def inherited_context_dependencies(root):
 expected={P+'candidate/epoch6/context.py':'28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2',P+'candidate/epoch15/context.py':'9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'}
 rows=[exact_ref(root,name)for name in expected]
 if any(row['sha256']!=expected[row['path']]for row in rows):raise ValueError('Transitive source-context dependency changed')
 return rows

def write_new(path,value):
 with path.open('x',encoding='utf-8')as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def validate_operation_budgets(counter_table,schema):
 ops=counter_table.get('expected_operation_counters')
 if not isinstance(ops,dict)or set(ops)!={'engineering'}or not isinstance(ops['engineering'],dict)or not ops['engineering']or any(not isinstance(k,str)or type(v)is not int or v<0 for k,v in ops['engineering'].items()):raise ValueError('Exact engineering-only counter table required')
 full_budget={'NLI_forward_calls_attempted':48,'NLI_forward_calls_completed':48,'NLI_readouts_completed':48,'ENGINEERING_forward_calls_attempted':48,'ENGINEERING_forward_calls_completed':48,'DEV_forward_calls_attempted':0,'DEV_forward_calls_completed':0,'native_queries_attempted':12,'native_queries_completed':12,'corpus_batches_attempted':1,'corpus_batches_completed':1,'native_index_initializations_attempted':12,'native_index_initializations_completed':12,'native_helper_starts_attempted':1,'native_helper_starts_completed':1,'native_binary_loads_attempted':1,'native_binary_loads_completed':1,'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_len_calls_attempted':24,'native_len_calls_completed':24,'model_initializations_attempted':1,'model_initializations_completed':1,'BGE_initializations_attempted':1,'BGE_initializations_completed':1,'engineering_oracle_reads':1,'engineering_oracle_expected_labels_accessed':12}
 if any(type(ops['engineering'].get(k))is not int or ops['engineering'][k]!=v for k,v in full_budget.items()):raise ValueError('Frozen four-arm forward/query/index/helper budget differs')
 for alias in ('full','engineering_rejected'):
  if counter_table.get(alias)!=ops:raise ValueError('Engineering-only counter alias differs: '+alias)
 if counter_table.get('engineering_rejected_operation_counters')!=ops:raise ValueError('No conditional second corpus path in E35')
 if schema.TOTAL_MAX_NLI_FORWARD_CALLS!=48 or schema.TOTAL_MAX_NATIVE_QUERIES!=12:raise ValueError('Schema budget differs')
 return ops

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch35');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh E35 workspace required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if(study/'plan.json').exists()or(study/'source-freeze.json').exists():raise ValueError('Master plan/freeze already exist; no overwrite')
 candidate=P+'candidate/epoch35/';assets=P+'epoch35/preparation/runtime-assets.lock.json'
 paths={'engineering_inputs':candidate+'engineering.inputs.json','engineering_oracle':candidate+'engineering.oracle.json','audit_protocol':candidate+'ENGINEERING_PROTOCOL.json','numeric_oracle':candidate+'NUMERIC_ORACLE.json','runtime_assets_lock':assets,'model_assets_lock':candidate+'MODEL_ASSETS.json','pretrained_model_source':schema.MODEL_SOURCE_PATH,'proof_source':candidate+'proof.py','proof_policy':candidate+'PROOF_POLICY.json','query_source':candidate+'query.py','query_policy':candidate+'QUERY_POLICY.json','source_context':candidate+'source_context.py','runtime_reuse_verification':common.RUNTIME_REUSE_VERIFICATION_PATH,'BGE_source':P+'candidate/epoch3/models.py','inherited_context_source':P+'candidate/epoch22/context.py','runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 required=list(paths.values())+[candidate+n for n in('worker.py','native_helper.cjs','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[P+'audit/epoch35/protocol.json',args.scorer]
 for name in required:exact_ref(root,name)
 for name in('source_parent','source_root','source_bench','source_scope'):
  if not re.fullmatch('[0-9a-f]{40}',getattr(args,name)):raise ValueError('Exact actual source-parent/tree SHA required')
 if not args.scorer.startswith(P+'audit/epoch35/')or not args.scorer.endswith('.py'):raise ValueError('Current independent scorer source required')
 publication.pretrained_source_ready(root,None,exact_ref(root,schema.MODEL_SOURCE_PATH))
 counter_table=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'))
 if counter_table.get('epoch')!=35 or counter_table.get('kind')!=KIND:raise ValueError('Counter epoch/kind differs')
 ops=validate_operation_budgets(counter_table,schema)
 inference_python=EXTERNAL_ENV/'bin/python'
 if(not inference_python.is_file()or not inference_python.resolve().is_file()or any(p.is_symlink()for p in inference_python.parents)or inference_python.resolve()!=Path(sys.executable).resolve()or Path(sys.prefix).absolute()!=EXTERNAL_ENV):raise ValueError('Use exact hash-verified read-only E33 venv Python with lexical executable path')
 if MODEL_DIRECTORY.is_symlink()or any(p.is_symlink()for p in MODEL_DIRECTORY.parents):raise ValueError('Symlink assets forbidden')
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
 dependencies +=[exact_ref(root,paths[key])for key in('runtime_policy_addendum','BGE_source','inherited_context_source')]
 context_dependencies=inherited_context_dependencies(root);dependencies+=context_dependencies
 expected={'BGE_source':'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716','inherited_context_source':'9ca2968ed800443bc75fac452daf2cbf17bf27cf1b3b75cbfb220bfa23a9e727'}
 if any(exact_ref(root,paths[k])['sha256']!=v for k,v in expected.items()):raise ValueError('Original inherited BGE/context changed')
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
 freeze={'schema_version':1,'epoch':35,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'engineering_ids':schema.ENGINEERING_IDS,'entries':entries,'inherited_context_dependencies':context_dependencies,'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],'rule':'All reviewed current source, new authored CC0 engineering inputs/oracles, independent scorer, reused runtime verification, pretrained source/license/asset identities frozen before one engineering-only worker. Unchanged E34 selector/packer and original hypothesis with rawT1, no proof/fit/calibration/TRAIN/DEV/CONF/retry/full104/benchmark or new submission. Engineering labels join once only after all48 readouts; no benchmark generalization claim.'}
 summary={'source_files':len(entries),'TRAIN_cases':0,'engineering_cases':12,'engineering_role':schema.ENGINEERING_ROLE,'engineering_model_forwards':48,'DEV_cases':0,'calibration_cases':0,'confirmation_cases':0,'total_max_model_forwards':48,'engineering_native_queries':12,'total_max_native_queries':12,'native_corpus_batches':1,'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'models_native_label_joins_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,schema.FREEZE_PATH);pins={r['path']:r for r in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':35,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'guardian_scope':str(GUARDIAN_SCOPE),'publication_parent':args.source_parent,'publication_parent_trees':dict(zip(('root','bench','scope'),(args.source_root,args.source_bench,args.source_scope))),'publication_stage_paths':{'source':str(args.source_stage.absolute()),'final':str(args.final_stage.absolute())},'created_at':datetime.now(timezone.utc).isoformat(),'hypothesis':'A single source-frozen numerical/deontic/source-scope engineering stress for the unchanged E34 b354 lexical-anchor/native-complement system. Twelve new fictional CC0 snippets4/class use independently reviewed exact rational/Decimal or two-compatible-world oracles. Native-only, lexical-only and positional same-reader controls share the E34 complete-group packer, original hypothesis query and rawT1 readout. One real native query per case is reused by primary/control. No empirical selection, solver override or nearby retrieval grid; all failures retained. Retrieval omission cannot prove absence. This is engineering readiness only, with all benchmark roles empty and no benchmark score/generalization/promotion claim.','data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'engineering_ids':schema.ENGINEERING_IDS,'training_ids':[],'development_ids':[],'calibration_ids':[],'confirmation_ids':[],'engineering_only':True,'benchmark_accuracy':None,'promotion_allowed':False,'used_confirmation_identities':[],'training_lineage_complete':schema.TRAINING_LINEAGE_COMPLETE,'diagnostic_only':schema.DIAGNOSTIC_ONLY,'probability_temperature':1.0,'raw_probability_temperature':1.0,'final_probability_policy':'UNCHANGED_RAW_T1_PROOF_DISABLED_ALL_ROLES','probability_policy':schema.PROBABILITY_POLICY,'metrics_policy':schema.METRICS_POLICY,'retrieval_policy':schema.RETRIEVAL_POLICY,'protocol':exact_ref(root,P+'audit/epoch35/protocol.json'),'protocol_path':P+'audit/epoch35/protocol.json','protocol_sha256':exact_ref(root,P+'audit/epoch35/protocol.json')['sha256'],'scorer':exact_ref(root,args.scorer),'source_freeze':freeze_ref,'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],'pretrained_model_source':exact_ref(root,schema.MODEL_SOURCE_PATH),'engineering_role':schema.ENGINEERING_ROLE,'engineering_gate':{'primary_required_correct':12,'each_class_required_correct':4,'proper_scores':['Brier','NLL'],'proper_score_rule':'NONINCREASE_VS_EACH_CONTROL','controls':['native_original','lexical','positional'],'benchmark_admission':False},'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'native_queries_per_case':1,'maximum_native_queries':12,'proof_enabled_roles':schema.PROOF_ENABLED_ROLES,'raw_same_model_ablation':'Every retained rawT1 output is scored, zero extra model calls, no posthoc selection','source_parameter_dtype':schema.SOURCE_PARAMETER_DTYPE,'compute_dtype':schema.COMPUTE_DTYPE,'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(inference_python),'external_python_environment':str(EXTERNAL_ENV),'runtime_reuse_policy':common.RUNTIME_REUSE_POLICY,'model_directory':str(MODEL_DIRECTORY),'expected_operation_counters':ops,'counter_table':exact_ref(root,candidate+'EXPECTED_COUNTERS.json'),'phase_limits':{'engineering':{'engineering_NLI_forward_calls':48,'conditional_DEV_NLI_forward_calls':0,'total_max_NLI_forward_calls':48,'engineering_native_queries':12,'conditional_DEV_native_queries':0,'total_max_native_queries':12,'optimizer_steps':0}},'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':0,'ENGINEERING_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},'pins':[pins[k]for k in sorted(pins)],**schema.FLAGS,'confirmation':[],'CPU_scope':'Kernel affinity0,1 plus narrow affinity-denial guard before model/native import; observed threads retained.','network_scope':'Frozen API interposition with inherited source-bound urllib3 IPv6 loopback capability probe only; no communication/listening/DNS allowance. Opaque compiled internal calls UNKNOWN.','host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_workspace_free_bytes':16777216,'policy':'Verify owner/source/external assets/actual host before single reservation; reservation burns sole engineering batch, no retry.'}}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 if 'engineering_rejected_operation_counters'in counter_table:plan['engineering_rejected_operation_counters']=counter_table['engineering_rejected_operation_counters']
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true')
 for name in('source-parent','source-root','source-bench','source-scope'):cli.add_argument('--'+name,required=True)
 for name in('source-stage','final-stage'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))
