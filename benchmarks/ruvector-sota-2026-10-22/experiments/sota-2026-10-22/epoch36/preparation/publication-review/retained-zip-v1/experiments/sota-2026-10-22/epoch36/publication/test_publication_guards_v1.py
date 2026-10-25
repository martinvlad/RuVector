"""Metadata/codec/phase tamper tests only; no models, sockets or Git calls."""
import sys
sys.dont_write_bytecode=True
import base64,copy,hashlib,importlib.util,json,math,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import publication_common_v1 as c
import phase_schema_v1 as s
import phase_receipts_v1 as r
import stage_publication_v1 as p

SCRATCH=Path(tempfile.gettempdir())

def bytes_json(value):return (json.dumps(value,separators=(',',':'),sort_keys=True)+'\n').encode()

class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='guards-',dir=SCRATCH);self.root=Path(self.tmp.name)
  self.put(s.PLAN_PATH,{'epoch':36});self.put(s.FREEZE_PATH,{'epoch':36});self.planref=c.ref(self.root,s.PLAN_PATH)
 def tearDown(self):self.tmp.cleanup()
 def put(self,path,value):
  f=self.root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(bytes_json(value));pin=c.ref(self.root,path)
  if path==s.E+'runs/engineering/execution.json':self.dispatch_fixture(pin)
  return pin
 def dispatch_fixture(self,execution=None):
  claim={'schema_version':1,'epoch':36,'kind':s.KIND,'phase':'engineering','plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
  dr=self.put(s.DISPATCH_PATHS['reservation'],claim);identity={'pid':111,'startticks':222,'pgid':111,'sid':111}
  da=self.put(s.DISPATCH_PATHS['attempt'],dict(claim,**identity,verified_launcher_start=True,uncertain_launcher_start=False))
  sc=self.put(s.DISPATCH_PATHS['completion'],{'epoch':36,'kind':s.KIND,'phase':'engineering','status':'ABOUT_TO_EXIT','intended_exit_code':0,'supervisor_identity':identity})
  proof={'schema_version':1,'epoch':36,'kind':s.KIND,'phase':'engineering','source_plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,
   'dispatch_reservation':dr,'dispatch_attempt':da,'supervisor_completion':sc,'execution':execution,'supervisor_identity':identity,'physical_supervisor_absent':True,'observed_supervisor_state':None,'physical_supervisor_closed':True,'owned_worker_group_members':[],'unknown_physical_ownership':False,'physical_closure_passed':True}
  if execution is None:proof.update(owned_worker_group_members=None,unknown_physical_ownership=True,physical_closure_passed=False)
  self.put(s.DISPATCH_PATHS['closure'],proof)

 def rows(self):return {x.relative_to(self.root).as_posix():c.ref(self.root,x.relative_to(self.root).as_posix()) for x in self.root.rglob('*') if x.is_file()}
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError)):fn(*args)
 def capture(self,phase='engineering',partial=False):
  self.put(s.PHASE_RESERVATIONS[phase],{'phase':phase,'plan_sha256':self.planref['sha256']})
  cr={}
  for role,path in s.CORPUS_RESERVATION_PATHS.items():cr[role]=self.put(path,{'epoch':36,'kind':s.KIND,'phase':'engineering','role':role,'plan_sha256':self.planref['sha256'],'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False})
  raw={'corpus_reservations':cr,'epoch':36,'phase':phase,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'data_roles':copy.deepcopy(s.ROLES),'plan_sha256':self.planref['sha256'],
   'status':'COMPLETED_ENGINEERING_AWAITING_INDEPENDENTENT_AUDIT' if phase=='engineering' else 'COMPLETED_ENGINEERING_AWAITING_INDEPENDENTENT_AUDIT',
   'counters':{'training_steps':0,'optimizer_steps':0,'NLI_forward_calls_completed':54,'xxlarge_model_initializations_attempted':1,'model_initializations_attempted':2,'corpus_batches_attempted':1,'corpus_batches_completed':1,'paid_calls':0,'GPU_calls':0},'errors':[]}
  selected='raw.partial.json' if partial else 'raw.json';pin=self.put(s.E+'runs/'+phase+'/'+selected,raw)
  execution={'corpus_reservations':cr,'corpus_reservation_count':1,'epoch':36,'phase':phase,'kind':s.KIND,'status':'WORKER_FAILED_OR_TIMEOUT' if partial else 'WORKER_COMPLETED',
   'worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,'exit_code':-9 if partial else 0,
   'owned_live_group_members':[],'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':1.0,'children_user_seconds':1.0,'children_system_seconds':0.0,'largest_child_peak_RSS_bytes':1000,'CPU_affinity':[0,1],
   'allowed_further_phase_workers':0,'cleanup_errors':[],'launcher_error':None,'source_plan_unchanged':True,'raw_closure_invariants':{'all_complete':not partial},
   'raw_bytes':None if partial else pin['bytes'],'raw_sha256':None if partial else pin['sha256'],'partial_raw_bytes':pin['bytes'] if partial else None,'partial_raw_sha256':pin['sha256'] if partial else None,
   'raw_operation_counters':raw['counters'],'raw_operation_counters_source':selected,'operation_counts_complete':not partial,'backend_execution_since_checkpoint':'UNKNOWN' if partial else 'NOT_APPLICABLE_FINAL_RAW'}
  self.put(s.E+'runs/'+phase+'/execution.json',execution)
  return raw,execution,pin
 def test_duplicate_and_nonfinite_JSON(self):
  self.reject(c.loads,b'{"a":1,"a":2}');self.reject(c.loads,b'{"a":NaN}')
 def test_scope_paths_binary_private(self):
  for path in ('../x','/x','a/../b','a\\b'):self.reject(c.relative,path)
  self.reject(c.public_text,s.E+'x.txt',b'a\0b');self.reject(c.public_text,s.E+'secret.txt',('gh'+'p_'+'x'*40).encode());self.reject(c.public_text,s.E+'key.txt',('s'+'k-'+'x'*32).encode())
 def test_unstarted_phase_resources_unknown(self):
  value=r.phase_evidence(self.root,'engineering',self.planref)
  self.assertEqual(value['actual']['worker_attempts'],0);self.assertIsNone(value['actual']['resources']);self.assertIsNone(value['actual']['errors'])
 def test_reservation_cannot_be_erased_as_unstarted(self):
  self.put(s.PHASE_RESERVATIONS['engineering'],{'phase':'engineering','plan_sha256':self.planref['sha256']});self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_complete_train_phase(self):
  self.capture();value=r.phase_evidence(self.root,'engineering',self.planref,self.rows());self.assertTrue(r.phase_completed(value));self.assertEqual(value['actual']['NLI_forward_calls_completed'],54)
 def test_reserved_uncertain_start_burns_one(self):
  _,e,_=self.capture(partial=True);e.update(verified_worker_starts=0,uncertain_start=True,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,partial_raw_bytes=None,partial_raw_sha256=None)
  (self.root/(s.E+'runs/engineering/raw.partial.json')).unlink();self.put(s.E+'runs/engineering/execution.json',e)
  value=r.phase_evidence(self.root,'engineering',self.planref);self.assertEqual(value['actual']['worker_attempts'],1);self.assertEqual(value['actual']['verified_worker_starts'],0);self.assertIsNone(value['actual']['errors'])
 def unknown_capture(self):
  _,e,_=self.capture(partial=True)
  (self.root/(s.E+'runs/engineering/raw.partial.json')).unlink()
  e.update(verified_worker_starts=0,uncertain_start=True,exit_code=None,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,
   partial_raw_bytes=None,partial_raw_sha256=None,owned_live_group_members=None,owned_live_processes_closed=None,
   owned_process_closure_observation='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF',worker_identity_source='UNKNOWN',worker_identity=None,recovered_preexec_child_identity=None)
  self.put(s.E+'runs/engineering/execution.json',e)
  proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(owned_worker_group_members=None,unknown_physical_ownership=True,physical_closure_passed=False);self.put(s.DISPATCH_PATHS['closure'],proof)
  return r.phase_evidence(self.root,'engineering',self.planref)
 def test_failed_unknown_physical_closure_preserved(self):
  value=self.unknown_capture();self.assertIsNone(value['actual']['owned_live_processes_closed']);self.assertIsNone(value['actual']['owned_live_group_members']);self.assertEqual(value['actual']['worker_attempts'],1)
  total=r.aggregate_actual(value);self.assertIsNone(total['owned_live_processes_closed'])
 def test_unknown_physical_closure_cannot_complete(self):
  self.assertFalse(r.phase_completed(self.unknown_capture()))
 def test_FINAL_unknown_physical_closure_refused(self):
  value=self.unknown_capture();total=r.aggregate_actual(value);self.reject(r.require_final_physical_closure,total)
 def test_known_partial_counters_cannot_be_hidden(self):
  _,e,_=self.capture(partial=True);e.update(raw_operation_counters_source='UNKNOWN',raw_operation_counters=None)
  self.put(s.E+'runs/engineering/execution.json',e);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_wrong_phase_receipt_rejected(self):
  raw,e,_=self.capture();e['phase']='train';self.put(s.E+'runs/engineering/execution.json',e);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_partial_not_completed(self):
  self.capture(partial=True);value=r.phase_evidence(self.root,'engineering',self.planref);self.assertFalse(r.phase_completed(value));self.assertFalse(value['actual']['operation_counts_complete']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN')
 def test_malformed_final_preserves_partial(self):
  _,e,_=self.capture(partial=True);f=self.root/(s.E+'runs/engineering/raw.json');f.write_bytes(b'{"unfinished":');pin=c.ref(self.root,s.E+'runs/engineering/raw.json');e.update(raw_bytes=pin['bytes'],raw_sha256=pin['sha256']);self.put(s.E+'runs/engineering/execution.json',e)
  value=r.phase_evidence(self.root,'engineering',self.planref);self.assertTrue(value['raw']['path'].endswith('raw.partial.json'));self.assertEqual(value['actual']['NLI_forward_calls_completed'],54)
 def test_actual_single_phase_accounting(self):
  self.capture();dev=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(dev);self.assertEqual(total['worker_attempts'],1);self.assertEqual(total['completed_corpus_batches'],1);self.assertEqual(total['engineering']['NLI_forward_calls_completed'],54)
 def test_no_benchmark_flags(self):
  p.verify_flags(s.FLAGS);wrong=dict(s.FLAGS,benchmark_accepted=True);self.reject(p.verify_flags,wrong)
 def test_legacy_exposure_strings_retained(self):
  old={'exposed_development_sets':['legacy'], 'champion':{'id':'native104'}};new=copy.deepcopy(old);p.preserve_history(old,new,p.MUTABLE)
  new['exposed_development_sets']=[];self.reject(p.preserve_history,old,new,p.MUTABLE)
 def test_dispatch_without_execution_burns_one_and_retains_unknown(self):
  self.dispatch_fixture();value=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(value)
  self.assertEqual(total['worker_attempts'],1);self.assertEqual(total['completed_corpus_batches'],None);self.assertIsNone(total['errors']);self.assertIsNone(total['peak_RSS_bytes']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN');self.assertFalse(r.phase_completed(value));self.assertIsNone(total['owned_live_processes_closed']);self.reject(r.require_final_physical_closure,total)
 def test_recovered_failed_start_can_close_physically_never_qualify(self):
  _,e,_=self.capture(partial=True);child={'pid':333,'ticks':444,'ppid':111,'pgid':333,'sid':333}
  preexec=self.put(s.E+'runs/engineering/worker-cpu-preexec.json',{'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,'child_identity':child})
  e.update(verified_worker_starts=0,uncertain_start=True,exit_code=None,worker_identity=child,recovered_preexec_child_identity=child,worker_identity_source='durable_preexec_only',worker_cpu_guard_preexec_artifact=preexec)
  self.put(s.E+'runs/engineering/execution.json',e);value=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(value);self.assertTrue(total['owned_live_processes_closed']);self.assertFalse(r.phase_completed(value));self.assertEqual(total['verified_worker_starts'],0);self.assertTrue(value['actual']['uncertain_start']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN');r.require_final_physical_closure(total)
 def test_missing_execution_cannot_claim_known_worker_closure(self):
  self.dispatch_fixture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(owned_worker_group_members=[],unknown_physical_ownership=False,physical_closure_passed=True);self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_missing_supervisor_closure_blocks_gold_and_final(self):
  self.capture();(self.root/s.DISPATCH_PATHS['closure']).unlink();self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_terminal_Z_supervisor_closed_but_not_absent(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(physical_supervisor_absent=False,observed_supervisor_state='Z');self.put(s.DISPATCH_PATHS['closure'],proof);value=r.phase_evidence(self.root,'engineering',self.planref);self.assertTrue(r.phase_completed(value));total=r.aggregate_actual(value);self.assertFalse(total['physical_supervisor_absent']);self.assertEqual(total['observed_supervisor_state'],'Z')
 def test_no_identity_cannot_magic_supervisor_closure(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof['supervisor_identity']=None;self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_supervisor_closure_wrong_execution_ref_rejected(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof['execution']=self.planref;self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def test_final_manifest_open_phase_projection_refused(self):
  manifest={'epoch':36,'kind':s.KIND,'status':'REJECTED_ENGINEERING_ADMISSION',**s.FLAGS,'confirmation':[],'all_slots_closed':True,'diagnostic_qualified':False,'engineering_passed':True,'readiness_qualified':True,'used_confirmation_identities':[],'phase_remaining':{'train':0,'dev':0,'calibration':0,'engineering':1,'confirmation':0}}
  self.put(s.E+'EPOCH_MANIFEST.json',manifest)
  with self.assertRaisesRegex(ValueError,'Final phase_remaining must close every allowance'):p.check_final(self.root,self.rows(),{}, {},{})
 def test_read_only_main_may_advance_independently(self):
  old='46d816ddc4c2a8a06cd3613534a79b1d557d858b';fresh='bd03775f2db17215039646864a138fa557d7b582'
  p.check_phase_main({'main':old},fresh);self.reject(p.check_phase_main,{'main':'invalid'},fresh)
 def test_source_sole_parent_conflict(self):
  proof={'commit':'1'*40,'parent':'2'*40,'checks_passed':True,'verified_actual_remote_readback':True,'root':'3'*40,'bench':'4'*40,'scope':'5'*40};p.check_readback(proof,'source','1'*40,('3'*40,'4'*40,'5'*40));proof['sole_parent']='0'*40;self.reject(p.check_readback,proof,'source','1'*40,('3'*40,'4'*40,'5'*40))
 def test_strict_transport_caps(self):
  blobs,groups=p.transport_groups({s.E+'x.json':b'['+b' '*200000+b']',s.E+'y.txt':b'y'*60000});self.assertEqual(len(blobs),1);self.assertTrue(all(len(c.encoded({'tree_elements':g}))<p.MAX_TREE_JSON for g in groups))
 def test_large_transport_dedup_preserves_both_leaves(self):
  body=b'['+b' '*70000+b']';changed={s.E+'runs/engineering/raw.json':body,s.E+'runs/engineering/raw.partial.json':body}
  blobs,groups=p.transport_groups(changed);self.assertEqual(len(blobs),1);entries=[row for group in groups for row in group];self.assertEqual(len(entries),2);self.assertEqual({x['path']for x in entries},{c.SCOPE+name for name in changed});self.assertEqual(len({x['sha']for x in entries}),1)
  leaves={name:p.leaf(name,value)for name,value in changed.items()};self.assertEqual(len(leaves),2);self.assertTrue(all(row['size']==len(body)for row in leaves.values()));self.assertEqual(len({row['sha']for row in leaves.values()}),1)
 def test_large_transport_SHA_collision_refused(self):
  with patch.object(p,'gitsha',return_value='a'*40):self.reject(p.transport_groups,{s.E+'a.json':b'['+b' '*70000+b']',s.E+'b.json':b'['+b' '*70001+b']'})
 def test_actual_BASE_cumulative_counts(self):
  base=Path('/workspace/ruvector-epoch36-d73fcce4c45f/kit')
  if not(base/'CONTINUATION.json').exists():self.skipTest('Fresh root reconstruction not complete')
  before=c.parse(base/'CONTINUATION.json')['execution_observed'];saved=copy.deepcopy(before)
  self.assertEqual((before['epoch35_cumulative_corpus_attempts'],before['epoch35_cumulative_completed_corpus_batches'],before['epoch35_cumulative_bounded_native_process_attempts']),(32,30,36))
  counts=r.cumulative_counts({'worker_attempts':1,'corpus_batches_attempted':1,'completed_corpus_batches':1,'engineering':{'operation_counts_complete':True,'xxlarge_model_initializations_attempted':1}});self.assertEqual((counts['corpus_attempts'],counts['completed_corpus_batches'],counts['bounded_native_process_attempts']),(33,31,37));self.assertEqual(counts['qualification_attempts'],6);self.assertEqual((counts['benchmark_HTTP_successes'],counts['benchmark_HTTP_failures']),(891,2));self.assertEqual(counts['epoch36_actual_official_benchmark_HTTP_successes'],3);self.assertEqual(before,saved)
 def model_source_fixture(self):
  header={'status':'ORIGINAL_ZIP_PICKLETOOLS_SYMBOLIC_METADATA_VERIFIED_NO_UNPICKLE','weights':{'bytes':s.MODEL_WEIGHTS['bytes'],'sha256':s.MODEL_WEIGHTS['sha256']},'archive':{'kind':'ZIP_STORED'},'unsafe_unpickling_calls':0,'checkpoint_functions_invoked':0,'ML_imports':0,'model_tokenizer_native_calls':0}
  href=self.put(s.XXL_WEIGHT_METADATA_PATH,header)
  bref=self.put(s.BASELINE_METADATA_ADMISSION['path'],{'authored_fixture':'baseline source metadata, not real admission'})
  self.enterContext(patch.object(p,'BASELINE_METADATA_ADMISSION',bref))
  source={'epoch':36,'kind':s.KIND,'repository':s.MODEL_REPOSITORY,'revision':s.MODEL_REVISION,'weights_file':s.MODEL_WEIGHTS['file'],'weights_bytes':s.MODEL_WEIGHTS['bytes'],'weights_sha256':s.MODEL_WEIGHTS['sha256'],'training_lineage_complete':False,'source_parameter_dtype':'F16','compute_dtype':s.COMPUTE_DTYPE,'native_id2label':{'0':'contradiction','1':'neutral','2':'entailment'},'canonical_E_C_N_from_raw':[2,0,1],'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[],'original_archive_metadata':href}
  baseline={**s.BASELINE_MODEL,'epoch':36,'kind':s.KIND,'training_lineage_complete':False,'native_id2label':{'0':'entailment','1':'neutral','2':'contradiction'},'canonical_E_C_N_to_raw':[0,2,1],'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[],'metadata_admission':bref}
  source_refs={'b354':self.put(s.BASELINE_MODEL_SOURCE_PATH,baseline),'xxlarge':self.put(s.MODEL_SOURCE_PATH,source)}
  profiles={'epoch':36,'kind':s.KIND,'shared_partition_model':'b354','profiles':{}}
  for tag,path,directory,labels,order in [('b354','BASELINE_MODEL_ASSETS.json',s.BASELINE_MODEL_DIRECTORY,['Entailment','NotMentioned','Contradiction'],[0,2,1]),('xxlarge','MODEL_ASSETS.json',s.MODEL_DIRECTORY,['Contradiction','NotMentioned','Entailment'],[2,0,1])]:
   lock=self.put(s.P+'candidate/epoch36/'+path,{'authored_fixture':'asset identities'})
   profiles['profiles'][tag]={'model_source':source_refs[tag],'model_assets_lock':lock,'model_directory':directory,'native_label_order':labels,'canonical_E_C_N_from_raw':order,'compute_dtype':'F32'}
  profiles['profiles']['xxlarge']['original_archive_metadata']=href
  self.put(s.MODEL_PROFILES_PATH,profiles)
  return source,baseline
 def test_exact_paired_pretrained_sources(self):
  source,baseline=self.model_source_fixture()
  with patch.object(p,'SOURCE_PARAMETER_DTYPE','F16'):
   pin=self.put(s.MODEL_SOURCE_PATH,source);p.pretrained_source_ready(self.root,self.rows(),pin)
   for key,value in [('revision','0'*40),('weights_sha256','0'*64),('training_lineage_complete',True),('weights_bytes',True),('source_parameter_dtype','F32'),('compute_dtype','F16'),('canonical_E_C_N_from_raw',[0,2,1]),('promotion_allowed',True)]:
    wrong=copy.deepcopy(source);wrong[key]=value;pin=self.put(s.MODEL_SOURCE_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,self.rows(),pin)
   pin=self.put(s.MODEL_SOURCE_PATH,source)
   for key,value in [('revision','0'*40),('weights_sha256','0'*64),('canonical_E_C_N_to_raw',[2,0,1]),('official_eligibility','ACCEPTED')]:
    wrong=copy.deepcopy(baseline);wrong[key]=value;self.put(s.BASELINE_MODEL_SOURCE_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,self.rows(),pin)
 def test_missing_static_source_dtype_blocks_freeze(self):
  source,_=self.model_source_fixture();pin=self.put(s.MODEL_SOURCE_PATH,source)
  with patch.object(p,'SOURCE_PARAMETER_DTYPE','PENDING_STATIC_SOURCE_INSPECTION'):self.reject(p.pretrained_source_ready,self.root,self.rows(),pin)
 def test_primary_original_archive_metadata_must_be_safe_and_bound(self):
  source,_=self.model_source_fixture();pin=self.put(s.MODEL_SOURCE_PATH,source)
  with patch.object(p,'SOURCE_PARAMETER_DTYPE','F16'):
   for key,value in [('unsafe_unpickling_calls',1),('ML_imports',False),('model_tokenizer_native_calls',1),('status','NOT_INSPECTED')]:
    original=c.parse(self.root/s.XXL_WEIGHT_METADATA_PATH);wrong=dict(original);wrong[key]=value;self.put(s.XXL_WEIGHT_METADATA_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,self.rows(),pin);self.put(s.XXL_WEIGHT_METADATA_PATH,original)
 def test_paired_profile_cannot_swap_raw_class_mapping_or_source(self):
  source,_=self.model_source_fixture();pin=self.put(s.MODEL_SOURCE_PATH,source);original=c.parse(self.root/s.MODEL_PROFILES_PATH)
  with patch.object(p,'SOURCE_PARAMETER_DTYPE','F16'):
   for key,value in [('canonical_E_C_N_from_raw',[0,2,1]),('canonical_E_C_N_from_raw',[2,False,True]),('native_label_order',['Entailment','NotMentioned','Contradiction']),('model_source',c.ref(self.root,s.BASELINE_MODEL_SOURCE_PATH)),('model_directory',s.BASELINE_MODEL_DIRECTORY)]:
    wrong=copy.deepcopy(original);wrong['profiles']['xxlarge'][key]=value;self.put(s.MODEL_PROFILES_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,self.rows(),pin)
 def test_complete_engineering_capture_never_implies_readiness(self):
  self.capture();value=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(value)
  self.assertTrue(r.phase_completed(value));self.assertEqual(total['completed_corpus_batches'],1)
  self.assertNotIn('engineering_passed',total)
  # Captured execution completion does not infer the separate frozen gate.
 def test_partial_capture_keeps_known_corpora_but_not_tail_certainty(self):
  self.capture(partial=True);value=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(value)
  self.assertIsNone(total['corpus_batches_attempted']);self.assertIsNone(total['completed_corpus_batches']);self.assertIsNone(r.cumulative_counts(total)['corpus_attempts'])
  self.assertEqual(total['known_corpus_reservation_count'],1);self.assertEqual(total['known_corpus_batches_attempted_at_last_capture'],1)
 def test_corpus_reservation_tamper_refused(self):
  self.capture();path=s.CORPUS_RESERVATION_PATHS['engineering'];wrong=c.parse(self.root/path);wrong['automatic_retry']=True;self.put(path,wrong);self.reject(r.phase_evidence,self.root,'engineering',self.planref)
 def runtime_alias_fixture(self):
  member={'path':c.P+'epoch26/preparation/runtime-members/python-wheel-members.json','bytes':4640799,'sha256':'87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9'}
  lock={'python_member_manifest':copy.deepcopy(member),'wheel_members_reference_path':member['path'],'wheel_members_reference_sha256':member['sha256'],'wheel_members_reference_count':17498,'verified_wheel_members':17498,'inference_python':str(c.EXTERNAL_ENV_PATH/'bin/python'),'fresh_runtime_directory':str(c.EXTERNAL_ENV_PATH),'runtime_reuse_policy':c.RUNTIME_REUSE_POLICY,'runtime_reuse_verification':{'path':c.RUNTIME_REUSE_VERIFICATION_PATH,'bytes':6556,'sha256':'d0aa0cf8ff62c4b2089998d3257694b1f6d5f1fe2c7eca2b29b4e5f1147d6b36'}}
  return member,lock
 def test_runtime_dual_manifest_aliases_required(self):
  member,lock=self.runtime_alias_fixture();self.assertEqual(c.validate_runtime_member_aliases(lock,member,17498),member)
  for key in ('python_member_manifest','wheel_members_reference_path','wheel_members_reference_sha256','wheel_members_reference_count','verified_wheel_members'):
   wrong=copy.deepcopy(lock);wrong.pop(key);self.reject(c.validate_runtime_member_aliases,wrong,member,17498)
 def test_runtime_member_alias_drift_rejected(self):
  member,lock=self.runtime_alias_fixture()
  for key,value in [('wheel_members_reference_sha256','0'*64),('wheel_members_reference_path','other.json'),('wheel_members_reference_count',True),('verified_wheel_members',17497)]:
   wrong=copy.deepcopy(lock);wrong[key]=value;self.reject(c.validate_runtime_member_aliases,wrong,member,17498)
  self.reject(c.validate_runtime_member_aliases,lock,dict(member,bytes=1),17498);self.reject(c.validate_runtime_member_aliases,lock,member,17497)
 def test_runtime_exact_reused_prefix_required(self):
  member,lock=self.runtime_alias_fixture();wrong=dict(lock,inference_python='/tmp/old/bin/python');self.reject(c.validate_runtime_member_aliases,wrong,member,17498)
 def runtime_reuse_fixture(self):
  _member,lock=self.runtime_alias_fixture();pin=lock['runtime_reuse_verification']
  value={'epoch':36,'all_hashes_checked':True,'python_wheel_members':17498,
   'policy':c.RUNTIME_REUSE_POLICY,'runtime_environment':str(c.EXTERNAL_ENV_PATH),
   'inference_python':str(c.EXTERNAL_ENV_PATH/'bin/python'),
   'old_filesystem_assumed':False,'old_model_or_runtime_files_modified':False}
  return lock,pin,value
 def test_runtime_reuse_receipt_must_be_source_bound(self):
  lock,pin,value=self.runtime_reuse_fixture();self.assertEqual(c.validate_runtime_reuse_receipt(lock,pin,value),pin)
  self.reject(c.validate_runtime_reuse_receipt,lock,dict(pin,sha256='0'*64),value)
 def test_runtime_reuse_cannot_claim_freshness_or_skipped_hashes(self):
  lock,pin,value=self.runtime_reuse_fixture()
  for key,new in [('all_hashes_checked',False),('python_wheel_members',17497),('python_wheel_members',True),('old_filesystem_assumed',True),('old_model_or_runtime_files_modified',True),('runtime_environment','/tmp/new-untested/.venv'),('policy','TRUST_PREVIOUS_FILESYSTEM')]:
   bad=dict(value);bad[key]=new;self.reject(c.validate_runtime_reuse_receipt,lock,pin,bad)
 def test_explicit_runtime_reuse_policy_required(self):
  member,lock=self.runtime_alias_fixture()
  for key in ('runtime_reuse_policy','runtime_reuse_verification'):
   wrong=copy.deepcopy(lock);wrong.pop(key);self.reject(c.validate_runtime_member_aliases,wrong,member,17498)
 def master_budget_fixture(self):
  source=Path(__file__).resolve().parent.parent/'preparation/reviewed_build_plan.py';spec=importlib.util.spec_from_file_location('pure_master_budget_validator',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  counts={'NLI_forward_calls_attempted':54,'NLI_forward_calls_completed':54,'NLI_readouts_completed':54,'ENGINEERING_forward_calls_attempted':54,'ENGINEERING_forward_calls_completed':54,'ENGINEERING_contexts_completed':54,'DEV_forward_calls_attempted':0,'DEV_forward_calls_completed':0,'native_queries_attempted':9,'native_queries_completed':9,'corpus_batches_attempted':1,'corpus_batches_completed':1,'native_index_initializations_attempted':9,'native_index_initializations_completed':9,'native_helper_starts_attempted':1,'native_helper_starts_completed':1,'native_binary_loads_attempted':1,'native_binary_loads_completed':1,'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_len_calls_attempted':18,'native_len_calls_completed':18,'model_initializations_attempted':2,'model_initializations_completed':2,'tokenizer_initializations_attempted':2,'tokenizer_initializations_completed':2,'BGE_initializations_attempted':1,'BGE_initializations_completed':1,'engineering_oracle_reads':1,'engineering_oracle_expected_labels_accessed':9,'engineering_native_predictions_compared':9,'full_source_contexts_completed':18,'two_group_contexts_completed':36,'native_complete_unitset_cases_verified':9,'model_unloads_attempted':2,'model_unloads_completed':2,'sequential_model_lifecycles_completed':2}
  for profile,n in [('b354',18),('xxlarge',36)]:
   for suffix in ('model_initializations_attempted','model_initializations_completed','tokenizer_initializations_attempted','tokenizer_initializations_completed','model_unloads_attempted','model_unloads_completed'):counts[profile+'_'+suffix]=1
   for suffix in ('forward_calls_attempted','forward_calls_completed','readouts_completed'):counts[profile+'_'+suffix]=n
  for prefix in ('NLI_capped_pair_tokenizer_calls','NLI_full_pair_tokenizer_calls','pair_tokenizations'):
   for suffix in ('attempted','completed'):counts[prefix+'_'+suffix]=54
  counts.update(ORT_sessions_attempted=1,ORT_sessions_completed=1,ENGINEERING_input_bank_reads=1)
  for key in ('paid_calls','GPU_calls','HTTP_requests','Node_network_operations_attempted','Python_network_operations_attempted','training_steps','fits','calibration_calls','generation_calls','full104_requests','source_evidence_lists_accessed','other_role_annotation_choices_accessed','backward_calls_attempted','backward_calls_completed','optimizer_initializations_attempted','optimizer_initializations_completed','optimizer_steps_attempted','optimizer_steps_completed','gradient_clips_attempted','gradient_clips_completed','parameter_artifacts_load_attempted','parameter_artifacts_load_completed','parameter_artifacts_write_attempted','parameter_artifacts_write_completed'):counts[key]=0
  return m,{'engineering':counts,'engineering_rejected':copy.deepcopy(counts)}
 def test_six_arm54_single_corpus_budget(self):
  m,t=self.master_budget_fixture();full=m.validate_operation_budgets(t,s);self.assertEqual(full['engineering']['NLI_readouts_completed'],54);self.assertEqual(full['engineering']['native_queries_completed'],9)
 def test_stale_E34_conditional_budget_refused(self):
  m,t=self.master_budget_fixture()
  for key,value in [('NLI_forward_calls_completed',120),('DEV_forward_calls_completed',96),('native_queries_completed',30),('corpus_batches_completed',2)]:
   bad=copy.deepcopy(t);bad['engineering'][key]=value;bad['engineering_rejected'][key]=value;self.reject(m.validate_operation_budgets,bad,s)
 def test_missing_engineering_budget_refused(self):
  m,t=self.master_budget_fixture();t['dev']=t.pop('engineering');self.reject(m.validate_operation_budgets,t,s)
 def test_paid_or_benchmark_role_counter_refused(self):
  m,t=self.master_budget_fixture()
  for key in ('paid_calls','GPU_calls','HTTP_requests','CONF_input_bank_reads','TRAIN_label_reads','DEV_annotation_choices_accessed'):
   bad=copy.deepcopy(t);bad['engineering'][key]=bad['engineering_rejected'][key]=1;self.reject(m.validate_operation_budgets,bad,s)
 def test_runtime_aliases_cannot_drift(self):
  m,t=self.master_budget_fixture()
  bad=copy.deepcopy(t);bad['engineering_rejected']['native_queries_completed']+=1;self.reject(m.validate_operation_budgets,bad,s)
 def test_transitive_source_context_dependencies_are_explicit(self):
  m,_t=self.master_budget_fixture()
  expected={s.P+'candidate/epoch6/context.py':'28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2',s.P+'candidate/epoch15/context.py':'9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'}
  def fake(_root,name):return {'path':name,'bytes':42,'sha256':expected[name]}
  with patch.object(m,'exact_ref',side_effect=fake):
   rows=m.inherited_context_dependencies(self.root);self.assertEqual({row['path']:row['sha256']for row in rows},expected)
  with patch.object(m,'exact_ref',side_effect=lambda _root,name:dict(fake(_root,name),sha256='0'*64)):self.reject(m.inherited_context_dependencies,self.root)
  with patch.object(m,'exact_ref',side_effect=FileNotFoundError('missing transitive context')):self.reject(m.inherited_context_dependencies,self.root)
 def test_new_reader_qualification_scope_separate_from_legacy_processes(self):
  self.capture();total=r.aggregate_actual(r.phase_evidence(self.root,'engineering',self.planref));v=r.cumulative_counts(total)
  self.assertEqual(v['qualification_attempts'],6);self.assertEqual(v['legacy_native_qualification_process_attempts'],6);self.assertEqual(v['epoch36_xxlarge_reader_initialization_attempts'],1)
  self.assertEqual(v['bounded_native_process_attempts'],37)
 def test_partial_reader_tail_is_unknown_not_zero(self):
  self.capture(partial=True);total=r.aggregate_actual(r.phase_evidence(self.root,'engineering',self.planref));v=r.cumulative_counts(total)
  self.assertIsNone(v['epoch36_xxlarge_reader_initialization_attempts']);self.assertEqual(v['known_epoch36_xxlarge_reader_initialization_attempts_at_last_capture'],1)
 def test_unknown_reader_attempt_not_fabricated(self):
  total=r.aggregate_actual(self.unknown_capture());v=r.cumulative_counts(total)
  self.assertIsNone(v['epoch36_xxlarge_reader_initialization_attempts']);self.assertIsNone(v['known_epoch36_xxlarge_reader_initialization_attempts_at_last_capture'])
 def test_more_than_one_xxlarge_init_refused(self):
  self.reject(r.cumulative_counts,{'worker_attempts':1,'corpus_batches_attempted':1,'completed_corpus_batches':1,'engineering':{'operation_counts_complete':True,'xxlarge_model_initializations_attempted':2}})
 def test_authoritative_paired_gate_has_strict_prospective_ceiling(self):
  self.assertEqual(s.ENGINEERING_GATE['primary_required_correct'],9);self.assertEqual(s.ENGINEERING_GATE['each_class_required_correct'],3)
  self.assertEqual(s.ENGINEERING_GATE['full_source_model_accuracy_gain_at_least'],2)
  self.assertEqual(s.ENGINEERING_GATE['controls'],['b354_full_source','xxlarge_native_two','xxlarge_lexical_two','xxlarge_positional_two'])
  self.assertEqual(s.MODEL_EXECUTION_ORDER,['b354','xxlarge']);self.assertEqual(s.MODEL_FORWARD_COUNTS,{'b354':18,'xxlarge':36})
 def test_new_parameter_payload_forbidden(self):
  self.reject(c.public_text,s.E+'trained-parameters.public.json',b'{}')

if __name__=='__main__':unittest.main()
