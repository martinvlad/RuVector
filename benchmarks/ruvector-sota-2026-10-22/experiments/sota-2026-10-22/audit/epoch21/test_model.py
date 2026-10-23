"""Synthetic metadata faults only: no tensor/model/parser/native/corpus execution."""
import copy
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch
import metrics as M
import model_checks as B
import replay as R
from test_replay import forward_fixture


def fixture():
    protocol = R.read(R.PROTOCOL); frozen = protocol['model']['source_header']
    header = R.read(R.member(frozen['path']))
    source = {name: {'dtype': row['dtype'], 'shape': row['shape'], 'elements': __import__('math').prod(row['shape'])}
              for name, row in header['tensor_metadata'].items()}
    floats = {name: row for name, row in source.items() if row['dtype'] == 'F16'}
    rows = [{'name': name, 'source_dtype': 'F16', 'source_shape': row['shape'],
             'elements': row['elements'], 'loaded_dtype': 'torch.float32', 'loaded_device': 'cpu',
             'equal_after_FP32_conversion': True} for name, row in sorted(floats.items())]
    token = {'backend_sha256': protocol['tokenizer']['operational_backend_sha256'],
             'type': 'DebertaV2TokenizerFast', 'backend_model': 'Unigram',
             'pair_format': '[CLS]P[SEP]H[SEP]', 'cls_id': 1, 'sep_id': 2, 'pad_id': 0,
             'padding': False, 'truncation': False, 'token_type_ids_fed': True,
             'type_vocab_size': 0, 'learned_segment_embeddings': False,
             'original_asset_bytes_unchanged': True, 'original_declared_padding': None,
             'original_declared_truncation': {'direction':'Right','max_length':512,'strategy':'LongestFirst','stride':0},
             'original_tokenizer_json_sha256': protocol['tokenizer']['original_tokenizer_json_sha256'],
             'actual_backend_json_path': R.PREFIX + 'epoch21/runs/dev/tokenizer-backend.json',
             'actual_backend_json_bytes': protocol['tokenizer']['operational_backend_bytes'],
             'actual_backend_json_sha256': protocol['tokenizer']['operational_backend_sha256']}
    state = {'parameter_count': B.FLOAT_ELEMENTS, 'parameter_tensor_count': 394,
             'parameter_dtype_element_counts': {'torch.float32': B.FLOAT_ELEMENTS},
             'buffer_dtype_element_counts': {'torch.int64':512}, 'devices':['cpu'],
             'all_floating_parameters_buffers_FP32':True, 'eval':True, 'deterministic_algorithms':True,
             'state_sha256':'a'*64, 'model_instance_token':'0xunit-test-only', 'quantized_modules':0,
             'threads':2, 'interop_threads':1, 'pooler_dense_weight_shape':[1024,1024],
             'pooler_dense_bias_shape':[1024], 'classifier_weight_shape':[3,1024], 'classifier_bias_shape':[3]}
    p = {'repo':R.MODEL, 'revision':R.REVISION,
         'raw_id2label':{'0':'Entailment','1':'NotMentioned','2':'Contradiction'},
         'canonical_order':list(M.ORDER), 'canonical_permutation':[0,2,1],
         'load_flags':{'local_files_only':True,'trust_remote_code':False,'weights_only':True,
                       'use_safetensors':True,'torch_dtype':'torch.float32',
                       'output_loading_info':True,'attn_implementation':'eager'},
         'loading_info':{k:[]for k in('missing_keys','unexpected_keys','mismatched_keys','error_msgs')},
         'actual_attention_implementation':'eager',
         'precision':'ORIGINAL_FP16_STORAGE_EXPLICIT_FP32_CPU_INFERENCE_NO_QUANTIZATION',
         'initialization_model_forwards':0,'quantization_initializations':0,
         'versions':copy.deepcopy(protocol['model']['versions']), 'pair_token_cap':512,'batch_size':1,'temperature':1,
         'source_checkpoint_raw_header_sha256':B.HEADER_SHA,
         'source_checkpoint_header_path':frozen['path'],'source_checkpoint_header_sha256':frozen['sha256'],
         'source_checkpoint_dtype_elements':{'torch.float16':B.FLOAT_ELEMENTS,'torch.int64':512},
         'source_checkpoint_tensors':395,'source_checkpoint_elements':B.FLOAT_ELEMENTS+512,
         'parameter_loading_verification':{'source_float_key_set_equals_all_named_parameters':True,
             'all_source_to_FP32_values_equal':True, 'compared_tensor_count':394,
             'compared_elements':B.FLOAT_ELEMENTS,'per_parameter':rows},
         'position_buffer':{'name':B.POSITION_NAME,'source_dtype':'I64','source_shape':[1,512],
             'values_equal_arange512':True,'equals_actual_buffer':True,'actual_persistent':False,
             'source_bytes_sha256':'5738153ec97595b1c1e4dc027f7b7fb4534f19ed2ce9f9ee712e6d34a384cde7'},
         'state_sha256':'a'*64,'architecture':copy.deepcopy(protocol['model']['architecture']),
         'source_config_architecture':copy.deepcopy(protocol['model']['source_config_architecture']),
         'actual_model_config_declared_dtype':'torch.float16','tokenizer':token}
    raw = {'kind':'SYNTHETIC_UNIT_TEST_NOT_MODEL_EXECUTION','phase':'dev','model_provenance':p,
           'fp32_state':state,'tokenizer':token,
           'asset_identities':[{k:row[k]for k in('path','bytes','sha256')}for row in protocol['model']['assets']]}
    return raw, protocol, source, floats


