"""Draw fresh DEV documents using a frozen eligibility registry, not old corpora."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent / "epoch3/sources/original-train.json"
INSTRUCTION = "Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned."
LABELS = {"Entailment": "Yes", "Contradiction": "No", "NotMentioned": "No"}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def norm(value): return " ".join(value.casefold().split())


def draw(source_path=DEFAULT_SOURCE):
    plan = json.loads((HERE / "draw-plan.json").read_text())
    registry = json.loads((HERE / "eligibility-manifest.json").read_text())
    if sha(HERE / "eligibility-manifest.json") != plan["eligibility_manifest_sha256"]:
        raise ValueError("Frozen eligibility registry changed")
    if sha(source_path) != plan["source_sha256"]:
        raise ValueError("Original train JSON source changed")
    source = json.loads(Path(source_path).read_text())
    all_ids = {doc["id"] for doc in source["documents"]}
    excluded = {doc["id"] for doc in registry["historical_exclusions"]["excluded_documents"]}
    prior = set(registry["consumed_epoch3_dev"]["document_ids"])
    expected_eligible = all_ids - excluded - prior
    if set(registry["eligible_document_ids"]) != expected_eligible:
        raise ValueError("Frozen eligibility list is inconsistent with prior exclusions")
    candidates = []
    for doc in source["documents"]:
        if doc["id"] not in expected_eligible: continue
        text_sha = hashlib.sha256(norm(doc["text"]).encode()).hexdigest()
        key = hashlib.sha256(("ruvector-original-contractnli-epoch4-dev-v1|" + str(doc["id"]) + "|" + text_sha).encode()).hexdigest()
        candidates.append((key, text_sha, doc))
    chosen = sorted(candidates, key=lambda entry: entry[0])[:plan["documents"]]
    if len(chosen) != 8: raise ValueError("Insufficient unused documents")
    records = []
    for key, text_sha, doc in chosen:
        if len(doc["annotation_sets"]) != 1: raise ValueError("Ambiguous source annotation")
        for hypothesis_id in plan["hypotheses"]:
            hypothesis = source["labels"][hypothesis_id]["hypothesis"]
            inp = {"state": doc["text"], "questions": {"decision": {
                "type": "choice", "instructions": INSTRUCTION,
                "criteria": {"Yes": hypothesis, "No": "The agreement does not establish the following: " + hypothesis}}}}
            # Labels are projected only after document eligibility and choice are fixed.
            original = doc["annotation_sets"][0]["annotations"][hypothesis_id]["choice"]
            records.append({
                "id": f"original-contractnli:train:epoch4:{doc['id']}:{hypothesis_id}", "split": "dev",
                "source": "stanfordnlp/contract-nli@" + plan["source_commit"] + "/train.json",
                "source_group": "original-contractnli:" + str(doc["id"]), "input": inp,
                "evaluation": {"type": "choice", "gold": LABELS[original], "labels": ["Yes", "No"],
                               "source_family": hypothesis_id, "group": "original-contractnli:" + str(doc["id"]),
                               "gold_distribution": None, "original_threeway_label": original},
                "input_sha256": hashlib.sha256(canonical(inp).encode()).hexdigest(),
                "normalized_input_sha256": hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),
                "provenance": {"document_id": doc["id"], "file_name": doc["file_name"], "source_split": "train",
                               "hypothesis_id": hypothesis_id, "document_draw_key": key,
                               "normalized_document_sha256": text_sha, "license": "CC-BY-4.0"},
                "exposure": "New project DEVdocument group, selected using frozen prior-exclusion registry. Public training-split data; not unseen-pretraining or official benchmark evidence."})
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = draw(args.source)
    with args.output.open("x") as stream:
        for record in records: stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"queries": len(records), "document_groups": len({r["source_group"] for r in records}), "sha256": sha(args.output), "native_calls": 0}))
