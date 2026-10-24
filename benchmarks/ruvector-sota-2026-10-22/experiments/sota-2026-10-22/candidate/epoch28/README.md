Epoch 28 qualifies the exact submitted full-input comparator on eight independently frozen CC0 authored engineering requests. It does not run a benchmark or make a generalization claim. Historical sources remain byte-identical.

Run only after root source publication and independent actual readback admission:

    python -B experiments/sota-2026-10-22/candidate/epoch28/launch_engineering.py --scope /tmp/ruvector-sota-2026-10-22/epoch28-aa09a8d75110 --plan /tmp/ruvector-sota-2026-10-22/epoch28-aa09a8d75110/project/experiments/sota-2026-10-22/epoch28/plan.json --admission /tmp/ruvector-sota-2026-10-22/epoch28-aa09a8d75110/project/experiments/sota-2026-10-22/epoch28/NATIVE_ADMISSION.json --expected-plan-sha <actual frozen plan SHA256>

The worker CLI uses --plan, --admission, --out, --expected-plan-sha and --deadline; root launches it only through the bounded launcher. Plan keys are documented by common.verify_plan. The data roles are all empty.

Runtime needs standard-library Python and Node plus the 17 hash-pinned RUNTIME_ASSETS rows:14 exact original TypeSafe closure files,2 BGE assets and the original model manifest. There is no Python ML environment, HTTP service, head fit or extra model. CPU affinity is0,1; computational environment budgets are2,UV1. OS helper/thread counts are measured. The whole launch including initialization and cleanup is bounded at600seconds.

The wrapper passes all source bytes and the exact question map through the unchanged validate_request and CompositeEngine pipeline. It tees actual synchronous stdin/stdout text without consuming data early. It preserves complete composite/native/baseline/proof responses, raw refusal lines and unknown error kinds. Untrained native noul remains an uncalibrated similarity score. The original16KiB state boundary and original BGE256token context limit are distinct. No source clipping, fallback settings, warmups or retries are added.

preflight.py performs only static/source-hash and synthetic mutation/network-policy checks. It does not import a model/native addon or read DEV/CONF inputs. All source must be frozen before the real engineering worker runs.

Before the original Node process execs, its isolated child is pinned to CPUs0,1 and installs no_new_privs plus a Linuxx86_64 seccomp filter denying sched_setaffinity203 and its x32 variant with EPERM. All future threads and execs inherit this narrow CPU resource boundary. The parent and global kernel configuration remain unchanged; original model settings remain unchanged. Actual preexec/proc evidence is retained, while actual blocked syscall totals remain unknown. Static preflight proves the boundary using a separate standard-library Python child, including exec/thread inheritance and x32 denial, without loading a model or native addon.
