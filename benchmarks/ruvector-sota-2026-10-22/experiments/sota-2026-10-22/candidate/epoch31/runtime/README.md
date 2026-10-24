# E31 detached, single DEV worker

The root bootstrap exclusively writes and fsyncs `DISPATCH_RESERVATION.json` before calling the frozen launcher once with `start_new_session=True`, closed inherited FDs and stdin/stdout/stderr connected to DEVNULL/exclusive files outside the public project. The actual returned supervisor PID/startticks/PGID/SID is sealed in `DISPATCH_ATTEMPT.json`. The launcher waits at most3seconds for that exact identity receipt; no model starts before it matches. The dispatch alone burns the sole logical budget. The count is the maximum of dispatch and DEV reservation, never their sum, and no uncertain dispatch is retried.

The launcher CLI is:

```text
<approved Python> -I -B runtime/launch.py --scope <S31> --plan <STUDY>/plan.json --admission <STUDY>/SOURCE_ADMISSION.json --expected-plan-sha <SHA256> --phase dev
```

The deadline starts at the shared same-boot dispatch monotonic/unix clocks. Source checks, static asset checks, startup wait, model initialization and cleanup count toward600seconds. Work stops by585seconds, leaving15seconds for owned cleanup/sealing. A supervisor alarm also bounds pre-Popen checks. During the worker wait the supervisor verifies the detached guardian's exact boot/PID namespace/PID/startticks/FD3/FLOCK/inode/generation/expiry at intervals no greater than0.5seconds. Authority loss stops only the proved owned worker session.

Whole-worker preexec pins CPU0,1, installs no_new_privs and a seccomp filter denying native/x32 sched_setaffinity with EPERM before Python exec. Threads and Node inherit it without resetting affinity. Compute thread environments are2 (interop1), while OS threads may exceed2 within the same two CPUs. The guard changes no global kernel setting; actual denied-call totals are unobserved.

Python and Node networking guards are persistent API interposition, not a kernel network sandbox. The inherited prospectively frozen E30 policy permits at most one pinned urllib3 `_has_ipv6` literal `('::1',0)` capability bind, records success/error/close/stack/source provenance, and requires descriptor closure. Communication, DNS, listening, accepting and other binds remain denied. No local service is permitted.

`runs/dev/execution.json` selects counters from exact final raw, exact partial raw, or UNKNOWN. Checkpoint counts are incomplete; execution since a checkpoint remains UNKNOWN. Original malformed final bytes and pending checkpoint bytes remain sealed. An unreturned worker Popen keeps starts uncertain even when exact direct-child preexec proof permits cleanup. Missing proof preserves null physical closure; it never becomes zero operations or a retryable slot.

`SUPERVISOR_COMPLETION.json` records ABOUT_TO_EXIT and intended exit code only. Root does not claim a waited detached-launcher exit code. The separate frozen observer produces `SUPERVISOR_OBSERVED_CLOSURE.json` after checking exact supervisor identity and all owned worker group members. Known Z/X with no FDs/live memory may be physically closed even when PID1 retains a zombie. Missing identity/ownership proof remains UNKNOWN and blocks final publication and gold join.

File-poll reattachment can tolerate lost tool stdio. Survival across container/cgroup restart is unproven, and such loss never reopens the budget. No job daemon or host-wide service is introduced.
