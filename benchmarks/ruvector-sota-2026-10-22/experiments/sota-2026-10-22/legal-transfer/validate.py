"""Pure source/draw/prompt/label/overlap validation; never performs inference."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_data


def validate_records(records):
    plan = json.loads((HERE / "draw-plan.json").read_text())
    if len(records) != 96:
        raise ValueError("Wrong denominator")
    ids, hashes, groups = set(), set(), set()
    counts = {}
    sources = {}
    for task in plan["tasks"]:
        with (HERE / "sources" / task / "test.tsv").open() as stream:
            sources[task] = {row["index"]: row for row in csv.DictReader(stream, delimiter="\t")}
    excluded = set(json.loads((HERE / "historical-overlap.json").read_text())["excluded_document_names"])
    for record in records:
        task = record["evaluation"]["source_family"]
        original = sources[task][record["provenance"]["official_index"]]
        if record["split"] != "confirmation" or record["evaluation"]["gold"] != original["answer"]:
            raise ValueError("Role or label projection invalid")
        if set(record["input"]) != {"state", "questions"} or record["input"]["state"] != original["text"]:
            raise ValueError("Inference boundary invalid")
        question = record["input"]["questions"]["decision"]
        expected_instruction = (HERE / "sources" / task / "base_prompt.txt").read_text().split("\n\n", 1)[0].strip() + "\n\nAnswer Yes or No."
        if question != {"type": "choice", "instructions": expected_instruction, "criteria": {"Yes": "Yes", "No": "No"}}:
            raise ValueError("Official instruction or fixed typed adaptation changed")
        if original["document_name"] in excluded:
            raise ValueError("Previously observed source document")
        if record["source_group"] != "contractnli:" + original["document_name"]:
            raise ValueError("Source group mismatch")
        if record["id"] in ids or record["source_group"] in groups or record["query_normalized_sha256"] in hashes:
            raise ValueError("Repeated item, document or query text")
        expected_hash = hashlib.sha256(build_data.canonical(record["input"]).encode()).hexdigest()
        if expected_hash != record["input_sha256"]:
            raise ValueError("Inference input hash mismatch")
        ids.add(record["id"]); groups.add(record["source_group"]); hashes.add(record["query_normalized_sha256"])
        counts[task] = counts.get(task, 0) + 1
    if counts != {task: 24 for task in plan["tasks"]}:
        raise ValueError("Per-task draw changed")
    return counts


def run():
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for item in manifest["files"]:
        path = HERE / item["path"]
        if build_data.sha(path) != item["sha256"]:
            raise ValueError("Frozen source mismatch: " + item["path"])
    records = [json.loads(line) for line in (HERE / "confirmation96.jsonl").read_text().splitlines()]
    counts = validate_records(records)
    # Re-run the exact text-only matching/draw algorithm without writing artifacts.
    regenerated = build_data.draw(write_outputs=False)
    if build_data.canonical(regenerated) != build_data.canonical(records):
        raise ValueError("Deterministic source draw does not replay")
    failures = 0
    for mutate in (lambda rows: rows[0]["input"].update(gold="Yes"),
                   lambda rows: rows[0]["evaluation"].update(gold="INVALID"),
                   lambda rows: rows[1].update(source_group=rows[0]["source_group"]),
                   lambda rows: rows[0].update(split="train")):
        broken = copy.deepcopy(records); mutate(broken)
        try:
            validate_records(broken)
        except (ValueError, KeyError):
            failures += 1
        else:
            raise AssertionError("Malformed transfer fixture was accepted")
    report = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
              "source_pins": len(manifest["files"]), "n": len(records), "task_counts": counts,
              "unique_documents": len({x["source_group"] for x in records}),
              "unique_query_texts": len({x["query_normalized_sha256"] for x in records}),
              "deterministic_draw_replayed_without_writes": True, "negative_controls_rejected": failures,
              "inference_inputs_contain_no_labels_or_metadata": True,
              "actual_native_or_paid_calls": 0, "official_score": None, "official_rank": None}
    build_data.save(HERE / "validation.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    run()
