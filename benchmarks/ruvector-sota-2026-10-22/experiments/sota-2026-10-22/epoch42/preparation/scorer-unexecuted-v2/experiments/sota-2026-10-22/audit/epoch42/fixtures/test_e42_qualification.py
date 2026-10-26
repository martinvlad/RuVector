"""Disjoint metadata qualification fixtures, never actual process/data records."""
import unittest
from unittest.mock import patch
import e42_qualification as Q
F=Q.F
class Qualification(unittest.TestCase):
 def fixture(self):
  ref=lambda x:{'path':x,'bytes':1,'sha256':'a'*64};refs={k:ref(k)for k in ['raw','execution','dispatch']};reservation=ref('reservation');identity={'pid':990000,'startticks':91,'pgid':990000,'sid':990000};cpu={'status':'CPU_GUARD_INSTALLED_BEFORE_EXEC','CPU_affinity':[0,1],'actual_proc_status':{'NoNewPrivs':'1','Seccomp':'2'}}
  # Literal E42 core wire, deliberately not copied from Q.INVARIANTS.
  keys=['raw_forecasts_complete_without_gold','exact_frozen_operation_counts','forbidden_operation_counts_zero','worker_errors_empty','offline_policy_closed','all72_unique_physical_windows','all72_required_physical_windows','native_child_closed','single_tasksource_reader_disposed','all36_unique_derived_forecasts','all36_required_derived_forecasts','packing_tokenizer_calls_complete','all_forecasts_closed_before_gold','gold_not_decoded'];self.assertEqual(set(keys),Q.INVARIANTS)
  e={'status':'WORKER_COMPLETED','wall_seconds_including_init_cleanup':40.,'exit_code':0,'launcher_error':None,'cleanup_errors':[],'stdout_stderr_capture_completed':True,'uncertain_start':False,'owned_live_processes_closed':True,'owned_live_group_members':[],'source_plan_unchanged':True,'raw_closure_invariants':dict.fromkeys(keys,True),'raw':refs['raw'],'raw_sha256':'a'*64,'raw_bytes':1,'raw_operation_counters_source':'raw.json','operation_counts_complete':True,'raw_operation_counters':{'NLI_readouts_completed':72},'dispatch_attempt':refs['dispatch'],'dispatch_reservation':reservation,'worker_cpu_guard_preexec_artifact':ref('cpu'),'worker_cpu_guard_preexec':cpu,'plan_sha256':'b'*64,'supervisor_identity':identity};c={'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','status':'SUPERVISOR_ABOUT_TO_EXIT','plan_sha256':'b'*64,'execution_sha256':'a'*64,'execution_status':'WORKER_COMPLETED','intended_exit_code':0,'exit_code_observed_by_root':False,'requires_external_physical_supervisor_closure':True,'supervisor_identity':identity};p={'evidence':{'reservation':reservation},'physical_supervisor_absent':False,'physical_supervisor_closed':True,'observed_supervisor_state':'Z','supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE','observed_supervisor_exit_wait_status':0,'observed_closed_by_monotonic_seconds':160.,'supervisor_identity':identity};return e,c,{'counters':{'NLI_readouts_completed':72}},refs,p,'.',{'dispatch_monotonic_seconds':100.},cpu
 def call(self,a):
  with patch.object(F,'load_ref',return_value=a[-1]):return Q.supervisor_qualification(*a[:-1])
 def test_literal_successful_schema(self):self.assertTrue(self.call(self.fixture())['checks_passed'])
 def test_absent_nonzero_or_overfullbound_never_qualifies(self):
  for change in [{'physical_supervisor_absent':True,'observed_supervisor_state':'ABSENT','observed_supervisor_exit_wait_status':None},{'observed_supervisor_exit_wait_status':256},{'observed_closed_by_monotonic_seconds':701.}]:
   a=self.fixture();a[4].update(change)
   with self.assertRaises(ValueError):self.call(a)
 def test_failed_worker_completion_or_plan_or_invariant_rejected(self):
  for change in [{'status':'WORKER_FAILED'},{'wall_seconds_including_init_cleanup':601.},{'exit_code':2}]:
   a=self.fixture();a[0].update(change)
   with self.assertRaises(ValueError):self.call(a)
  a=self.fixture();a[1]['plan_sha256']='c'*64
  with self.assertRaises(ValueError):self.call(a)
  a=self.fixture();a[0]['raw_closure_invariants']['gold_not_decoded']=False
  with self.assertRaises(ValueError):self.call(a)
if __name__=='__main__':unittest.main()
