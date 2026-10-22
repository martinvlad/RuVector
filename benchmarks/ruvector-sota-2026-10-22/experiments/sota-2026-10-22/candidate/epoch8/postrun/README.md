This append-only postrun analysis reads saved TRAIN72 and DEV24 outputs after the epoch8 study is terminal. It performs no model inference, native execution, optimization, candidate selection or frozen-source modification. No confirmation records or labels are opened.

The two raw-logit references were predeclared in `audit/epoch8/offline-reference-analysis-contract-v2.json`, pinned before measurement. They are descriptive, nongating references and cannot rescue a candidate, trigger confirmation or justify promotion. Reported DEV observations span eight document groups, not 24 independent cases; TRAIN results are in-sample.

From the repository root, set `--project-root` to the restored actual execution project and `--source-root` to the canonical repository containing the frozen source/annotation restore. Use new output filenames because both commands refuse to overwrite evidence:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 experiments/sota-2026-10-22/candidate/epoch8/postrun/build_diagnostic_v1.py --project-root /path/to/epoch8/project --source-root /path/to/repository --output /tmp/dev-diagnostic-v1.json
PYTHONDONTWRITEBYTECODE=1 python3 experiments/sota-2026-10-22/candidate/epoch8/postrun/build_findings_v1.py --diagnostic /tmp/dev-diagnostic-v1.json --output /tmp/dev-findings-v1.json
```

The first command validates saved probability support, original threeway/binary label consistency, exact document text and source offsets, and numeric retention against the saved spans. Full DEV annotation analysis is permitted only when all24 actual fitted-head DEV responses exist. A failed fit branch reads no held-out label source. The second command summarizes the first report and contains one explicitly unimplemented future hypothesis. Coverage remains mechanical evidence exposure and does not imply sufficiency.
