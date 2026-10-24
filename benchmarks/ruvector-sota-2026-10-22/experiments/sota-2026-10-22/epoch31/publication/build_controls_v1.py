"""Build separate E31 controls; no model/native/Git actions."""
import sys
sys.dont_write_bytecode=True
import argparse,copy,json
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from stage_publication_v1 import controls_at,data_role_record,retirement_record,MUTABLE,FINAL_MUTABLE,preserve_history
from phase_receipts_v1 import cumulative_counts,require_final_physical_closure

def build(args):
 root,kit,prior=map(directory,(args.project,args.kit,args.priorcontrols));live_owner(root.parent)
 output=new_output(args.out,(root,kit,prior));oldcp=parse(kit/'CHECKPOINT_MANIFEST.json')
 require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256,'BASE CP hash changed');check_inherited_checkpoint(oldcp);check_history(root,oldcp)
 before=controls_at(prior,kit);pcp=loads(before['CHECKPOINT_MANIFEST.json']);cont=loads(before['CONTINUATION.json']);active=loads(before['ACTIVE_RUN.json'])
 require(active.get('run_id')==OWNER_RUN_ID and cont.get('active_run')==dict(active,path='ACTIVE_RUN.json'),'Exact owned prior controls required')
 current=walk_current(root);rows=cp_rows(pcp)
 for path,body in current.items():
  row={'path':path,'bytes':len(body),'sha256':sha(body)}
  if path in rows:require(rows[path]==row,'Previously published file changed: '+path)
  else:rows[path]=row
 oldpaths={r['path'] for r in pcp['project_files']};cp=copy.deepcopy(pcp);cp['project_files']+=[rows[p] for p in sorted(set(rows)-oldpaths)]
 frozen={'plan':ref(root,PLAN_PATH),'source_freeze':ref(root,FREEZE_PATH)}
 if args.phase=='source':
  require(pcp==oldcp and active.get('state')=='EPOCH31_PLANNING_LEASE','SOURCE must follow original planning checkpoint')
  cp['epoch31_source']={'kind':KIND,'source_checkpoint':BASE_COMMIT,'frozen_source_parent':args.parent,**frozen}
  active.update(state='EPOCH31_SOURCE_FROZEN_DEV_PENDING_ADMISSION',work_active=True,conditional_train_allowed=0,conditional_dev_allowed=1)
  cont['epoch31_frozen_study']=frozen;cont['epoch31_data_roles']=data_role_record();cont['epoch31_archived_model_seal']=ref(root,ARCHIVED_SEAL_PATH)
  exposed=copy.deepcopy(cont.get('exposed_development_sets',[]));require(isinstance(exposed,list) and not any(isinstance(r,dict) and r.get('epoch')==31 for r in exposed),'Current DEV retirement already recorded');exposed.append(retirement_record());cont['exposed_development_sets']=exposed
 else:
  require(active.get('state') == 'EPOCH31_SOURCE_FROZEN_DEV_PENDING_ADMISSION' and cont.get('epoch31_frozen_study')==frozen,'FINAL must close exact SOURCE')
  m=parse(root/(E+'EPOCH_MANIFEST.json'));actual=m['actual_execution'];require_final_physical_closure(actual)
  active.update(state='EPOCH31_CLOSED',work_active=False,conditional_train_allowed=0,conditional_dev_allowed=0,all_unspent_epoch31_slots_permanently_closed=True,owned_native_groups_closed=actual['owned_live_processes_closed'])
  cont['epoch31_final']={**FLAGS,'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':ref(root,E+'RESULTS.json'),'status':m['status'],'diagnostic_qualified':m['diagnostic_qualified'],'archived_training_integrity_passed':m['archived_training_integrity_passed'],'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True}
  observed=copy.deepcopy(cont.get('execution_observed',{}));require('epoch31_actual_execution' not in observed,'Current effort already recorded')
  counts=cumulative_counts(actual)
  observed.update(epoch31_actual_execution=actual,epoch31_cumulative_corpus_attempts=counts['corpus_attempts'],epoch31_cumulative_completed_corpus_batches=counts['completed_corpus_batches'],epoch31_cumulative_bounded_native_process_attempts=counts['bounded_native_process_attempts'],epoch31_counting_scope='All historical flat fields remain unchanged; explicit prior E30 corpus25attempts/23complete plus current DEV reservations/completions. Boundednative prior31 plus reservations; qualifications6 and HTTP885success/2fail unchanged.')
  cont['execution_observed']=observed
  ledger=parse(root/(E+'REJECTION_LEDGER.json'));cont['rejection_ledger']=ref(root,E+'REJECTION_LEDGER.json')
  budget=copy.deepcopy(cont.get('cumulative_budget_ledger',{}));require('epoch31_budget' not in budget,'Current budget already recorded');budget['epoch31_budget']=ledger['epoch31_budget'];cont['cumulative_budget_ledger']=budget
  epochs=copy.deepcopy(cont.get('epochs',[]));require(not any(isinstance(r,dict) and r.get('epoch')==31 for r in epochs),'Current epoch already recorded');epochs.append({**FLAGS,'epoch':31,'kind':KIND,'status':m['status'],'manifest':ref(root,E+'EPOCH_MANIFEST.json'),'results':ref(root,E+'RESULTS.json'),'diagnostic_qualified':m['diagnostic_qualified'],'archived_training_integrity_passed':m['archived_training_integrity_passed']});cont['epochs']=epochs
 active.update(checkpoint_parent=args.parent,experiments_active=False,native_allowed=0,confirmation_allowed=0,conditional_confirmation_allowed=0,OS_lock_held=True,OS_lock_release_pending=True,
  instruction='Only current DEV after independent actual SOURCE readback and archived artifact/source admission. One nonretryable CPU2/600s phase total; zero current fits/TRAIN. No CONF/full104/benchmark acceptance/promotion/submission. FINAL closes every slot.')
 cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['checkpoint_manifest_sha256']=sha(encoded(cp,pretty=True));cont['prior_published_base_commit']=args.parent
 if args.continuation_updates:
  updates=parse(args.continuation_updates);require(isinstance(updates,dict) and all(k in FINAL_MUTABLE or k.startswith('epoch31_') for k in updates),'Unreviewed update')
  require(not set(updates)&{'active_run','checkpoint_manifest_sha256','prior_published_base_commit','epoch31_planning','epoch31_frozen_study','epoch31_data_roles'},'Protected continuation update');cont.update(updates)
 preserve_history(loads(before['CONTINUATION.json']),cont,FINAL_MUTABLE if args.phase=='final' else MUTABLE)
 output.mkdir(mode=0o700)
 for name,value in [('CHECKPOINT_MANIFEST.json',cp),('CONTINUATION.json',cont),('ACTIVE_RUN.json',active)]:write(output/name,encoded(value,pretty=True))
 if args.reviewed_files:
  dest=new_output(args.reviewed_files,(root,kit,prior,output));write(dest,encoded({'files':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in sorted(current.items())]},pretty=True))
 return {'phase':args.phase,'parent':args.parent,'controls':str(output),'CP_rows':len(rows),'CP_sha256':cont['checkpoint_manifest_sha256'],'public_files':len(current),'native_model_Git_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--phase',choices=('source','final'),required=True)
 for name in ('project','kit','priorcontrols','out'):cli.add_argument('--'+name,type=Path,required=True)
 cli.add_argument('--parent',required=True);cli.add_argument('--continuation-updates',type=Path);cli.add_argument('--reviewed-files',type=Path);print(json.dumps(build(cli.parse_args()),sort_keys=True))
