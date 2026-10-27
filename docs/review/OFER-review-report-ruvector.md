# Ofer adversarial review: ruvector side

Branch reviewed: `feat/ofer-streaming` at e7d6bb914. Repro branch: `feat/ofer-review-ruvector`
(worktree `/data/scratch/ofer-wt/review-ruvector`, target dir `/data/scratch/ofer-wt/target-review-ruvector`).
Every finding below has a test in `crates/rvf/rvf-runtime/tests/review_ofer_*.rs` or
`crates/rvf/rvf-wire/tests/review_ofer_stream.rs`, named with the finding id. Tests marked (defect)
pass today because they assert the defective behaviour; fix the code and they should be inverted.

Finding ids: F-01..F-06, F-11..F-17. There are no F-07..F-10 findings; `f08`, `f09`, `f10` in the test file are oracle tests that passed (listed under "sound"), `f07` is unused.

Headline: the RVSD core (descriptor decoder, verifier, frame reader, crypto) held up. I could not make it
panic, release an unverified byte, or reach Complete with a gap. The real defects are in the runtime Strict
policy surface (compaction re-signs unauthenticated bytes), a quadratic DoS in the runtime manifest scan
that runs before any signature check, and several "Strict is opt-in" gaps.

## Findings

### F-01 (high) compact() on a signed store launders tampered, manifest-listed segments into the signature
- Where: `crates/rvf/rvf-runtime/src/store.rs:1657-1930` (`compact`), esp. 1695-1700 (reads raw file bytes),
  1722-1800 (`scan_preservable_segments` + `copy_raw_segment` + `seg_writer.record_hash(.., compute_shake256_128(src payload))`).
- Test: `rvf-runtime/tests/review_ofer_compact.rs::f01_compact_launders_tampered_listed_segment` (defect).
- Trace: owner creates signed store with an embedded WASM segment. Attacker (no key) flips a bytecode byte and
  recomputes the header SHAKE-256-128 hash (keyless). `open_with_policy(Strict)` succeeds because WASM/kernel/eBPF
  segments are read lazily; `extract_wasm()` correctly fails with the committed-hash mismatch. Owner runs
  `open_signed(Strict)` then `compact()`: the tampered bytes are copied verbatim, a fresh hash is computed over them
  and written into the new signed trailer, the page is re-sealed. A fresh Strict open now serves the tampered WASM
  with a valid signature (`extract_wasm` returns the flipped byte).
- Impact: a keyless attacker converts "tamper with a lazily-read executable segment" into a validly signed file after
  any routine maintenance by the key holder. Defeats the "swapped segment is refused" claim in `security.rs` module docs.
- Fix: when `signing_key.is_some()`, never trust source bytes. Take the segment list from the verified directory only,
  read each source via `read_seg` (committed-hash check) and carry the committed hash forward instead of recomputing it
  from the bytes. Refuse to compact if any listed segment fails its committed hash.

### F-02 (medium) compact() adopts and signs segments that are not in the signed directory
- Where: same loop; `scan_preservable_segments` at `store.rs:4378-4452` scans the whole file byte by byte and includes
  segments "appended after the manifest".
- Test: `review_ofer_compact.rs::f02_compact_adopts_unindexed_injected_segment` (defect).
- Trace: signed file `[... M][P]`. Attacker inserts a header-valid WASM segment (algo 2, keyless hash) between M and a
  re-appended copy of the original page P. Strict open still passes (newest manifest unchanged, page valid, unindexed
  segment never read). Owner `compact()`: the injected segment is copied, hashed, added to the directory and signed.
  Afterwards `extract_wasm()` under Strict returns it.
- Note: unsigned witness segments after the manifest are normal in this design (`query_audited`, `store.rs:1464-1488`,
  appends a witness then re-seals the OLD manifest), so Strict cannot tell legitimate trailing segments from injected
  ones, and compaction launders both. That makes the F-01 fix necessary but not sufficient: preserve only
  directory-listed segments and treat the witness chain separately (verify it, or re-derive it).
- Fix: as F-01; additionally restrict preserved types for signed stores to the directory.

### F-03 (medium, DoS, regression) Runtime manifest scan is quadratic in file size and runs before any signature check
- Where: `rvf-runtime/src/read_path.rs:150-206` (`scan_tail_for_manifest`): per candidate it does
  `buf[payload_start..payload_end].to_vec()` (or allocates `vec![0; payload_length]` and reads) before
  `parse_manifest_payload` can reject it. The previous code parsed the slice in place (`git show origin/main:...read_path.rs`),
  so a failing candidate was O(1); now it is O(payload).
- Test: `rvf-runtime/tests/review_ofer_scan_dos.rs::f03_fake_manifest_headers_make_open_quadratic` (defect).
- Input: a file made only of back-to-back 64-byte MANIFEST headers (valid magic/version/type), header i claiming all
  following bytes as payload and arranged so payload bytes 14..18 (seg_count) are huge, so every parse fails.
- Measured (release, `RvfStore::open_with_policy(Strict)` on the hostile file): 1 MiB 0.10 s, 2 MiB 0.54 s, 4 MiB 1.9 s
  (about 4x per doubling). Extrapolated: 64 MiB about 8 min, 256 MiB about 2 h. Applies to every policy because the
  scan precedes the signature check, and to `open_readonly` of untrusted files in all CLI/launch paths.
- Related, pre-existing: the last scan window (`u64::MAX`) allocates the entire file (`vec![0u8; file_size - scan_start]`),
  so a large manifest-less file aborts on OOM instead of failing.
- Fix: parse candidates from the window slice without copying, cap the number of full-payload attempts per open (for
  example only candidates whose extent is consistent with the next segment boundary), stop at the first candidate in
  Strict mode that does not match the page when a page is present, and read windows with a bounded buffer.

### F-04 (low) A completed stream is flipped to Poisoned by trailing junk
- Where: `rvf-wire/src/stream/verifier.rs:216-221` (`poison` overwrites any state except Rejected, including Complete and Suspended);
  reachable from `frame.rs:124-132`, `149-155` (unknown frame type after the last frame).
- Test: `rvf-wire/tests/review_ofer_stream.rs::f04_trailing_junk_flips_complete_to_poisoned` (defect).
- Impact: one extra byte on the wire after a fully verified body moves state from Complete to Poisoned(StreamUnexpectedFrame).
  A consumer that checks `state()` at end of transfer revokes capabilities and drops a verified artifact (the ADR says
  Poisoned means "revoke, terminate, drop layers"). Truncation or corruption already lets a path attacker do this, but the
  inverse is also wrong: poisoning after Complete should not retroactively invalidate released data silently.
- Fix: `poison()` must be a no-op in Complete (return the code but keep state), or FrameReader must treat bytes after
  Complete as an error that does not change state.

