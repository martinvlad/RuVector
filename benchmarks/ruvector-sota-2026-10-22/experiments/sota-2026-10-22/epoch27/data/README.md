# Epoch27 fixed project DEV inputs

This bank contains eight original ContractNLI TRAIN documents, each paired with
the three fixed original hypotheses `nda-17`, `nda-7`, and `nda-3` (24 cases).
The document order is `609, 380, 592, 454, 559, 515, 349, 223`. A metadata-only
deterministic draw fixed these identities before source text, lengths,
annotation choices or model outputs were inspected. No redraw or class
balancing is allowed after exposure or failure.

Source: Yuta Koreeda and Christopher D. Manning (2021), *ContractNLI: A Dataset
for Document-level Natural Language Inference for Contracts*.
[Official repository and pinned revision](https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9).
The original `train.json` source blob is 7,608,211 bytes, SHA256
`dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5`.
The dataset is licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/);
the unchanged full license is in `LICENSE-CC-BY-4.0.txt`.

Transformations: select exactly the eight original TRAIN documents and three
original hypotheses, preserve their text exactly, and add case IDs, source
groups and canonical input hashes. The input projection contains no annotation
choices or gold evidence. `dev.inputs.json` has SHA256
`dc57e5d4553677e7d11795436e615c0374c84943df69590748a9a71e15f20e35`;
`input-identities.json` records exact and normalized input/document hashes.
The independent projection and alias audit are recorded separately.

These are project DEV inputs, not an official heldout benchmark. Their first
input exposure permanently spends all eight document identities for project
DEV, including unsuccessful attempts: 261 original TRAIN documents are exposed,
138 remain unreserved, and 24 remain reserved. The complete public annotated
source JSON is parsed in RAM during projection; label-field isolation is
logical and is not OS-enforced secrecy. Only the fixed 24 annotation choices
may be joined after complete, sealed 72-prediction outputs and verified process
closure, never during model execution or input selection.

The pinned BART MNLI head's original weight bytes have a documented 2020
publication history. That chronology supports exclusion of the later public
ContractNLI labeled dataset from the original head training; it does not prove
foundation-text decontamination or rule out later publisher reselection.
Foundation-text/fuzzy contract overlap and later publisher reselection remain
unknown. Three correlated hypotheses per document do not form 24 independent
sampling units. A retrieved-context NotMentioned prediction is not proof of
legal absence from the full agreement.

The actual full native104/RRF10 champion comparator is not materialized in
this experiment. Confirmation is therefore `[]` and remains HOLD regardless
of descriptive DEV results. This bank cannot authorize benchmark acceptance,
champion replacement, submission, a population improvement claim or an
official score/rank claim. The existing native104/RRF10 champion is retained.
