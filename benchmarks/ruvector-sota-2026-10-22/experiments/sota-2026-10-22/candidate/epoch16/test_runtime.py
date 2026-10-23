"""Injected six-pass/native wiring checks; no actual session, ANN or native104."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from tokenizers import Tokenizer

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('test_e16_runtime',HERE/'runtime.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)


class InjectedReader:
    def __init__(self,t):self.tokenizer=t;self.calls=[]
    def decode(self,premise,hypothesis):
        self.calls.append((premise,hypothesis))
        positive=not hypothesis.startswith(R.PAIRING.PREFIX)
        typed=({'Entailment':.6,'Contradiction':.1,'NotMentioned':.3} if positive else
               {'Entailment':.2,'Contradiction':.5,'NotMentioned':.3})
        enc=self.tokenizer.encode(premise,hypothesis)
        trace={'injected_engineering_only':True,'raw_threeway_probabilities':typed,
               'input_ids':enc.ids,'attention_mask':enc.attention_mask,'token_type_ids':enc.type_ids,
               'actual_model_pair_tokens':len(enc.ids),'logits':[0.,0.,0.],
               'input_text_sha256':hashlib.sha256(json.dumps({'premise':premise,'hypothesis':hypothesis},
                    ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
        return R.PAIRING.binary(typed),trace


class InjectedNative104:
    def __init__(self):self.calls=[]
    def predict(self,state,questions):
        self.calls.append((state,copy.deepcopy(questions)))
        return {'answers':{k:R.HELPERS.answer_for({'Yes':.6,'No':.4}) for k in questions},
                'usage':{'injected_engineering_only':True}}


class RuntimeTests(unittest.TestCase):
    def engine(self):
        t=Tokenizer.from_file(str(HERE.parent/'epoch15/assets/official-deberta-v3-large/tokenizer.json'))
        t.no_padding();t.no_truncation()
        e=R.CandidateEngine.__new__(R.CandidateEngine)
        e.config={'source_partition':{'target':32,'nli_cap':64,'bge_cap':256,'max_units':192},
                  'ranking_depth':40,'joint_pair_token_cap':512,
                  'query_prefix':'Represent this sentence for searching relevant passages: ',
                  'legacy_arm_names':'Injected engineering aliases only'}
        e.counters=dict.fromkeys(('requests_attempted','requests_completed',
            'context_partitions_attempted','context_partitions_completed',
            'context_packs_attempted','context_packs_completed',
            'native104_requests_attempted','native104_requests_completed',
            'nli_positive_pairs_attempted','nli_positive_pairs_completed',
            'nli_counterclaim_pairs_attempted','nli_counterclaim_pairs_completed'),0)
        e.nli=InjectedReader(t);e.bge=SimpleNamespace(raw_tokenizer=t)
        e.base=InjectedNative104();e.last_usage=None;e.retrieval_calls=[]
        e.execution_snapshot=lambda:{'counters':copy.deepcopy(e.counters),'injected_engineering_only':True}
        def retrieve(chunks,h):
            e.retrieval_calls.append((chunks,h))
            return list(reversed(range(min(40,len(chunks))))),{'injected_engineering_only':True}
        e.retrieve=retrieve
        return e

    def question(self,h=None):
        return {'p':{'type':'choice','criteria':{'Yes':h or R.PAIRING.HYPOTHESES['nda-3'],'No':'Other.'}}}

    def test_six_actual_injected_calls_and_free_rawH_control(self):
        e=self.engine()
        state='This agreement is between Acme and Beta.\n\nThe material (\u201cConfidential Information\u201d) stays protected.\n\nKeep records for 20 days.'
        question=self.question();h=question['p']['criteria']['Yes'];q=R.PAIRING.counterclaim(h)
        result=e.predict(state,question);arms=result['diagnostics']['p']['arms']
        self.assertEqual(len(e.nli.calls),6)
        self.assertEqual(e.counters['nli_positive_pairs_completed'],3)
        self.assertEqual(e.counters['nli_counterclaim_pairs_completed'],3)
        self.assertEqual(len(e.retrieval_calls),1);self.assertEqual(e.retrieval_calls[0][1],h)
        priorities=[a['coverage']['definition_priority'] for a in arms.values()]
        self.assertTrue(all(p==priorities[0] for p in priorities))
        for i,name in enumerate(R.ARM_KEYS):
            a=arms[name]
            self.assertEqual(e.nli.calls[2*i],(a['premise'],h))
            self.assertEqual(e.nli.calls[2*i+1],(a['premise'],q))
            self.assertEqual(a['pooled_threeway_probabilities'],
                {'Entailment':.55,'Contradiction':.15000000000000002,'NotMentioned':.3})
            self.assertEqual(a['coverage']['positive_joint_pair_tokens'],len(a['positive_decoding']['input_ids']))
            self.assertEqual(a['coverage']['counterclaim_joint_pair_tokens'],len(a['counterclaim_decoding']['input_ids']))
        primary=arms['ruvector_top2']
        self.assertEqual(e.base.calls,[(primary['premise'],question)])
        raw=result['ablation_responses']['same_nli_native_raw_h']
        self.assertEqual(raw,result['semantic_ablation_responses']['same_nli_native_raw_h'])
        self.assertEqual(raw['answers']['p']['typed_probabilities'],primary['positive_decoding']['raw_threeway_probabilities'])
        self.assertEqual(result['answers']['p']['typed_probabilities'],primary['pooled_threeway_probabilities'])
        self.assertEqual(result['usage']['semantic_control_extra_forwards'],0)

    def test_unknown_H_rejected_before_any_forward_or_partition(self):
        e=self.engine()
        with self.assertRaises(ValueError):e.predict('A public engineering fixture.',self.question('Unknown statement.'))
        self.assertEqual(e.nli.calls,[]);self.assertEqual(e.base.calls,[])
        self.assertEqual(e.retrieval_calls,[])
        self.assertEqual(e.counters['context_partitions_attempted'],0)

    def test_all_fixed_families_keep_exact_whole_H_and_Q_through_real_validator(self):
        for h in R.PAIRING.HYPOTHESES.values():
            e=self.engine();result=e.predict('Keep records for 20 days.',self.question(h))
            self.assertEqual(len(e.nli.calls),6)
            for i in range(3):
                self.assertEqual(e.nli.calls[2*i][1],h)
                self.assertEqual(e.nli.calls[2*i+1][1],R.PAIRING.PREFIX+h)

    def test_all_question_guards_before_first_forward(self):
        e=self.engine();qs=self.question();qs['bad']=self.question('Unknown statement.')['p']
        with self.assertRaises(ValueError):e.predict('A public engineering fixture.',qs)
        self.assertEqual(e.nli.calls,[]);self.assertEqual(e.base.calls,[])
        self.assertEqual(e.retrieval_calls,[])

    def test_joint_budget_conflict_before_any_forward(self):
        e=self.engine();e.config['joint_pair_token_cap']=8
        with self.assertRaises(ValueError):e.predict('This agreement is between Acme and Beta.',self.question())
        self.assertEqual(e.nli.calls,[]);self.assertEqual(e.base.calls,[])
        self.assertEqual(e.retrieval_calls,[])

    def test_invalid_artifact_rejected_before_base_constructor(self):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump({'not':'frozen'},f);f.flush()
            with patch.object(R.OLD.CandidateEngine,'__init__',side_effect=AssertionError('Must not initialize')):
                with self.assertRaises(ValueError):R.CandidateEngine(artifact_path=f.name)


if __name__=='__main__':unittest.main()
