"""Root-run E31 master source freeze; no models, labels or external calls.
Copy this reviewed source into public preparation before --check-only or write.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
P='experiments/sota-2026-10-22/'
SOURCE='b27d0c39ed3102cd16ba616b1225b7684b76851b'
KIND='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa')

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def write_new(path,value):
 with path.open('x',encoding='utf-8') as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch31');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh reconstructed E31 scope required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if (study/'plan.json').exists() or (study/'source-freeze.json').exists():raise ValueError('Master source plan/freeze already exist; no overwrite')
 candidate=P+'candidate/epoch31/';assets=P+'epoch31/preparation/runtime-assets.lock.json'
 paths={'dev_inputs':P+'audit/epoch31/data/dev.inputs.json',
  'runtime_assets_lock':assets,'bart_assets_lock':P+'candidate/epoch27/MODEL_ASSETS.json',
  'original_reader':P+'candidate/epoch27/reader/bart_reader.py',
  'runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json',
  'archived_model_code':P+'candidate/epoch30/model.py',
  'archived_algorithm_code':P+'candidate/epoch30/algorithm.py',
  'archived_parameter_codec':P+'candidate/epoch30/parameter_codec.py'}
 required=list(paths.values())+[candidate+n for n in ('worker.py','native_helper.cjs','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[P+'audit/epoch31/protocol.json',schema.ARCHIVED_SEAL_PATH,args.scorer]
 for name in required:exact_ref(root,name)
 for name in ('source_parent','source_root','source_bench','source_scope'):
  if not re.fullmatch('[0-9a-f]{40}',getattr(args,name)):raise ValueError('Exact actual source-parent/tree SHA required')
 if not args.scorer.startswith(P+'audit/epoch31/') or not args.scorer.endswith('.py'):raise ValueError('Current E31 independent scorer source required')
 archived_seal=common.parse(root/schema.ARCHIVED_SEAL_PATH);publication.archive_ready(root,common.cp_rows(common.parse(scope/'kit/CHECKPOINT_MANIFEST.json')),archived_seal)
 historical=common.parse(root/archived_seal['original_source_plan']['path'])
 counts=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'))
 ops=counts['expected_operation_counters']
 if counts.get('epoch')!=31 or counts.get('kind')!=KIND or set(ops)!={'dev'} or any(not isinstance(v,dict) or not v or any(not isinstance(k,str) or type(n)is not int or n<0 for k,n in v.items()) for v in ops.values()):raise ValueError('Exact source operation budgets required')
 if ops['dev'].get('NLI_forward_calls_completed')!=96:raise ValueError('Exactly96 fixed DEV forwards required')
 inference_python=root/'retrieval/.venv/bin/python'
 if (not inference_python.is_file() or not inference_python.resolve().is_file() or any(p.is_symlink() for p in inference_python.parents)
     or inference_python.resolve()!=Path(sys.executable).resolve() or Path(sys.prefix).absolute()!=root/'retrieval/.venv'):raise ValueError('Use approved project venv Python, preserving lexical executable path')
 lock=common.parse(root/assets);dependencies=[]
 for key in ('wheel_lock','native_closure','BGE_source','wheel_members_reference'):
  row=exact_ref(root,lock[key+'_path'])
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Runtime dependency identity changed: '+key)
  dependencies.append(row)
 dependencies += [exact_ref(root,paths[key])for key in ('bart_assets_lock','original_reader','runtime_policy_addendum','archived_model_code','archived_algorithm_code','archived_parameter_codec')]
 dependencies += [archived_seal[key]for key in schema.ARCHIVED_SOURCE_PATHS]
 entries=[]
 for relative in publication.ROOTS:
  directory=root/relative
  if not directory.exists():continue
  for path in sorted(directory.rglob('*')):
   if path.is_symlink():raise ValueError('Symlink in new source tree')
   if path.is_file():
    name=path.relative_to(root).as_posix();common.public_text(name,path.read_bytes());entries.append(exact_ref(root,name))
 entries.sort(key=lambda row:row['path'])
 if len({r['path'] for r in entries})!=len(entries):raise ValueError('Duplicate source member')
 if not any(r['path'].endswith('reviewed_build_plan.py') for r in entries):raise ValueError('Reviewed builder must be copied into current public source')
 if any('/runs/' in r['path'] or r['path'].endswith('/SOURCE_ADMISSION.json') or r['path']in set(schema.DISPATCH_PATHS.values())|set(schema.PHASE_RESERVATIONS.values()) for r in entries):raise ValueError('Execution/model admission exists before source freeze')
 freeze={'schema_version':1,'epoch':31,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'entries':entries,
  'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],'rule':'All current source/DEV inputs/scorer/runtime policy and archived BASE-published learned artifact/provenance fixed before one current DEV worker. No current TRAIN, fit, MODEL phase, CONF, retry, full104 or benchmark acceptance.'}
 summary={'source_files':len(entries),'current_TRAIN_cases':0,'DEV_cases':24,'current_TRAIN_model_forwards':0,'DEV_model_forwards':96,'models_native_labels_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,schema.FREEZE_PATH)
 pins={r['path']:r for r in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':31,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'publication_parent':args.source_parent,'publication_parent_trees':{'root':args.source_root,'bench':args.source_bench,'scope':args.source_scope},'publication_stage_paths':{'source':str(args.source_stage.absolute()),'final':str(args.final_stage.absolute())},'created_at':datetime.now(timezone.utc).isoformat(),
  'hypothesis':'First fixed measurement of the exact BASE-published E30 rank4-plus-head legal adaptation versus original2020 BART with actual native RuVector evidence on24 new frozen DEV decisions. Compare the same archived adapted model under native/lexical/positional retrieval. No current fit, MODEL publication phase, fresh confirmation or official placement.',
  'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'archived_training_algorithm':historical['training_algorithm'],
  'training_ids':[],'development_ids':['original-contractnli:train:epoch31:dev:'+str(d)+':'+h for d in schema.ROLES['dev'] for h in schema.HYPOTHESES],'calibration_ids':[],'confirmation_ids':[],
  'protocol':exact_ref(root,P+'audit/epoch31/protocol.json'),'protocol_path':P+'audit/epoch31/protocol.json','protocol_sha256':exact_ref(root,P+'audit/epoch31/protocol.json')['sha256'],'scorer':exact_ref(root,args.scorer),'source_freeze':freeze_ref,
  'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],
  'trained_parameters_path':schema.ARTIFACT_PATH,'archived_model_seal':exact_ref(root,schema.ARCHIVED_SEAL_PATH),'archived_model_seal_path':schema.ARCHIVED_SEAL_PATH,'archived_model_seal_sha256':exact_ref(root,schema.ARCHIVED_SEAL_PATH)['sha256'],
  'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(inference_python),'bart_model_directory':'models/bart-large-mnli-d7645e',
  'expected_operation_counters':ops,'phase_limits':{'dev':{'NLI_forward_calls':96,'optimizer_steps':0}},
  'limits':{'owned_workers':1,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'TRAIN_worker_attempts':0,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},
  'pins':[pins[k] for k in sorted(pins)],**schema.FLAGS,'confirmation':[],
  'CPU_scope':'Kernel affinity0,1 plus inherited narrow affinity-denial guard before model/native import; two CPU threads requested, observed runtime threads retained.',
  'network_scope':'Frozen Python/Node API interposition with one exact source-bound urllib3 loopback IPv6 capability probe per phase; no communication/listening/DNS allowance; compiled-internal opaque calls UNKNOWN.',
  'host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_tmp_free_bytes':16777216,'policy':'Recheck actual host/lock/frozen source before each single reservation. One reservation burns the only current DEV slot; no retry or additional hardware/spend authorization.'}}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true')
 for name in ('source-parent','source-root','source-bench','source-scope'):cli.add_argument('--'+name,required=True)
 for name in ('source-stage','final-stage'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))
