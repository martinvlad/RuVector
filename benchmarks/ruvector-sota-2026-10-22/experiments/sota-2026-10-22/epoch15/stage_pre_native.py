"""Stage reviewed frozen study artifacts; never runs a benchmark or updates Git."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,os,shutil
ROOT=Path(__file__).resolve().parents[3];S=ROOT/'experiments/sota-2026-10-22';E=S/'epoch15';SCOPE=ROOT.parent;KIT=SCOPE/'kit'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+chr(10)).encode()
def write(p,v):
 with Path(p).open('xb') as f:f.write(encoded(v));f.flush();os.fsync(f.fileno())
def ident(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest()}
owner=read(SCOPE/'owner.json');os.kill(owner['pid'],0)
a=S/'audit/epoch15/premeasurement-acceptance-v2.json';assert a.is_file(),'Independent full prelaunch acceptance required'
review=read(a);plan=E/'plan.v2.json';assert sha(plan)=='82cfe2fd0ab18ad1c7c1f6372df97925061832d6e809701cfcc9a53a37dcfc3f'
assert review.get('checks_passed') is True and review.get('plan_SHA256')==sha(plan) and review.get('decision')=='ACCEPT_PRELAUNCH_SOURCES_CONDITIONAL_ON_CAS_READBACK','Explicit independent plan-bound source acceptance required'
assert review.get('native_execution_admitted') is False,'Native admission only after reviewed CAS snapshot readback'
assert not (E/'launch.json').exists(),'Pre-native stage cannot claim an actual run'
allfiles=[]
for d in ['candidate/epoch15','audit/epoch15','legal-transfer/epoch15','controller/epoch15','epoch15']:
 for f in sorted((S/d).rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts or '/candidate/epoch15/assets/' in str(f):continue
  allfiles.append(f)
allfiles=sorted(set(allfiles))
source={'schema_version':1,'kind':'FROZEN_PRE_NATIVE_PUBLIC_SOURCE_AND_DATA_MANIFEST','epoch':15,'source_checkpoint':'0a6379a108919c9aa5ab52966ce1a9aacab8a0f4','scientific_plan':ident(plan),'files':[ident(f) for f in allfiles],'excludes':['This manifest','Derived frozen-study/used-identity manifests','Derived checkpoint controls','Pretrained model assets and __pycache__'],'actual_native_model_calls_before_this_manifest':0}
write(E/'SOURCE_MANIFEST.pre-native.json',source);allfiles.append(E/'SOURCE_MANIFEST.pre-native.json')
dev=read(S/'legal-transfer/epoch15/dev-allowlist.json');conf=read(S/'legal-transfer/epoch15/confirmation-allowlist.json')
used={'schema_version':1,'epoch':15,'kind':'FROZEN_ROLES_BEFORE_NATIVE_RUN','train':[],'calibration':[],'development':dev,'confirmation':conf,'DEV_annotation_projection':24,'CONF_annotation_choices_used':0,'native_attempts':0,'old_easy48_Legal96_f018_permanently_DEV':True,'prior_exposed_originaltrain_groups':189,'new_fixed_materialized_DEV_groups':8,'conservative_originaltrain_DEV_groups':197,'unreserved_originaltrain_groups':210,'reserved_confirmation_groups':16,'confirmation_project_model_unused':True,'confirmation_globally_retired':False,'no_confirmation_training_or_selection':True}
write(E/'USED_IDENTITIES.pre-native.json',used);allfiles.append(E/'USED_IDENTITIES.pre-native.json')
frozen={'schema_version':1,'epoch':15,'status':'FROZEN_NATIVE_NOT_STARTED','plan':ident(plan),'source_manifest':ident(E/'SOURCE_MANIFEST.pre-native.json'),'premeasurement_acceptance':ident(a),'used_identities':ident(E/'USED_IDENTITIES.pre-native.json'),'development_SHA256':'3233c621709ef64af45b6feec640165f1d6477062d6218dd7005d47b4bb09f6f','confirmation_SHA256':'850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50','native_model_fit_paid_GPU_calls':0,'limits':{'native_attempt_cap':2,'CPU_threads':2,'seconds_per_process_including_init_cleanup':600,'paid_GPU_calls':0},'champion_unchanged':'SubmittedNative104/RRF10','official_score':None,'official_rank':None,'goal_met':False,'no_scheduled_work_claimed_executed':True}
write(E/'FROZEN_STUDY_MANIFEST.pre-native.json',frozen);allfiles.append(E/'FROZEN_STUDY_MANIFEST.pre-native.json')
stage=SCOPE/'stage-pre-native';stage.mkdir(mode=0o700)
ck=read(KIT/'CHECKPOINT_MANIFEST.json');seen={r['path'] for r in ck['project_files']}
for f in allfiles:
 r=ident(f);assert r['path'] not in seen;seen.add(r['path']);ck['project_files'].append({k:r[k] for k in ['path','bytes','sha256']})
ck['project_files'].sort(key=lambda r:r['path']);ck['epoch15_prelaunch']={'source_frozen':True,'native_run_started':False,'fresh_restoration':True,'source_checkpoint':'0a6379a108919c9aa5ab52966ce1a9aacab8a0f4','plan_SHA256':sha(plan)}
c=read(KIT/'CONTINUATION.json');c['prior_published_base_commit']='0a6379a108919c9aa5ab52966ce1a9aacab8a0f4';c['checkpoint_manifest_sha256']=hashlib.sha256(encoded(ck)).hexdigest();c['epochs'].append({'epoch':15,'status':'FROZEN_NATIVE_NOT_STARTED','manifest':str((E/'FROZEN_STUDY_MANIFEST.pre-native.json').relative_to(ROOT)),'native_attempts':0,'confirmation_consumed':False})
refresh=read(S/'legal-transfer/epoch15/benchmark-refresh.json');j=refresh['JevBench'];c['benchmark_targets']['JevBench'].update(leader_observed=j['leader'],capability_observed=j['Capability_attribute'],headline_display=j['headline_display'],last_observed_at_UTC=refresh['observed_at_UTC'],refresh_required=True);c['benchmark_targets']['ClaimBench'].update(last_observed_at_UTC=refresh['observed_at_UTC'],RuVector_measured=False)
c['epoch15_frozen_study']=frozen;c['benchmark_refresh']='experiments/sota-2026-10-22/legal-transfer/epoch15/benchmark-refresh.json';c['publisher_status']='experiments/sota-2026-10-22/legal-transfer/epoch15/publisher-status.json'
c['active_run']={'path':'ACTIVE_RUN.json','run_id':owner['run_id'],'state':'FROZEN_NATIVE_NOT_STARTED','experiments_active':True,'native_allowed':2,'publication_complete_in_this_commit':False}
c['restoration_boundary']='Epoch15 fresh reconstruction verified2126 Git blobs,2055 projected checkpoint records+48base; selected7 pretrained assets,BGE2 and native22 exact regular-file bytes verified separately. No inference occurred before the frozen study snapshot. Historical restoration evidence remains unchanged.'
c['next_research_priority']='Continue ONLY this exclusive frozen epoch15 study using plan.v2.json and its strict gates. No overlapping run or retry. Native DEV has not started in this snapshot; no result, improvement or rank claimed. Preserve Native104 and eligible unusedCONF48. If runtime state or native reservation is uncertain, stop and reconcile evidence instead of repeating.'
c['publication_review']='experiments/sota-2026-10-22/audit/epoch15/premeasurement-acceptance-v2.json'
active={'schema_version':1,'run_id':owner['run_id'],'state':'FROZEN_NATIVE_NOT_STARTED','checkpoint_parent':'0a6379a108919c9aa5ab52966ce1a9aacab8a0f4','started_at':owner['started_at'],'expires_at':datetime.fromtimestamp(owner['expires_unix'],timezone.utc).isoformat(),'experiments_active':True,'native_allowed':2,'OS_lock_held':True,'native_attempts_executed':0,'frozen_plan_SHA256':sha(plan),'frozen_plan_path':'experiments/sota-2026-10-22/epoch15/plan.v2.json','prior_closed_native_attempts':16,'limits':frozen['limits'],'instruction':'Exclusive scoped epoch15 lease. Only this exact frozen candidate/source/data/gates after independent acceptance. Atmost2 nonretryable CPU2/600s processes inclinit/cleanup, DEVthenconditionalunchangedCONF48. No extra probes, paid/GPU0. Othercontinuations STOP whileactive. If currentprocess/reservationstateuncertain, stop; never repeat an uncertain mutation or native batch.','publication_complete_in_this_commit':False}
for f in allfiles:
 out=stage/str(f.relative_to(ROOT));out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,out)
for name,v in [('CHECKPOINT_MANIFEST.json',ck),('CONTINUATION.json',c),('ACTIVE_RUN.json',active)]:write(stage/name,v)
shutil.copyfile(KIT/'CHECKPOINT_MANIFEST.json',stage/'CHECKPOINT_MANIFEST.before-epoch15.json')
entries=[]
for f in sorted(stage.rglob('*')):
 if not f.is_file():continue
 rel=str(f.relative_to(stage));b=f.read_bytes();entry={'path':'benchmarks/ruvector-sota-2026-10-22/'+rel,'mode':'100644','type':'blob','content':b.decode('utf-8')}
 if rel=='CHECKPOINT_MANIFEST.before-epoch15.json':entry.pop('content');entry['sha']='3ce08bc832c8d82e240c6549e9645a170222201a'
 entries.append(entry)
batches=[];batch=[];size=0
for x in entries:
 n=len(json.dumps(x,ensure_ascii=False).encode())
 if batch and size+n>180000:batches.append(batch);batch=[];size=0
 batch.append(x);size+=n
if batch:batches.append(batch)
for i,b in enumerate(batches):write(SCOPE/('pre-native-transport-'+str(i)+'.json'),{'tree_elements':b})
summary={'status':'PREFREEZE_PUBLICATION_STAGED_NOT_PUBLISHED','stage':str(stage),'new_project_files':len(allfiles),'checkpoint_project_files':len(ck['project_files']),'tree_entries':len(entries),'batches':len(batches),'checkpoint_SHA256':c['checkpoint_manifest_sha256'],'files':[{'path':x['path'],'git_blob':x.get('sha') or hashlib.sha1(b'blob '+str(len(x['content'].encode())).encode()+bytes([0])+x['content'].encode()).hexdigest(),'bytes':len(x.get('content','').encode()) if 'content'in x else 455603} for x in entries]}
write(SCOPE/'pre-native-stage-summary.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k!='files'}))

