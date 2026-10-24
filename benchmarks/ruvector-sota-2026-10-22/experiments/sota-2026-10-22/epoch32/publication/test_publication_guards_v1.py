"""Metadata/codec/phase tamper tests only; no models, sockets or Git calls."""
import sys
sys.dont_write_bytecode=True
import base64,copy,hashlib,json,math,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import publication_common_v1 as c
import phase_schema_v1 as s
import phase_receipts_v1 as r
import stage_publication_v1 as p

SCRATCH=Path('/workspace/ruvector-e32-publication-impl')

def bytes_json(value):return (json.dumps(value,separators=(',',':'),sort_keys=True)+'\n').encode()

class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='guards-',dir=SCRATCH);self.root=Path(self.tmp.name)
  self.put(s.PLAN_PATH,{'epoch':32});self.put(s.FREEZE_PATH,{'epoch':32});self.planref=c.ref(self.root,s.PLAN_PATH)
 def tearDown(self):self.tmp.cleanup()
 def put(self,path,value):
  f=self.root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(bytes_json(value));pin=c.ref(self.root,path)
  if path==s.E+'runs/dev/execution.json':self.dispatch_fixture(pin)
  return pin
 def dispatch_fixture(self,execution=None):
  claim={'schema_version':1,'epoch':32,'kind':s.KIND,'phase':'dev','plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
  dr=self.put(s.DISPATCH_PATHS['reservation'],claim);identity={'pid':111,'startticks':222,'pgid':111,'sid':111}
  da=self.put(s.DISPATCH_PATHS['attempt'],dict(claim,**identity,verified_launcher_start=True,uncertain_launcher_start=False))
  sc=self.put(s.DISPATCH_PATHS['completion'],{'epoch':32,'kind':s.KIND,'phase':'dev','status':'ABOUT_TO_EXIT','intended_exit_code':0,'supervisor_identity':identity})
  proof={'schema_version':1,'epoch':32,'kind':s.KIND,'phase':'dev','source_plan_sha256':self.planref['sha256'],'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,
   'dispatch_reservation':dr,'dispatch_attempt':da,'supervisor_completion':sc,'execution':execution,'supervisor_identity':identity,'physical_supervisor_absent':True,'observed_supervisor_state':None,'physical_supervisor_closed':True,'owned_worker_group_members':[],'unknown_physical_ownership':False,'physical_closure_passed':True}
  if execution is None:proof.update(owned_worker_group_members=None,unknown_physical_ownership=True,physical_closure_passed=False)
  self.put(s.DISPATCH_PATHS['closure'],proof)

 def rows(self):return {x.relative_to(self.root).as_posix():c.ref(self.root,x.relative_to(self.root).as_posix()) for x in self.root.rglob('*') if x.is_file()}
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError)):fn(*args)
 def capture(self,phase='dev',partial=False):
  self.put(s.PHASE_RESERVATIONS[phase],{'phase':phase,'plan_sha256':self.planref['sha256']})
  cr={}
  for role,path in s.CORPUS_RESERVATION_PATHS.items():cr[role]=self.put(path,{'epoch':32,'kind':s.KIND,'phase':'dev','role':role,'plan_sha256':self.planref['sha256'],'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False})
  raw={'corpus_reservations':cr,'epoch':32,'phase':phase,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'data_roles':copy.deepcopy(s.ROLES),'plan_sha256':self.planref['sha256'],
   'status':'COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN' if phase=='dev' else 'COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN',
   'counters':{'training_steps':0,'optimizer_steps':0,'NLI_forward_pairs_completed':90,'corpus_batches_attempted':2,'corpus_batches_completed':2,'paid_calls':0,'GPU_calls':0},'errors':[]}
  selected='raw.partial.json' if partial else 'raw.json';pin=self.put(s.E+'runs/'+phase+'/'+selected,raw)
  execution={'corpus_reservations':cr,'corpus_reservation_count':2,'epoch':32,'phase':phase,'kind':s.KIND,'status':'WORKER_FAILED_OR_TIMEOUT' if partial else 'WORKER_COMPLETED',
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
  self.reject(c.public_text,s.E+'x.txt',b'a\0b');self.reject(c.public_text,s.E+'secret.txt',('gh'+'p_'+'x'*40).encode())
 def test_unstarted_phase_resources_unknown(self):
  value=r.phase_evidence(self.root,'dev',self.planref)
  self.assertEqual(value['actual']['worker_attempts'],0);self.assertIsNone(value['actual']['resources']);self.assertIsNone(value['actual']['errors'])
 def test_reservation_cannot_be_erased_as_unstarted(self):
  self.put(s.PHASE_RESERVATIONS['dev'],{'phase':'dev','plan_sha256':self.planref['sha256']});self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_complete_train_phase(self):
  self.capture();value=r.phase_evidence(self.root,'dev',self.planref,self.rows());self.assertTrue(r.phase_completed(value));self.assertEqual(value['actual']['NLI_forward_pairs_completed'],90)
 def test_reserved_uncertain_start_burns_one(self):
  _,e,_=self.capture(partial=True);e.update(verified_worker_starts=0,uncertain_start=True,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,partial_raw_bytes=None,partial_raw_sha256=None)
  (self.root/(s.E+'runs/dev/raw.partial.json')).unlink();self.put(s.E+'runs/dev/execution.json',e)
  value=r.phase_evidence(self.root,'dev',self.planref);self.assertEqual(value['actual']['worker_attempts'],1);self.assertEqual(value['actual']['verified_worker_starts'],0);self.assertIsNone(value['actual']['errors'])
 def unknown_capture(self):
  _,e,_=self.capture(partial=True)
  (self.root/(s.E+'runs/dev/raw.partial.json')).unlink()
  e.update(verified_worker_starts=0,uncertain_start=True,exit_code=None,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,
   partial_raw_bytes=None,partial_raw_sha256=None,owned_live_group_members=None,owned_live_processes_closed=None,
   owned_process_closure_observation='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF',worker_identity_source='UNKNOWN',worker_identity=None,recovered_preexec_child_identity=None)
  self.put(s.E+'runs/dev/execution.json',e)
  proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(owned_worker_group_members=None,unknown_physical_ownership=True,physical_closure_passed=False);self.put(s.DISPATCH_PATHS['closure'],proof)
  return r.phase_evidence(self.root,'dev',self.planref)
 def test_failed_unknown_physical_closure_preserved(self):
  value=self.unknown_capture();self.assertIsNone(value['actual']['owned_live_processes_closed']);self.assertIsNone(value['actual']['owned_live_group_members']);self.assertEqual(value['actual']['worker_attempts'],1)
  total=r.aggregate_actual(value);self.assertIsNone(total['owned_live_processes_closed'])
 def test_unknown_physical_closure_cannot_complete(self):
  self.assertFalse(r.phase_completed(self.unknown_capture()))
 def test_FINAL_unknown_physical_closure_refused(self):
  value=self.unknown_capture();total=r.aggregate_actual(value);self.reject(r.require_final_physical_closure,total)
 def test_known_partial_counters_cannot_be_hidden(self):
  _,e,_=self.capture(partial=True);e.update(raw_operation_counters_source='UNKNOWN',raw_operation_counters=None)
  self.put(s.E+'runs/dev/execution.json',e);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_wrong_phase_receipt_rejected(self):
  raw,e,_=self.capture();e['phase']='train';self.put(s.E+'runs/dev/execution.json',e);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_partial_not_completed(self):
  self.capture(partial=True);value=r.phase_evidence(self.root,'dev',self.planref);self.assertFalse(r.phase_completed(value));self.assertFalse(value['actual']['operation_counts_complete']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN')
 def test_malformed_final_preserves_partial(self):
  _,e,_=self.capture(partial=True);f=self.root/(s.E+'runs/dev/raw.json');f.write_bytes(b'{"unfinished":');pin=c.ref(self.root,s.E+'runs/dev/raw.json');e.update(raw_bytes=pin['bytes'],raw_sha256=pin['sha256']);self.put(s.E+'runs/dev/execution.json',e)
  value=r.phase_evidence(self.root,'dev',self.planref);self.assertTrue(value['raw']['path'].endswith('raw.partial.json'));self.assertEqual(value['actual']['NLI_forward_pairs_completed'],90)
 def test_actual_single_phase_accounting(self):
  self.capture();dev=r.phase_evidence(self.root,'dev',self.planref);total=r.aggregate_actual(dev);self.assertEqual(total['worker_attempts'],1);self.assertEqual(total['completed_corpus_batches'],2);self.assertEqual(total['dev']['NLI_forward_pairs_completed'],90)
 def test_no_benchmark_flags(self):
  p.verify_flags(s.FLAGS);wrong=dict(s.FLAGS,benchmark_accepted=True);self.reject(p.verify_flags,wrong)
 def test_legacy_exposure_strings_retained(self):
  old={'exposed_development_sets':['legacy'], 'champion':{'id':'native104'}};new=copy.deepcopy(old);new['exposed_development_sets'].append(p.retirement_record());p.preserve_history(old,new,p.MUTABLE)
  new['exposed_development_sets']=[];self.reject(p.preserve_history,old,new,p.MUTABLE)
 def test_dispatch_without_execution_burns_one_and_retains_unknown(self):
  self.dispatch_fixture();value=r.phase_evidence(self.root,'dev',self.planref);total=r.aggregate_actual(value)
  self.assertEqual(total['worker_attempts'],1);self.assertEqual(total['completed_corpus_batches'],None);self.assertIsNone(total['errors']);self.assertIsNone(total['peak_RSS_bytes']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN');self.assertFalse(r.phase_completed(value));self.assertIsNone(total['owned_live_processes_closed']);self.reject(r.require_final_physical_closure,total)
 def test_recovered_failed_start_can_close_physically_never_qualify(self):
  _,e,_=self.capture(partial=True);child={'pid':333,'ticks':444,'ppid':111,'pgid':333,'sid':333}
  preexec=self.put(s.E+'runs/dev/worker-cpu-preexec.json',{'kernel_boot_id':s.BOOT_ID,'pid_namespace_inode':s.PID_NAMESPACE,'child_identity':child})
  e.update(verified_worker_starts=0,uncertain_start=True,exit_code=None,worker_identity=child,recovered_preexec_child_identity=child,worker_identity_source='durable_preexec_only',worker_cpu_guard_preexec_artifact=preexec)
  self.put(s.E+'runs/dev/execution.json',e);value=r.phase_evidence(self.root,'dev',self.planref);total=r.aggregate_actual(value);self.assertTrue(total['owned_live_processes_closed']);self.assertFalse(r.phase_completed(value));self.assertEqual(total['verified_worker_starts'],0);self.assertTrue(value['actual']['uncertain_start']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN');r.require_final_physical_closure(total)
 def test_missing_execution_cannot_claim_known_worker_closure(self):
  self.dispatch_fixture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(owned_worker_group_members=[],unknown_physical_ownership=False,physical_closure_passed=True);self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_missing_supervisor_closure_blocks_gold_and_final(self):
  self.capture();(self.root/s.DISPATCH_PATHS['closure']).unlink();self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_terminal_Z_supervisor_closed_but_not_absent(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof.update(physical_supervisor_absent=False,observed_supervisor_state='Z');self.put(s.DISPATCH_PATHS['closure'],proof);value=r.phase_evidence(self.root,'dev',self.planref);self.assertTrue(r.phase_completed(value));total=r.aggregate_actual(value);self.assertFalse(total['physical_supervisor_absent']);self.assertEqual(total['observed_supervisor_state'],'Z')
 def test_no_identity_cannot_magic_supervisor_closure(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof['supervisor_identity']=None;self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_supervisor_closure_wrong_execution_ref_rejected(self):
  self.capture();proof=c.parse(self.root/s.DISPATCH_PATHS['closure']);proof['execution']=self.planref;self.put(s.DISPATCH_PATHS['closure'],proof);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_final_manifest_open_phase_projection_refused(self):
  manifest={'epoch':32,'kind':s.KIND,'status':'REJECTED_DEV_DIAGNOSTIC',**s.FLAGS,'confirmation':[],'all_slots_closed':True,'diagnostic_qualified':False,'engineering_passed':True,'phase_remaining':{'train':0,'dev':1,'confirmation':0}}
  self.put(s.E+'EPOCH_MANIFEST.json',manifest)
  with self.assertRaisesRegex(ValueError,'Final phase_remaining must be the exact typed-zero'):p.check_final(self.root,self.rows(),{}, {},{})
 def test_read_only_main_may_advance_independently(self):
  old='46d816ddc4c2a8a06cd3613534a79b1d557d858b';fresh='bd03775f2db17215039646864a138fa557d7b582'
  p.check_phase_main({'main':old},fresh);self.reject(p.check_phase_main,{'main':'invalid'},fresh)
 def test_source_sole_parent_conflict(self):
  proof={'commit':'1'*40,'parent':'2'*40,'checks_passed':True,'verified_actual_remote_readback':True,'root':'3'*40,'bench':'4'*40,'scope':'5'*40};p.check_readback(proof,'source','1'*40,('3'*40,'4'*40,'5'*40));proof['sole_parent']='0'*40;self.reject(p.check_readback,proof,'source','1'*40,('3'*40,'4'*40,'5'*40))
 def test_strict_transport_caps(self):
  blobs,groups=p.transport_groups({s.E+'x.json':b'['+b' '*200000+b']',s.E+'y.txt':b'y'*60000});self.assertEqual(len(blobs),1);self.assertTrue(all(len(c.encoded({'tree_elements':g}))<p.MAX_TREE_JSON for g in groups))
 def test_large_transport_dedup_preserves_both_leaves(self):
  body=b'['+b' '*70000+b']';changed={s.E+'runs/dev/raw.json':body,s.E+'runs/dev/raw.partial.json':body}
  blobs,groups=p.transport_groups(changed);self.assertEqual(len(blobs),1);entries=[row for group in groups for row in group];self.assertEqual(len(entries),2);self.assertEqual({x['path']for x in entries},{c.SCOPE+name for name in changed});self.assertEqual(len({x['sha']for x in entries}),1)
  leaves={name:p.leaf(name,value)for name,value in changed.items()};self.assertEqual(len(leaves),2);self.assertTrue(all(row['size']==len(body)for row in leaves.values()));self.assertEqual(len({row['sha']for row in leaves.values()}),1)
 def test_large_transport_SHA_collision_refused(self):
  with patch.object(p,'gitsha',return_value='a'*40):self.reject(p.transport_groups,{s.E+'a.json':b'['+b' '*70000+b']',s.E+'b.json':b'['+b' '*70001+b']'})
 def test_actual_BASE_cumulative_counts(self):
  base=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec/kit')
  if not(base/'CONTINUATION.json').exists():self.skipTest('Fresh root reconstruction not complete')
  before=c.parse(base/'CONTINUATION.json')['execution_observed'];saved=copy.deepcopy(before)
  self.assertEqual((before['epoch31_cumulative_corpus_attempts'],before['epoch31_cumulative_completed_corpus_batches'],before['epoch31_cumulative_bounded_native_process_attempts']),(26,24,32))
  counts=r.cumulative_counts({'worker_attempts':1,'corpus_batches_attempted':2,'completed_corpus_batches':2});self.assertEqual((counts['corpus_attempts'],counts['completed_corpus_batches'],counts['bounded_native_process_attempts']),(28,26,33));self.assertEqual(counts['qualification_attempts'],6);self.assertEqual(before,saved)
 def test_exact_pretrained_source_not_new_artifact(self):
  source={'epoch':32,'kind':s.KIND,'repository':s.MODEL_REPOSITORY,'revision':s.MODEL_REVISION,'weights_file':s.MODEL_WEIGHTS['file'],'weights_bytes':s.MODEL_WEIGHTS['bytes'],'weights_sha256':s.MODEL_WEIGHTS['sha256'],'training_lineage_complete':False}
  pin=self.put(s.MODEL_SOURCE_PATH,source);p.pretrained_source_ready(self.root,self.rows(),pin)
  for key,value in [('revision','0'*40),('weights_sha256','0'*64),('training_lineage_complete',True),('weights_bytes',True)]:
   wrong=copy.deepcopy(source);wrong[key]=value;pin=self.put(s.MODEL_SOURCE_PATH,wrong);self.reject(p.pretrained_source_ready,self.root,self.rows(),pin)
 def test_complete_engineering_refusal_is_not_positive_DEV(self):
  raw,e,_=self.capture();raw['counters']['NLI_forward_pairs_completed']=18;raw['counters'].update(corpus_batches_attempted=1,corpus_batches_completed=1);(self.root/s.CORPUS_RESERVATION_PATHS['dev']).unlink();raw['corpus_reservations']['dev']=None;e.update(corpus_reservations=raw['corpus_reservations'],corpus_reservation_count=1,status='WORKER_ENGINEERING_REJECTED',exit_code=2);raw['status']='ENGINEERING_REJECTED_DEV_NOT_STARTED';pin=self.put(s.E+'runs/dev/raw.json',raw);e.update(raw_bytes=pin['bytes'],raw_sha256=pin['sha256'],raw_operation_counters=raw['counters']);self.put(s.E+'runs/dev/execution.json',e)
  value=r.phase_evidence(self.root,'dev',self.planref);self.assertEqual(value['actual']['NLI_forward_pairs_completed'],18);self.assertFalse(r.phase_completed(value));total=r.aggregate_actual(value);self.assertEqual(total['corpus_batches_attempted'],1);self.assertEqual(total['completed_corpus_batches'],1);self.assertEqual(r.cumulative_counts(total)['corpus_attempts'],27)
  # Batch completion means closed execution; a distinct frozen scorer gate is
  # still required for DEV qualification and is never inferred from completion.
 def test_partial_capture_keeps_known_corpora_but_not_tail_certainty(self):
  self.capture(partial=True);value=r.phase_evidence(self.root,'dev',self.planref);total=r.aggregate_actual(value)
  self.assertIsNone(total['corpus_batches_attempted']);self.assertIsNone(total['completed_corpus_batches']);self.assertIsNone(r.cumulative_counts(total)['corpus_attempts'])
  self.assertEqual(total['known_corpus_reservation_count'],2);self.assertEqual(total['known_corpus_batches_attempted_at_last_capture'],2)
 def test_corpus_reservation_tamper_refused(self):
  self.capture();path=s.CORPUS_RESERVATION_PATHS['engineering'];wrong=c.parse(self.root/path);wrong['automatic_retry']=True;self.put(path,wrong);self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_new_parameter_payload_forbidden(self):
  self.reject(c.public_text,s.E+'trained-parameters.public.json',b'{}')

if __name__=='__main__':unittest.main()