### F-05 (low/info) Stage-order delivery completes with identity Unverifiable; nothing forces the follow-up
- Where: `verifier.rs:243-258` (`finish`), `verifier.rs:261-285` (`finish_identity`).
- Test: `review_ofer_stream.rs::f05_stage_order_completes_with_unverifiable_identity`.
- Impact: any delivery order other than file order (the main point of M2) reaches `Complete` with
  `IdentityStatus::Unverifiable`. `rvf_identity` is only checked if the caller persists the body and calls
  `finish_identity`. A consumer that keys policy on `rvf_identity` after `Complete` trusts a value nobody verified.
  The chunk commitments are signed so this only matters for a buggy or hostile signer, but the API makes the unsafe path
  the default.
- Fix: expose a distinct terminal state or make `Complete` carry the status type so it cannot be ignored; document that
  `rvf_identity` must not be used as an identity until `finish_identity` succeeds.

### F-06 (low/info) Equal-epoch conflict detection is optional
- Where: `descriptor.rs:75-84`.
- Test: `review_ofer_stream.rs::f06_equal_epoch_without_pin_hash_accepts_different_descriptor`.
- Impact: with `EpochPin { descriptor_hash: None }` a different signed descriptor at the same epoch for the same
  `file_id` is accepted, contradicting the ADR acceptance line "an equal epoch with different content is rejected".
  Pins are keyed by `file_id` only, so any trusted signer can raise another signer's lineage epoch (up to u64::MAX) and
  brick it. The pin update itself is the caller's job, so check-then-update races are the caller's too.
- Fix: make `descriptor_hash` mandatory in `EpochPin` (or reject None at equal epoch), bind pins to (signer, file_id).

### F-12 (low) Plain `RvfStore::open` + write irreversibly strips the signature
- Where: `store/policy_api.rs:98-111` (`append_cursor` truncates the 4096-byte page), `policy_api.rs:165-185` (Permissive recognises the page).
- Test: `rvf-runtime/tests/review_ofer_policy.rs::f12_plain_open_append_silently_unsigns_a_signed_store` (defect).
- Impact: any caller using the historical `open()` on a signed store and ingesting destroys the signed state; Strict readers
  then get `UnsignedManifest`. Fail-closed for readers, but destructive and silent for the owner.
- Fix: refuse (or require an explicit flag) to cut a valid signed page in a Permissive writer.

### F-15 (low/medium, deployment) Strict is opt-in and no in-tree consumer opts in
- `grep` over `crates/rvf` (excluding runtime and tests): every consumer uses `RvfStore::open` / `open_readonly`;
  nobody calls `open_with_policy`, `open_signed` or `create_signed`. In particular `rvf-launch/src/extract.rs:43-46`
  extracts a kernel for execution from an `open_readonly` (Permissive) store, `rvf-cli compact`/`ingest`/`delete`
  (`cmd/compact.rs:30`, `cmd/ingest.rs:50`, `cmd/delete.rs:30`) will strip or never produce signatures.
- Impact: ADR-354 item 5 "Strict is real" holds only for callers that migrate. Not a code defect in the new paths.
- Fix: route launch/server/CLI through `open_with_options` with a trust set, or fail closed on a signed file opened Permissive.

### F-13 (info/low) Fake manifest inside a trailing payload wins under non-Strict policies
- Test: `review_ofer_policy.rs::f13_fake_manifest_inside_trailing_vec_payload_wins_under_permissive` (defect).
- A MANIFEST segment placed at a 64-aligned offset inside the payload of a VEC segment appended after the real manifest
  (attacker-chosen floats; the leftover of a crashed append) is the newest aligned candidate and replaces the store.
  Strict refuses it (offset mismatch against the signed page). This is the documented weakness of both scan modes; reported
  because Permissive is the default for `open`.

