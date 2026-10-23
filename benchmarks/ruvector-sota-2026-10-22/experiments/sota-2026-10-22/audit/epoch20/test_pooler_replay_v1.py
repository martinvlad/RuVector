"""Exact unused-pooler compatibility corruption tests; no model imports/runs."""
import copy
import unittest
import metrics as M
import replay_pooler_v1 as P
from test_replay import model_fixture


def fixture():
    raw,_=model_fixture();protocol=P.read(P.PROTOCOL);p=raw['model_provenance']
    p['loading_info']['unexpected_keys']=['roberta.pooler.dense.bias','roberta.pooler.dense.weight']
    p['source_checkpoint_tensors']=395;p['source_checkpoint_elements']=356412419
    p['source_checkpoint_dtype_elements']={'torch.float32':356412419}
    raw['fp32_state']['parameter_tensor_count']=393
    p['unused_pooler_compatibility']={
        'policy':'EXACT_TWO_UNUSED_PRETRAINING_POOLER_KEYS_ONLY','head_reinitialization_allowed':False,
        'checkpoint_bytes_modified':False,'stock_classification_forward_uses_pooler':False,
        'allowed_unexpected_keys':['roberta.pooler.dense.bias','roberta.pooler.dense.weight'],
        'source_shapes':{'roberta.pooler.dense.weight':[1024,1024],'roberta.pooler.dense.bias':[1024]},
        'source_dtypes':{'roberta.pooler.dense.weight':'torch.float32','roberta.pooler.dense.bias':'torch.float32'},
        'source_tensors':{'roberta.pooler.dense.weight':{'shape':[1024,1024],'dtype':'torch.float32','elements':1048576},
                          'roberta.pooler.dense.bias':{'shape':[1024],'dtype':'torch.float32','elements':1024}},
        'source_tensor_count':395,'source_elements':356412419,'active_parameter_tensor_count':393,
        'active_parameter_elements':355362819,'unused_elements':1049600,
        'actual_model_pooler_is_none':True,'all_classification_forward_parameters_loaded':True}
    return raw,protocol


class ExactUnusedPoolerTests(unittest.TestCase):
    def test_exact_two_unused_source_tensors_pass(self):
        raw,protocol=fixture();self.assertEqual(P.model_replay(raw,protocol),('a'*64,'0xunit-test-only'))

    def test_unexpected_key_order_irrelevant(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['unexpected_keys'].reverse()
        self.assertEqual(P.model_replay(raw,protocol),('a'*64,'0xunit-test-only'))

    def test_extra_unused_key_not_allowed(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['unexpected_keys'].append('roberta.encoder.layer.0.attention.self.query.weight')
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_missing_original_pooler_key_report_rejected(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['unexpected_keys']=[]
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_duplicate_unexpected_key_rejected(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['unexpected_keys']=['roberta.pooler.dense.weight']*2
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_missing_classifier_weight_still_rejected(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['missing_keys']=['classifier.out_proj.weight']
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_mismatched_backbone_weight_still_rejected(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['mismatched_keys']=['roberta.embeddings.word_embeddings.weight']
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_loader_errors_still_rejected(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['error_msgs']=['syntheticerror']
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_unexpected_classifier_key_not_pooler(self):
        raw,protocol=fixture();raw['model_provenance']['loading_info']['unexpected_keys']=['classifier.out_proj.weight','roberta.pooler.dense.bias']
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_source_tensor_count_must_be_actual395(self):
        raw,protocol=fixture();raw['model_provenance']['source_checkpoint_tensors']=393
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_source_element_count_must_include_unused_pooler(self):
        raw,protocol=fixture();raw['model_provenance']['source_checkpoint_elements']=355362819
        raw['model_provenance']['source_checkpoint_dtype_elements']={'torch.float32':355362819}
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_active_parameter_count_must_exclude_unused_pooler(self):
        raw,protocol=fixture();raw['fp32_state']['parameter_count']=356412419
        raw['fp32_state']['parameter_dtype_element_counts']={'torch.float32':356412419}
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_unused_delta_must_be_exact1049600(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['unused_elements']=1024
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_actual_pooler_must_be_absent(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['actual_model_pooler_is_none']=False
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_all_classification_forward_parameters_must_load(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['all_classification_forward_parameters_loaded']=False
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_unused_pooler_shape_must_match_exact_original(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['source_shapes']['roberta.pooler.dense.weight']=[3,1024]
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_unused_pooler_dtype_must_be_original_float32(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['source_dtypes']['roberta.pooler.dense.weight']='torch.float16'
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_active_parameter_tensor_count_tied_to_actual_state(self):
        raw,protocol=fixture();raw['fp32_state']['parameter_tensor_count']=395
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_reinitialized_head_forbidden(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['head_reinitialization_allowed']=True
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_modified_checkpoint_forbidden(self):
        raw,protocol=fixture();raw['model_provenance']['unused_pooler_compatibility']['checkpoint_bytes_modified']=True
        with self.assertRaises(M.InvalidReceipt):P.model_replay(raw,protocol)

    def test_new_gold_and_token_helpers_import_new_replay(self):
        import project_gold_pooler_v1 as G
        import tokenizer_replay_pooler_v1 as T
        self.assertIs(G.R,P);self.assertIs(T.R,P)

    def test_new_runtime_versions_still_match_immutable_wheels(self):
        protocol=P.read(P.PROTOCOL);ref=protocol['model']['runtime_versions_source'];path=P.member(ref['path'])
        self.assertEqual(P.identity(path,ref['path']),ref)
        versions={r['filename'].split('-',2)[0]:r['filename'].split('-',2)[1]for r in P.read(path)['wheels']}
        self.assertEqual(protocol['model']['versions'],{k:versions[k]for k in protocol['model']['versions']})


if __name__=='__main__':unittest.main()
