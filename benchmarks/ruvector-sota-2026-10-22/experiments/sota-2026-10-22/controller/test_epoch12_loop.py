"""Budget and confirmation-gate regression tests; no model/native execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import hashlib
import sys
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("epoch12_loop", Path(__file__).with_name("epoch12_loop.py"))
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
                "prior_closed_study_native_attempts": 14, "prior_closed_original_study_attempts": 6,
                "prior_closed_epoch5_study_attempts": 1, "prior_closed_epoch6_study_attempts": 1, "prior_closed_epoch7_study_attempts": 1, "prior_closed_epoch8_study_attempts": 2, "prior_closed_epoch9_study_attempts": 1, "prior_closed_epoch10_study_attempts": 1, "prior_closed_epoch11_study_attempts": 1, "study_id": "native-fp32-quantization-fidelity-e12",
                "new_study_native_attempt_cap": 2, "new_study_native_attempts_before": 0,
                "runtime_admission": {"formula_id": "48xDEVmaxHTTPxunitratio+2xDEVinit+60-v1", "max_DEV_units": 10, "max_confirmation_units": 10}, "datasets": {"train":"train", "development": "dev", "confirmation": "confirm"}, "train": "train", "calibration": "none", "training_questions":6,"sanity_questions":6,"training_feature_questions":0,"primary_precision":"FP32_FIXED_BEFORE_TRAIN",
                "pins": [{"path": p} for p in ("experiments/sota-2026-10-22/benchmark/evaluate.py", "experiments/sota-2026-10-22/benchmark/sources/jevbench_scoring.py", "experiments/sota-2026-10-22/benchmark/source-manifest.json", "experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py")]}
        with mock.patch.object(M, "verify_plan"), mock.patch.object(M.T, "load", return_value=base):
            self.assertIs(M.require_plan(Path("unused")), base)
            for key, bad in (("prior_closed_study_native_attempts", 7), ("prior_closed_original_study_attempts", 5), ("prior_closed_epoch5_study_attempts", 0), ("prior_closed_epoch9_study_attempts", 0), ("prior_closed_epoch10_study_attempts", 0), ("new_study_native_attempt_cap", 3)):
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
                for n in ("fitted-head.json","readout-fit-lock.json"):(study/n).write_text("{}")
                (folder/"development-comparison.json").write_text("{}")
                (study/"train-sanity-completion-lock.json").write_text("{}")
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
                    (study / "train-sanity-completion-lock.json").write_text("{}")
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
        return {"study_id": "native-fp32-quantization-fidelity-e12", "limits": {"seconds_per_batch": 600, "seconds_per_decision": 30},
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
                if phase == "development": (study / "train-sanity-completion-lock.json").write_text("{}")
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
        self.assertEqual(result["lifetime_native_attempts"], 15)
        self.assertFalse(result["confirmation_consumed_or_attempted"])

    def test_passing_dev_slow_model_preserves_confirmation(self):
        calls, result = self.exercise_parent(True, slow=True)
        self.assertEqual(calls, ["development"])
        self.assertEqual(result["status"], "BLOCKED_CONFIRMATION_RUNTIME_BUDGET")

    def test_only_admitted_dev_starts_second_distinct_phase(self):
        calls, result = self.exercise_parent(True)
        self.assertEqual(calls, ["development", "confirmation"])
        self.assertEqual(result["lifetime_native_attempts"], 16)
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


class TrainingBoundaryTests(unittest.TestCase):
    def native_input(self, token="x"):
        return {"state": token, "questions": {"decision": {"instructions": "Is it allowed?", "type": "noul", "criteria": {"true":"Yes","false":"No"}}}}

    def row(self, idx, role):
        value = self.native_input(str(idx))
        return {"id": f"{role}:{idx}", "input":value,"input_sha256": "identity:"+str(idx), "gold": "MUST_NOT_BE_SENT"}

    def test_transport_metadata_never_sends_gold_or_alters_native_input(self):
        row=self.row(0,"train"); native, envelope, body=M.inference_envelope(row,"train")
        self.assertEqual(native,row["input"])
        self.assertEqual(set(envelope),{"state","questions","operation","training_example_id"})
        self.assertEqual(envelope["operation"],"train_sanity")
        self.assertEqual(envelope["training_example_id"],row["id"])
        self.assertNotIn(b"MUST_NOT_BE_SENT",body)
        _, dev, _=M.inference_envelope(row,"development")
        self.assertEqual(dev["operation"],"predict")
        self.assertNotIn("training_example_id",dev)

    def server(self):
        spec=importlib.util.spec_from_file_location("epoch12_server_test",Path(__file__).with_name("epoch12_server.py"))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_dispatch_has_no_quantized_operation_on_confirmation(self):
        server=self.server(); engine=mock.Mock(); body={**self.native_input(),"operation":"train_sanity","training_example_id":"train:1"}
        server.dispatch_request(engine,body,"development")
        engine.predict_train_sanity.assert_called_once_with("x",body["questions"],"train:1")
        engine.predict.assert_not_called()
        with self.assertRaises(server.RequestError):server.dispatch_request(engine,body,"confirmation")
        self.assertEqual(engine.predict_train_sanity.call_count,1)
        engine.reset_mock(); server.dispatch_request(engine,{**self.native_input(),"operation":"predict"},"confirmation")
        engine.predict.assert_called_once();engine.predict_train_sanity.assert_not_called()

    def test_dispatch_rejects_labels_missing_unknown_or_inconsistent_operations(self):
        server=self.server();engine=mock.Mock();base=self.native_input()
        for bad in ({**base,"gold":"Yes","operation":"train_sanity","training_example_id":"a"},base,
                    {**base,"operation":"quantized"},{**base,"operation":"predict","training_example_id":"a"},
                    {**base,"operation":"train_sanity"}):
            with self.assertRaises(server.RequestError):server.dispatch_request(engine,bad,"development")
        engine.predict.assert_not_called();engine.predict_train_sanity.assert_not_called()

    def test_finish_requires_six_distinct_successes_and_release_but_no_train_score(self):
        rows=[self.row(i,"train") for i in range(6)]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(M,"STUDY",Path(tmp)):
            engine=mock.Mock();engine.finish_training_sanity.return_value={"quantized_session_released":True,"train_sanity_completed":6}
            with self.assertRaises(ValueError):M.finish_train_sanity(engine,rows[:5],"p")
            with self.assertRaises(ValueError):M.finish_train_sanity(engine,rows[:5]+rows[:1],"p")
            engine.finish_training_sanity.assert_not_called()
            engine.finish_training_sanity.return_value={"quantized_session_released":False}
            with self.assertRaises(ValueError):M.finish_train_sanity(engine,rows,"p")
            self.assertFalse((Path(tmp)/"train-sanity-completion-lock.json").exists())
            engine.finish_training_sanity.return_value={"quantized_session_released":True}
            M.finish_train_sanity(engine,rows,"p")
            lock=json.loads((Path(tmp)/"train-sanity-completion-lock.json").read_text())
            self.assertFalse(lock["supervised_fit"]);self.assertEqual(lock["training_feature_queries"],0)
            self.assertEqual(lock["primary_precision"],"FP32_FIXED_BEFORE_TRAIN")
            self.assertNotIn("gold",json.dumps(lock))
            with self.assertRaises(FileExistsError):M.finish_train_sanity(engine,rows,"p")

    def test_pin_verifier_allows_sixty_per_request_but_never_over_sixhundred_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source";p.write_text("unchanged")
            plan={"pins":[{"path":"source","sha256":hashlib.sha256(p.read_bytes()).hexdigest()}],
                  "limits":{"threads":2,"seconds_per_batch":600,"seconds_per_decision":60,"candidate_configs":1,"native_batches":2,"paid_calls":0,"GPU_calls":0}}
            with mock.patch.object(M.T,"checked_path",return_value=p):
                M.verify_plan(plan)
                for key,bad in (("seconds_per_decision",61),("seconds_per_batch",601),("threads",3),("native_batches",3),("candidate_configs",2)):
                    old=plan["limits"][key];plan["limits"][key]=bad
                    with self.assertRaises(ValueError):M.verify_plan(plan)
                    plan["limits"][key]=old
                p.write_text("changed")
                with self.assertRaises(ValueError):M.verify_plan(plan)

    def exercise_mock_worker(self, fail_train=False):
        rows={"train":[self.row(i,"train") for i in range(6)],"development":[self.row(i,"dev") for i in range(24)]}
        events=[];fixture=self;wire_server=self.server()
        class FakeEngine:
            def __init__(self,enable_training_sanity):
                assert enable_training_sanity;self.native_pid=987654321;self.name="fake";self.attribution="synthetic"
                self.receipt={"nli":{"revision":"r","model_sha256":"fp32"},"initialization_wall_seconds":1}
                self.train_count=0;self.ready=False;events.append("init")
            def predict_train_sanity(self,state,questions,identity):
                self.train_count+=1;events.append("train")
                if fail_train and self.train_count==3:raise ValueError("injected sanity failure")
                return {"precision_fidelity":{},"synthetic":True}
            def finish_training_sanity(self):
                assert self.train_count==6;self.ready=True;events.append("release_int8")
                return {"quantized_session_released":True,"train_sanity_completed":6}
            def predict(self,state,questions):
                assert self.ready;events.append("dev");return {"synthetic":True}
            def close(self):events.append("close")
            def execution_snapshot(self):return {"synthetic":True}
        holder={}
        def make_server(engine,*args,phase):holder["engine"]=engine;return mock.Mock(server_port=12345)
        class FakeConnection:
            def __init__(self,*args,**kw):pass
            def request(self,method,path,body,headers):self.body=json.loads(body)
            def getresponse(self):
                try:out=wire_server.dispatch_request(holder["engine"],self.body,"development");status=200
                except Exception as exc:out={"error":str(exc)};status=500
                return types.SimpleNamespace(status=status,read=lambda:json.dumps(out).encode())
            def close(self):pass
        real_import=M.importlib.import_module
        def imports(name):
            if name=="epoch12_server":return types.SimpleNamespace(make_server=make_server)
            if name=="candidate.epoch12.runtime":return types.SimpleNamespace(CandidateEngine=FakeEngine)
            return real_import(name)
        with tempfile.TemporaryDirectory() as tmp:
            study=Path(tmp);(study/"runs/development").mkdir(parents=True);planpath=study/"plan.json";planpath.write_text("{}")
            plan={"datasets":{"train":"train","development":"development","confirmation":"confirmation"},"expected_native_receipt":{},"expected_nli_revision":"r","expected_nli_sha256":"fp32","limits":{"seconds_per_decision":60}}
            with mock.patch.object(M,"STUDY",study),mock.patch.object(M,"require_plan",return_value=plan),mock.patch.object(M.importlib,"import_module",side_effect=imports),mock.patch.object(M.T,"checked_path",side_effect=lambda key:Path(key)),mock.patch.object(M.T,"rows",side_effect=lambda path:rows[str(path)]),mock.patch.object(M.threading,"Thread"),mock.patch.object(M.http.client,"HTTPConnection",FakeConnection),mock.patch.object(M,"score_arms",side_effect=lambda records:{"synthetic_n":len(records)}),mock.patch.object(M,"development_gate",return_value=(False,{})):
                if fail_train:
                    with self.assertRaises(RuntimeError):M.worker(planpath,"p",M.time.time()+60,"development")
                else:M.worker(planpath,"p",M.time.time()+60,"development")
            records=M.T.rows(study/"runs/development/records.jsonl")
            report=json.loads((study/"runs/development/report.json").read_text())
            if fail_train:
                self.assertEqual(len(records),2);self.assertNotIn("dev",events);self.assertNotIn("release_int8",events)
                self.assertFalse((study/"train-sanity-completion-lock.json").exists());self.assertEqual(report["development_completed"],0)
            else:
                self.assertEqual(len(records),30);self.assertEqual([r["measured_phase"] for r in records],["train"]*6+["development"]*24)
                self.assertEqual(events,["init"]+["train"]*6+["release_int8"]+["dev"]*24+["close"])
                comparison=json.loads((study/"runs/development/development-comparison.json").read_text())
                self.assertEqual(comparison["metrics"]["synthetic_n"],24)
                self.assertEqual(report["train_sanity_completed"],6);self.assertEqual(report["training_feature_HTTP"],0)
                self.assertTrue((study/"train-sanity-completion-lock.json").exists())
            self.assertEqual(events[-1],"close")

    def test_worker_finishes_train_and_releases_int8_before_dev(self):self.exercise_mock_worker(False)
    def test_failed_train_stops_before_dev_and_cleans_without_retry(self):self.exercise_mock_worker(True)


if __name__ == "__main__": unittest.main(verbosity=2)
