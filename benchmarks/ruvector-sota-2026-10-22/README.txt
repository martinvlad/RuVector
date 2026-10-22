RuVector measured research continuation source kit

This kit preserves the original relative project hierarchy required by the real
native RuVector baseline and optional learned head. It contains public benchmark
inputs and local native response evidence. It contains no provider credentials,
private hosted-provider data, node_modules, native binaries or model weights.

Python 3.12 and Linux x86-64 glibc with Node >=18 are the measured platform.
The initial environment used Node24.19.0, numpy2.3.5 and scipy1.17.0.

Reconstruct text sources into a NEW directory:
  python3 bootstrap.py --dest /absolute/path/projected-ruvector

bootstrap.py verifies the exact old PUBLIC_MANIFEST SHA256 and downloads only
the named source files from immutable RuVector commit11983d212b951305bcab06ad868bca5a12ea2954.
Matching existing files are reused. Mismatched files and symlinks fail closed.
Default setup runs no inference and downloads no weights or native packages.

For offline source validation, point --base-local-directory to a verified local
copy of the old public kit. Verify a materialized project with --verify-only.

Optional dependency and asset setup, after reviewing these operations:
  python3 bootstrap.py --dest /absolute/path/projected-ruvector --install-npm --install-python --acquire-models

npm ci uses the pinned lockfile with lifecycle scripts disabled. acquire_models.py
uses pinned public Hugging Face revision URLs and exact SHA256/lengths. Existing
model assets can instead be placed at the assets.lock.json paths and checked with
--verify-models. Neither setup nor verification executes a benchmark.

Source-only validation in a DISPOSABLE COPY of the reconstructed project:
  python3 experiments/sota-2026-10-22/benchmark/validate.py
  python3 -m unittest discover -s experiments/sota-2026-10-22/candidate -p test_head.py
  python3 -m unittest discover -s experiments/sota-2026-10-22/controller -p test_loop.py

validate.py emits a new validation.json receipt. Running it in the historical
projection changes an archived receipt pin; use a disposable validation copy.

The historical initial epoch cannot be blindly re-run: its plan and one-shot
markers preserve measured attempt identity, and easy48 has been consumed as
confirmation. Use CONTINUATION.template.json to prepare a separate future epoch
with a new hypothesis and genuinely unused confirmation data. The old183 items
remain exposed adaptive development. A local diagnostic is not official SOTA.

The latest official target must be refreshed from the actual live board and
methodology; prior official JevBench submission reference is7FEA2738. The author
LegalBench-RAG email was already sent; this kit does not authorize duplicate mail.

LICENSE applies to new continuation code. Existing copied upstream code/data
retain their own license/provenance as listed in PROVENANCE.json and the exact
base THIRD_PARTY_NOTICES.md. Do not interpret generated task metadata as a new
license for upstream material.
