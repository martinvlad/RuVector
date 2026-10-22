"""Pure standalone data replay and negative controls. No historical corpus reads."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build


def check(records, source_path):
    expected = build.draw(source_path)
    if build.canonical(records) != build.canonical(expected): raise ValueError("Data differs from exact label-independent source draw")
    if len(records) != 24 or len({row["source_group"] for row in records}) != 8:
        raise ValueError("Wrong query/document denominator")
    if len({row["input_sha256"] for row in records}) != 24: raise ValueError("Duplicate inference inputs")
    registry = json.loads((HERE / "eligibility-manifest.json").read_text())
    consumed = set(registry["consumed_epoch3_dev"]["document_ids"]) | set(registry["consumed_epoch4_dev"]["document_ids"])
    if consumed & {row["provenance"]["document_id"] for row in records}: raise ValueError("Reused prior DEVdocument")
    for row in records:
        if set(row["input"]) != {"state", "questions"}: raise ValueError("Evaluation metadata leaked to inference")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=build.DEFAULT_SOURCE)
    args = parser.parse_args()
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for item in manifest["files"]:
        if build.sha(HERE / item["path"]) != item["sha256"]: raise ValueError("Frozen source changed: " + item["path"])
    records = [json.loads(line) for line in (HERE / "development24.jsonl").read_text().splitlines()]
    check(records, args.source)
    negatives = 0
    for mutation in (lambda rows: rows[0]["input"].update(gold="Yes"),
                     lambda rows: rows[0]["evaluation"].update(gold="invalid"),
                     lambda rows: rows[1].update(source_group=rows[0]["source_group"] + ":changed"),
                     lambda rows: rows[0].update(split="confirmation")):
        changed = copy.deepcopy(records); mutation(changed)
        try: check(changed, args.source)
        except ValueError: negatives += 1
        else: raise AssertionError("Malformed replay fixture accepted")
    # Reconstruct using only the required public source plus own frozen files.
    # No prior raw corpora, source report path, consumed data or confirmation labels are read.
    result = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
              "frozen_source_pins": len(manifest["files"]), "queries": 24, "document_groups": 8,
              "novel_to_epoch3_and_epoch4_DEV": True, "historical_novelty_basis": "Inherited hash-bound exclusion registry, not re-proved historical corpus semantics",
              "deterministic_draw_reproduced": True, "prior_raw_corpus_reads": 0, "confirmation_label_reads": 0,
              "negative_controls_rejected": negatives, "fit_or_calibration": False, "new_native_or_paid_calls": 0,
              "official_score": None, "official_rank": None}
    (HERE / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__": main()
