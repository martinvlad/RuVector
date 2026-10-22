"""Fail-closed promotion, plan integrity and exactly-once attempt controls."""
import copy
import tempfile
import unittest
from pathlib import Path

import loop


class Controls(unittest.TestCase):
    def setUp(self):
        self.base = dict(n=10, correct=6, accuracy=.6, brier=.7, nll=.9, strict_valid=10, errors=0)

    def test_calibration_gain_passes_without_accuracy_change(self):
        candidate = {**self.base, "brier": .6, "nll": .8}
        self.assertTrue(loop.dominates(candidate, self.base))

    def test_accuracy_regression_rejected_despite_calibration_gain(self):
        candidate = {**self.base, "correct": 5, "accuracy": .5, "brier": .1, "nll": .1}
        self.assertFalse(loop.dominates(candidate, self.base))

    def test_improved_one_proper_score_cannot_hide_regression_in_other(self):
        self.assertFalse(loop.dominates({**self.base, "brier": .6, "nll": 1.0}, self.base))

    def test_invalid_or_missing_results_rejected(self):
        for mutation in ({"errors": 1}, {"strict_valid": 9}, {"n": 9}):
            self.assertFalse(loop.dominates({**self.base, "brier": .6, **mutation}, self.base))

    def test_identical_metrics_do_not_make_improvement(self):
        self.assertFalse(loop.dominates(copy.deepcopy(self.base), self.base))

    def test_attempt_record_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "attempt.json"
            loop.begin_once(path, {"status": "STARTED"})
            with self.assertRaises(FileExistsError):
                loop.begin_once(path, {"status": "STARTED"})
            self.assertEqual(loop.load(path), {"status": "STARTED"})

    def test_path_escape_refused(self):
        with self.assertRaises(ValueError):
            loop.checked_path("../../etc/passwd")

    def test_mutated_pinned_source_stops_before_execution(self):
        plan = {"pins": [{"path": "package.json", "sha256": "0" * 64}],
                "limits": {"paid_calls": 0, "native_batches": 2}}
        with self.assertRaises(ValueError):
            loop.verify_plan(plan)

    def test_paid_or_expanded_execution_refused(self):
        for limits in ({"paid_calls": 1, "native_batches": 2}, {"paid_calls": 0, "native_batches": 7}):
            with self.assertRaises(ValueError):
                loop.verify_plan({"pins": [], "limits": limits})

    def test_threads_and_deadlines_cannot_expand(self):
        limits = dict(paid_calls=0, native_batches=2, threads=2, seconds_per_batch=600,
                      seconds_per_decision=10, candidate_configs=6)
        for mutation in ({"threads": 3}, {"seconds_per_batch": 601}, {"seconds_per_decision": 60}, {"candidate_configs": 7}):
            with self.assertRaises(ValueError):
                loop.verify_plan({"pins": [], "limits": {**limits, **mutation}})

    def test_worker_refuses_mutated_plan_before_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = Path(folder) / "plan.json"
            loop.save(plan, {"not": "the frozen plan"})
            with self.assertRaisesRegex(ValueError, "Worker plan identity mismatch"):
                loop.collect_worker(plan, "development", None, "0" * 64)

    def test_native_state_order_comes_from_original_wire(self):
        record = {"input": {"state": {"a": 1, "z": 2}, "questions": {"decision": {"type": "noul"}}}}
        original = '{"model":"legacy-name","state":{"z":2,"a":1},"questions":{"decision":{"type":"noul"}}}'
        request, body = loop.inference_request(record, original)
        self.assertEqual(list(request["state"]), ["z", "a"])
        self.assertEqual(set(request), {"state", "questions"})
        self.assertIn(b'"state":{"z":2,"a":1}', body)

    def test_literal_request_cannot_change_input_values(self):
        with self.assertRaises(ValueError):
            loop.inference_request({"input": {"state": "x", "questions": {}}}, '{"state":"y","questions":{}}')


if __name__ == "__main__":
    unittest.main()
