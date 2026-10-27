"""Independent read-only actual E54 failure/physical closure/source-pin review.
No model/native/tokenizer/DATA/Gold/scorer/Git execution; do not rewrite raw counters.
"""
from pathlib import Path
import json,hashlib,os,time
W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch54-6187205840a9');R=W/'project';O=Path(__file__).resolve().parent
P=R/'experiments/sota-2026-10-22/epoch54';RT=R/'experiments/sota-2026-10-22/runtime/epoch54'
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def load(p):return json.loads(p.read_bytes())
def checked(r):
 p=Path(r['path']);a=ref(p);assert a==r;return p
def proc(pid):
 p=Path('/proc')/str(pid)
 try:
  s=(p/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'state':s[0],'ppid':int(s[1]),'pgid':int(s[2]),'sid':int(s[3]),'startticks':int(s[19]),'statm':list(map(int,(p/'statm').read_text().split())),'FDSize':next(int(x.split()[1])for x in(p/'status').read_text().splitlines()if x.startswith('FDSize:'))}
 except FileNotFoundError:return None
plan=load(P/'plan.json');sf=load(P/'SOURCE_FREEZE.json');rawp=W/'private-run/engineering/raw.json';raw=load(rawp);outer=load(W/'ENGINEERING_OUTER_EXECUTION.actual.v1.json');cli=load(W/'ROOT_ENGINEERING_CLI_WALL.actual.v1.json');exc=W/'private-run/engineering/worker.exception.txt';progress=W/'private-run/engineering/worker-progress.jsonl'
assert ref(P/'plan.json')['sha256']=='5802c7822ee2162eb4bae3f09c80f407c7abd7f146b19bae0f56b79447bbe3ec'
assert ref(P/'SOURCE_FREEZE.json')['sha256']=='fe263e1c50fc023c89285b6fa1f62d7b5f2c7b690fd5fab12339acd1408d4162'
assert len(sf['files'])==63
for r in sf['files']:
 p=R/r['path'];v=ref(p);assert(v['bytes'],v['sha256'])==(r['bytes'],r['sha256'])
for k in ['plan_ref','owner_ref','admission_ref','independent_approval_ref','source_freeze_ref']:checked(outer[k])
assert raw['epoch']==outer['epoch']==cli['epoch']==54 and raw['plan_sha256']==outer['plan_ref']['sha256']
assert outer['source_commit']=='40012cee54b180a1b44a513164988aeaa98252cc'
assert raw['errors']==[{'code':'MINIMUM_THREE_GIB_CGROUP_HEADROOM_REQUIRED','type':'ValueError'}]
assert 'line 200, in main' in exc.read_text() and 'require_headroom(baseline)' in exc.read_text()
worker=(RT/'worker.py').read_text().splitlines();assert 'require_headroom(baseline)'in worker[199] and 'fixture=json.loads' in worker[200] and 'TOKENIZER_INITIALIZE_BEFORE'in worker[203] and 'support.embed_documents'in worker[212] and 'support.run_native'in worker[213]
assert raw['rows']==[] and raw['native_state']=={} and raw['fragment_catalog_audit']=={} and progress.stat().st_size==0
assert raw['status']=='PARTIAL_ENGINEERING_NOT_SCORED' and 'fixture_ref'not in raw
assert raw['counters']['forbidden_model_or_archive_file_access_attempts']==6
assert all(raw['counters'][k]==0 for k in ['typed_model_initializations','NLI_forwards_attempted','NLI_forwards_completed','semantic_gold_decodes','training_calls','calibration_calls','paid_API_calls','GPU_calls'])
s=raw['shared_memory_snapshots'][0];assert s['stage']=='before_assets'and s['headroom_bytes']==2467368960 and s['memory_current_bytes']==14712500224 and s['memory_max_bytes']==17179869184 and s['headroom_bytes']<3*1024**3
assert outer['actual_worker_starts']==1 and outer['worker_exit_code']==2 and cli['exit_code']==17 and not outer['killed'] and outer['forced_reason']is None and cli['timed_out']is False and outer['errors']==[]
assert cli['actual_CLI_wall_seconds_including_interpreter_bootstrap_capture']<600 and outer['outer_wall_seconds_including_preflight_hash_init_native_capture_cleanup']<600
expected={175828:None,175829:41509423,175830:41509455};current={str(pid):proc(pid)for pid in expected};live=[]
for p in Path('/proc').iterdir():
 if p.name.isdigit():
  x=proc(int(p.name))
  if x and (x['pgid']in(175828,175830)or x['sid']in(175828,175830)) and x['state']not in('Z','X'):live.append(x)
assert not live
for pid,x in current.items():
 assert x is None or (x['state']in('Z','X')and x['FDSize']==0 and all(v==0 for v in x['statm']))
