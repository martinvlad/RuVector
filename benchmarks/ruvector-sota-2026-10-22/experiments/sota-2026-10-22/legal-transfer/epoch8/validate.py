"""Exact TRAIN/DEV source replay and leakage controls; no model or inference."""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build


def check(records, source_path):
    expected = build.draw(source_path)
    if build.canonical(records) != build.canonical(expected): raise ValueError("Changed joint draw, role, label or inference projection")
    expected_sizes = {"train": (72, 24), "dev": (24, 8)}
    ids, hashes, groups = {}, {}, {}
    for role, rows in records.items():
        n, g = expected_sizes[role]
        ids[role] = {row["id"] for row in rows}
        hashes[role] = {row["input_sha256"] for row in rows}
        groups[role] = {row["source_group"] for row in rows}
        if len(rows) != n or len(ids[role]) != n or len(hashes[role]) != n or len(groups[role]) != g:
            raise ValueError("Wrong denominator or repeated identities")
        for row in rows:
            if row["split"] != role or row["provenance"]["source_split"] != "train": raise ValueError("Fit source/role leak")
            if set(row["input"]) != {"state", "questions"}: raise ValueError("Evaluation metadata in inference")
            original = row["evaluation"]["original_threeway_label"]
            if build.LABELS[original] != row["evaluation"]["gold"]: raise ValueError("Wrong 3way/binary projection")
    if ids["train"] & ids["dev"] or hashes["train"] & hashes["dev"] or groups["train"] & groups["dev"]:
        raise ValueError("TRAIN/DEV overlap")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=build.DEFAULT_SOURCE)
    args = parser.parse_args()
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for item in manifest["files"]:
        if build.sha(HERE / item["path"]) != item["sha256"]: raise ValueError("Frozen source changed: " + item["path"])
    records = {role: [json.loads(line) for line in (HERE / filename).read_text().splitlines()]
               for role, filename in (("train", "train72.jsonl"), ("dev", "development24.jsonl"))}
    check(records, args.source)
    for role in ("train", "dev"):
        meta = json.loads((HERE / (role + "-allowlist.json")).read_text())
        expected = build.allowlist(records[role], role, build.sha(HERE / ("train72.jsonl" if role == "train" else "development24.jsonl")))
        if meta != expected: raise ValueError("Input-only fitting/gating allowlist changed")
    rejected = 0
    mutations = [lambda r: r["train"][0]["input"].update(gold="Yes"),
                 lambda r: r["train"][0]["evaluation"].update(original_threeway_label="invalid"),
                 lambda r: r["train"][0].update(split="dev"),
                 lambda r: r["dev"][0].update(source_group=r["train"][0]["source_group"]),
                 lambda r: r["train"][0]["provenance"].update(source_split="dev"),
                 lambda r: r["dev"][0]["input"]["questions"]["decision"]["criteria"].update(Yes="Different predicate")]
    for mutation in mutations:
        changed = copy.deepcopy(records); mutation(changed)
        try: check(changed, args.source)
        except (ValueError, KeyError): rejected += 1
        else: raise AssertionError("Leaking or malformed fixture accepted")
    report = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
              "source_pins": len(manifest["files"]), "joint_label_independent_draw": True,
              "train": {"queries": 72, "documents": 24}, "dev": {"queries": 24, "documents": 8},
              "ids_inputs_and_groups_disjoint": True, "officialdev_or_test_in_fit": False,
              "original_threeway_labels_and_binary_mapping_replayed": True, "negative_controls_rejected": rejected,
              "historical_novelty_basis": "Frozen inherited eligibility registry; prior raw corpora not re-read",
              "confirmation_label_reads": 0, "native_model_paid_calls": 0, "official_score": None, "official_rank": None}
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__": main()
