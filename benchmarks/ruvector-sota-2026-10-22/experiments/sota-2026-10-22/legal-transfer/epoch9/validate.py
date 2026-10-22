"""Exact source replay and negative controls; no models or native operations."""
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
    if build.canonical(records) != build.canonical(expected): raise ValueError("Changed frozen draw, roles, labels or input")
    ids, inputs, groups, texts = {}, {}, {}, {}
    for role, (n, g) in {"dev": (24, 8), "confirmation": (48, 16)}.items():
        rows = records[role]
        ids[role] = {r["id"] for r in rows}; inputs[role] = {r["input_sha256"] for r in rows}
        groups[role] = {r["source_group"] for r in rows}; texts[role] = {r["provenance"]["normalized_document_sha256"] for r in rows}
        if (len(rows), len(ids[role]), len(inputs[role]), len(groups[role]), len(texts[role])) != (n, n, n, g, g):
            raise ValueError("Wrong denominator or repeated identities/text")
        for row in rows:
            if row["split"] != role or row["provenance"]["source_split"] != "train": raise ValueError("Role/source leak")
            if set(row["input"]) != {"state", "questions"}: raise ValueError("Gold or metadata in inference")
            if build.LABELS[row["evaluation"]["original_threeway_label"]] != row["evaluation"]["gold"]:
                raise ValueError("Wrong original threeway to binary projection")
    for sets in (ids, inputs, groups, texts):
        if sets["dev"] & sets["confirmation"]: raise ValueError("DEV/CONF overlap")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, default=build.DEFAULT_SOURCE)
    args = parser.parse_args()
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for item in manifest["files"]:
        if build.sha(HERE / item["path"]) != item["sha256"]: raise ValueError("Changed frozen artifact: " + item["path"])
    records = {role: [json.loads(line) for line in (HERE / filename).read_text().splitlines()] for role, filename in build.FILENAMES.items()}
    check(records, args.source)
    for role, filename in build.FILENAMES.items():
        if json.loads((HERE / (role + "-allowlist.json")).read_text()) != build.allowlist(records[role], role, build.sha(HERE / filename)):
            raise ValueError("Changed metadata-only allowlist")
    mutations = [lambda r: r["dev"][0]["input"].update(gold="Yes"),
                 lambda r: r["dev"][0]["evaluation"].update(original_threeway_label="invalid"),
                 lambda r: r["confirmation"][0].update(split="dev"),
                 lambda r: r["confirmation"][0].update(source_group=r["dev"][0]["source_group"]),
                 lambda r: r["dev"][0]["provenance"].update(source_split="dev"),
                 lambda r: r["confirmation"][0]["input"]["questions"]["decision"]["criteria"].update(Yes="Different predicate"),
                 lambda r: r["confirmation"][0]["evaluation"].update(gold="invalid")]
    for mutation in mutations:
        changed = copy.deepcopy(records); mutation(changed)
        try: check(changed, args.source)
        except (ValueError, KeyError): pass
        else: raise AssertionError("Invalid control accepted")
    report = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
              "source_pins": len(manifest["files"]), "joint_label_independent_draw": True,
              "train_queries": 0, "calibration_queries": 0, "dev": {"queries": 24, "documents": 8},
              "confirmation": {"queries": 48, "documents": 16}, "prior_officialtrain_groups_excluded": 149,
              "retired_officialdev_groups_excluded": 32, "ids_inputs_groups_and_texts_disjoint": True,
              "original_threeway_labels_and_binary_mapping_replayed": True, "negative_controls_rejected": len(mutations),
              "novelty_limit": "Project-unused public sources with inherited historical semantic registry; not sealed or pretraining-contamination-proof.",
              "old_confirmation_label_reads": 0, "native_model_paid_calls": 0, "official_score": None, "official_rank": None}
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n"); print(json.dumps(report))


if __name__ == "__main__": main()
