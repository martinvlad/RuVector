RuVector submission-development candidate

Selected candidate: ruvector-native-submission-round2-v2
Observed public development: 104/183 (56.8306%), original56/72, hard48/111,
strict-valid183, zeroerrors. The separately frozen two measured rounds were
100 ->103 ->104, with4gains and zero regressions versus the exact100 pipeline.
Full independent proofs live in ../audit/round1-independent-verification.json
and ../audit/round2-independent-verification.json. These are the same183 exposed
public development cases; they do not establish publisher Capability, matching
current300public/1200sealed coverage, an official score, or leaderboard placement.

What changed

Actual @ruvector/typesafe0.2.0 native BGE-small inference executes on every
request. The original native77 and exact100 answer streams are preserved in
all recorded responses. The four new exact supplied-record proof grammars are:
- course and track aliases -> prerequisite equivalence -> section/grade footnote;
- asset owner -> effective-dated team alias -> conditional severity -> routing;
- machine/fault joins -> approved safe bypass -> exact rational strict threshold;
- dataset tier / requester class / purpose -> current field classification and
  conditional retention maximum.
Unknown, conflicting or missing operative facts abstain to the exact100 pipeline.
Facts retain exact JSON pointers and source spans; steps retain trace operands.
No evaluation IDs, expected labels, family/cohort metadata, answer lookup table,
model training, new model download or external inference API enters prediction.
Gains belong to the integrated native-plus-validator pipeline. The native binary,
embedding model and tokenizer did not change; no index-only causal gain is claimed.

Selected-source validation

71 synthetic/protocol tests passed before the final source freeze, including
unseen entities/labels/thresholds, changed dates, absent/competing edges, archived
noise, nested operative-condition abstention, binding memo abstention, and exact
2.3-0.3==2 and 2-1e-100<2 strict-boundary counterfactuals. These are software tests,
not additional benchmark scores or untouched generalization evidence.

serve.py is a separate deployment entrypoint using the exact measured engine.
Validate the selected source and all3 model assets, without native/model calls:

PYTHONDONTWRITEBYTECODE=1 python3 experiments/submission-2026-10-22/jevbench/serve.py --policy-directory experiments/submission-2026-10-22/jevbench/round2-v2 --runtime-manifest experiments/submission-2026-10-22/jevbench/runtime-manifest.json --validate-only

Serve the pinned candidate (this actually starts a persistent native process):

PYTHONDONTWRITEBYTECODE=1 python3 experiments/submission-2026-10-22/jevbench/serve.py --policy-directory experiments/submission-2026-10-22/jevbench/round2-v2 --runtime-manifest experiments/submission-2026-10-22/jevbench/runtime-manifest.json --host 127.0.0.1 --port 8787

The request route is POST /v1/systemone, with the original official request
normalization/validation. SIGINT/SIGTERM closes the server and native child.
No service is left running by this worker. Root controls any external hosting.

Reproduction requires Python3.12 stdlib, Node, pinned @ruvector/typesafe0.2.0,
the inherited source paths in the selected37-file plan, and models/ assets listed
by exact SHA in runtime-manifest.json. Models are not newly downloaded by any
command here; the source manifest points to the original public BGE model source.
The candidate config and source hashes are fixed; preserve criterion insertion
order and the pinned original task JSONL bytes when replaying historical scores.

Preserved failures and source revisions

Original round2/ is a FROZEN BUT NEVER LAUNCHED prescore source revision. The
independent reviewer required a stricter optional-memo guard before launch, so
all its original files remained byte-for-byte at the same paths. Its cancellation
receipt proves zero launch/model/native/HTTP calls. The replacement round2-v2/
uses separately named run/freeze/guardian/verification/emitter helpers and was
source-pinned before the second actual measurement. It is not a third run.

The frozen final evaluation-only verification helper completed all184HTTP /
552original-score checks, then failed writing a cross-round comparison because
it used the unversioned dictionary key. Its source and failure receipt remain;
verify_round2_v3.py fixes only that saved-data bookkeeping key. No source,
model, result or HTTP execution changed or retried. Independent auditing used its
own saved-data verifier and separately reconstructed all four exact operations.

Both CPU2 runs completed under71seconds (cap600each); all four owned worker/native
PIDs are absent. No paid/API/download calls occurred in these two development
measurements. Local latency is observational and is not an official latency rank.
All prior compounding/swarm source and both old evidence ZIPs remain unchanged.
