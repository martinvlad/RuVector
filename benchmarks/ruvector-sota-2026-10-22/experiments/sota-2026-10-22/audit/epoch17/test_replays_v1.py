"""Generic transport/context fault injection only; no benchmark inputs or gold."""
from pathlib import Path
import copy
import hashlib
import json
import unittest
from tokenizers import Tokenizer, models, pre_tokenizers, processors
import replay_context_v1 as C
import replay_scores_v1 as S
import math_v1 as M

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]


def tokenizer(split):
    vocabulary = {'[UNK]':0,'[CLS]':1,'[SEP]':2}
    for word in ('This Agreement between Vendor and Recipient defines Protected Material '
                 'means generic source one two three four five six seven eight nine '
                 '10 20 30 40 50 60 70 80 90 100 applies hypothesis retained source unit').split():
        if word not in vocabulary: vocabulary[word] = len(vocabulary)
    value = Tokenizer(models.WordLevel(vocabulary,unk_token='[UNK]'))
    value.pre_tokenizer = split
    value.post_processor = processors.TemplateProcessing(single='[CLS] $A [SEP]',
        pair='[CLS] $A [SEP] $B:1 [SEP]:1',special_tokens=[('[CLS]',1),('[SEP]',2)])
    return value


class ContextFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = C.module(SOURCE/'candidate/epoch17/context.py','generic17_candidate_context')
        cls.partition = C.module(SOURCE/'candidate/epoch6/context.py','generic17_partition').partition
        cls.new = tokenizer(pre_tokenizers.Whitespace())
        cls.old = tokenizer(pre_tokenizers.CharDelimiterSplit(' '))
        cls.joint = C.JointBudgetTokenizer(cls.new,cls.old)
        cls.state = ('This Agreement between Vendor and Recipient applies.\n\n'
                     '"Protected Material" means generic source unit 10.\n\n'+
                     '\n\n'.join('source unit '+str(i)+' '+('one two three four five six seven eight nine '*12)
                                  for i in range(20,31)))
        cls.h = 'generic hypothesis applies'
        cls.units = cls.partition(cls.state,cls.joint,cls.new,target=128,nli_cap=160,bge_cap=256,max_units=192)
        cls.priority = C.M.priority(cls.state,cls.units,cls.joint)
        cls.order = list(range(min(40,len(cls.units))))

    def fixture(self):
        p = self.candidate.select_prelude(self.state,self.units,self.new,self.old)
        text,cov = self.candidate.pack(self.state,self.units,self.order,self.h,self.new,self.old,prelude=p,
                                      rank_depth=min(40,len(self.units)))
        return {'premise':text,'hypothesis':self.h,'coverage':cov,'ranking_ids':self.order,
                'chunk_ids':cov['selected_chunk_ids_rank_order'],
                'chunk_spans':[[self.units[i]['start'],self.units[i]['end']] for i in cov['selected_chunk_ids_rank_order']]}

    def check(self,value):
        return C.verify_pack(value,self.state,self.units,self.order,self.h,self.new,self.old,self.priority)

    def test_whole_source_both_budgets_and_numeric_surface(self):
        result,new,old = self.check(self.fixture())
        self.assertGreater(len(result['numbers']),0)
        self.assertLessEqual(max(len(new.ids),len(old.ids)),512)
        self.assertEqual(''.join(self.state[u['start']:u['end']] for u in self.units),self.state)

    def test_joint_uses_longer_both_single_and_pair(self):
        for text,pair in [('generic-source',None),('generic-source',self.h)]:
            encoded = self.joint.encode(text,pair)
            self.assertEqual(len(encoded.ids),max(len(self.new.encode(text,pair).ids),len(self.old.encode(text,pair).ids)))

    def test_wrong_source_bytes_fail(self):
        value=self.fixture();value['premise']+=' invented';
        with self.assertRaises(AssertionError): self.check(value)

    def test_wrong_rank_or_span_fail(self):
        for key in ('ranking_ids','chunk_spans'):
            value=self.fixture();value[key]=[]
            with self.assertRaises(AssertionError): self.check(value)

    def test_wrong_numeric_receipt_fails(self):
        value=self.fixture();value['coverage']['numeric_mentions']=[]
        with self.assertRaises(AssertionError): self.check(value)

    def test_wrong_previous_token_count_fails(self):
        value=self.fixture();value['coverage']['previous_reader_joint_pair_tokens']+=1
        with self.assertRaises(AssertionError): self.check(value)

    def test_wrong_trace_dual_reader_count_fails(self):
        value=self.fixture();self.assertTrue(value['coverage']['packing_attempts'])
        value['coverage']['packing_attempts'][0]['candidate_new_reader_pair_tokens']+=1
        with self.assertRaises(AssertionError): self.check(value)

    def test_counterfactual_is_tokenization_only(self):
        value=self.fixture();value['coverage']['no_priority_counterfactual']['model_forwards']=1
        with self.assertRaises(AssertionError): self.check(value)


