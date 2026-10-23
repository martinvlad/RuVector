"""Pure authored receipt fault fixtures, never actual model/native measurements."""
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_epoch19_scorer_under_test',HERE/'scorer.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
P=json.loads((HERE/'protocol.json').read_text())


def fixtures():
    """Intentionally synthetic, obvious hashes: no actual state/ranking is claimed."""
    plan={'schema_version':1,'epoch':19,'source_checkpoint':P['source_head'],
        'study_id':'native-semantic-precision-qualification-e19',
        'audit_protocol':S.file_identity(HERE/'protocol.json',S.PROTOCOL_REL),
        'spec_sha256':P['parent_spec']['sha256'],'native_addendum_sha256':P['native_addendum']['sha256'],
        'train':[],'calibration':[],'datasets':[],'confirmation':[],
        'limits':{'native_batches':1,'worker_attempts':1,'threads':2,'interop_threads':1,'seconds_per_batch':600,
            'seconds_per_decision':30,'candidate_configs':1,'paid_calls':0,'GPU_calls':0,'nli_forwards':6,
            'native_invocations':1,'native_queries':3,'other_model_forwards':0,'benchmark_corpora':0}}
    assets=[{k:r[k]for k in ('path','bytes','sha256')}for r in P['model']['assets']]
    assethash={Path(r['path']).name:r['sha256']for r in assets}
    raw={'schema_version':1,'epoch':19,'status':'COMPLETED','plan_sha256':'e'*64,'worker_pid':123456,'worker_pgid':123456,'cleanup':{'native_helper_pid':123457},
        'model_provenance':{'repo':P['model']['repo'],'revision':P['model']['revision'],'versions':P['model']['versions'],
            'architecture':{k:P['model']['architecture'][k]for k in ('layers','hidden_size','attention_heads','classes')},
            'asset_identities':assets,'original_checkpoint_sha256':assethash['pytorch_model.bin'],'config_sha256':assethash['config.json'],
            'raw_label_indices':dict(S.RAW_INDEX),'typed_order':list(S.ORDER),
            'loading_info':{k:[]for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')},
            'loading_flags':{'local_files_only':True,'trust_remote_code':False,'use_safetensors':False,'weights_only':True,
                'torch_dtype':'torch.float32','output_loading_info':True},'source_storage_dtype_inventory':{'torch.float16':10}},
        'tokenizer':{'spm_sha256':assethash['spm.model'],'converted_backend_sha256':'b'*64,'cls_id':1,'sep_id':2,'pad_id':0,'unk_id':3,
            'pair_format':'[CLS]premise[SEP]hypothesis[SEP]','high_level_backend_feed_equality_verified':True},
        'fp32_state':{'sha256':'a'*64,'parameter_count':1000,'parameter_dtypes':['torch.float32'],'buffer_dtypes':['torch.int64'],
            'devices':['cpu'],'model_instance_token':'synthetic-fixture-model-instance','classifier':{'weight_shape':[3,1536],'bias_shape':[3],'weight_dtype':'torch.float32','bias_dtype':'torch.float32'},
            'eligible_linear_modules':['classifier'],'eval':True,'inference_mode':True,'autocast':False,'threads':2,'interop_threads':1,'deterministic_algorithms':True},
        'int8_state':{'sha256':'c'*64,'eligible_linear_modules':['classifier'],
            'quantized_linear_modules':[{'name':'classifier','weight_dtype':'torch.qint8','shape':[3,1536]}],'quantized_linear_count':1,
            'model_instance_token':'synthetic-fixture-model-instance','fbgemm':True,'same_model_object':True,'inplace':True,'eval':True,'inference_mode':True,'autocast':False,'threads':2,'interop_threads':1,
            'device':'cpu','quantization_recipe':P['model']['quantization']},
        'forwards':[],
        'counters':{'model_initializations':1,'quantization_initializations':1,'nli_forward_pairs_attempted':6,'nli_forward_pairs_completed':6,
            'fp32_forwards_attempted':3,'fp32_forwards_completed':3,'int8_forwards_attempted':3,'int8_forwards_completed':3,'native_invocations':1,
            'native_queries':3,'other_model_forwards':0,'BGE_forwards':0,'ORT_sessions':0,'previous_reader_forwards':0,'native104_calls':0,
            'benchmark_HTTP_requests':0,'benchmark_corpora':0,'paid_API_calls':0,'GPU_calls':0,'train_fits':0,'calibration_fits':0,'CONF_calls':0}}
    raw_labels={'Entailment':2,'Contradiction':0,'NotMentioned':1}
    for precision in ('FP32','INT8'):
        for f in P['fixtures']:
            z=[0.,0.,0.];z[raw_labels[f['expected_typed_label']]]=4.
            raw['forwards'].append({'precision':precision,'fixture_id':f['id'],'fixture_sha256':f['sha256'],
                'premise':f['premise'],'hypothesis':f['hypothesis'],'input_ids':[1,4,2,5,2],'attention_mask':[1,1,1,1,1],
                'token_type_ids':[0,0,0,1,1],'offsets':[[0,0],[0,len(f['premise'])],[0,0],[0,len(f['hypothesis'])],[0,0]],
                'raw_logits':z,'typed_probabilities':S.probability_replay(z),'prediction':f['expected_typed_label'],
                'elapsed_seconds':0.1,'truncated':False,'padding':False,'feed_dtype':'torch.int64','feed_device':'cpu','batch_size':1,
                'raw_logit_dtype':'float32','raw_logit_shape':[1,3],
                'inference_mode_enabled':True,'grad_enabled':False,
                'high_level_pair_feed':{'input_ids':[1,4,2,5,2],'attention_mask':[1,1,1,1,1],'token_type_ids':[0,0,0,1,1]}})
    ref=S.engineering_reference(P['fixtures']);bundle={k:ref[k]for k in ('vectors','query_vectors')}
    bundlehash=hashlib.sha256((json.dumps(bundle,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()).hexdigest()
    native={'queries':[{'ids':[0,1,2],'latency_ms':.1}for _ in range(3)],'native_binary_sha256':next(r['sha256']for r in P['native']['files']if r['path'].endswith('/ruvector.node')),
        'package_version':'0.1.33','native':True,'vectors':3,'bundle_sha256':bundlehash}
    raw['native_trace']={'sourceIDs':[f['id']for f in P['fixtures']],'premises':[f['premise']for f in P['fixtures']],
        'hypotheses':[f['hypothesis']for f in P['fixtures']],'bundle':bundle,'raw_native_output':native,'initial_length':0,'final_length':3,
        'native_selection_affects_NLI':False,'native_helper_pid':123457,'raw_scores_available':False,'reference':{k:v for k,v in ref.items()if k not in ('vectors','query_vectors')},
        'bundle_serialization':'UTF8 JSON ensure_ascii=False indent=2 allow_nan=False followed by LF'}
    execution={'plan_sha256':'e'*64,'source_plan_unchanged':True,'error':None,
        'status':'COMPLETED_AWAITING_INDEPENDENT_ENGINEERING_REPLAY','unspent_epoch_slots_closed':True,'allowed_further_qualification_attempts':0,'automatic_retry':False,'qualification_worker_attempts':1,'verified_worker_starts':1,'worker_exit_code':0,'elapsed_seconds':100.,'CPU_affinity':[0,1],
        'worker_pid':123456,'worker_pgid':123456,'native_helper_pid':123457,'user_seconds':90.,'system_seconds':2.,'peak_RSS_bytes':4096,
        'cleanup':{'worker_exited':True,'native_helper_exited':True,'process_group_empty':True,'owned_live_pids':[],'details':{'finished_within_deadline':True}}}
    return plan,raw,execution


class QualificationFaults(unittest.TestCase):
    def check_invalid(self,mutate):
        plan,raw,execution=fixtures();mutate(plan,raw,execution)
        report=S.evaluate(plan,raw,execution)
        self.assertFalse(report['checks_passed'],report)
        self.assertFalse(report['engineering_qualified'])
        self.assertFalse(report['accepted'])
        self.assertEqual(report['status'],'INCONCLUSIVE_INVALID_OR_INCOMPLETE_EXECUTION')

    def test_synthetic_receipts_qualify_engineering_only(self):
        report=S.evaluate(*fixtures())
        self.assertTrue(report['checks_passed'],report)
        self.assertTrue(report['engineering_qualified'],report)
        self.assertFalse(report['accepted']);self.assertIsNone(report['official_rank'])

    def test_cli_binds_external_raw_and_plan_bytes(self):
        p,r,e=fixtures()
        with tempfile.TemporaryDirectory(prefix='e19-pure-scorer-cli-') as folder:
            folder=Path(folder);planfile=folder/'plan.json';rawfile=folder/'raw.json';external=folder/'external.json'
            planfile.write_text(json.dumps(p,indent=2)+'\n')
            digest=hashlib.sha256(planfile.read_bytes()).hexdigest();r['plan_sha256']=digest;e['plan_sha256']=digest
            rawfile.write_text(json.dumps(r,indent=2)+'\n');e['raw_sha256']=hashlib.sha256(rawfile.read_bytes()).hexdigest()
            external.write_text(json.dumps(e,indent=2)+'\n')
            command=[sys.executable,'-B',str(HERE/'scorer.py'),'--plan',str(planfile),'--raw',str(rawfile),'--execution',str(external)]
            first=folder/'first.json';result=subprocess.run(command+['--out',str(first)],text=True,capture_output=True,check=True)
            self.assertTrue(json.loads(first.read_text())['engineering_qualified'],result.stdout)
            e['raw_sha256']='f'*64;external.write_text(json.dumps(e,indent=2)+'\n')
            second=folder/'second.json';subprocess.run(command+['--out',str(second)],text=True,capture_output=True,check=True)
            rejected=json.loads(second.read_text());self.assertFalse(rejected['engineering_qualified']);self.assertFalse(rejected['checks_passed'])
            third=folder/'third.json';missing=subprocess.run([sys.executable,'-B',str(HERE/'scorer.py'),'--plan',str(planfile),'--raw',str(rawfile),'--out',str(third)],text=True,capture_output=True)
            self.assertNotEqual(missing.returncode,0);self.assertFalse(third.exists())

    def test_stable_shift_invariant_raw_logit_softmax(self):
        a=S.probability_replay([0.,0.,2.]);b=S.probability_replay([-1001.,-1001.,-999.])
        self.assertEqual(a,b);self.assertAlmostEqual(a['Entailment'],math.exp(2)/(math.exp(2)+2))

    def test_literal_reference_is_known_unique_order(self):
        ref=S.engineering_reference(P['fixtures'])
        self.assertEqual(ref['vectors'][0][:5],[1,1,0,0,0]);self.assertEqual(ref['vectors'][1][:5],[1,1,1,0,0])
        self.assertEqual(ref['vectors'][2][:5],[0,0,0,1,1]);self.assertEqual(ref['cosine_order'],[[0,1,2]]*3)
        self.assertEqual(ref['lexical_order'],[[0,1,2]]*3);self.assertAlmostEqual(ref['cosine_similarity'][0][1],2/math.sqrt(6))

    def test_partial_status_cannot_qualify(self):self.check_invalid(lambda p,r,e:r.__setitem__('status','FAILED'))
    def test_loader_boolean_cannot_be_numeric(self):self.check_invalid(lambda p,r,e:r['model_provenance']['loading_flags'].__setitem__('weights_only',1))
    def test_nan_raw_logit(self):self.check_invalid(lambda p,r,e:r['forwards'][0]['raw_logits'].__setitem__(0,float('nan')))
    def test_probability_mass(self):self.check_invalid(lambda p,r,e:r['forwards'][0]['typed_probabilities'].__setitem__('Entailment',1.00001))
    def test_wrong_logit_label_map(self):
        def change(p,r,e):r['model_provenance']['raw_label_indices']={'entailment':0,'contradiction':2,'neutral':1}
        self.check_invalid(change)
    def test_normalized_but_wrong_softmax(self):
        def change(p,r,e):r['forwards'][0]['typed_probabilities']={k:1/3 for k in S.ORDER}
        self.check_invalid(change)
    def test_altered_hypothesis(self):self.check_invalid(lambda p,r,e:r['forwards'][0].__setitem__('hypothesis','The lamp is off.'))
    def test_changed_feed_across_precision(self):self.check_invalid(lambda p,r,e:r['forwards'][3]['input_ids'].__setitem__(1,17))
    def test_actual_gradient_context_rejected(self):self.check_invalid(lambda p,r,e:r['forwards'][0].__setitem__('grad_enabled',True))
    def test_high_level_feed_parity_rejected(self):self.check_invalid(lambda p,r,e:r['forwards'][0]['high_level_pair_feed']['input_ids'].__setitem__(1,29))
    def test_actual_model_object_token_mismatch(self):self.check_invalid(lambda p,r,e:r['int8_state'].__setitem__('model_instance_token','other-synthetic-model-instance'))
    def test_padding_disallowed(self):self.check_invalid(lambda p,r,e:r['forwards'][0]['attention_mask'].__setitem__(1,0))
    def test_offset_outside_original_source(self):self.check_invalid(lambda p,r,e:r['forwards'][0]['offsets'].__setitem__(1,[0,10000]))
    def test_seventh_neural_forward(self):self.check_invalid(lambda p,r,e:r['forwards'].append(copy.deepcopy(r['forwards'][0])))
    def test_counter_extra_neural_forward(self):self.check_invalid(lambda p,r,e:r['counters'].__setitem__('nli_forward_pairs_attempted',7))
    def test_boolean_counter_is_not_integer(self):self.check_invalid(lambda p,r,e:r['counters'].__setitem__('model_initializations',True))
    def test_hidden_BGE_forward(self):self.check_invalid(lambda p,r,e:r['counters'].__setitem__('BGE_forwards',1))
    def test_native_wrong_full_order(self):self.check_invalid(lambda p,r,e:r['native_trace']['raw_native_output']['queries'][0].__setitem__('ids',[1,0,2]))
    def test_native_duplicate_ids(self):self.check_invalid(lambda p,r,e:r['native_trace']['raw_native_output']['queries'][0].__setitem__('ids',[0,0,2]))
    def test_native_wrong_bundle_hash(self):self.check_invalid(lambda p,r,e:r['native_trace']['raw_native_output'].__setitem__('bundle_sha256','d'*64))
    def test_native_literal_vector_mutation(self):self.check_invalid(lambda p,r,e:r['native_trace']['bundle']['vectors'][0].__setitem__(0,9))
    def test_native_synthetic_retrieval_cannot_replace_premise(self):self.check_invalid(lambda p,r,e:r['native_trace'].__setitem__('native_selection_affects_NLI',True))
    def test_native_missing_search(self):self.check_invalid(lambda p,r,e:r['native_trace']['raw_native_output']['queries'].pop())
    def test_missing_external_cleanup_is_inconclusive(self):
        p,r,e=fixtures();report=S.evaluate(p,r)
        self.assertFalse(report['engineering_qualified']);self.assertFalse(report['checks_passed'])
    def test_worker_embedded_execution_cannot_self_certify(self):
        p,r,e=fixtures();r['execution']=e;report=S.evaluate(p,r)
        self.assertFalse(report['checks_passed']);self.assertFalse(report['engineering_qualified'])
    def test_outer_different_plan(self):self.check_invalid(lambda p,r,e:e.__setitem__('plan_sha256','f'*64))
    def test_outer_different_worker(self):self.check_invalid(lambda p,r,e:e.__setitem__('worker_pid',234567))
    def test_outer_different_native_helper(self):self.check_invalid(lambda p,r,e:e.__setitem__('native_helper_pid',234568))
    def test_incomplete_cleanup_deadline_proof(self):self.check_invalid(lambda p,r,e:e['cleanup']['details'].__setitem__('finished_within_deadline',False))
    def test_missing_plan_role(self):self.check_invalid(lambda p,r,e:p.pop('confirmation'))
    def test_zero_source_offsets_cannot_claim_complete_pair(self):
        def change(p,r,e):
            for row in r['forwards']:row['offsets']=[[0,0]for _ in row['input_ids']]
        self.check_invalid(change)
    def test_hidden_nonfinite_native_scores(self):
        def change(p,r,e):
            for q in r['native_trace']['raw_native_output']['queries']:q['scores']=[float('nan')]*3
        self.check_invalid(change)
    def test_inconsistent_native_score_presence(self):self.check_invalid(lambda p,r,e:r['native_trace']['raw_native_output']['queries'][0].__setitem__('scores',[1.,.8,0.]))
    def test_live_owned_process(self):self.check_invalid(lambda p,r,e:e['cleanup'].__setitem__('owned_live_pids',[123457]))
    def test_terminal_cleanup_deadline(self):self.check_invalid(lambda p,r,e:e.__setitem__('elapsed_seconds',600.001))
    def test_per_forward_deadline(self):self.check_invalid(lambda p,r,e:r['forwards'][0].__setitem__('elapsed_seconds',30.001))
    def test_uninspected_storage(self):self.check_invalid(lambda p,r,e:r['model_provenance'].__setitem__('source_storage_dtype_inventory','uninspected'))
    def test_unsafe_loader_flag(self):self.check_invalid(lambda p,r,e:r['model_provenance']['loading_flags'].__setitem__('weights_only',False))
    def test_missing_classifier_coverage(self):self.check_invalid(lambda p,r,e:r['model_provenance']['loading_info'].__setitem__('missing_keys',['classifier.weight']))
    def test_non_FP32_classifier(self):self.check_invalid(lambda p,r,e:r['fp32_state']['classifier'].__setitem__('weight_dtype','torch.float16'))
    def test_quantization_not_same_object(self):self.check_invalid(lambda p,r,e:r['int8_state'].__setitem__('same_model_object',False))
    def test_new_benchmark_role_forbidden(self):self.check_invalid(lambda p,r,e:p.__setitem__('datasets',['legal-input.jsonl']))
    def test_same_labels_can_still_fail_fidelity_gate(self):
        p,r,e=fixtures()
        for row in r['forwards'][3:]:
            z=[value/2 for value in row['raw_logits']];row['raw_logits']=z;row['typed_probabilities']=S.probability_replay(z)
        report=S.evaluate(p,r,e)
        self.assertTrue(report['checks_passed'],report);self.assertFalse(report['engineering_qualified'])
        self.assertEqual(report['FP32_correct'],3);self.assertEqual(report['INT8_correct'],3)
        self.assertGreater(report['maximum_absolute_per_class_probability_delta'],.05)
        self.assertEqual(report['status'],'REJECTED_ENGINEERING_QUALIFICATION')
    def test_semantic_failure_does_not_invent_cause_or_promote(self):
        p,r,e=fixtures()
        for row in r['forwards']:
            row['raw_logits']=[4.,0.,0.];row['typed_probabilities']=S.probability_replay(row['raw_logits']);row['prediction']='Contradiction'
        report=S.evaluate(p,r,e)
        self.assertTrue(report['checks_passed'],report);self.assertFalse(report['engineering_qualified'])
        self.assertEqual(report['FP32_correct'],1);self.assertEqual(report['INT8_correct'],1)
        self.assertEqual(report['cause_of_epoch18_collapse'],'UNPROVEN');self.assertFalse(report['accepted'])


if __name__=='__main__':unittest.main(verbosity=2)
