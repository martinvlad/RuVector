# Epoch 9: broader pretrained NLI reader rejected

This internal ContractNLI NDA pilot used actual native RuVector evidence selection and one frozen, pretrained three-way NLI reader. The new licensed document split was frozen before model selection. Training and calibration were empty.

| DEV arm | Correct / 24 | Brier | NLL |
| --- | ---: | ---: | ---: |
| Native RuVector evidence + new reader | 11 | 0.7175704900 | 0.9995050324 |
| Same reader, lexical retrieval | 7 | 0.8287010157 | 1.1821149486 |
| Same reader, positional retrieval | 16 | 0.5310243475 | 0.8375419211 |
| Native104 on the primary arm's identical excerpts | 14 | 0.4995572963 | 0.6927044808 |

The frozen DEV gate failed. The submitted Native104 and RRF10 champions remain unchanged. The separately frozen confirmation bank of 48 questions from 16 other documents was not run and remains reserved. DEV's eight documents are permanently exposed.

One actual process batch completed in 58.68 seconds, including initialization and cleanup, with two CPU cores and zero paid or GPU calls. All 24 HTTP requests succeeded. The run made 72 NLI forward calls and actual native searches. Whole-request p50/p95 latency was 2.14065/3.61659 seconds; this includes all retrieval controls and the Native104 excerpt diagnostic. Process peak RSS was 1,158,332,416 bytes; this is not a sum of simultaneous process memory.

Independent replay reproduced the saved metrics, token IDs, logits, probabilities, native receipts and resource records. ANN top-two agreement was 24/24, candidate-set agreement 23/24, and full-order agreement 21/24. All disagreements remain in the evidence.

The reader predicted Yes 21 times against ten Yes labels; all five Contradictions were predicted Entailment. Positional retrieval retained less annotated evidence than native retrieval, so its advantage is not explained by greater annotation retention. Annotation coverage does not establish sufficiency. These are descriptive findings from eight document groups.

The next proposed hypothesis is a TRAIN-only learner for clause roles, scope and evidence. It has not been implemented or measured. A future experiment must freeze its own source, training, DEV and calibration identities while preserving the unused confirmation bank.

`EPOCH_MANIFEST.json`, `USED_IDENTITIES.json`, `REJECTION_LEDGER.json` and `../audit/epoch9/actual-independent-v1.json` retain the exact results. The active saved-evidence audit implementation is `../audit/epoch9/replay_actual_v2.py`; its two asset-directory corrections are documented in `replay-method-correction-v1.json`. The original plan-pinned audit script remains immutable. No scorer, gate or measured source changed.

Use the checkpoint's reviewed `restore_checkpoint.py` and `bootstrap.py` for source/data/result reconstruction. Runtime and model assets require the separately reviewed, hash-pinned restoration helpers. Reconstruction does not execute archived benchmark controllers. No current JevBench Capability, full LegalBench or ClaimBench score or official placement is established by this pilot.
