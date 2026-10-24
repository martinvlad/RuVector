"""Root-run E29 source plan builder; no models, labels or external mutations.

Copy this reviewed source into the public preparation directory before running
it. --check-only validates preparation without creating the two master files.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path

P='experiments/sota-2026-10-22/'
SOURCE='07a2cbe78fdee78a8c9bca2aeb64bc9746481ba0'
KIND='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch29-734329c6e9e6')

def exact_ref(root,name):
 path=root/name
 if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Missing/nonregular/symlink source: '+name)
 body=path.read_bytes();return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def source_operations(worker):
 """Evaluate only the reviewed literal/comprehension POSITIVE declaration."""
 tree=ast.parse(worker.read_text());values=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='POSITIVE' for t in n.targets)]
 if len(values)!=1:raise ValueError('Exactly one reviewed POSITIVE declaration required')
 allowed=(ast.Dict,ast.DictComp,ast.comprehension,ast.Name,ast.Load,ast.Store,ast.Constant,ast.Tuple)
 if any(not isinstance(n,allowed) or (isinstance(n,ast.Name) and n.id!='key') for n in ast.walk(values[0])):raise ValueError('Unreviewed operation-budget expression')
 result=eval(compile(ast.Expression(values[0]),str(worker),'eval'),{'__builtins__':{}},{})
 if not isinstance(result,dict) or not result or any(not isinstance(k,str) or type(v)is not int or v<0 for k,v in result.items()):raise ValueError('Invalid fixed operation budget')
 return result

def write_new(path,value):
 with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def build(scope,check_only=False):
 scope=scope.absolute();root=scope/'project';study=root/(P+'epoch29');pub=study/'publication'
 sys.path.insert(0,str(pub));import publication_common_v1 as common
 import stage_publication_v1 as publication
 common.live_owner(scope)
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact reconstructed E29 scope required')
 if (study/'plan.json').exists() or (study/'source-freeze.json').exists():raise ValueError('Master source plan/freeze already exist; no overwrite or retry')
 bank=P+'audit/epoch29/identity/data/engineering-inputs.json';protocol=P+'audit/epoch29/identity/protocol.json';assets=P+'epoch29/preparation/runtime-assets.lock.json';candidate=P+'candidate/epoch29/'
 required=[bank,protocol,assets,candidate+'worker.py',candidate+'native_identity.cjs',candidate+'runtime/common.py',candidate+'runtime/launch.py',candidate+'runtime/preflight.py',P+'audit/epoch29/identity/score_identity.py',publication.HOLD_REF['path']]
 for name in required:exact_ref(root,name)
 if exact_ref(root,bank)['sha256']!='ced6f3969f72f4f07da570f42ed62d439e5db1b440393688e8496acde731f4c3':raise ValueError('Frozen identity bank changed')
 data=json.loads((root/bank).read_text());corpus=[d['document_id'] for d in data['documents']];query=data['query']['document_id']
 if len(corpus)!=261 or corpus!=sorted(set(corpus)) or query!=548 or query in corpus or data['roles']!={'train':[],'dev':[],'calibration':[],'confirmation':[]}:raise ValueError('Wrong metadata-only identity corpus/query roles')
 ops=source_operations(root/(candidate+'worker.py'))
 inference_python=root/'retrieval/.venv/bin/python'
 if (not inference_python.is_file() or not inference_python.resolve().is_file()
     or any(p.is_symlink() for p in inference_python.parents)
     or inference_python.resolve()!=Path(sys.executable).resolve()
     or Path(sys.prefix).absolute()!=root/'retrieval/.venv'):
  raise ValueError('Run the builder with the approved project venv interpreter; preserve its lexical executable path')
 lock=json.loads((root/assets).read_text());dependencies=[]
 for key in ('wheel_lock','native_closure','BGE_source','wheel_members_reference'):
  path=lock[key+'_path'];row=exact_ref(root,path)
  if row['sha256']!=lock[key+'_sha256']:raise ValueError('Dependency manifest changed: '+key)
  dependencies.append(row)
 entries=[]
 for relative in publication.ROOTS:
  directory=root/relative
  if not directory.is_dir():continue
  for path in sorted(directory.rglob('*')):
   if path.is_symlink():raise ValueError('Symlink in current source tree')
   if path.is_file():
    name=path.relative_to(root).as_posix();body=path.read_bytes();common.public_text(name,body);entries.append(exact_ref(root,name))
 entries.sort(key=lambda r:r['path'])
 if len({r['path'] for r in entries})!=len(entries):raise ValueError('Duplicate current source member')
 if not any(row['path'].endswith('reviewed_build_plan.py') for row in entries):raise ValueError('Reviewed builder must be copied into current public source before freeze')
 freeze={'schema_version':1,'epoch':29,'kind':KIND,'source_checkpoint':SOURCE,'data_roles':publication.EMPTY_ROLES,'held_parameter_adaptation':publication.HOLD_REF,'entries':entries,'exclusions':[P+'epoch29/plan.json',P+'epoch29/source-freeze.json'],'rule':'All four-root source/input/oracle/runtime-policy/receipt metadata fixed before any admitted encoding/native call. Original allocation HOLD and no-redraw retirement remain. Result artifacts append only.'}
 summary={'source_files':len(entries),'corpus_documents':len(corpus),'identity_queries':len(corpus)+1,'operation_counter_fields':len(ops),'controls_or_native_Git_model_calls':0}
 if check_only:return {'status':'PREPARATION_CHECK_PASS','would_write_master_files':False,**summary}
 write_new(study/'source-freeze.json',freeze);freeze_ref=exact_ref(root,P+'epoch29/source-freeze.json')
 pins={row['path']:row for row in entries+dependencies+[freeze_ref]}
 plan={'schema_version':1,'epoch':29,'kind':KIND,'source_checkpoint':SOURCE,'actual_project':str(root),'created_at':datetime.now(timezone.utc).isoformat(),'hypothesis':'Use actual native RuVector core2.3 ANN candidate selection followed by authoritative full-normalized-text SHA identity checks to prevent exposed aliases entering allegedly fresh data. Match the same BGE vectors with exact brute cosine retrieval. Retrieval misses remain UNRESOLVED, never CLEAN. No semantic benchmark or model improvement claim.','data_roles':publication.EMPTY_ROLES,'held_parameter_adaptation':publication.HOLD_REF,'original_parameter_adaptation_data_admission':'HOLD; all16 original IDs retired with no redraw, labels, fit or DEV execution','engineering_ids':['document:'+str(i) for i in corpus+[query]],'engineering_inputs_path':bank,'engineering_inputs_sha256':exact_ref(root,bank)['sha256'],'engineering_inputs':exact_ref(root,bank),'protocol':exact_ref(root,protocol),'scorer':exact_ref(root,P+'audit/epoch29/identity/score_identity.py'),'source_freeze':freeze_ref,'source_freeze_path':freeze_ref['path'],'source_freeze_sha256':freeze_ref['sha256'],'runtime_assets_lock_path':assets,'runtime_assets_lock_sha256':exact_ref(root,assets)['sha256'],'worker_path':candidate+'worker.py','native_worker_path':candidate+'native_identity.cjs','inference_python':str(inference_python),'expected_operation_counters':ops,'limits':{'owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':0,'engineering_batches':1,'paid_calls':0,'GPU_calls':0,'training_steps':0,'NLI_calls':0,'CONF_reads':0,'retries_after_reservation':0},'pins':[pins[k] for k in sorted(pins)],'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_rank':None,'official_SOTA_verified':False,'proper_metric_computations':0,'protected_inputs':'Only frozen old-exposed261 corpus plus known retired alias548; remaining122 and protected24 are not encoded. Normalized complete-source SHA is authoritative; BGE internal token cap does not establish full semantic attention.','network_scope':'Persistent Python/Node API interposition, not OS network syscall isolation; opaque compiled-internal counts remain UNKNOWN.','CPU_scope':'Kernel affinity0,1 and inherited narrow sched_setaffinity denial before all native/model imports; sampled task threads disclosed, not asserted2.','host_admission_policy':{'minimum_unallocated_memory_bytes':536870912,'minimum_tmp_free_bytes':16777216,'expected_largest_child_peak_RSS_forecast_bytes':1073741824,'policy':'Refresh actual host/lock/source state after independent remote source readback and before Popen. No extra cache/spend/hardware expansion inferred.'}}
 write_new(study/'plan.json',plan)
 return {'status':'MASTER_SOURCE_FROZEN','plan':exact_ref(root,P+'epoch29/plan.json'),'source_freeze':freeze_ref,'pins':len(pins),**summary}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--scope',type=Path,default=DEFAULT_SCOPE);parser.add_argument('--check-only',action='store_true');args=parser.parse_args();print(json.dumps(build(args.scope,args.check_only),sort_keys=True))
