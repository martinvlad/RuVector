import copy
import os
import unittest
from sparse_transfer import sparse_payload, state_hash, train
from ultra_adapter import UltraAdapter


def fixture():
    rows=[dict(s=f"n{i}",r="r",o=f"n{i+1}",split="train") for i in range(20)]
    rows += [dict(s="n0",r="q",o="n20",split="train"),
             dict(s="n1",r="q",o="n19",split="valid"),
             dict(s="n0",r="r",o="n2",split="test")]
    return dict(name="synthetic-test",triples=rows)


class SparseContractTests(unittest.TestCase):
    def test_nested_and_coverage_floor(self):
        previous=set()
        for fraction in [.01,.05,.1,.25]:
            data=sparse_payload(fixture(),fraction)
            support={(r["s"],r["r"],r["o"]) for r in data["triples"] if r["split"]=="train"}
            self.assertTrue(previous <= support)
            self.assertEqual({r[1] for r in support},{"q","r"})
            self.assertEqual(len(support),data["support"]["count"])
            self.assertEqual(sum(r["split"]=="test" for r in data["triples"]),1)
            previous=support
        self.assertGreater(sparse_payload(fixture(),.01)["support"]["actualFraction"],.01)

    def test_validation_cannot_change_support(self):
        a=fixture(); b=copy.deepcopy(a)
        b["triples"][-2]["o"]="n18"
        self.assertEqual(sparse_payload(a,.25)["support"],sparse_payload(b,.25)["support"])


@unittest.skipUnless(os.environ.get("ULTRA_CHECKOUT"),"optional training integration")
class TrainingTests(unittest.TestCase):
    def test_real_gradient_update_and_truth_isolation(self):
        a=fixture(); b=copy.deepcopy(a)
        b["triples"][-2]["o"]="n18"
        outputs=[]
        for payload in (a,b):
            model=UltraAdapter(payload,os.environ["ULTRA_CHECKOUT"],checkpoint=False,seed=17)
            before=state_hash(model)
            record=train(model,seed=17,seconds=30,max_steps=2)
            self.assertEqual(record["steps"],2)
            self.assertNotEqual(before,state_hash(model))
            outputs.append(record["finalHash"])
        self.assertEqual(*outputs)


if __name__=="__main__":
    unittest.main()
