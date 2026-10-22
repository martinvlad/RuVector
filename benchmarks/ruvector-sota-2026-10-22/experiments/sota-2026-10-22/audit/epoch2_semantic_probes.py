"""Post-freeze independent diagnostic probes for decision invariance, no model calls."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "candidate/epoch2/head.py"
EXPECTED_SHA = "907f1a2827d5cca5d3ca33c91a8bd841b12e0b36df4f7944aed6be6152929db9"


def winner(p): return sorted(p, key=lambda k: (-p[k], k))[0]


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA
    spec = importlib.util.spec_from_file_location("independent_epoch2_head", SOURCE)
    head = importlib.util.module_from_spec(spec); spec.loader.exec_module(head)
    tests = 0; fallbacks = 0; rng = random.Random(938721)
    def check(value):
        nonlocal tests
        assert value
        tests += 1
    cases = []
    for n in range(2, 9):
        labels = [f"independent_{i}" for i in reversed(range(n))]
        for _ in range(100):
            logits = [rng.uniform(-750, 0) for _ in labels]
            p = [math.exp(x - max(logits)) for x in logits]
            cases.append(dict(zip(labels, [x / sum(p) for x in p])))
        cases.extend([{k: 1 / n for k in labels}, {k: float(i == n - 1) for i, k in enumerate(labels)}])
    for yes in [0, 1, .5, math.nextafter(.5, 0), math.nextafter(.5, 1), 1e-300, 1 - 1e-15]:
        cases.append({"yes": yes, "no": 1 - yes})
    for p in cases:
        for t in (.1, .8, 1, 4.7, 100):
            out, fallback = head.tempered(p, t)
            check(winner(out) == winner(p))
            check(set(out) == set(p) and all(math.isfinite(x) and 0 <= x <= 1 for x in out.values()))
            check(abs(sum(out.values()) - 1) < 1e-12)
            if fallback: fallbacks += 1
    records = []
    for i in range(20):
        q = {"type": "choice", "criteria": {"z": "indium", "a": "boron"}, "instructions": "Read the supplied chemical name."}
        records.append({"split": "calibration", "input": {"state": f"indium memo{i}", "questions": {"q": q}}, "evaluation": {"gold": "z" if i % 3 else "a"}, "response": {"answers": {"q": {"type": "choice", "choice": "z", "probabilities": {"z": .7, "a": .3}}}}})
    for config in head.candidate_configs():
        artifact = head.fit(records, config)
        q = {"choice": {"type": "choice", "criteria": {"z": "indium", "a": "boron"}, "instructions": "Read supplied name."},
             "scalar": {"type": "noul", "instructions": "Is this true?"},
             "ordinal": {"type": "score", "criteria": ["low", "medium", "high"], "instructions": "Read level."}}
        response = {"answers": {"choice": {"type": "choice", "choice": "z", "probabilities": {"z": .7, "a": .3}},
            "scalar": {"type": "noul", "noul": math.nextafter(.5, 1)},
            "ordinal": {"type": "score", "score": .123456789, "probabilities": {"0": .9, "1": .05, "2": .05}, "extra_source_proof": {"offsets": [2, 9]}}}}
        before = copy.deepcopy(response)
        out = head.transform(response, {"unordered": "raw state"}, q, artifact)
        check(before == response)
        check(out["answers"]["ordinal"] == before["answers"]["ordinal"])
        check(out["answers"]["choice"]["choice"] == before["answers"]["choice"]["choice"])
        check(winner(out["answers"]["choice"]["probabilities"]) == "z")
        check(winner(out["answers"]["scalar"]["probabilities"]) == "yes")
        check(out["answers"]["scalar"]["noul"] == out["answers"]["scalar"]["probabilities"]["yes"])
        for bad in (float("nan"), float("inf"), True, "0.5"):
            broken = copy.deepcopy(response); broken["answers"]["scalar"]["probabilities"] = {"yes": bad, "no": .5}
            try: head.transform(broken, "", q, artifact)
            except ValueError: tests += 1
            else: raise AssertionError("Invalid redundant Bernoulli map accepted")
        for bad in (True, False, 0, -1, float("nan"), float("inf")):
            try: head.tempered({"a": .6, "b": .4}, bad)
            except ValueError: tests += 1
            else: raise AssertionError("Invalid temperature accepted")
    proof = {"checks_passed": True, "checks": tests, "distribution_cases": len(cases), "temperatures_per_case": 5,
        "identity_fallbacks_exercised": fallbacks, "source_sha256": EXPECTED_SHA,
        "scope": "Independent synthetic numerical/semantic software checks after source freeze; no benchmark accuracy or generalization claim", "new_native_calls": 0, "new_paid_calls": 0}
    path = HERE / "epoch2-semantic-probes-v1.json"; path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({**proof, "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__": main()
