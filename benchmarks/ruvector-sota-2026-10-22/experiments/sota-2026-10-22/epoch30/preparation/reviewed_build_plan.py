"""Root-run E30 master source freeze; no models, labels or external calls.
Copy this reviewed source into public preparation before --check-only or write.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,importlib.util,json,os
from datetime import datetime,timezone
from pathlib import Path
P='experiments/sota-2026-10-22/'
SOURCE='ccd765026806aa3d7e43e295238a741c874a46b8'
KIND='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47')

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def write_new(path,value):
 with path.open('x',encoding='utf-8') as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def build(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch30');pub=study/'publication'
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact fresh reconstructed E30 scope required')
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 import phase_schema_v1 as schema
 common.live_owner(scope)
 if (study/'plan.json').exists() or (study/'source-freeze.json').exists():raise ValueError('Master source plan/freeze already exist; no overwrite')
 candidate=P+'candidate/epoch30/';assets=P+'epoch30/preparation/runtime-assets.lock.json'
 paths={'train_inputs':P+'audit/epoch30/data/train.inputs.json','dev_inputs':P+'audit/epoch30/data/dev.inputs.json',
  'runtime_assets_lock':assets,'bart_assets_lock':P+'candidate/epoch27/MODEL_ASSETS.json',
  'original_reader':P+'candidate/epoch27/reader/bart_reader.py',
  'runtime_policy_addendum':P+'audit/epoch30/runtime-policy-addendum-v1.json'}
 required=list(paths.values())+[candidate+n for n in ('worker.py','native_helper.cjs','algorithm.py','EXPECTED_COUNTERS.json','runtime/common.py','runtime/launch.py','runtime/preflight.py')]+[P+'audit/epoch30/protocol.json',P+'audit/epoch30/score_train.py',args.scorer]
 for name in required:exact_ref(root,name)
 if not args.scorer.startswith(P+'audit/epoch30/') or not args.scorer.endswith('.py'):raise ValueError('Current E30 independent scorer source required')
 spec=importlib.util.spec_from_file_location('reviewed_e30_stdlib_algorithm',root/(candidate+'algorithm.py'));algorithm=importlib.util.module_from_spec(spec);spec.loader.exec_module(algorithm)
 if algorithm.KIND!=KIND or algorithm.SEED!=30030 or list(algorithm.TRAIN_DOCUMENT_IDS)!=schema.ROLES['train'] or list(algorithm.DEV_DOCUMENT_IDS)!=schema.ROLES['dev'] or list(algorithm.HYPOTHESIS_IDS)!=schema.HYPOTHESES:raise ValueError('Fixed algorithm/roles differ')
 counts=common.parse(root/(candidate+'EXPECTED_COUNTERS.json'))
 ops=counts['expected_operation_counters']
 if counts.get('epoch')!=30 or counts.get('kind')!=KIND or set(ops)!={'train','dev'} or any(not isinstance(v,dict) or not v or any(not isinstance(k,str) or type(n)is not int or n<0 for k,n in v.items()) for v in ops.values()):raise ValueError('Exact source operation budgets required')
 if ops['train'].get('NLI_forward_calls_completed')!=24 or ops['dev'].get('NLI_forward_calls_completed')!=96 or ops['train'].get('TRAIN_input_bank_reads')!=2:raise ValueError('Frozen TRAIN24/DEV96 source budgets differ')
 inference_python=root/'retrieval/.venv/bin/python'
 if (not inference_python.is_file() or not inference_python.resolve().is_file() or any(p.is_symlink() for p in inference_python.parents)
     or inference_python.resolve()!=Path(sys.executable).resolve() or Path(sys.prefix).absolute()!=root/'retrieval/.venv'):raise ValueError('Use approved project venv Python, preserving lexical executable path')
 lock=common.parse(root/assets);dependencies=[]
 for key in ('wheel_lock','native_closure','BGE_source','wheel_members_reference'):
  row=exact_ref(root,lock[key+'_path'])
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Runtime dependency identity changed: '+key)
  dependencies.append(row)
 dependencies += [exact_ref(root,paths['bart_assets_lock']),exact_ref(root,paths['original_reader'])]
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
 if any('/runs/' in r['path'] or r['path'].endswith(('SOURCE_ADMISSION.json','MODEL_ADMISSION.json','MODEL_SEAL.json')) for r in entries):raise ValueError('Execution/model admission exists before source freeze')
 freeze={'schema_version':1,'epoch':30,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'entries':entries,
  'exclusions':[schema.PLAN_PATH,schema.FREEZE_PATH],'rule':'All source, inputs, fixed optimizer, runtime policy and independent scoring fixed before TRAIN labels/fit. Actual published independent MODEL seal is required before even reading DEV input bytes. No CONF, retry, full104 or benchmark acceptance.'}
 summary={'source_files':len(entries),'TRAIN_cases':24,'DEV_cases':24,'TRAIN_model_forwards':24,'DEV_model_forwards':96,'models_native_labels_Git_calls':0}
 if args.check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,schema.FREEZE_PATH)
 pins={r['path']:r for r in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':30,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'created_at':datetime.now(timezone.utc).isoformat(),
  'hypothesis':'One fixed rank4 adaptation of original2020 BART last2 decoder cross-attention q/v plus existing classifier on24 source-licensed TRAIN decisions may improve typed legal decisions with actual native RuVector evidence; compare original native baseline and same adapted model native/lexical/positional retrieval on24 frozen DEV decisions. DEV is diagnostic, not fresh confirmation or official benchmark placement.',
  'data_roles':schema.ROLES,'hypotheses':schema.HYPOTHESES,'training_algorithm':algorithm.ALGORITHM,
  'training_ids':list(algorithm.TRAIN_CASE_IDS),'development_ids':list(algorithm.DEV_CASE_IDS),'calibration_ids':[],'confirmation_ids':[],
  'protocol':exact_ref(root,P+'audit/epoch30/protocol.json'),'protocol_path':P+'audit/epoch30/protocol.json','protocol_sha256':exact_ref(root,P+'audit/epoch30/protocol.json')['sha256'],'scorer':exact_ref(root,args.scorer),'training_scorer':exact_ref(root,P+'audit/epoch30/score_train.py'),'source_freeze':freeze_ref,
  'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],
  'trained_parameters_path':schema.ARTIFACT_PATH,'trained_parameters_codec':schema.ARTIFACT_CODEC,
  'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_helper.cjs','inference_python':str(inference_python),'bart_model_directory':'models/bart-large-mnli-d7645e',
  'expected_operation_counters':ops,'phase_limits':{'train':{'NLI_forward_calls':24,'optimizer_steps':24},'dev':{'NLI_forward_calls':96,'optimizer_steps':0}},
  'limits':{'owned_workers':2,'per_phase_owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':2,'TRAIN_worker_attempts':1,'DEV_worker_attempts':1,'CONF_worker_attempts':0,'paid_calls':0,'GPU_calls':0},
  'pins':[pins[k] for k in sorted(pins)],**schema.FLAGS,'confirmation':[],
  'CPU_scope':'Kernel affinity0,1 plus inherited narrow affinity-denial guard before model/native import; two CPU threads requested, observed runtime threads retained.',
  'network_scope':'Frozen Python/Node API interposition with one exact source-bound urllib3 loopback IPv6 capability probe per phase; no communication/listening/DNS allowance; compiled-internal opaque calls UNKNOWN.',
  'host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_tmp_free_bytes':16777216,'policy':'Recheck actual host/lock/frozen source before each single reservation. TRAIN failure closes DEV; no retry or additional hardware/spend authorization.'}}
 for key,path in paths.items():plan[key+'_path']=path;plan[key+'_sha256']=exact_ref(root,path)['sha256']
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,schema.PLAN_PATH),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);cli.add_argument('--scorer',required=True);cli.add_argument('--check-only',action='store_true');print(json.dumps(build(cli.parse_args()),sort_keys=True))
