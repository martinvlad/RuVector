"""Pinned legacy JevBench parser/scorer plus explicitly local diagnostics.

These metrics are NOT the current official Capability score. Invalid responses
count wrong and receive diagnostic Brier=2 and NLL=-log(1e-15), never a fabricated
replacement distribution. Full-release calibration fidelity is unavailable.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SCORER_SHA256 = "frozen_by_source_manifest"


def _load_scorer():
    path = HERE / "sources" / "jevbench_scoring.py"
    import json
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    expected = next(x["sha256"] for x in manifest["files"] if x["path"] == "sources/jevbench_scoring.py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Pinned official scorer changed")
    spec = importlib.util.spec_from_file_location("sota_pinned_legacy_scorer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_record(record):
    scorer = _load_scorer()
    evaluation = record["evaluation"]
    labels = evaluation["labels"]
    gold = evaluation["gold"]
    kind = evaluation["type"]
    task = SimpleNamespace(labels=labels, expected=int(gold) if kind == "score" else gold, question={"type": kind})
    try:
        answer = record["response"]["answers"]["decision"]
        if answer["type"] != kind:
            raise ValueError("Native answer type mismatch")
        if kind == "noul":
            value = answer["noul"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("noul must be finite numeric probability")
            probabilities = {"yes": float(value), "no": 1.0 - float(value)}
        else:
            if kind == "choice" and answer.get("choice") not in labels:
                raise ValueError("Invalid native choice")
            probabilities = answer["probabilities"]
        scored = scorer.score_task(probabilities, task)
    except (KeyError, TypeError, ValueError) as exc:
        scored = {"valid": False, "strict_valid": False, "correct": False, "error": str(exc), "predicted": None}
    result = {"id": record["id"], "type": kind, **scored}
    if not scored["valid"]:
        result.update(brier=2.0, nll=-math.log(1e-15), confidence=0.0, ordinal_nrps=None)
        return result
    probabilities = scored["probs"]
    result["brier"] = sum((probabilities[label] - float(label == gold)) ** 2 for label in labels)
    result["nll"] = -math.log(max(1e-15, probabilities[gold]))
    result["confidence"] = max(probabilities.values())
    result["ordinal_nrps"] = None
    if kind == "score":
        cdf = 0.0
        values = []
        for index in range(len(labels) - 1):
            cdf += probabilities[str(index)]
            values.append((cdf - float(int(gold) <= index)) ** 2)
        result["ordinal_nrps"] = sum(values) / (len(labels) - 1)
    return result


def _aggregate(rows):
    n = len(rows)
    if not n:
        return {"n": 0, "correct": 0, "accuracy": None, "brier": None, "nll": None, "strict_valid": 0, "errors": 0, "ece10": None}
    ece = 0.0
    for index in range(10):
        bucket = [x for x in rows if x["valid"] and min(9, int(10 * x["confidence"])) == index]
        if bucket:
            ece += len(bucket) / n * abs(sum(x["confidence"] for x in bucket) / len(bucket) - sum(bool(x["correct"]) for x in bucket) / len(bucket))
    return {"n": n, "correct": sum(bool(x["correct"]) for x in rows),
            "accuracy": sum(bool(x["correct"]) for x in rows) / n,
            "brier": sum(x["brier"] for x in rows) / n,
            "nll": sum(x["nll"] for x in rows) / n,
            "strict_valid": sum(bool(x["strict_valid"]) for x in rows),
            "errors": sum(not x["valid"] for x in rows), "ece10": ece}


def score_records(records):
    """Return aggregate diagnostic metrics; each record has input/evaluation/response."""
    rows = [score_record(record) for record in records]
    return {**_aggregate(rows), "by_type": {kind: _aggregate([x for x in rows if x["type"] == kind]) for kind in sorted({x["type"] for x in rows})},
            "metric_scope": "legacy-public accuracy and local proper-score diagnostics; not current official Capability",
            "official_score": None, "official_rank": None}


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.records.read_text().splitlines() if line]
    print(json.dumps(score_records(records), indent=2, allow_nan=False))
