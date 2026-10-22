"""Validate original ContractNLI source, novel-document draw and inference boundary."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_original as build


def check_records(records, role, source):
    expected_docs = 8 if role == "dev" else 32
    if len(records) != expected_docs * 3: raise ValueError("Wrong query denominator")
    document_ids = {doc["id"]: doc for doc in source["documents"]}
    groups = {}
    ids, inputs = set(), set()
    for record in records:
        doc = document_ids[record["provenance"]["document_id"]]
        h = record["provenance"]["hypothesis_id"]
        positive = source["labels"][h]["hypothesis"]
        original = doc["annotation_sets"][0]["annotations"][h]["choice"]
        expected_input = {"state": doc["text"], "questions": {"decision": {
            "type": "choice", "instructions": build.INSTRUCTION,
            "criteria": {"Yes": positive, "No": "The agreement does not establish the following: " + positive}}}}
        if record["input"] != expected_input: raise ValueError("Inference contains altered text, hypothesis or unexpected metadata")
        if record["evaluation"]["gold"] != build.LABELS[original] or record["evaluation"]["original_threeway_label"] != original:
            raise ValueError("Original 3-way to binary projection changed")
        if record["split"] != role: raise ValueError("Wrong role")
        if record["id"] in ids or record["input_sha256"] in inputs: raise ValueError("Duplicate query")
        if hashlib.sha256(build.canonical(expected_input).encode()).hexdigest() != record["input_sha256"]:
            raise ValueError("Input hash changed")
        ids.add(record["id"]); inputs.add(record["input_sha256"])
        groups.setdefault(record["source_group"], set()).add(h)
    if len(groups) != expected_docs or any(hs != set(build.HYPOTHESES) for hs in groups.values()):
        raise ValueError("Wrong number of hypotheses or document groups")


def main():
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for item in manifest["files"]:
        if build.sha(HERE / item["path"]) != item["sha256"]: raise ValueError("Frozen source mismatch: " + item["path"])
    archive = json.loads((HERE / "archive-manifest.json").read_text())
    with zipfile.ZipFile(HERE / "sources/original-contractnli.zip") as packed:
        for item in archive["extracted"]:
            if hashlib.sha256(packed.read(item["member"])).hexdigest() != item["sha256"]:
                raise ValueError("Extracted JSON differs from pinned actual archive")
    measured = {}
    for role, filename, split in (("dev", "development24.jsonl", "train"), ("confirmation", "confirmation96.jsonl", "dev")):
        records = [json.loads(line) for line in (HERE / filename).read_text().splitlines()]
        source = json.loads((HERE / "sources" / ("original-" + split + ".json")).read_text())
        check_records(records, role, source)
        measured[role] = records
    if {x["source_group"] for x in measured["dev"]} & {x["source_group"] for x in measured["confirmation"]}:
        raise ValueError("Cross-role document overlap")
    reproduced, exclusion = build.build(write=False)
    if build.canonical(reproduced) != build.canonical(measured): raise ValueError("Exact deterministic source draw mismatch")
    negative_controls = 0
    source = json.loads((HERE / "sources/original-train.json").read_text())
    for mutation in (lambda rows: rows[0]["input"].update(gold="Yes"),
                     lambda rows: rows[0]["evaluation"].update(gold="invalid"),
                     lambda rows: rows[0].update(split="confirmation"),
                     lambda rows: rows[0]["input"]["questions"]["decision"]["criteria"].update(Yes="different predicate")):
        changed = copy.deepcopy(measured["dev"]); mutation(changed)
        try: check_records(changed, "dev", source)
        except (ValueError, KeyError): negative_controls += 1
        else: raise AssertionError("Malformed diagnostic fixture accepted")
    result = {"schema_version": 1, "at": datetime.now(timezone.utc).isoformat(), "checks_passed": True,
              "frozen_source_pins": len(manifest["files"]), "original_archive_jsons_verified": True,
              "dev": {"queries": 24, "document_groups": 8, "source_split": "train"},
              "confirmation": {"queries": 96, "document_groups": 32, "source_split": "dev"},
              "roles_document_disjoint": True, "full_input_and_original_binary_projection_replayed": True,
              "label_dependent_sampling": False, "negative_controls_rejected": negative_controls,
              "new_native_or_paid_calls": 0, "official_score": None, "official_rank": None}
    (HERE / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__": main()
