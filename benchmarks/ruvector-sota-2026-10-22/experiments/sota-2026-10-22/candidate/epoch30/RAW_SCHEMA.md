# Epoch30 retained evidence contract

This source-only contract describes two separately admitted CPU2 phases of
`REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC`. It authorizes no execution.
The source plan, prospective audit protocol and external admissions remain
mandatory. There are no CONF, full104, paid, GPU or generation calls.

The CLI is `worker.py --phase train|dev --plan PATH --expected-plan-sha SHA
--admission PATH --out PATH --deadline UNIX`. The launcher is
`runtime/launch.py`; canonical outputs are `epoch30/runs/train/` and
`epoch30/runs/dev/`. Each has `raw.json`, `execution.json`, progress JSONL and
an optional exact `raw.partial.json` checkpoint. Interrupted pending checkpoint
bytes remain `raw.partial.pending.json`, with their hash retained. A checkpoint
does not prove complete counters or backend execution since its last snapshot.

`worker.expected_counters(phase)` is the authoritative literal counter table;
`EXPECTED_COUNTERS.json` is its source-only projection for plan construction.
All attempted calls increment immediately before the actual operation, completed
calls increment after it returns. Dynamic BGE forward/text counts, native inserts
and validated hits are retained separately. A full phase requires the expected
counts, runtime phase-zero counters, no persistent network violation and owned
child closure. Kernel CPU0,1/NNP/seccomp precede Torch/ORT imports and are inherited
by Node. Observed thread counts need not equal two.

## Main raw JSON

`schema_version:1`, `epoch:30`, `kind`, `phase`, `source_checkpoint`,
`plan_sha256`, `source_freeze_sha256`, `worker_pid`, `worker_identity`,
`admission`, `owner_lock` and `data_roles` identify the actual worker. Roles always
contain all frozen TRAIN8/DEV8 IDs and empty calibration/confirmation, including
in TRAIN; these ID metadata do not cause DEV input reads.

`status` is `INITIALIZING`, `FAILED_TRAIN`, `FAILED_DEV`,
`COMPLETED_TRAIN_AWAITING_INDEPENDENT_MODEL_SEAL` or
`COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN`. `errors` retains actual exception
type/message/traceback. `counters`, `Python_network_events`,
`Python_network_violations`, `Node_guard_events`, `resources`,
`wall_seconds_including_initialization_cleanup`, `worker_cpu_guard_preexec` and
`worker_cpu_guard_preexec_artifact` retain measured operation and resource proof.
The raw CPU receipt exactly copies the outer preexec JSON and its actual ref3.
The narrowly admitted urllib3 IPv6 capability bind is counted separately and
records outcome/close/stack/source; it is not a service or network exception for
other calls. Network guards are API interposition, not compiled syscall tracing.

`phase_input_bank` is a relative `{path,bytes,sha256}` reference. Only the current
phase bank is read. `documents` maps the eight decimal document IDs to `units`,
`prelude`, `partition_seconds`, and embedding diagnostics. Units and prelude refer
to exact source character spans. `embedding` retains document/query BGE diagnostics,
exact prefixed hypotheses, source chunk SHA256s and measured norm extrema. No
annotator evidence lists enter chunking or context selection.

`BGE` records actual original source/model receipt and initialization time.
`model_initialization` retains original safe loader checks, base/head identity and
trainability configuration. `vector_bundle` and `native_result` are ref3 values;
the full numeric vector payload appears once in the bundle. Native stdout,
stderr, progress and any `.failure.json` remain unchanged. `native_scratch`
inventories owned temporary database files by bytes/SHA before their removal;
it lies outside the public project. `native_child_closed` and exit code report
actual child cleanup, not an assumed successful backend call.

`cases` contains 24 ordered rows: `id`, `document_id`, `hypothesis_id`,
`input_sha256`, full `document_sha256`, `hypothesis`, `hypothesis_sha256`,
`document_preparation_ref`, actual `native` query receipt, lexical Jaccard scores,
and `arms`. TRAIN has only `actual_native`; DEV additionally has `lexical` and
`positional`. Each arm has `observed_ranking`, literal `premise`, `context`,
`joint_pair_tokens`, context/query seconds and `reader:{original,adapted}`.
Context audit retains legacy numeric counts separately from source-provenance
numeric/UTF8 proofs, all selected/omitted spans and full-document coverage data.
True BART pairs have four special tokens and must fit512 without hidden clipping.

