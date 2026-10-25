# Epoch33 frozen candidate source

This is one diagnostic experiment with actual native RuVector and an existing
pretrained Moritz DeBERTa-v3-large NLI head. The primary hypothesis is one fixed,
hypothesis-only typed-modal retrieval-query expansion. Source metadata does not
establish stronger measured quality, publisher eligibility or benchmark rank.

The four arms are `actual_native` (expanded query), `native_original` (unaltered
query on the identical document index), `lexical` (the exact expanded query) and
`positional` (first source units). Every NLI hypothesis remains the original
unaltered source hypothesis. Query recipe, synonym terms, k, context packing,
reader/scorer identities and data roles freeze before any model measurement.

The single outer worker has a600-second total budget including source/runtime
checks, initialization and cleanup, under CPU affinity0,1. The first native corpus
contains the six **exposed epoch32 CC0 engineering regressions** with their original
case/document identities. It makes12 native queries and24 raw neural forwards.
Only a final native6/6 engineering gate can start the second corpus: eight fixed
new ContractNLI development documents ×three hypotheses ×four arms =96 additional
raw forwards and48 additional native queries. Maximum:120 raw forwards,60 native
queries,14 indexes,two sequential native helpers,one model initialization. No
TRAIN, fit, calibration, fresh confirmation, paid/GPU call or retry is authorized.

`proof.py` is a deliberately narrow controlled-language supplement for the exposed
engineering regressions. It can certify only a complete parse of the exact full
supplied input, literally equal to that arm's premise with one whole-source span.
An unparsed clause, unknown syntax, incomplete context, condition, exception or
ambiguous date anchor abstains. Distinct exact scalar values need identical event,
subject, date reference, EXACTLY qualifier and unit. A neutral certificate requires
two compatible logical models (claim true/false) over independent primitive
predicates. A retrieval miss cannot establish insufficient evidence.

The proof policy is **disabled for every DEV decision**. DEV final probabilities
and predictions equal the raw T1 model output, with an explicit disabled reason.
The three public NDA hypotheses cannot test this closed proof grammar. No benchmark
proof benefit or proof generalization will be claimed. Raw T1 neural outputs are
retained in all four arms. Engineering certificates have explicit onehot final
probabilities; improper certainty remains visible in Brier/NLL if a certificate
is wrong. Raw and final metrics are independently reported, never selected after
measurement. A premeasurement source audit found zero possible proof coverage and
caused this explicit query-treatment redesign; prior proposal metadata is retained.

The original b354 safetensors weights store394 learned F16 tensors (435,064,835
parameters) plus one I64 legacy position_ids buffer. The loader verifies every
source key/shape/dtype, converts the F16 values losslessly to CPU F32, assigns the
unchanged stock graph, checks arange512 buffer semantics and freezes all parameters.
This is no quantization, no trained-head replacement and no model warmup forward.
Source MIT model/foundation declarations do not license every upstream training
dataset. Exact training records/selection and foundation overlap remain unknown;
confirmation and official eligibility stay HOLD and Native104 remains unchanged.

Results are engineering/DEV diagnostics only, not JevBench, full LegalBench or
ClaimBench placement. All reserved DEV identities retire forever even on refusal.
A separately frozen scorer joins only the24 allowed DEV labels after complete
actual capture and an independent physical supervisor/worker/native closure proof.
Errors, partial/unknown counts, resource limits and failed gates must be retained.
