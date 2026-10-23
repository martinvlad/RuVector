"""Pure synthetic corruption tests; no model/tokenizer/native/source-label access."""
"""Synthetic receipt corruption tests only; no model/native/source-label access."""


import copy


import hashlib


import json


from pathlib import Path


import tempfile


import unittest


from unittest.mock import patch


import metrics as M


import replay as R
import trace_checks as T


import project_gold as G


from test_metrics import forward


def forward_fixture():
    row=forward({'Entailment':.98,'Contradiction':.01,'NotMentioned':.01})
    premise,hypothesis='The lamp is on.','The lamp is on.'
    ids=[1,279,6693,269,277,260,2,279,6693,269,277,260,2]
    feed={'input_ids':[ids],'attention_mask':[[1]*len(ids)],'token_type_ids':[[0]*7+[1]*6]}
    row.update(premise=premise,hypothesis=hypothesis,input_text_sha256=R.digest(R.canonical([premise,hypothesis])),
               raw_probabilities=[row['typed_probabilities'][x]for x in('Entailment','NotMentioned','Contradiction')],
               feed=feed,feed_sha256=R.digest(R.canonical(feed)),actual_tokens=len(ids),
               padding=False,truncation=False,inference_mode=True,cpu_autocast=False,elapsed_seconds=.2,
               model_state_sha256='a'*64,model_instance_token='0xunit-test-only',
               feed_dtype='torch.int64',feed_device='cpu',raw_logit_dtype='torch.float32',original_high_level_feed_equal=True)
    return row


def trace_fixture():
    vectors=[[1,1,0,0,0]+[0]*379,[1,1,1,0,0]+[0]*379,[0,0,0,1,1]+[0]*379]
    queries=[[1,1,0,0,0]+[0]*379 for _ in range(3)]
    bundle={'vectors':vectors,'query_vectors':queries}
    sha=R.digest((json.dumps(bundle,ensure_ascii=False,indent=2)+'\n').encode())
    trace={'bundle':bundle,'bundle_sha256':sha,
           'raw_native_output':{'native':True,'native_binary_sha256':R.BINARY_SHA,'package_version':'0.1.33',
                                'vectors':3,'bundle_sha256':sha,'queries':[{'ids':[0,1,2],'latency_ms':.1}for _ in range(3)]},
           'initial_length':0,'final_length':3,'source_script_sha256':R.NATIVE_SCRIPT_SHA,'helper_exit_code':0,
           'helper_exited':True,'candidate_depth':3,'native_helper_pid':999999991,'native_helper_pgid':999999990,
           'native_order_used_without_replacement':True,'raw_scores_available':False,'reference':R.reference(vectors,queries)}
    return trace,vectors,queries


def counters_fixture(complete):
    c={'model_initializations_attempted':1,'model_initializations_completed':1,
       'checkpoint_metadata_loads_attempted':1,'checkpoint_metadata_loads_completed':1,
       'nli_forward_pairs_attempted':75 if complete else 3,'nli_forward_pairs_completed':75 if complete else 3,
       'native_index_initializations_attempted':9 if complete else 1,'native_index_initializations_completed':9 if complete else 1,
       'native_queries_attempted':27 if complete else 3,'native_queries_completed':27 if complete else 3,
       'BGE_initializations_attempted':1 if complete else 0,'BGE_initializations_completed':1 if complete else 0,
       'ORT_sessions_attempted':1 if complete else 0,'ORT_sessions_completed':1 if complete else 0,
       'quantization_initializations':0,'paid_API_calls':0,'GPU_calls':0,'native104_calls':0,'previous_reader_forwards':0,
       'training_calibration_fits':0,'benchmark_HTTP_requests':0,'benchmark_documents_completed':8 if complete else 0,
       'benchmark_questions_completed':24 if complete else 0,'BGE_forwards_attempted':16 if complete else 0,
       'BGE_forwards_completed':16 if complete else 0,'BGE_texts_attempted':32 if complete else 0,
       'BGE_texts_completed':32 if complete else 0,'BGE_forward_seconds':1 if complete else 0}
    return {'counters':c,'documents':[{'source_units':[{}]}for _ in range(8)]if complete else []}


