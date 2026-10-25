"""Metadata/codec/phase tamper tests only; no models, sockets or Git calls."""
import sys
sys.dont_write_bytecode=True
import ast,base64,copy,hashlib,importlib.util,json,math,struct,tempfile,unittest
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
  self.put(s.PLAN_PATH,{'epoch':37});self.put(s.FREEZE_PATH,{'epoch':37});self.planref=c.ref(self.root,s.PLAN_PATH)
 def tearDown(self):self.tmp.cleanup()
 def put(self,path,value):
  f=self.root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(bytes_json(value));pin=c.ref(self.root,path)
  if path==s.E+'runs/engineering/execution.json':self.dispatch_fixture(pin)
  return pin
 def dispatch_fixture(self,execution=None):
  claim={'schema_version':1,'epoch':37,'kind':s.KIND,'phase':'engineering','plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
  dr=self.put(s.DISPATCH_PATHS['reservation'],claim);identity={'pid':111,'startticks':222,'pgid':111,'sid':111}
  da=self.put(s.DISPATCH_PATHS['attempt'],dict(claim,**identity,verified_launcher_start=True,uncertain_launcher_start=False))
  sc=self.put(s.DISPATCH_PATHS['completion'],{'epoch':37,'kind':s.KIND,'phase':'engineering','status':'ABOUT_TO_EXIT','intended_exit_code':0,'supervisor_identity':identity})
  proof={'schema_version':1,'epoch':37,'kind':s.KIND,'phase':'engineering','source_plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,
   'dispatch_reservation':dr,'dispatch_attempt':da,'supervisor_completion':sc,'execution':execution,'supervisor_identity':identity,'physical_supervisor_absent':True,'observed_supervisor_state':None,'physical_supervisor_closed':True,'owned_worker_group_members':[],'unknown_physical_ownership':False,'physical_closure_passed':True}
  if execution is None:proof.update(owned_worker_group_members=None,unknown_physical_ownership=True,physical_closure_passed=False)
  self.put(s.DISPATCH_PATHS['closure'],proof)

 def rows(self):return {x.relative_to(self.root).as_posix():c.ref(self.root,x.relative_to(self.root).as_posix()) for x in self.root.rglob('*') if x.is_file()}
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError)):fn(*args)
 def capture(self,phase='engineering',partial=False):
  self.put(s.PHASE_RESERVATIONS[phase],{'phase':phase,'plan_sha256':self.planref['sha256']})
  cr={}
  for role,path in s.CORPUS_RESERVATION_PATHS.items():cr[role]=self.put(path,{'epoch':37,'kind':s.KIND,'phase':'engineering','role':role,'plan_sha256':self.planref['sha256'],'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False})
  raw={'corpus_reservations':cr,'epoch':37,'phase':phase,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'data_roles':copy.deepcopy(s.ROLES),'plan_sha256':self.planref['sha256'],
   'status':'COMPLETED_ENGINEERING_AWAITING_INDEPENDENTENT_AUDIT' if phase=='engineering' else 'COMPLETED_ENGINEERING_AWAITING_INDEPENDENTENT_AUDIT',
   'counters':{'training_steps':0,'optimizer_steps':0,'NLI_forward_calls_completed':36,'xxlarge_model_initializations_attempted':1,'model_initializations_attempted':1,'corpus_batches_attempted':1,'corpus_batches_completed':1,'paid_calls':0,'GPU_calls':0},'errors':[]}
  selected='raw.partial.json' if partial else 'raw.json';pin=self.put(s.E+'runs/'+phase+'/'+selected,raw)
  execution={'corpus_reservations':cr,'corpus_reservation_count':1,'epoch':37,'phase':phase,'kind':s.KIND,'status':'WORKER_FAILED_OR_TIMEOUT' if partial else 'WORKER_COMPLETED',
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
 def test_complete_engineering_phase(self):
  self.capture();value=r.phase_evidence(self.root,'engineering',self.planref,self.rows());self.assertTrue(r.phase_completed(value));self.assertEqual(value['actual']['NLI_forward_calls_completed'],36)
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
  value=r.phase_evidence(self.root,'engineering',self.planref);self.assertTrue(value['raw']['path'].endswith('raw.partial.json'));self.assertEqual(value['actual']['NLI_forward_calls_completed'],36)
 def test_actual_single_phase_accounting(self):
  self.capture();dev=r.phase_evidence(self.root,'engineering',self.planref);total=r.aggregate_actual(dev);self.assertEqual(total['worker_attempts'],1);self.assertEqual(total['completed_corpus_batches'],1);self.assertEqual(total['engineering']['NLI_forward_calls_completed'],36)
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
  manifest={'epoch':37,'kind':s.KIND,'status':'REJECTED_ENGINEERING_ADMISSION',**s.FLAGS,'confirmation':[],'all_slots_closed':True,'diagnostic_qualified':False,'engineering_passed':True,'readiness_qualified':True,'used_confirmation_identities':[],'phase_remaining':{'train':0,'dev':0,'calibration':0,'engineering':1,'confirmation':0}}
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
 def test_exact_prior_counts_and_separate_reader_scope(self):
  actual={'worker_attempts':1,'corpus_batches_attempted':1,'completed_corpus_batches':1,'engineering':{'operation_counts_complete':True,'xxlarge_model_initializations_attempted':1}}
  counts=r.cumulative_counts(actual)
  self.assertEqual((counts['corpus_attempts'],counts['completed_corpus_batches'],counts['bounded_native_process_attempts']),(34,32,38))
  self.assertEqual(counts['qualification_attempts'],6);self.assertEqual(counts['legacy_native_qualification_process_attempts'],6)
  self.assertEqual(counts['epoch37_xxlarge_reader_initialization_attempts'],1);self.assertEqual((counts['benchmark_HTTP_successes'],counts['benchmark_HTTP_failures']),(894,2))
  actual['engineering']['operation_counts_complete']=False;counts=r.cumulative_counts(actual)
  self.assertIsNone(counts['epoch37_xxlarge_reader_initialization_attempts']);self.assertEqual(counts['known_epoch37_xxlarge_reader_initialization_attempts_at_last_capture'],1)
 def resource_fixture(self):
  policy={'cgroup_hard_limit_bytes':17179869184,'source_F16_payload_bytes':3133830150,'target_F32_payload_bytes':6267660300,
   'exact_source_plus_target_payload_bytes':9401490450,'conservative_simultaneous_source_heap_plus_F32_payload_bytes':9401874294,
   'additional_runtime_activation_reserve_bytes':2147483648,'minimum_reclaim_adjusted_headroom_bytes':11549357942,
   'one_reader_only':True,'observed_E36_largest_child_peak_RSS_bytes':8255184896,'minimum_workspace_free_bytes':16777216,
   'reclaimable_filecache_policy':'max(0,min(max(0,file-shmem),active_file+inactive_file)-file_dirty-file_writeback)'}
  f=self.root/p.RESOURCE_POLICY_SOURCE_PATH;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('RESOURCE_POLICY='+repr(policy)+'\nraise RuntimeError("must never import dispatcher")\n');return policy,f
 def test_resource_AST_never_imports_dispatcher(self):
  policy,_=self.resource_fixture();self.assertEqual(p.frozen_resource_policy(self.root),dict(policy,minimum_workspace_free_bytes=16777216))
 def test_resource_old_4GiB_or_float_or_shmem_refused(self):
  original,f=self.resource_fixture()
  for key,value in [('additional_runtime_activation_reserve_bytes',4294967296),('source_F16_payload_bytes',3133830150.0),('reclaimable_filecache_policy','max(0,file)')]:
   changed=dict(original);changed[key]=value;f.write_text('RESOURCE_POLICY='+repr(changed)+'\n');self.reject(p.frozen_resource_policy,self.root)
 def test_resource_nonliteral_and_duplicate_refused(self):
  _,f=self.resource_fixture()
  for text in ('RESOURCE_POLICY=dict()','RESOURCE_POLICY={}\nRESOURCE_POLICY={}',"RESOURCE_POLICY=__import__('os').environ"):
   f.write_text(text);self.reject(p.frozen_resource_policy,self.root)
 def model_source_fixture(self):
  meta={'status':'ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE','format':s.SOURCE_SERIALIZATION_FORMAT,'source_parameter_dtype':'F16','state_tensor_count':782,'floating_state_tensor_elements':1566915075,'metadata_pickle_count':5,'storage_data_ends_at_filelength':True,'storage_payloads_decoded':0,'weights':{'bytes':s.MODEL_WEIGHTS['bytes'],'sha256':s.MODEL_WEIGHTS['sha256']},'unsafe_unpickling_calls':0,'checkpoint_functions_invoked':0,'ML_imports':0,'model_tokenizer_native_calls':0}
  href=self.put(s.XXL_WEIGHT_METADATA_PATH,meta);self.enterContext(patch.object(p,'XXL_WEIGHT_METADATA_REF',href))
  load={'serialization_format':s.SOURCE_SERIALIZATION_FORMAT,'weights_only':True,'mmap':False,'map_location':'cpu','trust_remote_code':False,'unrestricted_pickle_allowed':False,'extra_pickle_safe_globals_added':0,'ZIP_fallback_allowed':False,'legacy_tar_fallback_in_statics':False,'alternate_checkpoint_allowed':False,'dynamic_quantization_allowed':False,'compute_dtype':'F32','before_source_freeze_actual_torch_loads_allowed':0,'model_initializations_in_acquisition_or_static_inspection':0}
  lref=self.put(s.LEGACY_LOAD_PLAN_PATH,{'future_frozen_loader_policy':load});self.enterContext(patch.object(p,'LEGACY_LOAD_PLAN_REF',lref))
  admission=self.put(s.P+'audit/epoch-fixture/metadata.json',{'fixture':'unexecuted source metadata admission only'})
  source={'epoch':37,'kind':s.KIND,'repository':s.MODEL_REPOSITORY,'revision':s.MODEL_REVISION,'weights_file':s.MODEL_WEIGHTS['file'],'weights_bytes':s.MODEL_WEIGHTS['bytes'],'weights_sha256':s.MODEL_WEIGHTS['sha256'],'training_lineage_complete':False,'source_parameter_dtype':'F16','source_serialization_format':s.SOURCE_SERIALIZATION_FORMAT,'compute_dtype':'F32','native_id2label':{'0':'contradiction','1':'neutral','2':'entailment'},'canonical_E_C_N_from_raw':[2,0,1],'promotion_allowed':False,'official_eligibility':'HOLD','confirmation':[],'original_archive_metadata':href,'legacy_original_load_plan':lref,'metadata_admission':admission}
  source_ref=self.put(s.MODEL_SOURCE_PATH,source);lock=self.put(s.P+'candidate/epoch37/MODEL_ASSETS.json',{'fixture':'not actual model asset lock'})
  profile={'model_source':source_ref,'model_assets_lock':lock,'model_directory':s.MODEL_DIRECTORY,'native_label_order':['Contradiction','NotMentioned','Entailment'],'canonical_E_C_N_from_raw':[2,0,1],'compute_dtype':'F32','original_archive_metadata':href,'legacy_original_load_plan':lref}
  self.put(s.MODEL_PROFILES_PATH,{'epoch':37,'kind':s.KIND,'shared_partition_model':'xxlarge','profiles':{'xxlarge':profile}});return source,source_ref
 def test_single_original_model_metadata_not_size_claim(self):
  source,pin=self.model_source_fixture();self.assertEqual(p.pretrained_source_ready(self.root,self.rows(),pin),source)
 def test_second_model_native_order_and_HOLD_tampering_refused(self):
  source,pin=self.model_source_fixture()
  for key,changed in [('canonical_E_C_N_from_raw',[0,2,1]),('compute_dtype','F16'),('promotion_allowed',True),('official_eligibility','APPROVED')]:
   wrong=copy.deepcopy(source);wrong[key]=changed;row=self.put(s.MODEL_SOURCE_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,None,row)
  self.put(s.MODEL_SOURCE_PATH,source);profiles=c.parse(self.root/s.MODEL_PROFILES_PATH);profiles['profiles']['second']={};self.put(s.MODEL_PROFILES_PATH,profiles);self.reject(p.pretrained_source_ready,self.root,None,pin)
 def test_historical_header_tampering_refused(self):
  _,pin=self.model_source_fixture();meta=c.parse(self.root/s.XXL_WEIGHT_METADATA_PATH);meta['source_parameter_dtype']='F32';self.put(s.XXL_WEIGHT_METADATA_PATH,meta);self.reject(p.pretrained_source_ready,self.root,None,pin)
 def protocol_fixture(self):
  root_ref=self.put(s.ROOT_CONTRACT_PATH,{'fixture':'prospective contract metadata only, not scientific input'})
  self.enterContext(patch.object(p,'frozen_metrics_policy',return_value=s.METRICS_POLICY_REF))
  self.enterContext(patch.object(p,'ROOT_CONTRACT_REF',root_ref))
  value={'schema_version':1,'epoch':37,'kind':s.KIND,'phase':'engineering','source_checkpoint':c.BASE_COMMIT,'data_roles':copy.deepcopy(s.ROLES),'engineering_only':True,'benchmark_accuracy':None,'promotion_allowed':False,'training_lineage_complete':False,'official_eligibility':'HOLD','engineering_case_ids':list(s.ENGINEERING_IDS),'raw_contexts':list(s.RAW_CONTEXT_NAMES),'metric_arms':list(s.METRIC_ARM_NAMES),'arm_to_measured_context':dict(s.READOUT_REUSE_MAP),'primary':s.PRIMARY_ARM,'engineering_gate':copy.deepcopy(s.ENGINEERING_GATE),'probability_policy':copy.deepcopy(s.PROBABILITY_POLICY),'actual_NLI_forwards':36,'final_derived_forecasts':60,'used_confirmation_identities':[],'root_contract':root_ref,'metrics_policy':s.METRICS_POLICY_REF}
  for key in ('candidate_protocol','core_source_manifest','core_source_ready','scorer_source_ready_v1'):value[key]=self.put(s.P+'audit/epoch37/fixture-'+key+'.json',{'fixture':key})
  self.put(p.AUDIT_PROTOCOL_PATH,value);return value
 def test_protocol_five_forecasts_three_contexts_exact_root_gate(self):
  value=self.protocol_fixture();self.assertEqual(p.audit_protocol_ready(self.root,self.rows()),value)
 def test_protocol_no_derived_as_actual_inference_or_confirmation(self):
  original=self.protocol_fixture()
  for key,value in [('actual_NLI_forwards',60),('final_derived_forecasts',36),('raw_contexts',['full','native','lexical']),('used_confirmation_identities',['forbidden']),('engineering_gate',dict(s.ENGINEERING_GATE,primary_required_correct=11)),('probability_policy',dict(s.PROBABILITY_POLICY,calibrated_posterior_claim=True))]:
   changed=copy.deepcopy(original);changed[key]=value;self.put(p.AUDIT_PROTOCOL_PATH,changed);self.reject(p.audit_protocol_ready,self.root)
 def test_protocol_requires_canonical_ready_index_physical_file(self):
  value=self.protocol_fixture();(self.root/value['scorer_source_ready_v1']['path']).unlink();self.reject(p.audit_protocol_ready,self.root)
 def master_budget_fixture(self):
  name='fixture_master_source';spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'preparation/reviewed_build_plan.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  counts={'NLI_forward_calls_attempted':36,'NLI_forward_calls_completed':36,'NLI_readouts_completed':36,'ENGINEERING_forward_calls_attempted':36,'ENGINEERING_forward_calls_completed':36,'ENGINEERING_contexts_completed':36,'native_queries_attempted':12,'native_queries_completed':12,'corpus_batches_attempted':1,'corpus_batches_completed':1,'native_index_initializations_attempted':12,'native_index_initializations_completed':12,'native_len_calls_attempted':24,'native_len_calls_completed':24,'model_initializations_attempted':1,'model_initializations_completed':1,'tokenizer_initializations_attempted':1,'tokenizer_initializations_completed':1,'native_helper_starts_attempted':1,'native_helper_starts_completed':1,'native_binary_loads_attempted':1,'native_binary_loads_completed':1,'native_version_calls_attempted':1,'native_version_calls_completed':1,'BGE_initializations_attempted':1,'BGE_initializations_completed':1,'ORT_sessions_attempted':1,'ORT_sessions_completed':1,'ENGINEERING_input_bank_reads':1,'engineering_oracle_reads':1,'engineering_oracle_expected_labels_accessed':12,'engineering_native_predictions_compared':12,'model_unloads_attempted':1,'model_unloads_completed':1,'derived_forecasts_completed':60,'readout_reuse_receipts_completed':60,'source_analysis_calls_attempted':48,'source_analysis_calls_completed':48,'certificate_decisions_attempted':36,'certificate_decisions_completed':36,'full_source_contexts_completed':12,'coverage_contexts_completed':24,'native_complete_unitset_cases_verified':12,'sequential_model_lifecycles_completed':1}
  for prefix in ('NLI_capped_pair_tokenizer_calls','NLI_full_pair_tokenizer_calls','pair_tokenizations'):
   for suffix in ('attempted','completed'):counts[prefix+'_'+suffix]=36
  for suffix in ('model_initializations_attempted','model_initializations_completed','tokenizer_initializations_attempted','tokenizer_initializations_completed','model_unloads_attempted','model_unloads_completed'):counts['xxlarge_'+suffix]=1
  for suffix in ('forward_calls_attempted','forward_calls_completed','readouts_completed'):counts['xxlarge_'+suffix]=36
  for key in ('paid_calls','GPU_calls','HTTP_requests','Python_network_operations_attempted','Node_network_operations_attempted','training_steps','fits','calibration_calls','generation_calls','full104_requests','source_evidence_lists_accessed','other_role_annotation_choices_accessed','backward_calls_attempted','backward_calls_completed','optimizer_initializations_attempted','optimizer_initializations_completed','optimizer_steps_attempted','optimizer_steps_completed','gradient_clips_attempted','gradient_clips_completed','parameter_artifacts_load_attempted','parameter_artifacts_load_completed','parameter_artifacts_write_attempted','parameter_artifacts_write_completed'):counts[key]=0
  return module,{'epoch':37,'kind':s.KIND,'engineering':counts}
 def test_master_budget36_actual60_derived_one_reader12queries(self):
  m,table=self.master_budget_fixture();result=m.validate_operation_budgets(table,s);self.assertEqual(result['engineering']['NLI_readouts_completed'],36);self.assertEqual(result['engineering']['derived_forecasts_completed'],60)
 def test_master_counter_tampering_and_paid_or_DEV_refused(self):
  m,table=self.master_budget_fixture()
  for key,value in [('NLI_forward_calls_completed',60),('model_initializations_attempted',2),('native_queries_completed',13),('engineering_oracle_expected_labels_accessed',11),('paid_calls',1),('DEV_forward_calls_completed',1),('training_steps',True)]:
   changed=copy.deepcopy(table);changed['engineering'][key]=value;self.reject(m.validate_operation_budgets,changed,s)
 def test_inherited_source_catalogue_exact_two_Git_pins(self):
  m,_=self.master_budget_fixture();rows=[]
  for name in (s.P+'candidate/epoch3/models.py',s.P+'audit/epoch30/runtime-policy-addendum-v1.json'):
   pin=self.put(name,{'fixture':'inert source reference'});pin['actual_git_blob_sha1']=c.gitsha((self.root/name).read_bytes());rows.append(pin)
  self.put(s.P+'candidate/epoch37/research/SOURCE_DEPENDENCIES.json',{'epoch':37,'source_checkpoint':c.BASE_COMMIT,'inactive_old_modules_imported':[],'active_inherited_sources':rows})
  self.assertEqual(len(m.inherited_source_dependencies(self.root)),3)
  (self.root/rows[0]['path']).write_bytes(b'changed');self.reject(m.inherited_source_dependencies,self.root)
 def test_original_root_gate_exact_no_hidden_grid(self):
  self.assertEqual(s.MODEL_EXECUTION_ORDER,['xxlarge']);self.assertEqual(s.MODEL_FORWARD_COUNTS,{'xxlarge':36});self.assertEqual((s.TOTAL_MAX_NLI_FORWARD_CALLS,s.TOTAL_FINAL_FORECASTS),(36,60))
  self.assertEqual(s.ENGINEERING_GATE['primary_required_correct'],12);self.assertEqual(s.ENGINEERING_GATE['each_class_required_correct'],4)
  self.assertEqual(s.ENGINEERING_GATE['proper_nonincrease_against'],['full_raw','native_raw','lexical_verified','full_verified']);self.assertIsNone(s.PROBABILITY_POLICY['fitting_or_confidence_parameter'])
 def test_results_helper_never_recomputes_or_overwrites_evaluated_fields(self):
  tree=ast.parse((Path(__file__).parents[1]/'preparation/reviewed_build_results.py').read_text());calls=[n for n in ast.walk(tree)if isinstance(n,ast.Call)]
  self.assertTrue(any(isinstance(n.func,ast.Attribute)and n.func.attr=='deepcopy'and n.args and isinstance(n.args[0],ast.Name)and n.args[0].id=='replay'for n in calls))
  body=ast.unparse(tree);self.assertIn('Never overwrite an evaluated replay field',body)
  for forbidden in ('torch','transformers','tokenize','subprocess','socket'):self.assertNotIn('import '+forbidden,body)

 def test_source_query_context_refs_not_convenience_aliases(self):
  query={'epoch':37,'kind':s.KIND,'policy':'unchanged-original-query-numeric-source-v1','truncation':False,'rewriting':False,'label_access':False}
  context={'epoch':37,'kind':s.KIND,'policy':'rank-prefix-until-source-constraint-coverage-v1','raw_contexts':s.RAW_CONTEXT_NAMES,'arms':s.ARM_NAMES,'readout_reuse_map':s.READOUT_REUSE_MAP,'partition_model':'xxlarge','BGE_source':s.P+'candidate/epoch3/models.py','root_contract_sha256':s.ROOT_CONTRACT_REF['sha256']}
  qref=self.put(s.QUERY_POLICY_PATH,query);cref=self.put(s.CONTEXT_POLICY_PATH,context)
  self.assertEqual(p.frozen_retrieval_policy(self.root,self.rows()),{'query_policy':qref,'context_policy':cref})
  query['label_access']=True;self.put(s.QUERY_POLICY_PATH,query);self.reject(p.frozen_retrieval_policy,self.root)

 def test_stable_metric_policy_and_clipped_diagnostic_binding(self):
  policy={'epoch':37,'kind':s.KIND,'gate_metric_binding':{'Brier':'Brier','NLL':'NLL'},'NLL':'UNCLIPPED_STABLE_SOURCE_LOGIT_LOGSOFTMAX_WITH_SAME_CANONICAL_CLASS_PERMUTATION','NLL_clipping_floor_diagnostic_only':1e-12,'acceptance_roundoff_tolerance':1e-12,'no_confidence_fitting':True,'no_calibrated_posterior_claim':True,'probability_policy':'SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'}
  row=self.put(s.METRICS_POLICY_PATH,policy)
  with patch.object(p,'METRICS_POLICY_REF',row):self.assertEqual(p.frozen_metrics_policy(self.root,self.rows()),row)
  policy['gate_metric_binding']['NLL']='NLL_clipped_1e-12';changed=self.put(s.METRICS_POLICY_PATH,policy)
  with patch.object(p,'METRICS_POLICY_REF',changed):self.reject(p.frozen_metrics_policy,self.root)

 def actual_runtime_metadata_fixture(self):
  data=(Path(__file__).parent/'fixtures/runtime-reuse-verification.e37.json').read_bytes()
  self.assertEqual(len(data),6707);self.assertEqual(hashlib.sha256(data).hexdigest(),'339d4073f5e7ced5f5d4d97329a4cc1453ae0c2a44c85e32de554d04f5e27547')
  value=c.loads(data);pin={'path':c.RUNTIME_REUSE_VERIFICATION_PATH,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  lock={'runtime_reuse_verification':pin,'official_CPU_wheels':31,'python_member_manifest':copy.deepcopy(value['member_manifest']),
   'assets':[{k:row[k]for k in ('path','bytes','sha256')}for row in value['native_BGE_assets']]}
  return lock,pin,value
 def test_REAL_E37_metadata_receipt_integration_without_old_aliases(self):
  lock,pin,value=self.actual_runtime_metadata_fixture();self.assertEqual(c.validate_runtime_reuse_receipt(lock,pin,value),pin)
  self.assertNotIn('all_hashes_checked',value);self.assertNotIn('old_model_or_runtime_files_modified',value)
  self.assertNotIn('python_wheel_members',value);self.assertNotIn('old_filesystem_assumed',value)
  self.assertEqual(sum(x['destination']=='FRESH_OPT_IN_COPY_HASH_VERIFIED'for x in value['native_BGE_assets']),3)
  self.assertEqual(sum(x['destination']=='RESTORED_CP_ALREADY_PRESENT_VERIFIED'for x in value['native_BGE_assets']),7)
  self.assertTrue(value['model_profiles_verified']['xxlarge']['nlink_ctime_changes_disclosed'])
 def test_runtime_receipt_exact_identity_no_unfrozen_metadata_substitute(self):
  lock,pin,value=self.actual_runtime_metadata_fixture()
  for key,wrong in [('bytes',6708),('sha256','0'*64),('path',c.P+'epoch36/preparation/runtime-reuse-verification.json')]:
   changed=dict(pin);changed[key]=wrong;changedlock=copy.deepcopy(lock);changedlock['runtime_reuse_verification']=changed
   self.reject(c.validate_runtime_reuse_receipt,changedlock,changed,value)
 def test_runtime_receipt_wrong_or_missing_scope_refused(self):
  lock,pin,value=self.actual_runtime_metadata_fixture()
  for key,wrong in [('actual_model_native_tokenizer_paid_GPU_calls',1),('actual_model_native_tokenizer_paid_GPU_calls',False),('fresh_environment_installs',1),('epoch',36),('verified_wheel_members',17497),('source_checkpoint','0'*40),('external_environment','/other'),('official_CPU_wheels',30),('wall_seconds',float('inf'))]:
   changed=copy.deepcopy(value);changed[key]=wrong;self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  del value['status'];self.reject(c.validate_runtime_reuse_receipt,lock,pin,value)
 def test_runtime_receipt_hardlink_metadata_changes_must_be_disclosed(self):
  lock,pin,value=self.actual_runtime_metadata_fixture()
  for key,wrong in [('nlink_ctime_changes_disclosed',False),('same_inodes_hardlinks_read_only',False),('original_payloads_byte_mode_mtime_unchanged',False),('payload_files',4),('original_directory','/other')]:
   changed=copy.deepcopy(value);changed['model_profiles_verified']['xxlarge'][key]=wrong;self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  for key,wrong in [('hardlink_nlink_ctime_metadata_changed',False),('payload_bytes_mode_mtime_unchanged',False),('same_payload_inode_read_only_reuse',False),('sha256','0'*64),('bytes',1)]:
   changed=copy.deepcopy(value);changed['model_profiles_verified']['xxlarge']['payloads'][0][key]=wrong;self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
 def test_runtime_receipt_duplicate_or_alternate_payload_refused(self):
  lock,pin,value=self.actual_runtime_metadata_fixture();changed=copy.deepcopy(value)
  changed['model_profiles_verified']['xxlarge']['payloads'][1]=copy.deepcopy(changed['model_profiles_verified']['xxlarge']['payloads'][0]);self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  changed=copy.deepcopy(value);changed['model_profiles_verified']['second']={};self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
 def test_runtime_receipt_native_copy_and_restored_metadata_provenance(self):
  lock,pin,value=self.actual_runtime_metadata_fixture()
  for key,wrong in [('destination','RESTORED_CP_ALREADY_PRESENT_VERIFIED'),('sha256','0'*64),('bytes',0),('source_directory','/other')]:
   changed=copy.deepcopy(value);changed['native_BGE_assets'][0][key]=wrong;self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  changed=copy.deepcopy(value);changed['native_BGE_assets'][2]['destination']='FRESH_OPT_IN_COPY_HASH_VERIFIED';self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  changed=copy.deepcopy(value);changed['native_BGE_assets'][2]=copy.deepcopy(changed['native_BGE_assets'][0]);self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
  changed=copy.deepcopy(value);changed['native_BGE_assets'].pop();self.reject(c.validate_runtime_reuse_receipt,lock,pin,changed)
 def test_runtime_receipt_and_wheel_alias_contract_join_on_real_metadata(self):
  lock,pin,value=self.actual_runtime_metadata_fixture();member=value['member_manifest']
  lock.update(wheel_members_reference_path=member['path'],wheel_members_reference_sha256=member['sha256'],wheel_members_reference_count=17498,verified_wheel_members=17498,
   inference_python=str(c.EXTERNAL_ENV_PATH/'bin/python'),fresh_runtime_directory=str(c.EXTERNAL_ENV_PATH),runtime_reuse_policy=c.RUNTIME_REUSE_POLICY)
  self.assertEqual(c.validate_runtime_member_aliases(lock,member,17498),member)
  self.assertEqual(c.validate_runtime_reuse_receipt(lock,pin,value),pin)
  lock['python_member_manifest']['sha256']='0'*64;self.reject(c.validate_runtime_reuse_receipt,lock,pin,value)

if __name__=='__main__':unittest.main()
