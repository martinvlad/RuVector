# @ruvector/kge — benchmarks and release gates

The measurement harness (ADR-003 / ADR-006): it trains the binding, evaluates
filtered ranking metrics, and gates a release on numbers, not on "tests pass".
See the package [README](../README.md) for the API and the FFT spike.

## Honest numbers, by construction

- **Filtered MRR / Hits@{1,3,10} with RANDOM tie-breaking** (ADR-003 §5; Sun et
  al. 2020, arXiv:1911.03903). Many older papers used TOP tie-breaking, which
  inflates scores — worst on WN18RR's symmetric relations. This harness asserts
  RANDOM in CI: an all-tied scorer must yield mean rank ≈ (|E|+1)/2, not 1.
  Because of this our numbers are directly comparable to LibKGE/PyKEEN and
  *lower* than TOP-inflated papers. That is correct.
- **Baselines are reproduced, then a margin is subtracted** — never invented.
  FB15k-237 and WN18RR gate on the LibKGE ComplEx MRR (0.348 / 0.475) minus 3
  points. CoDEx-M's baseline is read from arXiv:2009.07810 at build; its gate
  SKIPs until a maintainer records it with a source. The predict-latency gate is
  wired to `fft-spike-2026-09-21.json` (ADR-002): its native p95 threshold is
  live; the wasm threshold stays pending (wasm32 is compile-only in the spike).
- **HolE gate number = ComplEx's**, valid only because HolE ≡ ComplEx is proved
  by the crate unit test (ADR-002). That equivalence is a precondition, surfaced
  here as an external gate row.

## Running

```bash
node run.mjs --suite synthetic --tie-check --ann --adversarial --gate --report-only
node run.mjs --suite fb15k237 --scorer hole --dims 256 --epochs 100 --gate
node run.mjs --suite wn18rr --limit 5000 --ann --gate --report-only
```

Flags: `--suite synthetic|fb15k237|wn18rr|codexm|yago310|all`, `--scorer
hole|rotate`, `--dims`, `--epochs`, `--limit N`, `--ann`, `--adversarial`,
`--tie-check`, `--gate`, `--report-only`, `--baseline-receipt PATH`, `--out`.

The harness never crashes on an unavailable engine: each measured arm reports
"engine unavailable" and, under `--report-only`, the run still exits 0. Every
call into the Model binding goes through `lib/arms.mjs`. For a real synthetic
run before `train`/`eval` land in the core, point the harness at the fake:

```bash
KGE_BENCH_BINDING=./test/fixtures/fake-binding.cjs \
  node run.mjs --suite synthetic --tie-check --ann --adversarial --gate --report-only
```

## Datasets (fetched at bench time, nothing redistributed)

| Suite | Source | Licence stance | `--limit` |
|---|---|---|---|
| `synthetic` | frozen `fixtures/synthetic-kg.json` (committed) | n/a | n/a |
| `fb15k237` | villmow/datasets_knowledge_embedding (standard splits) | Freebase-derived; follows source | subgraph |
| `wn18rr` | same mirror (`WN18RR/text`) | WordNet-derived; follows source | subgraph |
| `codexm` | tsafavi/codex `data/triples/codex-m` + hard negatives | code MIT (root LICENSE, hashed); triples CC BY 4.0 per the paper | subgraph |
| `yago310` | same mirror (lazy: only with `--suite yago310`) | YAGO-derived; follows source | subgraph |

`--limit N` keeps the top-N entities by train degree (tie-broken by id) and every
triple across all splits whose head and tail both survive — a connected subgraph,
so filtered ranking stays meaningful (a random-triple slice would orphan the
filter sets). Fetched files are sha256-pinned after the first download; the
fetcher prints the hash to record.

## Gates (ADR-006 §Release gates)

`gates.json` — each threshold carries a `source`. Numeric gates apply only on
their suite / when their flag is present; otherwise SKIP (never a silent pass).
The synthetic suite exercises the tie-break, ANN-recall, adversarial and (native)
latency gates so CI measures something on every PR.

## Receipt

One `ruvector-kge-bench/receipt@1` per run: scorer, config, dataset/split
hashes, metrics per split, tie-break mode, ANN recall, the adversarial report,
predict latency, train throughput, host, and the binding's `statsJson`. It
records **no entity or relation ids** and **no triple text** (ADR-005) — hashes
and counts only.

## Experimental cross-graph ULTRA adapter

