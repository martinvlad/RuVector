"""Validate frozen data lineage, split boundaries and diagnostic scoring."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from evaluate import score_record, score_records


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main():
    contract = json.loads((HERE / "data-contract.json").read_text())
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for entry in manifest["files"]:
        root = HERE if entry["location"] == "benchmark" else ROOT
        path = root / entry["path"]
        assert path.stat().st_size == entry["bytes"]
        assert sha(path) == entry["sha256"], str(path)
    records = load(HERE / "exposed183-with-responses.jsonl")
    confirmation = load(HERE / "confirmation48.jsonl")
    assert len(records) == 183 and len(confirmation) == 48
    for item in [*records, *confirmation]:
        assert set(item["input"]) == {"state", "questions"}
        assert set(item["input"]["questions"]) == {"decision"}
        assert hashlib.sha256(canonical(item["input"]).encode()).hexdigest() == item["input_sha256"]
        assert item["evaluation"]["gold"] in item["evaluation"]["labels"]
        assert item["evaluation"]["gold_distribution"] is None
    split_sets = {}
    for split in ["train", "dev", "calibration", "confirmation"]:
        rows = [item for item in [*records, *confirmation] if item["split"] == split]
        split_sets[split] = {key: {item[key] for item in rows} for key in ["id", "source_group", "input_sha256", "normalized_input_sha256"]}
        assert len(rows) == contract["split_summary"][split]["n"]
    names = list(split_sets)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            for key in split_sets[left]:
                assert not split_sets[left][key] & split_sets[right][key], (left, right, key)
    metrics = score_records(records)
    assert metrics["correct"] == 104 and metrics["strict_valid"] == 183 and metrics["errors"] == 0
    assert abs(metrics["brier"] - 0.5739495692089873) < 1e-15
    assert abs(metrics["nll"] - 0.9978038016019558) < 1e-15
    assert metrics["official_score"] is None and metrics["official_rank"] is None
    # Proper scores must prefer a correct uncertain distribution over a confident
    # wrong distribution, and reject malformed native output without repairing it.
    sample = {"id": "scoring-contract-unseen", "evaluation": {"type": "choice", "gold": "g", "labels": ["g", "h"]},
              "response": {"answers": {"decision": {"type": "choice", "choice": "g", "probabilities": {"g": .7, "h": .3}}}}}
    good = score_record(sample)
    wrong = copy.deepcopy(sample)
    wrong["response"]["answers"]["decision"].update(choice="h", probabilities={"g": .01, "h": .99})
    bad = score_record(wrong)
    assert good["correct"] and not bad["correct"] and good["nll"] < bad["nll"] and good["brier"] < bad["brier"]
    malformed = copy.deepcopy(sample)
    malformed["response"]["answers"]["decision"]["probabilities"] = {"g": .8, "h": .8}
    invalid = score_record(malformed)
    assert not invalid["valid"] and not invalid["correct"] and invalid["brier"] == 2
    missing = copy.deepcopy(sample)
    missing["response"] = {}
    assert not score_record(missing)["valid"]
    boolean = {"id": "boolean-is-not-probability", "evaluation": {"type": "noul", "gold": "yes", "labels": ["no", "yes"]},
               "response": {"answers": {"decision": {"type": "noul", "noul": True}}}}
    assert not score_record(boolean)["valid"]
    summary = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
               "source_manifest_sha256": sha(HERE / "source-manifest.json"), "data_contract_sha256": sha(HERE / "data-contract.json"),
               "validation_source_sha256": sha(Path(__file__)), "frozen_source_checks": len(manifest["files"]),
               "split_counts": {name: contract["split_summary"][name]["n"] for name in names},
               "cross_split_id_group_request_duplicate_collisions": 0, "legacy104_saved_response_replay": metrics,
               "native_inference_calls": 0, "network_calls": 0,
               "diagnostic_contract_tests": ["proper scores prefer correct uncertainty to confident error", "unnormalized probabilities fail closed", "missing output fails closed", "bool noul fails closed"],
               "official_score": None, "official_rank": None}
    (HERE / "validation.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"checks_passed": True, "frozen_source_checks": len(manifest["files"]), "split_counts": summary["split_counts"], "legacy_correct": metrics["correct"], "native_inference_calls": 0}))


if __name__ == "__main__": main()
