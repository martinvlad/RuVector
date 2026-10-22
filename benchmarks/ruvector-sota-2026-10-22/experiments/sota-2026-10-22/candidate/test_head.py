"""Behavioral boundary tests using only generated, non-benchmark examples."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
from head import canonical_sha, candidate_configs, features, fit, options, transform
from runtime import CandidateEngine


def sample(i,split="train",kind="choice"):
    if kind=="choice":
        question={"type":"choice","instructions":"Identify the mentioned transport.","criteria":{"one":"bicycle","two":"sailboat","three":"airplane"}}
        p={"one":.65,"two":.25,"three":.1}
    elif kind=="noul":
        question={"type":"noul","instructions":"Does this document mention bicycle?","criteria":{"true":"bicycle mentioned","false":"bicycle absent"}}
        p={"no":.25,"yes":.75}
    else:
        question={"type":"score","instructions":"How high is the stated level?","criteria":["low","medium","high"]}
        p={"0":.2,"1":.5,"2":.3}
    gold=max(p,key=p.get)
    return {"id":f"fixture-{split}-{i}","split":split,"input":{"state":f"bicycle document token{i} role{split}","questions":{"decision":question}},"evaluation":{"type":kind,"gold":gold},"response":{"answers":{"decision":{"type":kind,"probabilities":p,"native_fallback_used":True,"choice":gold}},"usage":{"native_requests":1}}}


def fixtures():
    return [sample(i,"train") for i in range(24)]+[sample(i,"calibration") for i in range(24)]


class Tests(unittest.TestCase):
    def setUp(self):
        self.artifact=fit(fixtures(),candidate_configs()[1])

    def test_temperature_preserves_argmax_for_all_types(self):
        for kind in ("choice","noul","score"):
            s=sample(100,kind=kind)
            before=s["response"]["answers"]["decision"]["probabilities"]
            after=transform(s["response"],s["input"]["state"],s["input"]["questions"],self.artifact)["answers"]["decision"]["probabilities"]
            self.assertEqual(max(before,key=before.get),max(after,key=after.get))
            self.assertAlmostEqual(sum(after.values()),1)
            self.assertTrue(all(math.isfinite(p) and p>0 for p in after.values()))

    def test_option_permutation_and_class_renaming_equivariance(self):
        s=sample(100)
        artifact=fit(fixtures(),candidate_configs()[3])
        a=transform(s["response"],s["input"]["state"],s["input"]["questions"],artifact)["answers"]["decision"]
        perm={"C":"three","A":"one","B":"two"}
        q=copy.deepcopy(s["input"]["questions"])
        q["decision"]["criteria"]={new:q["decision"]["criteria"][old] for new,old in perm.items()}
        r=copy.deepcopy(s["response"])
        r["answers"]["decision"]["probabilities"]={new:r["answers"]["decision"]["probabilities"][old] for new,old in perm.items()}
        b=transform(r,s["input"]["state"],q,artifact)["answers"]["decision"]
        for new,old in perm.items():self.assertAlmostEqual(a["probabilities"][old],b["probabilities"][new],places=12)
        self.assertEqual(a["choice"],perm[b["choice"]])

    def test_held_out_evaluation_metadata_not_read(self):
        class Poison(dict):
            def __getitem__(self,k):raise AssertionError("DEV evaluation metadata was read by trainer")
        records=fixtures()+[sample(1,"dev")]
        records[-1]["evaluation"]=Poison()
        actual=fit(records,candidate_configs()[1])
        self.assertEqual(actual,self.artifact)

    def test_confirmation_rejected_before_fit(self):
        with self.assertRaisesRegex(ValueError,"Confirmation"):
            fit(fixtures()+[sample(100,"confirmation")],candidate_configs()[1])

    def test_cross_role_duplicate_rejected(self):
        records=fixtures();duplicate=copy.deepcopy(records[0]);duplicate["split"]="calibration"
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit(records+[duplicate],candidate_configs()[1])

    def test_unknown_split_rejected(self):
        records=fixtures();records[0]["split"]="official-sealed"
        with self.assertRaisesRegex(ValueError,"Unknown split"):
            fit(records,candidate_configs()[1])

    def test_native_distribution_validation(self):
        s=sample(100);s["response"]["answers"]["decision"]["probabilities"]["one"]=float("nan")
        with self.assertRaisesRegex(ValueError,"Invalid native"):
            transform(s["response"],s["input"]["state"],s["input"]["questions"],self.artifact)

    def test_actual_native_noul_scalar_wire(self):
        s=sample(100,kind="noul")
        answer=s["response"]["answers"]["decision"]
        answer.pop("probabilities");answer["noul"]=.75
        result=transform(s["response"],s["input"]["state"],s["input"]["questions"],self.artifact)["answers"]["decision"]
        self.assertGreater(result["noul"],.5)
        self.assertAlmostEqual(sum(result["probabilities"].values()),1)

    def test_artifact_tamper_rejected(self):
        bad=copy.deepcopy(self.artifact);bad["weights"][0]=3
        s=sample(100)
        with self.assertRaisesRegex(ValueError,"integrity"):
            transform(s["response"],s["input"]["state"],s["input"]["questions"],bad)

    def test_input_response_not_mutated(self):
        s=sample(100);original=copy.deepcopy(s)
        transform(s["response"],s["input"]["state"],s["input"]["questions"],self.artifact)
        self.assertEqual(s,original)

    def test_missing_evidence_features_finite(self):
        s=sample(100)
        x,p=features("",s["input"]["questions"]["decision"],s["response"]["answers"]["decision"])
        self.assertTrue(all(math.isfinite(v) for row in x for v in row))

    def test_runtime_artifact_none_exact_passthrough(self):
        sentinel={"answers":{"q":{"type":"choice","choice":"a"}},"usage":{"native_requests":1}}
        class Base:
            def predict(self,state,questions):return sentinel
        engine=CandidateEngine.__new__(CandidateEngine);engine.engine=Base();engine.artifact=None
        self.assertIs(engine.predict("state",{}),sentinel)

    def test_runtime_one_native_call_and_paired_baseline_preserved(self):
        s=sample(100)
        class Base:
            calls=0
            def predict(self,state,questions):self.calls+=1;return copy.deepcopy(s["response"])
        engine=CandidateEngine.__new__(CandidateEngine);engine.engine=Base();engine.artifact=self.artifact
        result=engine.predict(s["input"]["state"],s["input"]["questions"])
        self.assertEqual(engine.engine.calls,1)
        self.assertEqual(result["baseline104_response"],s["response"])
        self.assertNotIn("baseline104_response",result["baseline104_response"])


if __name__=="__main__":unittest.main()
