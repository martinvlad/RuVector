"""E36 independent engineering replay publication. No inference or label join.
The frozen scorer evaluates once after physical closure; BIND is separate.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,os,re
from pathlib import Path
P='experiments/sota-2026-10-22/'
DEFAULT_SCOPE=Path('/workspace/ruvector-epoch36-d73fcce4c45f')

def write_new(path,value):
 with path.open('x',encoding='utf-8')as target:json.dump(value,target,indent=2,ensure_ascii=False,allow_nan=False);target.write('\n');target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def run(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch36')
 if scope!=DEFAULT_SCOPE or root!=root.resolve():raise ValueError('Exact reconstructed E36 workspace required')
 sys.path.insert(0,str(study/'publication'));import publication_common_v1 as c
 import stage_publication_v1 as pub
 import phase_schema_v1 as schema
 import phase_receipts_v1 as receipts
 c.live_owner(scope);plan=c.parse(study/'plan.json');planref=c.ref(root,schema.PLAN_PATH)
 if plan.get('epoch')!=36 or plan.get('kind')!=schema.KIND or plan.get('source_checkpoint')!=c.BASE_COMMIT:raise ValueError('Wrong source plan')
 pins={r['path']:r for r in plan['pins']}
 if len(pins)!=len(plan['pins']):raise ValueError('Duplicate source pin')
 for path,row in pins.items():
  if c.ref(root,path)!=row:raise ValueError('Immutable source changed: '+path)
 ownsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not any(r['sha256']==ownsha and r['path'].endswith('reviewed_build_results.py')for r in pins.values()):raise ValueError('Results helper absent from sourcefreeze')
 if pins.get(plan['scorer']['path'])!=plan['scorer']:raise ValueError('Independent scorer not frozen')
 prior=args.priorcontrols.absolute()
 if prior!=scope/'controls-source':raise ValueError('Canonical actual SOURCE controls required')
 pc=c.parse(prior/'CONTINUATION.json');pa=c.parse(prior/'ACTIVE_RUN.json')
 if pa.get('state')!='EPOCH36_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION':raise ValueError('Wrong prior phase')
 admission=c.parse(study/'SOURCE_ADMISSION.json')
 if admission.get('plan_sha256')!=planref['sha256'] or admission.get('source_freeze_sha256')!=plan['source_freeze_sha256'] or not re.fullmatch('[0-9a-f]{40}',admission.get('published_source_commit','')):raise ValueError('Source admission differs')
 eng=receipts.phase_evidence(root,'engineering',planref);actual=receipts.aggregate_actual(eng);receipts.require_final_physical_closure(actual);counts=receipts.cumulative_counts(actual)
 pub.pretrained_source_ready(root,None,c.ref(root,schema.MODEL_SOURCE_PATH))
 def ref(path):return c.ref(root,Path(path).relative_to(root).as_posix())
 def collect():return[dict(path=path,bytes=len(body),sha256=c.sha(body))for path,body in sorted(c.walk_current(root).items())]
 replay_path=args.replay.absolute();report_path=args.acceptance.absolute()
 for path in(replay_path,report_path):
  if not path.is_relative_to(root/(P+'audit/epoch36')):raise ValueError('Current public independent audit artifacts required')
 if args.mode=='results':
  replay=c.parse(replay_path);passed=replay.get('engineering_passed');status=replay.get('status')
  if replay.get('epoch')!=36 or replay.get('kind')!=schema.KIND or replay.get('diagnostic_qualified')is not False or type(passed)is not bool or replay.get('readiness_qualified')is not passed:raise ValueError('Wrong engineering replay/verdict')
  if status not in pub.FINAL_STATUSES or(status=='ACCEPTED_ENGINEERING_ADMISSION_ONLY')is not passed:raise ValueError('Independent status/verdict differs')
  if replay.get('engineering_only')is not True or replay.get('benchmark_accuracy')is not None or replay.get('used_confirmation_identities')!=[]:raise ValueError('Engineering must not acquire benchmark score/confirmation')
  pub.verify_flags(replay)
  if passed and(replay.get('checks_passed')is not True or not receipts.phase_completed(eng)):raise ValueError('Positive engineering admission requires valid complete independently scored execution')
  if not receipts.same_fact(replay.get('actual_execution'),actual):raise ValueError('Replay canonical observed counters/resources differ')
  evidence={'raw':eng['raw'],'execution':eng['execution'],'pretrained_model_source':c.ref(root,schema.MODEL_SOURCE_PATH),'baseline_model_source':c.ref(root,schema.BASELINE_MODEL_SOURCE_PATH),'model_profiles':c.ref(root,schema.MODEL_PROFILES_PATH)}
  for key,value in evidence.items():
   if not receipts.same_fact(replay.get('evidence',{}).get(key),value):raise ValueError('Replay reference differs: '+key)
  reason=('Frozen new authored CC0 engineering admission passed all9/class/model-gain/proper-score gates. No benchmark generalization, fresh confirmation or official acceptance.'if passed else'Frozen new authored CC0 engineering admission failed. Preserve all numerical/deontic/source-scope errors, same-model controls, proper scores, uncertainty and any runtime/integrity failure. Do not tune/retry this suite or consume benchmark confirmation.')
  results=copy.deepcopy(replay)
  additions={**schema.FLAGS,'source_checkpoint':c.BASE_COMMIT,'published_frozen_source_commit':admission['published_source_commit'],'confirmation':[],'used_confirmation_identities':[],'data_roles':schema.ROLES,'reason':reason,'actual_execution':actual,'cumulative_execution':counts,'qualification_replay':ref(replay_path),'all_slots_closed':True,'scope':'One engineering-only CPU2/600s total worker, one native corpus, nine newly authored fictional CC0 supplied excerpts with exact arithmetic/open-world source-reviewed oracles, six rawT1 arms54 NLI readouts. New original xxlarge full-source primary, same-xxlarge native/lexical/positional two-group controls, and unchanged b354 full-source/native-two paired controls. One original hypothesis native query per case shared by primary/control,9 total. No numerical solver override, proof, fitting, calibration, TRAIN, DEV, CONF, retry or empirical case selection. Full-source labels are not inferred from retrieval omissions. Engineering metrics are stress/readiness evidence only, not a ClaimBench pilot or benchmark generalization/placement/established general model-strength claim. Both original reader training/selection/calibration/foundation lineages and publisher eligibility remain HOLD; submitted native104 unchanged.','future_confirmation':'None consumed or authorized. All325 old exposed benchmark documents remain DEV forever;74unused and24protected confirmation identities unchanged. The nine authored engineering cases are exposed engineering only.'}
  for key,value in additions.items():
   if key in results and not receipts.same_fact(results[key],value):raise ValueError('Never overwrite an evaluated replay field: '+key)
   results[key]=value
  write_new(study/'RESULTS.json',results);resultref=ref(study/'RESULTS.json')
  ledger=copy.deepcopy(c.parse(root/pc['rejection_ledger']['path']))
  ledger['epoch36_budget']={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
  ledger['epoch36_actual_execution']=actual;ledger['epoch36_cumulative_execution']=counts
  ledger['epoch36_counting_scope']='Preserve all historical fields. Explicit prior corpus32attempts/30complete and boundednative36 plus actual single engineering corpus/worker reservations. Legacy6 dedicated native qualification process slots preserved. Observed new xxlarge reader initialization attempts are separately scoped, not another native process slot. Official benchmark HTTP888 prior success plus3 actual E36 successful GETs equals891success/2fail. New model metadata/acquisition requests are separate, not benchmark HTTP. Missing/partial internal operations UNKNOWN; uncertain reservations burned, never replayed.'
  ledger['epoch36_data_roles']=copy.deepcopy(pc['epoch36_data_roles'])
  ledger['epoch36_decision']={**schema.FLAGS,'epoch':36,'status':status,'diagnostic_qualified':False,'engineering_passed':passed,'readiness_qualified':passed,'results':resultref,'reason':reason}
  if passed:ledger['epoch36_engineering_qualification']={**schema.FLAGS,'epoch':36,'status':status,'engineering_passed':True,'benchmark_accuracy':None,'results':resultref,'reason':reason}
  else:ledger['rejections'].append({'epoch':36,'status':status,'reason':reason,'results':resultref})
  write_new(study/'REJECTION_LEDGER.json',ledger)
  return{'status':status,'results':resultref,'actual_execution':actual,'cumulative_execution':counts,'scorer_fields_preserved':True}
 results=c.parse(study/'RESULTS.json');report=c.parse(report_path)
 if report.get('epoch')!=36 or report.get('kind')!=schema.KIND or report.get('checks_passed')is not True:raise ValueError('Independent final binding failed')
 for key in('diagnostic_qualified','engineering_passed','readiness_qualified'):
  if not receipts.same_fact(report.get(key),results[key]):raise ValueError('Independent verdict differs')
 expected={'raw':eng['raw'],'execution':eng['execution'],'results':ref(study/'RESULTS.json'),'pretrained_model_source':c.ref(root,schema.MODEL_SOURCE_PATH),'baseline_model_source':c.ref(root,schema.BASELINE_MODEL_SOURCE_PATH),'model_profiles':c.ref(root,schema.MODEL_PROFILES_PATH)}
 for key,value in expected.items():
  if not receipts.same_fact(report.get('evidence',{}).get(key),value):raise ValueError('Final binding reference differs: '+key)
 source={'schema_version':1,'epoch':36,'kind':schema.KIND,'source_checkpoint':c.BASE_COMMIT,'plan':planref,'source_freeze':plan['source_freeze'],'files':collect(),'rule':'Reviewed public artifacts before nonrecursive source/epoch manifest creation. Final checkpoint covers both. No current benchmark role exposed or confirmation consumed.'}
 write_new(study/'SOURCE_MANIFEST.json',source)
 manifest={'schema_version':1,'epoch':36,'kind':schema.KIND,**schema.FLAGS,'status':results['status'],'diagnostic_qualified':False,'engineering_passed':results['engineering_passed'],'readiness_qualified':results['readiness_qualified'],'benchmark_accuracy':None,'source_checkpoint':c.BASE_COMMIT,'confirmation':[],'used_confirmation_identities':[],'data_roles':schema.ROLES,'all_slots_closed':True,'phase_remaining':{'train':0,'dev':0,'calibration':0,'confirmation':0,'engineering':0},'plan':planref,'source_freeze':plan['source_freeze'],'pretrained_model_source':plan['pretrained_model_source'],'baseline_model_source':plan['baseline_model_source'],'model_profiles':plan['model_profiles'],'results':ref(study/'RESULTS.json'),'independent_report':ref(report_path),'source_manifest':ref(study/'SOURCE_MANIFEST.json'),'rejection_ledger':ref(study/'REJECTION_LEDGER.json'),'actual_execution':actual,'cumulative_execution':counts,'files':collect(),'limitations':results['scope'],'goal_verified':False}
 write_new(study/'EPOCH_MANIFEST.json',manifest)
 return{'manifest':ref(study/'EPOCH_MANIFEST.json'),'status':manifest['status'],'all_slots_closed':True,'models_native_label_joins_Git_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--mode',choices=('results','manifest'),required=True);cli.add_argument('--scope',type=Path,default=DEFAULT_SCOPE)
 for name in('priorcontrols','replay','acceptance'):cli.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(run(cli.parse_args()),sort_keys=True))
