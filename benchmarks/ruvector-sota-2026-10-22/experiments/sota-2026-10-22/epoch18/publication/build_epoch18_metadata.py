"""Derived controls and public manifest staging; never reads case labels."""
from pathlib import Path
import argparse,hashlib,json,os
from datetime import datetime,timezone
P=Path(__file__).resolve().parent; ROOT=P/'project'; S=ROOT/'experiments/sota-2026-10-22'; E=S/'epoch18'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def allfiles():
    out=[]
    for rel in ['candidate/epoch18','controller/epoch18','legal-transfer/epoch18','audit/epoch18','epoch18']:
        for p in sorted((S/rel).rglob('*')):
            if '__pycache__' in p.parts or 'assets' in p.parts:continue
            assert not any(x.is_symlink()for x in [p,*p.parents])
            if p.is_file():out.append(p)
    return out
def verify_snapshot():
    proof=read(E/'candidate-source-freeze.json')
    for row in proof['files']:
        f=ROOT/row['path']
        assert not any(x.is_symlink()for x in [f,*f.parents])
        assert ident(f)==row,row['path']
    return len(proof['files'])
def prenative():
    assert not (E/'SOURCE_MANIFEST.pre-native.json').exists()
    plan=read(E/'plan.json'); proof=read(S/'audit/epoch18/premeasurement-plan-independent-v1.json')
    assert proof['checks_passed']is True
    assert proof['plan_sha256']==sha(E/'plan.json'),'Independent review must bind actual immutable final plan'
    verify_snapshot()
    dev=read(S/'legal-transfer/epoch18/dev-allowlist.json'); conf=read(S/'legal-transfer/epoch18/confirmation-input-allowlist.json')
    pins={row['path']:row['sha256']for row in plan['pins']}
    for filename,value in [('dev-allowlist.json',dev),('confirmation-input-allowlist.json',conf)]:
        file=S/'legal-transfer/epoch18'/filename
        assert pins[str(file.relative_to(ROOT))]==sha(file),'Pinned role allowlist changed'
        assert value['queries']==24 and len(value['records'])==24
        assert len({row['source_group']for row in value['records']})==8

    assert not(S/'legal-transfer/epoch18/confirmation24.jsonl').exists()
    assert not(E/'launch.json').exists()and not(E/'runs').exists()
    used={'schema_version':1,'epoch':18,'source_checkpoint':'0eac156990f5a4ee0084af635eb3089913b437ff',
      'train':[],'calibration':[],
      'development':{'allowlist':ident(S/'legal-transfer/epoch18/dev-allowlist.json'),'records':dev['records'],
        'annotation_choices_projected':24,'exposed_forever_DEV':True,'model_attempted':False},
      'confirmation':{'allowlist':ident(S/'legal-transfer/epoch18/confirmation-input-allowlist.json'),'records':conf['records'],
        'annotation_choices_projected':0,'model_attempted':False,'reuse_exact_unused_epoch16_and17_bank':True,
        'may_only_project_after_frozen_DEV_and_runtime_admission':True},
      'older_confirmation48':{'path':'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl',
        'sha256':'850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50','parsed_or_model_consumed_this_epoch':False},
      'originaltrain_partition_after_DEV_projection':{'exposed':221,'unreserved':178,'reserved':24},
      'old_easy48_Legal96_f018_and_all_prior_exposed_forever_DEV':True,
      'unverified_pretraining_fuzzy_document_overlap':True,'official_score':None,'official_rank':None}
    write(E/'USED_IDENTITIES.pre-native.json',used)
    source={'schema_version':1,'epoch':18,'at':datetime.now(timezone.utc).isoformat(),
      'status':'FROZEN_SOURCE_ROLE_OPERATIONAL_ADMISSION_CAPSULE_NO_INFERENCE_EXECUTED',
      'source_checkpoint':'0eac156990f5a4ee0084af635eb3089913b437ff','planning_lease':'2e6aa4fca5acd9a5149c9f6b37aaf4360c035a45',
      'files':[ident(f)for f in allfiles()],
      'operational_plan':ident(E/'operational-plan.json'),'actual_operational_admission':ident(S/'audit/epoch18/prelabel-operational-admission-v1.json'),
      'final_plan':ident(E/'plan.json'),'premeasurement_independent_review':ident(S/'audit/epoch18/premeasurement-plan-independent-v1.json'),
      'source_freeze':ident(E/'candidate-source-freeze.json'),'source_closure':ident(E/'source-closure-report.json'),
      'native_model_fit_paid_GPU_calls':0,'official_score':None,'official_rank':None}
    write(E/'SOURCE_MANIFEST.pre-native.json',source)