`transfer/ultra_adapter.py` accepts RuVector `{s,r,o,split}` JSON exports and
provides exhaustive `predict({s,r,k})` / `predict({o,r,k})` style results through
an optional Python sidecar. It uses the original MIT ULTRA implementation and
the hash-pinned `ultra_3g.pth` checkpoint. It does not add a native Rust scorer,
change existing KGE behavior, or install anything automatically.

The first CPU pilot uses Nations, Kinships and UMLS from a recorded PyKEEN
revision. None is among the checkpoint's upstream-declared pretraining graphs
(FB15k237, WN18RR, CoDExMedium). This is evidence against that declared graph
list, not an independent audit of the original training process. Unlike the
legacy `carveTransfer` split, these are different whole graphs. Target support
edges are still available at inference: zero-shot means zero target updates,
not reasoning without observations.

The first 64 original test triples by SHA256 of JSON `[s,r,o]` are selected
without model scores. Other test facts stay filter-only. No valid or test
edges enter entity or relation message passing. All entities are candidates;
head and tail ranks use pessimistic ties. Random weights use seeds 101/202/303.
The native KGE control trains HolE for 50 epochs on target support only with
the same candidate universe, filters and queries. This is not an equal-total-
compute comparison: ULTRA brings prior external training. Source replay is
not measured here; earlier same-graph replay results cannot be substituted.

Reproduce from the repository root in an isolated Python environment with a
C++ compiler, using `transfer/requirements-cpu.txt` for the measured runtime:

```bash
python -m venv /tmp/ultra-env
source /tmp/ultra-env/bin/activate
pip install -r npm/packages/kge/bench/transfer/requirements-cpu.txt
git clone https://github.com/DeepGraphLearning/ULTRA.git /tmp/ultra
git -C /tmp/ultra checkout 427966ad8ed60420eef034063d44f3153addff90
git clone https://github.com/pykeen/pykeen.git /tmp/pykeen
git -C /tmp/pykeen checkout cbc1ea107afd7bebc531c1739c210c620f908fbf
python npm/packages/kge/bench/transfer/prepare_pykeen.py \
  --checkout /tmp/pykeen --dataset nations --output /tmp/nations.json
python npm/packages/kge/bench/transfer/ultra_adapter.py \
  --input /tmp/nations.json --upstream /tmp/ultra --output /tmp/ultra-result.json
node npm/packages/kge/bench/transfer/kge_control.mjs /tmp/nations.json \
  /absolute/path/to/installed/@ruvector/kge/index.js /tmp/kge-result.json
ULTRA_CHECKOUT=/tmp/ultra python -m unittest discover \
  -s npm/packages/kge/bench/transfer -p 'test_*.py'
```

Activate the environment so `ninja` is on PATH. The upstream CPU rspmm kernel
compiles on first inference. Setup/compilation time is excluded from recorded
evaluation time. Test without `ULTRA_CHECKOUT` runs seven standard-library
contracts and explicitly skips the three optional integration tests.

Pass `--query '{"s":"entity","r":"relation","k":5}'` to produce a ranked
prediction instead of a benchmark. Relation names must occur in target support;
they need not occur in checkpoint pretraining. Raw ULTRA and KGE scores are not
calibrated for combination. The adapter is sequential and experimental, not an
unrestricted inference service. All local model code, compiler and installed
dependencies must be trusted. Checkpoint bytes are SHA256-verified and loaded
with `weights_only=True`; no secrets or provider API are required.

Receipts in `transfer/pilot-results.json` preserve input/file/source hashes,
dependency versions, query hashes, paired head/tail ranks and controls. Positive
pretrained-versus-random results establish only a bounded exploratory transfer
signal. Promotion remains false. Acceptance for deployment requires separate
untouched graphs, target scratch and replay controls where meaningful,
equal target adaptation budgets, uncertainty estimates and a latency budget.

Measured pilot (2026-10-13), filtered MRR; controls averaged over three seeds:

| Graph | ULTRA zero-shot | Random ULTRA | Target-trained KGE |
|---|---:|---:|---:|
| Nations | 0.5753 | 0.2701 | 0.7396 |
| Kinships | 0.1858 | 0.0582 | 0.8128 |
| UMLS | 0.6767 | 0.0415 | 0.9276 |

ULTRA beats random weights on all three selected query sets and loses to
target-trained KGE on all three. Keep KGE as the incumbent; treat the structural
adapter as an experimental cold-start option. ULTRA evaluated 128 rankings per
graph in 1.92–2.28 seconds on this CPU environment, excluding initialization and
kernel compilation. KGE's 50 target epochs took 0.21–2.44 seconds per seed.
These are descriptive run timings, not a controlled latency benchmark.
