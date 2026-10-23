"""Derive only the three scoped checkpoint controls from reviewed public bytes."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,importlib.util,json,os,stat
from datetime import datetime,timezone
P='experiments/sota-2026-10-22/'
SOURCE='6eb624feef9ea93c3b1a8f76c20e8442c6bece50'

def raw(value):return (json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def regular(path,directory=False):
    path=path.absolute()
    assert not any(x.is_symlink() for x in [path,*path.parents])
    assert path.is_dir() if directory else stat.S_ISREG(path.lstat().st_mode)
    return path
def ref(root,name):
    assert name and '\\' not in name and not PurePosixPath(name).is_absolute()
    assert not any(x in ('','.','..') for x in name.split('/'))
    path=regular(root/name);assert path.resolve().is_relative_to(root)
    b=path.read_bytes()
    return {'path':name,'bytes':len(b),'sha256':sha(b)}
def read(path):return json.loads(regular(path).read_text())

def build(args):
    root=regular(args.project,True);kit=regular(args.kit,True);scope=regular(args.scope,True)
    out=args.out.absolute()
    assert not out.exists() and not out.is_symlink()
    assert not out.is_relative_to(root)
    assert not any(x.is_symlink() for x in [out,*out.parents])
    owner=read(scope/'owner.json');os.kill(owner['pid'],0)
    path=root/(P+'epoch19/publication/prepare_publication.py')
    assert sha(regular(path).read_bytes())=='19504b67100995984a8aab957728055764ba48f1df423876aa13379e045433fb'
    spec=importlib.util.spec_from_file_location('reviewed19publication',path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    common_path=root/(P+'candidate/epoch19/common.py')
    cspec=importlib.util.spec_from_file_location('exact19_source_common',regular(common_path))
    common=importlib.util.module_from_spec(cspec);cspec.loader.exec_module(common)
    common.require_plan(root/(P+'epoch19/plan.json'))
    current=helper.walk_current(root)
    assert sha(regular(kit/'CHECKPOINT_MANIFEST.json').read_bytes())=='adc60b85f5b9b11f85ae03e395c20323ab8ec9fba22144e5c8c5bcb3599c4bb7'
    cp=read(kit/'CHECKPOINT_MANIFEST.json')
    old={r['path']:r for r in cp['project_files']}
    assert len(old)==len(cp['project_files'])==2718 and not set(old)&set(current)
    for n,b in current.items():old[n]={'path':n,'bytes':len(b),'sha256':sha(b)}
    cp['project_files']=[old[n] for n in sorted(old)]
    mode=args.mode;final=mode=='final'
    manifest=read(root/(P+'epoch19/EPOCH_MANIFEST.json')) if final else None
    actual=manifest['actual_execution'] if final else None
    attempts=actual['qualification_worker_attempts'] if final else 0
    assert type(attempts) is int and 0<=attempts<=1
    if final:assert actual.get('owned_live_processes_closed') is True
    cp['epoch19_'+('final' if final else 'prelaunch')]={
        'source_checkpoint':SOURCE,'kind':'ENGINEERING_ONLY_SEMANTIC_PRECISION_QUALIFICATION',
        'public_new19_files':len(current),'benchmark_case_roles':[],
        'scope':'Exact reviewed new19 public source and evidence only; no models, private pages or credentials.'}
    cp_bytes=raw(cp)
    cont=read(kit/'CONTINUATION.json')
    cont.update(prior_published_base_commit=args.parent,checkpoint_manifest_sha256=sha(cp_bytes),
        goal_met=False,official_rank=None,champion='SubmittedNative104/RRF10 unchanged')
    state='EPOCH19_CLOSED' if final else 'EPOCH19_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION'
    active={'schema_version':1,'run_id':owner['run_id'],'state':state,'experiments_active':not final,
        'native_allowed':0,'native_allowed_after_exact_remote_readback':0,
        'checkpoint_parent':args.parent,'started_at':owner['started_at'],
        'expires_at':datetime.fromtimestamp(owner['expires_unix'],timezone.utc).isoformat(),
        'OS_lock_held':True,'OS_lock_release_pending_final_remote_readback':final,
        'limits':{'qualification_worker_attempt_cap':1,'CPU_threads':2,
            'seconds_per_process_including_init_cleanup':600,'paid_GPU_calls':0},
        'instruction':'Closed; no further epoch19 execution.' if final else
            'Source-only publication, not native admission. Exact independent remote readback and live exclusive-lock proof must precede one bounded six-forward engineering worker. No legal inputs/labels/CONF/promotion/submission.'}
    cont['active_run']={k:active[k] for k in ('run_id','state','experiments_active','native_allowed')}
    cont['active_run']['path']='ACTIVE_RUN.json'
    cont['epoch19_frozen_study']={'kind':'ENGINEERING_ONLY_SEMANTIC_PRECISION_QUALIFICATION',
        'source_checkpoint':SOURCE,'plan':ref(root,P+'epoch19/plan.json'),
        'source_freeze':ref(root,P+'epoch19/candidate-source-freeze.json'),
        'audit_protocol':ref(root,P+'audit/epoch19/protocol.json'),
        'role_manifest':ref(root,P+'legal-transfer/epoch19/role-manifest.json'),
        'benchmark_roles_empty':True,'new_legal_cases':0,'promotion_or_submission_allowed':False}
    refresh=read(root/(P+'legal-transfer/epoch19/benchmark-refresh.json'))
    pub=read(root/(P+'legal-transfer/epoch19/publisher-status.json'))
    j=refresh['JevBench'];c=refresh['ClaimBench'];at=refresh['observed_at_UTC']
    cont['benchmark_targets']['JevBench'].update(leader_observed=j['leader'],capability_observed=j['Capability_attribute'],
        headline_display=j['headline_display'],last_observed_at_UTC=at,latest_refresh_attempt=j,refresh_required=True)
    cont['benchmark_targets']['ClaimBench'].update(decision_leader_observed=c['decision_leader']['model'],
        accuracy_percent_observed=c['decision_leader']['accuracy_percent'],overall_language_models_at100=len(c['language_models_at100']),
        RuVector_measured=False,last_observed_at_UTC=at,latest_refresh_attempt=c,full_access_verified=False)
    cont['benchmark_refresh']=ref(root,P+'legal-transfer/epoch19/benchmark-refresh.json')
    cont['publisher_status']=ref(root,P+'legal-transfer/epoch19/publisher-status.json')
    cont['publisher_status_refresh_scope']=pub['interpretation']
    cont['restoration_epoch19']={'fresh_source_commit':SOURCE,'source_Git_blobs':2795,
        'restored_CP_files':2718,'BASE_files':48,'KIT_files':61,
        'separately_verified_public_assets':38,'official_CPU_wheels':31,'verified_wheel_members':17498,
        'reviewed_bootstrap_restore_used':True,'no_prior_filesystem_trust':True}
    ledger=cont['cumulative_budget_ledger']
    ledger.update(new_study_id='native-semantic-precision-qualification-e19',new_study_attempt_cap=1,
        new_study_attempts_used=attempts,new_study_attempts_remaining=0,
        new_study_unspent_phase_slots=0 if final else 1,
        current_epoch_closed=final,publication_period_native_calls_allowed=0,
        scope='ALL_EPOCHS_CLOSED_THROUGH19' if final else 'PRIOR18_CLOSED_EPOCH19_SOURCE_PENDING_ADMISSION')
    cont['official_result_status']={'score':None,'rank':None,'verified':False,
        'scope':pub['interpretation'],'original115_is_queue_position_never_rank':True}
    if final:
        cont['epoch19_final']={'manifest':ref(root,P+'epoch19/EPOCH_MANIFEST.json'),
            'results':ref(root,P+'epoch19/RESULTS.json'),
            'used_identities':ref(root,P+'epoch19/USED_IDENTITIES.json'),
            'source_manifest':ref(root,P+'epoch19/SOURCE_MANIFEST.json'),
            'rejection_ledger':ref(root,P+'epoch19/REJECTION_LEDGER.json'),
            'status':manifest['status'],'engineering_qualified':manifest['engineering_qualified'],
            'benchmark_accepted':False,'all_slots_closed':True,'actual_execution':manifest['actual_execution']}
        cont['epochs'].append({'epoch':19,'kind':'ENGINEERING_QUALIFICATION_ONLY',
            'status':manifest['status'],'manifest':P+'epoch19/EPOCH_MANIFEST.json',
            'native_qualification_attempts':manifest['actual_execution']['qualification_worker_attempts'],
            'benchmark_native_corpus_batches':0,'benchmark_HTTP_requests':0,'confirmation_consumed':False})
        cont['execution_observed']['native_qualification_attempts']=attempts
        cont['execution_observed']['engineering_NLI_pair_forwards']=manifest['actual_execution']['NLI_forward_pairs_completed']
        cont['execution_observed']['engineering_native_searches']=manifest['actual_execution']['native_searches_completed']
        ledger['epoch19_closed_qualification']={'cap':1,'used':manifest['actual_execution']['qualification_worker_attempts'],
            'allowed_further':0,'benchmark_corpora':0,'benchmark_HTTP':0,'paid_GPU_calls':0}
        ledger['cumulative_corpus_attempts_preserved']=19
        ledger['cumulative_qualification_attempts']=manifest['actual_execution']['qualification_worker_attempts']
        ledger['cumulative_native_process_attempts_including_qualification']=19+manifest['actual_execution']['qualification_worker_attempts']
        ledger['count_scope']='Legacy cumulative_native_attempts19 refers to corpus attempts. The new explicit native-process total also includes this one engineering qualification; HTTP/corpus counters remain separate.'
        cont['next_research_priority']=manifest['next_research_priority']
        cont['latest_learning']={'manifest':ref(root,P+'epoch19/EPOCH_MANIFEST.json'),'direction':manifest['next_research_priority']}
        cont['rejection_ledger']=ref(root,P+'epoch19/REJECTION_LEDGER.json')
        active.update(actual_epoch19_qualification_attempts=manifest['actual_execution']['qualification_worker_attempts'],
            all_unspent_epoch19_slots_permanently_closed=True,owned_native_groups_closed=actual['owned_live_processes_closed'],
            closed_at=manifest['finished_at'])
    else:
        cont['epoch19_planning']={'kind':'ENGINEERING_ONLY_SEMANTIC_PRECISION_QUALIFICATION',
            'actual_native_attempts':0,'planned_max_qualification_attempts':1,
            'new_benchmark_cases':0,'confirmation_calls':0,'promotion_allowed':False}
    out.mkdir(mode=0o700)
    for name,b in [('CHECKPOINT_MANIFEST.json',cp_bytes),('CONTINUATION.json',raw(cont)),('ACTIVE_RUN.json',raw(active))]:
        with (out/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return {'mode':mode,'CP_files':len(old),'new19_files':len(current),'checkpoint_sha256':sha(cp_bytes),'native_calls_by_builder':0}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('project','kit','scope','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--mode',choices=('source','final'),required=True);ap.add_argument('--parent',required=True)
    print(json.dumps(build(ap.parse_args())))
