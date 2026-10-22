"""Reproduce frozen project-unused DEV/confirmation roles; no model execution."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent / "epoch3/sources/original-train.json"
INSTRUCTION = "Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned."
LABELS = {"Entailment": "Yes", "Contradiction": "No", "NotMentioned": "No"}
FILENAMES = {"dev": "development24.jsonl", "confirmation": "confirmation48.jsonl"}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def norm(value): return " ".join(value.casefold().split())


def select(source_path=DEFAULT_SOURCE):
    plan = json.loads((HERE / "draw-plan.json").read_text())
    registry = json.loads((HERE / "eligibility-manifest.json").read_text())
    if sha(HERE / "eligibility-manifest.json") != plan["eligibility_manifest_sha256"]:
        raise ValueError("Frozen eligibility registry changed")
    if sha(source_path) != plan["source_sha256"]:
        raise ValueError("Official original TRAIN source changed")
    source = json.loads(Path(source_path).read_text())
    previous = set(registry["excluded_document_ids"])
    eligible = {doc["id"] for doc in source["documents"]} - previous
    if len(previous) != 149 or len(eligible) != 274 or eligible != set(registry["eligible_document_ids"]):
        raise ValueError("Exposed/eligible source identity set changed")
    cross_ids = {doc["document_id"] for doc in registry["cross_split_documents"]}
    cross_hashes = {doc["normalized_document_sha256"] for doc in registry["cross_split_documents"]}
    ranked = []
    for doc in source["documents"]:
        if doc["id"] not in eligible: continue
        text_sha = hashlib.sha256(norm(doc["text"]).encode()).hexdigest()
        if doc["id"] in cross_ids or text_sha in cross_hashes:
            raise ValueError("Official DEV/TEST source identity or text collision")
        key = hashlib.sha256((plan["salt"] + str(doc["id"]) + "|" + text_sha).encode()).hexdigest()
        ranked.append((key, text_sha, doc))
    chosen = sorted(ranked, key=lambda row: row[0])[:24]
    replay = [{"joint_document_rank": i, "document_id": doc["id"],
               "role": "dev" if i < 8 else "confirmation", "normalized_document_sha256": h,
               "document_draw_key": k} for i, (k, h, doc) in enumerate(chosen)]
    selection = json.loads((HERE / "document-selection.json").read_text())
    if selection["draw_plan_sha256"] != sha(HERE / "draw-plan.json") or replay != selection["documents"]:
        raise ValueError("Label-independent frozen document roles changed")
    return plan, source, chosen


def draw(source_path=DEFAULT_SOURCE):
    plan, source, chosen = select(source_path)
    output = {"dev": [], "confirmation": []}
    # Document selection/roles have been frozen and verified before any gold access.
    for position, (key, text_sha, doc) in enumerate(chosen):
        role = "dev" if position < 8 else "confirmation"
        if len(doc["annotation_sets"]) != 1: raise ValueError("Ambiguous source annotation")
        for hypothesis_id in plan["hypotheses"]:
            positive = source["labels"][hypothesis_id]["hypothesis"]
            inp = {"state": doc["text"], "questions": {"decision": {
                "type": "choice", "instructions": INSTRUCTION,
                "criteria": {"Yes": positive, "No": "The agreement does not establish the following: " + positive}}}}
            original = doc["annotation_sets"][0]["annotations"][hypothesis_id]["choice"]
            output[role].append({
                "id": f"original-contractnli:train:epoch9:{role}:{doc['id']}:{hypothesis_id}", "split": role,
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
                "exposure": "Internal project-unused public original ContractNLI NDA pilot. No fit/calibration. DEV only frozen gate; confirmation labels only scorer/auditor after frozen gate. Public source is not sealed or proof against pretraining contamination."})
    return output


def allowlist(records, role, data_sha):
    return {"schema_version": 1, "role": role, "queries": len(records),
            "document_groups": len({row["source_group"] for row in records}), "data_sha256": data_sha,
            "threeway_classes": list(LABELS), "binary_mapping": LABELS,
            "records": [{"id": row["id"], "input_sha256": row["input_sha256"], "source_group": row["source_group"],
                         "hypothesis_id": row["provenance"]["hypothesis_id"]} for row in records],
            "contains_labels_or_inputs": False, "fit_permitted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = draw(args.source)
    for role, filename in FILENAMES.items():
        path = args.output_dir / filename
        with path.open("x") as stream:
            for record in result[role]: stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        with (args.output_dir / (role + "-allowlist.json")).open("x") as stream:
            stream.write(json.dumps(allowlist(result[role], role, sha(path)), indent=2) + "\n")
    print(json.dumps({role: {"queries": len(records), "document_groups": len({r["source_group"] for r in records})} for role, records in result.items()}))
