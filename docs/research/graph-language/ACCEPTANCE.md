# RuGraph v0.1 acceptance evidence

Validated on 2026-10-16 against repository base
`46d816ddc4c2a8a06cd3613534a79b1d557d858b`.
This report covers the version 1 bounded language in [SPEC.md](SPEC.md).

## Result

Local acceptance passed: **70 tests**, formatting, strict targeted Clippy, ADR
number validation, packed npm client execution with TypeScript declarations,
and installed Python wheel execution and replay. No tests were skipped.

The implementation includes the text and JSON frontends, type/effect checks,
deterministic runtime, evidence and rule semantics, replay receipts, real
RuVector graph/KGE adapters, offline model lifecycle, CLI, process SDKs,
examples, five ADRs and a scoped CI workflow. Package publication and default
branch merge are separate release actions.

## Reproduction

Install Rust 1.90.0 with rustfmt and Clippy, Node.js 24, Python 3.12, setuptools
and wheel. The package smoke script downloads TypeScript 5.9.3 through npm;
it does not publish a package. Run from the repository root:

```bash
bash scripts/test-graph-language.sh
bash scripts/smoke-graph-language-packages.sh
cargo +1.90.0 run --release --locked \
  --manifest-path crates/ruvector-language-native/Cargo.toml --example native_bench
```

