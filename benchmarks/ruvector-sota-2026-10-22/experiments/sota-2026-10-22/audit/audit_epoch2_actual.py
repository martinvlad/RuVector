"""Independent epoch2 receipts, decision invariance and proper-score replay.

Designed before this auditor inspects actual epoch2 outcomes. No native/network
calls. The 96-item adapted LegalBench transfer diagnostic is not an official
full LegalBench score or JevBench Capability result.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(HERE))
from verify_epoch_v2 import paired_diagnostics, paired_bootstrap_interval


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def main():
    out = HERE / "epoch2-actual-independent-v1.json"
    if out.exists(): raise ValueError("Completed review is immutable")
    plan_path = STUDY / "epoch2/plan.json"
    assert sha(plan_path) == "d6dcb07ffa077f0097703e23e52a21721f685cfb15c44a5cecbeb57893ac3ab5"
    plan = load(plan_path)
    for pin in plan["pins"]: assert sha(ROOT / pin["path"]) == pin["sha256"]
    first = module(HERE / "audit_actual_epoch.py", "previous_independent_actual_helpers")
    previous = load(STUDY / "plan.json")
    baseline, _ = first.verify_batch("development", previous)
    scorer = first.module(STUDY / "benchmark/sources/jevbench_scoring.py", "independent_epoch2_pinned_scorer")
    head = first.module(STUDY / "candidate/epoch2/head.py", "independent_epoch2_frozen_head")
    baseline_summary = first.aggregate(baseline, scorer)
    trials = load(STUDY / "epoch2/runs/trials.json")
    assert len(trials) == len(head.candidate_configs()) == 2
    accepted = []; trial_proofs = []
    for trial in trials:
        path = ROOT / trial["artifact"]; assert sha(path) == trial["artifact_sha256"]
        artifact = load(path); head.validate_artifact(artifact)
        assert artifact["config"] == trial["config"]
        assert artifact["fit_counts"] == {"train": 106, "calibration": 34}
        for role in ("train", "calibration"):
            assert set(artifact["fit_input_hashes"][role]) == {first.normalized_sha(x["input"]) for x in baseline if x["split"] == role}
        transformed = []
        pairs = []
        for old in baseline:
            r = copy.deepcopy(old); r["response"] = head.transform(old["response"], old["input"]["state"], old["input"]["questions"], artifact)
            a = first.scored(old, scorer); b = first.scored(r, scorer)
            assert a["correct"] == b["correct"]
            assert sorted(a["probabilities"], key=lambda k: (-a["probabilities"][k], k))[0] == sorted(b["probabilities"], key=lambda k: (-b["probabilities"][k], k))[0]
            if old["evaluation"]["type"] == "score": assert old["response"]["answers"]["decision"] == r["response"]["answers"]["decision"]
            if old["split"] == "dev":
                pairs.append({"id": old["id"], "gold": old["evaluation"]["gold"], "labels": old["evaluation"]["labels"], "baseline": a, "candidate": b})
            transformed.append(r)
        full = first.aggregate(transformed, scorer); first.compare(trial["full_exposed_development_metrics"], full)
        assert full["correct"] == baseline_summary["correct"] == 104
        diagnostics = paired_diagnostics(pairs)
        first.compare(trial["metrics"], {**diagnostics["candidate"], "n": 43, "strict_valid": 43, "errors": 0})
        assert trial["dev_gate_passed"] == diagnostics["development_gate_passed"]
        if trial["dev_gate_passed"]: accepted.append(trial)
        trial_proofs.append({"config": trial["config"], "artifact_sha256": trial["artifact_sha256"], "full_exposed": full, "paired_DEV": diagnostics})
    proof = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
        "plan_sha256": sha(plan_path), "source_pins_verified": len(plan["pins"]), "trials": trial_proofs,
        "baseline104_public183": baseline_summary, "all_public183_decisions_preserved_for_both_configs": True,
        "official_score": None, "official_rank": None, "official_sota_established": False, "native_calls_by_auditor": 0, "paid_calls_by_auditor": 0}
    if accepted:
        best = min(accepted, key=lambda x: (x["metrics"]["brier"], x["metrics"]["nll"], -x["metrics"]["correct"]))
        selection = load(STUDY / "epoch2/runs/selection.json"); lock = load(STUDY / "epoch2/runs/confirmation-lock.json")
        assert selection["selected"] == best
        assert lock["selection_sha256"] == sha(STUDY / "epoch2/runs/selection.json") and lock["artifact_sha256"] == best["artifact_sha256"]
        first.STUDY = STUDY / "epoch2"
        transfer, runtime = first.verify_batch("confirmation", plan)
        attempt = load(STUDY / "epoch2/runs/confirmation/attempt.json")
        assert selection["at"] <= lock["at"] <= attempt["at"]
        assert runtime["artifact_sha256"] == best["artifact_sha256"]
        assert len(transfer) == 96
        summary = load(STUDY / "epoch2/runs/confirmation-comparison.json")
        candidate, baseline, native = [first.aggregate(transfer, scorer, x) for x in ("candidate", "baseline", "native")]
        first.compare(summary["candidate"], candidate); first.compare(summary["baseline"], baseline)
        differences = {"accuracy": [], "brier": [], "nll": []}
        pairs = []; per_task = {}
        artifact = load(ROOT / best["artifact"])
        for record in transfer:
            response = record["response"]
            replay = head.transform(response["baseline104_response"], record["input"]["state"], record["input"]["questions"], artifact)
            assert replay["answers"] == response["answers"]
            c = first.scored(record, scorer); b = first.scored(record, scorer, response["baseline104_response"])
            assert c["correct"] == b["correct"]
            winner = lambda p: sorted(p, key=lambda k: (-p[k], k))[0]
            assert winner(c["probabilities"]) == winner(b["probabilities"])
            differences["accuracy"].append(int(c["correct"]) - int(b["correct"]))
            for key in ("brier", "nll"): differences[key].append(b[key] - c[key])
            pairs.append({"id": record["id"], "gold": record["evaluation"]["gold"], "labels": record["evaluation"]["labels"], "baseline": b, "candidate": c})
            per_task.setdefault(record["evaluation"]["source_family"], []).append(record)
        paired = paired_diagnostics(pairs)
        assert paired["development_gate_passed"] == summary["confirmation_gate_diagnostic_only"]
        uncertainty = {k: paired_bootstrap_interval(v) for k, v in differences.items()}
        proof["transfer96"] = {"selected": best["config"], "candidate": candidate, "same_native_call_baseline104": baseline,
            "native_only": native, "decisions_preserved_all96": True, "paired": paired, "paired_uncertainty": uncertainty,
            "per_task": {k: {"candidate": first.aggregate(v, scorer), "baseline": first.aggregate(v, scorer, "baseline")} for k, v in per_task.items()},
            "empirical_transfer_promotion_gate_passed": paired["development_gate_passed"],
            "both_proper_score_ci_lower_bounds_positive": all(uncertainty[k]["ci95"][0] > 0 for k in ("brier", "nll")),
            "scope": "96-question four-task zero-shot adaptation; public heldout project transfer diagnostic, not official full LegalBench/JevBench score"}
    else:
        assert not (STUDY / "epoch2/runs/confirmation-lock.json").exists()
        proof["transfer96"] = {"consumed": False, "reason": "No DEV candidate met preregistered gate"}
    proof["actual_artifact_pins"] = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted((STUDY / "epoch2/runs").rglob("*")) if p.is_file()]
    out.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"path": str(out), "sha256": sha(out), "checks_passed": True, "transfer96": proof["transfer96"]}))


if __name__ == "__main__": main()
