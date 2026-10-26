# E48 runtime contract

The four execution sources are `worker.py`, `reader.py`, `packing.py`, and
`native_helper.cjs`. Importing their Python modules does not import Torch,
tokenizers, ONNX Runtime, or native RuVector. The fixture test uses invented
strings and fake tensors only. It is engineering evidence, not benchmark accuracy.

Root alone owns SOURCE publication, DATA admission, dispatch, hard timeout,
independent runtime qualification, Gold access, scoring and checkpoint publication.
This directory grants none of those authorities.

## Worker command

```
python -I -B worker.py --plan PLAN --expected-plan-sha256 SHA256 \
  --phase dev --admission SCI_ADMISSION --expected-admission-sha256 SHA256 \
  --output PUBLIC_RAW --private-run-directory PRIVATE_RUN \
  --deadline-monotonic-seconds ABSOLUTE_DISPATCH_START_PLUS_570
```

Use `confirmation` for the independently accepted, unchanged second phase only.
Root launches this worker in one new owned session with CPU affinity 0,1 and no
automatic retry. Native helper inherits the same session and process group.
Root enforces the complete 600-second bound, including initialization and physical
cleanup; the worker checks the absolute 570-second soft deadline between stages.

## Immutable plan required fields

- `schema_version: 1`, `epoch: 48`, `kind: REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT`.
- `dataset_revision: eced6528dd3c1d14d73f9a87df8f7bdbc03126f9` and
  `source_archive_sha256`: exact official source archive identity.
- `phase_roles.dev` and `phase_roles.confirmation`, each with ordered
  `document_ids` (four integers) and `case_ids` (twelve strings, document-major
  nda-1, nda-10, nda-16). Data policy and source/scorer references belong in this
  immutable plan. Feature bank bytes and hash do not: they are created after SOURCE.
- `model_directory`: absolute local directory; `model_assets`: exactly seven
  objects `{file,path,bytes,sha256}`, names README.md, config.json, merges.txt,
  pytorch_model.bin, special_tokens_map.json, tokenizer_config.json, vocab.json.
  Each path equals model_directory/file. All exact artifacts must already exist.
- `runtime_versions`: exact installed distribution versions for torch,
  transformers, tokenizers, numpy, onnxruntime and any additionally pinned runtime
  distributions. Root currently reported torch2.7.1+cpu, transformers4.52.4,
  tokenizers0.21.4, numpy2.2.6 and onnxruntime1.22.1; use actual verified receipts.
- `bge_model`, `bge_tokenizer`, `native_binary`, `node`: exact file references
  `{path,bytes,sha256}`. BGE uses the original 384-dimensional encoder, one
  CPUExecutionProvider session, two intra-op threads and one inter-op thread.
- `native_root`: exact original project root with
  retrieval/node_modules/@ruvector/core0.1.33 and platform0.1.31. The binary is
  retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node with SHA256
  ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e;
  actual native version must be2.3.0. Node is an absolute exact pinned executable.

## Post-SOURCE SCI admission required fields

The admission is a Root-written, hash-pinned JSON file with schema_version1,
epoch48, exact kind, `phase`, `allowed:true`, `plan_sha256`, `source_commit`,
`source_freeze_sha256`, `worker_slot_token` (64 hexadecimal public nonce), and
`native_batch_ordinal`1 for dev or2 for confirmation.

`source_files` is a list of exact absolute `{path,bytes,sha256}` references and
includes all four runtime execution files. `owner` pins current owner.json.
The worker checks its original locked inode, live PID/startticks and expiry.
Root's outer runner must continue enforcing owner/lease and original process
ownership while the worker runs.

`data_admission` pins the post-SOURCE DATA report; `features` pins its feature bank.
The DATA report must have epoch48, exact kind, phase, plan_sha256,
source_freeze_sha256, status READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT,
errors empty, semantic_gold_values_decoded0, and exactly matching features and
private_features references. Confirmation also
requires `independent_DEV_acceptance` with checks_passed:true, dev_passed:true and
the unchanged plan_sha256. Root must additionally enforce that report's exact
frozen point gates and physical closure before admitting confirmation.

The feature bank is the agreed E47-style format: schema_version1, epoch48,
exact kind, `role`, source_archive_sha256, four document records with exact full
source hashes and contiguous verbatim evidence units, and twelve case records
with id/document_id/hypothesis_id/input_sha256/claim. No annotation choices.
Both phases use official source member `dev`; role alone distinguishes held
confirmation. The worker checks original-text and normalized-text hashes and
the full claim+document input hash before any model operation.

## Public RAW v1

Top keys include schema_version1, epoch48, exact kind, phase, plan_sha256,
source_freeze_sha256, status, rows, counters, timing, resources, errors,
source_pins and loading_audit. Complete status is FORECASTS_COMPLETE_NO_GOLD.

Each of 36 ordered rows has case_id, document_id, hypothesis_id, arm (`native`,
`lexical`, `source_order`), probabilities/logits/log_probabilities in canonical
`[Entailment,Contradiction,NotMentioned]` order, prediction, elapsed_seconds,
packing_seconds, forward_seconds and evidence metadata. Evidence contains only
unit IDs, offsets, hashes, token counts, packing decisions and occurrence hashes.
Full premises, claims, source text and token IDs are never emitted in public RAW.

Logits are actual original learned-head FP32 outputs represented as Python
floats. Stable FP64 log-softmax derives both log probabilities and probabilities.
No epsilon clipping, temperature fit or decision override occurs. Exact ties
choose the first canonical class. NotMentioned is the model's learned neutral
prediction, not a proof about absent evidence or full-source coverage.

Native receipt retains all raw hit scores and source-vector bit hashes. Original
vectors and full source bundles remain in the private run directory. Model/Node
exceptions and stdout/stderr remain private; public errors use bounded codes.

Per-row elapsed time covers packing plus one NLI forward; shared embeddings,
native indexing and initialization are measured by whole-batch timing. Worker
SELF CPU excludes child CPU; largest-child RSS is not a sum. Shared cgroup
memory values are explicitly not candidate-incremental use or a fresh peak.

Counters contain actual attempts and completions separately. Native corpus
attempt is recorded before helper Popen; completed corpus is recorded only after
the helper's exact result/counter checks. Last native progress capture preserves
partial attempted/completed counts on failure without claiming uncertain calls
completed. Root must retain owned-process closure evidence if an outer hard kill
prevents the worker's final write. No automatic retry or fallback is implemented.
