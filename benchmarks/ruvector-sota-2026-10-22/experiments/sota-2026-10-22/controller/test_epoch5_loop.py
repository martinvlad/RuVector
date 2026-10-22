"""Budget and confirmation-gate regression tests; no model/native execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("epoch5_loop", Path(__file__).with_name("epoch5_loop.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class GatesAndAttemptBudget(unittest.TestCase):
    def metrics(self):
        base = {"n": 24, "correct": 12, "strict_valid": 24, "errors": 0, "brier": .5, "nll": .7}
        result = {name: dict(base) for name in M.ARMS}
        result["ruvector_top2"].update(correct=16, brier=.4, nll=.6)
        return result

    def test_all_controls_required(self):
        values = self.metrics()
        self.assertTrue(M.development_gate(values)[0])
        values["native104_on_ruvector_evidence"]["nll"] = .59
        self.assertFalse(M.development_gate(values)[0])

    def test_invalid_control_stops_confirmation(self):
        values = self.metrics()
        values["same_nli_positional_first2"].update(errors=1, strict_valid=23)
        self.assertFalse(M.development_gate(values)[0])

    def test_matched_control_tie_is_not_improvement(self):
        values = self.metrics()
        values["same_nli_lexical_top2"] = dict(values["ruvector_top2"])
        self.assertFalse(M.development_gate(values)[0])

    def test_missing_control_and_nonfinite_scores_stop(self):
        values = self.metrics()
        values.pop("same_nli_lexical_top2")
        self.assertFalse(M.development_gate(values)[0])
        values = self.metrics()
        values["ruvector_top2"]["nll"] = float("nan")
        self.assertFalse(M.development_gate(values)[0])

    def test_empty_dev_cannot_open_confirmation(self):
        values = self.metrics()
        for row in values.values():
            row.update(n=0, correct=0, strict_valid=0)
        self.assertFalse(M.development_gate(values)[0])

    def test_owned_orphan_group_is_escalated(self):
        live = [987654321]
        def kill(pgid, sig):
            self.assertEqual(pgid, 987654321)
            if sig == M.signal.SIGKILL:
                live.clear()
        with mock.patch.object(M, "owned_group_members", side_effect=lambda _: list(live)), \
             mock.patch.object(M.os, "killpg", side_effect=kill), \
             mock.patch.object(M.time, "monotonic", side_effect=iter(range(30))), \
             mock.patch.object(M.time, "sleep"):
            proof = M.close_owned_group(987654321)
        self.assertEqual(proof["signals"], ["SIGTERM", "SIGKILL"])
        self.assertEqual(proof["live_members_after"], [])

    def test_refuses_unowned_process_group(self):
        with self.assertRaises(ValueError):
            M.close_owned_group(M.os.getpgrp())
        with self.assertRaises(ValueError):
            M.close_owned_group(1)

    def test_single_shared_deadline_and_no_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            study = Path(temp)
            planpath = study / "plan.json"
            planpath.write_text("{}")
            plan = {"study_id": "native-deberta-base-resolved-2026-10-22-e5", "limits": {"seconds_per_batch": 600}, "lease_expires_unix": M.time.time() + 1000}
            process = mock.Mock(pid=987654321, returncode=0)
            process.wait.return_value = 0
            with mock.patch.object(M, "STUDY", study), mock.patch.object(M, "RUN", study / "runs/composite"), \
                 mock.patch.object(M, "require_plan", return_value=plan), \
                 mock.patch.object(M.subprocess, "Popen", return_value=process) as popen, \
                 mock.patch.object(M.os, "killpg"):
                M.parent(planpath)
                self.assertEqual(popen.call_count, 1)
                argv = popen.call_args.args[0]
                self.assertIn("--worker", argv)
                deadline = float(argv[argv.index("--deadline") + 1])
                self.assertLessEqual(deadline - M.time.time(), 600)
                self.assertLessEqual(process.wait.call_args.kwargs["timeout"], 600)
                completion = json.loads((study / "runs/composite/completion.json").read_text())
                self.assertEqual(completion["new_study_attempts_remaining"], 0)
                with self.assertRaises(FileExistsError):
                    M.parent(planpath)
                self.assertEqual(popen.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
