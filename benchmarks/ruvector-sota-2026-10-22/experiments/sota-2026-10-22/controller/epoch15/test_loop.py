"""Budget and confirmation-gate regression tests; no model/native execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("epoch15_loop", Path(__file__).with_name("loop.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class GatesAndAttemptBudget(unittest.TestCase):
    def metrics(self):
        base = {"n": 24, "correct": 12, "strict_valid": 24, "errors": 0, "brier": .5, "nll": .7}
        result = {name: dict(base) for name in M.ARMS}
        result["ruvector_top2"].update(correct=16, brier=.4, nll=.6)
        return result

    def test_closed_ledgers_and_zero_paid_budget_are_required(self):
        base = {"limits": {"native_batches": 2, "threads": 2, "paid_calls": 0, "GPU_calls": 0, "seconds_per_batch": 600},
                "prior_closed_study_native_attempts": 16, "prior_closed_original_study_attempts": 6,
                "prior_closed_epoch5_study_attempts": 1, "prior_closed_epoch6_study_attempts": 1, "prior_closed_epoch7_study_attempts": 1, "prior_closed_epoch8_study_attempts": 2, "prior_closed_epoch9_study_attempts": 1, "prior_closed_epoch10_study_attempts": 1, "prior_closed_epoch11_study_attempts": 1, "prior_closed_epoch12_study_attempts": 1, "prior_closed_epoch13_study_attempts": 1, "prior_closed_epoch14_native_attempts": 0, "study_id": "native-definition-priority-deberta-threeway-e15",
                "new_study_native_attempt_cap": 2, "new_study_native_attempts_before": 0,
                "runtime_admission": {"formula_id": "48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1", "max_DEV_units": 10, "max_confirmation_units": 10}, "datasets": {"development": "dev", "confirmation": "confirm"}, "train": "none", "calibration": "none",
                "pins": [{"path": p} for p in ("experiments/sota-2026-10-22/benchmark/evaluate.py", "experiments/sota-2026-10-22/benchmark/sources/jevbench_scoring.py", "experiments/sota-2026-10-22/benchmark/source-manifest.json", "experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py")]}
        with mock.patch.object(M.T, "verify_plan"), mock.patch.object(M.T, "load", return_value=base):
            self.assertIs(M.require_plan(Path("unused")), base)
            for key, bad in (("prior_closed_study_native_attempts", 7), ("prior_closed_original_study_attempts", 5), ("prior_closed_epoch5_study_attempts", 0), ("prior_closed_epoch9_study_attempts", 0), ("prior_closed_epoch10_study_attempts", 0), ("prior_closed_epoch11_study_attempts", 0), ("prior_closed_epoch12_study_attempts", 0), ("prior_closed_epoch13_study_attempts", 0), ("prior_closed_epoch14_native_attempts", 1), ("new_study_native_attempt_cap", 3)):
                old = base[key]; base[key] = bad
                with self.assertRaises(ValueError): M.require_plan(Path("unused"))
                base[key] = old
            for key, bad in (("GPU_calls", 1), ("seconds_per_batch", 601)):
                old = base["limits"][key]; base["limits"][key] = bad
                with self.assertRaises(ValueError): M.require_plan(Path("unused"))
                base["limits"][key] = old

    def test_confirmation_process_failure_retires_bank_without_HTTP(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp); planpath=study/"plan.json";planpath.write_text("{}")
            def phase(path, sha, plan, name, number):
                folder=study/"runs"/name;folder.mkdir(parents=True)
                (folder/"attempt.json").write_text("{}")
                if name=="confirmation":raise ValueError("constructor failed before HTTP")
                (folder/"development-comparison.json").write_text("{}")
                return {"metrics":self.metrics(),"records":[{"elapsed_s":2.}]*24,"initialization_seconds":2.}
            with mock.patch.object(M,"STUDY",study),mock.patch.object(M,"require_plan",return_value=self.runtime_plan()),mock.patch.object(M,"run_phase",side_effect=phase):
                with self.assertRaises(ValueError):M.parent(planpath)
            result=json.loads((study/"study-completion.json").read_text())
            self.assertEqual(result["actual_native_attempts"],2)
            self.assertTrue(result["confirmation_consumed_or_attempted"])
            self.assertTrue(result["confirmation_phase_attempted"])
            self.assertFalse(result["confirmation_HTTP_started"])
            self.assertFalse((study/"runs/confirmation/started-requests.jsonl").exists())

    def exercise_invocation_failure(self, fail_attempt_save):
        with tempfile.TemporaryDirectory() as temp:
            study = Path(temp); planpath = study / "plan.json"; planpath.write_text("{}")
            plan = self.runtime_plan(); metrics = self.metrics(); real_phase = M.run_phase; real_save = M.T.save
            process = mock.Mock(pid=987654321, returncode=0); process.wait.return_value = 0
            cleanup = {"pgid": process.pid, "live_members_before": [], "live_members_after": [], "finished_within_deadline": True}
            def dispatch(path, sha, plan, phase, number):
                if phase == "development":
                    folder = study / "runs" / phase; folder.mkdir(parents=True)
                    (folder / "attempt.json").write_text("{}")
                    (folder / "development-comparison.json").write_text("{}")
                    return {"metrics": metrics, "records": [{"elapsed_s": 2.}] * 24, "initialization_seconds": 2.}
                return real_phase(path, sha, plan, phase, number)
            def saving(path, value):
                if fail_attempt_save and Path(path).name == "attempt.json": raise OSError("injected PID receipt write failure")
                return real_save(path, value)
            with mock.patch.object(M, "STUDY", study), mock.patch.object(M, "require_plan", return_value=plan), \
                 mock.patch.object(M, "run_phase", side_effect=dispatch), mock.patch.object(M.T, "save", side_effect=saving), \
                 mock.patch.object(M.subprocess, "Popen", **({"return_value": process} if fail_attempt_save else {"side_effect": OSError("injected Popen failure")})) as popen, \
                 mock.patch.object(M, "close_owned_group", return_value=cleanup) as closed:
                with self.assertRaises(RuntimeError): M.parent(planpath)
                result = json.loads((study / "study-completion.json").read_text())
                self.assertEqual(popen.call_count, 1)
                self.assertTrue((study / "runs/confirmation/popen-attempt.json").exists())
                self.assertFalse((study / "runs/confirmation/attempt.json").exists())
                self.assertFalse((study / "runs/confirmation/started-requests.jsonl").exists())
                self.assertTrue(result["confirmation_consumed_or_attempted"])
                self.assertEqual(result["actual_native_attempts"], 2)
                self.assertEqual(result["native_processes_started"], 2 if fail_attempt_save else 1)
                self.assertEqual(closed.call_count, 1 if fail_attempt_save else 0)
                completion = json.loads((study / "runs/confirmation/completion.json").read_text())
                self.assertEqual(completion["native_process_started"], fail_attempt_save)
                with self.assertRaises(FileExistsError): M.parent(planpath)
                self.assertEqual(popen.call_count, 1)

    def test_confirmation_Popen_failure_marker_retires_bank_without_claiming_process(self):
        self.exercise_invocation_failure(False)

    def test_confirmation_PID_receipt_failure_cleans_process_and_retires_bank(self):
        self.exercise_invocation_failure(True)

    def test_development_Popen_failure_retires_DEV_without_claiming_process(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);planpath=study/"plan.json";planpath.write_text("{}")
            with mock.patch.object(M,"STUDY",study), mock.patch.object(M,"require_plan",return_value=self.runtime_plan()), \
                 mock.patch.object(M.subprocess,"Popen",side_effect=OSError("injected DEV Popen failure")) as popen:
                with self.assertRaises(RuntimeError):M.parent(planpath)
                result=json.loads((study/"study-completion.json").read_text())
                self.assertTrue(result["development_conservatively_exposed_DEV"])
                self.assertFalse(result["confirmation_consumed_or_attempted"])
                self.assertEqual(result["actual_native_attempts"],1)
                self.assertEqual(result["native_processes_started"],0)
                self.assertEqual(result["lifetime_native_attempts"],17)
                self.assertTrue((study/"runs/development/popen-attempt.json").exists())
                self.assertFalse((study/"runs/development/attempt.json").exists())
                self.assertFalse((study/"runs/confirmation").exists())
                with self.assertRaises(FileExistsError):M.parent(planpath)
                self.assertEqual(popen.call_count,1)

    def test_all_controls_required(self):
        values = self.metrics()
        self.assertTrue(M.development_gate(values)[0])
        values["native104_on_ruvector_evidence"]["nll"] = .59
        self.assertFalse(M.development_gate(values)[0])

    def test_single_correct_gain_is_insufficient(self):
        values = self.metrics()
        values["same_nli_lexical_top2"]["correct"] = 15
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
             mock.patch.object(M.time, "time", side_effect=iter(range(30))), \
             mock.patch.object(M.time, "sleep"):
            proof = M.close_owned_group(987654321)
        self.assertEqual(proof["signals"], ["SIGTERM", "SIGKILL"])
        self.assertEqual(proof["live_members_after"], [])

    def test_refuses_unowned_process_group(self):
        with self.assertRaises(ValueError):
            M.close_owned_group(M.os.getpgrp())
        with self.assertRaises(ValueError):
            M.close_owned_group(1)

    def runtime_plan(self):
        return {"study_id": "native-definition-priority-deberta-threeway-e15", "limits": {"seconds_per_batch": 600, "seconds_per_decision": 30},
                "lease_expires_unix": M.time.time() + 2000,
                "runtime_admission": {"formula_id": "48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1", "max_DEV_units": 20, "max_confirmation_units": 20}}

    def test_runtime_forecast_blocks_slow_or_short_lease(self):
        plan = self.runtime_plan()
        self.assertTrue(M.confirmation_runtime_admission(plan, [{"elapsed_s": 2.}] * 24, 3)["allowed"])
        self.assertFalse(M.confirmation_runtime_admission(plan, [{"elapsed_s": 14.}] * 24, 3)["allowed"])
        plan["lease_expires_unix"] = M.time.time() + 150
        self.assertFalse(M.confirmation_runtime_admission(plan, [{"elapsed_s": 2.}] * 24, 3)["allowed"])
        with self.assertRaises(ValueError): M.confirmation_runtime_admission(plan, [], 3)
        with self.assertRaises(ValueError): M.confirmation_runtime_admission(plan, [{"elapsed_s": 2.}] * 24, 0)

    def exercise_parent(self, passing, slow=False):
        with tempfile.TemporaryDirectory() as temp:
            study = Path(temp); planpath = study / "plan.json"; planpath.write_text("{}")
            metrics = self.metrics()
            if not passing: metrics["same_nli_lexical_top2"]["correct"] = 20
            calls = []
            def fake_phase(path, sha, plan, phase, number):
                calls.append(phase); folder = study / "runs" / phase; folder.mkdir(parents=True)
                (folder / "attempt.json").write_text("{}")
                (folder / (phase + "-comparison.json")).write_text("{}")
                if phase == "confirmation":
                    self.assertTrue((study / "confirmation-selection-lock.json").exists())
                    (folder / "started-requests.jsonl").write_text("{}\n")
                return {"metrics": metrics, "records": [{"elapsed_s": 14. if slow else 2.}] * 24, "initialization_seconds": 2.}
            with mock.patch.object(M, "STUDY", study), mock.patch.object(M, "require_plan", return_value=self.runtime_plan()), mock.patch.object(M, "run_phase", side_effect=fake_phase):
                M.parent(planpath)
                result = json.loads((study / "study-completion.json").read_text())
                with self.assertRaises(FileExistsError): M.parent(planpath)
            return calls, result

    def test_dev_failure_never_opens_confirmation_or_retries(self):
        calls, result = self.exercise_parent(False)
        self.assertEqual(calls, ["development"])
        self.assertEqual(result["status"], "REJECTED_DEV_GATE")
        self.assertEqual(result["lifetime_native_attempts"], 17)
        self.assertFalse(result["confirmation_consumed_or_attempted"])

    def test_passing_dev_slow_model_preserves_confirmation(self):
        calls, result = self.exercise_parent(True, slow=True)
        self.assertEqual(calls, ["development"])
        self.assertEqual(result["status"], "BLOCKED_CONFIRMATION_RUNTIME_BUDGET")

    def test_only_admitted_dev_starts_second_distinct_phase(self):
        calls, result = self.exercise_parent(True)
        self.assertEqual(calls, ["development", "confirmation"])
        self.assertEqual(result["lifetime_native_attempts"], 18)
        self.assertEqual(result["actual_native_attempts"], 2)
        self.assertTrue(result["confirmation_consumed_or_attempted"])

    def test_each_phase_owns_new_process_and_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            study = Path(temp); path = study / "plan.json"; path.write_text("{}")
            process = mock.Mock(pid=987654321, returncode=0); process.wait.return_value = 0
            def loaded(p):
                if p.name == "runtime.json": return {"receipt": {"initialization_wall_seconds": 2}}
                if "comparison" in p.name: return {"metrics": self.metrics()}
                return {}
            with mock.patch.object(M, "STUDY", study), mock.patch.object(M.subprocess, "Popen", return_value=process) as popen, mock.patch.object(M.T, "load", side_effect=loaded), mock.patch.object(M.T, "rows", return_value=[]), mock.patch.object(M.os, "killpg"):
                M.run_phase(path, M.T.digest(path), self.runtime_plan(), "development", 1)
                self.assertEqual(popen.call_count, 1)
                argv = popen.call_args.args[0]
                self.assertEqual(argv[argv.index("--phase") + 1], "development")
                self.assertLessEqual(float(argv[argv.index("--deadline") + 1])-M.time.time(), 595)
                self.assertLessEqual(process.wait.call_args.kwargs["timeout"], 595)
                with self.assertRaises(FileExistsError): M.run_phase(path, M.T.digest(path), self.runtime_plan(), "development", 1)
                self.assertEqual(popen.call_count, 1)


if __name__ == "__main__": unittest.main(verbosity=2)