def check(raw, protocol, source, floats):
    frozen = protocol['model']['source_header']
    def identity(path, relative=None):
        if str(path).endswith('source-safetensors-header.json'): return frozen
        token=raw['tokenizer']
        return {'path':token['actual_backend_json_path'],'bytes':token['actual_backend_json_bytes'],
                'sha256':token['backend_sha256']}
    with ExitStack() as stack:
        stack.enter_context(patch.object(B,'source_header',return_value=(source,floats,B.HEADER_SHA)))
        stack.enter_context(patch.object(B,'member',side_effect=lambda x:R.ROOT/x))
        stack.enter_context(patch.object(B,'identity',side_effect=identity))
        stack.enter_context(patch.object(B,'read',return_value={'model':{'type':'Unigram'},'padding':None,'truncation':None}))
        return B.model_replay(raw,protocol)


class ModelMetadataFaultTests(unittest.TestCase):
    def test_valid_complete_synthetic_metadata(self):
        self.assertEqual(check(*fixture()),('a'*64,'0xunit-test-only'))

    def test_source_storage_config_is_distinct_from_loaded_architecture(self):
        r,p,s,f=fixture()
        self.assertEqual(r['model_provenance']['source_config_architecture']['torch_dtype'],'float16')
        self.assertNotIn('torch_dtype',r['model_provenance']['architecture'])
        self.assertEqual(check(r,p,s,f),('a'*64,'0xunit-test-only'))

    def test_actual_config_dtype_is_not_used_as_tensor_precision_proof(self):
        for value in ('torch.float16','torch.float32'):
            r,p,s,f=fixture();r['model_provenance']['actual_model_config_declared_dtype']=value
            self.assertEqual(check(r,p,s,f),('a'*64,'0xunit-test-only'))

    def test_actual_structural_config_or_source_config_cannot_change(self):
        for field in ('architecture','source_config_architecture'):
            r,p,s,f=fixture();r['model_provenance'][field]['hidden_size']=768
            with self.subTest(field=field),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_actual_num_labels_cannot_change_or_be_boolean(self):
        for value in (2,True):
            r,p,s,f=fixture();r['model_provenance']['architecture']['num_labels']=value
            with self.subTest(value=value),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_actual_declared_versions_match_immutable_wheel_metadata(self):
        p=R.read(R.PROTOCOL);row=p['model']['runtime_versions_source'];path=R.member(row['path'])
        self.assertEqual(R.identity(path,row['path']),row)
        versions={x['filename'].split('-',2)[0]:x['filename'].split('-',2)[1]for x in R.read(path)['wheels']}
        self.assertEqual(p['model']['versions'],{k:versions[k]for k in p['model']['versions']})

    def test_all_four_loading_error_lists_mandatory_empty(self):
        for key in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs'):
            r,p,s,f=fixture();r['model_provenance']['loading_info'][key]=['trained.classifier']
            with self.subTest(key=key),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_old_unused_pooler_exception_cannot_pass(self):
        r,p,s,f=fixture();r['model_provenance']['loading_info']['unexpected_keys']=['roberta.pooler.dense.weight']
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_wrong_model_revision_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['revision']='f'*40
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_raw_C_and_E_permutation_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['raw_id2label']['0']='Contradiction'
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_source_FP16_cannot_be_reported_as_FP32(self):
        r,p,s,f=fixture();r['model_provenance']['source_checkpoint_dtype_elements']={'torch.float32':B.FLOAT_ELEMENTS,'torch.int64':512}
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_inference_downcast_rejected(self):
        r,p,s,f=fixture();r['fp32_state']['parameter_dtype_element_counts']={'torch.float16':B.FLOAT_ELEMENTS}
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_half_buffer_rejected(self):
        r,p,s,f=fixture();r['fp32_state']['buffer_dtype_element_counts']['torch.float16']=1
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_wrong_classifier_or_pooler_shape_rejected(self):
        for key in ('pooler_dense_weight_shape','classifier_weight_shape'):
            r,p,s,f=fixture();r['fp32_state'][key]=[2,1024]
            with self.subTest(key=key),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_nonpersistent_position_is_not_optional(self):
        for key,value in [('actual_persistent',True),('values_equal_arange512',False),('equals_actual_buffer',False)]:
            r,p,s,f=fixture();r['model_provenance']['position_buffer'][key]=value
            with self.subTest(key=key),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_bool_position_shape_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['position_buffer']['source_shape']=[True,512]
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_any_unverified_source_parameter_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['parameter_loading_verification']['per_parameter'][3]['equal_after_FP32_conversion']=False
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_missing_parameter_comparison_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['parameter_loading_verification']['per_parameter'].pop()
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_duplicate_parameter_comparison_rejected(self):
        r,p,s,f=fixture();v=r['model_provenance']['parameter_loading_verification']['per_parameter'];v[2]=copy.deepcopy(v[1])
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_parameter_order_not_ambiguous(self):
        r,p,s,f=fixture();r['model_provenance']['parameter_loading_verification']['per_parameter'].reverse()
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_parameter_source_dtype_and_dimension_rejected(self):
        for key,value in [('source_dtype','F32'),('source_shape',[1,1]),('loaded_device','cuda'),('loaded_dtype','torch.float16')]:
            r,p,s,f=fixture();r['model_provenance']['parameter_loading_verification']['per_parameter'][0][key]=value
            with self.subTest(key=key),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_compared_boolean_tensor_count_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['parameter_loading_verification']['compared_tensor_count']=True
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_prequalified_tokenizer_backend_cannot_change(self):
        r,p,s,f=fixture();r['tokenizer']['backend_sha256']='b'*64
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_source_tokenizer_identity_cannot_change(self):
        r,p,s,f=fixture();r['tokenizer']['original_tokenizer_json_sha256']='b'*64
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_tokenizer_extra_learned_segments_rejected(self):
        r,p,s,f=fixture();r['tokenizer']['learned_segment_embeddings']=True
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_tokenizer_cannot_hide_type_ids(self):
        r,p,s,f=fixture();r['tokenizer']['token_type_ids_fed']=False
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_runtime_version_drift_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['versions']['numpy']='2.3.5'
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_saved_state_hash_must_match(self):
        r,p,s,f=fixture();r['fp32_state']['state_sha256']='c'*64
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_remote_code_or_non_safetensors_rejected(self):
        for key,value in [('trust_remote_code',True),('use_safetensors',False),('torch_dtype','torch.float16')]:
            r,p,s,f=fixture();r['model_provenance']['load_flags'][key]=value
            with self.subTest(key=key),self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_bool_source_counter_rejected(self):
        r,p,s,f=fixture();r['model_provenance']['quantization_initializations']=False
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)

    def test_asset_byte_hash_tampering_rejected(self):
        r,p,s,f=fixture();r['asset_identities'][0]['sha256']='b'*64
        with self.assertRaises(M.InvalidReceipt):check(r,p,s,f)


