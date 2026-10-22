"""Reconstruct actual loopback evidence and metrics without inference/network.

Written before outcome inspection. The output deliberately records both rejected
and selected DEV policies and never treats internal diagnostics as an official
rank. Re-running refuses to overwrite the first completed review.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(HERE))
from verify_epoch_v2 import paired_diagnostics, paired_bootstrap_interval, proper_scores

PLAN_SHA = "3e2c36366972d22568f41a341346c089798a454c94948883f95d7d6508a91e2f"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj


def normalized_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def scored(record, scorer, response=None):
    e = record["evaluation"]
    answer = (response if response is not None else record["response"])["answers"]["decision"]
    assert answer["type"] == e["type"]
    if e["type"] == "noul":
        p = {"yes": answer["noul"], "no": 1 - answer["noul"]}
    else:
        p = answer["probabilities"]
    task = SimpleNamespace(labels=e["labels"], expected=int(e["gold"]) if e["type"] == "score" else e["gold"], question={"type": e["type"]})
    out = scorer.score_task(p, task)
    assert out["strict_valid"] and out["valid"]
    return {"correct": bool(out["correct"]), "probabilities": out["probs"], **proper_scores(out["probs"], e["gold"], e["labels"])}


def aggregate(records, scorer, mode="candidate"):
    output = []
    for record in records:
        response = record["response"]
        if mode == "baseline": response = response["baseline104_response"]
        elif mode == "native":
            base = response.get("baseline104_response", response)
            answer = base["answers"]["decision"]["native_original_answer"]
            response = {"answers": {"decision": answer}}
        output.append(scored(record, scorer, response))
    return {"n": len(output), "correct": sum(x["correct"] for x in output), "brier": statistics.mean(x["brier"] for x in output), "nll": statistics.mean(x["nll"] for x in output), "strict_valid": len(output), "errors": 0}


def compare(summary, actual):
    for k in ("n", "correct", "strict_valid", "errors"): assert summary[k] == actual[k], k
    for k in ("brier", "nll"): assert math.isclose(summary[k], actual[k], rel_tol=0, abs_tol=1e-12), k


def verify_batch(phase, plan):
    directory = STUDY / "runs" / phase
    attempt, runtime, collection, cleanup = [load(directory / name) for name in ("attempt.json", "runtime.json", "collection.json", "cleanup.json")]
    actual, wire, server = [rows(directory / name) for name in ("records.jsonl", "wire.jsonl", "server-audit.jsonl")]
    inputs = rows(ROOT / plan["datasets"][phase])
    assert attempt["status"] == "COMPLETE" and attempt["exit_code"] == 0
    assert collection["status"] == "COMPLETE"
    assert len(actual) == len(wire) == len(server) == len(inputs) == collection["n"] == collection["expected"]
    assert sha(directory / "records.jsonl") == collection["records_sha256"]
    assert sha(directory / "wire.jsonl") == collection["wire_sha256"]
    for k, v in plan["expected_native_receipt"].items(): assert runtime["receipt"][k] == v
    assert runtime["native_child_pids"] and cleanup["native_child_pids_absent"]
    assert all(not Path(f"/proc/{pid}").exists() for pid in runtime["native_child_pids"])
    for expected, record, pair, event in zip(inputs, actual, wire, server):
        assert expected["id"] == record["id"] == pair["id"]
        assert expected["evaluation"] == record["evaluation"]
        assert expected["split"] == record["split"]
        assert normalized_sha(record["input"]) == expected["input_sha256"]
        request = json.loads(pair["request"])
        assert set(request) == {"state", "questions"} and request == record["input"]
        # Compare actual JSON rendering so dictionary order is preserved through
        # runtime and the saved offline feature inputs.
        assert json.dumps(request, ensure_ascii=False) == json.dumps(record["input"], ensure_ascii=False)
        assert pair["status"] == event["status"] == 200 and event["ok"]
        for side in ("request", "response"):
            digest = hashlib.sha256(pair[side].encode()).hexdigest()
            assert digest == pair[side + "_sha256"] == event[side + "_sha256"]
        assert json.loads(pair["response"]) == record["response"]
        assert event["usage"]["native_requests"] == record["response"]["usage"]["native_requests"] == 1
        assert math.isfinite(record["elapsed_s"]) and 0 <= record["elapsed_s"] <= plan["limits"]["seconds_per_decision"]
    return actual, runtime


def main():
    out = HERE / "actual-epoch-independent-v1.json"
    if out.exists(): raise ValueError("Completed audit already frozen")
    plan_path = STUDY / "plan.json"; assert sha(plan_path) == PLAN_SHA
    plan = load(plan_path)
    for pin in plan["pins"]: assert sha(ROOT / pin["path"]) == pin["sha256"]
    baseline, base_runtime = verify_batch("development", plan)
    scorer = module(STUDY / "benchmark/sources/jevbench_scoring.py", "independent_actual_scorer")
    head = module(STUDY / "candidate/head.py", "independent_actual_head_replay")
    baseline_summary = aggregate(baseline, scorer)
    compare(load(STUDY / "runs/baseline-metrics.json"), baseline_summary)
    assert baseline_summary["correct"] == 104
    native_baseline_summary = aggregate(baseline, scorer, "native")
    assert native_baseline_summary["correct"] == 77
    dev = [x for x in baseline if x["split"] == "dev"]
    trials = load(STUDY / "runs/trials.json")
    assert len(trials) == len(head.candidate_configs()) == 6
    accepted = []
    trial_proofs = []
    for t in trials:
        artifact_path = ROOT / t["artifact"]; assert sha(artifact_path) == t["artifact_sha256"]
        artifact = load(artifact_path); head.validate_artifact(artifact)
        assert artifact["config"] == t["config"]
        assert artifact["fit_counts"]["train"] == 106 and artifact["fit_counts"]["calibration"] == 34
        for role in ("train", "calibration"):
            assert set(artifact["fit_input_hashes"][role]) == {normalized_sha(x["input"]) for x in baseline if x["split"] == role}
        transformed = []
        for record in baseline:
            r = copy.deepcopy(record); r["response"] = head.transform(record["response"], record["input"]["state"], record["input"]["questions"], artifact); transformed.append(r)
        full = aggregate(transformed, scorer); compare(t["full_exposed_development_metrics"], full)
        paired = []
        for original, changed in zip(baseline, transformed):
            if original["split"] == "dev":
                e = original["evaluation"]
                paired.append({"id": original["id"], "gold": e["gold"], "labels": e["labels"], "baseline": scored(original, scorer), "candidate": scored(changed, scorer)})
        diag = paired_diagnostics(paired)
        compare(t["metrics"], {**diag["candidate"], "n": len(dev), "strict_valid": len(dev), "errors": 0})
        gate = diag["development_gate_passed"] and full["correct"] >= 104
        assert gate == t["dev_gate_passed"] and t["confirmation_used"] is False
        if gate: accepted.append(t)
        trial_proofs.append({"index": t["index"], "config": t["config"], "artifact_sha256": t["artifact_sha256"], "full_exposed_metrics": full, "paired_DEV": diag})
    result = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
        "plan_sha256": PLAN_SHA, "pins_verified": len(plan["pins"]), "native_baseline": native_baseline_summary,
        "frozen104_baseline": baseline_summary, "trials": trial_proofs, "official_score": None, "official_rank": None,
        "official_sota_established": False, "new_native_calls_by_auditor": 0, "new_paid_calls_by_auditor": 0}
    if accepted:
        selection = load(STUDY / "runs/selection.json"); lock = load(STUDY / "runs/confirmation-lock.json")
        best = min(accepted, key=lambda t: (t["metrics"]["brier"], t["metrics"]["nll"], -t["metrics"]["correct"]))
        assert selection["selected"] == best and not selection["confirmation_consumed_before_selection"]
        assert lock["artifact_sha256"] == best["artifact_sha256"] and lock["selection_sha256"] == sha(STUDY / "runs/selection.json")
        confirmation, runtime = verify_batch("confirmation", plan)
        attempt = load(STUDY / "runs/confirmation/attempt.json")
        assert selection["at"] <= lock["at"] <= attempt["at"]
        assert runtime["artifact_sha256"] == best["artifact_sha256"]
        candidate, control, native = [aggregate(confirmation, scorer, mode) for mode in ("candidate", "baseline", "native")]
        summary = load(STUDY / "runs/confirmation-comparison.json")
        compare(summary["candidate"], candidate); compare(summary["baseline"], control)
        differences = {"brier": [], "nll": [], "accuracy": []}
        for record in confirmation:
            c = scored(record, scorer); b = scored(record, scorer, record["response"]["baseline104_response"])
            for key in ("brier", "nll"): differences[key].append(b[key] - c[key])
            differences["accuracy"].append(int(c["correct"]) - int(b["correct"]))
        result["confirmation"] = {"n": len(confirmation), "selected": best["config"], "candidate": candidate,
            "same_native_call_baseline104": control, "native_only": native,
            "paired_uncertainty": {k: paired_bootstrap_interval(v) for k, v in differences.items()},
            "freshness_scope": "First known project use of small public easy48; not current canonical draw or publisher sealed set", "generalization_established": False}
    else:
        assert not (STUDY / "runs/confirmation-lock.json").exists()
        result["confirmation"] = {"consumed": False, "reason": "No DEV promotion"}
    evidence = []
    for p in sorted((STUDY / "runs").rglob("*")):
        if p.is_file(): evidence.append({"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)})
    result["actual_artifact_pins"] = evidence
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checks_passed": True, "path": str(out), "sha256": sha(out), "confirmation": result["confirmation"]}))


if __name__ == "__main__":
    main()
