# Exact E42 archive restoration adapter

This helper validates one exact archive and materializes only its287 reviewed public-project files. It makes no Git, package, model, native, data, Gold or EVAL calls. The embedded old ledger may be restored locally byte-for-byte; the separate transaction controller forbids creating or referencing its old uncertain Git object.

Current recovery invocation, only after independent approval:

    python3 -I -B restore_epoch42_archive.py --restore-scope NEW_SCOPE --kit-root NEWKIT --dest NEWR --archive recoveries/epoch42-publication-20261026/immutable-e42-artifacts.zip --projection recoveries/epoch42-publication-20261026/ARCHIVE_PROJECTED_FILES.v1.json

`--plan` defaults to `recoveries/epoch42-publication-20261026/RECOVERY_TRANSACTION_PLAN.v1.json` within NEWKIT. Archive/projection/plan relative paths resolve within NEWKIT; exact absolute regular inputs are also accepted. `--kit` is an alias for `--kit-root`. `--restore-scope` defaults to the historical gen3 recovery scope. A future continuation may supply its new canonical isolated scope; KIT and project must be sibling descendants. The fixed transaction plan still describes the historical archive transaction and does not claim its owner is current.

Whole immutable old W42 and03:18 recovery scopes are blocked in both ancestry directions. Original public ZIP/supplement files and all selected output collisions or ancestry overlaps with inputs are blocked. NEWKIT may contain its own new recoveries inputs intentionally. All287 existing targets in BOTHdestinations are validated before the first mkdir/filewrite; then only O_EXCL+file/directory fsync writes or byte-identical verification occur. Copies are used; no old inode or archive is linked, changed or overwritten.

Append `--verify-only` after restoration to demand all287 exact bodies in both KIT and project without creating anything. KIT materialization is mandatory because unchanged restore_checkpoint.py reads its source bytes from KIT even when project targets already exist. Never use extractall or extract any of the other70 members. The unchanged legacy transports restore their separate3 files.

The adapter is source-reviewed and passed ten unrelated invented ZIP/tempdir fixtures. No real archive validation or actual restoration was performed by its author. Root must retain the approved source hash and concrete transaction/ZIP/projection identities before running full reconstruction.
