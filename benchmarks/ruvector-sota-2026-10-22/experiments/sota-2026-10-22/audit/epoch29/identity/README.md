# Epoch29 document identity engineering

This is a separate document-integrity qualification. The fixed LoRA TRAIN/DEV
allocation remains HOLD: selected document548 aliases exposed E27 document515.
All16 selected IDs stay retired; the pool remains277exposed/122unreserved/24reserved.
No TRAIN,DEV,calibration or confirmation roles are opened by this engineering step.

The source is Koreeda and Manning(2021), ContractNLI, official revision
https://github.com/stanfordnlp/contract-nli/tree/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9 .
The original train.json is7608211bytes, SHA256
`dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5`.
CC BY4.0 applies to corpus text; see ../LICENSE-CC-BY-4.0.txt for unchanged licence.
Changes: canonical text, metadata, source hashes and engineering case IDs added.
Model/code licences remain separate from corpus-text licensing.

A frozen id/text-only builder hashed all423 original documents, explicitly
including protected24 and remaining122, and read no annotation choices or evidence.
The complete annotated public JSON was parsed in RAM: field isolation is logical,
not OS-enforced secrecy. Hash-only metadata has422 canonical groups; the only
normalized duplicate is548/515. This is a full-source identity fact, not a semantic
similarity or legal-label result. Future inventory grants no new data allocation.

Authoritative identity is SHA256(UTF8(' '.join(document.casefold().split()))).
The model bank contains only the old261 exposed documents and the already-spent
548 query. Any old exposed document whose hash matched protected24 would have
been excluded before encoding; there are no such exclusions or protected aliases.
No reserved24 or remaining122 text is emitted to the model bank or encoded.
BGE input uses NFKC(normalized_text).casefold(), preserving canonical separators;
its separate input hash never changes the authoritative historical identity rule.

The one bounded CPU2/600second worker may initialize the fixed BGE-small encoder
and actual pinned RuVectorcore2.3.0 once. BGE attends at most256 tokens; full-text
hashing does not imply full-document attention. Corpus self-query vectors are
reused. ANN fetches17 then excludes self and retains16; external548 fetches16.
A brute cosine arm uses exactly the same retained float32 vector bits and excludes
self; exact-score ties use lowest numeric document ID. All candidate order, native
vector receipts, tokenization/truncation, errors and process resources are retained.

Only exact normalized-hash confirmation establishes an alias. A retrieval miss
is UNRESOLVED, never CLEAN or fresh. The frozen evaluation has262queries and one
positive query,548→515. Recall@16 therefore qualifies a finite known case; it is
not a generalization estimate. No optional near-duplicate threshold is fitted.
No NLI labels, decision accuracy, NLL/Brier, benchmark acceptance, promotion,
submission, confirmation or official rank is supplied by this engineering check.
