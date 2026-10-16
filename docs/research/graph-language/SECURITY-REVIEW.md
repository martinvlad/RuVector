# RuGraph scoped security review

Date: 2026-10-16. Scope: the two new Rust crates, SDKs, CLI, their boundaries,
and the additive GraphDB visitor API. Authorized work: implementation, local
read only scanning and correction of defects in the new implementation. No
production systems, external provider credentials or real user data were used.

## Trust model

| Boundary | Threat | Mitigation and residual responsibility |
|---|---|---|
| Untrusted text/JSON → program | Type confusion, duplicate fields, excessive input | Strict parsing, version checks, one representation, hard size/depth bounds |
| Program → host authority | Self granted permissions or arbitrary effects | Host grants checked separately; only three effects; no general I/O operations |
| Snapshot → runtime | Dangling references, oversized properties, excessive derivation | Validation, work and result limits, bounded provenance, fixed point over admitted facts |
| GraphDB → snapshot | Allocation before checking; inconsistent concurrent reads | Borrowed bounded visitors; caller must exclude every writer |
| Predictor → language | Mislabelled scores, malformed output, excessive results | Typed isolation, finite/identity/count checks, native preflight; custom predictors are trusted code |
| Model file → native scorer | Invalid shape, nonfinite weights, forged claimed metrics | Strict artifact bounds and native validation; host trusts producer or reruns evaluation |
| SDK → local executable | Shell injection, output flood, indefinite process | Argument arrays, explicit paths, timeout and bounded pipe draining |
| Receipt → consumer | Tampering or treating a checksum as authenticity | Checksum verification and full replay; authentication is explicitly outside scope |

## Confirmed fixes and validation

The independent review confirmed oversized graph capture and native prediction
allocation paths. Both were fixed at the boundary before copying or accumulating
payloads. Regression tests and the repeated native memory reproducer pass.
JSON roundtrip, request validation, nested canonical hashing, Python output
draining, JavaScript numeric precision and CLI preflight defects were also fixed
and covered by executed tests. No unresolved high or critical finding remains
within this focused code review scope.

The SDK executable and model paths are trusted host configuration. The clients
are not OS sandboxes for arbitrary hostile binaries. A trusted custom Rust
Predictor can perform work outside the interpreter's accounting; only the
provided native implementation preflights its internal scoring work.

## Tools and coverage

Read only scans used the validated `@claude-flow/cli@3.25.6` runtime:

```bash
npx --yes @claude-flow/cli@3.25.6 security scan \
  --target crates/ruvector-language --depth deep --type all
npx --yes @claude-flow/cli@3.25.6 security scan \
  --target crates/ruvector-language-native --depth deep --type all
npx --yes @claude-flow/cli@3.25.6 security scan \
  --target python/ruvector-language --depth deep --type all
```

The npm package was copied into an isolated temporary directory, its empty
dependency lockfile generated with scripts disabled, and both `npm audit --json`
and the same Ruflo scan run from that directory. This avoids auditing the
monorepo parent's unrelated npm dependency tree. The SDK declares no runtime or
development dependencies; the isolated audit reported zero dependencies and zero
advisories. Scoped Ruflo scans reported no findings. Scanner output is supporting
evidence, not a proof of safety.

Scan date and npm advisory retrieval date: 2026-10-16. The service did not expose
an advisory database snapshot timestamp, so an exact feed revision is unknown.
Cargo transitive advisory auditing was not performed; no Rust dependency
cleanliness claim is made. Python build tools and the host runtime are outside
the zero runtime dependency claim. Root repository vulnerabilities were not
assessed or remediated by this feature review.

Rust lockfile hashes, compiler versions, full acceptance commands and results
are recorded in [ACCEPTANCE.md](ACCEPTANCE.md). No secret values are included in
this report or the committed fixtures.
