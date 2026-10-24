The reader is restricted to a DEV-only diagnostic with empty CONF/TRAIN/CALIB.
This implementation does not establish official confirmation eligibility or a
complete protected104 champion comparator. Retain the admission report's limits
on publisher selection/calibration records, original OANC legal text, later
undocumented reselection, and foundation-text overlap.

Import bart_reader.py or acquire_bart_assets.py without ML imports. Only construct
FrozenBartReader inside the parent-admitted single bounded worker. Its API is
FrozenBartReader(model_directory, asset_lock, max_pair_tokens=512,
attention="sdpa"), score_pair(premise, hypothesis), and score_pairs(pairs).
Raw logits use the key raw_logits_C_N_E. The canonical probabilities_E_C_N
permutation is [2,0,1], full-head temperature1. Native argmax ties use C,N,E
index order; binary Yes requires pE>0.5, otherwise No. Neutral mass is retained.
No generation, prompt rewrite, calibration or weight conversion is used.

Tokenization is the native true pair with only_first truncation requested, but
the reader counts the full pair and rejects lengths above512 before a forward.
The actual token sequence must equal the full pair. The upstream packed-evidence
constructor must therefore fit both strings and all four special tokens within
the512-token limit. No hidden truncation is accepted. The reader checks the fast
BART tokenizer class, vocabulary size, token IDs and native pair formatting.

All original-bin tensor/parameter/head checks occur after safe exact loading in
the worker. Loading uses local_files_only=True, trust_remote_code=False,
use_safetensors=False, weights_only=True, FP32 and fixed stock CPU SDPA; failures
are terminal. Unique parameters must total407344131; classification dense and
output shapes must be1024x1024 and3x1024. All parameters must already be CPU FP32.
No fallback precision, unsafe pickle globals or alternate loader is allowed.

The asset_lock argument accepts either the actual modeldir/asset-lock.json or
the parent's source-pinned public MODEL_ASSETS.json metadata copy. A public copy
must match the direct actual lock's exact bytes and SHA256. All paths must already
be absolute/canonical, with no symlink in any path component. The model directory
must contain exactly the eight required assets plus asset-lock.json, regardless
of the supplied public copy's filename/location. Asset/config/original2020 weight
byte/hash checks remain mandatory after metadata equality is established.

The acquisition plan contains eight files. The BART repository has neither a
special_tokens_map.json nor a LICENSE file; those absences are explicit. Native
special-token configuration is validated inside the worker. The official full
MIT text is copied from the pinned fairseq source and called LICENSE.fairseq.
Pinned config/card/license metadata are copied locally; the original.bin and
four available tokenizer files each have one immutable public GET attempt.
Git blob IDs pin non-LFS files; publisher SHA256 pins the original weight bytes.
Every resulting file gets its actual SHA256 in asset-lock.json. No safe variant,
second weight copy, conversion or tensor parser is used during acquisition.
Only the first16 bytes are read separately as a static original-bin header.

First run `python acquire_bart_assets.py` for a plan with no network. Root must
copy the nine required source files together, create an actual source manifest
from implementation-source-manifest.template.json, and set its source_git_commit
to published durable lease checkpoint4fed2fd4d8d94df71d52ac47c61c6f59ffbd2a67.
Root must author the real permit from
prepare-permit.example.json, replacing every placeholder and setting the actual
permit's preparation_go to true after independent review. The example stays
false. The permit binds source/plan hashes, exact unused destination, base/current
checkpoint, all original-weight pins and physical root lease PID75591 with
start ticks15190845. A reused PID or missing process is fatal. No helper performs
a Git mutation or infers authorization from an example file.

Acquisition command after root's concrete preparation GO:

    python acquire_bart_assets.py --execute --source-manifest /ABS/implementation-source-manifest.json --permit /ABS/root-prepare-permit.json --destination /ABS/unused-model-directory

Root must create the destination's parent first. The helper reserves a persistent
sibling .NAME.acquisition-attempt.json with O_EXCL before opening any URL. An
existing destination or receipt blocks reuse, retry and resume even after a
failure. A failed attempt removes only its own stage. It streams one weight
copy, requires64MiB free disk beyond all planned assets, caps acquisition at300s,
and preserves the receipt. These acquisition limits are distinct from the
worker's CPU2, FP32, one72-pair, at-most600s complete execution admission.

Run `python test_bart_reader.py` for synthetic stdlib numerical and guard tests.
Those tests never call acquire(), construct a tokenizer/model, or open a URL.
The parent worker's network guard separately allows literal::1 bind events only
and treats every other attempted network operation as fatal.
