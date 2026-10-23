"""Budget and confirmation-gate regression tests; no model/native execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("epoch10_loop", Path(__file__).with_name("epoch10_loop.py"))
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
                "prior_closed_study_native_attempts": 12, "prior_closed_original_study_attempts": 6,
                "prior_closed_epoch5_study_attempts": 1, "prior_closed_epoch6_study_attempts": 1, "prior_closed_epoch7_study_attempts": 1, "prior_closed_epoch8_study_attempts": 2, "prior_closed_epoch9_study_attempts": 1, "study_id": "native-evidence-role-head-e10",
                "new_study_native_attempt_cap": 2, "new_study_native_attempts_before": 0,
                "runtime_admission": {"formula_id": "48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1", "max_DEV_units": 10, "max_confirmation_units": 10}, "datasets": {"train": "train", "development": "dev", "confirmation": "confirm"}, "train": "train", "training_questions": 72, "calibration": "none",
                "pins": [{"path": p} for p in ("experiments/sota-2026-10-22/benchmark/evaluate.py", "experiments/sota-2026-10-22/benchmark/sources/jevbench_scoring.py", "experiments/sota-2026-10-22/benchmark/source-manifest.json", "experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py")]}
        with mock.patch.object(M.T, "verify_plan"), mock.patch.object(M.T, "load", return_value=base):
            self.assertIs(M.require_plan(Path("unused")), base)
            for key, bad in (("prior_closed_study_native_attempts", 8), ("prior_closed_original_study_attempts", 5), ("prior_closed_epoch5_study_attempts", 0), ("new_study_native_attempt_cap", 3)):
                old = base[key]; base[key] = bad
                with self.assertRaises(ValueError): M.require_plan(Path("unused"))
                base[key] = old
            for key, bad in (("GPU_calls", 1), ("seconds_per_batch", 601)):
                old = base["limits"][key]; base["limits"][key] = bad
                with self.assertRaises(ValueError): M.require_plan(Path("unused"))
                base["limits"][key] = old

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
        return {"study_id": "native-evidence-role-head-e10", "limits": {"seconds_per_batch": 600, "seconds_per_decision": 30},
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
                if phase == "development":
                    (study / "fitted-head.json").write_text("{}")
                    (study / "readout-fit-lock.json").write_text("{}")
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
        self.assertEqual(result["prior_closed_attempts"], 12)
        self.assertEqual(result["lifetime_native_attempts"], 13)
        self.assertFalse(result["confirmation_consumed_or_attempted"])

    def test_passing_dev_slow_model_preserves_confirmation(self):
        calls, result = self.exercise_parent(True, slow=True)
        self.assertEqual(calls, ["development"])
        self.assertEqual(result["status"], "BLOCKED_CONFIRMATION_RUNTIME_BUDGET")

    def test_only_admitted_dev_starts_second_distinct_phase(self):
        calls, result = self.exercise_parent(True)
        self.assertEqual(calls, ["development", "confirmation"])
        self.assertEqual(result["lifetime_native_attempts"], 14)
        self.assertEqual(result["actual_native_attempts"], 2)
        self.assertTrue(result["confirmation_consumed_or_attempted"])

    def test_confirmation_process_failure_retires_bank_without_HTTP(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp); planpath=study/"plan.json";planpath.write_text("{}")
            def phase(path, sha, plan, name, number):
                folder=study/"runs"/name;folder.mkdir(parents=True)
                (folder/"attempt.json").write_text("{}")
                if name=="confirmation":raise ValueError("constructor failed before HTTP")
                for n in ("fitted-head.json","readout-fit-lock.json"):(study/n).write_text("{}")
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


class TrainingIsolation(unittest.TestCase):
    def exercise(self, fail_fit=False):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp); run=study/"runs/development";run.mkdir(parents=True)
            plan={"datasets":{"train":"train", "development":"dev", "confirmation":"conf"},
                  "expected_native_receipt":{"backend":"native"},"expected_nli_revision":"revision",
                  "expected_nli_sha256":"digest","limits":{"seconds_per_decision":30},"training_contract":"contract"}
            receipt={"backend":"native","nli":{"revision":"revision","model_sha256":"digest"}}
            engine=mock.Mock(native_pid=987654321,receipt=receipt)
            engine.execution_snapshot.return_value={"counters":{}}
            read=[];fits=[];requests=[]
            def rows(path):
                corpus=str(path);read.append(corpus)
                if corpus=="dev": self.assertTrue((study/"readout-fit-lock.json").exists())
                self.assertNotEqual(corpus,"conf")
                return [{"id":corpus+str(i),"input_sha256":"a"*64,"evaluation":{"original_threeway_label":"Entailment"}} for i in range(72 if corpus=="train" else 24)]
            def fit(records, artifact):
                fits.append(len(records));self.assertEqual(read,["train"])
                self.assertTrue(all(r["measured_phase"]=="train" for r in records))
                self.assertEqual(len((run/"training-cache.jsonl").read_text().splitlines()),72)
                if fail_fit: raise ValueError("fixed fit failed, no fallback")
                artifact.write_text("{}")
                return {"fit_once":True}
            engine.fit_from_records.side_effect=fit
            class Reply:
                status=200
                def read(self): return b'{"unscored_fake_response":true}'
            class Connection:
                def __init__(self,*a,**kw): pass
                def request(self,method,path,body,headers):
                    obj=json.loads(body);requests.append(obj)
                    if len(requests)>72:selfouter.assertTrue((study/"readout-fit-lock.json").exists())
                    selfouter.assertEqual(set(obj),{"state","questions"})
                def getresponse(self):return Reply()
                def close(self):pass
            selfouter=self
            httpd=mock.Mock(server_port=12345);httpd.serve_forever.return_value=None
            server=mock.Mock();server.make_server.return_value=httpd
            runtime=mock.Mock();runtime.CandidateEngine.return_value=engine
            modules={"server":server,"candidate.epoch10.runtime":runtime}
            metrics=GatesAndAttemptBudget().metrics()
            with mock.patch.object(M,"STUDY",study),mock.patch.object(M,"require_plan",return_value=plan),mock.patch.object(M.importlib,"import_module",side_effect=lambda k:modules[k]),mock.patch.object(M.T,"checked_path",side_effect=Path),mock.patch.object(M.T,"rows",side_effect=rows),mock.patch.object(M.T,"inference_request",return_value=({"state":"text","questions":[]},b'{"state":"text","questions":[]}')),mock.patch.object(M.http.client,"HTTPConnection",Connection),mock.patch.object(M,"score_arms",return_value=metrics):
                if fail_fit:
                    with self.assertRaises(ValueError):M.worker(study/"plan.json","frozen",M.time.time()+600,"development")
                else:M.worker(study/"plan.json","frozen",M.time.time()+600,"development")
            self.assertEqual(fits,[72]);self.assertEqual(read,["train"] if fail_fit else ["train","dev"])
            self.assertEqual(len(requests),72 if fail_fit else 96)
            self.assertEqual(engine.close.call_count,1)
            if not fail_fit:
                lock=json.loads((study/"readout-fit-lock.json").read_text());self.assertEqual(len(lock["train_inputs"]),72)
                self.assertEqual(lock["DEV_requests_before_fit_lock"],0)
                report=json.loads((run/"report.json").read_text());self.assertEqual(report["train_completed"],72);self.assertEqual(report["development_completed"],24)
    def test_fit_artifact_locked_before_any_DEV_file_read_or_request(self):self.exercise()
    def test_fit_failure_never_reads_or_predicts_DEV_and_never_falls_back(self):self.exercise(True)
    def test_confirmation_rejects_changed_fit_artifact_before_constructor(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);(study/"runs/development").mkdir(parents=True)
            for name in ("runs/development/development-comparison.json","readout-fit-lock.json","fitted-head.json"):(study/name).write_text("{}")
            (study/"runtime-admission.json").write_text('{"allowed":true}')
            lock={"plan_sha256":"frozen","development_comparison_sha256":M.T.digest(study/"runs/development/development-comparison.json"),"runtime_admission_sha256":M.T.digest(study/"runtime-admission.json"),"fitted_head_sha256":M.T.digest(study/"fitted-head.json"),"fit_lock_sha256":M.T.digest(study/"readout-fit-lock.json")}
            (study/"confirmation-selection-lock.json").write_text(json.dumps(lock));(study/"fitted-head.json").write_text('{"changed":true}')
            runtime=mock.Mock()
            with mock.patch.object(M,"STUDY",study),mock.patch.object(M,"require_plan",return_value={}),mock.patch.object(M.importlib,"import_module",return_value=runtime):
                with self.assertRaises(ValueError):M.worker(study/"plan.json","frozen",M.time.time()+600,"confirmation")
            runtime.CandidateEngine.assert_not_called()


if __name__ == "__main__": unittest.main(verbosity=2)
