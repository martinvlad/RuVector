This is a new ARCHIVE_RECOVERY_NO_SCI transport, not an E49 retry.

The exact reviewed ZIP has 2,909,023 bytes and SHA256
2b7e357a7058f8fd850810589cdfbc41937ccac20cd49ac985a7600bb9881194.
The envelope is one text Git payload; no ZIP member is a Git blob payload or live
Git object reference. Its 76 project files are a separate decoded overlay and
never CP project_files rows. Old requests, journals, controllers and scientific
slots inside the envelope remain closed evidence and must not execute.

Canonical recovery prefix:
recoveries/epoch49-stop-publication-20261027-g15/
Actual lease root W50:
/dev/shm/ruvector-sota-2026-10-22/epoch50-ad86e60e2402
Operational recovery root: W50/recovery-transport
Project root: W50/project (not operational-root/project).
Owner/release checks reference actual W50, Guardian15 PID158817/start38479788,
original dev33/inode13626, CPU0,1, exact owner711/2854df82624e7c7c236b45b799c383a3555673a6268d7500858f1b9bc18410bc.
Fresh actual recovery parent ad86e60e240281c0439429b02746c2239a39c0d3,
Git leaves8128, CP rows8121. Main remains read-only c44d7337c0c5ad2ecd2294178475387facb96516.

Three permanent UNKNOWN objects are metadata only, never query, recreate or live-reference:
486888de9602bbb5d817a55f707b4fcfd11c65e0
3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5
a68b7ba587332f176f65d0348de3e910aa16e77a
All newly decoded Git payload hashes are checked against these before staging.
The immutable E49 journal is never loaded by this recovery controller.

Reviewed recovery-v1/{guard.py,stagebuilder.py,controller.js} are copied by Root
to operational-root/publication-helpers and canonical recovery/publication/.
They retain reviewed durable raw-first/O_EXCL/CAS/full-tree algorithms. Operational
phase is source only, with prefix e50-recovery-source-g15. No FINAL recovery mode.
Kind and receipt publication_role are ARCHIVE_RECOVERY_NO_SCI.
V2 adds an awaited 2,000 ms delay immediately before each reserve/intent sequence,
followed by the existing fresh owner fences. All mutations remain sequential, with
no retries. Freeze minimum_pre_mutation_delay_ms:2000 in the recovery and standard
plans. Pacing makes no claim about the cause of the E49 UNKNOWN error.

Required phase input (same exact3ref conventions as reviewed E49 transport):
schema_version1,epoch50,kind ARCHIVE_RECOVERY_NO_SCI,phase source,
source_checkpoint and parent both actual original ad86 commit,
owner exact local3ref, plan canonical recovery/plan.json3ref,
source_freeze canonical recovery/SOURCE_FREEZE.json3ref,
transport_sources:{guard,stagebuilder,controller} exact canonical3refs,
source_map actual local3ref,root_baseline and bench_baseline local3refs (raw MCP
envelopes or decoded API tree objects),current_CP/current_CONT actual local3refs,
artifacts [{path,local_path:absolute R/path,bytes,sha256}],ACTIVE,CONT_patch,
CP_phase_record,commit_message. Only the recovery prefix and three controls may change.

Plan contains epoch50,kind ARCHIVE_RECOVERY_NO_SCI,source_checkpoint ad86,
source_freeze_path canonical relative (never absolute). SF contains epoch50,
source_checkpoint ad86,files covering every recovery artifact including plan,
except SF itself. Integrated approvals referencing the SF hash remain operational
outside R until later closure, avoiding a hash cycle.

ACTIVE epoch50,phase source,kind ARCHIVE_RECOVERY_NO_SCI,source_checkpoint ad86,
owner_sha256 exact,work_active true,experiments_active false,
OS_lock_observation_scope PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE,
publication_is_not_scientific_authorization true.

CONTROL_PATCH_FRAGMENT.v1.json is a reviewed metadata authoring fragment. Its CP
record key is epoch49_publication_recovery15, not epoch50_source. CONT permits only
that new recovery record and cumulative_budget_ledger; the new budget row is
epoch49_actual_execution, preserving every existing old field/type. Original facts:
41 blob attempts,40 acknowledged,1 UNKNOWN,0 tree/commit/ref,0 DATA/model/native/
Gold/EVAL/paidAPI/GPU. The fragment records original E49 publication as unpublished,
all E49 source/scientific slots closed unexecuted, exact envelope/extractor/manifest
references, overlay76 separate from CP/Git, native104 unchanged, no official rank.
Root must compare the fragment's old cumulative budget to freshly captured CONT.

Preparation approval: checks_passed true,phase_preparation_allowed true,
phase_input_sha256 exact. Root alone invokes fresh stagebuilder once:
python -I -B operational-root/publication-helpers/stagebuilder.py --input INPUT
 --input-sha SHA --approval PREP --approval-sha SHA --out operational-root/stage-source

Full stage approval requires checks_passed,publication_phase_allowed,
source_and_denylist_review_passed,dual_unknown_denylist_reviewed all true (the legacy
field name is retained; forbidden_Git_objects must list all THREE sorted SHAs),
epoch50,phase source,stage_metadata_sha256,expected_final_root_sha,source_parent,
owner_sha256,source_freeze_sha256,original_blob5_execution UNKNOWN_PERMANENTLY.

Root pins loaded controller bytes to canonical frozen source before definitions:
const c = new Function('tools',source+'\nreturn {publishE50Recovery,persistE50RecoveryReceipt};')(tools);
const actual=await c.publishE50Recovery('source',approvalPath,approvalSHA);
const receipt=await c.persistE50RecoveryReceipt(actual);
No automatic invocation; no retry, reconciliation, old journal import or SCI authority.

Root then independently reads back actual full remote commit/tree/leaves/controls.
Only after this actual recovery proof may Root invoke definitions-only
render_transports.render('standard',freshOwnOut,readback). Required proof fields:
checks_passed true,verified_actual_remote_readback true,
publication_role ARCHIVE_RECOVERY_NO_SCI,original_parent ad86,
commit/root/bench/scope actual40hex,Git_leaves/CP_rows actual counts. Deltas from
8128/8121 must match (only recovery transport public rows were added).
The standard render binds E50 BASE/plan.source_checkpoint to this actual recovery
commit, scopes new sources to P50/A50/T50, retains same Guardian15 and all three
DENY entries. Standard journal/stages are under W50, separate from recovery.
The E50 scientific source/plan checkpoint bindings must agree after recovery.
No future commit or scientific source freeze is guessed. Standard SOURCE/FINAL
still require their separate exact preparation and full-stage approvals.

Reconstruction: reviewed original bootstrap/restore and older separate overlays
first; then restore_e49_overlay.py verifies the exact ZIP and all268 member hashes,
restores ONLY the76 project rows with no overwrite of differing bytes, never
extracts old operational requests into executable project paths, and runs nothing.
Standard inherited SF references must have baseline CP/Git provenance; E49 overlay
members have neither. Use the published recovery manifest/envelope for provenance
and newly reviewed E50 source under P50/A50/T50 for the new actual pilot.
