"""One owned supervisor; capture failures before workerPopen and all cleanup."""
import argparse
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import time
import re

INVARIANTS = ["source_plan_and_slot_match", "worker_exit_zero",
    "worker_preexec_CPU_network_guard_valid", "all_36_forecasts_present",
    "all_36_completion_draws_present", "native_one_corpus_closed",
    "reader_process_reaped_exit_zero", "no_gold_decoded", "no_worker_errors",
    "worker_affinity_and_thread_limits", "no_warmup_or_external_network", "whole_soft_deadline_met"]


def load(name):
    p = Path(__file__).with_name(name + ".py")
    s = importlib.util.spec_from_file_location("e46_" + name, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--plan", required=True)
    parser.add_argument("--plan-sha256", required=True); parser.add_argument("--admission", required=True)
    args = parser.parse_args(); C = load("common")
    scope = C.ROOT / "experiments/sota-2026-10-22/epoch46"
    out = scope / "runs/dev"; out.mkdir(parents=True, exist_ok=True)
    reservation = C.read(scope / "DISPATCH_RESERVATION.json")
    dispatch_time = reservation["dispatch_monotonic_seconds"]
    supervisor = C.stable_identity(C.proc(os.getpid())); worker = None; identity = None; raw = None; plan = None
    result = {"schema_version":1,"epoch":46,"kind":C.KIND,"phase":"dev",
              "plan_sha256":args.plan_sha256,"status":"FAILED","errors":[],
              "worker_popen_attempted":False,"worker_returned_handle":False,
              "supervisor_identity":supervisor,
              "worker_identity":None,"worker_exit_code":None,"raw":None,
              "operation_counts_complete":False,"raw_operation_counters_source":"UNKNOWN",
              "worker_slot_reservation":reservation["worker_slot_reservation"]}
    C.put(scope / "SUPERVISOR_STARTED.json", {"supervisor_identity":supervisor,
             "plan_sha256":args.plan_sha256,"dispatch_monotonic_seconds":dispatch_time})
    streams = []; invariants = {key:False for key in INVARIANTS}; rc = 1
    try:
        plan = C.admit(args.plan, args.plan_sha256, args.admission)
        C.require(plan["worker_slot_reservation"] == reservation["worker_slot_reservation"], "RESERVED_SLOT")
        guard = C.load_module("e46_process_guard", C.HERE / "process_guard.py")
        external = C.no_symlink(plan["external_run_directory"])
        external.mkdir(mode=0o700, parents=True, exist_ok=True)
        cpu_path = external / "WORKER_CPU_NETWORK_GUARD.json"
        cpu_fd = os.open(cpu_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        stdout = (external / "worker.stdout").open("xb"); stderr = (external / "worker.stderr").open("xb")
        streams = [stdout, stderr]
        command = [plan["python_executable"], "-I", "-B", str(C.HERE / "worker.py"),
                   "--plan", args.plan, "--plan-sha256", args.plan_sha256, "--admission", args.admission]
        result["worker_popen_attempted"] = True
        try:
            worker = subprocess.Popen(command, cwd=external, env=C.child_env(plan),
                stdout=stdout, stderr=stderr, start_new_session=True,
                preexec_fn=guard.make_preexec(cpu_fd), pass_fds=(cpu_fd,))
        finally: os.close(cpu_fd)
        result["worker_returned_handle"] = True; identity = C.proc(worker.pid)
        result["worker_identity"] = identity
        C.require(identity and identity["pgid"] == worker.pid and identity["sid"] == worker.pid,
                  "WORKER_SESSION_IDENTITY")
        while worker.poll() is None:
            C.owner_fence()
            C.require(time.monotonic() < dispatch_time + 585, "SUPERVISOR_WORKER_DEADLINE")
            time.sleep(0.2)
    except BaseException as error:
        message=str(error)
        result["errors"].append({"code":"SUPERVISOR_STAGE_FAILED","type":type(error).__name__,
                                 "reason_code":message if re.fullmatch(r'[A-Z0-9_]{1,120}',message) else None})
    finally:
        if worker is not None and worker.poll() is None:
            current = C.proc(worker.pid)
            if identity and current and current["ticks"] == identity["ticks"] and current["pgid"] == worker.pid:
                os.killpg(worker.pid, signal.SIGTERM)
                try: worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(worker.pid, signal.SIGKILL); worker.wait(timeout=2)
            else:
                result["errors"].append({"code":"WORKER_CLEANUP_IDENTITY_UNKNOWN","type":"OwnershipUnknown"})
        for stream in streams: stream.close()
        result["worker_exit_code"] = worker.returncode if worker is not None else None
        if (out / "raw.json").exists():
            result["raw"] = C.ref(out / "raw.json")
            try:
                raw = C.read(out / "raw.json")
                result["raw_operation_counters_source"] = "RETAINED_WORKER_RAW"
                result["operation_counts_complete"] = raw.get("status") == "DEV_FORECASTS_COMPLETE_NO_GOLD"
                result["operation_counters"] = raw["counters"]
            except BaseException as error:
                result["errors"].append({"code":"RAW_CAPTURE_FAILED","type":type(error).__name__})
        if raw is not None and plan is not None:
            counts = raw["counters"]; facts = raw["closure_facts"]; resources = raw["resources"]
            cpu = C.read(Path(plan["external_run_directory"]) / "WORKER_CPU_NETWORK_GUARD.json")
            invariants = {
                "source_plan_and_slot_match":raw["plan_sha256"]==args.plan_sha256 and raw["worker_slot_reservation"]==plan["worker_slot_reservation"],
                "worker_exit_zero":result["worker_exit_code"]==0,
                "worker_preexec_CPU_network_guard_valid":cpu.get("status")=="CPU_AND_UNIX_GUARD_INSTALLED_BEFORE_EXEC" and cpu.get("CPU_affinity")==[0,1],
                "all_36_forecasts_present":len(raw["completed_forecast_ids"])==36 and set(raw["completed_forecast_ids"])==set(raw["required_forecast_ids"]),
                "all_36_completion_draws_present":counts["completion_requests_completed"]==36 and counts["first_answer_token_draws_observed"]==36,
                "native_one_corpus_closed":facts["native_child_closed"] is True and facts["native_exit_code"]==0 and counts["corpus_batches_completed"]==1,
                "reader_process_reaped_exit_zero":facts["reader_child_closed"] is True and facts["reader_exit_code"]==0,
                "no_gold_decoded":counts["semantic_gold_decodes"]==0,
                "no_worker_errors":raw["errors"]==[],
                "worker_affinity_and_thread_limits":resources["cpu_affinity"]==[0,1] and resources["reader_threads"]==2 and resources["reader_batch_threads"]==2 and resources["HTTP_threads"]==1,
                "no_warmup_or_external_network":(raw.get("reader_runtime_receipt") or {}).get("warmup") is False and cpu.get("allowed_socket_domain")==1,
                "whole_soft_deadline_met":raw.get("work_completed_monotonic_seconds",float("inf"))-dispatch_time<=570,
            }
        result["wall_seconds"] = time.monotonic()-dispatch_time
        if all(invariants.values()) and not result["errors"]:
            result["status"]="WORKER_COMPLETED"; rc=0
        execution = C.put(out / "execution.json", result)
        C.put(scope / "SUPERVISOR_COMPLETION.json", {"schema_version":1,"epoch":46,"kind":C.KIND,
            "phase":"dev","plan_sha256":args.plan_sha256,"execution":execution,
            "supervisor_identity":supervisor,"errors":result["errors"],"invariants":invariants,
            "intended_process_returncode":rc,"dispatch_monotonic_seconds":dispatch_time,
            "completed_monotonic_seconds":time.monotonic(),
            "actual_exit_status_source":"NOT_OBSERVED_BY_SELF_REQUIRES_PHYSICAL_OBSERVER"})
    return rc


if __name__ == "__main__": raise SystemExit(main())