Reader receipts retain original native C,N,E logits and all canonical E,C,N
probabilities, finite output checks, pair IDs SHA, text SHA, counts, actual state
identity and latency. T1/three-way native-index ties and binary exact-half No are
unchanged from the original reader. No semantic rule overrides any prediction.

## TRAIN-only evidence and learned artifact

All24 native contexts precede the selective source-choice helper. TRAIN bank
read attempts total two: preparation and the frozen helper's independent
identity-checking reparse; hash-only reads are outside this semantic-read count.
Only exact
TRAIN24 choice fields are read; DEV/CONF/other choices and source evidence lists
remain zero. `choice_read_receipt` contains helper source/input references,
read counts and selected case/input identities; individual source choices and
target indices are omitted. `TRAIN_class_counts` is descriptive aggregate data,
not a selection criterion. Independent TRAIN integrity auditing does not join
gold or traverse these class counts.

`steps` contains exactly24 ordered `{id,context_ref,reader}` records. Step reader
proof includes actual native logits, finite unweighted CE, backward/clip/update
receipt, each LoRA B gradient and post-step trainable manifest SHA. No accuracy,
loss monotonicity, parity forward, warmup or validation forward chooses a model.
`train_integrity` retains original head identity, all12 before/after trainable
hashes, the511 frozen original tensor before/after manifests and aggregate SHA,
four effective BA delta hash/norm proofs, and actual24 steps. Every intended
tensor must change, each B must receive nonzero finite gradient, and every other
pretrained parameter must remain bit-identical.

`parameter_artifact` references `runs/train/trained-parameters.public.json`.
Its strict16-key schema is implemented in `parameter_codec.validate_artifact`:
schema_version, epoch, kind, codec, base_model, algorithm, source_plan_sha256,
training_inputs_sha256, training_steps, trainable_parameter_count, tensors,
original_head_manifest, initial_trainable_manifest, trainable_changes,
frozen_pretrained_proof, effective_lora_delta. There are exactly12 ordered
FP32LE payload records named/shaped in `algorithm.EXPECTED_TENSORS`; each has
`name,shape,dtype,numel,bytes,sha256,data_base64`. Total decoded bytes4341772,
scalars1085443, base64 characters5789056. No base weights or optimizer state is
exported. Canonical artifact serialization is sorted-key compact UTF8 JSON plus
newline, bounded8MiB. Frozen-manifest aggregate hashes use the same canonical
serialization on ordered six-key manifests. Effective BA hashes are from actual
FP32 Torch arithmetic and are rechecked by the fresh DEV worker.

TRAIN completion alone does not admit DEV. Root must publish the exact learned
artifact and MODEL_SEAL, independently read the actual Git MODEL commit back and
write MODEL_ADMISSION. The seal binds artifact, TRAIN raw/execution, independent
TRAIN integrity report, source plan/freeze and the original ce2536 base hash.

## DEV-only evidence and final scientific scope

The fresh original model scores24 actual-native cases before any learned tensor
decode/injection. Only then does `adapted_state_load` retain exact applied tensor
manifests/effective deltas/seal reference. Adapted native/lexical/positional score72
cases in fixed order. Original/adapted native text and token hashes must match.
`loaded_parameter_artifact` identifies the exact applied bytes. There are96 DEV
forwards and no backward, optimizer, label or fitting calls.

Only the independent scorer may join DEV24 choices after the complete closed raw
seal. `benchmark_accuracy` and `proper_scores` in worker raw remain null;
`benchmark_accepted`, `champion_promoted` and `new_submission` remain false.
This is a small, correlated, conditional diagnostic of joint LoRA/head adaptation
and evidence retrieval. It is not exclusive LoRA causal proof, CONF or benchmark
promotion, and current full104 comparator eligibility remains HOLD.
