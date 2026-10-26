E48 focused publication transport, public metadata only.

The three executable source files are guard.py, stagebuilder.py and controller.js.
Root copies reviewed bytes to W/publication-helpers, with guard.py and
stagebuilder.py together. Root alone invokes actual modes. Source and Final each
require separate independently approved input and resulting full desired tree.
No publication approval/receipt grants DATA or scientific execution authority.

W = /dev/shm/ruvector-sota-2026-10-22/epoch48-37b29244dcf5
R = W/project. Canonical references are {path,bytes,sha256}; public references
resolve against R, local references use absolute paths. Counts are derived.

Required phase-input fields:
schema_version:1, epoch:48, kind:REAL_CONTRACTNLI_ROBERTA_NLI_TRANSFER_PILOT,
phase:source|final, source_checkpoint:37b29244dcf51eec23510c111e0ea27c11cc646d,
parent:actual phase parent, owner:exact Guardian13 local3ref,
plan:canonical3ref(P48/plan.json), source_freeze:canonical3ref(P48/SOURCE_FREEZE.json),
transport_sources:{guard:canonical3ref,stagebuilder:canonical3ref,controller:canonical3ref},
source_map:local3ref(actual complete Git map),
root_baseline:local3ref(actual root tree API object OR full MCP capture),
bench_baseline:local3ref(actual bench tree API object OR full MCP capture),
current_CP:local3ref(actual current Git CP bytes),
current_CONT:local3ref(actual current Git CONT bytes),
artifacts:[{path:canonical current path,local_path:absolute R/path,bytes,sha256}],
ACTIVE:reviewed snapshot described below, CONT_patch:reviewed narrow patch,
CP_phase_record:reviewed new opaque current phase record, commit_message:string.

Plan minimum fields: epoch, kind, source_checkpoint, source_freeze_path. The SF
minimum is epoch, source_checkpoint, files:[canonical3ref]. SF includes every
current SOURCE artifact, including exact plan, except SF itself. Inherited
frozen references require exact baseline CP/Git provenance. All three publication
sources must be frozen. No SF hash is required inside plan, avoiding a cycle.

ACTIVE minimum fields: epoch:48,phase,kind,source_checkpoint,owner_sha256,
work_active:true for SOURCE / false for FINAL,experiments_active:false,
OS_lock_observation_scope:PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE,
publication_is_not_scientific_authorization:true. This is a snapshot, not a claim
that the publisher's later reader owns a current lock.

SOURCE CONT patch permits only epoch48_source,epoch48_frozen_study,epoch48_data_roles.
FINAL permits epoch48_final,rejection_ledger,latest_learning,next_research_priority,
cumulative_budget_ledger,benchmark_refresh,publisher_status,exposed_development_sets.
All untouched old fields remain type-exact; champion/goal/rank/unused confirmation
remain unchanged. Budget permits only a new epoch48_actual_execution row and keeps
every old fact. DEV history preserves the old prefix/records. CP appends only new
public rows and one epoch48_source|epoch48_final record. CONT's CP hash is derived
from the newly encoded CP. CP-only70 and E44 overlay55 remain distinct.

FINAL additionally requires actual_SOURCE_receipt:local3ref and
independent_SOURCE_readback:local3ref, with independent fields checks_passed:true,
verified_actual_remote_readback:true,commit,tree_sha,source_plan_sha256,
source_freeze_sha256. It requires epoch_manifest:canonical3ref(P48/EPOCH_MANIFEST.json)
whose fields are epoch:48,source_checkpoint,no_project_additions_after_manifest:true,
files:[all current canonical3refs except itself]. The current source files remain
byte-identical. New FINAL files must exactly equal current inventory minus SOURCE.

Preparation approval fields: checks_passed:true,phase_preparation_allowed:true,
phase_input_sha256:exact SHA. Root executes ONCE, with independently pinned helper:
python -I -B W/publication-helpers/stagebuilder.py --input INPUT --input-sha SHA
 --approval PREP --approval-sha SHA --out W/stage-source|W/stage-final
The builder only writes the fresh operational stage; it does not call Git.

Full stage approval minimum fields: checks_passed:true,publication_phase_allowed:true,
source_and_denylist_review_passed:true,dual_unknown_denylist_reviewed:true,
epoch:48,phase,stage_metadata_sha256,expected_final_root_sha,source_parent,
owner_sha256,source_freeze_sha256,forbidden_Git_objects:[sorted exact dual retired IDs],
original_blob5_execution:UNKNOWN_PERMANENTLY.

Root pins controller source bytes against frozen source before loading definitions:
const c = new Function('tools', source + '\nreturn {publishE48Phase,persistE48Receipt};')(tools);
const actual = await c.publishE48Phase('source'|'final', approvalAbsolutePath, approvalSHA);
const receiptPath = await c.persistE48Receipt(actual);
Root uses a fresh controller instance per phase. Receipt persistence is a separate
explicit call and accepts only the successful same-instance result object. It is
factual capture after completed work, not authority for a future mutation.

Every mutation is O_EXCL reserved, intent-fsynced, owner-fenced, then called once.
The entire raw MCP return is O_EXCL/fsync captured before any post-call owner check,
parsing or ACK validation. Thrown calls also capture transport_error and STOP with
outstanding intent. Each identifying SHA is verified; a bare ref success produces
ack_sha:null and requires fresh exact ref GET. Tree updates are sparse full-root
updates in chunks <=32, with predicted root/bench/scope hashes and full actual
readback before sole-parent commit. Scope readback requires exact returned scope
SHA and unique actual leaf paths; duplicate leaves cannot mask an omitted path.
Ref updates require exact parent and force:false.
No uncertain retry, old object query/recreation, main update, or SCI call exists.

Tests use invented metadata only; their results make no benchmark/model/runtime
claim. The implementation is newly authored, informed by previously reviewed E47
request syntax and durable transaction boundaries; no old mode was executed.
