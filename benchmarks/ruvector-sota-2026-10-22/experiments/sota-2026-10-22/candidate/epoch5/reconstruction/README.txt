Offline native runtime reconstruction (postfreeze provenance tooling)

This helper materializes the eight core package files and fourteen TypeSafe
execution files into the canonical paths of a reconstructed project. It does
not change the frozen candidate or experimental plan and never starts inference.

First use the existing reviewed bootstrap.py and restore_checkpoint.py for text
sources, restore_epoch3_data.py for original source data, and model asset helpers
for BGE and candidate4's pinned DeBERTa-base assets. Those tools have their own
explicit acquisition options; this helper adds no acquisition or installation.

Provide local cache trees containing these exact canonical paths:
  CORE_CACHE/retrieval/node_modules/@ruvector/core/...
  CORE_CACHE/retrieval/node_modules/ruvector-core-linux-x64-gnu/...
  TYPESAFE_CACHE/node_modules/@ruvector/typesafe/...

The reviewed epoch4/runtime-repair/restore_native_closure.py can construct a new
core cache tree from its two already cached official npm archives. The reviewed
bootstrap's explicitly selected npm dependency setup can supply the TypeSafe
cache. Alternatively, reuse an existing local tree with the pinned file bytes.
This helper neither invokes those operations nor downloads missing binaries.
The cache roots may be the same directory. Every ancestor and file must be a
regular directory/file, not a symlink. Hashes alone cannot supply absent bytes.

After the fresh project directory exists, run:

  PYTHONDONTWRITEBYTECODE=1 python3 \
    experiments/sota-2026-10-22/candidate/epoch5/reconstruction/restore_runtime.py \
    --project-root /absolute/fresh-project \
    --core-cache-root /absolute/CORE_CACHE \
    --typesafe-cache-root /absolute/TYPESAFE_CACHE \
    --receipt /absolute/new-runtime-restoration.json

Cache roots are explicit; no global npm lookup or package resolution occurs.
Both complete source closures and all existing target files are validated before
any write. Missing targets are created exclusively, matching targets are reused,
and mismatches or symlink ancestors fail without replacing existing files.
Directories are traversed with O_NOFOLLOW handles. New runtime files are copied
as regular files, never linked to external caches. Re-running reuses exact files.

Verify an already restored project without caches:

  PYTHONDONTWRITEBYTECODE=1 python3 \
    experiments/sota-2026-10-22/candidate/epoch5/reconstruction/restore_runtime.py \
    --project-root /absolute/fresh-project --verify-only \
    --receipt /absolute/new-runtime-verification.json

Receipt files must be new. The helper pins the bundled official core closure,
TypeSafe closure and submitted runtime manifest by SHA256. The TypeSafe native
binary identity must agree across both manifests. Absolute resolution paths in
the historical TypeSafe manifest are observations only; targets use its frozen
relative file paths under the explicitly supplied project root.

The helper imports no addon, package or model runtime and executes no subprocess,
provider call, benchmark, install, network access or forward. Exact file identity
and isolated placement do not establish ABI loading, ONNX provider support,
inference correctness, benchmark performance or rank. A later separately
authorized experiment must use its own plan and resource budget.

Nine pure helper tests use tiny synthetic files, not real model/addon execution:

  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s experiments/sota-2026-10-22/candidate/epoch5/reconstruction \
    -p test_restore_runtime.py -v