def controls(phase,label=None):
    verify_snapshot()
    dest=P/('capsule-'+(label or phase));dest.mkdir()
    base=read(P/'lease-controls.json');a=base['active'];c=base['continuation'];cp=read(P/'kit/CHECKPOINT_MANIFEST.json')
    if phase=='final':
        a=read(P/'capsule-frozen/ACTIVE_RUN.json');c=read(P/'capsule-frozen/CONTINUATION.json')
    files=allfiles(); old={r['path']:r for r in cp['project_files']}
    for f in files:
        r=ident(f); assert r['path']not in old;old[r['path']]=r
    cp['project_files']=sorted(old.values(),key=lambda r:r['path'])
    cp['epoch18_'+phase]={'source_checkpoint':'0eac156990f5a4ee0084af635eb3089913b437ff','planning_lease':'2e6aa4fca5acd9a5149c9f6b37aaf4360c035a45',
       'project_files':len(cp['project_files']),'scientific_source_immutable_after_freeze':True,
       'model_assets':'Exact immutable17 external registry paths; no private runtime or weights in source checkpoint'}
    write(dest/'CHECKPOINT_MANIFEST.json',cp);c['checkpoint_manifest_sha256']=sha(dest/'CHECKPOINT_MANIFEST.json')
    if phase=='frozen':
        plan=read(E/'plan.json')
        a.update(state='EPOCH18_FROZEN_REVIEWED_PENDING_DURABLE_READBACK',native_allowed=0,
            native_allowed_after_exact_remote_readback=2,
            native_start_condition='Only after exact independently verified frozen commit/control/tree readback, live exclusive lock and full final plan validation; one DEV, conditional CONF; no retries.')
        c['epoch18_frozen_study']={'status':'FROZEN_NOT_EXECUTED','plan':ident(E/'plan.json'),'source_freeze':ident(E/'candidate-source-freeze.json'),
           'source_manifest':ident(E/'SOURCE_MANIFEST.pre-native.json'),'used_identities':ident(E/'USED_IDENTITIES.pre-native.json'),
           'operational_admission':ident(S/'audit/epoch18/prelabel-operational-admission-v1.json'),
           'DEV_choices_projected':24,'CONF_choices_projected':0,'native_model_fit_paid_GPU_calls':0,'confirmation_only_if_DEV_and_runtime_gates_pass':True}
        c['cumulative_budget_ledger'].update(current_epoch_closed=False,scope='EPOCH18_FROZEN_PENDING_READBACK_PRIOR18_NATIVE_ATTEMPTS_CLOSED',
          publication_period_native_calls_allowed=0,new_study_id=plan['study_id'],new_study_attempt_cap=2,
          new_study_attempts_used=0,new_study_attempts_remaining=0,new_study_unspent_phase_slots=2,
          allowed_further_attempts_in_closed_study=0)
        c['cumulative_budget_ledger']['epoch18_active_study']={'study_id':plan['study_id'],'cap':2,'used':0,
          'native_allowed':0,'conditional_native_allowance_after_exact_remote_readback':2,
          'CPU_threads':2,'seconds_each_including_all_initialization_cleanup':600,'paid_GPU_calls':0}
        c['epoch18_data_roles']={'originaltrain_exposed':221,'unreserved':178,'reserved_unused_confirmation':24,'old48_unused':True,'newCONF24_unused':True}
        c['exposed_development_sets'].append('Epoch18 fixedDEV8 projected once after actual full operational PASS and label-free capacity;221exposed/178unreserved/24reserved. These documents are DEV forever even if native fails.')
        c['next_research_priority']='Execute only the exact independently reviewed published18plan after matching remote source/control readback and owned exclusive lock; max2nonretryableCPU2/600s phases,paid0. CONF only frozen DEV+runtime gates.'
    else:
        final=read(E/'EPOCH_MANIFEST.json')
        a.update(state='EPOCH18_CLOSED',experiments_active=False,native_allowed=0,OS_lock_held=True,
                 native_allowed_after_exact_remote_readback=0,native_start_condition='Closed. No further epoch18 attempt permitted.',
                 OS_lock_release_pending_final_remote_readback=True,actual_epoch18_attempts=final['actual_execution']['native_process_attempts'],
                 all_unspent_epoch18_slots_permanently_closed=True)
        c['epochs'].append({'epoch':18,'status':final['status'],'manifest':str((E/'EPOCH_MANIFEST.json').relative_to(ROOT)),
                            'native_attempts':final['actual_execution']['native_process_attempts'],
                            'confirmation_consumed':final['confirmation']['CONF_annotations_projected']>0})
        c['epoch18_final']={'manifest':ident(E/'EPOCH_MANIFEST.json'),'status':final['status'],'accepted':final['accepted'],
           'all_further_attempts_closed':True,'actual_execution':final['actual_execution']}
        c['execution_observed']=final['cumulative_execution'];c['epoch18_data_roles']=final['originaltrain_partition']
        c['rejection_ledger']=str((E/'REJECTION_LEDGER.json').relative_to(ROOT))
        c['latest_learning']={'manifest':ident(E/'EPOCH_MANIFEST.json'),'direction':final['next_priority']}
        c['next_research_priority']=final['next_priority']
        c['cumulative_budget_ledger'].update(current_epoch_closed=True,publication_period_native_calls_allowed=0,
           scope='ALL_EPOCHS_CLOSED_THROUGH18',total_historical_attempts=final['cumulative_execution']['native_corpus_attempts_including_failed_request'],
           cumulative_native_attempts=final['cumulative_execution']['native_corpus_attempts_including_failed_request'],
           allowed_further_attempts_in_closed_study=0)
        c['cumulative_budget_ledger']['epoch18_closed_study']={'used':final['actual_execution']['native_process_attempts'],'cap':2,'remaining':0}
        c['cumulative_budget_ledger'].update(new_study_attempts_used=final['actual_execution']['native_process_attempts'],new_study_attempts_remaining=0,
           new_study_unspent_phase_slots=2-final['actual_execution']['native_process_attempts'])
        c['cumulative_budget_ledger']['epoch18_active_study'].update(native_allowed=0,conditional_native_allowance_after_exact_remote_readback=0,status='CLOSED',used=final['actual_execution']['native_process_attempts'])
        if final['confirmation']['CONF_annotations_projected']>0 or final['confirmation'].get('confirmation_attempts',0)>0:
            retired=[x for x in c['unused_confirmation_sets']if x.get('questions')==24]
            c['unused_confirmation_sets']=[x for x in c['unused_confirmation_sets']if x.get('questions')!=24]
            c.setdefault('retired_confirmation_sets',[]).append({'epoch':18,'previous_reserved_entries':retired,
              'status':'PERMANENTLY_EXPOSED_DEV_AFTER_ACTUAL_ATTEMPT_OR_CHOICES','used_identities':ident(E/'USED_IDENTITIES.json')})
        else:
            for row in c['unused_confirmation_sets']:
                row['epoch18_model_unused']=True;row['epoch18_annotation_choices_used']=0
    c['champion']='SubmittedNative104/RRF10 unchanged';c['goal_met']=False;c['official_rank']=None
    c['active_run']={'path':'ACTIVE_RUN.json','run_id':a['run_id'],'state':a['state'],'experiments_active':a['experiments_active'],'native_allowed':0}
    c['benchmark_refresh']='experiments/sota-2026-10-22/legal-transfer/epoch18/benchmark-refresh.json'
    c['publisher_status']='experiments/sota-2026-10-22/legal-transfer/epoch18/publisher-status.json'
    refresh=read(S/'legal-transfer/epoch18/benchmark-refresh.json')
    for name in ['JevBench','ClaimBench']:
        c['benchmark_targets'][name]['latest_refresh_attempt']=refresh[name]
        c['benchmark_targets'][name]['last_observed_at_UTC']=refresh['observed_at_UTC']
    c['benchmark_targets']['JevBench'].update(leader_observed=refresh['JevBench']['leader'],
       capability_observed=refresh['JevBench']['Capability_attribute'],headline_display=refresh['JevBench']['headline_display'])
    c['benchmark_targets']['ClaimBench'].update(decision_leader_observed=refresh['ClaimBench']['decision_leader']['model'],
       accuracy_percent_observed=refresh['ClaimBench']['decision_leader']['accuracy_percent'],full_access_verified=False,RuVector_measured=False)
    c['publisher_status_refresh_scope']='Exact first account search0; second account and broader search FORBIDDEN. No claim of result absence; current officialresult/rank UNVERIFIED.'
    c['publication_review']='experiments/sota-2026-10-22/audit/epoch18/'+('premeasurement-plan-independent-v1.json'if phase=='frozen'else'acceptance-rejection-independent-v1.json')
    c['epoch18_publication_reviews']=[ident(x)for x in allfiles()if x.name.startswith(('capsule-','privacy-'))and x.suffix=='.json']
    c['publication_review_scope']='Exact public18 source/results/identity capsule only; no main/merge/release/secrets/outbound mail/new submission or officialrank claim.'
    write(dest/'ACTIVE_RUN.json',a);write(dest/'CONTINUATION.json',c)
    write(P/('project-files-'+(label or phase)+'.json'),[ident(f)for f in files])
    print(json.dumps({'phase':phase,'project_files':len(files),'CP':len(cp['project_files']),'controls':str(dest)}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prenative','frozen','final']);ap.add_argument('--out-label');args=ap.parse_args()
    prenative()if args.phase=='prenative'else controls(args.phase,args.out_label)
