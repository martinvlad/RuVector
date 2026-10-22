"""One label-independent source-document draw, then disjoint TRAIN/DEV roles."""
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
        raise ValueError("Official original TRAIN source identity changed")
    source = json.loads(Path(source_path).read_text())
    historical = {row["id"] for row in registry["historical_exclusions"]["excluded_documents"]}
    prior = set().union(*(set(registry[f"consumed_epoch{i}_dev"]["document_ids"]) for i in (3, 4, 5, 6, 7)))
    all_ids = {doc["id"] for doc in source["documents"]}
    if historical & prior or len(historical | prior) != 117:
        raise ValueError("Prior exposure identity set changed")
    eligible = all_ids - historical - prior
    if eligible != set(registry["eligible_document_ids"]) or len(eligible) != 306:
        raise ValueError("Frozen eligibility list disagrees with source/history")
    ranked = []
    for doc in source["documents"]:
        if doc["id"] not in eligible: continue
        text_sha = hashlib.sha256(norm(doc["text"]).encode()).hexdigest()
        key = hashlib.sha256(("ruvector-original-contractnli-epoch8-joint-v1|" + str(doc["id"]) + "|" + text_sha).encode()).hexdigest()
        ranked.append((key, text_sha, doc))
    chosen = sorted(ranked, key=lambda item: item[0])[:32]
    if len(chosen) != 32: raise ValueError("Insufficient new source documents")
    output = {"train": [], "dev": []}
    for position, (key, text_sha, doc) in enumerate(chosen):
        role = "train" if position < 24 else "dev"
        if len(doc["annotation_sets"]) != 1: raise ValueError("Ambiguous source annotation")
        for hypothesis_id in plan["hypotheses"]:
            positive = source["labels"][hypothesis_id]["hypothesis"]
            inp = {"state": doc["text"], "questions": {"decision": {
                "type": "choice", "instructions": INSTRUCTION,
                "criteria": {"Yes": positive, "No": "The agreement does not establish the following: " + positive}}}}
            # Selection and role assignment are already final before gold access.
            original = doc["annotation_sets"][0]["annotations"][hypothesis_id]["choice"]
            output[role].append({
                "id": f"original-contractnli:train:epoch8:{role}:{doc['id']}:{hypothesis_id}", "split": role,
                "source": "stanfordnlp/contract-nli@" + plan["source_commit"] + "/train.json",
                "source_group": "original-contractnli:" + str(doc["id"]), "input": inp,
                "evaluation": {"type": "choice", "gold": LABELS[original], "labels": ["Yes", "No"],
                               "source_family": hypothesis_id, "group": "original-contractnli:" + str(doc["id"]),
                               "gold_distribution": None, "original_threeway_label": original},
                "input_sha256": hashlib.sha256(canonical(inp).encode()).hexdigest(),
                "normalized_input_sha256": hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),
                "provenance": {"document_id": doc["id"], "file_name": doc["file_name"], "source_split": "train",
                               "hypothesis_id": hypothesis_id, "document_draw_key": key, "joint_document_rank": position,
                               "normalized_document_sha256": text_sha, "license": "CC-BY-4.0"},
                "exposure": "New project source-document group from official original TRAIN split. TRAIN labels may fit the frozen head; DEV labels may only score the frozen gate. No official test/generalization claim."})
    return output


def allowlist(records, role, data_sha):
    return {"schema_version": 1, "role": role, "queries": len(records),
            "document_groups": len({row["source_group"] for row in records}), "data_sha256": data_sha,
            "original_threeway_label_field": "evaluation.original_threeway_label", "threeway_classes": list(LABELS),
            "binary_mapping": LABELS,
            "records": [{"id": row["id"], "input_sha256": row["input_sha256"], "source_group": row["source_group"],
                         "hypothesis_id": row["provenance"]["hypothesis_id"]} for row in records],
            "contains_labels_or_inputs": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = draw(args.source)
    for role, filename in (("train", "train72.jsonl"), ("dev", "development24.jsonl")):
        path = args.output_dir / filename
        with path.open("x") as stream:
            for record in result[role]: stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        meta = allowlist(result[role], role, sha(path))
        (args.output_dir / (role + "-allowlist.json")).write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({role: {"queries": len(records), "document_groups": len({r["source_group"] for r in records})} for role, records in result.items()}))
