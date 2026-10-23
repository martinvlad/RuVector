# Epoch10: evidence and clause-role learner rejected

One real native RuVector process completed TRAIN72 plus new DEV24 in 209.731997 seconds, including initialization, five fixed TRAIN fits and cleanup. The frozen development gate failed. The submitted Native104/RRF10 champion is unchanged; confirmation48 was never attempted and no publisher submission or email was sent.

This is a source-licensed original ContractNLI three-predicate NDA pilot, not a score on current JevBench300, full LegalBench or ClaimBench. TRAIN72/24documents reused previously exposed training bytes. DEV24/8different documents was drawn once without labels before measurement. The existing48/16document confirmation bank remains project-model-unused. Pretraining overlap is unknown. All old easy48, Legal96 and original-dev confirmation96 remain DEV forever.

| Frozen DEV arm | Correct /24 | Binary Brier | NLL |
| --- | ---: | ---: | ---: |
| Native RuVector evidence + frozen learned reader | 17 | 0.4066192724 | 0.5852220228 |
| Same learned reader, lexical evidence | 14 | 0.4575333788 | 0.6459060835 |
| Same learned reader, positional evidence | 17 | 0.3833582395 | 0.5631454693 |
| Native104 on identical primary packed excerpts | 17 | 0.4985879821 | 0.6917351499 |

Acceptance required at least two additional correct answers against every control, no worse Brier/NLL against all three, and a strict proper-score gain against both matched reader controls. Ties against positional evidence and excerpt Native104 failed the accuracy gate; positional evidence also had better proper scores. The excerpt baseline is not a rerun of the full submitted champion. Eight DEV document groups provide limited statistical precision; paired document confidence intervals do not establish superiority.

The fixed reader reused Xenova/DeBERTa-v3-base-mnli-fever-anli revision72a1ce83a0144efaf828b3c3844320a61197a53d (quantized ONNX SHA256 ab9da76bb06054ea6b921560c1ecf5683a9e4d96f0ea73d78d3b4a8990aea882). Raw E/Neutral/C logits fed shared clause-role/scope features and a three-way residual head. Three document-fold annotation-overlap auxiliary fits plus one all-TRAIN auxiliary and one residual fit each ran400 fixed Adam steps. The auxiliary target is any positive annotation-character intersection, not evidence sufficiency or absence. Decision fitting used out-of-fold probabilities; inference used the all-TRAIN auxiliary, a disclosed distribution shift. TRAIN cache, artifact and fit lock preceded any DEV read. No calibration, model/feature grid, fallback or retry was performed.

Independent saved-output replay verified all190 frozen pins,96 successful HTTP requests (72TRAIN feature acquisitions +24DEV evaluations),288 NLI singleton pairs,610 BGE texts/174BGE batches, native calls, source offsets, numerical retention, scorer outputs and all five fitted numerical histories. All96 saved native full rankings matched saved-vector cosine ranks; repeated same-context logit drift was zero. Those checks do not establish semantic correctness or generalization.

DEV whole-HTTP latency p50 was1.905440s and p95 was3.007384s, including all three NLI arms, excerpt Native104, embeddings and indexing. It is not primary-only deployment latency. The worker peak RSS was1,331,503,104bytes; process and child high-water marks are not simultaneous total memory. The process used CPU affinity0,1 and two ORT threads. Zero HTTP/model execution errors, paid API calls or GPU calls occurred. The single epoch attempt is closed; its unused conditional slot is not retry budget. Lifetime checkpoints now record13 attempts,11 completed batches,735 successful HTTP requests (144TRAIN features +591 evaluation diagnostics), and two historical failed HTTP requests.

The official JevBench open-weights Capability leader observed from boardv1.7.47 remains Chon-1.0-12B at85.3. Only the original acknowledgement of submission7FEA2738 was found;115 was its original queue position, never rank. No official RuVector score/rank is established. ClaimBench's live decision-model leader changed to decision/d1-ultra at100.0%; four language models also show100%. Full ClaimBench data, scorer, license and submission access remain unverified, so no RuVector ClaimBench pilot score or placement is claimed. Any future retrieval must stay within supplied10-K excerpts; a retrieval miss cannot establish insufficient evidence.

Research continues from saved failures rather than a rescue selected on this DEV set. The next distinct hypothesis should improve typed contradiction, actor/action and exception reasoning using verified pretrained/source provenance and native evidence, with fresh frozen development and preserved unused confirmation gates. Official SOTA still requires a matching publisher result, rank and eligibility.
