"""Build new E28 control files outside the immutable projected source tree.

This convenience CLI grants no execution permission and publishes nothing.
The independently reviewed stager remains the authoritative control checker.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,json
from pathlib import Path
from publication_common_v1 import (P,BASE_COMMIT,BASE_CP_SHA256,OWNER_RUN_ID,
 check_history,check_inherited_checkpoint,content,cp_rows,directory,encoded,
 live_owner,loads,new_output,parse,ref,require,sha,walk_current,write)
from stage_publication_v1 import (KIND,E,PLAN_PATH,FREEZE_PATH,FINAL_MUTABLE,FORBIDDEN_RESULT_FLAGS,
 SOURCE_MUTABLE,controls_at,preserve_history,checked_review)

def build(args):
 project,kit,prior=map(directory,(args.project,args.kit,args.priorcontrols));owner=live_owner(project.parent)
 out=new_output(args.out,(project,kit,prior))
 oldcp=parse(kit/'CHECKPOINT_MANIFEST.json');require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256,'Original CP hash changed');check_inherited_checkpoint(oldcp);check_history(project,oldcp)
 beforeb=controls_at(prior,kit);beforecp=loads(beforeb['CHECKPOINT_MANIFEST.json']);cont=loads(beforeb['CONTINUATION.json']);active=loads(beforeb['ACTIVE_RUN.json'])
 require(active.get('run_id')==OWNER_RUN_ID and cont.get('active_run')==dict(active,path='ACTIVE_RUN.json'),'Prior owned controls required')
 current=walk_current(project);rows=cp_rows(beforecp)
 for path,body in current.items():
  row={'path':path,'bytes':len(body),'sha256':sha(body)}
  if path in rows:require(rows[path]==row,'Previously published source changed: '+path)
  else:rows[path]=row
 previous_paths={r['path'] for r in beforecp['project_files']}
 cp=copy.deepcopy(beforecp);cp['project_files']=copy.deepcopy(beforecp['project_files'])+[rows[p] for p in sorted(set(rows)-previous_paths)]
 frozen={'plan':ref(project,PLAN_PATH),'source_freeze':ref(project,FREEZE_PATH)}
 if args.phase=='source':
  require(beforecp==oldcp and active.get('state')=='EPOCH28_PLANNING_LEASE','Source must follow original planning lease')
  cp['epoch28_source']={'kind':KIND,'source_checkpoint':BASE_COMMIT,'frozen_source_parent':args.parent,'new_source_files':len(current),**frozen}
  active.update(state='EPOCH28_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',checkpoint_parent=args.parent,work_active=True,experiments_active=False,native_allowed=0,native_allowed_after_exact_remote_readback=1,conditional_confirmation_allowed=0,confirmation_allowed=0,instruction='One nonretryable actual full-input Native104 engineering qualification after exact independent actual remote source readback and local admission. CPU2 <=600 seconds including initialization and cleanup; no benchmark DEV/CONF/train/calibration/paid/GPU or promotion/submission. Authored cases are engineering evidence only.')
  cont['epoch28_frozen_study']=frozen
 else:
  require(active.get('state')=='EPOCH28_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION' and cont.get('epoch28_frozen_study')==frozen,'Final must close exact published frozen source')
  manifest=parse(project/(E+'EPOCH_MANIFEST.json'))
  active.update(state='EPOCH28_CLOSED',checkpoint_parent=args.parent,work_active=False,experiments_active=False,native_allowed=0,native_allowed_after_exact_remote_readback=0,conditional_confirmation_allowed=0,confirmation_allowed=0,all_unspent_epoch28_slots_permanently_closed=True,owned_native_groups_closed=manifest.get('actual_execution',{}).get('owned_live_processes_closed',False),instruction='Closed E28 engineering qualification. All slots permanently closed. Preserve Native104 and exact acceptance/rejection; release physical lock only after independent final actual remote readback.')
  false_flags={key:False for key in FORBIDDEN_RESULT_FLAGS}
  cont['epoch28_final']={**false_flags,'manifest':ref(project,E+'EPOCH_MANIFEST.json'),'results':ref(project,E+'RESULTS.json'),'status':manifest.get('status'),'engineering_qualified':manifest.get('engineering_qualified'),'official_rank':None,'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
  actual=manifest.get('actual_execution',{});attempts=actual.get('worker_attempts');require(type(attempts) is int and 0<=attempts<=1,'Actual worker attempt count required')
  observed=copy.deepcopy(cont.get('execution_observed',{}));require('epoch28_actual_execution' not in observed,'E28 already recorded');observed['epoch28_actual_execution']=actual
  for key in ('cumulative_bounded_native_process_attempts_including_qualification','native_qualification_attempts'):
   if key in observed:observed[key]+=attempts
  cont['execution_observed']=observed
  ledgerpath=E+'REJECTION_LEDGER.json';require(ledgerpath in current,'Current E28 rejection/qualification ledger required');ledger=parse(project/ledgerpath)
  cont['rejection_ledger']=ref(project,ledgerpath)
  budget=copy.deepcopy(cont.get('cumulative_budget_ledger',{}));require('epoch28_budget' not in budget,'E28 budget already recorded');budget['epoch28_budget']=copy.deepcopy(ledger.get('epoch28_budget'));cont['cumulative_budget_ledger']=budget
  epochs=copy.deepcopy(cont.get('epochs',[]));require(not any(e.get('epoch')==28 for e in epochs),'E28 epoch already recorded');epochs.append({**false_flags,'epoch':28,'kind':KIND,'status':manifest.get('status'),'manifest':ref(project,E+'EPOCH_MANIFEST.json'),'results':ref(project,E+'RESULTS.json'),'engineering_qualified':manifest.get('engineering_qualified'),'official_rank':None});cont['epochs']=epochs
 cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['checkpoint_manifest_sha256']=sha(encoded(cp,pretty=True));cont['prior_published_base_commit']=args.parent
 refresh=P+'legal-transfer/epoch28/benchmark-refresh.json'
 if refresh in current:
  rr=ref(project,refresh)
  if args.phase=='source':cont['epoch28_official_refresh']=rr;cont['benchmark_refresh']=rr
  else:require(cont.get('epoch28_official_refresh')==rr,'Published official refresh changed')
 if args.continuation_updates:
  updates=parse(args.continuation_updates);require(isinstance(updates,dict),'Continuation updates object required')
  allowed=FINAL_MUTABLE if args.phase=='final' else SOURCE_MUTABLE
  require(all((k in allowed or k.startswith('epoch28_')) and k not in {'active_run','checkpoint_manifest_sha256','prior_published_base_commit','epoch28_frozen_study','epoch28_planning'} for k in updates),'Unreviewed/protected update key')
  cont.update(updates)
 preserve_history(loads(beforeb['CONTINUATION.json']),cont,FINAL_MUTABLE if args.phase=='final' else SOURCE_MUTABLE)
 out.mkdir(mode=0o700)
 for name,value in [('CHECKPOINT_MANIFEST.json',cp),('CONTINUATION.json',cont),('ACTIVE_RUN.json',active)]:write(out/name,encoded(value,pretty=True))
 if args.reviewed_files:
  dest=new_output(args.reviewed_files,(project,kit,prior,out));write(dest,encoded({'files':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in sorted(current.items())]},pretty=True))
 return {'phase':args.phase,'controls':str(out),'parent':args.parent,'new_CP_rows':len(rows),'public_files':len(current),'CP_sha256':cont['checkpoint_manifest_sha256'],'native_or_model_calls':0,'Git_mutations':0}

def main():
 cli=argparse.ArgumentParser(description=__doc__)
 cli.add_argument('--phase',choices=('source','final'),required=True)
 for name in ('project','kit','priorcontrols','out'):cli.add_argument('--'+name,type=Path,required=True)
 cli.add_argument('--parent',required=True);cli.add_argument('--continuation-updates',type=Path);cli.add_argument('--reviewed-files',type=Path)
 print(json.dumps(build(cli.parse_args()),sort_keys=True))

if __name__=='__main__':main()