The two acceptance scripts completed with exit code 0. Exact local versions:
rustc 1.90.0 (`1159e78c4`, 2025-09-14), Node.js 24.19.0, Python 3.12.14,
setuptools 84.0.0, wheel 0.48.0. Target: Linux x86_64, glibc 2.39.
The checked in workflow uses the same Rust, Python and Node major versions.
The dedicated remote acceptance workflow also passed at commit
`01d961f2d48528b3cf320d335adefa0f1245dc79`:
[Graph language run 38899871818](https://github.com/ruvnet/RuVector/actions/runs/38899871818).
Broader repository checks are separate from that successful feature gate.

## Requirement trace

| Requirement | Executed evidence | Result |
|---|---|---|
| Text/JSON parity; strict schema; limits; static types and effects | `tests/frontend.rs`, 16 tests | Pass |
| Four evidence states; explicit negative support; temporal freshness | `tests/runtime.rs`, part of 15 tests | Pass |
| Signed conjunction, chained derivation, source lineage, cycles | `tests/runtime.rs` | Pass |
| Deletion, expiry and alternate witness recomputation | `tests/runtime.rs` | Pass |
| Traversal and exact cosine ranking with deterministic ties | `tests/runtime.rs` | Pass |
| Host capability denial, budget exhaustion, provenance bounds | `tests/runtime.rs` | Pass |
| Prediction/evidence separation and provider response checks | Frontend and runtime tests | Pass |
| Hashes independent of nested object insertion order | `tests/canonical.rs`, 2 tests, serde `preserve_order` enabled | Pass |
| CLI strict input, preflight, integrity and replay behavior | Core `tests/cli.rs`, 5 tests | Pass |
| Real GraphDB capture and bounded borrowed traversal | Native `tests/native.rs`, part of 9 tests | Pass |
| HolE and RotatE score parity with direct native calls | Native `tests/native.rs` | Pass |
| Actual training changes weights; deterministic seed; native evaluation parity | Native `tests/native.rs` | Pass |
| Reject split leakage, unseen vocabulary, malformed models and metrics | Native `tests/native.rs` | Pass |
| Train → promote → evaluate → predict → replay, in real processes | Native `tests/cli.rs`, 1 test | Pass |
| JavaScript process API, replay, permission and stream boundaries | Node test runner, 11 tests | Pass |
| Python process API, full u64 replay, stream/thread cleanup | Python unittest, 11 tests | Pass |
| Published layout usability without publication | npm pack/install + strict TypeScript compile; Python wheel/install | Pass |
| Formatting, warning gate and ADR allocation | Both manifests: fmt; Clippy all targets/no deps with `-D warnings`; ADR check | Pass |

Core test paths are relative to `crates/ruvector-language`; native paths are
relative to `crates/ruvector-language-native`. The 70 total comprises 38 core,
10 native, 11 JavaScript and 11 Python tests. Artifact smoke checks are additional
to this count. Every newly added source and test file is below 500 lines.

## Independent review and regressions

The compiler, runtime and native implementation were built in separate work
streams, then cross reviewed against the shared specification. Integration and
review found and fixed:

1. Flattened operation deserialization incorrectly rejected valid JSON fields.
   Canonical JSON and combined request roundtrips now pass while unknown fields
   and duplicate effects remain rejected.
2. Nested property key order affected hashing when an embedding host enabled
   serde's insertion ordered map feature. Borrowed canonical serialization now
   sorts nested object keys and charges sorting work.
3. Graph capture cloned arbitrary payloads before validation. Borrowed fallible
   visitors now validate identities, depth and property bounds before copying.
4. Native prediction copied large candidate strings before the output limit.
   It now ranks score/index pairs and preflights output bytes before allocation.
5. Python buffered unbounded child output and JavaScript could round u64 values.
   Streaming limits and explicit numeric precision checks now fail closed.
6. Missing replay arguments were detected after request execution. Required
   flags are now checked before input or model loading.

For the native output regression, the identical 1,000 entity / 50 subject /
top 1,000 request with 512 byte identities fell from 90,312 KiB to 9,216 KiB
peak child RSS and returned `LIMIT` before candidate allocation. It is a
targeted synthetic regression, not a general memory usage guarantee.

## Performance evidence

Full machine, source hash, workload, measurements and previous runs are in
[native-benchmark.json](native-benchmark.json). The final run uses HolE,
32 dimensions, 256 entities, 8 subjects, top 5, five warmups and 30 samples.
Direct and adapter paths both rank score/index pairs and clone only top k.
Candidate scores and rankings match before timing starts.

| Path | Median µs | p95 µs |
|---|---:|---:|
| Direct native KGE | 406.690 | 580.892 |
| Native adapter | 418.458 | 1,520.381 |
| Full language runtime | 437.987 | 1,000.401 |

Observed median runtime overhead is **7.70%** for this workload. The shared build
environment showed substantial tail variance. The direct baseline omits
validation, permission checks and receipt hashing, so this does not establish
the proposed 10% equivalent work product gate. The proposed 30% application code
reduction has not been established. Both remain product evaluation targets.
Synthetic initialized weights measure execution only; toy training tests do not
establish useful real world prediction accuracy or transfer to unseen graphs.

## Dependency identity and review scope

| Lockfile | SHA256 |
|---|---|
| Core `Cargo.lock` | `2381cce2e1ec9e372714914533e335bb6ec6866a96e17c2a2ad85e51e7f8dbe0` |
| Native `Cargo.lock` | `3beba443fc7ade7b251411c4e471f5728eb270b0cf7bfb578751de36d227fe5c` |

Both lockfiles are committed. A followup CI repair changes only the root
`rustls` lock entry from 0.23.45 to 0.23.46 and its registry checksum. Cargo
downloaded and verified the patched archive; dependency requirements, features
and minimum Rust version are identical in the registry records. The patched
library compiled with the root ring/std/tls12/logging feature profile in an
isolated Cargo check. Dedicated advisory checks now cover both standalone
language lockfiles; root advisory and lockfile integrity jobs validate the root
repair in CI. This does not suppress advisory findings. The
existing graph crate receives two additive borrowed visitor methods; existing
APIs keep their behavior. [SECURITY-REVIEW.md](SECURITY-REVIEW.md) records the
threat boundary, scanner scope, fixed findings and advisory coverage limits.

## Remaining limits

Graph capture requires caller enforced exclusion of all writers. The snapshot
profile supports one label per node, binary edges and no edge properties or
hyperedges. Predictions are transductive scorer outputs, not probabilities.
Imported model metrics and observation sources require host trust. Receipts
provide checksums, not signatures. Cross platform FFT bit equality is not
guaranteed. JavaScript accepts only safe integers; Python and Rust support u64.

No claim is made that all unrelated RuVector crates pass, that every transitive
dependency is vulnerability free, or that performance and accuracy targets have
been met outside the measured workload. This release implements the specified
bounded language; broader research extensions remain separate work.
