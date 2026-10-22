"""Generated input/model-double boundary checks; no corpus or actual inference."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("epoch3_test_runtime",HERE/"runtime.py")
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)


class Tests(unittest.TestCase):
    def test_chunks_cover_all_tokens_and_limit_is_explicit(self):
        offsets=[(i,i+1) for i in range(1000)]
        spans=runtime.chunk_offsets(offsets,1000,max_tokens=192,overlap=32)
        self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],1000)
        self.assertTrue(all(b-a<=192 for a,b in spans))
        self.assertTrue(all(left[1]>=right[0] for left,right in zip(spans,spans[1:])))
        with self.assertRaisesRegex(ValueError,"reject"):
            runtime.chunk_offsets(offsets,1000,max_tokens=10,overlap=2,max_chunks=2)

    def test_empty_state_chunk_is_not_fabricated_evidence(self):
        self.assertEqual(runtime.chunk_offsets([],0),[(0,0)])

    def test_hypothesis_exact_supplied_predicate_no_task_lookup(self):
        q={"type":"choice","instructions":"irrelevant metadata","criteria":{"No":"negation","Yes":"Ome obligations remain."}}
        self.assertEqual(runtime.validate_question(q),"Ome obligations remain.")

    def test_unsupported_semantics_rejected(self):
        for q in [{"type":"noul","criteria":{"true":"A","false":"B"}},{"type":"choice","criteria":{"Entailed":"A","Neutral":"B"}},{"type":"choice","criteria":{"Yes":"","No":"B"}}]:
            with self.assertRaises(ValueError):runtime.validate_question(q)

    def test_lexical_selection_is_label_free_and_stable(self):
        chunks=["boat","bicycle pedal","bicycle pedal"]
        self.assertEqual(runtime.lexical_ids(chunks,"bicycle",2),[1,2])

    def test_nli_actual_mapping_neutral_counts_as_no(self):
        decoder=runtime.MODELS.NliDecoder.__new__(runtime.MODELS.NliDecoder)
        decoder.label_indices={"entailment":2,"contradiction":0,"neutral":1}
        decoder.predict=lambda pairs:(np.array([[0.,6.,0.] for _ in pairs]),{"model_batches":1})
        p,d=decoder.decode(["unrelated"],"permission exists")
        self.assertGreater(p["No"],.99)
        self.assertEqual(d["binary_mapping"],"Yes=entailment; No=contradiction+neutral")

    def test_max_entailment_pooling_same_for_all_arms(self):
        decoder=runtime.MODELS.NliDecoder.__new__(runtime.MODELS.NliDecoder)
        decoder.label_indices={"contradiction":0,"entailment":1,"neutral":2}
        logits=np.array([[0.,5.,0.],[4.,0.,0.]])
        decoder.predict=lambda pairs:(logits,{"model_batches":1})
        p,_=decoder.decode(["allowed","denied"],"permission exists")
        self.assertAlmostEqual(p["Yes"],float(runtime.MODELS.softmax(logits)[0,1]))
        self.assertAlmostEqual(sum(p.values()),1)

    def test_token_limit_rejects_before_any_model_execution(self):
        model=runtime.MODELS.OnnxText.__new__(runtime.MODELS.OnnxText)
        model.max_tokens=512
        model.raw_tokenizer=SimpleNamespace(encode_batch=lambda examples:[SimpleNamespace(ids=list(range(513)))])
        model.session=SimpleNamespace(run=lambda *a:(_ for _ in ()).throw(AssertionError("model ran despite token limit")))
        with self.assertRaisesRegex(ValueError,"refusing hidden"):
            model.predict([("premise","predicate")])

    def test_answer_contract_and_lexicographic_tie(self):
        a=runtime.answer_for({"Yes":.5,"No":.5})
        self.assertEqual(a["choice"],"No");self.assertFalse(a["calibrated"])

    def test_full_pipeline_control_pairing_and_same_decoder(self):
        calls={"baseline":0,"decoder":[]}
        control={"answers":{"decision":{"type":"choice","choice":"No","probabilities":{"Yes":.3,"No":.7}}},"usage":{"native_requests":1}}
        class Base:
            receipt={}
            def predict(self,state,questions):calls["baseline"]+=1;return copy.deepcopy(control)
        class Nli:
            def decode(self,premises,hypothesis):
                calls["decoder"].append((premises,hypothesis))
                return {"Yes":.7,"No":.3},{"examples":[{"truncated":False} for _ in premises],"elapsed_ms":1.0}
        engine=runtime.CandidateEngine.__new__(runtime.CandidateEngine)
        engine.base=Base();engine.nli=Nli()
        engine.config={"chunk_tokens":3,"overlap_tokens":1,"max_chunks":64,"top_k":2}
        engine.bge=SimpleNamespace(raw_tokenizer=SimpleNamespace(encode=lambda text,add_special_tokens:SimpleNamespace(offsets=[(i,i+1) for i in range(len(text))])))
        engine.retrieve=lambda chunks,hyp:([len(chunks)-1,0],{"embedding":{"actual_embedded_texts":len(chunks)+1,"cached_chunk_vectors":0}})
        q={"decision":{"type":"choice","instructions":"Decide","criteria":{"Yes":"A permission exists.","No":"Not established"}}}
        result=engine.predict("abc def ghi",q)
        self.assertEqual(calls["baseline"],1)
        self.assertEqual(len(calls["decoder"]),3)
        self.assertEqual({h for _,h in calls["decoder"]},{"A permission exists."})
        self.assertEqual([len(p) for p,_ in calls["decoder"]],[2,2,2])
        self.assertEqual(result["baseline104_response"],control)
        self.assertEqual(set(result["ablation_responses"]),{"same_nli_lexical_top2","same_nli_positional_first2"})
        self.assertIn("all matched decoder controls",result["usage"]["latency_scope"])
        self.assertEqual(result["answers"]["decision"]["probabilities"],{"Yes":.7,"No":.3})


if __name__=="__main__":unittest.main()
