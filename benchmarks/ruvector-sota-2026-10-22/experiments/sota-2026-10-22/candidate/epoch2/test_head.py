"""Unseen generated diagnostics; no benchmark or confirmation labels loaded."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("epoch2_behavior_head",Path(__file__).parent/"head.py")
head=importlib.util.module_from_spec(spec);spec.loader.exec_module(head)


def fixture(i,role="calibration",kind="choice"):
    if kind=="choice":
        q={"type":"choice","instructions":"Pick the named vehicle","criteria":{"alpha":"bicycle","beta":"sailboat","gamma":"train"}}
        a={"type":kind,"probabilities":{"alpha":.6,"beta":.3,"gamma":.1},"choice":"alpha"}
        gold="alpha"
    elif kind=="noul":
        q={"type":"noul","instructions":"Is bicycle mentioned?","criteria":{"true":"mentioned","false":"absent"}}
        a={"type":kind,"noul":.7};gold="yes"
    else:
        q={"type":"score","instructions":"Choose a level","criteria":["low","medium","high"]}
        a={"type":kind,"probabilities":{"0":.2,"1":.5,"2":.3},"score":.55};gold="1"
    return {"id":str(i),"split":role,"input":{"state":f"bicycle {role} example {i}","questions":{"decision":q}},"evaluation":{"gold":gold,"type":kind},"response":{"answers":{"decision":a},"usage":{"native_requests":1}}}


def records():
    return [fixture(i,"train") for i in range(12)]+[fixture(i,kind="choice" if i%2 else "noul") for i in range(24)]


class Tests(unittest.TestCase):
    def setUp(self):self.artifact=head.fit(records(),head.candidate_configs()[1])

    def transformed(self,record,artifact=None):
        return head.transform(record["response"],record["input"]["state"],record["input"]["questions"],artifact or self.artifact)

    def test_exact_scorer_decision_invariance_all_types(self):
        for kind in ("choice","noul","score"):
            r=fixture(500,kind=kind);q=r["input"]["questions"]["decision"];a=r["response"]["answers"]["decision"]
            b=self.transformed(r)["answers"]["decision"];labels=head.options(q)
            self.assertEqual(head.argmax(head.distribution(a,labels,kind)),head.argmax(head.distribution(b,labels,kind)))

    def test_noul_scalar_probability_map_consistent(self):
        r=fixture(500,kind="noul");a=self.transformed(r)["answers"]["decision"]
        self.assertEqual(a["noul"],a["probabilities"]["yes"])
        self.assertAlmostEqual(1-a["noul"],a["probabilities"]["no"])

    def test_noul_half_tie_and_nextafter_exact_decisions(self):
        for temperature in (.1,1,100):
            for value in (0.,math.nextafter(.5,0),.5,math.nextafter(.5,1),1.):
                p={"no":1-value,"yes":value};new,_=head.tempered(p,temperature)
                self.assertEqual(head.argmax(p),head.argmax(new),(temperature,value,new))
                self.assertAlmostEqual(sum(new.values()),1)

    def test_choice_tie_semantics_and_exact_choice_field(self):
        r=fixture(500);a=r["response"]["answers"]["decision"]
        a["probabilities"]={"alpha":.4,"beta":.4,"gamma":.2}
        b=self.transformed(r)["answers"]["decision"]
        self.assertEqual(b["choice"],a["choice"])
        self.assertEqual(head.argmax(b["probabilities"]),"alpha")

    def test_score_entire_answer_and_moment_identity(self):
        r=fixture(500,kind="score");before=copy.deepcopy(r["response"]["answers"]["decision"])
        after=self.transformed(r)["answers"]["decision"]
        self.assertEqual(before,after)
        self.assertEqual(sum(int(k)*p for k,p in before["probabilities"].items()),sum(int(k)*p for k,p in after["probabilities"].items()))

    def test_score_degenerate_boundaries_identity(self):
        for index in ("0","2"):
            r=fixture(500,kind="score");a=r["response"]["answers"]["decision"]
            a["probabilities"]={str(i):float(str(i)==index) for i in range(3)};a["score"]=float(index)/2
            self.assertEqual(self.transformed(r)["answers"]["decision"],a)

    def test_positive_normalized_classification_distributions(self):
        for kind in ("choice","noul"):
            r=fixture(500,kind=kind);a=self.transformed(r)["answers"]["decision"]
            self.assertAlmostEqual(sum(a["probabilities"].values()),1)
            self.assertTrue(all(math.isfinite(p) and p>0 for p in a["probabilities"].values()))

    def test_option_renaming_and_permutation_non_ties(self):
        r=fixture(500);before=self.transformed(r)["answers"]["decision"]
        mapping={"Z":"gamma","Y":"alpha","X":"beta"}
        q=r["input"]["questions"]["decision"];a=r["response"]["answers"]["decision"]
        q["criteria"]={new:q["criteria"][old] for new,old in mapping.items()}
        a["probabilities"]={new:a["probabilities"][old] for new,old in mapping.items()};a["choice"]="Y"
        after=self.transformed(r)["answers"]["decision"]
        for new,old in mapping.items():self.assertAlmostEqual(after["probabilities"][new],before["probabilities"][old])
        self.assertEqual(after["choice"],"Y")

    def test_missing_choice_distribution_rejected(self):
        r=fixture(500);r["response"]["answers"]["decision"].pop("probabilities")
        with self.assertRaisesRegex(ValueError,"Exact label"):self.transformed(r)

    def test_native_noul_without_distribution_supported(self):
        r=fixture(500,kind="noul");self.assertNotIn("probabilities",r["response"]["answers"]["decision"])
        self.assertIn("probabilities",self.transformed(r)["answers"]["decision"])

    def test_inconsistent_noul_map_rejected(self):
        r=fixture(500,kind="noul");r["response"]["answers"]["decision"]["probabilities"]={"yes":.3,"no":.7}
        with self.assertRaisesRegex(ValueError,"Inconsistent"):self.transformed(r)

    def test_noul_map_nonfinite_bool_and_nonnumeric_rejected(self):
        for bad in (float("nan"),float("inf"),True,".7"):
            r=fixture(500,kind="noul");r["response"]["answers"]["decision"]["probabilities"]={"yes":bad,"no":.3}
            with self.assertRaisesRegex(ValueError,"Inconsistent"):self.transformed(r)

    def test_dev_and_train_labels_not_read(self):
        class Poison(dict):
            def __getitem__(self,key):raise AssertionError("Noncalibration labels read")
        data=records()
        for row in data:
            if row["split"]=="train":row["evaluation"]=Poison()
        row=fixture(999,"dev");row["evaluation"]=Poison();data.append(row)
        self.assertEqual(head.fit(data,head.candidate_configs()[1]),self.artifact)

    def test_confirmation_and_crossrole_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError,"Confirmation"):head.fit(records()+[fixture(999,"confirmation")],head.candidate_configs()[0])
        duplicate=copy.deepcopy(records()[0]);duplicate["split"]="calibration"
        with self.assertRaisesRegex(ValueError,"Duplicate"):head.fit(records()+[duplicate],head.candidate_configs()[0])

    def test_artifact_tamper_and_invalid_temperature(self):
        bad=copy.deepcopy(self.artifact);bad["temperatures"]["global"]["temperature"]=0
        with self.assertRaises(ValueError):self.transformed(fixture(500),bad)
        for t in (0,-1,float("inf"),float("nan"),True,"1"):
            with self.assertRaises(ValueError):head.tempered({"yes":.6,"no":.4},t)

    def test_input_immutability(self):
        r=fixture(500);original=copy.deepcopy(r);self.transformed(r);self.assertEqual(r,original)


if __name__=="__main__":unittest.main()
