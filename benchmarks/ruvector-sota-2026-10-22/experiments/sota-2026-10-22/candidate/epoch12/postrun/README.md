# Epoch12 saved-output findings

This kit analyzes only the30 saved and already consumed phase1 outputs: six TRAIN diagnostics and24 DEV decisions. It imports no model runtime and opens no confirmation file, complete corpus, new input, model session or optimizer. The candidate source manifest `e026244f921171860a8cb9a9b9ce0c03de61bd2330d6521653b16db9455b9aaf` remains unchanged.

The six TRAIN pairs share exact native packed contexts and identical token IDs/masks/types. FP32 and INT8 agree on four binary decisions and five typed decisions. Posterior total variation reaches0.67806643; centered-logit difference reaches2.27456371. FP32 scores3/6 versus INT8 1/6 descriptively on this already exposed bank, with lower Brier/NLL. These measurements establish differences between co-located published variants; they do not verify original upstream weights or isolate a pure quantization causal effect. The fixed FP32 primary was chosen before these outputs and was never selected from them.

On the new DEV bank, native/lexical/positional/excerpt104 correct counts are13/10/12/8. The native FP32 reader answers Yes16 times and No8 times; its typed predictions are17 Entailment,1 Contradiction and6 NotMentioned. It correctly identifies zero of the three true contradictions and three of eight NotMentioned cases. Nine of its11 binary errors have confidence at least0.8. Its NLL1.55319931 exceeds positional's1.50585951, and it improves only one answer against positional where the frozen gate requires two. Excerpt104 has lower proper losses. The candidate remains rejected.

Native retains170/690 numeric source mentions per query, compared with150 for lexical and188 for positional. Mean source-character coverage is0.271995 for native,0.265183 for lexical and0.258663 for positional. These are repeated source-position exposure counts, not unique-document totals, numeric truth, gold-annotation retention or evidence sufficiency. No new annotation projection was read.

Epoch11 and epoch12 DEV documents differ. The13/24 versus12/24 historical scores do not establish a causal accuracy gain. FP32's new DEV output diversity cannot be compared with an unexecuted INT8 run on the same new DEV. Only the six TRAIN comparisons hold input and context identical while comparing the measured published variants.

Reproduce both exact JSON artifacts with Python stdlib only, choosing two genuinely unused output paths:

```bash
python -B experiments/sota-2026-10-22/candidate/epoch12/postrun/build_diagnostic_v1.py --records experiments/sota-2026-10-22/epoch12/runs/development/records.jsonl --out /tmp/UNUSED-epoch12-diagnostic.json --findings-out /tmp/UNUSED-epoch12-findings.json
```

The builder refuses overwrites. Six synthetic boundary tests check feed matching, precision roles, common-logit offsets, decision ties, proper scores and role completeness. No benchmark-generalization claim follows from those tests. Confirmation remains unused and the submitted champion unchanged; official SOTA requires a matching publisher result and eligibility.