class LogitFixtures(unittest.TestCase):
    def fixture(self,new=True):
        text={'premise':'generic source','hypothesis':'generic hypothesis'}
        raw=json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()
        mapping=({'contradiction':0,'neutral':1,'entailment':2} if new else {'contradiction':0,'entailment':1,'neutral':2})
        logits=[1.,-1.,2.]
        dec={'raw_label_indices':mapping,'logits':logits,'raw_threeway_probabilities':M.softmax(logits,mapping),
             'model_revision':S.NEW_REV if new else S.MODEL_REV,
             'temperature':1.,'batch_size':1,'truncated':False,'padding_tokens':0,
             'input_tokens':5,'raw_tokens':5,'used_tokens':5,'actual_model_pair_tokens':5,
             'input_ids':[1,3,2,4,2],'attention_mask':[1]*5,'token_type_ids':[0,0,0,1,1],
             'input_text_sha256':hashlib.sha256(raw).hexdigest()}
        receipt={'new_reader':{'quantized_weight_state_sha256':'a'*64,
                              'tokenizer':{'converted_backend_sha256':'b'*64}}}
        if new:
            dec.update(model_repo='microsoft/deberta-v2-xlarge-mnli',original_checkpoint_sha256=S.NEW_SHA,
                tokenizer_sha256=S.NEW_SPM,config_sha256=S.NEW_CONFIG,
                precision='TORCH_DYNAMIC_QINT8_LINEAR_FP32_REMAINDER_FBGEMM',raw_logit_dtype='float32',
                actual_model_inputs=['input_ids','attention_mask','token_type_ids'],typed_order=list(M.LABELS),
                canonical_logits_E_C_N=[2.,1.,-1.],quantized_weight_state_sha256='a'*64,
                converted_tokenizer_backend_sha256='b'*64)
        else: dec.update(onnx_sha256=S.MODEL_SHA,actual_graph_inputs=['attention_mask','input_ids'])
        return dec,receipt

    def check(self,dec,receipt,new=True):
        return S.raw_distribution(dec,'generic source','generic hypothesis',new,receipt)

    def test_exact_different_label_maps(self):
        a,ra=self.fixture();b,rb=self.fixture(False)
        self.assertEqual(M.prediction(self.check(a,ra)),'Entailment')
        self.assertEqual(M.prediction(self.check(b,rb,False)),'NotMentioned')

    def test_label_permutation_not_silently_accepted(self):
        value,receipt=self.fixture();value['raw_label_indices']={'contradiction':0,'entailment':1,'neutral':2}
        with self.assertRaises(AssertionError): self.check(value,receipt)

    def test_wrong_quantized_state_or_input_identity_fail(self):
        for key in ('quantized_weight_state_sha256','input_text_sha256','converted_tokenizer_backend_sha256'):
            value,receipt=self.fixture();value[key]='f'*64
            with self.assertRaises(AssertionError): self.check(value,receipt)

    def test_clipping_or_padding_or_bad_feed_fails(self):
        for key,change in [('truncated',True),('padding_tokens',1),('input_tokens',513),('attention_mask',[1,1,1,1,0])]:
            value,receipt=self.fixture();value[key]=change
            with self.assertRaises(AssertionError): self.check(value,receipt)


if __name__ == '__main__': unittest.main()
