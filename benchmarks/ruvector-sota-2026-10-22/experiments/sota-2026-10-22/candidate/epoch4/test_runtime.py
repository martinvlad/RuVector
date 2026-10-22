"""Generated source-only checks; no ONNX or native execution."""
import copy
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
import numpy as np

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('epoch4_test_runtime',HERE/'runtime.py');runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)


class Words:
    def encode(self,text,pair=None,add_special_tokens=True):
        offsets=[(m.start(),m.end()) for m in re.finditer(r'\S+',text)]
        n=len(offsets)+(len(pair.split()) if pair is not None else 0)+(3 if add_special_tokens else 0)
        return SimpleNamespace(ids=list(range(n)),attention_mask=[1]*n,type_ids=[0]*n,offsets=offsets)


def counters():
    return {key:0 for key in ['requests_attempted','requests_completed','native104_requests_attempted','native104_requests_completed','native_core_searches_attempted','native_core_searches_completed','bge_forward_batches_attempted','bge_forward_batches_completed','bge_texts_attempted','bge_texts_completed','nli_forward_pairs_attempted','nli_forward_pairs_completed','nli_input_tokens_attempted','nli_input_tokens_completed','bge_forward_wall_seconds','nli_forward_wall_seconds']}


class Tests(unittest.TestCase):
    def test_joint_source_order_merge_and_complete_text(self):
        state='AAA 12 BBB 34 CCC 56 DDD 78'
        spans=[(0,10),(8,20),(20,len(state))]
        premise,audit=runtime.CONTEXT.joint_context(state,spans,[2,0],'A predicate.',Words())
        self.assertEqual(premise,state[:10]+'\n\n'+state[20:])
        self.assertEqual(audit['selected_chunk_ids_source_order'],[0,2])
        self.assertFalse(audit['selected_evidence_truncated'])
        self.assertFalse(audit['claim_truncated'])
        merged,_=runtime.CONTEXT.joint_context(state,spans,[1,0],'A predicate.',Words())
        self.assertEqual(merged,state[:20])

    def test_numeric_coverage_is_mechanical_and_position_specific(self):
        state='Keep 30 days. Omit 60 days. Keep 30 months.'
        spans=[(0,13),(14,27),(28,len(state))]
        _,audit=runtime.CONTEXT.joint_context(state,spans,[2,0],'A predicate.',Words())
        self.assertEqual(audit['numeric_mentions_retained'],2)
        self.assertEqual(audit['numeric_mentions_omitted'],1)
        self.assertEqual([n['text'] for n in audit['numeric_mentions'] if not n['retained']],['60'])
        self.assertIn('do not establish insufficient evidence',audit['scope'])

    def test_pair_over_limit_rejects_without_truncating_claim(self):
        state='word '*510
        with self.assertRaisesRegex(ValueError,'no clipping'):
            runtime.CONTEXT.joint_context(state,[(0,len(state))],[0],'Entire mandatory claim remains present.',Words())

    def test_invalid_selection_ids_rejected(self):
        for ids in [[],[0,0],[3],[-1],[True]]:
            with self.assertRaises(ValueError):runtime.CONTEXT.merge_spans([(0,3),(2,5)],ids)

    def test_source_windows_cover_document_without_hidden_drop(self):
        offsets=[(i,i+1) for i in range(1000)]
        spans=runtime.CONTEXT.spans_from_offsets(offsets,1000)
        self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],1000)
        self.assertTrue(all(b-a<=192 for a,b in spans))
        with self.assertRaisesRegex(ValueError,'no hidden clipping'):
            runtime.CONTEXT.spans_from_offsets(offsets,1000,10,2,2)

    def fake_nli(self,logits):
        nli=runtime.MODELS.SingletonNli.__new__(runtime.MODELS.SingletonNli)
        nli.tokenizer=Words();nli.counters=counters();nli.label_indices={'entailment':2,'contradiction':0,'neutral':1};nli.inputs={'input_ids','attention_mask'}
        calls=[]
        def run(outputs,feed):calls.append(copy.deepcopy(feed));return [np.asarray([logits])]
        nli.session=SimpleNamespace(run=run)
        return nli,calls

    def test_singleton_shape_no_padding_and_joint_decoder_mapping(self):
        nli,calls=self.fake_nli([0.,7.,0.])
        p,trace=nli.decode('Complete evidence paragraph one. Complete paragraph two.','The contract permits copying.')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['input_ids'].shape[0],1)
        self.assertTrue(np.all(calls[0]['attention_mask']==1))
        self.assertGreater(p['No'],.99)
        self.assertEqual(trace['batch_size'],1);self.assertEqual(trace['padding_tokens'],0);self.assertFalse(trace['truncated'])
        self.assertIn('no per-chunk maximum',trace['pool'])
        self.assertEqual(nli.counters['nli_forward_pairs_attempted'],1);self.assertEqual(nli.counters['nli_forward_pairs_completed'],1)

    def test_no_companion_example_can_influence_same_pair_readout(self):
        nli,calls=self.fake_nli([0.,1.,2.])
        a,t=nli.decode('Same premise.','Same claim.')
        nli.decode('A much longer unrelated companion premise. '*10,'Another claim.')
        b,u=nli.decode('Same premise.','Same claim.')
        self.assertEqual(a,b);self.assertEqual(t['input_ids'],u['input_ids'])
        self.assertTrue(all(feed['input_ids'].shape[0]==1 for feed in calls))

    def test_nli_over_limit_has_zero_forward_attempts(self):
        nli,calls=self.fake_nli([0.,1.,2.])
        with self.assertRaisesRegex(ValueError,'no clipping'):nli.decode('word '*512,'Claim remains.')
        self.assertEqual(calls,[]);self.assertEqual(nli.counters['nli_forward_pairs_attempted'],0)

    def test_counted_bge_failure_retains_exact_attempts(self):
        counts=counters()
        def fail(*args):raise RuntimeError('deliberate fixture failure')
        session=runtime.MODELS.CountedSession(SimpleNamespace(run=fail),counts)
        with self.assertRaisesRegex(RuntimeError,'fixture'):session.run(None,{'input_ids':np.zeros((3,10),dtype=np.int64)})
        self.assertEqual(counts['bge_forward_batches_attempted'],1);self.assertEqual(counts['bge_texts_attempted'],3)
        self.assertEqual(counts['bge_forward_batches_completed'],0);self.assertEqual(counts['bge_texts_completed'],0)

    def test_matched_arm_pipeline_and_evidence_native_reference(self):
        engine=runtime.CandidateEngine.__new__(runtime.CandidateEngine);engine.counters=counters();engine.native_pid=None
        calls=[]
        class Nli:
            tokenizer=Words()
            def decode(self,premise,claim):calls.append((premise,claim));return {'Yes':.6,'No':.4},{'input_tokens':len(premise.split())+len(claim.split())+3,'batch_size':1,'truncated':False}
        native=[]
        class Base:
            def predict(self,state,questions):
                native.append({'state':state,'questions':copy.deepcopy(questions)})
                return {'answers':{k:{'type':'choice','choice':'No','probabilities':{'Yes':.2,'No':.8}} for k in questions},'usage':{'native_requests':1}}
        engine.nli=Nli();engine.base=Base()
        engine.retrieve=lambda chunks,hyp:([len(chunks)-1,0],{'native':{'native':True},'bundle_evidence':{'sha256':'fixture'}})
        state='term '*400
        question={'decision':{'type':'choice','instructions':'Decide whether entailed.','criteria':{'Yes':'Copying is allowed.','No':'Not established.'}}}
        result=engine.predict(state,question)
        self.assertEqual(len(calls),3);self.assertEqual({h for _,h in calls},{'Copying is allowed.'})
        self.assertEqual(native[0]['state'],calls[0][0]);self.assertEqual(native[0]['questions'],question)
        self.assertNotEqual(native[0]['state'],state)
        self.assertEqual(result['baseline104_response']['model'],'native104_on_ruvector_evidence')
        self.assertEqual(set(result['ablation_responses']),{'same_nli_lexical_top2','same_nli_positional_first2'})
        self.assertEqual(engine.counters['native104_requests_attempted'],1);self.assertEqual(engine.counters['native104_requests_completed'],1)
        self.assertEqual(engine.counters['requests_attempted'],1);self.assertEqual(engine.counters['requests_completed'],1)
        self.assertIn('self_peak_rss_KiB',engine.last_usage['execution_terminal']['resources'])


if __name__=='__main__':unittest.main()
