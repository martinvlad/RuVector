"""Root-run E30 replay publication; no model, label join or external calls.
The independently frozen scorer creates the replay and final binding first.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,os,re
from pathlib import Path
P='experiments/sota-2026-10-22/'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47')

def write_new(path,value):
 with path.open('x',encoding='utf-8') as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def run(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch30')
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact reconstructed E30 root required')
 sys.path.insert(0,str(study/'publication'));import publication_common_v1 as c
 import stage_publication_v1 as pub
 import phase_schema_v1 as schema
 import phase_receipts_v1 as receipts
 c.live_owner(scope);plan=c.parse(study/'plan.json');planref=c.ref(root,schema.PLAN_PATH)
 if plan.get('epoch')!=30 or plan.get('kind')!=schema.KIND or plan.get('source_checkpoint')!=c.BASE_COMMIT:raise ValueError('Wrong immutable source plan')
 pins={row['path']:row for row in plan['pins']}
 if len(pins)!=len(plan['pins']):raise ValueError('Duplicate source pin')
 for path,row in pins.items():
  if c.ref(root,path)!=row:raise ValueError('Immutable source changed: '+path)
 ownsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not any(row['sha256']==ownsha and row['path'].endswith('reviewed_build_results.py') for row in pins.values()):raise ValueError('Results helper not in master source freeze')
 if pins.get(plan['scorer']['path'])!=plan['scorer']:raise ValueError('Independent scorer not in source freeze')
 prior=args.priorcontrols.absolute()
 if prior not in (scope/'controls-source',scope/'controls-model'):raise ValueError('Canonical actual SOURCE/MODEL prior controls required')
 pc=c.parse(prior/'CONTINUATION.json');pa=c.parse(prior/'ACTIVE_RUN.json')
 accepted=pa.get('state')=='EPOCH30_MODEL_SEALED_DEV_PENDING_ADMISSION'
 if not accepted and pa.get('state')!='EPOCH30_SOURCE_FROZEN_TRAIN_PENDING_ADMISSION':raise ValueError('Wrong actual prior phase')
 admission=c.parse(study/'SOURCE_ADMISSION.json')
 if admission.get('plan_sha256')!=planref['sha256'] or admission.get('source_freeze_sha256')!=plan['source_freeze_sha256'] or not re.fullmatch('[0-9a-f]{40}',admission.get('published_source_commit','')):raise ValueError('Actual source admission differs')
 train=receipts.phase_evidence(root,'train',planref);dev=receipts.phase_evidence(root,'dev',planref)
 actual=receipts.aggregate_actual(train,dev);counts=receipts.cumulative_counts(actual)
 if not accepted and dev['actual']['status']!='NOT_STARTED':raise ValueError('Unaccepted MODEL cannot have consumed DEV')
 def ref(path):return c.ref(root,Path(path).relative_to(root).as_posix())
 def collect():return [dict(path=path,bytes=len(body),sha256=c.sha(body)) for path,body in sorted(c.walk_current(root).items())]
 replay_path=args.replay.absolute();report_path=args.acceptance.absolute()
 for path in (replay_path,report_path):
  if not path.is_relative_to(root/(P+'audit/epoch30')):raise ValueError('Current public independent audit artifacts required')
 if args.mode=='results':
  replay=c.parse(replay_path)
  if replay.get('epoch')!=30 or replay.get('kind')!=schema.KIND or type(replay.get('diagnostic_qualified'))is not bool or type(replay.get('train_integrity_passed'))is not bool:raise ValueError('Wrong independent replay epoch/verdict')
  status=replay.get('status');qualified=replay['diagnostic_qualified']
  if status not in pub.FINAL_STATUSES or (status=='DEV_DIAGNOSTIC_QUALIFIED')is not qualified:raise ValueError('Independent status/verdict mismatch')
  if (not accepted and (status!='TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED' or qualified)) or (accepted and (status=='TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED' or replay['train_integrity_passed']is not True)):raise ValueError('Replay misstates actual accepted MODEL phase')
  if not receipts.same_fact(replay.get('actual_execution'),actual):raise ValueError('Replay canonical observed phase counters/resources differ')
  evidence={'train_raw':train['raw'],'train_execution':train['execution'],'dev_raw':dev['raw'],'dev_execution':dev['execution']}
  for key,value in evidence.items():
   if not receipts.same_fact(replay.get('evidence',{}).get(key),value):raise ValueError('Replay receipt reference differs: '+key)
  if accepted:
   seal,_,_=pub.model_ready(root,plan,None)
   for key,value in {'model_seal':c.ref(root,schema.MODEL_SEAL_PATH),'parameter_artifact':seal['parameter_artifact']}.items():
    if replay.get('evidence',{}).get(key)!=value:raise ValueError('Replay lost sealed MODEL reference: '+key)
  # Copy independent outcomes/uncertainty wholesale; prose never replaces scores.
  reason=('Frozen DEV diagnostic acceptance passed; no fresh confirmation or official benchmark acceptance exists.' if qualified else 'Frozen TRAIN/MODEL/DEV diagnostic acceptance did not pass; retain all original failures, unstarted phases and incomplete/unknown captured counters. No retry or confirmation is authorized.')
  results=copy.deepcopy(replay);results.update(**schema.FLAGS,source_checkpoint=c.BASE_COMMIT,
   published_frozen_source_commit=admission['published_source_commit'],confirmation=[],used_confirmation_identities=[],data_roles=schema.ROLES,
   reason=reason,actual_execution=actual,cumulative_execution=counts,qualification_replay=ref(replay_path),all_slots_closed=True,
   scope='One fixed24-step legal parameter adaptation TRAIN and at most one96-forward DEV diagnostic, with original native baseline and matched same-model native/lexical/positional retrieval. No CONF, full104 retry, benchmark placement, champion promotion or new submission.',
   future_confirmation='None consumed or authorized. Every current16 TRAIN/DEV document identity remains exposed forever.')
  write_new(study/'RESULTS.json',results);resultref=ref(study/'RESULTS.json')
  ledger=copy.deepcopy(c.parse(root/pc['rejection_ledger']['path']))
  ledger['epoch30_budget']={'train_worker_attempts_used':train['actual']['worker_attempts'],'dev_worker_attempts_used':dev['actual']['worker_attempts'],'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
  ledger['epoch30_actual_execution']=actual;ledger['epoch30_cumulative_execution']=counts
  ledger['epoch30_counting_scope']='Preserve every historical flat field. Explicit prior corpus24attempts/22complete and boundednative30 plus current phase reservations/completions; qualifications6 and HTTP885success/2fail unchanged. TRAIN/DEV NLI forwards are separate from HTTP. Reserved/uncertain attempts remain burned; absent/partial internal operations UNKNOWN.'
  ledger['epoch30_data_roles']=copy.deepcopy(pc['epoch30_data_roles'])
  ledger['epoch30_decision']={**schema.FLAGS,'epoch':30,'status':status,'diagnostic_qualified':qualified,'train_integrity_passed':results['train_integrity_passed'],'results':resultref,'reason':reason}
  if qualified:ledger['epoch30_diagnostic_qualification']={**schema.FLAGS,'epoch':30,'status':status,'diagnostic_qualified':True,'results':resultref,'reason':reason}
  else:ledger['rejections'].append({'epoch':30,'status':status,'reason':reason,'results':resultref})
  write_new(study/'REJECTION_LEDGER.json',ledger)
  return {'status':status,'results':resultref,'actual_execution':actual,'cumulative_execution':counts,'scorer_fields_preserved':True}
 results=c.parse(study/'RESULTS.json');report=c.parse(report_path)
 if report.get('epoch')!=30 or report.get('kind')!=schema.KIND or report.get('checks_passed')is not True:raise ValueError('Independent final binding did not pass')
 for key in ('diagnostic_qualified','train_integrity_passed'):
  if not receipts.same_fact(report.get(key),results[key]):raise ValueError('Independent verdict differs')
 expected={'train_raw':train['raw'],'train_execution':train['execution'],'dev_raw':dev['raw'],'dev_execution':dev['execution'],'results':ref(study/'RESULTS.json')}
 if accepted:
  seal,_,_=pub.model_ready(root,plan,None);expected.update(model_seal=c.ref(root,schema.MODEL_SEAL_PATH),parameter_artifact=seal['parameter_artifact'])
 for key,value in expected.items():
  if not receipts.same_fact(report.get('evidence',{}).get(key),value):raise ValueError('Final binding reference mismatch: '+key)
 source={'schema_version':1,'epoch':30,'kind':schema.KIND,'source_checkpoint':c.BASE_COMMIT,'plan':planref,'source_freeze':plan['source_freeze'],'files':collect(),'rule':'Current reviewed public files before nonrecursive source/epoch manifest creation. Final checkpoint covers both.'}
 write_new(study/'SOURCE_MANIFEST.json',source)
 manifest={'schema_version':1,'epoch':30,'kind':schema.KIND,**schema.FLAGS,'status':results['status'],'diagnostic_qualified':results['diagnostic_qualified'],'train_integrity_passed':results['train_integrity_passed'],
  'source_checkpoint':c.BASE_COMMIT,'confirmation':[],'used_confirmation_identities':[],'data_roles':schema.ROLES,'all_slots_closed':True,'phase_remaining':{'train':0,'dev':0,'confirmation':0},
  'plan':planref,'source_freeze':plan['source_freeze'],'results':ref(study/'RESULTS.json'),'independent_report':ref(report_path),'source_manifest':ref(study/'SOURCE_MANIFEST.json'),'rejection_ledger':ref(study/'REJECTION_LEDGER.json'),
  'actual_execution':actual,'cumulative_execution':counts,'files':collect(),'limitations':results['scope'],'goal_verified':False}
 write_new(study/'EPOCH_MANIFEST.json',manifest)
 return {'manifest':ref(study/'EPOCH_MANIFEST.json'),'status':manifest['status'],'all_slots_closed':True,'models_native_labels_Git_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--mode',choices=('results','manifest'),required=True);cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE)
 for name in ('priorcontrols','replay','acceptance'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(run(cli.parse_args()),sort_keys=True))