assert all(not(W/'private-run/engineering'/n).exists()for n in ['native-config.json','native-source.json','native-result.json','native-progress.jsonl','native-started.json'])
refs=[ref(p)for p in[rawp,exc,progress,W/'ROOT_ENGINEERING_CLI_LAUNCH.actual.v1.json',W/'ROOT_ENGINEERING_CLI_STARTED.actual.v1.json',W/'ROOT_ENGINEERING_CLI_WALL.actual.v1.json',W/'ENGINEERING_OUTER_ATTEMPT.actual.v1.json',W/'ENGINEERING_OUTER_EXECUTION.actual.v1.json',W/'ENGINEERING_WORKER_STARTED.actual.v1.json',P/'plan.json',P/'SOURCE_FREEZE.json',RT/'worker.py',RT/'supervisor.py',RT/'inherited_guards.py',RT/'support.py']]
report={'schema_version':1,'epoch':54,'kind':plan['kind'],'status':'REJECTED_RUNTIME_NOT_SCORED','independent_review_complete':True,'engineering_qualified':False,'benchmark_accepted':False,'official_goal_verified':False,'official_rank':None,'reviewer_independence':'Authored official/public-data metadata only; did not author engineering fixtures/candidate, runtime, reporter, publication code or execute the attempted engineering worker.','exact_SOURCE_commit':outer['source_commit'],'all_63_SOURCE_FREEZE_members_rehashed':True,'all_owned_processes_closed':True,'current_process_snapshots':current,'live_owned_process_group_or_session_members':live,'actual_worker_starts':1,'actual_native_corpus_batches_attempted':0,'actual_native_corpus_batches_completed':0,'zero_native_count_evidence':'Worker traceback/source order proves failure beforefixture load,tokenizer/catalog/BGE/native calls; workerprogress0B and no native launch/progress/result artifacts. Raw omits native/BGE/tokenizer counters; these independentderived zero counts do not rewrite the raw result.','actual_counts_independently_derived':{'tokenizer_initializations':0,'fragment_pair_tokenizations':0,'BGE_initializations':0,'BGE_forwards':0,'native_helper_starts':0,'native_queries':0,'engineered_contexts_completed':0},'raw_recorded_counters_unmodified':raw['counters'],'retained_unresolved_forbidden_open_attempts':{'count':6,'audit_rule':'Denied open events for suffixes.safetensors,.bin,.pt,.pth,.zip; incrementedbeforeRuntimeError atworker168-174.','actual_target_paths_or_stacktraces_recorded':False,'attribution':'UNPROVEN. Sixruntimeversionchecks occurafterhookinstallation andbeforeheadroom; a packagingZipFileprobe is a plausible explanation, not established actual-run evidence. Do not claim harmlessness or zero weight/archive attempts.','additional_qualification_blocker':'Frozenfinalgate requires zero forbiddenmodel/archivefileattempts. Any future distinctepoch needs narrowly evidenced guard diagnosis before model/native dispatch; no E54rerun authorized.'},'runtime_error':raw['errors'],'shared_cgroup_at_failure':s,'cgroup_scope':'Sharedsnapshot; notcandidateincrementalRAM orcauseattribution for otherprocesses/historicalOOMcounters.','timing':{'actual_CLI_wall_seconds_including_interpreter_bootstrap_capture':cli['actual_CLI_wall_seconds_including_interpreter_bootstrap_capture'],'supervisor_outer_wall_seconds':outer['outer_wall_seconds_including_preflight_hash_init_native_capture_cleanup'],'worker_wall_seconds':raw['timing']['worker_wall_seconds_including_init_cleanup'],'within600':True},'resources':raw['resources'],'forced_termination':False,'terminal_worker_wait_status':512,'quality_metrics':{'accuracy':None,'Brier':None,'NLL':None,'p50':None,'p95':None},'metric_scope':'No contexts/queries completed. No benchmark/scientificscore or latency percentiles manufactured.','planned_fixture_query_identities_retired_without_execution':plan['roles']['engineering'],'planned_fixture_document_identities_retired':plan['phase_roles']['engineering']['document_ids'],'fixture_ref_from_frozen_plan_not_raw':plan['fixtures'],'fixture_exposure_policy':'Alreadyauthored/frozen publicCC0engineeringidentities retired and never freshbenchmarkconfirmation; no furtherE54slot/rerun. Rawfixture_ref absentbecausebeforeloadfailure; report must retain null ratherthan manufactureadmission.','train_development_calibration_confirmation_roles':{k:plan['roles'][k]for k in['train','development','calibration','fresh_confirmation']},'used_confirmation_identities':[],'raw_or_report_private_payloads_released':False,'privacy_scope':'Exceptioncontains only public project/runtimepaths, workerline200/guardline31 and expliciterror; selectedsafeoperationalJSON contains no credentials/mailheaders/caseGold. Rawengineeringresult contains no semantic labels.','all_remaining_E54_scientific_slots_closed':True,'native104_champion_preserved':True,'promotion_or_new_publisher_submission_authorized':False,'paid_API_GPU_calls':0,'exact_evidence_refs':refs,'review_source_ref':ref(Path(__file__))}
p=O/'ENGINEERING_ACTUAL_REJECTION_AND_PHYSICAL_CLOSURE_INDEPENDENT.v1.json';b=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
print(json.dumps(ref(p)))
