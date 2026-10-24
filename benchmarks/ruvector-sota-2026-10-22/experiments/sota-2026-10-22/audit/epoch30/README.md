# Epoch30 fixed TRAIN and DEV inputs

This new project diagnostic fixes original ContractNLI TRAIN document IDs
`237,120,187,422,464,207,294,250` for project TRAIN and
`594,343,394,103,403,481,154,306` for project DEV. Each uses the exact original
hypotheses `nda-17`, `nda-7`, and `nda-3`:24 TRAIN and24 DEV cases.

Source: Yuta Koreeda and Christopher D. Manning(2021), *ContractNLI: A Dataset
for Document-level Natural Language Inference for Contracts*.
Official revision: https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9 .
The original train.json is7,608,211bytes, SHA256
`dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5`.
The corpus is CC BY4.0; LICENSE-CC-BY-4.0.txt preserves the full licence.
Model and runtime licences are separate from corpus-text licensing.

A deterministic metadata-only draw fixed IDs and hypotheses before raw source
text, lengths, choices, evidence or model outputs were accessed. It used E29's
precomputed canonical SHA catalog and excluded all277 exposed and24 protected
IDs, their exact normalized aliases and184 cross-split metadata hashes. All122
unused IDs passed those checks;16distinct canonical groups were fixed once.
No length/class filter, redraw or replacement is allowed.

Transformations preserve exact selected document/hypothesis text and add case
IDs, roles and canonical hashes. The frozen input-only builder parses the complete
public annotated JSON into RAM but traverses only selected document id/text and
hypothesis descriptor fields. This is logical field isolation, not OS-enforced
label secrecy. It read no annotation choices or evidence lists. The identity
auditor reads input texts and historical metadata, not the annotated source.

The first input projection permanently spends all16 fixed IDs, including failures.
The423original-document pool is now293exposed,106unreserved and24reserved.
All protected IDs and historical E29 HOLD/retirements remain unchanged.
Calibration and confirmation are empty.

TRAIN choices may be joined exactly24times only inside the admitted TRAINworker,
after complete source/input/runtime freeze. No evidence lists or other-role
choices may be read. DEV choices may be joined exactly24times only by the frozen
independent scorer after all96predictions, raw structure audit and physical closure.
No choice-projection file belongs to premeasurement source pins.

The study uses one fixed24-step LoRA+pretrained-classifier fit, then a separately
bounded DEVworker after trained-parameter sealing and actual MODEL Git readback.
Original BART native24 predictions precede the exact learned-state application;
adapted native/lexical/positional predictions use the same fixed learned artifact.
Only8DEVdocument groups underlie the24correlated hypotheses. No official heldout
benchmark, population superiority, exclusive LoRA causal effect, champion replacement,
confirmation, full104 retry, submission or official rank is established.

The original2020BART weight chronology supports exclusion of later ContractNLI
supervision from the original released head; foundation-text/fuzzy overlap and
undocumented later publisher reselection remain unknown. Original full-contract
labels may not be supported by retrieved excerpts; NotMentioned is not proof of
legal absence. Native104/RRF10 remains the champion regardless of this diagnostic.
