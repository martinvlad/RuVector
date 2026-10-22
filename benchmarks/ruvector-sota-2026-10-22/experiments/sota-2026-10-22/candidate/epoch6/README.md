Epoch6 changes context handling while retaining the pinned DeBERTa-base model, singleton decoder, temperature1, binary mapping and real native RuVector search. There is one fixed configuration, no training, calibration fit or grid. The prior use of these weights is exposed development history, not a fresh model result.

The source string is partitioned completely and without overlap. Blank lines define paragraphs; sentence or semicolon boundaries define legal atoms. Adjacent complete atoms are grouped toward128 NLI tokens, with a hard160-token unit limit and256-token BGE limit. An oversized atom is explicitly split at observed NLI token offsets. Every fallback boundary, exact source offset and unit token count is recorded. More than192 units causes rejection before any forward; no source tail is dropped.

Each retrieval arm supplies at most40 ranked anchor candidates. Native ranking is the actual returned order from the unchanged native worker; lexical Jaccard and positional rankings have the same min(40, unit_count) depth. The packer scans anchors in rank order. If an entire anchor fits the exact512-token premise-plus-whole-hypothesis budget, it is admitted; the previous and next same-paragraph units are then tried, in that order. Neighbor expansion may inspect units outside the40-anchor ranking, identically in all arms. Later ranked anchors can use remaining space. Selected source spans are merged and concatenated in source order. There is no hidden clipping or per-chunk maximum over NLI outputs.

The four response names remain compatible with the controller: primary `ruvector_top2`, `same_nli_lexical_top2`, `same_nli_positional_first2` and `baseline104_response`. The top2/first2 names are legacy aliases for variable-unit packing. The native104 reference receives the exact primary packed excerpt and original question, with an explicit excerpt-control label, input bytes/hash and unit IDs. It is not the original full-input104 configuration.

`CandidateEngine` inherits the unchanged frozen epoch4 model initialization, BGE/native execution counters, CPU/RSS observations, native vector-bundle preservation and cleanup. New counters track partition and pack attempts/completions. Every successful arm retains its exact premise, whole hypothesis, token IDs, raw logits and source coverage. Numeric-retention and omission fields are mechanical observations; they do not establish entailment, insufficient evidence or correctness.

The runtime accepts only `predict(state, questions)`. It does not inspect evaluation IDs, labels, split names, task tables or gold spans. The candidate implementation has not read new development or confirmation inputs/labels and has run no model or native forwards. Independent review must perform tokenizer-only domain checks before the separately controlled corpus batch. Per-admission and final raw pair checks enforce the budget for the actual ranking path; this is not an exhaustive enumeration of all possible subsets.

Source-only tests use synthetic tokenizers and injected readers:

```bash
PYTHONDONTWRITEBYTECODE=1 retrieval/.venv/bin/python -m unittest discover \
  -s experiments/sota-2026-10-22/candidate/epoch6 -p 'test_*.py' -v
```

Frozen earlier files and weights remain unchanged. Reconstruction uses the reviewed checkpoint/model helpers plus candidate/epoch5/reconstruction/restore_runtime.py for the exact core8 and TypeSafe14 execution closure. A reconstructed runtime does not start or authorize an experiment.
