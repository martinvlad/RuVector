# Reproducible RuVector retrieval development results

This is a small **saved-output replay kit** for a custom, observed LegalBench-RAG
development draw. It reconstructs two fixed rank-fusion recipes and their
character-span metrics. It does not execute embeddings, RuVector search, a
reranker, HTTP requests, or paid APIs. It is not a full162-task LegalBench result
or an official leaderboard submission.

Run with Python3.10+ and no third-party packages:

```sh
python3 -I -S replay.py --out /tmp/ruvector-rag-replay.json
```

The kit is independent of the original workspace and evidence ZIPs. Its replay
verifies the public per-file manifest; 1,680 exact Fraction-based rankings;
35,280 saved author-metric scalars; every source and all seven cutoffs; and both
original 2,000-draw document-group bootstrap distributions. The source extraction
builder requires the original local evidence tree and existing NumPy; it is not
the portable replay entry point.

## Results and scope

| Observed study | Recipe | Recall@8 | Precision@8 |
|---|---|---:|---:|
| Custom development,776queries | Confirmed pipeline, equalRRF10 | 36.363598% | 5.731471% |
| Same custom development | Development contender, equalRRF20 | 36.619529% | 5.828935% |
| Reused historical64MAUD queries | Confirmed pipeline, equalRRF10 | 21.064582% | 3.501953% |
| Same historical64 | Development contender, equalRRF20 | 21.802657% | 3.633984% |

The776 queries contain194 per source: PrivacyQA, ContractNLI, CUAD and MAUD.
They search a shared72-document pool with17,403 non-overlapping500-character
chunks. This custom draw follows a disclosed source-derived sampling procedure;
it is **not proven to be the canonical paper mini question split**. It is also
not the complete LegalBench-RAG dataset. We make no directly reproduced paper
leaderboard, SOTA, official rank or index-only causal improvement claim.

The latest continuation searched37 cached-ranking policies:32 in the first
round and5 diversity policies in the next, followed by one separate selected
verification replay. Earlier embedding, reranker and native-pipeline exploration
also occurred. The37 count is not the whole project's adaptive-search total.
`search-history.json` records every policy's original aggregate outcomes and
acceptance diagnostics. This minimal kit replays the fixed RRF10 and selected
RRF20 pair, not the entire128-candidate/diversity search history. Hash-bound
original independent audits and provenance are included.

At8, the descriptive paired development gains are recall+0.255931 percentage
points and precision+0.097464 points. Their72-document-group95% intervals are
recall[-0.520651,+1.054098] points and precision[-0.039392,+0.250169] points.
Both include zero. The diagnostic fourfold grouping stays within observed
development; it is not unseen cross-validation.

The64-query MAUD comparison reuses an already observed eight-document study,
searched over80 documents/22,644 chunks. It was previously used to confirm the
earlier pipeline against its own matched baseline; the present reuse cannot
confirm a later contender. The current RRF20-versus-RRF10 gains are recall
+0.738075 points and precision+0.132031 points. Their descriptive eight-group95%
intervals are recall[-1.570023,+3.252425] and precision[-0.384671,+0.647549]
points; both include zero. A separate proposed96-query confirmation remains
**PREPARED_UNSCORED** after a missed GPU launch window. No GPU was rented and no
quality outcome exists for it. The confirmed recipe therefore remains RRF10.

## Pipeline and exact replay semantics

The complete retrieval pipeline used hosted `qwen/qwen3-embedding-8b` through
the fixed DeepInfra route, actual native RuVector retrieval, and
`cross-encoder/ms-marco-MiniLM-L6-v2` FP32 reranking. The reranker revision is
`233902d25c440f23af6f7d6e94d2946bac0bee0a`, with weight SHA256
`821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae`.
The hosted embedding service's underlying weight revision was **not
cryptographically verified**. Saved service/model/native receipts and prior
audits do not remove that limitation. No hosted model or native execution is
reproduced by this kit.

Both recipes take the same saved native top64 and the same top64 of the prior
verified FP32 reranking pool. For each list position r starting at1, add
1/[2(c+r)] to that chunk's exact rational score. Use c=10 for the confirmed
recipe and c=20 for the contender, sort by descending exact score, and break
ties by ascending original integer chunk ID. Retain64 hits.

At each k in1,2,4,8,16,32,64, the pinned author's `QAResult` sums character
overlap for every retrieved/gold pair in the **same document**. Divide by summed
retrieved lengths for precision and summed gold lengths for recall, and compute
per-query F1. There is no union-merging of retrieved spans. Aggregate query
metrics within each source; the development aggregate weights the four equally
sized sources equally. The pinned author sources are retained in `upstream/`
for inspection; the offline replay independently implements that arithmetic.

`data/` contains only ordered rank lists, selected output IDs, saved metrics,
document names, necessary chunk/gold coordinates, source indices, query hashes
and original seeded bootstrap indices. It omits raw question/answer/document
text, embedding vectors, model weights and logits. Geometry includes5,764
referenced development chunks and1,744 historical chunks, preserving original
chunk IDs. Removing unrelated geometry changes neither rank fusion nor metrics.
Query hashes and indices provide bindings to the original licensed inputs;
they do not by themselves prove an underlying model prediction was authentic.

## Provenance and licenses

Author code revision: `431bc8f2488a81569ab7259fa633dcc50ab77f9a` in
[ZeroEntropy LegalBench-RAG](https://github.com/zeroentropy-ai/legalbenchrag).
Corpus/benchmark mirror revision:
`2b9c248bc8179ef0908fd6ba01d50b156facd48b` at
[awinml/legalbench-rag](https://huggingface.co/datasets/awinml/legalbench-rag).
Exact local source hashes, transformations and prior archive identities are in
`extraction-provenance.json`; original source document hashes are in
`evidence/corpus-source-receipts.json`. The two original independent retrieval
audits, selected recipe, frozen plans, pre-quality abort and unscored96 closure
are included under `evidence/`.

The upstream metric software carries the included ZeroEntropy MIT license.
Underlying benchmark and source-document terms remain separate; see
`LICENSES.md` and the pinned dataset card. This kit does not relicense them.
Please cite Pipitone and Houir Alami(2024), LegalBench-RAG,
[arXiv2408.10343](https://arxiv.org/abs/2408.10343), plus the upstream source
datasets identified in `LICENSES.md`.

The publication prefix is `benchmarks/legalbench-rag-2026-10-22/` in
`ruvnet/RuVector`. The prepared issue template contains an immutable-URL
placeholder; root fills that only in the outgoing issue payload after publishing
and verifying an actual commit. A community report is a request for methodology
review, not an accepted official ranked entry.
