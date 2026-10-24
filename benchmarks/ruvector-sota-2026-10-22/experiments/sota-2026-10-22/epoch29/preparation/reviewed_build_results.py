"""Root-run exact E29 replay publication, with no inference or label joins.

The frozen independent scorer evaluates/binds evidence separately. This helper
copies its factual fields and builds append-only reports/ledger/manifest.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,os,re
from pathlib import Path

P='experiments/sota-2026-10-22/'
SOURCE='07a2cbe78fdee78a8c9bca2aeb64bc9746481ba0'
KIND='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch29-734329c6e9e6')
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_rank':None,'official_SOTA_verified':False}
SCORER_SHA='27d009fa857fa7f0d1f6ff74d5427c9f89aa6aecb96592f02dd65da1d60415dc'

def selected_replay_raw(root,rawref,execution,qualified,common,publication):
 if rawref is None:return None
 publication.checked_ref(root,rawref)
 try:return common.parse(root/rawref['path'])
 except (ValueError,UnicodeError):
  if not (qualified is False and execution.get('status')=='WORKER_FAILED_OR_TIMEOUT'
      and execution.get('raw_operation_counters_source')=='UNKNOWN'
      and rawref['path']==P+'epoch29/runs/engineering/raw.json'
      and execution.get('raw_bytes')==rawref['bytes']
      and execution.get('raw_sha256')==rawref['sha256']):raise
  # Retain the original malformed file/reference in the replay. Its operation
  # counts remain UNKNOWN; the frozen scorer and stager enforce partial
  # precedence and prevent a valid raw from being relabelled malformed.
  return None

def write_new(path,value):
 with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def run(args):
 scope=args.scope.absolute();root=scope/'project';study=root/(P+'epoch29');audit=root/(P+'audit/epoch29/identity')
 if scope!=SCOPE or root!=root.resolve():raise ValueError('Exact owned E29 root required')
 sys.path.insert(0,str(study/'publication'))
 import publication_common_v1 as c
 import stage_publication_v1 as p
 c.live_owner(scope)
 plan=c.parse(study/'plan.json');admission=c.parse(study/'NATIVE_ADMISSION.json')
 if plan.get('epoch')!=29 or plan.get('kind')!=KIND or plan.get('source_checkpoint')!=SOURCE:raise ValueError('Wrong frozen source plan')
 if admission.get('plan_sha256')!=c.sha(c.content(study/'plan.json')) or admission.get('source_freeze_sha256')!=plan['source_freeze_sha256'] or not re.fullmatch('[0-9a-f]{40}',admission.get('published_source_commit','')):raise ValueError('Actual source admission no longer binds frozen plan')
 pins={row['path']:row for row in plan['pins']}
 if len(pins)!=len(plan['pins']):raise ValueError('Duplicate frozen source pin')
 for path,row in pins.items():
  if c.ref(root,path)!=row:raise ValueError('Frozen source changed: '+path)
 ownsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not any(row['sha256']==ownsha and row['path'].endswith('reviewed_build_results.py') for row in pins.values()):raise ValueError('Executed results helper was not frozen in source')
 scorer=P+'audit/epoch29/identity/score_identity.py'
 if pins.get(scorer,{}).get('sha256')!=SCORER_SHA:raise ValueError('Final frozen scorer revision mismatch')
 def ref(path):return c.ref(root,Path(path).relative_to(root).as_posix())
 def collect():
  return [dict(path=name,bytes=len(body),sha256=c.sha(body)) for name,body in sorted(c.walk_current(root).items())]
 replay_path=args.replay or audit/'qualification-replay.json'
 report_path=args.acceptance or audit/'independent-acceptance.json'
 if not replay_path.is_relative_to(root) or not report_path.is_relative_to(root):raise ValueError('Copy reviewed replay/acceptance into current public audit root before canonical publication')
 if args.mode=='results':
  replay=c.parse(replay_path);execution=c.parse(study/'execution.json')
  if replay.get('epoch')!=29 or replay.get('kind')!=KIND or type(replay.get('engineering_qualified')) is not bool:raise ValueError('Wrong independent replay scope/verdict')
  qualified=replay['engineering_qualified'];status=replay.get('status')
  if status not in p.OUTCOME_STATUSES or ((status=='DATA_ADMISSION_HOLD_WITH_ENGINEERING_QUALIFIED') is not qualified):raise ValueError('Replay status/verdict contradiction')
  rawref=replay['evidence']['raw'];raw=selected_replay_raw(root,rawref,execution,qualified,c,p)
  actual=p.derive_actual(raw,execution)
  if not p.same_fact(actual,replay.get('actual_execution')):raise ValueError('Replay changed captured actual effort/resources')
  if replay.get('held_parameter_adaptation')!=p.HOLD_REF:raise ValueError('Original normalized-alias HOLD changed')
  reason=('Actual native RuVector document identity qualification passed its frozen source-hash/ANN/brute/coverage gates. It prevents invalid freshness claims; it establishes no semantic benchmark or trained-model improvement. Original LoRA allocation remains on HOLD with all16 IDs retired.' if qualified else 'Frozen native identity engineering acceptance failed; exact captured outputs, independent failures and any incomplete/unknown counters remain. Retrieval misses remain UNRESOLVED. Original LoRA allocation remains on HOLD with all16 IDs retired; no redraw or retry.')
  # Preserve the scorer fields wholesale, including absent/unknown fields and
  # all original failures. Additional prose never replaces its measurements.
  results=copy.deepcopy(replay)
  results.update(**FLAGS,source_checkpoint=SOURCE,published_frozen_source_commit=admission['published_source_commit'],
   confirmation=[],used_confirmation_identities=[],data_roles=copy.deepcopy(p.EMPTY_ROLES),
   reason=reason,actual_execution=actual,qualification_replay=ref(replay_path),
   independent_functional_evaluation_integrity=replay['checks_passed'],all_slots_closed=True,
   scope='Source-licensed document identity engineering over frozen old-exposed261 corpus plus known retired alias548. Full normalized text SHA is authoritative. Native/brute BGE top16 results and exact-hash positives are engineering measures; misses are UNRESOLVED, never CLEAN. No semantic question/NLI/label/calibration/proper-score/benchmark gain claim.',
   future_confirmation='HOLD. No fresh confirmation role or publisher submission activated. Future data selection must freeze normalized alias-class eligibility before allocating new roles; this held allocation cannot be redrawn or repaired.')
  write_new(study/'RESULTS.json',results)
  source_cont=c.parse(scope/'controls-source/CONTINUATION.json')
  oldref=c.parse(scope/'kit/CONTINUATION.json')['rejection_ledger'];ledger=copy.deepcopy(c.parse(root/oldref['path']));rr=ref(study/'RESULTS.json')
  ledger['epoch29_budget']={'worker_attempts_used':actual['worker_attempts'],'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
  ledger['epoch29_data_admission']=copy.deepcopy(source_cont['epoch29_data_admission'])
  ledger['epoch29_actual_execution']=actual
  ledger['epoch29_counting_scope']='One bounded native engineering reservation if worker_attempts1; zero benchmark corpus batches. The reserved count burns even if no verified worker returned. No labels/fit/NLI/paid/GPU/CONF. Original TRAIN/DEV proposal remains HOLD and all16 IDs retired. Opaque or checkpoint-tail backend counts remain UNKNOWN.'
  ledger['epoch29_decision']={'epoch':29,'status':status,'engineering_qualified':qualified,**FLAGS,'results':rr,'reason':reason}
  if qualified:ledger['epoch29_qualification']={'epoch':29,'status':status,'engineering_qualified':True,**FLAGS,'results':rr,'reason':reason}
  else:ledger['rejections'].append({'epoch':29,'status':status,'reason':reason,'results':rr})
  write_new(study/'REJECTION_LEDGER.json',ledger)
  return {'status':status,'results':rr,'actual_execution':actual,'copied_scorer_fields_verbatim':True}
 results=c.parse(study/'RESULTS.json');report=c.parse(report_path)
 if report.get('checks_passed') is not True or report.get('epoch')!=29 or report.get('kind')!=KIND or report.get('engineering_qualified') is not results['engineering_qualified']:raise ValueError('Exact independent final binding required')
 if report['evidence']['results']!=ref(study/'RESULTS.json') or report['evidence']['execution']!=ref(study/'execution.json'):raise ValueError('Bound results/execution identity differs')
 for field,pin in report['evidence'].items():
  if pin is not None:p.checked_ref(root,pin)
 source={'schema_version':1,'epoch':29,'kind':KIND,'source_checkpoint':SOURCE,'published_frozen_source_commit':results['published_frozen_source_commit'],'plan':ref(study/'plan.json'),'source_freeze':ref(study/'source-freeze.json'),'held_parameter_adaptation':p.HOLD_REF,'files':collect(),'scope':'Current reviewed public E29 files except this source manifest and epoch manifest, avoiding self-recursion; final checkpoint covers both.'}
 write_new(study/'SOURCE_MANIFEST.json',source)
 manifest={'schema_version':1,'epoch':29,'kind':KIND,'status':results['status'],'engineering_qualified':results['engineering_qualified'],**FLAGS,'source_checkpoint':SOURCE,'published_frozen_source_commit':results['published_frozen_source_commit'],'confirmation':[],'used_confirmation_identities':[],'data_roles':copy.deepcopy(p.EMPTY_ROLES),'held_parameter_adaptation':p.HOLD_REF,'all_slots_closed':True,'plan':ref(study/'plan.json'),'source_freeze':ref(study/'source-freeze.json'),'results':ref(study/'RESULTS.json'),'independent_report':ref(report_path),'source_manifest':ref(study/'SOURCE_MANIFEST.json'),'rejection_ledger':ref(study/'REJECTION_LEDGER.json'),'actual_execution':results['actual_execution'],'files':collect(),'limitations':results['scope'],'goal_verified':False}
 write_new(study/'EPOCH_MANIFEST.json',manifest)
 priority='Preserve submitted Native104/RRF10 and every prior rejection. E29 original parameter-adaptation allocation is permanently on normalized-alias HOLD:548 aliases exposed515; all16 fixed IDs retired, no redraw/fit/DEV/CONF. Native document identity '+('qualified' if results['engineering_qualified'] else 'failed')+' only under this frozen engineering protocol; full normalized-source SHA remains authoritative and retrieval misses remain UNRESOLVED. Future independently frozen roles require precomputed normalized alias-class eligibility before allocation. Strong legal typed-decision training/NLI and matched same-model native evidence selection remain the benchmark direction, with genuine unused confirmation and actual full champion comparator/protocol before any promotion. Jev original115 was queue position, never rank; no official RuVector score/eligibility or ClaimBench full data/scorer/licence/access verified. Zero new paid/GPU cap persists.'
 updates={'rejection_ledger':ref(study/'REJECTION_LEDGER.json'),'next_research_priority':priority,'epoch29_data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[],'used_confirmation_identities':[],'engineering_ids':plan['engineering_ids'],'benchmark_generalization':False,'original_parameter_adaptation_HOLD':p.HOLD_REF}}
 write_new(scope/'continuation-updates-final.json',updates)
 return {'status':results['status'],'manifest':ref(study/'EPOCH_MANIFEST.json'),'source_manifest':ref(study/'SOURCE_MANIFEST.json'),'public_files':len(collect()),'all_slots_closed':True}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('results','final'));parser.add_argument('--scope',type=Path,default=SCOPE);parser.add_argument('--replay',type=Path);parser.add_argument('--acceptance',type=Path);args=parser.parse_args();print(json.dumps(run(args),sort_keys=True))
