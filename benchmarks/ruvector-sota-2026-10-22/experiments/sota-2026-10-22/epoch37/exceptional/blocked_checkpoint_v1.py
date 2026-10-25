"""Exceptional E37 failure metadata only. No worker, oracle, model or Git calls.
Frozen observer/evaluation/source bytes remain authoritative and unchanged.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,importlib,json,math,os,re
from pathlib import Path
P='experiments/sota-2026-10-22/';E=P+'epoch37/';A=P+'audit/epoch37/';X=E+'exceptional/'
W=Path('/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4')
KIND='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES';STATUS='EXCEPTIONAL_BLOCKED_CHECKPOINT'
SOURCE='a93a1d6922c8a14f356461fb383846157816c70b'
TREES={'root':'fe62b7d381fc04f6f05957101011c120801c5d10','bench':'632da9246ed32e46164c7e3cd46607e3f27f93b9','scope':'dae1d90376557c0a6a1bb71fb912ada288a5e230'}
FROZEN={'plan':{'path':E+'plan.json','bytes':59583,'sha256':'d9066f1c310514203af07f0eaa588a65ce4a72e8b621b657fa97645ab3338741'},
 'source_freeze':{'path':E+'source-freeze.json','bytes':38340,'sha256':'97dc7bc84afab4821de6daa1894b4bc3ce7a6bd9aaaeb802184ad7f1d46b6964'},
 'frozen_observer':{'path':E+'SUPERVISOR_OBSERVED_CLOSURE.json','bytes':1122,'sha256':'3ba8089c949d69d8794c30631896f5960807c5da222d8fe8e305fa032243d94d'},
 'frozen_evaluation':{'path':A+'qualification-replay.json','bytes':4856,'sha256':'883f5374ff9e976ccb6b880075dbdf4a00cd452fa2af040a477097bf7f686c73'},
 'stderr':{'path':X+'evidence/supervisor.stderr','bytes':1101,'sha256':'6046a50c895920a3a396c37fa3588fef70885239b56feb35a5fb98f398319fdc'}}
SUPPLEMENT_REF={'path':A+'exceptional-preworker-resolution-independent-v1.json','bytes':8433,'sha256':'d8164d037fe1cbdaebd17bc649dd6409625e12edb799d6ac86a8ec9238925db8'}
CONSISTENCY_REF={'path':A+'SUPPLEMENT_CONSISTENCY_REVIEW_v1.json','bytes':6451,'sha256':'b441ee88f162fcc92af677d9a1e95b632cbc73984e876a22cb5121a09dd548f9'}
FUTURE_REF={'path':A+'future-engineering-asset-repair-independent-v1.json','bytes':6174,'sha256':'268b499a814eadf70e80fc23e79638970009670ad75d68a2258f3fe004a46f31'}
PATCH_REF={'path':E+'future-source-review/asset-identity-fix/FUTURE_ONLY_SOURCE_INTEGRATION.patch','bytes':4707,'sha256':'f6daacb76d4fdd9129db70d1dfe83e432d2b8fd3bd1c7d524ed6af2f9572b29b'}
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None}
REMAINING=dict.fromkeys(('train','dev','calibration','confirmation','engineering','native_corpus_batches','paid_calls','GPU_calls','retry'),0)
ABSENT=[E+'ENGINEERING_ATTEMPT_RESERVATION.json',E+'SUPERVISOR_COMPLETION.json',E+'runs/engineering/execution.json',E+'runs/engineering/raw.json',E+'runs/engineering/raw.partial.json',E+'runs/engineering/ENGINEERING_CORPUS_ATTEMPT_RESERVATION.json',E+'runs/engineering']

def require(value,message):
 if not value:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def parse(path):
 def pairs(items):
  result={}
  for k,v in items:require(k not in result,'Duplicate JSON key');result[k]=v
  return result
 def floating(text):
  value=float(text);require(math.isfinite(value),'Nonfinite JSON float');return value
 return json.loads(path.read_bytes(),object_pairs_hook=pairs,parse_float=floating,parse_constant=lambda x:(_ for _ in()).throw(ValueError('Nonfinite JSON')))
def reference(root,name):
 require(isinstance(name,str)and name and not name.startswith('/')and '\\'not in name and all(v not in ('','.','..')for v in name.split('/')),'Unsafe public reference')
 file=root/name;require(file.is_file()and not any(p.is_symlink()for p in (file,*file.parents)),'Missing/nonregular/symlink public file: '+name)
 data=file.read_bytes();return {'path':name,'bytes':len(data),'sha256':sha(data)}
def checked(root,row):
 require(isinstance(row,dict)and set(row)=={'path','bytes','sha256'}and type(row['bytes'])is int,'Canonical exact public reference required')
 require(reference(root,row['path'])==row,'Actual public reference drift: '+row['path']);return row

def validate_replay(value):
 require(value.get('epoch')==37 and value.get('kind')==KIND and value.get('status')=='REJECTED_ENGINEERING_INTEGRITY','Retain frozen integrity rejection')
 require(value.get('checks_passed')is False and value.get('engineering_passed')is False and value.get('readiness_qualified')is False,'Never convert failed evaluation into success')
 require(value.get('actual_NLI_forwards')is None and value.get('final_derived_forecasts')is None and value.get('engineering_metrics')is None,'No invented scientific readouts/scores')
 require(value.get('used_confirmation_identities')==[]and value.get('confirmation')==[]and value.get('benchmark_accuracy')is None,'No confirmation or benchmark score')
 require(all(value.get(k)==v for k,v in FLAGS.items()),'Forbidden success/promotion claim')
 require(value.get('evidence',{}).get('execution')is None and value['evidence'].get('raw')is None,'No synthetic execution/raw receipt')
 require(value['evidence'].get('supervisor_observed_closure')==FROZEN['frozen_observer'],'Frozen false observer reference differs')
 return value

def validate_supplement(value):
 expected={'schema_version':1,'epoch':37,'kind':KIND,'status':'SOURCE_BOUND_PREWORKER_FAILURE_WITH_KERNEL_ZOMBIE_RESOLUTION',
  'checks_passed':True,'exceptional_preworker_resolution_passed':True,'retained_frozen_observer_physical_closure_passed':False,
  'retained_frozen_observer_unknown_physical_ownership':True,'frozen_evaluation_checks_passed':False,'logical_dispatch_slot_burned':1,
  'all_remaining_slots':0,'internal_operation_counts':'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'}
 require(isinstance(value,dict)and all(type(value.get(k))is type(v)and value[k]==v for k,v in expected.items()),'Exact separate exceptional supplement required; frozen false/UNKNOWN stays false/UNKNOWN')
 require(isinstance(value.get('evidence'),dict)and value['evidence'],'Independent supplement exact evidence required')
 require(value.get('published_source_commit')==SOURCE and value.get('source_trees')==TREES,'Supplement source parent/trees differ')
 physical=value.get('physical_kernel_observation',{});boundary=value.get('source_failure_boundary',{})
 require(physical.get('supervisor_pid')==112597 and physical.get('supervisor_startticks')==25316871 and physical.get('supervisor_state')=='Z'
  and physical.get('kernel_boot_id')=='4632fb06-b0ef-4df5-b72b-0e875bbad810'and physical.get('current_PID_namespace_inode')==4026532200
  and physical.get('statm_all_zero')is True and physical.get('kernel_FDSize_zero')is True and physical.get('status_fields',{}).get('FDSize')=='0'
  and physical.get('observed_fd_entries')is None and physical.get('fd_directory_observation')=='DENIED_EACCES'
  and physical.get('same_identity_before_and_after_scan')is True and physical.get('live_scoped_PGID_or_SID_members')==[]and physical.get('current_direct_children')==[],
  'Exact separately observed kernel Z/FDSize0 with honest EACCES and known scoped no-live-members required')
 require(boundary.get('frozen_source_and_stderr_consistent')is True and boundary.get('runtime_guard_top_level_before_worker_try')is True
  and boundary.get('worker_reservation_line')==220 and boundary.get('worker_Popen_line')==263
  and boundary.get('frozen_launch_statement_order')==[{'call':'C.verify_runtime','line':212},{'call':'reserve','line':220},{'call':'subprocess.Popen','line':263}],
  'Exact source-fenced pre-reservation/Popen failure boundary required')
 return value

def add_results(replay,metadata):
 validate_replay(replay);require('exceptional_blocked_checkpoint'not in replay,'Exceptional result already exists')
 result=copy.deepcopy(replay);result['exceptional_blocked_checkpoint']=copy.deepcopy(metadata)
 require(all(result[k]==v for k,v in replay.items()),'Every frozen EVALUATE field must remain unchanged');return result

def write_new(path,value):
 data=json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8')as target:target.write(data);target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def public_metadata_text(c,name,data):
 if name.endswith('.patch'):
  require(name==PATCH_REF['path']and len(data)==PATCH_REF['bytes']and sha(data)==PATCH_REF['sha256'],'Only the exact independently reviewed future-source patch is allowed')
  return c.public_text(name+'.txt',data)
 return c.public_text(name,data)

def collect_current(root,c):
 found={}
 for relative in c.ROOTS:
  directory=c.canonical(root/relative)
  if not directory.exists():continue
  c.directory(directory)
  for base,dirs,files in os.walk(directory,followlinks=False):
   dirs.sort();files.sort()
   for name in dirs:
    target=c.directory(Path(base)/name)
    require(not any(v.lower()in c.BANNED or v.lower().startswith('.env')for v in target.relative_to(root).parts),'Private/runtime directory in exceptional public roots')
   for name in files:
    file=Path(base)/name;relative=file.relative_to(root).as_posix();data=c.content(file);public_metadata_text(c,relative,data)
    require(relative not in found,'Duplicate exceptional public path');found[relative]=data
 require(found,'No current exceptional public metadata');return found

def blocked_transport_groups(changed,c,p):
 entries=[];blobs=[];groups=[];large={}
 for name,body in sorted(changed.items()):
  text=public_metadata_text(c,name,body);entry={'path':c.SCOPE+name,'mode':'100644','type':'blob'}
  if len(body)>p.LARGE_FILE_BYTES:
   payload={'content':text,'encoding':'utf-8'};require(len(c.encoded(payload))<p.MAX_BLOB_JSON,'Strict exceptional blob cap')
   identity=c.gitsha(body)
   if identity in large:require(large[identity]==body,'Unequal payloads share Git SHA')
   else:large[identity]=body;blobs.append((name,body,payload))
   entry['sha']=identity
  else:entry['content']=text
  require(len(c.encoded({'tree_elements':[entry]}))<p.MAX_TREE_JSON,'Strict single exceptional tree-entry cap');entries.append(entry)
 batch=[]
 for entry in entries:
  if batch and len(c.encoded({'tree_elements':batch+[entry]}))>=p.MAX_TREE_JSON:groups.append(batch);batch=[]
  batch.append(entry)
 if batch:groups.append(batch)
 return blobs,groups

def setup(args):
 require(args.scope.absolute()==W,'Exact exceptional owned scope required');root=W/'project'
 for row in FROZEN.values():checked(root,row)
 plan=parse(root/FROZEN['plan']['path']);pins={v['path']:v for v in plan['pins']};require(len(pins)==len(plan['pins']),'Duplicate frozen pins')
 for row in pins.values():checked(root,row)
 require(all(not(root/name).exists()for name in ABSENT),'Unexpected execution/raw/reservation/completion: halt, no exceptional shortcut')
 observer=parse(root/FROZEN['frozen_observer']['path'])
 require(observer.get('physical_supervisor_closed')is True and observer.get('physical_closure_passed')is False and observer.get('unknown_physical_ownership')is True and observer.get('execution')is None and observer.get('supervisor_completion')is None,'Retain exact frozen unresolved observer')
 require(observer.get('supervisor_identity')=={'pid':112597,'startticks':25316871,'pgid':112597,'sid':112597},'Wrong exact supervisor')
 replay=validate_replay(parse(root/FROZEN['frozen_evaluation']['path']))
 for row in replay['evidence'].values():
  if row is not None:checked(root,row)
 # Import only exact already frozen pure publication modules, after all pins.
 for name in ('publication_common_v1.py','phase_schema_v1.py','phase_receipts_v1.py','stage_publication_v1.py'):require(E+'publication/'+name in pins,'Pure frozen helper unpinned')
 sys.path.insert(0,str(root/(E+'publication')));c=importlib.import_module('publication_common_v1');p=importlib.import_module('stage_publication_v1');c.live_owner(W)
 protocol=reference(root,X+'PROTOCOL.v1.json');document=parse(root/protocol['path'])
 require(document.get('status')==STATUS and document.get('source_commit')==SOURCE and document.get('frozen')==FROZEN and document.get('remaining_slots')==REMAINING,'Exceptional protocol/source/frozen identities changed')
 require(args.source_review.startswith(A),'Independent source review must be canonical current audit metadata');review=reference(root,args.source_review);rv=parse(root/review['path'])
 require(rv.get('checks_passed')is True and rv.get('exceptional_source_only')is True and rv.get('scientific_authorization')==0,'Independent exceptional source-only review required')
 reviewed={row['path']:row for row in rv.get('files',[])}
 for name in ('blocked_checkpoint_v1.py','PROTOCOL.v1.json','publish_blocked_v1.js','test_blocked_checkpoint_v1.py'):
  row=reference(root,X+name);require(reviewed.get(row['path'])==row,'Exceptional helper absent from exact independent review: '+name)
 supplement=reference(root,args.supplement);require(supplement==SUPPLEMENT_REF,'Exact reviewed exceptional supplement required');sv=validate_supplement(parse(root/supplement['path']))
 checked(root,CONSISTENCY_REF);consistency=parse(root/CONSISTENCY_REF['path']);require(consistency.get('checks_passed')is True and consistency.get('scientific_authorization')==0 and consistency.get('supplement')==SUPPLEMENT_REF,'Separate metadata-only consistency report required')
 for row in sv['evidence'].values():
  if isinstance(row,dict)and set(row)=={'path','bytes','sha256'}:checked(root,row)
 require(sv['evidence'].get('frozen_observer')==FROZEN['frozen_observer']and sv['evidence'].get('frozen_evaluation')==FROZEN['frozen_evaluation']and sv['evidence'].get('plan')==FROZEN['plan']and sv['evidence'].get('supervisor_stderr')==FROZEN['stderr'],'Supplement does not bind frozen rejection/source trace')
 future=reference(root,args.future_review);require(future==FUTURE_REF,'Exact sealed independent future-source review required');fv=parse(root/future['path'])
 require(fv.get('checks_passed')is True and fv.get('future_source_only')is True and fv.get('applied_to_frozen_E37')is False and fv.get('E37_retry_authorized')is False and fv.get('actual_model_payload_reads_current_guard_model_native_tokenizer_actual12_EVALUATE_BIND_newdispatch_or_external_mutations_by_auditor')==0,'Future guard repair must remain independently reviewed source-only')
 for row in fv.get('approved_public_source_entries',[]):checked(root,row)
 return root,c,p,plan,replay,protocol,review,supplement,future

def metadata(protocol,review,supplement,future):
 return {'status':STATUS,**FLAGS,'publication_scope':'Failure metadata and independently scoped physical resolution only; no accepted experiment or ordinary closure override.',
  'source_commit':SOURCE,'protocol':protocol,'source_review':review,'supplement_consistency_review':CONSISTENCY_REF,'independent_preworker_resolution':supplement,'future_source_guard_review':future,
  'frozen_evaluation':FROZEN['frozen_evaluation'],'frozen_observer':FROZEN['frozen_observer'],'frozen_evaluated_integrity_checks_passed':False,
  'frozen_physical_closure_passed':False,'frozen_unknown_physical_ownership':True,'exceptional_preworker_physical_resolution_passed':True,
  'logical_dispatch_slots_burned':1,'verified_launcher_starts':1,'internal_operation_counts':'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT',
  'actual_NLI_forwards':None,'final_derived_forecasts':None,'corpus_batches_attempted':None,'corpus_batches_completed':None,'model_initializations':None,
  'actual_worker_start_status':'UNKNOWN_NO_CAPTURED_EXECUTION','actual_resources':None,'remaining_slots':copy.deepcopy(REMAINING),'used_confirmation_identities':[],
  'cumulative_scope':{'known_prior_corpus_attempts':33,'known_prior_completed_corpus_batches':31,'current_corpus_attempts':None,'current_completed_corpus_batches':None,'bounded_outer_process_attempts':38,'legacy_dedicated_qualification_attempts':6,'epoch37_xxlarge_reader_initialization_attempts':None,'official_benchmark_HTTP_successes':894,'official_benchmark_HTTP_failures':2},
  'reason':'One actual dispatcher slot was burned. Frozen launcher source asset validation failed before a phase execution receipt. The frozen observer and EVALUATE remain unresolved/rejected. Separate source-bound traceback and kernel evidence resolve only exceptional preworker physical ownership. No retry or measurement is claimed.'}

def results(args):
 root,c,p,plan,replay,protocol,review,supplement,future=setup(args);info=metadata(protocol,review,supplement,future)
 for name in ('RESULTS.json','REJECTION_LEDGER.json','USED_CONFIRMATION_IDENTITIES.json','LEARNINGS.json','SOURCE_MANIFEST.json','EPOCH_MANIFEST.json'):require(not(root/(E+name)).exists(),'Immutable exceptional outputs already exist; no replay')
 write_new(root/(E+'RESULTS.json'),add_results(replay,info));rr=reference(root,E+'RESULTS.json')
 prior=parse(W/'controls-source/CONTINUATION.json');checked(root,prior['rejection_ledger']);ledger=copy.deepcopy(parse(root/prior['rejection_ledger']['path']))
 require(not any(isinstance(v,dict)and v.get('epoch')==37 for v in ledger.get('rejections',[])),'Epoch already rejected')
 ledger['rejections'].append({'epoch':37,'status':STATUS,'scientific_status':replay['status'],'reason':info['reason'],'results':rr})
 ledger['epoch37_exceptional_blocked_checkpoint']=info;ledger['epoch37_budget']={'logical_dispatch_slots_burned':1,'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'paid_GPU_remaining':0,'all_unspent_slots_permanently_closed':True,'actual_internal_counts':'UNKNOWN'}
 write_new(root/(E+'REJECTION_LEDGER.json'),ledger)
 write_new(root/(E+'USED_CONFIRMATION_IDENTITIES.json'),{'schema_version':1,'epoch':37,'kind':KIND,'status':STATUS,'used_confirmation_identities':[],'train':[],'dev':[],'calibration':[],'confirmation':[],'engineering_publicly_exposed_identities':plan['engineering_ids'],'planned_engineering_identities':plan['engineering_ids'],'actual_measured_identities':[],'measured_identity_scope':'No empirical readout records exist; source-inferred prePopen failure is separate from UNKNOWN captured operation counts. All12source-exposed engineering identities remain exposed forever.','engineering_candidate_execution_counts':'UNKNOWN_NO_RAW_RECEIPT','benchmark_partition_unchanged':{'exposed':325,'unused':74,'protected':24},'actual_oracle_labels_read_by_scorer':0})
 write_new(root/(E+'LEARNINGS.json'),{'schema_version':1,'epoch':37,'kind':KIND,'status':STATUS,'scientific_status':replay['status'],'scientific_acceptance':False,'measured_accuracy':None,'proper_scores':None,'measured_identities':[],'planned_source_exposed_engineering_identities_forever':plan['engineering_ids'],'used_confirmation_identities':[],'captured_NLI_forward_count':'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT','source_inference_scope':'Exact frozen traceback and statement order place failure before phase reserve/Popen; this does not synthesize empirical operation counters or replace frozen observer uncertainty.','material_blocker':'Original expanded payload Git-blob identity was compared against an upstream LFS pointer identity by frozen source asset admission. The dispatch slot is burned without a completed scientific corpus.','future_source_review':future,'future_steps_proposed_not_executed':['Preserve native104 champion and all325DEV/74unused/24protected identities.','Keep separate immutable expected asset catalog; preserve Git pointer versus expanded payload identity types.','Require independent source review and an unstubbed full real-asset guard admission before any new frozen epoch; do not infer full admission from a metadata/unit fixture.','Create a new epoch and genuinely unused authorized confirmation only after frozen development gates and eligible licensed model/data/provenance. No E37 retry, recycled fresh confirmation, paid/GPU authorization or new publisher submission.'],'budget_authorized_future_paid_GPU':0,'supplement':supplement,'supplement_consistency_review':CONSISTENCY_REF})
 return {'status':STATUS,'results':rr,'every_frozen_replay_field_preserved':True,'all_slots_zero':True,'Git_model_native_calls':0}

def checked_binding(root,args,replay):
 result=parse(root/(E+'RESULTS.json'));require(all(result.get(k)==v for k,v in replay.items()),'Frozen replay was changed')
 bound=reference(root,args.binding);binding=parse(root/bound['path'])
 require(binding.get('binding_scope')=='EXCEPTION_ONLY_METADATA_IDENTITY'and binding.get('frozen_evaluation_checks_passed')is False
  and binding.get('publication_binding_checks_passed')is True and binding.get('checks_passed')is True,'Separate exception-only metadata binding must retain false evaluated integrity')
 require(binding.get('evidence',{}).get('results')==reference(root,E+'RESULTS.json')and binding['evidence'].get('qualification_replay')==FROZEN['frozen_evaluation'],'Exact exception-only binding references required')
 report=reference(root,args.acceptance);value=parse(root/report['path'])
 require(value.get('checks_passed')is True and value.get('exceptional_checkpoint_publication_allowed')is True and value.get('engineering_passed')is False and value.get('frozen_evaluation_checks_passed')is False,'Independent exceptional publication report required')
 require(value.get('results')==reference(root,E+'RESULTS.json')and value.get('binding')==bound and value.get('independent_preworker_resolution')==result['exceptional_blocked_checkpoint']['independent_preworker_resolution'],'Exceptional acceptance evidence drift')
 return result,bound,report

def manifest(args):
 root,c,p,plan,replay,protocol,review,supplement,future=setup(args);result,bound,report=checked_binding(root,args,replay)
 require(result['exceptional_blocked_checkpoint']==metadata(protocol,review,supplement,future),'Exceptional result scope drift')
 def files():return [dict(path=name,bytes=len(body),sha256=sha(body))for name,body in sorted(collect_current(root,c).items())]
 require(not(root/(E+'SOURCE_MANIFEST.json')).exists()and not(root/(E+'EPOCH_MANIFEST.json')).exists(),'Immutable manifest already exists')
 write_new(root/(E+'SOURCE_MANIFEST.json'),{'schema_version':1,'epoch':37,'kind':KIND,'status':STATUS,'source_commit':SOURCE,'plan':FROZEN['plan'],'source_freeze':FROZEN['source_freeze'],'files':files(),'scope':'All public metadata before these two nonrecursive manifests. Frozen source and failed observer/evaluation remain unchanged; no project writes after EPOCH seal.'})
 value={'schema_version':1,'epoch':37,'kind':KIND,'status':STATUS,'scientific_status':replay['status'],**FLAGS,'goal_verified':False,'benchmark_accuracy':None,'engineering_passed':False,'readiness_qualified':False,'diagnostic_qualified':False,'evaluated_integrity_checks_passed':False,'exceptional_metadata_publication_checks_passed':True,'all_slots_closed':True,'phase_remaining':REMAINING,'used_confirmation_identities':[],'confirmation':[],
  'source_commit':SOURCE,'plan':FROZEN['plan'],'source_freeze':FROZEN['source_freeze'],'frozen_observer':FROZEN['frozen_observer'],'frozen_evaluation':FROZEN['frozen_evaluation'],'results':reference(root,E+'RESULTS.json'),'rejection_ledger':reference(root,E+'REJECTION_LEDGER.json'),'used_identities':reference(root,E+'USED_CONFIRMATION_IDENTITIES.json'),'learnings':reference(root,E+'LEARNINGS.json'),'source_manifest':reference(root,E+'SOURCE_MANIFEST.json'),'exception_only_metadata_binding':bound,'independent_report':report,'exceptional_blocked_checkpoint':result['exceptional_blocked_checkpoint'],'files':files()}
 write_new(root/(E+'EPOCH_MANIFEST.json'),value)
 return {'status':STATUS,'manifest':reference(root,E+'EPOCH_MANIFEST.json'),'all_slots_zero':True,'Git_model_native_calls':0}

def validated_seal(root,c,args,replay,protocol,review,supplement,future):
 result,bound,report=checked_binding(root,args,replay);info=metadata(protocol,review,supplement,future)
 require(result.get('exceptional_blocked_checkpoint')==info,'Exceptional metadata drift')
 manifest=parse(root/(E+'EPOCH_MANIFEST.json'));require(manifest.get('status')==STATUS and manifest.get('scientific_status')==replay['status']and manifest.get('evaluated_integrity_checks_passed')is False and manifest.get('phase_remaining')==REMAINING and manifest.get('used_confirmation_identities')==[]and all(manifest.get(k)==v for k,v in FLAGS.items())and manifest.get('benchmark_accuracy')is None and manifest.get('goal_verified')is False and manifest.get('engineering_passed')is False and manifest.get('all_slots_closed')is True and manifest.get('exceptional_blocked_checkpoint')==info,'Sealed exceptional manifest drift')
 require(manifest.get('independent_report')==report and manifest.get('exception_only_metadata_binding')==bound and manifest.get('results')==reference(root,E+'RESULTS.json'),'Sealed exceptional report/results drift')
 current=collect_current(root,c);wanted={name:{'path':name,'bytes':len(body),'sha256':sha(body)}for name,body in current.items()}
 require({r['path']:r for r in manifest['files']}=={name:row for name,row in wanted.items()if name!=E+'EPOCH_MANIFEST.json'},'No project additions/edits allowed after exceptional EPOCH seal')
 sm=parse(root/(E+'SOURCE_MANIFEST.json'))
 require({r['path']:r for r in sm['files']}=={name:row for name,row in wanted.items()if name not in {E+'EPOCH_MANIFEST.json',E+'SOURCE_MANIFEST.json'}},'Nonrecursive source manifest differs')
 return manifest,current

def controls(args):
 root,c,p,plan,replay,protocol,review,supplement,future=setup(args);m,current=validated_seal(root,c,args,replay,protocol,review,supplement,future)
 require(args.out.absolute()==W/'controls-blocked','Exact new blocked controls directory required');output=c.new_output(args.out,(root,W/'kit',W/'controls-source'))
 old=c.parse(W/'controls-source/CHECKPOINT_MANIFEST.json');prior=c.parse(W/'controls-source/CONTINUATION.json');active=c.parse(W/'controls-source/ACTIVE_RUN.json')
 require(prior.get('epoch37_frozen_study')=={'plan':FROZEN['plan'],'source_freeze':FROZEN['source_freeze']}and active.get('state')=='EPOCH37_SOURCE_FROZEN_ENGINEERING_PENDING_ADMISSION','Exact actual SOURCE controls required')
 c.check_history(root,old);cp=copy.deepcopy(old);rows=c.cp_rows(cp)
 for name,body in sorted(current.items()):
  row={'path':name,'bytes':len(body),'sha256':sha(body)}
  if name in rows:require(rows[name]==row,'Published SOURCE byte changed: '+name)
  else:cp['project_files'].append(row);rows[name]=row
 final={'status':STATUS,**FLAGS,'manifest':reference(root,E+'EPOCH_MANIFEST.json'),'results':reference(root,E+'RESULTS.json'),'scientific_status':replay['status'],'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True,'evaluated_integrity_checks_passed':False,'exceptional_preworker_resolution':supplement}
 cp['epoch37_exceptional_blocked_checkpoint']={'source_commit':SOURCE,'status':STATUS,'manifest':final['manifest']}
 cont=copy.deepcopy(prior);require('epoch37_final'not in cont,'Exceptional final already present');cont['epoch37_final']=final;cont['epoch37_exceptional_blocked_checkpoint']=m['exceptional_blocked_checkpoint'];cont['rejection_ledger']=reference(root,E+'REJECTION_LEDGER.json')
 epoch={'epoch':37,'kind':KIND,**FLAGS,'status':STATUS,'scientific_status':replay['status'],'manifest':final['manifest'],'results':final['results'],'engineering_passed':False,'readiness_qualified':False,'diagnostic_qualified':False}
 require(not any(isinstance(v,dict)and v.get('epoch')==37 for v in cont.get('epochs',[])),'Epoch already summarized');cont.setdefault('epochs',[]).append(epoch)
 observed=copy.deepcopy(cont.get('execution_observed',{}));require('epoch37_exceptional_blocked_execution'not in observed,'Blocked execution already recorded')
 observed.update(epoch37_exceptional_blocked_execution=m['exceptional_blocked_checkpoint'],epoch37_cumulative_corpus_attempts=None,epoch37_cumulative_completed_corpus_batches=None,epoch37_cumulative_bounded_native_process_attempts=38,epoch37_corpus_count_scope='Prior33attempts/31complete remain known lower bounds. Current corpus and backend operations UNKNOWN without captured execution/raw. One reserved and verified outer launcher brings37 to38 bounded process attempts; no extra native qualification slot or invented reader init.')
 cont['execution_observed']=observed;budget=copy.deepcopy(cont.get('cumulative_budget_ledger',{}));budget['epoch37_budget']=parse(root/(E+'REJECTION_LEDGER.json'))['epoch37_budget'];cont['cumulative_budget_ledger']=budget
 old_priority=cont.get('next_research_priority','');cont['next_research_priority']='E37 blocked once before phase capture at frozen original asset Git-identity validation; dispatch slot permanently burned. Future work is SOURCE REVIEW ONLY until a new frozen epoch: independently verified typed Git-blob versus LFS pointer/payload guard repair, a separate immutable expected catalog plus UNSTUBBED FULL REAL-ASSET GUARD admission before a new epoch freeze, exact original licenses/lineage, and unchanged zero paid/GPU cap. Do not retry E37, infer accuracy or consume confirmation. Retain prior research direction: '+str(old_priority)
 active=copy.deepcopy(active);active.update(state='EPOCH37_EXCEPTIONAL_BLOCKED_CLOSED',work_active=False,experiments_active=False,checkpoint_parent=SOURCE,native_allowed=0,conditional_train_allowed=0,conditional_dev_allowed=0,conditional_engineering_allowed=0,confirmation_allowed=0,conditional_confirmation_allowed=0,all_unspent_epoch37_slots_permanently_closed=True,OS_lock_held=True,OS_lock_release_pending=True,exceptional_preworker_resolution=supplement,frozen_observer_physical_closure_passed=False,frozen_observer_unknown_physical_ownership=True,instruction='Blocked failure-metadata checkpoint only. Frozen false closure/evaluation and UNKNOWN backend counts retained. All E37 scientific/retry/paid/GPU slots permanently zero; no promotion/submission. Release guardian only after independent actual blocked checkpoint readback.')
 cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['checkpoint_manifest_sha256']=sha(c.encoded(cp,pretty=True));cont['prior_published_base_commit']=SOURCE
 p.preserve_history(prior,cont,p.FINAL_MUTABLE)
 output.mkdir(mode=0o700)
 for name,value in [('CHECKPOINT_MANIFEST.json',cp),('CONTINUATION.json',cont),('ACTIVE_RUN.json',active)]:c.write(output/name,c.encoded(value,pretty=True))
 if args.reviewed_files:
  dest=c.new_output(args.reviewed_files,(root,W/'kit',output));c.write(dest,c.encoded({'files':[{'path':name,'bytes':len(body),'sha256':sha(body)}for name,body in sorted(current.items())]},pretty=True))
 return {'status':STATUS,'controls':str(output),'CP_rows':len(rows),'CP_sha256':cont['checkpoint_manifest_sha256'],'all_slots_zero':True,'Git_model_native_calls':0}

def stage(args):
 root,c,p,plan,replay,protocol,review,supplement,future=setup(args);m,current=validated_seal(root,c,args,replay,protocol,review,supplement,future)
 output=c.new_output(args.out,(root,W/'kit',W/'controls-source',W/'controls-blocked'));require(output==W/'stage-blocked','Exact isolated blocked stage required')
 proof=c.parse(args.parent_readback);p.check_phase_main(proof,args.expected_main);p.check_readback(proof,'final',SOURCE,tuple(TREES[k]for k in ('root','bench','scope')))
 beforedata=c.content(W/'stage-source/expected-leaves.json');require(sha(beforedata)=='bffb99e4a760c522c2e7705f22cea4715dcefa9ddc9af0490d7d2154c1e8924c','Exact actual SOURCE expected map required');before=p.tuple_map(c.loads(beforedata))
 require(len(before)==5894 and p.scope_tree_sha(before)==TREES['scope'],'Actual SOURCE full tuple identity changed')
 oldcp=c.parse(W/'controls-source/CHECKPOINT_MANIFEST.json');newcp=c.parse(W/'controls-blocked/CHECKPOINT_MANIFEST.json');oldrows=c.cp_rows(oldcp);newrows=c.cp_rows(newcp)
 require(all(newcp.get(k)==v for k,v in oldcp.items()if k!='project_files')and all(newrows.get(k)==v for k,v in oldrows.items()),'Full old SOURCE CP metadata/rows must remain unchanged')
 require(set(newcp)==set(oldcp)|{'epoch37_exceptional_blocked_checkpoint'}and set(newrows)==set(oldrows)|set(current),'Exceptional checkpoint must cover only old/source plus all current roots')
 for name,body in current.items():require(newrows[name]=={'path':name,'bytes':len(body),'sha256':sha(body)},'New current CP mismatch: '+name)
 prior=p.controls_at(W/'controls-source');bodies=p.controls_at(W/'controls-blocked');cont=c.loads(bodies['CONTINUATION.json']);active=c.loads(bodies['ACTIVE_RUN.json']);p.preserve_history(c.loads(prior['CONTINUATION.json']),cont,p.FINAL_MUTABLE)
 oldcont=c.loads(prior['CONTINUATION.json']);oldactive=c.loads(prior['ACTIVE_RUN.json'])
 require(cont.get('epochs',[])[:-1]==oldcont.get('epochs',[])and cont['epochs'][-1].get('epoch')==37 and cont['epochs'][-1].get('status')==STATUS,'Append one blocked epoch without historical epoch edits')
 require(all(cont.get('execution_observed',{}).get(k)==v for k,v in oldcont.get('execution_observed',{}).items())and all(k in oldcont.get('execution_observed',{})or k.startswith('epoch37_')for k in cont.get('execution_observed',{})),'Historical execution counters changed')
 require(active.get('physical_owner')==oldactive.get('physical_owner')and active.get('checkpoint_parent')==SOURCE and active.get('OS_lock_release_pending')is True and active.get('experiments_active')is False,'Blocked control owner/source identity differs')
 oldledger=parse(root/oldcont['rejection_ledger']['path']);newledger=parse(root/(E+'REJECTION_LEDGER.json'))
 require(newledger['rejections'][:-1]==oldledger['rejections']and newledger['rejections'][-1].get('epoch')==37 and newledger['rejections'][-1].get('status')==STATUS and all(newledger.get(k)==v for k,v in oldledger.items()if k!='rejections')and all(k in oldledger or k.startswith('epoch37_')for k in newledger),'Historical rejection ledger changed')
 require(cont.get('epoch37_final',{}).get('manifest')==reference(root,E+'EPOCH_MANIFEST.json')and cont['epoch37_final'].get('status')==STATUS and cont['active_run']==dict(active,path='ACTIVE_RUN.json')and cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json']),'Blocked control projection differs')
 require(active.get('work_active')is False and active.get('state')=='EPOCH37_EXCEPTIONAL_BLOCKED_CLOSED'and active.get('OS_lock_held')is True and all(type(active.get(k))is int and active[k]==0 for k in ('native_allowed','conditional_train_allowed','conditional_dev_allowed','conditional_engineering_allowed','confirmation_allowed','conditional_confirmation_allowed')),'All blocked scientific allowances must be exactly zero')
 expected=copy.deepcopy(before)
 for name,body in prior.items():require(before.get(name)==p.leaf(name,body),'Actual SOURCE prior control mismatch')
 for name,body in {**current,**bodies}.items():
  row=p.leaf(name,body)
  if name in before and name not in c.CONTROLS:require(before[name]==row,'Frozen/historical SOURCE tuple changed: '+name)
  expected[name]=row
 p.checked_review(c.parse(args.reviewed_files),current);c.check_history(root,oldcp)
 c.check_transport(root,c.parse(W/'kit/CONTINUATION.json'),cont,newrows,set(expected),kit=W/'kit')
 changed={name:body for name,body in {**current,**bodies}.items()if before.get(name)!=expected[name]};require(c.CONTROLS<=set(changed),'All three controls must be updated')
 blobs,groups=blocked_transport_groups(changed,c,p);output.mkdir(mode=0o700);(output/'transport').mkdir(mode=0o700)
 meta={'schema_version':1,'stage':'blocked','status':STATUS,'prior_controls_name':'controls-source','scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'source_plan_sha256':FROZEN['plan']['sha256'],'publication_parent':SOURCE,'read_only_main_observation':args.expected_main,'exceptional_manifest':reference(root,E+'EPOCH_MANIFEST.json'),'exceptional_protocol':protocol,'exceptional_source_review':review,'CAS_guards':{'expected_root_tree':TREES['root'],'expected_benchmarks_tree':TREES['bench'],'expected_scope_tree':TREES['scope'],'expected_branch_sha':SOURCE,'force':False},'prior_Git_leaves':len(before),'expected_Git_leaves':len(expected),'old_CP_rows':len(oldrows),'new_CP_rows':len(newrows),'old_CP_metadata_and_source_tuples_preserved':True,'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[],'changed_files':[{'path':name,'bytes':len(body),'sha256':sha(body),'git_blob_sha1':c.gitsha(body)}for name,body in sorted(changed.items())]}
 for i,(name,body,payload)in enumerate(blobs):
  file='transport/blob-%03d.json'%i;data=c.encoded(payload);c.write(output/file,data);meta['large_blob_requests'].append({'path':name,'file':file,'bytes':len(data),'sha256':sha(data),'expected_blob_sha1':c.gitsha(body)})
 for i,group in enumerate(groups):
  file='transport/tree-%03d.json'%i;data=c.encoded({'tree_elements':group});require(len(data)<p.MAX_TREE_JSON,'Strict tree request cap');c.write(output/file,data);meta['create_tree_groups'].append({'file':file,'bytes':len(data),'sha256':sha(data),'entries':len(group)})
 leaves=c.encoded({'schema_version':1,'scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'files':[expected[k]for k in sorted(expected)]});c.write(output/'expected-leaves.json',leaves);meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':sha(leaves),'count':len(expected)};c.write(output/'metadata.json',c.encoded(meta,pretty=True))
 return {'status':STATUS,'publication_parent':SOURCE,'stage':str(output),'CP_rows':len(newrows),'expected_Git_leaves':len(expected),'Git_model_native_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('mode',choices=('results','manifest','controls','stage'));cli.add_argument('--scope',type=Path,default=W)
 for name in ('source-review','supplement','future-review'):cli.add_argument('--'+name,required=True)
 for name in ('binding','acceptance'):cli.add_argument('--'+name)
 for name in ('out','reviewed-files','parent-readback'):cli.add_argument('--'+name,type=Path)
 cli.add_argument('--expected-main');args=cli.parse_args()
 print(json.dumps(globals()[args.mode](args),sort_keys=True))