def token_proof_fixture():
    raw={'phase':'dev','status':'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE',
         'tokenizer':{'backend_sha256':R.read(R.PROTOCOL)['tokenizer']['operational_backend_sha256']},'canary_forwards':[{'forward':forward_fixture()}for _ in range(3)],
         'documents':[{'questions':[{'arms':{a:{'forward':forward_fixture()}for a in M.ARMS}}for _ in range(3)]}for _ in range(8)]}
    pairs=[x['forward']for x in raw['canary_forwards']]
    for doc in raw['documents']:
        for question in doc['questions']:pairs.extend(question['arms'][a]['forward']for a in M.ARMS)
    assets={r['remote_path']:r for r in R.read(R.PROTOCOL)['model']['assets']}
    proof={'checks_passed':True,'epoch':21,'phase':'dev','kind':'INDEPENDENT_POSTRUN_SOURCE_TOKENIZER_JSON_FEED_REPLAY',
           'plan_sha256':'c'*64,'raw_receipt_sha256':'a'*64,'actual_feed_pairs_replayed':75,
           'feeds':[{'forward_index':i,'input_text_sha256':p['input_text_sha256'],'feed_sha256':p['feed_sha256'],'tokens':p['actual_tokens']}for i,p in enumerate(pairs)],
           'model_native_forwards':0,'gold_labels_read':0,'neural_framework_imports':[],
           'actual_worker_backend_sha256':R.read(R.PROTOCOL)['tokenizer']['operational_backend_sha256'],'tokenizers_version':'0.21.4',
           'independent_reconstructed_backend_sha256':R.read(R.PROTOCOL)['tokenizer']['operational_backend_sha256'],
           'execution_receipt':{'path':'execution.json','bytes':100,'sha256':'e'*64},
           'assets':[{k:assets[name][k]for k in('path','bytes','sha256')}for name in R.read(R.PROTOCOL)['tokenizer']['source_asset_names']]}
    return raw,proof


class FeedFaultTests(unittest.TestCase):
    def check(self,row):return R.forward_replay(row,'The lamp is on.','The lamp is on.','a'*64,'0xunit-test-only')

    def test_structurally_valid_synthetic_feed(self):self.assertEqual(self.check(forward_fixture()),.2)

    def test_text_pair_changed_rejected(self):
        r=forward_fixture();r['premise']='The lamp is not on.'
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_actual_feed_hash_tampering_rejected(self):
        r=forward_fixture();r['feed']['input_ids'][0][1]=4
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_boolean_id_substitution_rejected(self):
        r=forward_fixture();r['feed']['input_ids'][0][0]=False;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_attention_hole_rejected(self):
        r=forward_fixture();r['feed']['attention_mask'][0][3]=0;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_missing_official_token_types_rejected(self):
        r=forward_fixture();del r['feed']['token_type_ids'];r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_silent_truncation_rejected(self):
        r=forward_fixture();r['truncation']=True
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_wrong_instance_rejected(self):
        r=forward_fixture();r['model_instance_token']='0xother'
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_wrong_precision_state_rejected(self):
        r=forward_fixture();r['model_state_sha256']='c'*64
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_nonfinite_latency_rejected(self):
        r=forward_fixture();r['elapsed_seconds']=float('nan')
        with self.assertRaises(M.InvalidReceipt):self.check(r)


class NativeFaultTests(unittest.TestCase):
    def test_synthetic_native_receipt_structure(self):
        t,v,q=trace_fixture();self.assertEqual(R.native_replay(t,v,q)['native_order_matches_saved_vector_reference'],[True]*3)

    def test_reference_not_substituted_for_observed_ANN(self):
        t,v,q=trace_fixture();t['raw_native_output']['queries'][0]['ids']=[1,0,2]
        r=R.native_replay(t,v,q);self.assertEqual(r['native_order_matches_saved_vector_reference'],[False,True,True])

    def test_wrong_native_binary_rejected(self):
        t,v,q=trace_fixture();t['raw_native_output']['native_binary_sha256']='c'*64
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_reference_only_faked_native_flag_rejected(self):
        t,v,q=trace_fixture();t['raw_native_output']['native']=False
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_duplicate_hit_rejected(self):
        t,v,q=trace_fixture();t['raw_native_output']['queries'][0]['ids']=[0,0,2]
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_boolean_hit_rejected(self):
        t,v,q=trace_fixture();t['raw_native_output']['queries'][0]['ids']=[0,True,2]
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_changed_bundle_rejected(self):
        t,v,q=trace_fixture();t['bundle']['vectors'][0][0]=2
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_fabricated_reference_rejected(self):
        t,v,q=trace_fixture();t['reference'][0]['cosine_similarities'][0]=.01
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_negative_latency_rejected(self):
        t,v,q=trace_fixture();t['raw_native_output']['queries'][0]['latency_ms']=-1
        with self.assertRaises(M.InvalidReceipt):R.native_replay(t,v,q)

    def test_zero_cosine_vector_rejected(self):
        with self.assertRaises(M.InvalidReceipt):R.reference([[0]*384],[[1]+[0]*383]*3)


