# Epoch 10 data contract

The licensed source is Stanford NLP's ContractNLI dataset, pinned to commit `eced6528dd3c1d14d73f9a87df8f7bdbc03126f9` under CC BY 4.0. Attribution and the license are preserved here and in each projected record's source/provenance fields. The source repository is https://github.com/stanfordnlp/contract-nli.

TRAIN72 is an exact copy of epoch8's 72 already-exposed training questions from 24 documents. It is not fresh benchmark evidence. The separate TRAIN-only annotation sidecar binds those exact IDs, input hashes, original three-way labels and source character spans. These annotations may supervise annotation-coverage prediction during fitting. Coverage is not semantic sufficiency, and a retrieval miss does not establish absence.

DEV24 comes from eight new original-training-source documents selected once by a text/ID hash ranking. All 157 previously exposed training-source documents and the 16 reserved confirmation documents were excluded. Document roles were frozen before projecting new DEV labels. Calibration is empty. Exact-ID and normalized full-document collisions against historical and official dev/test registries were rejected.

The existing epoch9 confirmation48 bank remains unchanged at SHA256 `850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50`. Its metadata-only allowlist is copied here. Confirmation labels were not used for data selection or fitting, and the fitter must not load the full original-training-source file. Inference receives only `state` and `questions`.

`build.py --source /path/to/original-train.json --output-dir /new/output` replays the five canonical TRAIN/DEV files using only the frozen eligibility/draw/selection metadata, exact TRAIN72 reference and pinned original source. `validate.py --source /path/to/original-train.json` checks source hashes, gold projection, role separation and eight mutation controls, then performs a clean-directory byte-exact rebuild. Neither command invokes native RuVector, a model or paid services. The source corpus and raw benchmark pages are excluded from publication.

The pilot covers three NDA predicates and is internal public-source evaluation. It does not establish a full LegalBench score, current JevBench Capability score, ClaimBench score, sealed-test generalization or freedom from pretraining overlap.

The fresh official benchmark refresh found Chon-1.0-12B still leading Jev-class Capability at 85.3. ClaimBench's current decision-model leader is now `decision/d1-ultra` at 100.0%; `decision/decider-v1.2` remains at 99.694%. Four language-model rows are also at 100%. Only aggregate results and public examples are verified; full ClaimBench questions, scorer, license and submission access remain unverified. No RuVector ClaimBench result exists.
