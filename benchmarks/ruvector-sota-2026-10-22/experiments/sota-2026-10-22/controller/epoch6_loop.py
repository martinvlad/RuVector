"""One native corpus batch: frozen fresh DEV, then gated unused confirmation.

The original six-attempt and epoch5 one-attempt studies remain closed. This new context study
allows one composite corpus attempt, with a shared deadline and no native retry.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import http.client
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent
STUDY = SOURCE / "epoch6"
RUN = STUDY / "runs" / "composite"
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location("reviewed_epoch3_primitives", HERE / "epoch3_loop.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
ARMS = ("ruvector_top2", "native104_on_ruvector_evidence", "same_nli_lexical_top2", "same_nli_positional_first2")


def now():
    return datetime.now(timezone.utc).isoformat()


def require_plan(path, expected=None):
    if expected and T.digest(path) != expected:
        raise ValueError("Plan bytes changed")
    plan = T.load(path)
    T.verify_plan(plan)
    if (plan["limits"]["native_batches"] != 1 or plan["prior_closed_study_native_attempts"] != 7 or
            plan["prior_closed_original_study_attempts"] != 6 or plan["prior_closed_epoch5_study_attempts"] != 1 or
            plan["study_id"] != "native-coherent-context-deberta-base-e6" or
            plan["new_study_native_attempt_cap"] != 1 or plan["new_study_native_attempts_before"] != 0):
        raise ValueError("Separate frozen study or prior closed ledger changed")
    if set(plan["datasets"]) != {"development", "confirmation"}:
        raise ValueError("Unexpected inference corpus")
    if plan["train"] != "none" or plan["calibration"] != "none":
        raise ValueError("No unbudgeted fitting or calibration")
    if (plan["limits"]["threads"] != 2 or plan["limits"]["paid_calls"] != 0 or
            plan["limits"]["GPU_calls"] != 0 or not 0 < plan["limits"]["seconds_per_batch"] <= 600):
        raise ValueError("Resource budget changed")
    if not {"experiments/sota-2026-10-22/benchmark/evaluate.py", "experiments/sota-2026-10-22/benchmark/sources/jevbench_scoring.py", "experiments/sota-2026-10-22/benchmark/source-manifest.json", "experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py"}.issubset({p["path"] for p in plan["pins"]}):
        raise ValueError("Direct evaluator/scorer pins required")
    return plan


def score_arms(records):
    result = {}
    for name in ARMS:
        selected = []
        for rec in records:
            response = rec["response"]
            if name == "native104_on_ruvector_evidence":
                response = response["baseline104_response"]
            elif name != "ruvector_top2":
                response = response["ablation_responses"][name]
            selected.append({**rec, "response": response})
        result[name] = T.score(selected)
    return result


def development_gate(metrics):
    if set(metrics) != set(ARMS):
        return False, {"invalid": "Missing or unexpected control"}
    for x in metrics.values():
        if (x["n"] != 24 or not 0 <= x["correct"] <= 24 or
                not all(isinstance(x[k], (int, float)) and math.isfinite(x[k]) for k in ("brier", "nll"))):
            return False, {"invalid": "Wrong DEV count or nonfinite loss"}
    primary = metrics["ruvector_top2"]
    valid = all(x["errors"] == 0 and x["strict_valid"] == x["n"] == primary["n"] for x in metrics.values())
    comparisons = {
        name: {"accuracy_nondecrease": primary["correct"] >= x["correct"],
               "brier_nonincrease": primary["brier"] <= x["brier"] + 1e-12,
               "nll_nonincrease": primary["nll"] <= x["nll"] + 1e-12}
        for name, x in metrics.items() if name != "ruvector_top2"
    }
    strict = all(primary["brier"] < metrics[name]["brier"] - 1e-12 or primary["nll"] < metrics[name]["nll"] - 1e-12
                 for name in ("same_nli_lexical_top2", "same_nli_positional_first2"))
    return valid and strict and all(all(x.values()) for x in comparisons.values()), comparisons


def measured_resources():
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"worker_cpu_user_seconds": own.ru_utime, "worker_cpu_system_seconds": own.ru_stime,
            "worker_peak_RSS_bytes": own.ru_maxrss * 1024,
            "terminated_children_cpu_user_seconds": children.ru_utime,
            "terminated_children_cpu_system_seconds": children.ru_stime,
            "largest_terminated_child_peak_RSS_bytes": children.ru_maxrss * 1024,
            "peak_memory_scope": "Linux getrusage process high-water marks; child maximum is not sum or simultaneous total memory",
            "allowed_CPU_ids": sorted(os.sched_getaffinity(0)), "configured_ORT_threads": 2}


def owned_group_members(pgid):
    members = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid and fields[0] not in ("Z", "X"):
                members.append(int(path.name))
        except (OSError, ValueError, IndexError):
            pass
    return sorted(members)


def close_owned_group(pgid):
    if pgid <= 1 or pgid == os.getpgrp():
        raise ValueError("Refuse cleanup outside owned worker process group")
    proof = {"pgid": pgid, "live_members_before": owned_group_members(pgid), "signals": []}
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not owned_group_members(pgid):
            break
        try:
            os.killpg(pgid, sig)
            proof["signals"].append(sig.name)
        except ProcessLookupError:
            pass
        until = time.monotonic() + 2
        while owned_group_members(pgid) and time.monotonic() < until:
            time.sleep(.05)
    proof["live_members_after"] = owned_group_members(pgid)
    return proof


def worker(plan_path, expected_sha, deadline):
    plan = require_plan(plan_path, expected_sha)
    sys.path.insert(0, str(ROOT / "experiments/swarm/jevbench-adapter"))
    server = importlib.import_module("server")
    runtime = importlib.import_module("candidate.epoch6.runtime")
    engine = None
    httpd = None
    thread = None
    pids = []
    report = {"started_at": now(), "status": "STARTING", "native_corpus_batches": 1,
              "development_completed": 0, "confirmation_completed": 0,
              "official_score": None, "official_rank": None, "champion_promoted": False}
    os.environ["RUVECTOR_SOTA_BUNDLE_DIR"] = str(RUN / "bundles")
    phase_records = {"development": [], "confirmation": []}
    try:
        engine = runtime.CandidateEngine()
        pids = [engine.native_pid]
        for key, expected in plan["expected_native_receipt"].items():
            if engine.receipt.get(key) != expected:
                raise ValueError("Actual native runtime receipt mismatch: " + key)
        if engine.receipt["nli"]["revision"] != plan["expected_nli_revision"] or engine.receipt["nli"]["model_sha256"] != plan["expected_nli_sha256"]:
            raise ValueError("Actual stronger NLI receipt mismatch")
        httpd = server.make_server(engine, "127.0.0.1", 0, RUN / "server-audit.jsonl")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        T.save(RUN / "runtime.json", {"at": now(), "pid": os.getpid(), "native_child_pids": pids,
               "receipt": copy.deepcopy(engine.receipt), "model_initialization_in_batch": True,
               "deadline_unix": deadline, "initial_resources": measured_resources()})
        report["status"] = "DEVELOPMENT"
        T.save(RUN / "report.json", report)
        with (RUN / "records.jsonl").open("x") as out, (RUN / "wire.jsonl").open("x") as wire, (RUN / "started-requests.jsonl").open("x") as started:
            for phase in ("development", "confirmation"):
                if phase == "confirmation":
                    dev = score_arms(phase_records["development"])
                    passed, comparisons = development_gate(dev)
                    T.save(RUN / "development-comparison.json", {"at": now(), "metrics": dev, "comparisons": comparisons,
                           "frozen_development_gate_passed": passed, "scope": "Fresh original ContractNLI train8document/24query DEV diagnostic; no official score"})
                    report["development_gate_passed"] = passed
                    if not passed:
                        report.update(status="REJECTED_DEV_GATE", confirmation_status="NOT_MODEL_CONSUMED")
                        break
                    T.begin_once(RUN / "confirmation-selection-lock.json", {"at": now(), "plan_sha256": expected_sha,
                                 "development_comparison_sha256": T.digest(RUN / "development-comparison.json"),
                                 "candidate": "Single frozen stronger-decoder source; no grid or fitting",
                                 "shared_deadline_unix": deadline})
                    report.update(status="CONFIRMATION", confirmation_status="CONSUMPTION_STARTING")
                    T.save(RUN / "report.json", report)
                phase_inputs = T.rows(T.checked_path(plan["datasets"][phase]))
                if len(phase_inputs) != {"development": 24, "confirmation": 96}[phase] or len({record["id"] for record in phase_inputs}) != len(phase_inputs):
                    raise ValueError("Frozen corpus count/identity uniqueness mismatch")
                for record in phase_inputs:
                    if time.time() >= deadline - 2:
                        raise TimeoutError("Shared one-batch deadline reached")
                    request, body = T.inference_request(record)
                    request_sha = hashlib.sha256(body).hexdigest()
                    started.write(json.dumps({"at": now(), "id": record["id"], "phase": phase,
                                  "request_sha256": request_sha, "request": body.decode()}, ensure_ascii=False) + "\n")
                    started.flush()
                    os.fsync(started.fileno())
                    connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port,
                                  timeout=min(plan["limits"]["seconds_per_decision"], max(.1, deadline - time.time())))
                    before = time.perf_counter()
                    try:
                        connection.request("POST", "/v1/systemone", body=body, headers={"Content-Type": "application/json"})
                        reply = connection.getresponse()
                        raw = reply.read()
                        elapsed = time.perf_counter() - before
                        wire.write(json.dumps({"id": record["id"], "phase": phase, "request": body.decode(),
                                   "response": raw.decode(), "request_sha256": request_sha,
                                   "response_sha256": hashlib.sha256(raw).hexdigest(), "status": reply.status,
                                   "elapsed_s": elapsed}, ensure_ascii=False) + "\n")
                        wire.flush()
                        if reply.status != 200:
                            raise RuntimeError("HTTP prediction failed: " + str(reply.status))
                        response = json.loads(raw)
                    finally:
                        connection.close()
                    measured = {**record, "input": request, "response": response, "elapsed_s": elapsed, "measured_phase": phase}
                    out.write(json.dumps(measured, ensure_ascii=False, allow_nan=False) + "\n")
                    out.flush()
                    phase_records[phase].append(measured)
                    report[phase + "_completed"] += 1
                    T.save(RUN / "progress.json", {"at": now(), "phase": phase, "development_completed": report["development_completed"],
                           "confirmation_completed": report["confirmation_completed"], "resources": measured_resources()})
                if phase == "confirmation":
                    metrics = score_arms(phase_records[phase])
                    T.save(RUN / "confirmation-comparison.json", {"at": now(), "metrics": metrics,
                           "scope": "Original public ContractNLI officialdev32doc/96query binary adaptation; not official full LegalBench/JevBench/ClaimBench",
                           "independent_document_group_uncertainty_review_required": True,
                           "official_score": None, "official_rank": None})
                    report.update(status="CONFIRMATION_COMPLETE_AWAITING_INDEPENDENT_REVIEW", confirmation_status="USED_NOW_EXPOSED_DEV")
        report.update(records_sha256=T.digest(RUN / "records.jsonl"), wire_sha256=T.digest(RUN / "wire.jsonl"), finished_at=now())
    except BaseException as error:
        report.update(status="FAILED_PRESERVED_EVIDENCE", error=type(error).__name__ + ": " + str(error), finished_at=now())
        raise
    finally:
        cleanup_errors = []
        for action in ([httpd.shutdown, httpd.server_close] if httpd is not None else []) + ([lambda: thread.join(timeout=3)] if thread is not None else []) + ([engine.close] if engine is not None else []):
            try:
                action()
            except BaseException as exc:
                cleanup_errors.append(type(exc).__name__ + ": " + str(exc))
        if engine is not None:
            try:
                T.save(RUN / "final-engine.json", {"at": now(), "receipt_after_close": copy.deepcopy(engine.receipt),
                       "execution_after_close": engine.execution_snapshot()})
            except BaseException as exc:
                cleanup_errors.append("final engine evidence: " + type(exc).__name__ + ": " + str(exc))
        if cleanup_errors:
            report.update(status="FAILED_CLEANUP_PRESERVED_EVIDENCE", cleanup_errors=cleanup_errors)
        try:
            T.save(RUN / "resources.json", {"at": now(), **measured_resources(),
                   "whole_pipeline": "All matched NLI arms + native104 evidence reader + evidence embedding/index; primary-only deployment cost not measured"})
        finally:
            try:
                T.save(RUN / "cleanup.json", {"at": now(), "engine_close_called": engine is not None,
                       "cleanup_errors": cleanup_errors, "native_child_pids": pids,
                       "native_child_pids_absent": all(not Path(f"/proc/{pid}").exists() for pid in pids)})
            finally:
                T.save(RUN / "report.json", report)
        if cleanup_errors:
            raise RuntimeError("Cleanup errors retained; parent will close owned process group")


def parent(plan_path):
    plan = require_plan(plan_path)
    plan_sha = T.digest(plan_path)
    # Directory setup and all source verification precede the exclusive launch.
    RUN.mkdir(parents=True, exist_ok=False)
    T.begin_once(STUDY / "launch.json", {"at": now(), "plan_sha256": plan_sha,
                 "state": "PREPARED_RESERVATION_NOT_ACTUAL_START", "study_id": plan["study_id"], "new_study_native_attempt": 1, "lifetime_native_attempt": 8,
                 "automatic_retry": False, "prior_closed_study_native_attempts": 7})
    env = dict(os.environ)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "2"
    env["TOKENIZERS_PARALLELISM"] = "false"
    deadline = min(time.time() + plan["limits"]["seconds_per_batch"], plan["lease_expires_unix"] - 30)
    if deadline <= time.time() + 60:
        raise RuntimeError("Insufficient remaining exclusive lease")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--plan", str(plan_path),
               "--worker", "--expected-plan-sha", plan_sha, "--deadline", str(deadline)]
    before = time.perf_counter()
    with (RUN / "worker.log").open("x") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                  start_new_session=True, preexec_fn=lambda: os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2]))
        T.save(RUN / "attempt.json", {"at": now(), "pid": process.pid, "pgid": process.pid,
               "status": "STARTED", "study_id": plan["study_id"], "new_study_native_attempt": 1,
               "lifetime_native_attempt": 8, "epoch_native_attempts": 1,
               "deadline_unix": deadline, "shared_DEV_and_confirmation_deadline": True,
               "automatic_retry": False, "source_plan_sha256": plan_sha})
        error = None
        try:
            exit_code = process.wait(timeout=max(1, deadline - time.time()))
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            exit_code = process.returncode
        finally:
            group_cleanup = close_owned_group(process.pid)
    T.save(RUN / "completion.json", {"at": now(), "exit_code": exit_code, "error": error,
           "wall_seconds_including_model_load": time.perf_counter() - before,
           "source_plan_unchanged": T.digest(plan_path) == plan_sha, "native_attempts": 1,
           "prior_study_native_attempts_used": 7, "original_study_native_attempts_used": 6, "epoch5_study_native_attempts_used": 1, "prior_study_attempts_remaining": 0,
           "new_study_native_attempts_used": 1, "new_study_attempts_remaining": 0, "lifetime_native_attempts_used": 8,
           "owned_group_cleanup": group_cleanup,
           "new_paid_calls": 0, "new_GPU_calls": 0, "official_score": None, "official_rank": None})
    if exit_code or error or group_cleanup["live_members_after"]:
        raise RuntimeError("Sole native attempt failed; preserved evidence; never rerun automatically")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--expected-plan-sha")
    parser.add_argument("--deadline", type=float)
    args = parser.parse_args()
    if args.worker:
        if not args.expected_plan_sha or not args.deadline:
            raise ValueError("Worker requires frozen plan and shared deadline")
        worker(args.plan, args.expected_plan_sha, args.deadline)
    else:
        parent(args.plan)


if __name__ == "__main__":
    main()
