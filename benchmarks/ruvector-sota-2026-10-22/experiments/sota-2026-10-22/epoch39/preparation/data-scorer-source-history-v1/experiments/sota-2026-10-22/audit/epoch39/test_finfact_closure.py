import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import finfact_io as I
import finfact_closure as C
import finfact_metrics as M
import test_finfact_metrics as MT
import test_finfact_execution as XT
class Closure(unittest.TestCase):
 def fixture(self,root,bad_tree=False,bad_raw=False):
  env={'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev'};observer=root/'unrelated-observer.py';observer.write_text('# unrelated pure source fixture\n');oref=I.raw_ref(observer);expected={'epoch':39,'kind':I.KIND,'dev':{'unrelated_counter':12},'variable_observed_counters':['BGE_forward_calls_attempted','BGE_forward_calls_completed','Python_literal_loopback_capability_binds_allowed']};er=I.put(root/'expected.json',expected);ids=['unrelated-toy-'+str(i)for i in range(12)];plan={**env,'data_roles':{'train':[],'dev':ids,'calibration':[],'confirmation':[]},'arms':M.ARMS,'used_confirmation_identities':[],'actual_NLI_forwards':48,'source_freeze_sha256':'f'*64,'source_freeze':{'sha256':'f'*64},'observer_source':oref,'observer_helper_source':oref,'expected_counters_source':er,'expected_operation_counters':{'dev':expected['dev']}};pr=I.put(root/'plan.json',plan);ps=pr['sha256'];want=[i+'::'+a for i in ids for a in M.ARMS];rows=[MT.MetricsTest().row(i)for i in range(12)]
  for row in rows:
   row['source_unit_ids']=[0];row['context_order_seconds']=.001;row['native_query_seconds']=.0001
   for r in row['readouts'].values():r['timing']={'pair_tokenization_seconds':.01,'NNI_forward_seconds':.02,'reader_total_seconds':.04,'context_order_seconds':.001,'native_query_seconds':.0001,'scope':'unrelatedtoyfixture'}
  facts={'physical_readouts_completed':48,'model_profiles_disposed':['xxlarge','b354'],'native_child_closed':True,'all_forecasts_closed_before_gold':True};raw={**env,'source_checkpoint':I.SOURCE,'plan_sha256':ps,'status':'DEV_FORECASTS_COMPLETE_NO_GOLD','errors':[],'cases':rows,'required_readout_ids':want,'completed_readout_ids':want,'closure_facts':facts,'reader_lifecycle':XT.Execution().life(),'model_runtime_receipts':XT.Execution().runtime(),'offline_policy':{'clean':True,'literal_capability_bind_closed':True,'allowed_capability_count':1,'violations_count':0},'native_state':{'capture_complete':True,'child_closed':True},'wall_seconds':5,'resources':{'cpu_affinity':[0,1],'torch_num_threads':2,'torch_num_interop_threads':1,'user_seconds':2.,'system_seconds':.1,'max_rss_kib':123},'counters':{'unrelated_counter':12,'BGE_forward_calls_attempted':24,'BGE_forward_calls_completed':24,'Python_literal_loopback_capability_binds_allowed':1}};rr=I.put(root/'raw.json',raw);dispatch=I.put(root/'dispatch.json',{**env,'plan_sha256':ps});execution=I.put(root/'execution.json',{**env,'plan_sha256':ps,'raw':pr if bad_raw else rr});reservation=I.put(root/'reservation.json',{**env,'plan_sha256':ps});completion=I.put(root/'completion.json',{**env,'plan_sha256':ps});proof=I.put(root/'proof.json',{**env,'source_plan_sha256':ps,'physical_supervisor_closed':True,'physical_supervisor_absent':False,'observed_supervisor_state':'Z','physical_closure_passed':True,'unknown_physical_ownership':False,'owned_worker_group_members':[],'evidence':{'dispatch_attempt':dispatch,'execution':execution,'reservation':reservation,'completion':completion}});commit='a'*40;independent=I.put(root/'independent.json',{**env,'checks_passed':True,'verified_actual_remote_readback':True,'commit':commit,'source_plan_sha256':ps,'source_freeze_sha256':'f'*64,'tree_sha':'b'*40});source=I.put(root/'source.json',{**env,'checks_passed':True,'verified_actual_remote_readback':True,'actual_source_commit':commit,'published_source_commit':commit,'source_plan_sha256':ps,'plan_sha256':ps,'source_freeze_sha256':'f'*64,'tree_sha':('c'if bad_tree else'b')*40,'independent_actual_source_readback':independent});return I.put(root/'admission.json',{**env,'source_checkpoint':I.SOURCE,'root_custodian_authorized':True,'approved_late_gold_read':True,'source_plan_sha256':ps,'source_commit':commit,'evidence':{'plan':pr,'raw':rr,'execution':execution,'dispatch':dispatch,'observer':oref,'physical_closure':proof,'source_admission':source}})
 def test_bundle_binds_source_readback_and_actual_readouts_before_physical_check(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);a=self.fixture(root)
   with patch.object(C.D,'check_physical_gold_fence',return_value={})as fence:
    r=C.checked_bundle(a,root);self.assertEqual(len(r['readout_ids']),48);fence.assert_called_once();self.assertEqual(r['objects']['physical_closure']['observed_supervisor_state'],'Z');self.assertFalse(r['objects']['physical_closure']['physical_supervisor_absent'])
 def test_independent_tree_mismatch_stops_before_gold(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);a=self.fixture(root,bad_tree=True)
   with patch.object(C.D,'check_physical_gold_fence')as fence:
    with self.assertRaisesRegex(ValueError,'TREE_MISMATCH'):C.checked_bundle(a,root)
    fence.assert_not_called()
 def test_executor_raw_mismatch_stops(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);a=self.fixture(root,bad_raw=True)
   with self.assertRaisesRegex(ValueError,'CAPTURED_RAW'):C.checked_bundle(a,root)
if __name__=='__main__':unittest.main()
