"""Deterministic, label-independent LegalBench transfer diagnostic construction."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return " ".join(text.casefold().split())


def text_hash(text):
    return hashlib.sha256(normalized(text).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def history():
    corpus = {}
    pins = []
    for path in sorted((ROOT / "experiments").rglob("*.txt")):
        if "/corpus/contractnli/" not in str(path):
            continue
        digest = sha(path)
        corpus.setdefault(digest, (str(path.relative_to(ROOT)), normalized(path.read_text())))
        pins.append({"path": str(path.relative_to(ROOT)), "sha256": digest, "kind": "prior_contractnli_corpus"})
    old_texts = set()
    paths = sorted(set((ROOT / "data/legalbench").rglob("*.tsv")) | set((ROOT / "experiments/optimization").rglob("*.tsv")))
    for path in paths:
        with path.open() as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                old_texts.update(normalized(value) for key, value in row.items()
                                 if key not in {"index", "answer"} and value and len(value) > 40)
        pins.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "kind": "prior_classification_tsv"})
    return corpus, old_texts, pins


def draw(write_outputs=True):
    plan = json.loads((HERE / "draw-plan.json").read_text())
    corpus, old_texts, history_pins = history()
    candidates = {}
    excluded_docs = set()
    overlaps = []
    for task in plan["tasks"]:
        with (HERE / "sources" / task / "test.tsv").open() as stream:
            values = list(csv.DictReader(stream, delimiter="\t"))
        candidates[task] = values
        for row in values:
            text = normalized(row["text"])
            corpus_hits = [path for path, old in corpus.values() if text in old]
            if corpus_hits or text in old_texts:
                excluded_docs.add(row["document_name"])
                overlaps.append({"task": task, "index": row["index"], "document_name": row["document_name"],
                                 "normalized_text_sha256": text_hash(text), "prior_corpus_paths": corpus_hits,
                                 "prior_classification_exact_match": text in old_texts})
    def key(task, row):
        return hashlib.sha256(("sota-legal-transfer-v1|" + task + "|" + row["index"] + "|" + text_hash(row["text"])).encode()).hexdigest()
    by_task_doc = {}
    for task, values in candidates.items():
        by_task_doc[task] = {}
        for row in sorted(values, key=lambda item: key(task, item)):
            if row["document_name"] not in excluded_docs:
                by_task_doc[task].setdefault(row["document_name"], []).append(row)
    # Fixed task scarcity order is computed from input availability, never labels.
    task_order = sorted(plan["tasks"], key=lambda task: (len(by_task_doc[task]), task))
    slots = [(task, slot) for task in task_order for slot in range(plan["rows_per_task"])]
    neighbors = {task: sorted(by_task_doc[task], key=lambda doc: (key(task, by_task_doc[task][doc][0]), doc)) for task in task_order}
    doc_owner = {}
    def match(slot, visited):
        for doc in neighbors[slot[0]]:
            if doc in visited:
                continue
            visited.add(doc)
            if doc not in doc_owner or match(doc_owner[doc], visited):
                doc_owner[doc] = slot
                return True
        return False
    for slot in slots:
        if not match(slot, set()):
            raise ValueError("Not enough disjoint unused source documents for preregistered draw")
    assignment = {slot: doc for doc, slot in doc_owner.items()}
    selected = []
    selected_texts = set()
    for task, slot in slots:
        document = assignment[(task, slot)]
        row = next((item for item in by_task_doc[task][document] if text_hash(item["text"]) not in selected_texts), None)
        if row is None:
            raise ValueError("Cross-document duplicate text prevents unique query draw")
        selected_texts.add(text_hash(row["text"]))
        # Only now read a label, after text-only eligibility, matching and selection.
        if row["answer"] not in {"Yes", "No"}:
            raise ValueError("Unexpected official binary label")
        first_instruction = (HERE / "sources" / task / "base_prompt.txt").read_text().split("\n\n", 1)[0].strip()
        inp = {"state": row["text"], "questions": {"decision": {
            "type": "choice", "instructions": first_instruction + "\n\nAnswer Yes or No.",
            "criteria": {"Yes": "Yes", "No": "No"}}}}
        selected.append({
            "id": "legalbench:" + task + ":test:" + row["index"], "split": "confirmation",
            "source": "nguha/legalbench@" + plan["huggingface_revision"] + "/data/" + task + "/test.tsv",
            "source_group": "contractnli:" + document,
            "input": inp,
            "evaluation": {"type": "choice", "gold": row["answer"], "labels": ["Yes", "No"],
                           "source_family": task, "group": document, "gold_distribution": None},
            "input_sha256": hashlib.sha256(canonical(inp).encode()).hexdigest(),
            "normalized_input_sha256": hashlib.sha256(normalized(canonical(inp)).encode()).hexdigest(),
            "query_normalized_sha256": text_hash(row["text"]),
            "provenance": {"official_index": row["index"], "document_name": document,
                           "deterministic_draw_key": key(task, row), "license": "CC-BY-4.0"},
            "exposure": "First known project use of this task/query; public test data, not publisher sealed or model-training contamination proof"})
    selected.sort(key=lambda record: (record["evaluation"]["source_family"], record["id"]))
    if write_outputs:
        with (HERE / "confirmation96.jsonl").open("w") as stream:
            for record in selected:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    overlap_report = {"prior_unique_contractnli_documents": len(corpus), "prior_classification_text_fields": len(old_texts),
                      "prior_source_pins": history_pins, "excluded_document_names": sorted(excluded_docs),
                      "excluded_overlapping_rows": overlaps, "selected_source_documents": len(assignment),
                      "selected_query_texts_unique": len(selected_texts),
                      "document_identity_limit": "Document names are upstream IDs; historical matching also excludes whole source documents if any current clause is a normalized substring of prior corpus. Absence of a match cannot prove unseen training or fuzzy document identity."}
    if write_outputs:
        save(HERE / "historical-overlap.json", overlap_report)
    return selected


if __name__ == "__main__":
    selected = draw()
    print(json.dumps({"rows": len(selected), "source_documents": len({x["source_group"] for x in selected}),
                      "data_sha256": sha(HERE / "confirmation96.jsonl"), "native_calls": 0}))
