"""Root-run E33 master source freeze; no models, labels or external calls.
Copy this reviewed source into public preparation before checking or writing.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
P='experiments/sota-2026-10-22/'
SOURCE='0522a2c521c92c55d843d21c71495a44b43977e5'
KIND='REAL_NATIVE_TYPED_MODAL_RETRIEVAL_NLI_DIAGNOSTIC'
DEFAULT_SCOPE=Path('/workspace/ruvector-epoch33-0522a2c521c9')
GUARDIAN_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9')
EXTERNAL_ENV=Path('/tmp/ruvector-sota-2026-10-22/epoch33-0522a2c521c9/runtime/.venv')
MODEL_DIRECTORY=Path('/workspace/ruvector-e33-reader-assets/moritz-b3546ea6')

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def write_new(path,value):
 with path.open('x',encoding='utf-8') as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def validate_operation_budgets(counter_table,schema):
 ops=counter_table['expected_operation_counters']
 refusal=counter_table.get('engineering_rejected_operation_counters')
 if not isinstance(refusal,dict) or set(refusal)!={'dev'} or not isinstance(refusal['dev'],dict) or any(not isinstance(k,str) or type(v)is not int or v<0 for k,v in refusal['dev'].items()):raise ValueError('Exact frozen engineering-refusal counter table required')
 full_budget={'NLI_forward_calls_attempted':schema.TOTAL_MAX_NLI_FORWARD_CALLS,'NLI_forward_calls_completed':schema.TOTAL_MAX_NLI_FORWARD_CALLS,'NLI_readouts_completed':schema.TOTAL_MAX_NLI_FORWARD_CALLS,'ENGINEERING_forward_calls_attempted':schema.ENGINEERING_NLI_FORWARD_CALLS,'ENGINEERING_forward_calls_completed':schema.ENGINEERING_NLI_FORWARD_CALLS,'DEV_forward_calls_attempted':schema.DEV_NLI_FORWARD_CALLS,'DEV_forward_calls_completed':schema.DEV_NLI_FORWARD_CALLS,'native_queries_attempted':schema.TOTAL_MAX_NATIVE_QUERIES,'native_queries_completed':schema.TOTAL_MAX_NATIVE_QUERIES,'corpus_batches_attempted':2,'corpus_batches_completed':2,'native_index_initializations_attempted':14,'native_index_initializations_completed':14,'native_helper_starts_attempted':2,'native_helper_starts_completed':2}
 refusal_budget=dict(full_budget,NLI_forward_calls_attempted=schema.ENGINEERING_NLI_FORWARD_CALLS,NLI_forward_calls_completed=schema.ENGINEERING_NLI_FORWARD_CALLS,NLI_readouts_completed=schema.ENGINEERING_NLI_FORWARD_CALLS,DEV_forward_calls_attempted=0,DEV_forward_calls_completed=0,native_queries_attempted=schema.ENGINEERING_NATIVE_QUERIES,native_queries_completed=schema.ENGINEERING_NATIVE_QUERIES,corpus_batches_attempted=1,corpus_batches_completed=1,native_index_initializations_attempted=6,native_index_initializations_completed=6,native_helper_starts_attempted=1,native_helper_starts_completed=1)
 if any(type(ops['dev'].get(k))is not int or ops['dev'][k]!=v for k,v in full_budget.items()) or any(type(refusal['dev'].get(k))is not int or refusal['dev'][k]!=v for k,v in refusal_budget.items()):raise ValueError('Frozen four-arm forward/query/index/helper counter contract differs')
 return ops,refusal

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch33');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh reconstructed E33 workspace required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if (study/'plan.json').exists() or (study/'source-freeze.json').exists():raise ValueError('Master source plan/freeze already exist; no overwrite')
 candidate=P+'candidate/epoch33/';assets=P+'epoch33/preparation/runtime-assets.lock.json'
 paths={'dev_inputs':P+'audit/epoch33/data/dev.inputs.json',
  'engineering_inputs':candidate+'engineering.inputs.json','engineering_oracle':candidate+'engineering.oracle.json',
  'runtime_assets_lock':assets,'model_assets_lock':candidate+'MODEL_ASSETS.json',
  'pretrained_model_source':schema.MODEL_SOURCE_PATH,'proof_source':candidate+'proof.py','proof_policy':candidate+'PROOF_POLICY.json','query_source':candidate+'query.py','query_policy':candidate+'QUERY_POLICY.json',
  'BGE_source':P+'candidate/epoch3/models.py','inherited_context_source':P+'candidate/epoch22/context.py',
  'runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 required=list(paths.values())+[candidate+n for n in ('worker.py','native_helper.cjs','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[P+'audit/epoch33/protocol.json',args.scorer]
 for name in required:exact_ref(root,name)
 for name in ('source_parent','source_root','source_bench','source_scope'):
  if not re.fullmatch('[0-9a-f]{40}',getattr(args,name)):raise ValueError('Exact actual source-parent/tree SHA required')
 if not args.scorer.startswith(P+'audit/epoch33/') or not args.scorer.endswith('.py'):raise ValueError('Current E33 independent scorer source required')
 publication.pretrained_source_ready(root,None,exact_ref(root,schema.MODEL_SOURCE_PATH))
 counter_table=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'));ops=counter_table['expected_operation_counters']
 if counter_table.get('epoch')!=33 or counter_table.get('kind')!=KIND or set(ops)!={'dev'} or any(not isinstance(v,dict) or not v or any(not isinstance(k,str) or type(n)is not int or n<0 for k,n in v.items())for v in ops.values()):raise ValueError('Exact source operation budgets required')
 validate_operation_budgets(counter_table,schema)
 # The complete and engineering-refusal counter tables are frozen, not inferred
 # by a publishing helper. The scorer enforces each conditional path.
 inference_python=EXTERNAL_ENV/'bin/python'
 if (not inference_python.is_file() or not inference_python.resolve().is_file() or any(p.is_symlink()for p in inference_python.parents)
  or inference_python.resolve()!=Path(sys.executable).resolve() or Path(sys.prefix).absolute()!=EXTERNAL_ENV):raise ValueError('Use verified fresh E33 venv Python, preserving lexical executable path')
 if MODEL_DIRECTORY.is_symlink() or any(p.is_symlink()for p in MODEL_DIRECTORY.parents):raise ValueError('Symlink model assets forbidden')
 lock=common.parse(root/assets);dependencies=[]
 for key in ('wheel_lock','native_closure','BGE_source'):
  row=exact_ref(root,lock[key+'_path'])
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Runtime dependency identity changed: '+key)
  dependencies.append(row)
 member_ref=lock['python_member_manifest'];row=exact_ref(root,member_ref['path'])
 if row!=member_ref:raise ValueError('Runtime dependency identity changed: python_member_manifest')
 members=common.parse(root/member_ref['path'])
 if not isinstance(members,list) or len({item['path']for item in members})!=len(members):raise ValueError('Runtime member manifest must be a unique-path list')
 common.validate_runtime_member_aliases(lock,row,len(members))
 dependencies.append(row)
 dependencies += [exact_ref(root,paths[key])for key in ('runtime_policy_addendum','BGE_source','inherited_context_source')]
 expected_inherited={'BGE_source':'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716','inherited_context_source':'9ca2968ed800443bc75fac452daf2cbf17bf27cf1b3b75cbfb220bfa23a9e727'}
 if any(exact_ref(root,paths[key])['sha256']!=digest for key,digest in expected_inherited.items()):raise ValueError('Original inherited BGE/context dependency changed')
 entries=[]
 for relative in publication.ROOTS:
  directory=root/relative
  if not directory.exists():continue
  for path in sorted(directory.rglob('*')):
   if path.is_symlink():raise ValueError('Symlink in new source tree')
   if path.is_file():
    name=path.relative_to(root).as_posix();common.public_text(name,path.read_bytes());entries.append(exact_ref(root,name))
 entries.sort(key=lambda row:row['path'])
 if len({r['path']for r in entries})!=len(entries):raise ValueError('Duplicate source member')
 if not any(r['path'].endswith('reviewed_build_plan.py')for r in entries):raise ValueError('Reviewed builder must be copied into current public source')
 if any('/runs/'in r['path'] or r['path'].endswith('/SOURCE_ADMISSION.json')or r['path']in set(schema.DISPATCH_PATHS.values())|set(schema.PHASE_RESERVATIONS.values())for r in entries):raise ValueError('Execution/admission exists before source freeze')
 freeze={'schema_version':1,'epoch':33,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'entries':entries,
  'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],'rule':'All current source, exposed authored CC0 engineering regression oracle, DEV inputs, scorer, runtime policy, exact pretrained source/license/asset identities frozen before one engineering-gated typed-modal retrieval DEV worker; proof disabled on DEV. No fits, calibration, TRAIN, CONF, retry, full104, benchmark acceptance or new submission.'}
 summary={'source_files':len(entries),'TRAIN_cases':0,'engineering_cases':schema.ENGINEERING_CASES,'engineering_role':schema.ENGINEERING_ROLE,'engineering_model_forwards':schema.ENGINEERING_NLI_FORWARD_CALLS,'DEV_cases':schema.DEV_CASES,'conditional_DEV_model_forwards':schema.DEV_NLI_FORWARD_CALLS,'total_max_model_forwards':schema.TOTAL_MAX_NLI_FORWARD_CALLS,'engineering_native_queries':schema.ENGINEERING_NATIVE_QUERIES,'conditional_DEV_native_queries':schema.DEV_NATIVE_QUERIES,'total_max_native_queries':schema.TOTAL_MAX_NATIVE_QUERIES,'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'models_native_labels_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,schema.FREEZE_PATH);pins={r['path']:r for r in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':33,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'guardian_scope':str(GUARDIAN_SCOPE),
  'publication_parent':args.source_parent,'publication_parent_trees':dict(zip(('root','bench','scope'),(args.source_root,args.source_bench,args.source_scope))),
  'publication_stage_paths':{'source':str(args.source_stage.absolute()),'final':str(args.final_stage.absolute())},'created_at':datetime.now(timezone.utc).isoformat(),
  'hypothesis':'Test one fixed generic typed-modal hypothesis-query expansion with actual native RuVector evidence selection. Compare expanded native retrieval with original-query native causal control, lexical retrieval using the same expanded query, and positional retrieval, all with the same fixed generic Moritz DeBERTa NLI model. A frozen strict whole-input proof supplement is used only for the six exposed CC0 engineering regression cases and is explicitly disabled on DEV; every DEV final output equals raw T1 with proof_disabled_for_DEV reason. Twenty-four exposed engineering raw NLI forwards gate96 new DEV raw forwards; both native queries share each fixed document index. Retain raw-derived ablations with zero extra NLI calls. This is a public diagnostic, not a newly demonstrated stronger model, proof efficacy claim or fresh confirmation.',
  'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'training_ids':[],
  'development_ids':['original-contractnli:train:epoch33:dev:'+str(d)+':'+h for d in schema.ROLES['dev']for h in schema.HYPOTHESES],
  'calibration_ids':[],'confirmation_ids':[],'training_lineage_complete':schema.TRAINING_LINEAGE_COMPLETE,'diagnostic_only':schema.DIAGNOSTIC_ONLY,'probability_temperature':1.0,'raw_probability_temperature':1.0,'final_probability_policy':'ONE_HOT_ONLY_FOR_INDEPENDENTLY_VERIFIABLE_FROZEN_WHOLE_INPUT_CERTIFICATE_ELSE_RAW_T1','probability_policy':schema.PROBABILITY_POLICY,'metrics_policy':schema.METRICS_POLICY,
  'protocol':exact_ref(root,P+'audit/epoch33/protocol.json'),'protocol_path':P+'audit/epoch33/protocol.json','protocol_sha256':exact_ref(root,P+'audit/epoch33/protocol.json')['sha256'],
  'scorer':exact_ref(root,args.scorer),'source_freeze':freeze_ref,'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],
  'pretrained_model_source':exact_ref(root,schema.MODEL_SOURCE_PATH),'engineering_role':schema.ENGINEERING_ROLE,'arms':schema.ARM_NAMES,'raw_arm_names':schema.RAW_ARM_NAMES,'metric_arm_names':schema.METRIC_ARM_NAMES,'raw_to_metric_arm':schema.RAW_TO_METRIC_ARM,'native_queries_per_case':schema.NATIVE_QUERIES_PER_CASE,'maximum_native_queries':schema.TOTAL_MAX_NATIVE_QUERIES,'proof_enabled_roles':schema.PROOF_ENABLED_ROLES,'raw_same_model_ablation':'Derived from every retained raw T1 output, zero additional model calls, no posthoc selection','source_parameter_dtype':schema.SOURCE_PARAMETER_DTYPE,'compute_dtype':schema.COMPUTE_DTYPE,
  'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(inference_python),'external_python_environment':str(EXTERNAL_ENV),'model_directory':str(MODEL_DIRECTORY),
  'expected_operation_counters':ops,'counter_table':exact_ref(root,candidate+'EXPECTED_COUNTERS.json'),
  'phase_limits':{'dev':{'engineering_NLI_forward_calls':schema.ENGINEERING_NLI_FORWARD_CALLS,'conditional_DEV_NLI_forward_calls':schema.DEV_NLI_FORWARD_CALLS,'total_max_NLI_forward_calls':schema.TOTAL_MAX_NLI_FORWARD_CALLS,'engineering_native_queries':schema.ENGINEERING_NATIVE_QUERIES,'conditional_DEV_native_queries':schema.DEV_NATIVE_QUERIES,'total_max_native_queries':schema.TOTAL_MAX_NATIVE_QUERIES,'optimizer_steps':0}},
  'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},
  'pins':[pins[k]for k in sorted(pins)],**schema.FLAGS,'confirmation':[],
  'CPU_scope':'Kernel affinity0,1 plus inherited narrow affinity-denial guard before model/native import; two CPU threads requested, observed threads retained.',
  'network_scope':'Frozen API interposition, only inherited exact source-bound urllib3 IPv6 loopback capability probe; no communication/listening/DNS allowance. Opaque compiled internal calls UNKNOWN.',
  'host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_workspace_free_bytes':16777216,'policy':'Verify guardian, source, external runtime/model assets and actual host before the single reservation; reservation burns sole combined batch, no retry.'}}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 if 'engineering_rejected_operation_counters'in counter_table:plan['engineering_rejected_operation_counters']=counter_table['engineering_rejected_operation_counters']
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true')
 for name in ('source-parent','source-root','source-bench','source-scope'):cli.add_argument('--'+name,required=True)
 for name in ('source-stage','final-stage'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))
