"""Disjoint metadata fixtures only; never calls run(), real labels or evaluator."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ast,copy,json,unittest
import assemble_failure_metadata_v1 as m


def fixtures():
    env={'schema_version':1,'epoch':39,'kind':m.KIND,'phase':'dev'}
    ids=['disjoint-fixture-'+str(i)for i in range(12)]
    counters={'NLI_forward_calls_completed':48,'NLI_readouts_completed':48,'corpus_batches_attempted':1,'corpus_batches_completed':1,'native_queries_completed':12,'semantic_gold_labels_decoded':0}
    plan={**env,'source_checkpoint':m.BASE,'pins':[{}for _ in range(354)],'arms':m.ARMS,'data_roles':{'train':[],'dev':ids,'calibration':[],'confirmation':[]},'expected_operation_counters':{'dev':counters}}
    cases=[]
    for i,caseid in enumerate(ids):
        timing={k:i+1.0 for k in ('pair_tokenization_seconds','NNI_forward_seconds','reader_total_seconds','context_order_seconds','native_query_seconds')};timing['scope']='disjoint metadata scope'
        cases.append({'id':caseid,'readouts':{a:{'timing':copy.deepcopy(timing)}for a in m.ARMS}})
    rids=[case+'::'+a for case in ids for a in m.ARMS]
    raw={**env,'plan_sha256':m.PLAN_SHA,'status':'DEV_FORECASTS_COMPLETE_NO_GOLD','errors':[],'cases':cases,'completed_readout_ids':rids,'required_readout_ids':rids,'counters':counters,'closure_facts':{'native_child_closed':True,'model_profiles_disposed':['xxlarge','b354']},'wall_seconds':3.0,'resources':{'scope':'disjoint metadata'}}
    execution={**env,'plan_sha256':m.PLAN_SHA,'raw_operation_counters':counters,'operation_counts_complete':True,'status':'WORKER_COMPLETED','exit_code':0,'verified_worker_starts':1,'worker_popen_attempts':1,'uncertain_start':False,'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':3.1,'largest_child_peak_RSS_bytes':1234,'children_user_seconds':2.0,'children_system_seconds':.1}
    docs={'plan':plan,'raw':raw,'execution':execution,
          'source_admission':{**env,'published_source_commit':m.SOURCE,'verified_actual_remote_readback':True},
          'observer':{**env,'physical_closure_passed':True,'source_plan_sha256':m.PLAN_SHA,'unknown_physical_ownership':False,'observed_supervisor_exit_wait_status':0},
          'physical_closure':{**env,'physical_closure_passed':True,'checks_passed':True,'source_plan_sha256':m.PLAN_SHA,'frozen_pins_verified_unchanged':354},
          'gold_admission':dict(env),
          'gold_join_report':{**env,'status':'GOLD_JOIN_FAILED_FINAL_NO_RETRY','source_plan_sha256':m.PLAN_SHA,'semantic_labels_decoded':2,'decode_attempted_tokens':2,'semantic_decode_count_uncertain':False,'label_reader_calls':1,'errors':['ValueError:UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP'],'original_archive_gold_traversals':0,'model_tokenizer_native_calls':0,'used_confirmation_identities':[]},
          'source_representation_finding':{**env,'phase':'source_contract_audit_after_closed_run'},
          'independent_custody_failure':{**env,'checks_passed':True,'scientific_evaluation_executed':False,'semantic_label_tokens_decoded':2,'semantic_decode_count_uncertain':False}}
    for i in range(2):
        docs[f'progress_{i:02d}_before']={**env,'caseid':ids[i],'previous_semantic_decodes':i,'token_sha256':'0'*64,'decode_started':True,'decode_completed':False}
        docs[f'progress_{i:02d}_after']={**env,'caseid':ids[i],'semantic_decodes_completed':i+1,'decode_completed':True,'supported_literal':i==0}
    protocol={'epoch':39,'kind':m.KIND,'postmeasurement_metadata_only':True,'root_reported_EVALUATE_invocations':0,'references':{k:{'path':v,'bytes':1,'sha256':'0'*64}for k,v in m.PATHS.items()}}
    return protocol,docs


class FailureMetadata(unittest.TestCase):
    def reject(self,section,key,value):
        p,d=fixtures();d[section][key]=value
        with self.assertRaises((ValueError,KeyError)):m.assemble(p,d)
    def test_success_is_failure_only_and_never_quality_score(self):
        p,d=fixtures();out=m.assemble(p,d)
        self.assertEqual(out['status'],'REJECTED_DEV_INTEGRITY');self.assertFalse(out['checks_passed']);self.assertFalse(out['dev_passed']);self.assertFalse(out['evaluation_executed']);self.assertIsNone(out['metrics'])
        self.assertEqual(len(out['gate_checks']),15);self.assertEqual(set(out['gate_checks'].values()),{'NOT_EVALUATED'});self.assertTrue(all(v is None for row in out['quality_metrics'].values()for v in row.values()))
        self.assertEqual(out['actual_execution']['actual_NLI_forwards'],48);self.assertEqual(out['label_custody']['semantic_label_decodes'],2);self.assertEqual(out['label_custody']['remaining_selected_tokens_opaque'],10);self.assertTrue(all(out[k] is v for k,v in m.FLAGS.items()))
    def test_public_timing_interpolation_only(self):
        p,d=fixtures();out=m.assemble(p,d);q=out['timing_metadata']['per_arm'][m.ARMS[0]]['NNI_forward_seconds'];self.assertEqual(q['p50'],6.5);self.assertAlmostEqual(q['p95'],11.45);self.assertEqual(q['N'],12)
    def test_no_quality_input_mutation(self):
        p,d=fixtures();before=copy.deepcopy(d);m.assemble(p,d);self.assertEqual(before,d)
    def test_exact_two_certain_decodes(self):
        for key,value in [('semantic_labels_decoded',3),('decode_attempted_tokens',3),('semantic_decode_count_uncertain',True),('label_reader_calls',2),('joined_labels',{})]:self.reject('gold_join_report',key,value)
    def test_no_remap_different_failure_or_extra_work(self):
        for key,value in [('errors',['other failure']),('original_archive_gold_traversals',1),('model_tokenizer_native_calls',1),('used_confirmation_identities',['forbidden'])]:self.reject('gold_join_report',key,value)
    def test_progress_cannot_contain_label_values_or_change_order(self):
        self.reject('progress_01_after','labels',{'forbidden':'fixture'});self.reject('progress_01_after','supported_literal',True);self.reject('progress_01_after','semantic_decodes_completed',3);self.reject('progress_00_before','caseid','wrong')
    def test_incomplete_or_unknown_execution_refused(self):
        for key,value in [('operation_counts_complete',False),('uncertain_start',True),('owned_live_processes_closed',False),('exit_code',1),('verified_worker_starts',0)]:self.reject('execution',key,value)
    def test_observer_unknown_and_source_change_refused(self):
        self.reject('observer','unknown_physical_ownership',True);self.reject('observer','observed_supervisor_exit_wait_status',None);self.reject('physical_closure','frozen_pins_verified_unchanged',353);self.reject('source_admission','published_source_commit','0'*40)
    def test_missing_readout_or_counter_refused(self):
        p,d=fixtures();d['raw']['completed_readout_ids']=d['raw']['completed_readout_ids'][:-1]
        with self.assertRaises(ValueError):m.assemble(p,d)
        p,d=fixtures();d['raw']['counters']=dict(d['raw']['counters'],NLI_forward_calls_completed=47)
        with self.assertRaises(ValueError):m.assemble(p,d)
    def test_not_evaluate_and_type_sensitive_counts(self):
        for value in (1,False):
            p,d=fixtures();p['root_reported_EVALUATE_invocations']=value
            with self.assertRaises(ValueError):m.assemble(p,d)
        self.reject('gold_join_report','semantic_labels_decoded',2.0)
    def test_strict_json_and_external_paths(self):
        for b in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.assertRaises(ValueError):m.loads(b)
        for path in ('../vault.bin','/tmp/vault.bin','a\\b'):
            with self.assertRaises(ValueError):m.public_path(Path('/tmp/disjoint-fixture-root'),path)
    def test_finite_timing_and_stdlib_imports_only(self):
        with self.assertRaises(ValueError):m.quantile([float('nan')],.5)
        tree=ast.parse(Path(m.__file__).read_text());imports={n.names[0].name.split('.')[0]for n in ast.walk(tree)if isinstance(n,ast.Import)}
        self.assertTrue(imports<={'sys','argparse','copy','hashlib','json','math','os'})
        test_tree=ast.parse(Path(__file__).read_text());self.assertFalse(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='run'for n in ast.walk(test_tree)))


if __name__=='__main__':unittest.main()