class AdditionalFeedFaultTests(unittest.TestCase):
    def check(self,row):return B.forward_replay(row,'The lamp is on.','The lamp is on.','a'*64,'0xunit-test-only')

    def test_nonmonotonic_segments_rejected(self):
        r=forward_fixture();r['feed']['token_type_ids'][0][3]=1;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_bool_segment_rejected(self):
        r=forward_fixture();r['feed']['token_type_ids'][0][3]=False;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_model_reserved_vocab_boundary_rejected(self):
        r=forward_fixture();r['feed']['input_ids'][0][3]=128100;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_source_special_ids_rejected(self):
        r=forward_fixture();r['feed']['input_ids'][0][0]=0;r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_extra_feed_key_rejected(self):
        r=forward_fixture();r['feed']['position_ids']=[[1]*r['actual_tokens']];r['feed_sha256']=R.digest(R.canonical(r['feed']))
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_wrong_observed_feed_dtype_rejected(self):
        r=forward_fixture();r['feed_dtype']='torch.float32'
        with self.assertRaises(M.InvalidReceipt):self.check(r)

    def test_original_high_level_comparison_is_required(self):
        r=forward_fixture();r['original_high_level_feed_equal']=False
        with self.assertRaises(M.InvalidReceipt):self.check(r)


if __name__ == '__main__': unittest.main()

