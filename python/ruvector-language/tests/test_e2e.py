import copy
import json
from pathlib import Path
import unittest

from ruvector_language import RuGraph, RuGraphError

EXAMPLES = Path(__file__).resolve().parents[3] / "crates/ruvector-language/examples"


class RuGraphE2E(unittest.TestCase):
    def setUp(self):
        self.client = RuGraph()
        self.request = {
            "program": self.client.compile((EXAMPLES / "incident.rvg").read_text()),
            "snapshot": json.loads((EXAMPLES / "snapshot.json").read_text()),
            "context": json.loads((EXAMPLES / "context.json").read_text()),
        }

    def test_native_process_execute_replay(self):
        receipt = self.client.run(self.request)
        self.assertEqual(self.client.replay(self.request, receipt), receipt)
        self.assertTrue(any(x["subject"] == "database" and x["predicate"] == "Degraded" and x["status"] == "supported" for x in receipt["output"]["items"]))

    def test_expiry_and_retraction(self):
        for mutate in (lambda r: r["context"].update(now=1100), lambda r: r["snapshot"].update(observations=[])):
            request = copy.deepcopy(self.request)
            mutate(request)
            receipt = self.client.run(request)
            self.assertTrue(all(x["status"] == "unknown" for x in receipt["output"]["items"]))

    def test_permissions_and_replay_mismatch(self):
        receipt = self.client.run(self.request)
        self.request["context"]["now"] = 1001
        with self.assertRaises(RuGraphError) as result:
            self.client.replay(self.request, receipt)
        self.assertEqual(result.exception.code, "REPLAY_MISMATCH")
        self.request["context"]["capabilities"] = []
        with self.assertRaises(RuGraphError) as result:
            self.client.run(self.request)
        self.assertEqual(result.exception.code, "UNAUTHORIZED")

    def test_nonfinite_rejected(self):
        self.request["context"]["now"] = float("nan")
        with self.assertRaises(RuGraphError) as result:
            self.client.run(self.request)
        self.assertEqual(result.exception.code, "INVALID_INPUT")

    def test_full_u64_timestamps_are_lossless(self):
        maximum = 2**64 - 1
        self.request["context"]["now"] = maximum - 2
        for observation in self.request["snapshot"]["observations"]:
            observation["observed_at"] = maximum - 3
            observation["expires_at"] = maximum
        receipt = self.client.run(self.request)
        self.assertEqual(receipt["now"], maximum - 2)
        observed = [e for d in receipt["output"]["items"] for e in d["evidence"]]
        self.assertTrue(observed)
        self.assertTrue(all(e["expires_at"] == maximum for e in observed))
        self.assertEqual(self.client.replay(self.request, receipt), receipt)


if __name__ == "__main__":
    unittest.main()