class GoldAndResourceGuardTests(unittest.TestCase):
    def test_unapproved_gold_never_opens_source(self):
        with patch.object(R,'identity',side_effect=AssertionError('must not even inspect raw before root authorization')):
            with self.assertRaises(M.InvalidReceipt):G.guard_completed(Path('plan'),Path('raw'),Path('execution'),'a'*64,False)

    def test_partial_predictions_never_open_gold(self):
        raw={'phase':'dev','epoch':21,'status':'FAILED_OR_INCOMPLETE_PRESERVED_EVIDENCE','plan_sha256':'a'*64,'errors':[]}
        with patch.object(R,'identity',return_value={'sha256':'a'*64}),patch.object(R,'plan_replay',return_value=({},{})),patch.object(R,'read',side_effect=[raw,{}]):
            with self.assertRaises(M.InvalidReceipt):G.guard_completed(Path('plan'),Path('raw'),Path('execution'),'a'*64,True)

    def test_negative_duration_rejected(self):
        with self.assertRaises(M.InvalidReceipt):R.duration(-1)

    def test_boolean_counter_rejected(self):
        with self.assertRaises(M.InvalidReceipt):R.integer(True)

    def test_unsafe_source_path_rejected(self):
        for p in ['../source','/source','a/./b','a\\b','a//b']:
            with self.subTest(path=p):
                with self.assertRaises(M.InvalidReceipt):R.member(p)


class CounterAndTokenProofFaultTests(unittest.TestCase):
    def test_exact_synthetic_counters_complete(self):R.counters_replay(counters_fixture(True),True)
    def test_exact_synthetic_counters_engineering(self):R.counters_replay(counters_fixture(False),False)

    def test_unplanned_ORT_sessions_rejected(self):
        r=counters_fixture(True);r['counters']['ORT_sessions_attempted']=r['counters']['ORT_sessions_completed']=99
        with self.assertRaises(M.InvalidReceipt):R.counters_replay(r,True)

    def test_ORT_sessions_before_engineering_pass_rejected(self):
        r=counters_fixture(False);r['counters']['ORT_sessions_attempted']=r['counters']['ORT_sessions_completed']=1
        with self.assertRaises(M.InvalidReceipt):R.counters_replay(r,False)

    def test_bool_completed_BGE_counter_rejected(self):
        for field in ('BGE_forwards','BGE_texts'):
            r=counters_fixture(True);r['counters'][field+'_attempted']=1;r['counters'][field+'_completed']=True
            with self.subTest(field=field):
                with self.assertRaises(M.InvalidReceipt):R.counters_replay(r,True)

    def test_hidden_extra_embedding_calls_rejected(self):
        r=counters_fixture(True);r['counters']['BGE_forwards_attempted']=r['counters']['BGE_forwards_completed']=17
        with self.assertRaises(M.InvalidReceipt):R.counters_replay(r,True)

    def check_proof(self,raw,proof):
        execution=R.ROOT/'execution.json'
        def fake_identity(path,relative=None):
            return {'path':'execution.json','bytes':100,'sha256':'e'*64}if Path(path)==execution else {'sha256':'a'*64}
        original_read=T.read
        def fake_read(path):return original_read(path)if Path(path)==R.PROTOCOL else proof
        with patch.object(T,'member',return_value=R.ROOT/'token-proof.json'),patch.object(T,'identity',side_effect=fake_identity),patch.object(T,'read',side_effect=fake_read):
            return R.tokenizer_report_replay(raw,R.ROOT/'raw.json','c'*64,execution)

    def test_exact_synthetic_tokenizer_proof(self):
        r,p=token_proof_fixture();self.check_proof(r,p)

    def test_placeholder_tokenizer_proof_rows_rejected(self):
        r,p=token_proof_fixture();p['feeds']=[{}]*75
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)

    def test_stale_tokenizer_execution_receipt_rejected(self):
        r,p=token_proof_fixture();p['execution_receipt']['sha256']='f'*64
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)

    def test_wrong_tokenizer_proof_feed_rejected(self):
        r,p=token_proof_fixture();p['feeds'][5]['feed_sha256']='f'*64
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)

    def test_bool_tokenizer_proof_index_rejected(self):
        r,p=token_proof_fixture();p['feeds'][0]['forward_index']=False
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)

    def test_wrong_tokenizer_proof_text_rejected(self):
        r,p=token_proof_fixture();p['feeds'][5]['input_text_sha256']='f'*64
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)

    def test_wrong_tokenizer_proof_source_assets_rejected(self):
        r,p=token_proof_fixture();p['assets'][0]['sha256']='f'*64
        with self.assertRaises(M.InvalidReceipt):self.check_proof(r,p)


if __name__=="__main__":unittest.main()
