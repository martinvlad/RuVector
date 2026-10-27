E50 standard SOURCE/FINAL publication transport, following actual archive recovery.

Actual recovery parent for this study:
f65c8a3e2ad835577e912d60c817e86ba73e29cb
root3fd4e9f047783a8c96afc33e340e5e1d7bc64032
bencha0ecee57f32cc1ee2f2fd93e35d07035d21fbf4e
scope4b9920d36f051b423c352a0ca991e96c1637b61d
Git8148 / CP8141. These are actual independently read-back facts, not a predicted
future SOURCE commit. E50 plan.source_checkpoint and SF.source_checkpoint must
equal this recovery commit. Both actual scientific source and source admission
remain unexecuted until their separate frozen-source/readback/data gates pass.

Kind: REAL_CONTRACTNLI_ROBERTA_FAITHFUL_MMAP_TRANSFER_PILOT.
W50=/dev/shm/ruvector-sota-2026-10-22/epoch50-ad86e60e2402
R=W50/project. Operational standard helpers are W50/publication-helpers,
stages W50/stage-source and W50/stage-final, journal W50/publication.
These are separate from recovery-transport and the closed E49 journal.
Guardian15 remains epoch50/gen15, PID158817/start38479788, owner711 bytes,
SHA2854df82624e7c7c236b45b799c383a3555673a6268d7500858f1b9bc18410bc,
original FD3 dev33/inode13626, CPU0,1. Owner is freshly checked for each mutation.

Allowed NEW source/result paths only:
experiments/sota-2026-10-22/epoch50/
experiments/sota-2026-10-22/audit/epoch50/
experiments/sota-2026-10-22/runtime/epoch50/
Existing changes only CONTINUATION.json,CHECKPOINT_MANIFEST.json,ACTIVE_RUN.json.
Recovery20 published transport rows, all prior ACK/UNKNOWN facts, CP-only70,
E44 separate overlay55 and E49 separate overlay76 remain unchanged.
E49 overlay76 files are not direct Git members or CP project_files rows; source
provenance should use the published recovery manifest/envelope. New E50 code is
reviewed under the E50 roots. All three UNKNOWN Git objects remain permanently
denied for queries, payload recreation, and live references:
486888de9602bbb5d817a55f707b4fcfd11c65e0
3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5
a68b7ba587332f176f65d0348de3e910aa16e77a

All references are exact {path,bytes,sha256}; public refs resolve against R, local
refs are absolute. Required phase-input fields:
schema_version1,epoch50,kind,phase source|final,source_checkpoint actual recovery
commit above,parent actual phase parent,owner exact local3ref,
plan canonical P50/plan.json3ref,source_freeze canonical P50/SOURCE_FREEZE.json3ref,
transport_sources:{guard,stagebuilder,controller} canonical exact3refs,
source_map actual complete Git-map local3ref,root_baseline and bench_baseline
local3refs (raw MCP envelope or decoded API tree),current_CP/current_CONT exact
actual Git bytes local3refs,artifacts:[{path,local_path:absolute R/path,bytes,sha256}],
ACTIVE,CONT_patch,CP_phase_record,commit_message.

Root copies the three reviewed rendered files from W50/standard-transport-sources
to the operational mirror and its reviewed canonical source mapping, ordinarily
P50/publication/{guard.py,stagebuilder.py,controller.js}. Root supplies exact
canonical mapping in transport_sources; no recovery controller is substituted.

Plan minimum fields: epoch50,kind,source_checkpoint above,
source_freeze_path canonical relative P50/SOURCE_FREEZE.json (not absolute),
minimum_pre_mutation_delay_ms:2000. SF epoch50/source_checkpoint above and files
cover every current SOURCE artifact, including exact plan, except SF itself.
Inherited frozen files require actual baseline CP/Git provenance. Later integrated
reviews that reference the SF hash stay operational outside R until FINAL, avoiding
a circular SF hash. No source may change after frozen publication/admission.

ACTIVE: epoch50,phase,kind,source_checkpoint above,owner_sha256 exact,
work_active true for SOURCE / false for FINAL,experiments_active false,
OS_lock_observation_scope PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE,
publication_is_not_scientific_authorization true.

SOURCE CONT patch only epoch50_source,epoch50_frozen_study,epoch50_data_roles.
FINAL only epoch50_final,rejection_ledger,latest_learning,next_research_priority,
cumulative_budget_ledger,benchmark_refresh,publisher_status,exposed_development_sets.
Untouched old fields remain type-exact; champion/goal/rank/unused confirmation
remain unchanged. Existing budget facts remain exact; only epoch50_actual_execution
is appended. Existing DEV history remains a prefix/unchanged records. CP appends
only new current public rows and epoch50_source|epoch50_final. CONT's CP hash is
derived from the newly encoded CP. Case identities and scientific semantics are
separately reviewed; opaque patch fields do not bypass acceptance gates.

FINAL additionally requires actual_SOURCE_receipt local3ref and independent_SOURCE_readback
local3ref with checks_passed/verified_actual_remote_readback true,commit,tree_sha,
source_plan_sha256,source_freeze_sha256. It requires canonical P50/EPOCH_MANIFEST.json
with epoch50,source_checkpoint above,no_project_additions_after_manifest true,
files all current canonical3refs except itself. Current source files remain
byte-identical; FINAL new artifact list exactly equals current files minus SOURCE.

Preparation approval: checks_passed true,phase_preparation_allowed true,
phase_input_sha256 exact. Root alone invokes the pinned helper once per phase:
python -I -B W50/publication-helpers/stagebuilder.py --input INPUT --input-sha SHA
 --approval PREP --approval-sha SHA --out W50/stage-source|W50/stage-final

Full-stage approval: checks_passed,publication_phase_allowed,
source_and_denylist_review_passed,dual_unknown_denylist_reviewed true (legacy field
name; forbidden_Git_objects must contain all THREE sorted SHAs),epoch50,phase,
stage_metadata_sha256,expected_final_root_sha,source_parent,owner_sha256,
source_freeze_sha256,original_blob5_execution UNKNOWN_PERMANENTLY.

Root pins exact controller bytes to frozen canonical source, loads definitions:
const c=new Function('tools',source+'\nreturn {publishE50Phase,persistE50Receipt};')(tools);
const actual=await c.publishE50Phase('source'|'final',approvalPath,approvalSHA);
const receipt=await c.persistE50Receipt(actual);
Fresh controller instance per phase. Receipt persistence is explicit and factual,
not future scientific authority. No automatic invocation, retry, reconciliation,
old journal import, publisher submission, merge, release, or main update exists.

Each mutation waits2000ms BEFORE reserve/intent, then freshly fences ownership.
Calls remain sequential. Request reservation is O_EXCL; intent is fsynced before
one tool call. Whole raw MCP return is O_EXCL/fsync persisted before post-call
owner checks/parsing/ACK validation. Thrown or uncertain calls STOP without retry.
Ref bare success records ack_sha:null and requires fresh exact post-CAS GET.
Sparse full-root trees use chunks<=32, expected Git Merkle identities, unrelated
sibling preservation and complete actual scope readback with unique leaf paths
and exact scope SHA before sole-parent commit/nonforce exact-parent CAS. Main
c44d7337c0c5ad2ecd2294178475387facb96516 stays read-only.
