"""Generation2 publication-only recovery of frozen E30 SOURCE -> rejected FINAL.

This wrapper never imports a model/runtime/scorer or changes any frozen source.
Only frozen publication live_owner callbacks are rebound, after exact proof,
source-byte, physical absence and recovery-lock checks. Every scientific gate
and captured original execution identity remains unchanged.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,fcntl,hashlib,importlib.util,json,os,re,stat,time
from pathlib import Path
from types import SimpleNamespace
S=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47')
ROOT=S/'project';P='experiments/sota-2026-10-22/';E=P+'epoch30/'
HERE=ROOT/(E+'recovery');PROTOCOL=HERE/'protocol.json'
SOURCE='8d1f126b9dffaef5d50712e80489f7a5f3984091'
TREES=('662cc2b7b68ee19a7ebde3d062d2df84f518c9a6','8f2ee3bf50ef11810d2583fc0dc4171d6f62d923','41524144fe02e954382c4505665d948bfe78b96e')
MAIN='46d816ddc4c2a8a06cd3613534a79b1d557d858b'
KIND='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
PID,TICKS,INODE,DEV,EXPIRY=86359,18881796,13626,33,1792868716.0493217
OWNER=S/'recovery-owner.json';LOCK=S.parent/'exclusive.work.lock'
OLD_OWNER_SHA='ff77382ed1dc4b99a600b3754b7cba5f42465fa8ab4a158dc842d9b4ff0a8fa3'
OLD_JOURNAL_SHA='ad9a3f9c0c31badc5ce20a18384dfb61d631f5a32553737c711094c493270326'
FINAL_STAGE=Path('/workspace/ruvector-e30-publication-staging/epoch30-9f13c9bb6e47/final')
REASON='Original frozen execution guardian was lost after completed independently accepted TRAIN and before actual MODEL publication. Generation2 authority may only retain truthful failed/unstarted diagnostic evidence and publish FINAL; no retraining, MODEL publication, DEV admission, benchmark acceptance or promotion.'
FROZEN_MODULES={
 'publication_common_v1.py':'5b4808450b6f0a72d82512102d66e15bf6b67e37bbeb65b97b8f0133db74ff0c',
 'phase_schema_v1.py':'573540c8ffcbe5433fc6b505b6a9fe55ecb7ea22073d53d72951fbcf105114e4',
 'phase_receipts_v1.py':'f42be530bade9fd3bc3bc392b77e0a09ddca04af0654dae8afa1fa7560cc1308',
 'parameter_artifact_v1.py':'a2122e517483e139fb2502876a1d524b2dca001daa97c60727b80fccc6744502',
 'stage_publication_v1.py':'6cea6e57ddaa8ab4d01aada364e05dc0ffef65215c6a9bc32b96067d9463810e',
 'build_controls_v1.py':'0912f701e43dd23c0fdc85c2255f86d734fe94645ca65ba77fb7c6b1c9c7c8e8'}
RESULTS_SHA='02d3dbbbe1612c1c747fce7096755508c8c3e40b9e38cf387c56c57379f7906c'

def require(test,message):
 if not test:raise ValueError(message)

def canonical(path):
 path=Path(path).absolute();require(not any(x.is_symlink() for x in (path,*path.parents)),'Symlink refused');return path

def blob(path):
 path=canonical(path);require(path.is_file() and stat.S_ISREG(path.stat().st_mode),'Regular file required: '+str(path));return path.read_bytes()

def sha(data):return hashlib.sha256(data).hexdigest()

def unique(pairs):
 result={}
 for key,value in pairs:require(key not in result,'Duplicate JSON key');result[key]=value
 return result

def read(path):return json.loads(blob(path),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ValueError('Nonfinite JSON')))

def identity(path):
 body=blob(path);return {'path':str(Path(path).absolute()),'bytes':len(body),'sha256':sha(body)}

def exact(row,public=False):
 require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Exact reference required')
 path=ROOT/row['path'] if public else Path(row['path'])
 value=identity(path);require(value['bytes']==row['bytes'] and value['sha256']==row['sha256'],'Exact identity changed: '+str(path));return canonical(path)

def public_ref(path):
 row=identity(path);row['path']=str(canonical(path).relative_to(ROOT));return row

def proc(pid):
 try:
  row=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'state':row[0],'ppid':int(row[1]),'pgid':int(row[2]),'sid':int(row[3]),'ticks':int(row[19])}
 except (OSError,ValueError,IndexError):return None

def recovery_owner(_scope=S):
 require(canonical(_scope)==S,'Wrong recovery scope');owner=read(OWNER)
 require(owner.get('generation')==2 and (owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==(PID,TICKS,INODE)
  and owner.get('expires_unix')==EXPIRY and owner.get('run_id')==S.name
  and owner.get('scope')=='ruvnet/RuVector:benchmarks/ruvector-sota-2026-10-22'
  and owner.get('lock')==str(LOCK) and owner.get('CPU_affinity')==[0,1],'Wrong recovery guardian identity')
 row=proc(PID);require(row and row['state']not in ('Z','X') and row['ticks']==TICKS and time.time()<EXPIRY and not(S/'recovery-release.request').exists(),'Recovery guardian dead/reused/released/expired')
 require(os.sched_getaffinity(PID)=={0,1},'Recovery affinity changed')
 fd=os.open(canonical(LOCK),os.O_RDONLY|os.O_NOFOLLOW)
 try:
  info=os.fstat(fd);require(stat.S_ISREG(info.st_mode) and info.st_ino==INODE and info.st_dev==DEV,'Recovery FLOCK inode/device differs')
  wanted=(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino);held=False
  for line in Path('/proc/locks').read_text().splitlines():
   fields=line.split()
   if len(fields)>=8 and fields[1:5]==['FLOCK','ADVISORY','WRITE',str(PID)]:
    a,b,c=fields[5].split(':');held|=(int(a,16),int(b,16),int(c))==wanted
  require(held,'Recovery exact FLOCK absent')
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:
   fcntl.flock(fd,fcntl.LOCK_UN);raise ValueError('Recovery contender unexpectedly acquired lock')
 finally:os.close(fd)
 return owner

def guard(args):
 require(canonical(args.protocol)==PROTOCOL and sha(blob(PROTOCOL))==args.protocol_sha256,'Wrong independently frozen new recovery protocol')
 protocol=read(PROTOCOL);require(protocol.get('epoch')==30 and protocol.get('kind')=='FINAL_ONLY_PUBLICATION_RECOVERY' and protocol.get('generation')==2 and protocol.get('source_commit')==SOURCE,'Wrong recovery-only protocol')
 exact(protocol['wrapper'],True);require(protocol['wrapper']['path']==E+'recovery/finalize_only.py' and canonical(__file__)==HERE/'finalize_only.py','Wrong reviewed recovery wrapper')
 require(sha(blob(S/'owner.json'))==OLD_OWNER_SHA and len(blob(S/'owner.json'))==431,'Historical owner bytes changed')
 oldjournal=blob(S/'mutation-journal.jsonl');require(sha(oldjournal)==OLD_JOURNAL_SHA and len(oldjournal.splitlines())==40,'Historical mutation journal changed')
 for pid in (84004,86119,86120):require(proc(pid)is None,'Old guardian/known worker PID still exists')
 require(not(ROOT/(E+'DEV_ATTEMPT_RESERVATION.json')).exists() and not(ROOT/(E+'runs/dev')).exists() and not(ROOT/(E+'MODEL_ADMISSION.json')).exists(),'DEV/reservation/admission must remain absent')
 for row in protocol['frozen_files']:exact(row,True)
 for row in protocol['historical_local_files']:exact(row)
 proofpath=exact(protocol['independent_recovery_proof'],True);proof=read(proofpath)
 require(proof.get('checks_passed')is True and proof.get('original_source_commit')==SOURCE
  and proof.get('oldguardian_absent')is True and proof.get('old_worker_groups_absent')is True
  and proof.get('DEV_reservation_directory_admission_absent')is True,'Independent actual recovery absence proof required')
 require(proof.get('original_owner')==identity(S/'owner.json') and proof.get('original_journal')==identity(S/'mutation-journal.jsonl'),'Recovery proof historical owner/journal identity differs')
 owner=recovery_owner();require(protocol.get('recovery_owner_external')==identity(OWNER),'Recovery owner file identity differs')
 plan=read(ROOT/(E+'plan.json'));pins={r['path']:r for r in plan['pins']};require(len(pins)==len(plan['pins']),'Duplicate frozen original source pin')
 for row in pins.values():exact(row,True)
 require(read(S/'controls-source/ACTIVE_RUN.json').get('state')=='EPOCH30_SOURCE_FROZEN_TRAIN_PENDING_ADMISSION','Only actual original SOURCE can be finalized')
 require(read(ROOT/(E+'SOURCE_ADMISSION.json')).get('published_source_commit')==SOURCE,'Original actual source admission changed')
 train_execution=read(ROOT/(E+'runs/train/execution.json'));worker=train_execution.get('worker_identity')
 require(isinstance(worker,dict) and type(worker.get('pgid'))is int and type(worker.get('sid'))is int,'Exact original TRAIN process identity required')
 for entry in Path('/proc').iterdir():
  if entry.name.isdigit():
   row=proc(int(entry.name))
   require(not(row and row['state']not in ('Z','X') and (row['pgid']==worker['pgid'] or row['sid']==worker['sid'])),'Original TRAIN group/session still has live processes')
 pubdir=ROOT/(E+'publication')
 for name,digest in FROZEN_MODULES.items():require(sha(blob(pubdir/name))==digest and pins.get(E+'publication/'+name,{}).get('sha256')==digest,'Frozen publication dependency differs: '+name)
 require(sha(blob(ROOT/(E+'preparation/reviewed_build_results.py')))==RESULTS_SHA and pins.get(E+'preparation/reviewed_build_results.py',{}).get('sha256')==RESULTS_SHA,'Frozen results builder changed')
 return protocol,owner

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def frozen_modules(args):
 protocol,owner=guard(args);folder=ROOT/(E+'publication');sys.path.insert(0,str(folder))
 for name in ('publication_common_v1','phase_schema_v1','phase_receipts_v1','parameter_artifact_v1','stage_publication_v1','build_controls_v1'):
  require(name not in sys.modules,'Fresh wrapper process required; no cached frozen modules')
 common=load('publication_common_v1',folder/'publication_common_v1.py')
 # The only callback substitution. Original owner constants and every source,
 # phase/scoring/history/transport/acceptance check remain unmodified.
 common.live_owner=recovery_owner
 stage=load('stage_publication_v1',folder/'stage_publication_v1.py')
 controls=load('build_controls_v1',folder/'build_controls_v1.py')
 results=load('e30_original_frozen_results',ROOT/(E+'preparation/reviewed_build_results.py'))
 require(stage.live_owner is recovery_owner and controls.live_owner is recovery_owner,'Frozen live-owner callback binding failed')
 train=stage.phase_evidence(ROOT,'train',common.ref(ROOT,E+'plan.json'),required=True)
 require(stage.phase_completed(train) and train['actual']['worker_attempts']==1,'Retained original TRAIN must remain completed and physically closed')
 require(stage.phase_evidence(ROOT,'dev',common.ref(ROOT,E+'plan.json'))['actual']['status']=='NOT_STARTED','Recovery DEV must remain unstarted')
 return protocol,owner,common,stage,controls,results

def final_verdict(path):
 value=read(path);require(value.get('status')=='TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED' and value.get('train_integrity_passed')is True and value.get('diagnostic_qualified')is False and value.get('metrics')is None,'Recovery cannot change frozen interrupted outcome')
 for key in ('benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'):require(value.get(key)is False,'Forbidden acceptance/promotion')
 require(value.get('official_rank')is None,'Forbidden official rank');return value

def replace_new(path,value):
 temp=path.with_name(path.name+'.recovery-new');body=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
 with temp.open('xb')as out:out.write(body);out.flush();os.fsync(out.fileno())
 os.replace(temp,path);fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def authority(args,protocol,owner):
 return {'kind':'FINAL_ONLY_PUBLICATION_RECOVERY','generation':2,'publication_recovery_owner':copy.deepcopy(owner),'protocol':public_ref(PROTOCOL),'independent_recovery_proof':protocol['independent_recovery_proof'],'reason':REASON,'original_physical_owner_role':'HISTORICAL_FROZEN_EXECUTION_IDENTITY_NOT_CURRENT_PUBLICATION_AUTHORITY','scientific_gates_unchanged':True,'MODEL_published':False,'DEV_admitted':False,'new_model_native_or_label_calls':0}

def assert_final_controls(args,protocol,owner):
 active=read(S/'controls-final/ACTIVE_RUN.json');cont=read(S/'controls-final/CONTINUATION.json');old=read(S/'controls-source/ACTIVE_RUN.json');record=authority(args,protocol,owner)
 require(active.get('physical_owner')==old['physical_owner'] and active.get('physical_owner_role')==record['original_physical_owner_role'],'Frozen historical execution owner misrepresented')
 require(active.get('publication_recovery')==record and cont.get('epoch30_publication_recovery')==record and cont.get('active_run')==dict(active,path='ACTIVE_RUN.json'),'Explicit current publication authority missing')
 require(active.get('OS_lock_held_by')=='publication_recovery.publication_recovery_owner' and active.get('state')=='EPOCH30_CLOSED' and active.get('work_active')is False and active.get('native_allowed')==active.get('conditional_train_allowed')==active.get('conditional_dev_allowed')==0,'Recovery final did not close all permissions')

def run(args):
 protocol,owner,c,stage,controls,results=frozen_modules(args)
 if args.operation in ('results','manifest'):
  replay=canonical(args.replay);acceptance=canonical(args.acceptance);final_verdict(replay)
  output=results.run(SimpleNamespace(scope=S,priorcontrols=S/'controls-source',replay=replay,acceptance=acceptance,mode=args.operation))
  final_verdict(ROOT/(E+'RESULTS.json'))
 elif args.operation=='final-controls':
  final_verdict(ROOT/(E+'RESULTS.json'))
  output=controls.build(SimpleNamespace(project=ROOT,kit=S/'kit',priorcontrols=S/'controls-source',phase='final',parent=SOURCE,out=S/'controls-final',reviewed_files=S/'reviewed-final.json',continuation_updates=None))
  active=read(S/'controls-final/ACTIVE_RUN.json');cont=read(S/'controls-final/CONTINUATION.json');record=authority(args,protocol,owner)
  active.update(physical_owner_role=record['original_physical_owner_role'],publication_recovery=record,OS_lock_held_by='publication_recovery.publication_recovery_owner')
  cont['epoch30_publication_recovery']=record;cont['active_run']=dict(active,path='ACTIVE_RUN.json')
  replace_new(S/'controls-final/ACTIVE_RUN.json',active);replace_new(S/'controls-final/CONTINUATION.json',cont);assert_final_controls(args,protocol,owner)
 else:
  assert_final_controls(args,protocol,owner);final_verdict(ROOT/(E+'RESULTS.json'))
  output=stage.prepare(SimpleNamespace(project=ROOT,kit=S/'kit',controls=S/'controls-final',priorcontrols=S/'controls-source',phase='final',source_filemap=S/'actual-git-map.json',prior_expected=S/'stage-source/expected-leaves.json',reviewed_files=S/'reviewed-final.json',parent_readback=ROOT/(P+'audit/epoch30/source-actual-readback-independent.json'),parent=SOURCE,expected_main=MAIN,expected_root=TREES[0],expected_bench=TREES[1],expected_scope=TREES[2],out=FINAL_STAGE))
 recovery_owner();return {'operation':args.operation,'FINAL_only_recovery':True,'publication_recovery_owner_pid':PID,'frozen_operation_result':output,'model_native_scorer_or_label_calls_by_wrapper':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--protocol',type=Path,required=True);cli.add_argument('--protocol-sha256',required=True)
 cli.add_argument('operation',choices=('results','manifest','final-controls','final-stage'));cli.add_argument('--replay',type=Path);cli.add_argument('--acceptance',type=Path)
 args=cli.parse_args()
 if args.operation in ('results','manifest')and(args.replay is None or args.acceptance is None):cli.error('results/manifest require public --replay and --acceptance paths')
 print(json.dumps(run(args),sort_keys=True))
