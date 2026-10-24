"""Root-run E31 replay publication; no model, label join or external calls.
The independently frozen scorer creates the replay and final binding first.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,os,re
from pathlib import Path
P='experiments/sota-2026-10-22/'
DEFAULT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa')

def write_new(path,value):
 with path.open('x',encoding='utf-8') as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def run(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch31')
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact reconstructed E31 root required')
 sys.path.insert(0,str(study/'publication'));import publication_common_v1 as c
 import stage_publication_v1 as pub
 import phase_schema_v1 as schema
 import phase_receipts_v1 as receipts
 c.live_owner(scope);plan=c.parse(study/'plan.json');planref=c.ref(root,schema.PLAN_PATH)
 if plan.get('epoch')!=31 or plan.get('kind')!=schema.KIND or plan.get('source_checkpoint')!=c.BASE_COMMIT:raise ValueError('Wrong immutable source plan')
 pins={row['path']:row for row in plan['pins']}
 if len(pins)!=len(plan['pins']):raise ValueError('Duplicate source pin')
 for path,row in pins.items():
  if c.ref(root,path)!=row:raise ValueError('Immutable source changed: '+path)
 ownsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not any(row['sha256']==ownsha and row['path'].endswith('reviewed_build_results.py') for row in pins.values()):raise ValueError('Results helper not in master source freeze')
 if pins.get(plan['scorer']['path'])!=plan['scorer']:raise ValueError('Independent scorer not in source freeze')
 prior=args.priorcontrols.absolute()
 if prior!=scope/'controls-source':raise ValueError('Canonical actual SOURCE prior controls required')
 pc=c.parse(prior/'CONTINUATION.json');pa=c.parse(prior/'ACTIVE_RUN.json')
 if pa.get('state')!='EPOCH31_SOURCE_FROZEN_DEV_PENDING_ADMISSION':raise ValueError('Wrong actual current prior phase')
 admission=c.parse(study/'SOURCE_ADMISSION.json')
 if admission.get('plan_sha256')!=planref['sha256'] or admission.get('source_freeze_sha256')!=plan['source_freeze_sha256'] or not re.fullmatch('[0-9a-f]{40}',admission.get('published_source_commit','')):raise ValueError('Actual source admission differs')
 dev=receipts.phase_evidence(root,'dev',planref);actual=receipts.aggregate_actual(dev);counts=receipts.cumulative_counts(actual)
 seal=pub.archive_ready(root,c.cp_rows(c.parse(scope/'kit/CHECKPOINT_MANIFEST.json')),c.parse(root/schema.ARCHIVED_SEAL_PATH))
 def ref(path):return c.ref(root,Path(path).relative_to(root).as_posix())
 def collect():return [dict(path=path,bytes=len(body),sha256=c.sha(body)) for path,body in sorted(c.walk_current(root).items())]
 replay_path=args.replay.absolute();report_path=args.acceptance.absolute()
 for path in (replay_path,report_path):
  if not path.is_relative_to(root/(P+'audit/epoch31')):raise ValueError('Current public independent audit artifacts required')
 if args.mode=='results':
  replay=c.parse(replay_path)
  if replay.get('epoch')!=31 or replay.get('kind')!=schema.KIND or type(replay.get('diagnostic_qualified'))is not bool or type(replay.get('archived_training_integrity_passed'))is not bool:raise ValueError('Wrong independent replay epoch/verdict')
  status=replay.get('status');qualified=replay['diagnostic_qualified']
  if status not in pub.FINAL_STATUSES or (status=='DEV_DIAGNOSTIC_QUALIFIED')is not qualified:raise ValueError('Independent status/verdict mismatch')
  if replay['archived_training_integrity_passed']is not True:raise ValueError('Historical archive integrity attribution differs')
  if not receipts.same_fact(replay.get('actual_execution'),actual):raise ValueError('Replay canonical observed phase counters/resources differ')
  evidence={'raw':dev['raw'],'execution':dev['execution'],'archived_model_seal':c.ref(root,schema.ARCHIVED_SEAL_PATH),'parameter_artifact':seal['parameter_artifact']}
  for key,value in evidence.items():
   if not receipts.same_fact(replay.get('evidence',{}).get(key),value):raise ValueError('Replay receipt/archive reference differs: '+key)
  # Copy independent outcomes/uncertainty wholesale; prose never replaces scores.
  reason=('Frozen DEV diagnostic acceptance passed; no fresh confirmation or official benchmark acceptance exists.' if qualified else 'Frozen current DEV archived-adaptation diagnostic acceptance did not pass; retain all original failures, unstarted phases and incomplete/unknown captured counters. No retry or confirmation is authorized.')
  results=copy.deepcopy(replay);results.update(**schema.FLAGS,source_checkpoint=c.BASE_COMMIT,
   published_frozen_source_commit=admission['published_source_commit'],confirmation=[],used_confirmation_identities=[],data_roles=schema.ROLES,
   reason=reason,actual_execution=actual,cumulative_execution=counts,qualification_replay=ref(replay_path),all_slots_closed=True,
   scope='One96-forward current DEV diagnostic of the exact BASE-published E30 learned artifact, with original native baseline and matched same archived adapted model native/lexical/positional retrieval. Zero current TRAIN/fit/MODEL phase. No CONF, full104 retry, benchmark placement, champion promotion or new submission.',
   future_confirmation='None consumed or authorized. All8 current DEV document identities remain exposed forever; archived E30TRAIN8 are historical and remain retired separately.')
  write_new(study/'RESULTS.json',results);resultref=ref(study/'RESULTS.json')
  ledger=copy.deepcopy(c.parse(root/pc['rejection_ledger']['path']))
  ledger['epoch31_budget']={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
  ledger['epoch31_actual_execution']=actual;ledger['epoch31_cumulative_execution']=counts
  ledger['epoch31_counting_scope']='Preserve every historical flat field. Explicit prior corpus25attempts/23complete and boundednative31 plus current DEV reservation/completion; qualifications6 and HTTP885success/2fail unchanged. Current DEV NLI forwards are separate from HTTP. Reserved/uncertain attempts remain burned; absent/partial internal operations UNKNOWN.'
  ledger['epoch31_data_roles']=copy.deepcopy(pc['epoch31_data_roles'])
  ledger['epoch31_decision']={**schema.FLAGS,'epoch':31,'status':status,'diagnostic_qualified':qualified,'archived_training_integrity_passed':results['archived_training_integrity_passed'],'results':resultref,'reason':reason}
  if qualified:ledger['epoch31_diagnostic_qualification']={**schema.FLAGS,'epoch':31,'status':status,'diagnostic_qualified':True,'results':resultref,'reason':reason}
  else:ledger['rejections'].append({'epoch':31,'status':status,'reason':reason,'results':resultref})
  write_new(study/'REJECTION_LEDGER.json',ledger)
  return {'status':status,'results':resultref,'actual_execution':actual,'cumulative_execution':counts,'scorer_fields_preserved':True}
 results=c.parse(study/'RESULTS.json');report=c.parse(report_path)
 if report.get('epoch')!=31 or report.get('kind')!=schema.KIND or report.get('checks_passed')is not True:raise ValueError('Independent final binding did not pass')
 for key in ('diagnostic_qualified','archived_training_integrity_passed'):
  if not receipts.same_fact(report.get(key),results[key]):raise ValueError('Independent verdict differs')
 expected={'raw':dev['raw'],'execution':dev['execution'],'results':ref(study/'RESULTS.json'),'archived_model_seal':c.ref(root,schema.ARCHIVED_SEAL_PATH),'parameter_artifact':seal['parameter_artifact']}
 for key,value in expected.items():
  if not receipts.same_fact(report.get('evidence',{}).get(key),value):raise ValueError('Final binding reference mismatch: '+key)
 source={'schema_version':1,'epoch':31,'kind':schema.KIND,'source_checkpoint':c.BASE_COMMIT,'plan':planref,'source_freeze':plan['source_freeze'],'files':collect(),'rule':'Current reviewed public files before nonrecursive source/epoch manifest creation. Final checkpoint covers both.'}
 write_new(study/'SOURCE_MANIFEST.json',source)
 manifest={'schema_version':1,'epoch':31,'kind':schema.KIND,**schema.FLAGS,'status':results['status'],'diagnostic_qualified':results['diagnostic_qualified'],'archived_training_integrity_passed':results['archived_training_integrity_passed'],
  'source_checkpoint':c.BASE_COMMIT,'confirmation':[],'used_confirmation_identities':[],'data_roles':schema.ROLES,'all_slots_closed':True,'phase_remaining':{'train':0,'dev':0,'confirmation':0},
  'plan':planref,'source_freeze':plan['source_freeze'],'archived_model_seal':plan['archived_model_seal'],'results':ref(study/'RESULTS.json'),'independent_report':ref(report_path),'source_manifest':ref(study/'SOURCE_MANIFEST.json'),'rejection_ledger':ref(study/'REJECTION_LEDGER.json'),
  'actual_execution':actual,'cumulative_execution':counts,'files':collect(),'limitations':results['scope'],'goal_verified':False}
 write_new(study/'EPOCH_MANIFEST.json',manifest)
 return {'manifest':ref(study/'EPOCH_MANIFEST.json'),'status':manifest['status'],'all_slots_closed':True,'models_native_labels_Git_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--mode',choices=('results','manifest'),required=True);cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE)
 for name in ('priorcontrols','replay','acceptance'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(run(cli.parse_args()),sort_keys=True))
