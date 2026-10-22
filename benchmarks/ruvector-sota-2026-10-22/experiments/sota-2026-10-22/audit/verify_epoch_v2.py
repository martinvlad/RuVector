"""Independent, fail-closed artifact and empirical calibration checks.

This verifier makes no native, network, or paid calls. An internal diagnostic
cannot satisfy the official gate, including when its numerical score exceeds a
published leader. All per-label Brier/NLL values here are empirical diagnostics,
not the official JevBench Calibration axis. Distribution sum tolerance 1e-3
matches the pinned upstream strict scorer; raw accepted values are not rescaled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_input_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_pins(pins, root):
    root = Path(root).resolve()
    checked = []
    for pin in pins:
        p = Path(pin["path"])
        original = root / p if not p.is_absolute() else p
        p = original.resolve()
        if not p.is_relative_to(root) or any(x.is_symlink() for x in (original, *original.parents)) or not p.is_file():
            raise ValueError("Pinned file is not an ordinary project file")
        actual = sha256(p)
        if actual != pin["sha256"]:
            raise ValueError("Pinned bytes changed: " + str(p))
        checked.append({"path": str(p.relative_to(root)), "sha256": actual})
    return checked


def check_distribution(probabilities, labels):
    if set(probabilities) != set(labels) or not labels:
        raise ValueError("Distribution labels do not match question labels")
    values = list(probabilities.values())
    if not all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in values):
        raise ValueError("Nonfinite, nonnumeric, or out-of-range probability")
    if abs(sum(values) - 1) > 1e-3:
        raise ValueError("Distribution does not sum to one")


def proper_scores(probabilities, gold, labels):
    check_distribution(probabilities, labels)
    if gold not in labels:
        raise ValueError("Gold is outside the declared label set")
    return {
        "brier": sum((probabilities[label] - float(label == gold)) ** 2 for label in labels),
        "nll": -math.log(max(probabilities[gold], 1e-15)),
    }


def check_split_isolation(records, group_key="source_group"):
    """Check row IDs, normalized inputs and source groups across declared roles."""
    ids, inputs, groups = {}, {}, {}
    role_counts = {}
    for record in records:
        role = record["split"]
        if role not in {"train", "dev", "calibration", "confirmation", "diagnostic"}:
            raise ValueError("Unknown data role")
        identity = record["id"]
        if identity in ids:
            raise ValueError("Repeated dataset ID")
        ids[identity] = role
        digest = canonical_input_hash(record["input"])
        if record.get("input_sha256") != digest:
            raise ValueError("Normalized input hash mismatch")
        if digest in inputs and inputs[digest] != role:
            raise ValueError("Normalized input crosses data roles")
        inputs[digest] = role
        group = record.get(group_key)
        if group is None:
            raise ValueError("Missing source group")
        if group in groups and groups[group] != role:
            raise ValueError("Source group crosses data roles")
        groups[group] = role
        if role == "confirmation" and record.get("previously_loop_used") is not False:
            raise ValueError("Confirmation freshness missing or data previously used")
        role_counts[role] = role_counts.get(role, 0) + 1
    return {"roles": role_counts, "rows": len(ids), "input_identities": len(inputs), "groups": len(groups)}


def paired_diagnostics(rows):
    """Rows contain pinned evaluator correctness; no argmax proxy for typed score."""
    seen = set()
    results = []
    for row in rows:
        if row["id"] in seen:
            raise ValueError("Duplicate prediction ID")
        seen.add(row["id"])
        values = {"id": row["id"]}
        for name in ("baseline", "candidate"):
            answer = row[name]
            if type(answer["correct"]) is not bool:
                raise ValueError("Typed correctness must be explicit boolean")
            values[name] = {**proper_scores(answer["probabilities"], row["gold"], row["labels"]), "correct": answer["correct"]}
        results.append(values)
    if not results:
        raise ValueError("Empty paired sample")
    summary = {"n": len(results), "scope": "empirical label-only paired diagnostic"}
    for name in ("baseline", "candidate"):
        summary[name] = {
            "correct": sum(x[name]["correct"] for x in results),
            "accuracy": mean(float(x[name]["correct"]) for x in results),
            "brier": mean(x[name]["brier"] for x in results),
            "nll": mean(x[name]["nll"] for x in results),
        }
    summary["gains"] = [x["id"] for x in results if x["candidate"]["correct"] and not x["baseline"]["correct"]]
    summary["losses"] = [x["id"] for x in results if x["baseline"]["correct"] and not x["candidate"]["correct"]]
    b, c = summary["baseline"], summary["candidate"]
    epsilon = 1e-12
    summary["development_gate_passed"] = (
        c["correct"] >= b["correct"]
        and c["brier"] <= b["brier"] + epsilon
        and c["nll"] <= b["nll"] + epsilon
        and (c["brier"] < b["brier"] - epsilon or c["nll"] < b["nll"] - epsilon)
    )
    summary["official_Calibration"] = None
    summary["official_rank"] = None
    return summary


def paired_bootstrap_interval(differences, seed=20261022, draws=2000):
    if not differences or not all(math.isfinite(v) for v in differences):
        raise ValueError("Need finite paired differences")
    rng = random.Random(seed)
    n = len(differences)
    distribution = sorted(mean(differences[rng.randrange(n)] for _ in range(n)) for _ in range(draws))
    # Nearest empirical percentiles, indices fixed before any observed result.
    return {"mean_improvement": mean(differences), "ci95": [distribution[int(.025 * (draws - 1))], distribution[int(.975 * (draws - 1))]], "draws": draws, "seed": seed}


def official_sota_gate(evidence):
    required = {
        "publisher_primary_source_measured": True,
        "independently_verified_receipt": True,
        "exact_candidate_identity_matches": True,
        "current_score_version_matches": True,
        "eligible_under_official_caps": True,
        "rank": 1,
    }
    if not all(evidence.get(k) == v for k, v in required.items()):
        return False
    if type(evidence.get("rank")) is not int:
        return False
    if evidence.get("scope") != "publisher_full_sealed_evaluation":
        return False
    if evidence.get("total_decisions", 0) < 1500 or evidence.get("sealed_decisions", 0) < 1200:
        return False
    url = evidence.get("primary_source_url", "")
    if not url.startswith("https://benchmarkheaven.com/"):
        return False
    if not isinstance(evidence.get("source_receipt_sha256"), str) or len(evidence["source_receipt_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in evidence["source_receipt_sha256"]):
        return False
    if not all(isinstance(evidence.get(k), (int, float)) and not isinstance(evidence[k], bool) and math.isfinite(evidence[k]) and evidence[k] >= 0 for k in ("Capability", "cost_usd_per_1000", "adjusted_p50_s")):
        return False
    return evidence["Capability"] <= 100 and evidence["cost_usd_per_1000"] <= .06459465517241379 and evidence["adjusted_p50_s"] <= 1.2329566404223442


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired-jsonl", type=Path)
    parser.add_argument("--splits-jsonl", type=Path)
    parser.add_argument("--official-evidence", type=Path)
    args = parser.parse_args()
    output = {}
    if args.paired_jsonl:
        output["paired"] = paired_diagnostics([json.loads(x) for x in args.paired_jsonl.read_text().splitlines() if x])
    if args.splits_jsonl:
        output["splits"] = check_split_isolation([json.loads(x) for x in args.splits_jsonl.read_text().splitlines() if x])
    if args.official_evidence:
        output["official_sota_gate"] = official_sota_gate(json.loads(args.official_evidence.read_text()))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
