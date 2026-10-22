# RuVector JevBench author-engine candidate

Candidate `ruvector-native-submission-round2-v2` scored **104/183 (56.83%)** on
an older public development snapshot: original **56/72**, hard **48/111**, all183
strict-valid, zero query errors. It gained4 cases with zero regressions against
the exact100 pipeline. These public cases were used for adaptive development and
rule selection. This is not an official Capability, current-release score, sealed
result, or leaderboard placement. `official_rank` remains null.

The pipeline executes actual `@ruvector/typesafe@0.2.0` native BGE-small inference
for every request and adds four finite source-linked typed relation validators.
The native77 and exact100 fallback answers are retained. The native binary and
embedding weights are unchanged; no model training or vector-index-only gain is
claimed. Unsupported, conflicting, ambiguous, or incomplete rule inputs retain
the prior pipeline. Probabilities are explicitly uncalibrated.

## Setup

Use Python3.12 and Node>=18 on **Linux x86-64 with glibc** for the exact pinned
native-binary identity. The validation machine uses Node24.19.0. From this kit's
root directory (the directory containing package.json):

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 acquire_models.py
PYTHONDONTWRITEBYTECODE=1 python3 experiments/submission-2026-10-22/jevbench/serve.py --policy-directory experiments/submission-2026-10-22/jevbench/round2-v2 --runtime-manifest experiments/submission-2026-10-22/jevbench/runtime-manifest.json --validate-only
PYTHONDONTWRITEBYTECODE=1 python3 experiments/submission-2026-10-22/jevbench/serve.py --policy-directory experiments/submission-2026-10-22/jevbench/round2-v2 --runtime-manifest experiments/submission-2026-10-22/jevbench/runtime-manifest.json --host 127.0.0.1 --port 8787
```

The service speaks `POST /v1/systemone`. It starts on loopback; deployment and any
external access are an operator action. SIGINT/SIGTERM closes the native child.
`--validate-only` verifies all37 selected source files and all3 model assets,
without running inference. The model acquisition script uses immutable public
revision URLs, validates SHA256/length before atomic installation, and refuses to
overwrite an existing mismatched asset. `python3 acquire_models.py --verify-only`
validates assets already present. No credentials or hosted inference are required.

`assets.lock.json` pins Xenova BGE revision
`ea104dacec62c0de699686887e3f920caeb4f3e3`; model SHA starts `828e1496`, tokenizer
SHA starts `d241a60d`. Native binary SHA is
`e4db4b945a91b5cb8937765236e180763e8a3f4866b791e0f71a98d0018c289d`.
A different binary/platform is a different reproducibility configuration.

## Saved evidence replay

This command uses **Python standard library only**, no Node, models, dependency
install, network, HTTP, native calls, or paid APIs:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -I -S replay_saved.py
```

It rehashes the public manifest, preserves the exact original JSONL byte/order,
replays184 literal request/response pairs (one warmup plus183 scored), runs the
unchanged official adapter response parser and original scorer on all candidate,
native77, and baseline100 answer streams, and reconstructs all184 pure solver
answers from normalized inference inputs. The warmup stays outside the denominator.
The result is104/183, strict183, four gained/zero lost cases against100.

`validation/isolated-native-smoke.json` describes a separate unseen synthetic
HTTP protocol smoke test in a clean isolated copy. It is not a benchmark score.
Its dependency installation and reused model-asset method are explicitly recorded.
The bulk redundant task/decision caches are omitted; exact wire bytes, pinned public
inputs, official scoring helpers, and the projected saved-score reference suffice
for independent replay. Projection provenance is in PROVENANCE.json.

## Source and scope

Every selected measured source file keeps its original relative hierarchy and
byte-identical SHA. Historical harness helper files are retained for provenance;
use the documented serving/replay commands rather than attempting to overwrite
saved benchmark artifacts. `PUBLIC_MANIFEST.json` lists publishable text files.
No model/native binaries, node_modules, provider keys, environment files, or raw
embedding matrices are published.

The two actual development rounds were100->103->104. An unlaunched prescore source
revision was superseded before the second run to harden memo handling; it is not
a third measurement. A saved-data cross-round dictionary-key bookkeeping error
was corrected in a separate evaluation reader without rerunning or changing
inference. The independent final report discloses this chronology and scope.

The selected71 synthetic/protocol tests cover unseen entities/labels/thresholds,
date boundaries, missing/competing edges, unknown operative fields, binding memos,
and exact rational subtraction boundaries. They are software tests, not fresh
benchmark generalization. Submission does not assert an accepted publisher rank.

See THIRD_PARTY_NOTICES.md, data/jevbench/LICENSE, and PROVENANCE.json for source
attribution and license notices. This kit does not relicense upstream data/code.
