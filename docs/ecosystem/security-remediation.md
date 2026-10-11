# Workspace security remediation — 2026-10-11

This change patches three compatible dependencies in `npm/package-lock.json`. It does **not** certify the complete npm workspace or all published packages as secure. The repository's new standalone constellation package has a separate dependency graph and release gate.

## Evidence and scope

The [Dependabot snapshot](dependabot-2026-10-11.json) contains 52 open advisory instances across JavaScript and Rust manifests: 5 critical, 15 high, 28 medium, and 4 low. These are not the same counting unit as npm audit's vulnerable dependency nodes, which include propagated findings in parent packages.

| Root npm lock audit | Before | After |
| --- | ---: | ---: |
| Critical nodes | 4 | 2 |
| High nodes | 39 | 38 |
| Moderate nodes | 10 | 10 |
| Total nodes | 53 | 50 |

Both audits used `npm audit --package-lock-only --ignore-scripts --json`. The remaining audit exits nonzero; a smaller count is not a clean security result. GitHub will re-evaluate alerts after the updated lock reaches its monitored branch; no alerts were manually dismissed.

## Compatible patches applied

| Package | Locked before | Locked after | Advisory evidence |
| --- | --- | --- | --- |
| `handlebars` | 4.7.9 | 4.7.10 | [GHSA-8r5x-fm3f-whwj](https://github.com/advisories/GHSA-8r5x-fm3f-whwj), [GHSA-p8wg-vrv2-v86f](https://github.com/advisories/GHSA-p8wg-vrv2-v86f), [GHSA-xw65-4hp5-5hc7](https://github.com/advisories/GHSA-xw65-4hp5-5hc7) |
| `proxy-addr` | 2.0.7 | 2.0.8 | [GHSA-jqcg-44mw-7w3h](https://github.com/advisories/GHSA-jqcg-44mw-7w3h) |
| `source-map-js` | 1.2.1 | 1.2.2 | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) |

Every incoming locked dependency range admits the corresponding patch: Handlebars `^4.7.9`; proxy-addr `^2.0.7` or `~2.0.7`; source-map-js `^1.0.1`, `^1.2.0`, or `^1.2.1`. No global override or forced major update was introduced. Registry URLs, integrity values, dependency metadata, and engines were taken from an npm-generated isolated lockfile for these exact releases. Only their entries were transferred; existing development flags were retained. Handlebars' updated minimist range `^1.2.8` is satisfied by the existing 1.2.8 resolution.

A clean isolated project containing all three exact patched dependencies passed `npm ci --ignore-scripts --no-fund` and its install audit. Runtime smoke checks verified Handlebars HTML escaping, proxy address selection with loopback trust, and a source-map generation/consumption round trip. These checks validate the patched packages, not every workspace consumer.

## Resolver corrections and remaining blockers

The existing `@ruvector/agentic-synth` manifest requested Vitest `^4.1.11` but coverage-v8 `^3.2.6`, whose resolved 3.2.7 release requires Vitest exactly 3.2.7. Registry metadata confirms coverage-v8 4.1.11 peers with Vitest 4.1.11. Aligning the coverage dependency with the existing Vitest major is a required follow-up, together with a complete resolver-generated lock and coverage-suite validation. This change leaves the existing coverage manifest and lock entries untouched because full dependency resolution is blocked; no coverage upgrade or passing coverage suite is claimed.

`npm audit fix --package-lock-only --ignore-scripts` and `npm ci --dry-run --ignore-scripts` stop with `ERESOLVE`: agentic-synth declares optional peer `ruvector: ^0.2.0`, while the root lock links the RuVector workspace at 0.3.0. Optional peers still constrain an installed package. Resolve this contract using consumer compatibility tests before widening the range; simply ignoring peers would hide the problem. A workspaces-disabled remediation attempt also encounters the same conflict. No `--force` or `--legacy-peer-deps` was used.

The remaining critical audit nodes are `tinypool` and its affected Vitest parent. Dependabot records tinypool fixes at 2.1.1 and 2.1.2; audit proposes a Vitest/coverage family major migration to 5.0.3. That requires coordinated framework, coverage, UI, configuration, Node-engine, and test validation. Do not force tinypool 2.x under an older Vitest dependency contract.

Other unresolved findings include MCP SDK, axios, compression, brace-expansion, js-yaml, qs, ip-address, and propagated Jest/micromatch nodes. Some have compatible fixes, but the blocked workspace resolver prevents safely regenerating the complete graph in this change. Jest-related audit recommendations include a major migration to 30.5.2; nodemon recommendations also change its version contract. Review each consumer rather than automatically accepting audit's proposed version. Cargo lockfile findings in the snapshot are outside this npm lock remediation and remain open.

## Completion criteria

Fix the existing workspace peer contracts with consumer evidence, regenerate the lock without peer bypasses, rerun a clean workspace install, run the affected test and coverage suites, and require an acceptable audit result before releasing affected packages. Then verify each packed package independently: a workspace lock update does not retrofit dependencies into already published tarballs or establish platform-binary compatibility.
