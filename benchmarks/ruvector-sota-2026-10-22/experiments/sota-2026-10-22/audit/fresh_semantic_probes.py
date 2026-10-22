"""Auditor-created post-freeze pure probes; synthetic software checks only."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
HEAD = HERE.parent / "candidate/head.py"
EXPECTED_HEAD_SHA256 = "c0179108"


def main():
    digest = hashlib.sha256(HEAD.read_bytes()).hexdigest()
    if not digest.startswith(EXPECTED_HEAD_SHA256):
        raise ValueError("Candidate changed after probe design began")
    spec = importlib.util.spec_from_file_location("audited_frozen_head", HEAD)
    head = importlib.util.module_from_spec(spec); spec.loader.exec_module(head)
    records = []
    for role in ("train", "calibration"):
        for i in range(30):
            q = {"type": "choice", "instructions": "Which supplied alloy name appears in the memo?", "criteria": {"amber": "zirconium", "violet": "rhenium", "teal": "scandium"}}
            selected = i % 3
            labels = list(q["criteria"])
            p = {label: (.72 if j == selected else .14) for j, label in enumerate(labels)}
            gold = labels[selected if i % 5 else (selected + 1) % 3]
            records.append({"id": f"unseen-{role}-{i}", "split": role,
                "input": {"state": f"{role} ledger {i}: supplied alloy {list(q['criteria'].values())[selected]}; arbitrary record ZQ{i}.", "questions": {"probe": q}},
                "evaluation": {"gold": gold}, "response": {"answers": {"probe": {"type": "choice", "choice": labels[selected], "probabilities": p, "native_fallback_used": True}}}})
    artifacts = [head.fit(records, c) for c in head.candidate_configs()]
    checks = []
    def check(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(name)
    sample = records[3]
    for artifact in artifacts:
        label = artifact["config"]["id"]
        q = copy.deepcopy(sample["input"]["questions"])
        response = copy.deepcopy(sample["response"])
        before = copy.deepcopy((response, q, sample["input"]["state"]))
        result = head.transform(response, sample["input"]["state"], q, artifact)
        check(label + ":does_not_mutate_inputs", (response, q, sample["input"]["state"]) == before)
        check(label + ":finite_exact_distribution", all(0 <= p <= 1 for p in result["answers"]["probe"]["probabilities"].values()) and abs(sum(result["answers"]["probe"]["probabilities"].values()) - 1) < 1e-12)
        mapping = {"XX": "teal", "YY": "amber", "ZZ": "violet"}
        q["probe"]["criteria"] = {new: q["probe"]["criteria"][old] for new, old in mapping.items()}
        ans = response["answers"]["probe"]
        ans["probabilities"] = {new: ans["probabilities"][old] for new, old in mapping.items()}
        ans["choice"] = next(new for new, old in mapping.items() if old == ans["choice"])
        renamed = head.transform(response, sample["input"]["state"], q, artifact)
        check(label + ":class_renaming_and_reordering_equivariant", all(abs(renamed["answers"]["probe"]["probabilities"][new] - result["answers"]["probe"]["probabilities"][old]) < 1e-12 for new, old in mapping.items()))
        class Poison(dict):
            def __getitem__(self, key): raise AssertionError("Non-fitting label read")
            def get(self, *args): raise AssertionError("Non-fitting label read")
            def items(self): raise AssertionError("Non-fitting label read")
            def values(self): raise AssertionError("Non-fitting label read")
        dev = copy.deepcopy(records[0]); dev["split"] = "dev"; dev["input"]["state"] += " distinct untouched DEV"; dev["evaluation"] = Poison()
        check(label + ":dev_labels_not_read_by_fit", head.fit(records + [dev], artifact["config"]) == artifact)
        bad = copy.deepcopy(records[0]); bad["split"] = "confirmation"; bad["input"]["state"] += " unused confirmation"; bad["evaluation"] = Poison()
        try:
            head.fit(records + [bad], artifact["config"])
        except ValueError:
            check(label + ":confirmation_rejected_before_any_gold_read", True)
        else:
            raise AssertionError("Confirmation not rejected")
    output = {"checks_passed": True, "checks": checks, "n": len(checks), "head_sha256": digest,
        "scope": "Post-freeze independent pure synthetic software probes, not benchmark accuracy or generalization", "native_calls": 0, "paid_calls": 0}
    path = HERE / "fresh-semantic-probes-v1.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"checks_passed": True, "n": len(checks), "receipt": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
