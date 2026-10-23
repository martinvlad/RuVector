from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch13';pub=e/'publication';stage=pub/'stage';kit=e/'durable-kit'
def h(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
base=load(e/'durable-files.json')['files'];assert len(base)==1916;stage.mkdir(parents=True,exist_ok=False)
for x in base:
 src=kit/x['path'];dst=stage/x['path'];b=src.read_bytes();assert len(b)==x['bytes'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
paths=set();ca=load(s/'candidate/epoch13/public-allowlist-v1.json')
for x in ca['files']:
 p=r/x['path'];assert p.stat().st_size==x['bytes'] and h(p.read_bytes())==x['sha256'];paths.add(Path(x['path']))
paths.add(Path('experiments/sota-2026-10-22/candidate/epoch13/public-allowlist-v1.json'))
postrun=s/'candidate/epoch13/postrun'
if postrun.exists():
 cp=load(postrun/'public-allowlist-v1.json')
 for x in cp['files']:
  rel=Path(x['path']);assert rel.is_relative_to(Path('experiments/sota-2026-10-22/candidate/epoch13/postrun'));f=r/rel;assert f.stat().st_size==x['bytes'] and h(f.read_bytes())==x['sha256'];paths.add(rel)
 paths.add((postrun/'public-allowlist-v1.json').relative_to(r))
da=load(s/'legal-transfer/epoch13/publication-files.json')
for x in da['files']:
 p=s/'legal-transfer/epoch13'/x['relative_path'];assert p.stat().st_size==x['bytes'] and h(p.read_bytes())==x['sha256'];paths.add(p.relative_to(r))
paths.add(Path('experiments/sota-2026-10-22/legal-transfer/epoch13/publication-files.json'))
data_postrun=s/'legal-transfer/epoch13/postrun'
if data_postrun.exists():
 dp=load(data_postrun/'publication-files-v1.json')
 for x in dp['files']:
  rel=Path(x['relative_path']);assert not rel.is_absolute() and '..' not in rel.parts;f=data_postrun/rel;assert f.stat().st_size==x['bytes'] and h(f.read_bytes())==x['sha256'];paths.add(f.relative_to(r))
 paths.add((data_postrun/'publication-files-v1.json').relative_to(r))
proofs={'publication-cold-review-v1.json','publication-asset-bindings-v1.json','cold-cached-replay-independent-v1.json','final-publication-review-v1.json'}
for f in (s/'audit/epoch13').iterdir():
 if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md','.txt','.log') and f.name not in proofs and not any(t in f.name for t in ('.private','terminal-recovery-capture','postrun-diagnostic-replay','postrun-findings-replay','postrun-replay-v1','published-epoch','post-review-diff','automation-independent')):paths.add(f.relative_to(r))
for f in e.iterdir():
 if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md','.txt','.log') and f.name!='durable-files.json' and '.private' not in f.name:paths.add(f.relative_to(r))
for f in (e/'runs').rglob('*'):
 if f.is_file() and f.suffix in ('.json','.jsonl','.log','.txt') and '.private' not in f.name:paths.add(f.relative_to(r))
for f in (s/'controller/epoch13').rglob('*'):
 if f.is_file() and f.suffix in ('.py','.json','.md','.txt','.log') and '.private' not in f.name:paths.add(f.relative_to(r))
for rel in sorted(paths):
 src=r/rel;assert src.is_file() and not src.is_symlink();b=src.read_bytes();b.decode('utf8');dst=stage/rel;assert not dst.exists(),'Historical public file overwrite:'+str(rel);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
m=load(kit/'CHECKPOINT_MANIFEST.json');old={x['path']:x for x in m['project_files']};assert len(old)==1847
for rel in sorted(paths):
 b=(stage/rel).read_bytes();q=str(rel);assert q not in old;old[q]={'path':q,'bytes':len(b),'sha256':h(b)}
shutil.copy2(kit/'CHECKPOINT_MANIFEST.json',stage/'CHECKPOINT_MANIFEST.before-epoch13.json');m['project_files']=[old[k] for k in sorted(old)];m['scope']+=' Append-only epoch13 distinct official RoBERTa threeway C0/E1/N2 reader with active BPE context packing frozen before measurement; actual native matched retrieval, all15priorattempts closed, TRAIN/calibration empty,newDEV24/conditionalpreservedCONF48.';m['epoch13_restoration']={'source_data_results':'Reviewed bootstrap+restore exact source/licensed projections/saved outputs; no archivedcontroller rerun.','new_model':'Official cross-encoder/nli-roberta-base FP32 from exact source revision and SHA in candidate13/assets.lock.json; Apache-2.0 declaration/SNLI+MultiNLI supervision and unknown pretraining/document overlap disclosed. All pretrained binaries/tokenizers omitted and separately hashbound in cold proof. Active BPE context policy differs from old SentencePiece; packing algorithm preserved.','native':'Exact8core+14TypeSafe regularfiles viareviewedrestore_runtime.py; zero inference duringrestore'};save(stage/'CHECKPOINT_MANIFEST.json',m)
c=load(kit/'CONTINUATION.json');result=load(e/'EPOCH_MANIFEST.json');a=result['actual_results'];budget=result['budget'];retired=result['confirmation_consumed'];status=result['status'];c.update(checkpoint_manifest_sha256=h((stage/'CHECKPOINT_MANIFEST.json').read_bytes()),champion='SubmittedNative104/RRF10unchanged; epoch13 '+status,goal_met=False,official_rank=None,rejection_ledger='experiments/sota-2026-10-22/epoch13/REJECTION_LEDGER.json',benchmark_refresh='experiments/sota-2026-10-22/legal-transfer/epoch13/benchmark-refresh.json',publisher_status='experiments/sota-2026-10-22/epoch13/publisher-status.json',publication_review='experiments/sota-2026-10-22/audit/epoch13/final-publication-review-v1.json',next_research_priority=result['next_research_priority'])
c['audit_replay_reproduction']=result.get('replay_reproduction',{})
learning=e/'RESEARCH_DIRECTION.json'
if learning.exists():
 direction=load(learning);c['latest_learning']={'path':str(learning.relative_to(r)),'sha256':h(learning.read_bytes())};c['next_research_priority']=direction['next_research_priority']
refresh=load(s/'legal-transfer/epoch13/benchmark-refresh.json');j=refresh['JevBench'];cl=refresh['ClaimBench'];c['benchmark_targets']['JevBench'].update(leader_observed=j['leader'],capability_observed=j['Capability'],refresh_required=True,last_observed_at_UTC=j['source']['observed_at_UTC']);c['benchmark_targets']['ClaimBench'].update(decision_leader_observed=cl['decision_model_leader'],accuracy_percent_observed=cl['decision_model_accuracy_percent'],overall_language_models_at100=len(cl['language_models_at100_percent']),RuVector_measured=False,last_observed_at_UTC=cl['aggregate_source']['observed_at_UTC'])
ex=c['execution_observed'];assert ex['native_corpus_attempts_including_failed_request']==15 and ex['native_corpus_batches_completed']==13;assert ex['actual_HTTP_successful_decisions']==789 and ex['actual_HTTP_training_feature_requests']==144 and ex['actual_HTTP_training_sanity_diagnostic_requests']==6 and ex['actual_HTTP_evaluation_diagnostic_decisions']==639 and ex['actual_HTTP_failed_requests']==2
ex['native_corpus_attempts_including_failed_request']+=budget['this_epoch_native_attempts'];ex['actual_HTTP_successful_decisions']+=a['successful_HTTP'];ex['actual_HTTP_decisions']=ex['actual_HTTP_successful_decisions'];ex['actual_HTTP_failed_requests']+=a['failed_HTTP'];ex['native_corpus_batches_completed']+=a['completed_corpora'];ex['native_corpus_batches']=ex['native_corpus_batches_completed'];ex['actual_HTTP_evaluation_diagnostic_decisions']+=a['successful_HTTP'];assert a['training_feature_HTTP']==a['training_sanity_HTTP']==0;assert ex['actual_HTTP_successful_decisions']==ex['actual_HTTP_evaluation_diagnostic_decisions']+ex['actual_HTTP_training_feature_requests']+ex['actual_HTTP_training_sanity_diagnostic_requests'];ex['counting_note']='Cumulative counts include historicaladaptivepublic/evaluationdiagnostics; notallfreshheldout. The144trainingfeature and6epoch12TRAINsanity diagnosticHTTP are preserved separately; epoch13 has no TRAIN/fitting/calibration. DEV/CONF evaluationdiagnostics are not officialbenchmarkgeneralization; scheduledwork notcalledexecuted.'
c['epochs'].append({'epoch':13,'status':status,'manifest':'experiments/sota-2026-10-22/epoch13/EPOCH_MANIFEST.json','DEV_n':a['DEV_n'],'TRAIN_sanity_HTTP':0,'training_feature_HTTP':0,'candidate_correct':a['candidate_correct'],'confirmation_consumed':retired,'confirmation_requests_completed':result['confirmation_requests_completed'],'scored_decisions':a['DEV_n']+result['confirmation_requests_completed']})
ident=load(e/'USED_IDENTITIES.json');devhash=ident['source_frozen_roles']['development']['sha256']
if ident['new_DEV_groups_retired']:c['exposed_development_sets'].append('epoch13DEV24/8neworiginaltrain groups SHA'+devhash+' permanentlyDEVafterphase1attempt evenpartialfailure; TRAIN/calibrationempty. Totalexposedoriginaltrain='+str(ident['exposed_originaltrain_groups_total'])+'; unreserved218; confirmation16retired='+str(retired))
if retired:
 c['used_confirmation_sets'].append('epoch13originaltrainCONF48/16groups850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50 permanentlyDEVafterattempt; actualcompletedcountsseparate');c['unused_confirmation_sets']=[]
else:c['unused_confirmation_sets']=[{'path':'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl','sha256':'850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50','questions':48,'document_groups':16,'status':'PROJECT_MODEL_UNUSED_RESERVED; sourcepublic,unknownpretrainingoverlap; nofit/selection'}]
c['restoration_boundary']='All public source/data/results hashrestored; native22filehelper verified. Coldproof explicitly lists deferredmodelassetpins(old/new); weights acquiredseparately via reviewedhelpers/exactofficialrevision+hashes. No inference or archivedcontroller rerun duringrestore.'
c['cumulative_budget_ledger']['closed_epoch12_study']={'id':'native-fp32-quantization-fidelity-e12','used':1,'cap':2,'unspent_slots':1,'allowed_further':0};c['cumulative_budget_ledger'].update(cumulative_native_attempts=budget['lifetime_native_attempts'],current_epoch_closed=True,publication_period_native_calls_allowed=0,new_study_id='native-official-roberta-threeway-e13',new_study_attempt_cap=2,new_study_attempts_used=budget['this_epoch_native_attempts'],new_study_unspent_phase_slots=budget['unspent_phase_slots'],new_study_attempts_remaining=0,allowed_further_attempts_in_closed_study=0,total_historical_attempts=budget['lifetime_native_attempts'],next_epoch_rule='Allhistoricalstudiesclosed, includinganyunspentconditional13slot; no retry. A newexplicitcontinuation permitsdistincthypothesis onlyafterfrozenlicensedTRAIN/DEV/calibration/project-unusedCONF/source/runtime, atmost2nonretryableCPU2/600sphases,paid0/GPU0. Oldf018DEVforever. Preserveepoch9CONF48ifunused; ifretiredneednewverifiedbank. No repeatedunchangedblockerprobes.')
owner=load(e/'lock-owner.json');lr=load(e/'lease.json');assert owner['run_id']==lr['run_id'];lease={'schema_version':1,'run_id':owner['run_id'],'state':'COMPLETE_'+status,'started_at':owner['acquired_at'],'expires_at':datetime.fromtimestamp(owner['expires_unix'],timezone.utc).isoformat(),'owner_scope':'RuVectorSOTAepoch13-distinct-official-RoBERTa-NLI','checkpoint_parent':lr['parent_checkpoint'],'limits':{'native_batches':2,'threads':2,'seconds_per_batch':600,'paid_calls':0,'GPU_calls':0},'prior_closed_lifetime_attempts':15,'new_study_attempts_started':budget['this_epoch_native_attempts'],'experiments_active':False,'instruction':'All15priorhistoricalattempts and this epoch13 study closed; no further inference in publication. Preserve champion pending independently accepted frozen DEV/unusedCONF and publisher protocol/eligibility. Distinct future work needs a new explicit continuation/freeze; no overlapping run or uncertain external mutation.','publication_complete_in_this_commit':True,'finished_at':datetime.now(timezone.utc).isoformat(),'new_study_native_attempts_used':budget['this_epoch_native_attempts'],'new_study_unspent_phase_slots':budget['unspent_phase_slots'],'new_study_native_attempts_remaining':0,'allowed_further_attempts_in_closed_study':0};c['active_run']={'path':'ACTIVE_RUN.json','run_id':lease['run_id'],'state':lease['state'],'experiments_active':False,'publication_complete_in_this_commit':True};save(stage/'CONTINUATION.json',c);save(stage/'ACTIVE_RUN.json',lease)
files=[]
for f in sorted(stage.rglob('*')):
 if f.is_file():
  q=str(f.relative_to(stage));b=f.read_bytes();files.append({'path':q,'bytes':len(b),'sha256':h(b),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
save(pub/'publication-map.json',{'schema_version':1,'base_commit':lr['lease_commit'],'base_tree':lr['lease_tree'],'files':files,'new_project_files':len(old)-1847,'checkpoint_project_files':len(old)});print(json.dumps({'public_leaf_files':len(files),'project_files':len(old),'new_project_files':len(old)-1847,'bytes':sum(x['bytes'] for x in files)}))
