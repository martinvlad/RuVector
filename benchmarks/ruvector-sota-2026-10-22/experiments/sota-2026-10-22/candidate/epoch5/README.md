This directory adds a read-only preflight for the unchanged epoch4 candidate. It performs no model initialization, forward, native-addon load, corpus read, or prediction.

Run against the actual isolated project, with the official closure specification and its own inference Python:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/sota-2026-10-22/candidate/epoch5/preflight.py \
  --project-root /absolute/isolated/project \
  --closure-spec /absolute/official-package-closure.json \
  --inference-python /absolute/isolated/project/retrieval/.venv/bin/python \
  --output /absolute/new-preflight-receipt.json
```

The output path must be new. The official package specification, candidate manifest and asset lock are pinned in the script. The gate checks all eight regular native package files, all sixteen assets, frozen candidate sources, exact Python distribution versions, both isolated Node entrypoints, static NLI ONNX input/output metadata and native ELF metadata. Node runs with `--no-addons --no-global-search-paths`; only built-in packages execute. Python reads package distribution metadata without importing model libraries.

`actual-preflight.json` records the successful check of the epoch5 execution project. It establishes file identity and isolated resolution. It does not establish successful addon ABI loading, ONNX Runtime session/provider compatibility, inference correctness, benchmark performance or a score.

The source review found no additional blocking feed/shape/policy issue. The frozen NLI decoder uses int64 rank-two inputs, a singleton unpadded joint context, the config's three-class mapping and the graph's single three-class logits output. The graph contains its own weights. Actual initialization and execution remain the sole corpus batch's responsibility.

The frozen runtime puts `execution_after` counters in each successful wire response. It adds `execution_terminal` and request wall time to `last_usage` in `finally`; those latter fields belong to the server audit. This observation changes no runtime code or accounting claims.

Eight source-only tests exercise path escapes, file tampering, symlink ancestors, pinned-spec tampering, malformed protobuf messages, feed/shape validation, external-weight rejection, and Node resolution without executing intentionally throwing package entrypoints or an invalid addon:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s experiments/sota-2026-10-22/candidate/epoch5 -p test_preflight.py -v
```
