"""Epoch2: reuse pinned actual DEV, test decision-preserving calibration on new LegalBench tasks.

Derived from the frozen epoch1 controller; prior code and outcomes remain immutable.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE_STUDY = Path(__file__).resolve().parent.parent
STUDY = SOURCE_STUDY / "epoch3" / "retry2"
sys.path.insert(0, str(SOURCE_STUDY))


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def inference_request(record, original_request_text=None):
    """Restore original nested insertion order before native state serialization."""
    original = json.loads(original_request_text) if original_request_text else record["input"]
    request = {"state": original["state"], "questions": original["questions"]}
    if encoded(request) != encoded(record["input"]):
        raise ValueError("Literal request and frozen semantic input disagree")
    # Canonical hashing is for identities; it must not reorder native inputs.
    body = json.dumps(request, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    return request, body


def checked_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Path outside project")
    return path


def verify_plan(plan):
    for item in plan["pins"]:
        path = checked_path(item["path"])
        if not path.is_file() or digest(path) != item["sha256"]:
            raise ValueError("Frozen identity changed: " + item["path"])
    if plan["limits"]["paid_calls"] != 0:
        raise ValueError("This controller has no paid execution route")
    if not 1 <= plan["limits"]["native_batches"] <= 6:
        raise ValueError("Native batch limit invalid")
    for key, maximum in (("threads", 2), ("seconds_per_batch", 600), ("seconds_per_decision", 30), ("candidate_configs", 6)):
        value = plan["limits"][key]
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError("Execution limit invalid: " + key)


def verify_collection(directory, plan):
    collected = load(directory / "collection.json")
    measured = rows(directory / "records.jsonl")
    wire = rows(directory / "wire.jsonl")
    audited = rows(directory / "server-audit.jsonl")
    if collected["status"] != "COMPLETE" or len(measured) != collected["expected"]:
        raise ValueError("Incomplete native measurement")
    if not len(measured) == len(wire) == len(audited) == collected["n"]:
        raise ValueError("Actual request counts disagree")
    runtime = load(directory / "runtime.json")
    for key, expected in plan["expected_native_receipt"].items():
        if runtime["receipt"].get(key) != expected:
            raise ValueError("Native runtime receipt mismatch: " + key)
    if digest(directory / "records.jsonl") != collected["records_sha256"] or digest(directory / "wire.jsonl") != collected["wire_sha256"]:
        raise ValueError("Collected bytes changed")
    for record, pair, audit in zip(measured, wire, audited):
        if record["id"] != pair["id"] or json.loads(pair["request"]) != record["input"]:
            raise ValueError("Request/input correspondence failed")
        if set(json.loads(pair["request"])) != {"state", "questions"}:
            raise ValueError("Non-inference fields in native request")
        if pair["status"] != 200 or not audit["ok"] or audit["status"] != 200:
            raise ValueError("Unsuccessful native request")
        for key in ("request", "response"):
            actual = hashlib.sha256(pair[key].encode()).hexdigest()
            if actual != pair[key + "_sha256"] or actual != audit[key + "_sha256"]:
                raise ValueError("Wire/audit hash mismatch")
        if json.loads(pair["response"]) != record["response"] or audit["usage"]["native_requests"] != 1:
            raise ValueError("Native output or invocation count mismatch")
    cleanup = load(directory / "cleanup.json")
    if not cleanup["native_child_pids_absent"] or any(Path(f"/proc/{pid}").exists() for pid in runtime["native_child_pids"]):
        raise ValueError("Native child cleanup not established")
    return measured


def begin_once(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def dominates(candidate, baseline, epsilon=1e-12):
    """Development gate, not confirmation or official rank evidence."""
    if candidate["n"] != baseline["n"] or candidate["errors"] or candidate["strict_valid"] != candidate["n"]:
        return False
    if candidate["correct"] < baseline["correct"]:
        return False
    brier_gain = baseline["brier"] - candidate["brier"]
    nll_gain = baseline["nll"] - candidate["nll"]
    return brier_gain >= -epsilon and nll_gain >= -epsilon and (brier_gain > epsilon or nll_gain > epsilon)


def score(records):
    module = importlib.import_module("benchmark.evaluate")
    result = module.score_records(records)
    # The benchmark worker owns normalization and scoring; reject missing evidence.
    for key in ("n", "correct", "accuracy", "brier", "nll", "strict_valid", "errors"):
        if key not in result:
            raise ValueError("Missing scorer result field: " + key)
    return result


def transform_records(records, artifact):
    transform = importlib.import_module("candidate.epoch2.head").transform
    output = []
    for record in records:
        transformed = copy.deepcopy(record)
        transformed["response"] = transform(copy.deepcopy(record["response"]), record["input"]["state"], record["input"]["questions"], artifact)
        output.append(transformed)
    return output


def collect_worker(plan_path, phase, artifact_path, expected_plan_sha):
    """One native process, real loopback HTTP; evaluation fields never enter requests."""
    if not expected_plan_sha or digest(plan_path) != expected_plan_sha:
        raise ValueError("Worker plan identity mismatch")
    plan = load(plan_path)
    verify_plan(plan)
    runtime = importlib.import_module("candidate.epoch3.runtime")
    sys.path.insert(0, str(ROOT / "experiments/swarm/jevbench-adapter"))
    server = importlib.import_module("server")
    directory = STUDY / "runs" / phase
    input_path = checked_path(plan["datasets"][phase])
    records = rows(input_path)
    order_map = {}
    if phase in plan.get("request_order_sources", {}):
        entries = rows(checked_path(plan["request_order_sources"][phase]))
        order_map = {entry["id"]: entry["request_body_utf8"] for entry in entries}
        if len(order_map) != len(entries) or set(order_map) != {record["id"] for record in records}:
            raise ValueError("Request ordering evidence is incomplete")
    engine = None
    httpd = None
    thread = None
    started = time.perf_counter()
    completed = 0
    native_pids = []
    try:
        os.environ["RUVECTOR_SOTA_BUNDLE_DIR"] = str(directory / "bundles")
        engine = runtime.CandidateEngine(artifact_path=artifact_path)
        engine_receipt = copy.deepcopy(engine.receipt)
        # Record descendants via actual parent PID; do not invent a binary execution proof.
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                for line in (proc / "status").read_text().splitlines():
                    if line.startswith("PPid:") and int(line.split()[1]) == os.getpid():
                        native_pids.append(int(proc.name))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                pass
        httpd = server.make_server(engine, "127.0.0.1", 0, directory / "server-audit.jsonl")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        save(directory / "runtime.json", {"at": now(), "pid": os.getpid(), "native_child_pids": native_pids,
             "receipt": engine_receipt, "input_path": str(input_path.relative_to(ROOT)), "input_sha256": digest(input_path),
             "artifact_path": str(artifact_path) if artifact_path else None,
             "artifact_sha256": digest(artifact_path) if artifact_path else None,
             "endpoint": f"http://127.0.0.1:{httpd.server_port}/v1/systemone"})
        with (directory / "records.jsonl").open("x") as out, (directory / "wire.jsonl").open("x") as wire:
            for record in records:
                request, body = inference_request(record, order_map.get(record["id"]))
                connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=plan["limits"]["seconds_per_decision"])
                t0 = time.perf_counter()
                try:
                    connection.request("POST", "/v1/systemone", body=body, headers={"Content-Type": "application/json"})
                    reply = connection.getresponse()
                    raw = reply.read()
                    elapsed = time.perf_counter() - t0
                    wire.write(json.dumps({"id": record["id"], "request": body.decode(), "response": raw.decode(),
                        "request_sha256": hashlib.sha256(body).hexdigest(), "response_sha256": hashlib.sha256(raw).hexdigest(),
                        "status": reply.status, "elapsed_s": elapsed}, ensure_ascii=False) + "\n")
                    wire.flush()
                    if reply.status != 200:
                        raise RuntimeError("HTTP prediction failed: " + str(reply.status))
                    response = json.loads(raw)
                finally:
                    connection.close()
                result = {**record, "input": request, "response": response, "elapsed_s": elapsed}
                out.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
                out.flush()
                completed += 1
                if completed % 10 == 0:
                    save(directory / "progress.json", {"at": now(), "completed": completed, "total": len(records), "native_http": True})
        save(directory / "collection.json", {"status": "COMPLETE", "at": now(), "n": completed, "expected": len(records),
             "records_sha256": digest(directory / "records.jsonl"), "wire_sha256": digest(directory / "wire.jsonl"),
             "elapsed_s": time.perf_counter() - started, "measured_kind": "native engine through actual loopback HTTP"})
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        if thread is not None:
            thread.join(timeout=3)
        if engine is not None:
            engine.close()
        save(directory / "cleanup.json", {"at": now(), "engine_close_called": engine is not None, "completed": completed,
             "native_child_pids": native_pids,
             "native_child_pids_absent": all(not Path(f"/proc/{pid}").exists() for pid in native_pids)})


class Controller:
    def __init__(self, plan_path):
        self.plan_path = Path(plan_path).resolve()
        self.plan = load(self.plan_path)
        self.initial_plan_sha = digest(self.plan_path)
        verify_plan(self.plan)
        self.status = {"schema_version": 1, "started_at": now(), "controller_pid": os.getpid(), "controller_active": True, "state": "STARTING",
                       "official_rank": None, "official_sota_established": False, "native_batches_started": 0,
                       "plan_sha256": digest(self.plan_path), "events": []}

    def checkpoint(self, state, **details):
        event = {"at": now(), "state": state, **details}
        self.status.update(event)
        self.status["events"].append(event)
        save(STUDY / "status.json", self.status)

    def native_batch(self, phase, artifact_path=None):
        if digest(self.plan_path) != self.initial_plan_sha:
            raise ValueError("Parent plan identity changed")
        verify_plan(self.plan)
        if self.status["native_batches_started"] >= self.plan["limits"]["native_batches"]:
            raise RuntimeError("Native batch budget exhausted")
        directory = STUDY / "runs" / phase
        directory.mkdir(exist_ok=False)
        self.status["native_batches_started"] += 1
        attempt = {"at": now(), "phase": phase, "status": "STARTED", "automatic_retry": False,
                   "input_sha256": digest(checked_path(self.plan["datasets"][phase])),
                   "artifact_sha256": digest(artifact_path) if artifact_path else None}
        begin_once(directory / "attempt.json", attempt)
        self.checkpoint("NATIVE_" + phase.upper())
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--plan", str(self.plan_path), "--collect-worker", phase,
                   "--expected-plan-sha", self.initial_plan_sha]
        if artifact_path:
            command.extend(["--artifact", str(artifact_path)])
        env = dict(os.environ)
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            env[key] = str(self.plan["limits"]["threads"])
        with (directory / "worker.log").open("x") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=lambda: os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2]))
            save(directory / "process.json", {"pid": process.pid, "pgid": process.pid, "started_at": now()})
            try:
                exit_code = process.wait(timeout=min(self.plan["limits"]["seconds_per_batch"], max(1, self.plan["lease_expires_unix"] - time.time() - 30)))
            except BaseException as error:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                attempt.update(status="FAILED", finished_at=now(), exit_code=process.returncode,
                               error=type(error).__name__ + ": " + str(error))
                save(directory / "attempt.json", attempt)
                raise
        # Close any leaked group descendant even when the worker exits normally.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        attempt.update(status="COMPLETE" if exit_code == 0 else "FAILED", finished_at=now(), exit_code=exit_code)
        save(directory / "attempt.json", attempt)
        if exit_code:
            raise RuntimeError("Native batch failed; evidence preserved at " + str(directory))
        return verify_collection(directory, self.plan)

    def run(self):
        begin_once(STUDY / "controller" / "launch.json", {"at": now(), "pid": os.getpid(), "plan_sha256": digest(self.plan_path)})
        def arms(records):
            outputs={"ruvector_top2":records}
            for name in ("native104_on_ruvector_evidence", "same_nli_lexical_top2", "same_nli_positional_first2"):
                selected=[]
                for record in records:
                    response=record["response"]
                    other=response["baseline104_response"] if name=="native104_on_ruvector_evidence" else response["ablation_responses"][name]
                    selected.append({**record,"response":other})
                outputs[name]=selected
            return {name:score(values) for name,values in outputs.items()}
        try:
            development=self.native_batch("development")
            metrics=arms(development)
            primary=metrics["ruvector_top2"]
            comparisons={name:{"accuracy_nondecrease":primary["correct"]>=base["correct"],
                              "brier_nonincrease":primary["brier"]<=base["brier"]+1e-12,
                              "nll_nonincrease":primary["nll"]<=base["nll"]+1e-12}
                         for name,base in metrics.items() if name!="ruvector_top2"}
            good=all(value["errors"]==0 and value["strict_valid"]==value["n"] for value in metrics.values()) and all(all(values.values()) for values in comparisons.values())
            good=good and all(primary["brier"]<metrics[name]["brier"]-1e-12 or primary["nll"]<metrics[name]["nll"]-1e-12
                              for name in ("same_nli_lexical_top2","same_nli_positional_first2"))
            save(STUDY/"runs"/"development-comparison.json",{"at":now(),"metrics":metrics,"comparisons":comparisons,
                 "frozen_development_gate_passed":good,"scope":"OriginalContractNLItrain24grouped8doc publicDEV; notcurrentJevBench/fullLegalBench"})
            self.checkpoint("DEV_GATE_PASSED_BUDGET_EXHAUSTED" if good else "RESEARCH_NEEDED_DEV_GATE_FAILED", metrics=metrics,
                            frozen_development_gate_passed=good, confirmation_consumed=False,
                            reason="Failed initial request plus this DEV batch exhaust epoch two-attempt budget. Confirmation96 remains unused; no promotion or submission.")
            return
        except BaseException as error:
            self.checkpoint("STOPPED_WITH_PRESERVED_EVIDENCE",error=type(error).__name__+": "+str(error))
            raise
        finally:
            self.status["controller_active"]=False;self.status["finished_at"]=now()
            save(STUDY/"status.json",self.status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--collect-worker", choices=("development",))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--expected-plan-sha")
    args = parser.parse_args()
    if args.collect_worker:
        collect_worker(args.plan, args.collect_worker, args.artifact, args.expected_plan_sha)
    else:
        Controller(args.plan).run()


if __name__ == "__main__":
    main()
