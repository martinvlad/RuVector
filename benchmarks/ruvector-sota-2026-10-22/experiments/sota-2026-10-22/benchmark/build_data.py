"""Deterministic group-disjoint projection of exposed data and easy48 confirmation."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def input_hash(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def normalized_hash(value): return hashlib.sha256(re.sub(r"\s+", " ", canonical(value)).casefold().strip().encode()).hexdigest()
def load_jsonl(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def save(path, value): Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
def write_jsonl(path, values): Path(path).write_text("".join(canonical(x) + "\n" for x in values))


def project(task, source, split):
    question = {k: task["question"][k] for k in ["type", "instructions"]}
    if task["question"].get("criteria") is not None:
        question["criteria"] = task["question"]["criteria"]
    inference_input = {"state": task["state"], "questions": {"decision": question}}
    return {"id": task["id"], "split": split, "source": source,
            "source_group": task.get("group") or task["id"], "input": inference_input,
            "evaluation": {"type": question["type"], "gold": str(task["expected"]), "labels": task["labels"],
                           "source_family": task["family"], "group": task.get("group"), "gold_distribution": None},
            "input_sha256": input_hash(inference_input), "normalized_input_sha256": normalized_hash(inference_input)}


def main():
    if (HERE / "data-contract.json").exists():
        raise RuntimeError("Data already frozen; do not overwrite source/split evidence")
    (HERE / "sources").mkdir(exist_ok=True)
    sources = [ROOT / "data/jevbench/original.jsonl", ROOT / "data/jevbench/hard.jsonl", HERE / "easy.jsonl"]
    official_sources = ROOT / "experiments/swarm/jevbench-adapter/sources"
    for name in ["jevbench_tasks.py", "jevbench_scoring.py", "jevbench_adapters_base.py", "jevbench_adapters_typesafe.py"]:
        shutil.copyfile(official_sources / name, HERE / "sources" / name)
    records = []
    for source in sources[:2]:
        for task in load_jsonl(source):
            group = task.get("group") or task["id"]
            bucket = int(hashlib.sha256(("sota-2026-10-22:group-split:v1:" + group).encode()).hexdigest(), 16) % 10
            split = "train" if bucket < 6 else "dev" if bucket < 8 else "calibration"
            row = project(task, str(source.relative_to(ROOT)), split)
            row["exposure"] = "all old183 were used adaptively before this resplit; dev/calibration are not fresh benchmark holdouts"
            records.append(row)
    confirmation = [project(task, "datasets/public/easy.jsonl@1d5a81a6fc8c5e2dd3e243202802f0f3a04c7f35", "confirmation") for task in load_jsonl(sources[2])]
    for row in confirmation:
        row["exposure"] = "public upstream task, first-use internal confirmation based on current local historical artifact search; not sealed or universal contamination proof"
    all_records = records + confirmation
    assert len({x["id"] for x in all_records}) == len(all_records)
    collisions = []
    for field in ["source_group", "input_sha256", "normalized_input_sha256"]:
        seen = {}
        for row in all_records:
            old = seen.setdefault(row[field], row["split"])
            if old != row["split"]: collisions.append({"field": field, "id": row["id"], "splits": [old, row["split"]]})
    if collisions: raise ValueError(collisions)
    write_jsonl(HERE / "exposed183.jsonl", records)
    write_jsonl(HERE / "confirmation48.jsonl", confirmation)
    for split in ["train", "dev", "calibration"]:
        write_jsonl(HERE / (split + ".jsonl"), [x for x in records if x["split"] == split])
    decisions_path = ROOT / "experiments/submission-2026-10-22/jevbench/round2-v2/decisions.jsonl"
    decisions = {x["id"]: x for x in load_jsonl(decisions_path) if not x.get("warmup")}
    cached = []
    for row in records:
        decision = decisions[row["id"]]
        assert str(decision["expected"]) == row["evaluation"]["gold"]
        request_path = decisions_path.parent / decision["request_file"]
        response_path = decisions_path.parent / decision["response_file"]
        assert digest(request_path) == decision["request_sha256"]
        assert digest(response_path) == decision["response_sha256"]
        request = json.loads(request_path.read_bytes().split(b"\r\n\r\n", 1)[1])
        assert {"state": request["state"], "questions": request["questions"]} == row["input"]
        row = dict(row)
        row["response"] = decision["raw_response"]
        row["response_provenance"] = {"mode": "saved actual104 native-plus-validator response; no new native inference", "decisions_path": str(decisions_path.relative_to(ROOT)), "request_sha256": decision["request_sha256"], "response_sha256": decision["response_sha256"]}
        cached.append(row)
    write_jsonl(HERE / "exposed183-with-responses.jsonl", cached)
    split_summary = {split: {"n": sum(x["split"] == split for x in all_records),
                             "question_types": dict(Counter(x["evaluation"]["type"] for x in all_records if x["split"] == split)),
                             "source_groups": len({x["source_group"] for x in all_records if x["split"] == split})}
                     for split in ["train", "dev", "calibration", "confirmation"]}
    files = []
    for path in [*sorted((HERE / "sources").glob("*.py")), *sources, decisions_path, HERE / "current-repo-public-tree.json", HERE / "publisher-data-page.html", HERE / "publisher-data-page.txt", HERE / "publisher-data-receipt.json", HERE / "easy-exposure-search.json", *sorted(HERE.glob("*.jsonl")), HERE / "evaluate.py", HERE / "build_data.py"]:
        files.append({"path": str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path.relative_to(ROOT)), "sha256": digest(path), "bytes": path.stat().st_size, "location": "benchmark" if path.is_relative_to(HERE) else "project"})
    save(HERE / "source-manifest.json", {"schema_version": 1, "files": files})
    save(HERE / "data-contract.json", {
        "schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "frozen": True,
        "normalization": "Unmodified upstream build_question: type, instructions, criteria when non-null. input is only state/questions; model field omitted and no metadata passed.",
        "input_hash": "SHA256(json.dumps(input,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8'))",
        "normalized_input_hash": "Casefold and collapse all whitespace in canonical serialized input, then SHA256",
        "record_schema": {"id": "evaluation-only id", "split": "train|dev|calibration|confirmation", "source": "provenance only", "source_group": "paraphrase group or exact id", "input": {"state": "upstream state", "questions": {"decision": "upstream typed question"}}, "evaluation": {"type": "noul|choice|score", "gold": "exact STRING label, including ordinal index", "labels": "exact upstream labels in order", "source_family": "upstream family", "group": "upstream group or null", "gold_distribution": None}, "input_sha256": "canonical hash", "normalized_input_sha256": "duplicate-control hash", "response": "only in cached/measured records"},
        "split_summary": split_summary,
        "files": {name: {"path": name, "sha256": digest(HERE/name)} for name in ["exposed183.jsonl", "exposed183-with-responses.jsonl", "train.jsonl", "dev.jsonl", "calibration.jsonl", "confirmation48.jsonl"]},
        "split_rule": "SHA256('sota-2026-10-22:group-split:v1:' + source_group) mod10: <6 train, <8 dev, else calibration. easy48 held out separately.",
        "cross_split_id_group_canonical_and_normalized_input_collisions": collisions,
        "scoring_api": "benchmark.evaluate.score_records(records) -> n,correct,accuracy,brier,nll,strict_valid,errors,ece10,by_type; benchmark.evaluate.score_record(record) -> per-item diagnostics",
        "brier_definition": "Sum over exact labels of (p - one_hot_gold)^2, averaged over items. Invalid item penalty2; no fabricated probabilities.",
        "nll_definition": "-log(max(1e-15,p_gold)); invalid item penalty -log(1e-15).",
        "strict_and_label_accuracy": "Pinned unchanged legacy official scoring.py, same adapter noul/choice/score parsing semantics; not the current full-release Capability score.",
        "current_release300": {"status": "NOT_PUBLICLY_LOCATED", "evidence": ["current-repo-public-tree.json", "publisher-data-page.txt"], "meaning": "Untruncated official public repo exposes original72/hard111/easy48; publisher data page offers aggregate system results only. Current draw300 cannot be reconstructed from these sources."},
        "current_official_scorer": {"status": "CURRENT_V16_SOURCE_NOT_LOCATED_IN_OFFICIAL_JEVBENCH_TREE", "fallback": "Legacy pinned unchanged per-item scorer plus explicitly local proper-score diagnostics only"},
        "official_capability": None, "official_rank": None,
        "native_inference_calls_by_data_preparation": 0,
        "limits": ["All exposed183 labels already used adaptively before this resplit", "easy48 is public historical data, not current300 or publisher sealed test", "No gold probability distributions are available for official fidelity calibration", "No claim that unseen project IDs imply unseen model training data"]})
    print(json.dumps({"status": "frozen", "splits": split_summary, "current300": "not publicly located", "manifest_sha256": digest(HERE/'source-manifest.json'), "data_contract_sha256": digest(HERE/'data-contract.json')}))


if __name__ == "__main__": main()
