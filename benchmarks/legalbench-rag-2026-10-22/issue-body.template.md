We are sharing a reproducible RuVector retrieval development study and would appreciate methodology review and guidance on your preferred venue for reporting custom-draw results.

**Immutable report and offline replay kit:** <IMMUTABLE_REPORT_URL>

The Python standard-library replay reconstructs1,680 fixed RRF10/RRF20 rankings and35,280 saved precision/recall/F1 scalars at k=1,2,4,8,16,32,64, plus the exact original2,000-draw group-bootstrap distributions. It uses finite JSON rank lists and document/character geometry; it makes no model, native-search, HTTP or paid API calls. An independent kit review is supplied alongside the report when available.

| Observed study | Recipe | Recall@8 | Precision@8 |
|---|---|---:|---:|
| Custom776-query development draw | Confirmed RRF10 pipeline |36.363598%|5.731471%|
| Same draw | RRF20 development contender |36.619529%|5.828935%|
| Reused historical64-query MAUD study | RRF10 |21.064582%|3.501953%|
| Same historical study | RRF20 |21.802657%|3.633984%|

Important scope and limitations:

- The776 questions contain194/source and search a shared72-document pool with17,403 non-overlapping500-character chunks. The draw and source-derived sampling are disclosed; we have not established that its questions equal the canonical paper mini split. This is a custom observed development comparison, not a full benchmark or paper leaderboard reproduction.
- The latest continuation searched37 cached-ranking policies, followed by a separate selected verification replay. Earlier embedding/reranker/native pipeline exploration also occurred. All37 aggregate outcomes and source hashes are included;37 is not the full project's adaptive-search total.
- Both recipes use the same hosted `qwen/qwen3-embedding-8b` responses/native RuVector ranks and the same FP32 MiniLM reranking outputs, then equal-weight rational RRF on native64/reranked64 with c=10 or20 and ascending original numeric-ID ties. These are complete-pipeline results; they do not isolate an index-only gain. The hosted embedding model's underlying weight revision is not cryptographically verified.
- Development recall/precision gains are+0.255931/+0.097464 percentage points. Their72-group95% intervals are[-0.520651,+1.054098] and[-0.039392,+0.250169] points, both crossing zero. Diagnostic folds stay within observed development.
- The historical64 comparison reuses already observed eight-document MAUD outcomes. Its recall/precision gain intervals are[-1.570023,+3.252425] and[-0.384671,+0.647549] points; both cross zero. It is not a new unused confirmation. RRF10 remains the confirmed recipe.
- A separately prepared96-query study remains unscored after its GPU launch window expired; no GPU was rented and no quality result exists. No official rank, SOTA result, full162-task LegalBench result or independent inference reproduction is claimed.
- The kit retains pinned author metric sources/MIT notice, exact source provenance, prior independent audits and relevant per-source license notes. It omits raw corpus/query/answer text, credentials, vectors, weights and logits. Saved-output replay alone cannot prove a hosted model's immutable weight identity.

In particular, feedback on the custom-draw reporting protocol and the relationship to the canonical mini question selection would be useful; we saw the question in issue#2 and do not want to overstate comparability. Thank you for releasing the benchmark and evaluator.
