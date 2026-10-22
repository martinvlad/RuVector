"""Frozen document-disjoint original ContractNLI dev diagnostic; no inference."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HYPOTHESES = ("nda-17", "nda-7", "nda-3")
INSTRUCTION = "Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned."
LABELS = {"Entailment": "Yes", "Contradiction": "No", "NotMentioned": "No"}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def norm(text): return " ".join(text.casefold().split())
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def docname(value): return re.sub(r"\.(?:pdf|txt)$", "", urllib.parse.unquote(value).casefold())


def history():
    previous = [json.loads(line) for line in (HERE.parent / "confirmation96.jsonl").read_text().splitlines()]
    names = {docname(row["evaluation"]["group"]) for row in previous}
    clauses = {norm(row["input"]["state"]) for row in previous}
    overlap = json.loads((HERE.parent / "historical-overlap.json").read_text())
    names.update(docname(name) for name in overlap["excluded_document_names"])
    body_hashes = set()
    historical_pins = []
    for path in sorted((ROOT / "experiments").rglob("*.txt")):
        if "/corpus/contractnli/" not in str(path): continue
        names.add(docname(path.name))
        body_hashes.add(hashlib.sha256(norm(path.read_text()).encode()).hexdigest())
        historical_pins.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    tsvs = set((ROOT / "data/legalbench").rglob("*.tsv")) | set((ROOT / "experiments/optimization").rglob("*.tsv"))
    for path in sorted(tsvs):
        with path.open() as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                clauses.update(norm(text) for key, text in row.items() if key not in {"index", "answer"} and text and len(text) > 40)
        historical_pins.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    return names, clauses, body_hashes, historical_pins


def build(write=False):
    plan = json.loads((HERE / "draw-plan-v2-original-contractnli.json").read_text())
    names, clauses, body_hashes, prior_pins = history()
    all_records, report, selected_groups = {}, {}, set()
    for source_split, role, requested in (("train", "dev", 8), ("dev", "confirmation", 32)):
        source = json.loads((HERE / "sources" / ("original-" + source_split + ".json")).read_text())
        exclusions, eligible = [], []
        for doc in source["documents"]:
            body = norm(doc["text"])
            digest = hashlib.sha256(body.encode()).hexdigest()
            reasons = []
            if docname(doc["file_name"]) in names: reasons.append("previous_document_name")
            if digest in body_hashes: reasons.append("previous_normalized_fulltext")
            if any(clause in body for clause in clauses): reasons.append("previous_query_clause_in_document")
            if reasons:
                exclusions.append({"id": doc["id"], "file_name": doc["file_name"], "normalized_text_sha256": digest, "reasons": reasons})
            else:
                key = hashlib.sha256(("ruvector-original-contractnli-v1|" + source_split + "|" + str(doc["id"]) + "|" + digest).encode()).hexdigest()
                eligible.append((key, doc))
        if len(eligible) < requested:
            raise ValueError("Insufficient unused original ContractNLI documents: " + source_split)
        chosen = sorted(eligible, key=lambda pair: pair[0])[:requested]
        records = []
        for key, doc in chosen:
            group = "original-contractnli:" + str(doc["id"])
            if group in selected_groups: raise ValueError("Document reused across roles")
            selected_groups.add(group)
            if len(doc["annotation_sets"]) != 1: raise ValueError("Ambiguous source annotation set")
            for hypothesis_id in HYPOTHESES:
                hypothesis = source["labels"][hypothesis_id]["hypothesis"]
                inp = {"state": doc["text"], "questions": {"decision": {
                    "type": "choice", "instructions": INSTRUCTION,
                    "criteria": {"Yes": hypothesis, "No": "The agreement does not establish the following: " + hypothesis}}}}
                # No label is accessed until document selection is immutable.
                original_label = doc["annotation_sets"][0]["annotations"][hypothesis_id]["choice"]
                records.append({
                    "id": f"original-contractnli:{source_split}:{doc['id']}:{hypothesis_id}", "split": role,
                    "source": "stanfordnlp/contract-nli@" + plan["source_commit"] + "/" + source_split + ".json",
                    "source_group": group, "input": inp,
                    "evaluation": {"type": "choice", "gold": LABELS[original_label], "labels": ["Yes", "No"],
                                   "source_family": hypothesis_id, "group": group, "gold_distribution": None,
                                   "original_threeway_label": original_label},
                    "input_sha256": hashlib.sha256(canonical(inp).encode()).hexdigest(),
                    "normalized_input_sha256": hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),
                    "provenance": {"document_id": doc["id"], "file_name": doc["file_name"], "source_split": source_split,
                                   "hypothesis_id": hypothesis_id, "document_draw_key": key,
                                   "normalized_document_sha256": hashlib.sha256(norm(doc["text"]).encode()).hexdigest(),
                                   "license": "CC-BY-4.0"},
                    "exposure": "New project-level document group from official original ContractNLI split; public data, not proof of unseen model training."})
        all_records[role] = records
        report[role] = {"source_split": source_split, "source_documents": len(source["documents"]),
                        "eligible_documents": len(eligible), "selected_documents": requested,
                        "queries": len(records), "excluded_documents": exclusions}
    report.update(prior_source_pins=prior_pins, model_calls=0,
                  novelty_limit="Exact document names, normalized fulltext, and verbatim casefold/whitespace prior query substrings checked; unknown/fuzzy provenance overlap and model pretraining contamination not ruled out.")
    if write:
        for role, name in (("dev", "development24.jsonl"), ("confirmation", "confirmation96.jsonl")):
            with (HERE / name).open("w") as stream:
                for record in all_records[role]: stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        (HERE / "historical-exclusions.json").write_text(json.dumps(report, indent=2) + "\n")
    return all_records, report


if __name__ == "__main__":
    records, report = build(write=True)
    print(json.dumps({role: {"queries": len(rows), "document_groups": len({row["source_group"] for row in rows})} for role, rows in records.items()}))
