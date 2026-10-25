"""Unrelated metadata-only qualifications; never actual run/case/gold artifacts."""
import copy,unittest
from unittest.mock import patch
import contractnli_execution as X
import contractnli_io as I
class ExecutionFixtures(unittest.TestCase):
 def fixture(self):
  ref=lambda x:{'path':x,'bytes':1,'sha256':'a'*64}
  refs={k:ref(k)for k in ['raw','execution','dispatch']};reservation=ref('reservation');ident={'pid':91,'startticks':9,'pgid':91,'sid':91};cpu={'status':'CPU_GUARD_INSTALLED_BEFORE_EXEC','CPU_affinity':[0,1],'actual_proc_status':{'NoNewPrivs':'1','Seccomp':'2'}}
  e={'status':'WORKER_COMPLETED','wall_seconds_including_init_cleanup':40.,'exit_code':0,'launcher_error':None,'cleanup_errors':[],'stdout_stderr_capture_completed':True,'uncertain_start':False,'owned_live_processes_closed':True,'owned_live_group_members':[],'source_plan_unchanged':True,'raw_closure_invariants':dict.fromkeys(X.SUPERVISOR_INVARIANT_KEYS,True),'raw':refs['raw'],'raw_sha256':'a'*64,'raw_bytes':1,'raw_operation_counters_source':'raw.json','operation_counts_complete':True,'raw_operation_counters':{'n':48},'dispatch_attempt':refs['dispatch'],'dispatch_reservation':reservation,'worker_cpu_guard_preexec_artifact':ref('cpu'),'worker_cpu_guard_preexec':cpu,'plan_sha256':'b'*64,'supervisor_identity':ident}
  c={'schema_version':1,'epoch':40,'kind':I.KIND,'phase':'dev','status':'SUPERVISOR_ABOUT_TO_EXIT','plan_sha256':'b'*64,'execution_sha256':'a'*64,'execution_status':'WORKER_COMPLETED','intended_exit_code':0,'exit_code_observed_by_root':False,'requires_external_physical_supervisor_closure':True,'supervisor_identity':ident}
  p={'evidence':{'reservation':reservation},'physical_supervisor_absent':False,'physical_supervisor_closed':True,'observed_supervisor_state':'Z','supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE','observed_supervisor_exit_wait_status':0,'observed_closed_by_monotonic_seconds':160.,'supervisor_identity':ident};return e,c,{'counters':{'n':48}},refs,p,'.',{'dispatch_monotonic_seconds':100.},cpu
 def run_q(self,args):
  with patch.object(I,'load_ref',return_value=args[-1]):return X.supervisor_qualification(*args[:-1])
 def test_exact_qualified_schema(self):self.assertTrue(self.run_q(self.fixture())['checks_passed'])
 def test_failed_overbudget_absent_nonzero_rejected(self):
  for field,value in [('status','WORKER_FAILED'),('wall_seconds_including_init_cleanup',601.),('exit_code',2),('cleanup_errors',['FAIL'])]:
   a=self.fixture();a[0][field]=value
   with self.assertRaises(ValueError):self.run_q(a)
  for delta in [{'physical_supervisor_absent':True,'observed_supervisor_state':'ABSENT','observed_supervisor_exit_wait_status':None},{'observed_supervisor_exit_wait_status':256},{'observed_closed_by_monotonic_seconds':701.}]:
   a=self.fixture();a[4].update(delta)
   with self.assertRaises(ValueError):self.run_q(a)
 def test_completion_plan_and_invariant_tamper(self):
  a=self.fixture();a[1]['plan_sha256']='c'*64
  with self.assertRaises(ValueError):self.run_q(a)
  a=self.fixture();a[0]['raw_closure_invariants']['gold_not_decoded']=False
  with self.assertRaises(ValueError):self.run_q(a)
if __name__=='__main__':unittest.main()
