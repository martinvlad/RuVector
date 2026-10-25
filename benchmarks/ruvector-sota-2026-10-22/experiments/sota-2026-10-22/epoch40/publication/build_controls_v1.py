"""Separate E40 controls, append-only history; no cases/science/Git."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json
import publication_common_v1 as c
import stage_publication_v1 as stage
from phase_contract_v1 import *

def build(args):
 root,kit,prior=map(c.directory,(args.project,args.kit,args.priorcontrols));c.live_owner(root.parent);output=c.new_output(args.out,(root,kit,prior))
 old=c.parse(kit/'CHECKPOINT_MANIFEST.json');c.require(c.sha(c.content(kit/'CHECKPOINT_MANIFEST.json'))==c.BASE_CP_SHA256,'Actual base CP changed');c.check_inherited_checkpoint(old);c.check_history(root,old)
 before=stage.controls_at(prior,kit);cp=c.loads(before['CHECKPOINT_MANIFEST.json']);cont=c.loads(before['CONTINUATION.json']);active=c.loads(before['ACTIVE_RUN.json'])
 c.require(active.get('run_id')==c.OWNER_RUN_ID and cont.get('active_run')==dict(active,path='ACTIVE_RUN.json'),'Exact owned prior controls')
 plan=c.parse(root/PLAN_PATH);freeze={'plan':c.ref(root,PLAN_PATH),'source_freeze':c.ref(root,FREEZE_PATH)};current=c.walk_current(root);rows=c.cp_rows(cp);new=copy.deepcopy(cp)
 for name,body in sorted(current.items()):
  row={'path':name,'bytes':len(body),'sha256':c.sha(body)}
  if name in rows:c.require(rows[name]==row,'Published source changed: '+name)
  else:new['project_files'].append(row);rows[name]=row
 if args.phase=='source':
  c.require(cp==old and active.get('state')=='EPOCH40_PLANNING_LEASE','SOURCE extends exact planning checkpoint')
  new['epoch40_source']={'kind':KIND,'phase':PHASE,'source_checkpoint':c.BASE_COMMIT,'parent':args.parent,**freeze}
  active.update(state='EPOCH40_SOURCE_FROZEN_DEV_PENDING_ADMISSION',work_active=True,conditional_dev_allowed=1)
  cont['epoch40_frozen_study']=freeze;cont['epoch40_data_roles']={'roles':plan['data_roles'],'scope':'Twelve real ContractNLI identities exposed DEV forever, separate from old423/325DEV/74unused/24protected and all prior authored engineering cases. No CONF.'}
 else:
  c.require(active.get('state')=='EPOCH40_SOURCE_FROZEN_DEV_PENDING_ADMISSION'and cont.get('epoch40_frozen_study')==freeze,'FINAL closes exact SOURCE')
  manifest=c.parse(root/(E+'EPOCH_MANIFEST.json'));c.require(manifest.get('all_slots_closed')is True and manifest.get('phase_remaining')==REMAINING,'Every remaining slot closed')
  counts=manifest['cumulative_execution'];c.require(counts['corpus_attempts']is None and counts['completed_corpus_batches']is None,'Historical E37 actual cumulative tail stays UNKNOWN')
  active.update(state='EPOCH40_CLOSED',work_active=False,conditional_dev_allowed=0,all_unspent_epoch40_slots_permanently_closed=True)
  summary={'epoch':40,'kind':KIND,'phase':PHASE,'status':manifest['status'],'dev_passed':manifest['dev_passed'],'manifest':c.ref(root,E+'EPOCH_MANIFEST.json'),'results':manifest['results'],'all_slots_closed':True,'goal_met':False,**FLAGS}
  c.require('epoch40_final'not in cont,'No duplicate FINAL');cont['epoch40_final']=summary;cont['epochs']=copy.deepcopy(cont.get('epochs',[]))+[summary]
  observed=copy.deepcopy(cont.get('execution_observed',{}));c.require('epoch40_actual_execution'not in observed,'No duplicate execution');observed.update(epoch40_actual_execution=manifest['actual_execution'],epoch40_cumulative_execution=counts);cont['execution_observed']=observed
  ledger=c.parse(root/(E+'REJECTION_LEDGER.json'));cont['rejection_ledger']=c.ref(root,E+'REJECTION_LEDGER.json');budgets=copy.deepcopy(cont.get('cumulative_budget_ledger',{}));budgets['epoch40_budget']=ledger['epoch40_budget'];cont['cumulative_budget_ledger']=budgets
  if args.updates:
   updates=c.parse(args.updates);c.require(isinstance(updates,dict)and set(updates)<=set(('next_research_priority','latest_learning')),'Only reviewed final research direction update');cont.update(updates)
 active.update(checkpoint_parent=args.parent,experiments_active=False,native_allowed=0,conditional_train_allowed=0,conditional_calibration_allowed=0,conditional_engineering_allowed=0,confirmation_allowed=0,conditional_confirmation_allowed=0,OS_lock_held=True,OS_lock_release_pending=True,instruction='DEV-only real ContractNLI pilot. SOURCE conditional work only after actual independent readback/admission. One48readout/12query corpus CPU2/600total, no TRAIN/calibCONF/paidGPU/retry. FINAL closes every slot; no fullbenchmark placement/promotion.')
 cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['checkpoint_manifest_sha256']=c.sha(c.encoded(new,pretty=True));cont['prior_published_base_commit']=args.parent
 stage.preserve_history(c.loads(before['CONTINUATION.json']),cont,stage.FINAL_MUTABLE if args.phase=='final'else stage.MUTABLE)
 output.mkdir(mode=0o700)
 for name,value in [('CHECKPOINT_MANIFEST.json',new),('CONTINUATION.json',cont),('ACTIVE_RUN.json',active)]:c.write(output/name,c.encoded(value,pretty=True))
 if args.reviewed_files:c.write(c.new_output(args.reviewed_files,(root,kit,prior,output)),c.encoded({'files':[{'path':name,'bytes':len(body),'sha256':c.sha(body)}for name,body in sorted(current.items())]},pretty=True))
 return {'phase':args.phase,'controls':str(output),'CP_rows':len(rows),'CP_sha256':cont['checkpoint_manifest_sha256'],'public_files':len(current),'science_Git_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('source','final'),required=True)
 for name in ('project','kit','priorcontrols','out'):parser.add_argument('--'+name,type=Path,required=True)
 parser.add_argument('--parent',required=True);parser.add_argument('--updates',type=Path);parser.add_argument('--reviewed-files',type=Path)
 print(json.dumps(build(parser.parse_args()),sort_keys=True))