### F-14 (info/low) Legacy byte-granular scanning is selected by one unauthenticated byte
- Where: `read_path.rs:71-81` (`mode_for_file` keys on the first segment's `checksum_algo`).
- Test: `review_ofer_policy.rs::f14_first_header_algo_byte_selects_byte_granular_scan_and_splits_parsers` (defect).
- Trace: set byte 0x20 of the first segment header to 0 (no hash covers it; `verify_payload_hash(0, ..)` also accepts XXH3).
  The runtime now scans every byte offset and follows an UNALIGNED fake manifest in a trailing payload, while
  `rvf_wire::tail_scan::find_latest_manifest` (what other consumers use) still returns the real one. This is the ZIP-style
  parser differential ADR-354 item 4 wants gone; it survives for any non-Strict open. Strict is immune (requires Aligned
  and algo 2, `store/security.rs:187-191`).
- Fix: do not let an unauthenticated byte pick the weaker scan for files that otherwise parse as wire dialect, or require
  every segment header found by the aligned walk to be legacy before switching.

### F-16 (low) Strict/Paranoid commit only to payload bytes; header fields are unauthenticated
- Where: `store/policy_api.rs:117-140` (`read_seg`), `read_path.rs` hash check.
- Test: `review_ofer_policy.rs::f16_strict_does_not_authenticate_segment_header_fields` (defect): Paranoid opens a file
  whose Vec segment header has `seg_type`, `flags`, `segment_id`, `compression`, `timestamp_ns` rewritten.
- Impact: the runtime itself ignores those fields (I found no use), but any other reader of a "Strict-verified" file
  (type confusion Vec to WASM, flipped `compression`) trusts attacker-chosen header semantics. RVSD does not have this
  problem because `stored_len` covers the whole segment.
- Fix: commit to SHAKE-256-128 over header (with hash field zeroed) plus payload, or check header fields against the directory.

### F-11 (low, 32-bit + non-default policy) Frame total wraps; split header gives panic or unbounded buffering
- Where: `rvf-wire/src/stream/frame.rs:171-178` (`Ok((hdr + payload) as usize)` in `admit`) and `frame.rs:137` (`target - self.buf.len()`).
- Test: `review_ofer_stream.rs::f11_frame_total_wraps_on_32bit` (cfg 32-bit; run `cargo test --target armv7-unknown-linux-musleabihf` under qemu-arm-static with `RUSTFLAGS="-C target-feature=+crt-static"` and `rust-lld`).
- Trace (policy allows a 0xFFFF_FFF0-byte segment in the segment-granular profile; `stored_len <= u32::MAX` is accepted): a chunk header declaring len 0xFFFFFFF0 gives total = 0x1_0000_0001 which wraps to 1 on a 32-bit usize.
  - Header delivered whole (fast path): a runt 1-byte frame is pushed and the stream is Poisoned(StreamFrameSizeLie). Fails closed.
  - Header split across feeds (10 bytes then 7, slow path): `admit` sets `need = Some(1)` with 17 bytes buffered; the next feed evaluates `1 - 17`: panic "attempt to subtract with overflow" at `frame.rs:137` in debug, wraps to usize::MAX in release so `take = data.len()` and the buffer grows without bound because `buf.len() == need` can never hold again. Observed the debug panic under qemu.
- Impact: remote panic (DoS) or unbounded memory on 32-bit receivers, only with a custom policy admitting segments near 4 GiB and a descriptor signed for such a segment. Default policy (1 GiB segment cap) is not affected.
- Fix: `usize::try_from(hdr + payload)` and poison on failure; use `checked_sub` for `take`; cap `max_segment_bytes` at `usize::MAX - 17` per target.

### F-17 (low/info) Chunk tables held for all segments at once; no cap on tables in flight
- Where: `verifier.rs:on_table` (`self.segs[i].leaves = Some(f[13..].to_vec())`), retained until the segment completes.
- A hostile transport can deliver every (valid, hash-matching) table frame before any chunk; the order is attacker-chosen even though the geometry is signer-chosen. Resident bytes = sum over segments of 32 x chunk_count, about `body_len / chunk_size x 32`. Under default limits (1 TiB body, 64 KiB chunks) that is 512 MiB; with 4 KiB chunks 8 GiB. The module doc says memory is "bounded by the policy"; that is true but the bound is large and there is no in-flight table budget. Not reproduced (arithmetic only).
- Fix: add a policy cap on bytes of accepted-but-unfinished tables, or accept a table only for the segment currently being received.

### Minor / informational
- `ErrorCode::StreamFaultBudgetExceeded` is defined and never returned (`verifier.rs:195-200` returns the triggering code).
- `StreamEntry.flags` is documented "reserved" but not required to be zero; root-page pseudo-entry may have any `stored_len >= 1` and
  any content (builder emits 4096/RVM0 only). Signer-controlled, so only matters for consumers that assume the shape.
- `now_ns: None` silently disables expiry; `expires_ns` is signed but a clockless receiver ignores it by design.
- Level-0 page signature uses `ed25519_verify` (non-strict) while RVSD uses `verify_strict`; with dalek 2.x canonical-S enforcement
  and a trusted key this is not exploitable, but align them.
- No freshness for runtime Strict: an older validly signed file (page and all) replays cleanly; no epoch pin on the runtime path.
- COW children are created Permissive and parents are opened with `SecurityState::permissive()` (`store.rs:3449`), so Strict cannot
  currently validate a COW chain (no signed child can exist; fails closed).
- `Paranoid` adds only "read every directory segment"; `Level1InvalidSignature` is never produced.
- `compact()` of a signed store copies preserved segments verbatim, so a segment written under XXH3 keeps its old header hash/algo and
  becomes unreadable under Strict (fail closed, functional only).

## Checked and found sound (how hard I tried)
- Descriptor decoder (`descriptor.rs`, `rvf-types/src/stream.rs`): all arithmetic is checked or u64-widened; `table_len = seg_count*72` is
  validated in u64; exact-length check precedes any index; every index into `bytes` is behind it. Signature is verified before the table
  is parsed; allocations before verification are bounded by `max_descriptor_bytes` (1 MiB). Oracle test `f10`: every single-bit flip of
  every byte, every truncation and one-byte extension of chunked and segment-granular descriptors is rejected (about 20k cases).
- Signature handling: `verify_strict`; key always from the trusted set, never from the descriptor; `signer_key_id` collision only
  selects which TRUSTED keys are tried; `sig_alg`/`hash_alg`/reserved bytes/`sig_len` are checked and signed; domain prefix
  `RVF-v1-stream-descriptor\0` is disjoint from segment signatures (`RVFS...`) and Level-0 pages (`RVM0...`).
- Leaf/table encodings: distinct tag bytes, fixed-width fields, `file_id`/`seg_id`/index/len bound; n==1 vs n>1 decided by the signed
  `stored_len`; tables for n<=1 are refused; no ambiguity found.
- Verifier: exact-next-chunk, every error path in `Receiving` is a counted fault or a poison (only `StreamBadState` from Suspended/Complete/Rejected is uncounted, and it changes nothing), released bytes are the hashed bytes (borrow of
  the pushed frame), requires_mask check precedes release, acyclicity check is correct (2-cycles and longer rejected), `Complete` needs every
  entry done and `verified_bytes == body_len`, zero/undersized segments rejected at the descriptor, exec/index header reads are length-safe
  (stored_len >= 64 and chunk >= 4096). Frame reader holds at most one frame, limits come from the signed descriptor, header bytes only before admission.
- Oracle `f08`: 20,000 random mutated streams (bit flips, dup, drop, swap, truncate, extend, cross-segment splice) with random splits, plus
  3,000 on 32-bit under qemu: no panic, every released chunk equals the signed body slice, no chunk released twice, Complete implies full coverage.
  Existing `stream_m1/descriptor/alloc/vectors` suites pass on armv7 musl under qemu. The three existing cargo-fuzz targets ran briefly with no crash (see limits).
- Portable `rvf_types::sha256` vs `sha2`: identical on 0..400 bytes, block boundaries and random splits (`f09`).
- Runtime Strict: empty trusted set refuses (never accept-all); CRC, sig_algo, sig_len, fingerprint match, signature, then binding of offset, length
  and SHAKE hash of the manifest, then trailer present; mode must be Aligned and algo 2; committed hash checked on every `read_seg`; keyed by the signed
  directory; replaying page P over a different manifest, appending after the page, swapping segments with recomputed header hashes (existing tests) all fail.
- Tail scanner (`tail_scan.rs`): no panicking index, `checked_sub`, extent math via `checked_add`/`try_from`.
- Runtime manifest parse: counts validated against payload size before allocation.

## Not checked / limits
- `StreamIngest`, rvf-server endpoints (out of scope). The shared JSON vectors and the `rvm` side.
- Only armv7 musl (32-bit) was run, not i686; no thumbv7 no_std build. No Miri / sanitizer runs on the verifier.
- Fuzzing was short: `rvsd_frames` 1.14M runs/121 s, `rvsd_descriptor` 328k runs/61 s, `rvsd_split` 159k runs/61 s, no crash (existing targets, repo seeds). Not a substitute for a long campaign.
- Timing side channels not analysed (public data). Concurrency between a Strict reader and a writer cutting the page was reasoned, not stress tested.
- Crash-consistency of the sign-on-commit protocol (kill between segments, manifest and page) was reasoned from code, not fault-injected.

---

# Round 2

Reviewed `origin/feat/ofer-streaming` at e466d903e merged into `feat/ofer-review-ruvector`. Original repros were re-run unmodified
(the F-06 test only adapted to the new pin API). Baseline results: F-01, F-02, F-03, F-04, F-05, F-06, F-12, F-14, F-16 no longer
reproduce; F-13 still reproduces (non-Strict, by design); F-11 fixed in `FrameReader` but see F2-11. New repros are in
`rvf-runtime/tests/review2_ofer_runtime.rs`, `review2_ofer_stream.rs`, `rvf-server/tests/review2_ofer_server.rs`; fuzz targets in `rvf-runtime/fuzz/`.
Tests named `f2_*`/`r2_*` that FAIL today are defect repros (they assert the desired behaviour).

## Fix verification

| Finding | Verdict | What I tried |
|---|---|---|
| F-01 compaction launders listed segment | closed | `r2_midsession_tamper_then_compact_is_refused` (file edited under an open `open_signed` handle, header hash recomputed): compact refuses. Original `f01` now fails as intended. `r2_midsession_vec_tamper_not_laundered`: Vec/Meta/Index/Journal are skipped by the verifier but rebuilt from memory loaded (and verified) at open, so a mid-session Vec edit does not reach the new file. |
| F-02 unlisted segment adopted | closed | original `f02` fails; `r2_injected_segment_with_witness_flow` (injection + audited query + compact + Paranoid open): injected WASM never becomes signed. Directory-only preservation, carried hash taken from the in-memory writer (not recomputed). |
| witness handling | sound | `r2_legit_signed_store_survives_all_ops`: kernel, eBPF, dashboard, WASM, audited queries, delete, two compactions, owner reopen and a third compaction all succeed, Paranoid open extracts every type, vector count correct. Witnesses are now listed in the signed directory (one manifest rewrite per audited query: cost, not a defect). No legitimate-store failure found. Residual: stores written by the pre-fix code with unlisted trailing witnesses lose those on first compaction (silently). |
| F-03 quadratic scan | closed, new availability edge (F2-07) | original `f03` now fails (linear, microseconds). |
| F-04/F-05 | closed | `Complete`/`CompleteUnverified` terminal, `poison()` is a no-op after completion, `FrameReader` reports bytes after completion without changing state. Original `f04`/`f05` fail as intended. |
| F-06 | closed | pin keyed by (signer_key_id, file_id), hash mandatory; equal-epoch/different-hash is `StreamEpochConflict`. |
| F-11 | partly (F2-11) | `FrameReader::admit` uses `usize::try_from`. `StreamIngest::feed` has its own framer without it. |
| F-12 | closed | `r2_f12_*`: plain `open()` of a signed store is write-blocked for ingest, delete, compact, embed, set_file_metadata; signature intact afterwards. |
| F-14 | **bypassed** (F2-10) | layout vote is spoofable through unhashed padding. |
| F-16 | closed for directory segments, open for the manifest header (F2-06) | `r2_f16_every_header_byte_is_pinned`: every bit of every header byte of a committed Vec and WASM segment is detected under Paranoid. |
| F-17 | capped, but see F2-09 | |

## New findings

### F2-02 (medium) A signed Layer A can hang every querying client
- Where: `rvf-index/src/progressive.rs:117` (`for vid in part.vector_id_start..part.vector_id_end`) reached from `progressive_stream/ingest.rs` `query`;
  `layers.rs` `decode_a` accepts any partition ranges.
- Test: `rvf-runtime/tests/review2_ofer_stream.rs::f2_02_hostile_partition_range_hangs_query` (defect; exits 101 after 5 s of no return).
  A one-centroid Layer A with partition `0..u64::MAX` makes `query` iterate 2^64 ids per probed centroid.
- Impact: any publisher key holder (a different tenant, or a compromised signer) stalls all clients that query between Layer A and Layer C.
  Also `StreamIngest::query` is unbounded in time for large legitimate ranges.
- Fix: validate ranges in `decode_a` against the declared id universe (and `end - start` against a policy cap), and have the search iterate
  the vector store's present ids in range instead of the numeric range; add a per-query work budget.

### F2-01 (medium) Verified-but-signer-controlled counts amplify memory 5-6x; INDEX/JOURNAL segments are fully buffered
- Where: `layers.rs` `decode_a`/`decode_b` (`Vec::with_capacity(n)` and `BTreeMap` inserts after a count bounded only by remaining bytes);
  `ingest.rs` `Parse::Buf` accumulates the whole segment before decode.
- Test: `f2_01_layer_decode_memory_amplification` (defect): 40 MB Layer A of empty top layers -> +234 MB resident (6x); 35 MB Layer B -> +194 MB (5x).
- Impact: with the default policy (1 GiB per segment, 1 TiB per class) a tenant publisher costs a client about 1 GiB buffer plus 5-6 GiB decoded, and
  interleaving first chunks of many INDEX segments holds all their buffers at once. The bound exists but is far above a client budget.
- Fix: per-ingest budget (bytes buffered + decoded estimate), smaller default class caps for Index/Journal, incremental decoding of layers.

### F2-03 (low/medium) Witness list silently stops recording at 4096 entries, dropping the terminal record
- Where: `ingest.rs` `witness()` (`MAX_WITNESSES`); `end_of_input`/`resume` each add one record per reconnect.
- Test: `f2_03_witness_cap_drops_the_terminal_record` (defect): 2100 suspend/resume cycles, then a bad frame: `StreamPoisoned` is not recorded
  although the stream is poisoned. RVM consumers revoke capabilities from that record.
- Fix: never drop terminal records (reserve capacity, or ring-buffer the Suspended/Resumed pairs and coalesce).

### F2-04 (low/medium) Frame log is overwritten from offset 0 when a recovered client resumes
- Where: `client.rs` `with_log` (`OpenOptions` without append, no seek to `ingest.offset()`; `set_len` does not move the cursor).
- Test: `f2_04_log_is_corrupted_when_a_recovered_client_resumes` (defect): log is 254458 bytes where the stream is 490883; the second `recover()` cannot replay.
- Impact: crash-recovery silently loses its spill (fail closed: nothing unverified is published, because `recover` re-verifies everything).
  A tampered log cannot publish data: `f2_oracle_hostile_logs` (60 truncated/flipped/extended/cut logs, plus a directory as log) never shows an unauthentic vector.
- Fix: `seek(SeekFrom::Start(offset))` after `set_len`, or open with append semantics.

### F2-05 (medium/low) Stream slots can be pinned indefinitely; the pool is shared with TCP 0x05
- Where: `rvf-server/src/stream.rs` `body` (permit moved into the response stream; blocking sender waits on a 4-slot channel; no write/idle timeout) and `tcp.rs` `handle_stream` (same `try_permit`).
- Test: `rvf-server/tests/review2_ofer_server.rs::f2_05_slowloris_pins_every_stream_slot`: two silent connections hold both slots for 4 s+; the next HTTP range request gets 429 and a TCP 0x05 request is refused.
- Fix: per-connection write timeout / minimum rate, per-IP cap, separate pools.

### F2-06 (low) The MANIFEST segment's own header is not pinned
- Test: `review2_ofer_runtime.rs::r2_f2_06_manifest_segment_header_bits_are_unpinned` (defect): under Paranoid, flips of header bytes 6-15 (flags, segment_id), 24-31 (timestamp), 33-63 (compression, reserved, content_hash, uncompressed_len, pad) are accepted.
  The page binds offset, length and payload hash only. Nothing in the runtime reads those fields; other readers of a "verified" file might.
- Fix: check the manifest header like directory segments (`Committed::header_ok`).

### F2-07 (low) 256 fake candidates hide the real manifest (availability)
- Where: `read_path.rs` `MAX_PARSE_ATTEMPTS`/`scan_blocks`.
- Test: `r2_hide_real_manifest_behind_fake_candidates_plain` and `..._strict` (defects): 300 fake manifest headers appended after the real manifest (Strict: between manifest and page) make the file unopenable. The scan returns the newest 256 candidates only.
- Selection of a fake did not become easier: a fake must still parse within the first 256 and, under Strict, match the signed page (a parseable fake newer than the page makes the open fail instead of falling back to the page-named manifest). Needs write access; a tenant's vector bytes cannot place candidates after the newest manifest except in crash leftovers.
- Fix: under a signed page, jump straight to `expect_offset` instead of scanning newer candidates; otherwise skip candidates whose declared extent overlaps the next candidate.

### F2-08 (low/info) `stage_plan` unchecked arithmetic
- `build.rs:236-240`: `off + SEGMENT_HEADER_SIZE + plen` with a hostile `payload_length` panics in debug (`f2_08_...`); release wraps and the builder then errors. Server start-up path for the served body; operator-supplied file.

### F2-09 (low) `max_table_bytes` default (64 MiB) is below what the other defaults allow
- `rvf-wire/src/stream/verifier.rs` `on_table`/`mod.rs`: tables are now retained for the whole stream (needed for duplicate checks) and capped at 64 MiB. Table bytes are 32 per chunk: a legitimate body of about 8 GiB at 4 KiB chunks or 128 GiB at 64 KiB chunks exceeds the cap, although `max_body_len` defaults to 1 TiB. Such a stream faults on its tables and poisons. Arithmetic only, not reproduced. Align the defaults.

### F2-10 (low, non-Strict) F-14 fix bypassed: the layout vote can be forced to a tie
- Where: `read_path.rs:125-157` `mode_for_file`.
- Test: `r2_f14_padding_plant_forces_byte_granular` (defect): write `RVFS` + version 1 + type 1 into the (unhashed) zero padding after the first segment's payload (at `unpadded`), set the first segment's `checksum_algo` to 0. Both candidate positions now hold a valid header, the vote falls through to the algo byte, byte-granular scanning is chosen and the runtime follows an unaligned fake manifest (0 vectors) while rvf-wire's aligned scanner still sees the real one. Strict is unaffected.
- Fix: require the padded position to be the only valid header and treat a valid header inside padding as corruption, or ignore the algo byte unless the whole walk is unpadded.

### F2-11 (low, 32-bit + non-default policy) `StreamIngest::feed` overflows `hdr + declared as usize`
- `ingest.rs:242`. Test `f2_11_ingest_total_overflows_on_32bit` (cfg 32-bit, armv7 musl under qemu): debug build panics "attempt to add with overflow"; release wraps to a runt frame that poisons (fail closed). Same fix as `FrameReader::admit`.

### F2-12 (info)
- `rvf-server` stream endpoints are unauthenticated; the whole store is downloadable. The served body path and the key path are operator-supplied (no request-controlled path, no traversal surface); error strings contain only the configured paths, never key bytes; the key is read once and not logged (hex copy not zeroized).
- A body without a root page gets `file_id = [0; 16]` (`stream.rs` `load`), so all such bodies signed by one key share a pin namespace.
- `StreamIngest` is not `Send` (policy holds `dyn Fn`); `query` computes `k + deleted.len().min(k)` and overflows for `k` near `usize::MAX`; `VerifiedVectors` slot index is `u32`; vectors from different segments and anchors with the same id overwrite each other (last writer wins, signer-controlled); `visible_vectors` counts tombstoned ids; Layer A with a dimension different from the VEC dimension is published and its anchors silently dropped.

## Rechecked and sound
- Poison/unpublish: `stream_ingest_feed` fuzz asserts that after `Poisoned`/`Rejected` no vector and no layer is visible and `sealed` is true only in `Complete`; duplicate/late frames after completion are refused without changing state; authentic duplicates are idempotent and capped.
- Visible vectors are always authentic (fuzz oracle against the dataset), `VecParse` bounds counts against the verified payload length and is split-independent.
- Client against a lying HTTP/TCP transport: Content-Length/Content-Range/total consistency, chunked refused, header size cap, bounded reply sizes; anything that passes is still chunk-verified (existing mirror tests plus my reading). Refusal/stall budgets bound retries.
- Server: Range parser (multi-range, suffix, overflow, leading `+`/zeros, odd spacing), 300 random TCP 0x05 frames, `u64::MAX` offsets and `u32::MAX` lengths: no panic, process stays up (`f2_oracle_hostile_inputs_do_not_panic`).

## Fuzz (bounded)
| target | runs | result |
|---|---|---|
| `rvsd_frames` | 725,684 / 91 s | no crash |
| `rvsd_descriptor` | 322,330 / 61 s | no crash |
| `rvsd_split` | 163,192 / 61 s | no crash |
| `tail_scan_differential` | 5,012,487 / 91 s | no crash |
| `stream_ingest_feed` (new, structure-aware: flips/drops/dups/swaps/truncations/splits of a real signed stream; authenticity, poison-clears-state and sealed invariants) | 59,184 / 241 s (about 245 exec/s, each run replays a 2,600-vector stream) | no crash |
| `server_stream_frames` (new, loopback sockets: arbitrary TCP bytes, 0x05 payloads, HTTP Range strings, plan ranges; panic hook aborts) | 14,734 / 151 s | no crash |

Not covered: wall-clock memory ceilings on 32-bit runtime builds beyond F2-11, long fuzz campaigns, server behaviour under real network partitions, TLS (none).

---

# Round 3

Merged `origin/feat/ofer-streaming` at 8600c66b5 (PinStore, completion re-check, chunk-wise `finish_identity`, R2 fixes). Original F2 repros kept as baseline and re-run
unmodified. New repros: `rvf-runtime/tests/review3_ofer.rs`, `rvf-server/tests/review3_ofer_server.rs`. Tests that FAIL today are open defects.

## What no longer reproduces (original assertion now fails or passes as "fixed")
F2-01 (decode now returns `None` at 2x payload + 4 KiB; `f2_01` fails at "decodes"), F2-02 as written (`0..u64::MAX` range returns at once),
F2-03 (terminal witness kept), F2-04 (log append), F2-05 as written (silent clients freed after `idle_timeout`; separate TCP pool),
F2-06 (manifest header pinned), F2-07 (300 fake candidates no longer hide the manifest, plain and Strict), F2-08, F2-09 (default `max_table_bytes` = 8 GiB, see F3-06),
F2-10 (padding plant no longer selects byte-granular), F2-11 (armv7 under qemu: `StreamFrameSizeLie`, no panic; also the FrameReader split-header path is a clean poison; my older `f11` "ok" is a false positive from the test's own `unwrap`).
F-04/F-05 originals also fail as intended; F-13 (non-Strict planted manifest) remains by design.

## Still open or new

### F3-01 (medium) F2-02 not closed: overlapping partitions multiply query cost
- Where: `rvf-index/src/progressive.rs:113-127` with the new `VectorStore::for_each_in_range` (`vectors.rs:92`). Each partition matching a probed centroid costs up to one step per visible vector and pushes a candidate per hit; nothing bounds the number of partitions or de-duplicates overlapping ranges. `decode_a`'s only range check is `end >= start`.
- Test: `review3_ofer.rs::f3_01_overlapping_partitions_multiply_query_cost` (defect): 250/500/1000 identical `0..u64::MAX` partitions over 20,000 vectors cost 0.15/0.29/0.60 s (linear in partitions; 1000 partitions is a 20 KB payload). A 20 MB Layer A carries about 1M partitions: roughly 10 minutes and about 2x10^10 candidates (tens of GB) per query.
- Other hostile ranges tried: ids near `u64::MAX`, inverted, zero-width, width exactly `slot.len()` (both branches of `for_each_in_range`) are safe (no overflow, bounded by one pass over present ids). Partition-count lies are bounded by the payload bytes (and 2x budget).
- Fix: cap `partition_map.len()` (and total decoded partition coverage) in `decode_a`, merge/validate non-overlapping ranges, and de-duplicate by iterating the union of ranges once; add a per-query work budget.

### F3-02 (medium/low, freshness) The "ignore newer manifests under a signed page" change enables rollback by swapping only the 4 KiB page
- Where: `read_path.rs` `ScanHint::expect_offset` / `store.rs` `boot_with_ancestry`.
- Test: `review3_ofer.rs::rollback::f3_02_page_swap_rolls_back_without_truncation` (defect): signed store (12 vectors) ingests 6 more (18). Writing the old page P1 over the new one: Strict/Paranoid open succeeds and serves 12 vectors; the newer segments and manifest are still in the file. Before the change this was refused (newest manifest != page). Rollback by truncation was always possible and the runtime has no freshness anchor; the new behaviour removes the need to truncate and keeps the newer bytes in the file.
- Not exploitable for a forged state (the page still has to match a signed manifest). Planting a newer manifest no longer causes DoS (intended).
- Fix: expose a minimum-epoch / pin hook on `open_with_policy` (the page and manifest both carry an epoch), and when a parseable manifest newer than the page-named one exists, report it (warning or `RollbackSuspected`) instead of silently ignoring it; document that Strict alone gives authenticity, not freshness.

### F3-03 (low) `commit_pin` is not idempotent for identical concurrent sessions
- Where: `MemoryPinStore::advance` compares `cur != expected_current` before considering `cur == new`; `verifier.rs` `commit_pin` uses the pin seen at admission.
- Test: `f3_03_identical_concurrent_session_gets_spurious_conflict` (defect): two verifiers admit the same descriptor with an empty store; the first commits; the second gets `StreamEpochConflict` although the stored pin equals what it would write, contradicting the trait's "re-recording the identical pin is a no-op success". Fail-closed; legitimate parallel downloads of one artifact see an error.
- The core race is handled: a session superseded by a later epoch gets `StreamStaleEpoch` at the completion re-check and again at `commit_pin` (reasoned through both interleavings; recheck is not atomic with consumption, which the docs state).
- Fix: in `advance`, return `Ok` first when `cur == Some(new)`.

### F3-04 (info) Tombstones and vectors are not charged to the ingest budget
- Test `f3_04_tombstone_set_growth_is_unbudgeted` passes at 1.6x resident per wire byte (47 MB of journal segments -> +76 MB). Memory is proportional to bytes streamed (and per-class caps), not to the 256 MiB buffer budget; a 1 TiB default body can still mean hundreds of GB of visible vectors and tombstones. Harmless for honest sizes; document it, or add `max_visible_vectors` / `max_tombstones`.
- INDEX/JOURNAL buffering is correctly bounded by `buffer_budget` (256 MiB, overflow poisons with `StreamLimitExceeded`; also means a legitimate Layer C above 256 MiB is refused unless `set_buffer_budget` is raised; `Vec` doubling can transiently hold 2x). Repeated Layer A segments replace the layer but each adds its anchors to `VerifiedVectors`; bounded by wire bytes.

### F3-05 (low) Slot pinning narrowed but not removed
- Test: `review3_ofer_server.rs::f3_05_slow_reader_keeps_slot_until_total_deadline` (defect; `SLEEP_MS` knob). With `idle_timeout` 2 s: silent clients are released (oracle passes); clients reading about 80 KB/s total lose their slots; two readers at about 400 KB/s each (3 Mbit/s) keep every slot (429 for others) for up to `total_deadline` (default 3600 s). 8 modest connections can monopolise the default pool for an hour.
- Fix: minimum-rate rule (bytes per window), per-client slot cap, shorter default `total_deadline` for ranged requests (a 256 MiB range needs seconds).
- Pre-existing and unchanged: TCP connections themselves are unlimited; each may announce a 16 MiB frame (zeroed `Vec`, lazily committed) before sending it.

### F3-06 (hardening/doc) Default `max_table_bytes` of 8 GiB no longer bounds memory meaningfully
- `mod.rs`: `(1<<40)/4096*32` = 8 GiB, derived from the 1 TiB body limit at 4 KiB chunks. Retained tables (`SegState.leaves`, kept for the whole stream for duplicate checks) can therefore reach 8 GiB per stream, and a server holding several concurrent verifiers multiplies it. It is correct (no legitimate stream is refused) but it is a ceiling, not a protection. Recommend documenting that deployments must lower `max_body_len` and `max_table_bytes` together, or storing leaves lazily (re-derive from the table frame hash on demand / evict finished segments and verify duplicates by re-hash only).

## Rechecked and sound
- PinStore: admission read, completion re-check (`finish()` -> poison with `StreamStaleEpoch`/`StreamEpochConflict`), CAS never moves a pin backwards, `commit_pin` only from `Complete`; `StreamIngest::query` re-checks the pin on every call so a superseded session reports `sealed=false`.
- Chunk-wise `finish_identity`: leaf and identity hashes are computed from the same buffer reads, every leaf must equal the verified leaf, a host supplying different bytes poisons, a failed read returns `StreamBadState` without changing state; `entries.clone()` is the only extra allocation.
- `for_each_in_range`: bounded by present ids; saturating/exclusive-end arithmetic; the two branches agree.
- F-16/F-12/F-01/F-02 re-run: unchanged and closed (`review2_ofer_runtime` 10/10).

## Fuzz (60-120 s each, final merged code)
| target | runs | result |
|---|---|---|
| `rvsd_frames` | 712,054 / 91 s | no crash |
| `rvsd_descriptor` | 487,210 / 91 s | no crash |
| `rvsd_split` | 236,773 / 91 s | no crash |
| `tail_scan_differential` | 2,315,132 / 91 s | no crash |
| `stream_ingest_feed` | 38,647 / 121 s | no crash |
| `server_stream_frames` | 18,676 / 121 s | no crash |

Not covered: i686, Miri/sanitizers on the verifier, multi-hour fuzzing, real-network behaviour.

---

# Round 4

Merged `origin/feat/ofer-streaming` at 00ee404a7. R3 repros kept as baseline; new ones are appended to `rvf-runtime/tests/review3_ofer.rs` (`f4_*`) and `rvf-server/tests/review3_ofer_server.rs`.
Tests that FAIL today are open defects.

## R3 baseline outcome
Closed (original defect assertions now fail or pass as "fixed"): F3-01 (overlapping/duplicate partitions rejected at decode: sorted + disjoint, `MAX_PARTITIONS` 65,536; the hostile stream is refused at Layer A), F3-02 default (plain page swap is refused), F3-03 (`advance` idempotent), F3-05 (min-rate + per-client caps present, see F4-06), F3-06 (tables freed on completion).

## Verification notes
- **F3-01:** disjoint-but-many partitions are bounded by 65,536 entries and one pass over present ids in total; layer search additionally runs under a deterministic step budget (`BudgetedStore`: lookups and range passes, default 1M + 16/visible). Exhaustion yields `work_truncated = true`, quality `Degraded` (never `Verified`), `BudgetExhausted` degradation and `sealed` unchanged (true only in `Complete`), so an answer is partial but never falsely complete. Residual: the centroid scan/sort in `search_layer_a_only` is not charged (F4-02).
- **F3-02 options:** default refuses a newer parseable manifest beyond the page (`ContentHashMismatch`, pointer `newer_manifest_beyond_signed_page`); `serve_signed_prefix = true` serves the signed state and exposes `newer_manifest_ignored()`; `min_epoch` refuses older state with `StreamStaleEpoch` on Strict and Paranoid. The attacker cannot choose refuse vs serve (caller option), but can suppress the evidence (F4-04).
- **F3-03:** `f4_oracle_pin_advance_matrix` (passes): identical re-record with stale expectation ok; different hash at the same epoch fails (with fresh or stale expectation); lower epoch fails; higher epoch needs the current expectation; never backwards; lineages independent.
- **Presets:** `conservative()` and `embedded()` are self-consistent (table caps derive from body limits: 128 MiB and 2 MiB); note descriptor-size caps (256 KiB / 64 KiB) bound `seg_count` to about 3,600 / 900 in practice.
- **Query policy:** `unpublished` is set by `after_push` on every terminal transition, vectors are cleared, and `ok_query` requires `!unpublished && visible > 0`; fuzzed (below). `sealed` derives from `Complete` + pin recheck. `coverage_vectors` is a conservative estimate (visible / (stored VEC bytes / record size)), 0 before the descriptor/any record, <= 1.
- **Server:** per-client caps key on `ConnectInfo<SocketAddr>` (the socket peer); no header (`X-Forwarded-For` etc.) is read anywhere. HTTP producer is now an async task using `send_timeout(idle)` plus a deadline check per piece and a per-window min-rate rule; no deadlock found, and the permit/client slot are held by the task and released when it ends, so a slow client holds a slot for at most `total_deadline` + `idle_timeout` (default 600 s + 30 s).

## New findings

### F4-01 (medium) `Reserve` prepays memory for the DECLARED size of a VEC segment
- Where: `vectors.rs` `VecEvent::Reserve` / `VerifiedVectors::reserve` (`slot.reserve`, `ids.reserve`, `data.reserve`), emitted from the first 6 payload bytes.
- Test: `f4_01_reserve_prepays_declared_segment_size` (defect): a signed descriptor claiming one 512 MiB VEC segment, with only its 64 KiB first chunk and the 256 KiB table on the wire (320 KB total), grows the process by 1,600 MB of address space and 85 MB resident. Resident cost per claim is about 270x the wire bytes; address-space about 5,000x.
- Impact: a hostile or buggy publisher (a different tenant) makes a client commit memory for data it never sends. Many such segments (up to the 1 TiB class cap, or a few thousand 1 GiB claims) exhaust RAM or abort on allocation failure; small devices fail at the first claim. The ingest buffer budget does not cover it. Before the optimisation memory followed received bytes.
- Fix: reserve only what has arrived (reserve per received chunk, or cap `Reserve` at the bytes in hand plus a small factor) and include reserved bytes in the ingest budget.

### F4-04 (low/medium) Rollback evidence is suppressible; the default is not a freshness guarantee
- Test: `rollback4::f4_04_page_swap_plus_hidden_newer_manifest_defeats_the_default` (defect). A plain page swap is refused by default (fix works), but swapping the page and flipping one byte of the newer manifest's header makes the scan not see it: the old state is served silently with default options (12 of 18 vectors). The same effect is available with more than 256 junk candidates after it. `min_epoch` is the only real control; its default of 0 means none.
- Fix: document that Strict gives authenticity only; make `min_epoch` (or a pin store) a required argument of a "fresh" open path, record the accepted epoch durably, and treat a page whose epoch is below the manifest epochs seen anywhere in the file as tampering (the page carries an epoch field that is compared to nothing).

### F4-05 (low) After a multi-chunk segment's table is freed, a late chunk of the right length is accepted as `Duplicate` without any hash check
- Where: `verifier.rs` `on_duplicate_chunk` (the freed-table branch).
- Test: `f4_05_late_garbage_duplicate_is_accepted_after_table_freed` (defect): arbitrary bytes of the right length for chunk 1 of a finished 4-chunk segment return `Ok(Event::Duplicate)`. Nothing is released or applied (ingest ignores duplicates), and each is charged to the duplicate cap (`4 x chunks + 64`), but the event's documentation says "authentic". A consumer or the frame log that treats `Duplicate` as authenticated will log garbage.
- Late table frames for a finished segment and wrong-length chunks are still refused/poisoned (checked). Fix: report these as `Ignored` (a different event), or refuse them as unexpected frames; do not log them.

### F4-06 (medium/low) Per-client caps do not stop address diversity; the pool is small
- Test: `f4_06_two_addresses_pin_the_whole_pool` (defect; uses loopback aliases `127.0.0.2/3`): two source addresses at the default cap of 4 each hold all 8 slots for 14 s while reading above the 32 KB/s floor; a third address then gets 429. The fifth connection from a holder address also gets 429 (the cap itself works). IPv6 is worse: caps key on the full address, so one /64 rotates addresses freely; IPv4-mapped IPv6 would key separately from IPv4.
- Without `into_make_service_with_connect_info` (any embedder that mounts `stream::router` directly, as the test harness does) `peer` is `None` and the per-client cap is silently skipped (fail-open).
- Fix: key IPv6 by /64, normalise mapped addresses, scale per-client share with pool use, fail closed (or log loudly) when the peer is unknown, and consider larger pools or a minimum rate that rises with contention.

### F4-02 (low/info) The deterministic query budget does not cover the centroid scan
- `progressive.rs` `search_layer_a_only` computes distances to all centroids and sorts them before any store lookup. Measured (dim 8): 250k centroids 4 ms, 500k 8 ms, 1M 23 ms per query with a 1,000-step budget and `work_steps = 0`. Bounded by the 2x decode cap (about 8M centroids at the 256 MiB buffer budget: roughly 0.2 s/query). Charge centroid work to the budget or cap centroid count.

### F4-03 (low/info) `Auto` scans every arrived vector when no Layer A exists
- `query.rs`: `!can_layers || visible <= threshold`. Measured: 4.0M dim-1 vectors scanned in 4.2 ms, i.e. cost tracks received bytes (about 10 GB/s), so a 1 GiB layerless stream costs about 0.1 s per query (more for large dimension). The 25 ms latency bound applies only when layers are available. Fix: cap the scan at `scan_threshold` rows and report coverage when no layers exist, or document it.

### Minor
- `ScanOnly` mode is unbounded by design; `scan_ns_per_vec` is an exponential average of the last scan, so one unusually fast scan raises the threshold for the next (self-correcting).
- Pre-existing and unchanged: TCP frames may claim up to 16 MiB before sending; `StreamIngest` is not `Send`.

## Fuzz (90-120 s each, final merged code, no crashes)
| target | runs |
|---|---|
| `rvsd_frames` | 801,119 / 101 s |
| `rvsd_descriptor` | 556,388 / 101 s |
| `rvsd_split` | 268,528 / 101 s |
| `tail_scan_differential` | 2,842,305 / 111 s |
| `stream_ingest_feed` | 38,002 / 111 s |
| `server_stream_frames` | 18,394 / 111 s |
| `stream_query_interleave` (NEW: `query()` in all three modes interleaved with `feed()` over mutated streams; asserts returned ids are visible and authentic, `sealed` only in `Complete`, coverage in [0,1] and monotone until a terminal failure, empty results and zero visible vectors after Poisoned/Rejected, empty before any vector) | 21,258 / 111 s |

## RELEASE RECOMMENDATION (ruvector side)
No known critical open. One medium blocker candidate for a release that exposes streams to untrusted publishers: **F4-01** (declared-size prepay, memory amplification about 270x resident from a signed message). It is a small fix (reserve per received chunk). With that fixed, or with the release scoped to trusted publishers, the recommendation is: no known high/critical open. F4-04 and F4-06 are deployment caveats to document (freshness needs `min_epoch`; per-client caps are not a DoS defence against multi-address attackers); F4-02/03/05 are low.

---

# Round 5 (final)

Merged `origin/feat/ofer-streaming` at 82d5ba746; baseline repros kept. New repros: `review3_ofer.rs` (`f5_*`), `review3_ofer_server.rs` (`f5_06`).

## Result per F4 finding
- **F4-01 closed.** The 512 MiB-declared / 320 KB-delivered case now grows the process by +0 MB virtual and +0 MB resident (was +1,600 MB / +85 MB). Forty segments each declaring 512 MiB (20 GiB claimed; first chunk and table of each delivered, 12.8 MB on the wire) grow virtual +6 MB and resident +17 MB (the retained tables account for most of it). Memory now follows received chunks (`f5_01_many_declared_segments_do_not_prepay`).
- **F4-04 closed.** Freshness unset -> `FreshnessRequired`; `MinEpoch(MAX)` refuses; the original page swap, swap + one-byte flip of the newer manifest, 64 B / 4096 B zero bytes and a 1-byte tail between manifest and page are all refused as an unsigned tail (`f5_04_rollback_variants`). Residual by design: rollback by truncating to an older signed state is accepted under `Freshness::Unchecked`; only `MinEpoch` or an external pin detects it.
- **F4-06 closed for the reported attack, bounded residual remains.** Two addresses (same /24) can no longer pin the pool, and a router without connect-info is refused with 503. No header is consulted anywhere (grep for forwarded/real-ip: none). Eight distinct /24 prefixes, one stream each at about 400 KB/s, still fill the 8-slot pool and a ninth prefix gets 429 (`f5_06_many_prefixes_still_fill_the_pool`). That is inherent to a bounded pool; it costs the attacker eight prefixes and about 3 MB/s. Document it; use a front proxy or larger pool.
- **F4-02/03 closed.** 250k/500k/1M centroids and 4M arrived vectors now exhaust the query work budget immediately and report `work_truncated = true` (degraded, never sealed).
- **F4-05 closed.** A late garbage chunk of a finished multi-chunk segment returns `Event::Unverified`; 88 such frames were accepted and the 89th poisoned the stream (`StreamDuplicateFlood`); `verified_bytes` did not move; ingest ignores the event (no vector or layer changes); a late table frame is still refused (`f5_05_unverified_events_are_inert_and_capped`). `PinStore::advance` matrix still passes.

## Fuzz (90 s each, no crashes)
`rvsd_frames` 702,848; `rvsd_descriptor` 485,348; `rvsd_split` 240,023; `tail_scan_differential` 2,792,346; `stream_ingest_feed` 27,957; `server_stream_frames` 13,301; `stream_query_interleave` 20,739.

## RELEASE RECOMMENDATION (ruvector side)
No known critical, high or medium open; F4-01 is closed. No blockers. Document these accepted residuals: Strict gives authenticity, freshness only with `Freshness::MinEpoch` or an external pin (truncation rollback under `Unchecked`); the HTTP stream pool is bounded, so a many-prefix attacker can still exhaust it; and `F2-12`/`F3-04` style memory growth proportional to the bytes streamed (no cap on visible vectors).
