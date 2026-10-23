from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch10';pub=e/'publication';stage=pub/'stage';kit=e/'durable-kit'
def h(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
base=load(e/'durable-files.json')['files'];stage.mkdir(parents=True,exist_ok=False)
for x in base:
 src=kit/x['path'];dst=stage/x['path'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
paths=set();ca=load(s/'candidate/epoch10/public-allowlist.json')
for x in ca['files']:
 p=r/x['path'];assert p.stat().st_size==x['bytes'] and h(p.read_bytes())==x['sha256'];paths.add(Path(x['path']))
paths.add(Path('experiments/sota-2026-10-22/candidate/epoch10/public-allowlist.json'))
for f in (s/'candidate/epoch10/postrun').rglob('*'):
 if f.is_file() and f.suffix in ('.py','.json','.txt','.md') and '.private' not in f.name:paths.add(f.relative_to(r))
da=load(s/'legal-transfer/epoch10/publication-files.json')
for x in da['files']:
 p=s/'legal-transfer/epoch10'/x['relative_path'];assert p.stat().st_size==x['bytes'] and h(p.read_bytes())==x['sha256'];paths.add(p.relative_to(r))
paths.add(Path('experiments/sota-2026-10-22/legal-transfer/epoch10/publication-files.json'))
for f in (s/'audit/epoch10').iterdir():
 if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md','.txt','.log') and not any(t in f.name for t in ('.private','postrun-diagnostic-replay','postrun-findings-replay','postrun-replay-v1','published-epoch','post-review-diff','automation-independent')):paths.add(f.relative_to(r))
for f in e.iterdir():
 if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md','.txt','.log') and f.name!='durable-files.json':paths.add(f.relative_to(r))
for f in (e/'runs').rglob('*'):
 if f.is_file() and f.suffix in ('.json','.jsonl','.log','.txt'):paths.add(f.relative_to(r))
for n in ('epoch10_loop.py','test_epoch10_loop.py'):paths.add(Path('experiments/sota-2026-10-22/controller')/n)
for rel in sorted(paths):
 src=r/rel;assert src.is_file() and not src.is_symlink();b=src.read_bytes();b.decode('utf8');dst=stage/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
m=load(kit/'CHECKPOINT_MANIFEST.json');old={x['path']:x for x in m['project_files']};assert len(old)==1264
for rel in sorted(paths):
 b=(stage/rel).read_bytes();q=str(rel);x={'path':q,'bytes':len(b),'sha256':h(b)}
 if q in old:assert old[q]==x,'Historical project file modified:'+q
 old[q]=x
shutil.copy2(kit/'CHECKPOINT_MANIFEST.json',stage/'CHECKPOINT_MANIFEST.before-epoch10.json');m['project_files']=[old[k] for k in sorted(old)];m['scope']+=' Append-only epoch10 TRAIN-only crossfitted evidence/clause-role residual head overfixedpretrained9, actualnative matchedretrieval; prior12attemptsclosed, reusedTRAIN72/newDEV24/conditionalpreservedCONF48,calibrationempty.';m['epoch10_restoration']={'source_data_results':'Exact source/licensed projections/saved evidence; reviewedbootstrap+restore, no archivedcontroller rerun.','new_model':'No newpretrainedweights; exact22publicHFassetpins restoredfromverifiedcache via reviewed4/9helpers. Immutablemodelrevision/size/SHA pinned, pretrainedbinaries omitted. All deferredassetpins explicitlylisted bycoldproof.','native':'Exact8core+14TypeSafe regularfiles via reviewedepoch5restore_runtime.py; no model/native calls duringrestore'};save(stage/'CHECKPOINT_MANIFEST.json',m)
c=load(kit/'CONTINUATION.json');result=load(e/'EPOCH_MANIFEST.json');a=result['actual_results'];budget=result['budget'];retired=result['confirmation_consumed'];status=result['status'];c.update(checkpoint_manifest_sha256=h((stage/'CHECKPOINT_MANIFEST.json').read_bytes()),champion='SubmittedNative104/RRF10unchanged; epoch10 '+status,goal_met=False,official_rank=None,rejection_ledger='experiments/sota-2026-10-22/epoch10/REJECTION_LEDGER.json',benchmark_refresh='experiments/sota-2026-10-22/legal-transfer/epoch10/benchmark-refresh.json',publisher_status='experiments/sota-2026-10-22/epoch10/publisher-status.json',publication_review='experiments/sota-2026-10-22/audit/epoch10/final-publication-review-v1.json',next_research_priority=result['next_research_priority'])
c['audit_replay_reproduction']=result.get('replay_reproduction',{})
refresh=load(s/'legal-transfer/epoch10/benchmark-refresh.json');j=refresh['JevBench'];cl=refresh['ClaimBench'];c['benchmark_targets']['JevBench'].update(leader_observed=j['leader'],capability_observed=j['Capability'],refresh_required=True,last_observed_at_UTC=j['source']['observed_at_UTC']);c['benchmark_targets']['ClaimBench'].update(decision_leader_observed=cl['decision_model_leader'],accuracy_percent_observed=cl['decision_model_accuracy_percent'],overall_language_models_at100=len(cl['language_models_at100_percent']),RuVector_measured=False,last_observed_at_UTC=cl['aggregate_source']['observed_at_UTC'])
ex=c['execution_observed'];ex['native_corpus_attempts_including_failed_request']+=budget['this_epoch_native_attempts'];ex['actual_HTTP_successful_decisions']+=a['successful_HTTP'];ex['actual_HTTP_decisions']=ex['actual_HTTP_successful_decisions'];ex['actual_HTTP_failed_requests']+=a['failed_HTTP'];ex['native_corpus_batches_completed']+=a['completed_corpora'];ex['native_corpus_batches']=ex['native_corpus_batches_completed'];ex['actual_HTTP_evaluation_diagnostic_decisions']+=a['successful_HTTP']-a['training_feature_HTTP'];ex['actual_HTTP_training_feature_requests']+=a['training_feature_HTTP'];ex['counting_note']='Cumulative counts include historicaladaptivepublic/evaluationdiagnostics; notallfreshheldout. TrainingfeatureHTTP countedseparately, never benchmarkgeneralization. Epoch10 actual TRAIN/DEV/conditionalCONF fromPopen/wire; scheduledwork notcalledexecuted.'
c['epochs'].append({'epoch':10,'status':status,'manifest':'experiments/sota-2026-10-22/epoch10/EPOCH_MANIFEST.json','DEV_n':a['DEV_n'],'candidate_correct':a['candidate_correct'],'confirmation_consumed':retired,'confirmation_requests_completed':result['confirmation_requests_completed'],'scored_decisions':a['DEV_n']+result['confirmation_requests_completed']})
ident=load(e/'USED_IDENTITIES.json')
if ident['newDEV8_retired_conservatively_after_phase1']:c['exposed_development_sets'].append('epoch10DEV24/8neworiginaltrain groups SHAb33c63e727b2990b2efea24234af5b7b9890e4b0ed2634534d4e1e942ca9a86e permanentlyDEVafterphase1attempt evenfitfailure; reusedTRAIN24adds0newexposures. Totalexposedoriginaltrain='+str(ident['exposed_originaltrain_groups_total'])+'; unreserved242; confirmation16retired='+str(retired))
if retired:
 c['used_confirmation_sets'].append('epoch10originaltrainCONF48/16groups850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50 permanentlyDEVafterattempt; actualcompletedcountsseparate');c['unused_confirmation_sets']=[]
else:c['unused_confirmation_sets']=[{'path':'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl','sha256':'850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50','questions':48,'document_groups':16,'status':'PROJECT_MODEL_UNUSED_RESERVED; sourcepublic,unknownpretrainingoverlap; nofit/selection'}]
c['restoration_boundary']='All public source/data/results hashrestored; native22filehelper verified. Coldproof explicitly lists deferredmodelassetpins(old/new); weights acquiredseparately via reviewedhelpers/exactofficialrevision+hashes. No inference or archivedcontroller rerun duringrestore.'
c['cumulative_budget_ledger']['closed_epoch9_study']={'id':'native-typed-pretrained-nli-e9','used':1,'cap':2,'unspent_slots':1,'allowed_further':0};c['cumulative_budget_ledger'].update(cumulative_native_attempts=budget['lifetime_native_attempts'],current_epoch_closed=True,publication_period_native_calls_allowed=0,new_study_id='native-evidence-role-head-e10',new_study_attempt_cap=2,new_study_attempts_used=budget['this_epoch_native_attempts'],new_study_unspent_phase_slots=budget['unspent_phase_slots'],new_study_attempts_remaining=0,allowed_further_attempts_in_closed_study=0,total_historical_attempts=budget['lifetime_native_attempts'],next_epoch_rule='Allhistoricalstudiesclosed, includinganyunspentconditional10slot; no retry. A newexplicitcontinuation permitsdistincthypothesis onlyafterfrozenlicensedTRAIN/DEV/calibration/project-unusedCONF/source/runtime, atmost2nonretryableCPU2/600sphases,paid0/GPU0. Oldf018DEVforever. Preserveepoch9CONF48ifunused; ifretiredneednewverifiedbank. No repeatedunchangedblockerprobes.')
lease=load(e/'lease.json');lease.update(state='COMPLETE_'+status,experiments_active=False,publication_complete_in_this_commit=True,finished_at=datetime.now(timezone.utc).isoformat(),new_study_attempts_started=budget['this_epoch_native_attempts'],new_study_native_attempts_used=budget['this_epoch_native_attempts'],new_study_unspent_phase_slots=budget['unspent_phase_slots'],new_study_native_attempts_remaining=0,allowed_further_attempts_in_closed_study=0);c['active_run']={'path':'ACTIVE_RUN.json','run_id':lease['run_id'],'state':lease['state'],'experiments_active':False,'publication_complete_in_this_commit':True};save(stage/'CONTINUATION.json',c);save(stage/'ACTIVE_RUN.json',lease)
files=[]
for f in sorted(stage.rglob('*')):
 if f.is_file():
  q=str(f.relative_to(stage));b=f.read_bytes();files.append({'path':q,'bytes':len(b),'sha256':h(b),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
save(pub/'publication-map.json',{'schema_version':1,'base_commit':'24e671dd2b27f5119f25651056456832e0657745','base_tree':'e51d627d7f5b8e9f5410830a0b39f0ce2cbe6f45','files':files,'new_project_files':len(old)-1264,'checkpoint_project_files':len(old)});print(json.dumps({'public_leaf_files':len(files),'project_files':len(old),'new_project_files':len(old)-1264,'bytes':sum(x['bytes'] for x in files)}))
