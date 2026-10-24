# Epoch29 fixed source roles — data admission HOLD

The fixed proposal selected eight original ContractNLI TRAIN documents for project TRAIN:
`309, 369, 386, 593, 579, 505, 536, 383`, and eight for project DEV:
`548, 203, 492, 252, 162, 200, 529, 589`, each with the exact original hypotheses
`nda-17`, `nda-7`, and `nda-3`. The metadata-only draw preceded text, length,
choice, evidence and model access. No redraw is permitted.

Source: Yuta Koreeda and Christopher D. Manning (2021), *ContractNLI: A Dataset
for Document-level Natural Language Inference for Contracts*.
Official revision: https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9 .
The original `train.json` is 7,608,211 bytes with SHA256
`dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5`.
The dataset is CC BY 4.0; the unchanged legal text is in
`LICENSE-CC-BY-4.0.txt`. Model/code licences are separate from dataset text.

Transformations: preserve exact selected document and hypothesis text, add case
IDs, role metadata and canonical hashes. The builder parses the complete public
annotated JSON in RAM but accesses only document id/text and hypothesis descriptor
fields. This is logical field isolation, not OS-enforced label secrecy. It
accessed no annotation choices or evidence lists. TRAIN choices were reserved
for a future admitted TRAIN worker; that admission did not occur.

The builder wrote `data/train.inputs.json` (24 unlabelled records) and its
identity metadata. On the first DEV document, 548, it stopped at the frozen
normalized-document alias check: the hash
`769fe472e0405060afb6bb91fe8ac3a5abf547e20d342ddcb6d97c882ad29f3a`
matches already exposed E27 DEV document 515. `data/dev.inputs.json` was never
created. The partial TRAIN bank is retained as provenance and does not authorize
training. No choice, evidence, model, tokenizer, native, optimizer or inference
activity occurred in this projection.

The frozen reservation conservatively retires all 16 selected IDs on any
projection failure, including remaining untraversed DEV documents. The original
423-document pool is now recorded as 277 exposed, 122 unreserved and 24 reserved.
Reserved IDs and their roles remain unchanged; calibration and confirmation
are empty. The data-admission HOLD cannot be repaired by dropping or replacing
document 548 or changing the normalization rule.

These are project development roles, not an official heldout benchmark. No
trained model or diagnostic improvement exists. E28's rejection and the
Native104/RRF10 champion remain unchanged. No benchmark acceptance, promotion,
submission, official rank, or confirmation is authorized. Foundation-text/fuzzy
overlap and undocumented later publisher reselection remain unknown.
