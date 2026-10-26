"""One source-admitted actual native corpus and36 Qwen completion readouts; noGold."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
import re
import traceback


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True); parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--admission", required=True)
    args = parser.parse_args()
    C = module("e46_common", Path(__file__).with_name("common.py"))
    plan = C.admit(args.plan, args.plan_sha256, args.admission)
    out = C.ROOT / "experiments/sota-2026-10-22/epoch46/runs/dev"
    external = C.no_symlink(plan["external_run_directory"])
    reservation = C.read(C.ROOT / "experiments/sota-2026-10-22/epoch46/DISPATCH_RESERVATION.json")
    deadline = reservation["dispatch_monotonic_seconds"] + 570
    C.remaining(deadline)
    C.put(out / "attempt.json", {**C.proc(os.getpid()), "startticks":C.proc(os.getpid())["ticks"],
                                "plan_sha256":plan["_plan_sha"]})
    counters_module = C.load_module("e46_counters", C.HERE / "counters.py")
    counters = counters_module.initial(); lifecycle = []; journal = []
    raw = {"schema_version":1, "epoch":46, "kind":C.KIND, "phase":"dev", "plan_sha256":plan["_plan_sha"], "node_runtime_receipt":plan["node_runtime_receipt"],
           "status":"DEV_PARTIAL_NO_GOLD", "cases":[], "counters":counters, "errors":[],
           "reader_lifecycle":lifecycle, "reader_runtime_receipt":None, "reader_state":{},
           "native_state":{}, "external_evidence":{}, "required_forecast_ids":[i+"::"+a for i in C.CASES for a in C.ARMS],
           "completed_forecast_ids":[], "backend_forward_batch_count":None,
           "worker_slot_reservation":plan["worker_slot_reservation"]}
    progress_file = external / "worker-progress.jsonl"
    def progress(event):
        if event.get("event") in ("BGE_FORWARD_BEFORE", "BGE_INITIALIZATION_BEFORE", "NATIVE_HELPER_POPEN_BEFORE"):
            C.remaining(deadline)
        with progress_file.open("a") as stream:
            stream.write(json.dumps({"monotonic_seconds":time.monotonic(), **event,
                                     "counters":dict(counters)}, allow_nan=False)+"\n")
            stream.flush(); os.fsync(stream.fileno())
    reader = None; started = time.monotonic(); rc = 1
    try:
        guard = C.load_module("e46_assets_guard", C.HERE / "assets_guard.py")
        raw["asset_runtime_receipt"] = guard.verify(C, plan)
        features = C.load_module("e46_features_only", C.checked(plan["features_source"]["path"]))
        rows = features.load_private_features(plan["private_features"]["path"],
                    plan["private_features"]["sha256"], C.CASES)
        C.require([r["id"] for r in rows] == C.CASES, "FEATURE_ID_ORDER")
        counters["feature_cases_admitted"] = len(rows)
        counters["feature_documents_admitted"] = len({r["document_id"] for r in rows})
        catalog = C.load_module("e46_source_catalog", C.HERE / "source_catalog.py")
        documents = {}
        for row in rows: documents.setdefault(row["document_id"], row["evidence"])
        for doc, spans in documents.items():
            C.require(catalog.sentence_catalog(''.join(s["sentence"] for s in spans)) == spans,
                      "FULL_CATALOG_REPRODUCTION")
            C.require(len(spans) == plan["source_units_per_document"][str(doc)], "SOURCE_COUNT")
        bge = C.load_module("e46_bge", C.HERE / "bge.py")
        codec = C.load_module("e46_vector_codec", C.HERE / "vector_codec.py")
        bundle, prepared, bge_receipt = bge.prepare_bundle(C, rows, counters, progress, codec)
        raw["BGE_runtime_receipt"] = bge_receipt
        native_io = C.load_module("e46_native_io", C.HERE / "native_io.py")
        native = native_io.run(C, plan, bundle, counters, progress, out, external, deadline, raw["native_state"])
        raw["external_evidence"]["native_output"] = C.ref(external / "dev-native-result.json")
        raw["external_evidence"]["native_input"] = C.ref(external / "dev-native-bundle.json")
        observed = {}
        for document in native["documents"]:
            for query in document["queries"]:
                observed[query["case_id"].removesuffix("::retrieval:original")] = (document, query)
        P = C.load_module("e46_protocol", C.HERE / "protocol.py")
        transport = C.load_module("e46_http_transport", C.HERE / "http_transport.py")
        reader_module = C.load_module("e46_reader", C.HERE / "reader.py")
        packing = C.load_module("e46_packing", C.HERE / "packing.py")
        coverage = C.load_module("e46_coverage", C.HERE / "coverage_audit.py")
        reader = reader_module.Reader(C, P, transport, plan, counters, progress, lifecycle, deadline, external)
        reader.start(); raw["reader_runtime_receipt"] = reader.runtime_receipt
        for record in rows:
            document, query = observed[record["id"]]; spans = record["evidence"]; n = len(spans)
            C.require(query["requested_k"] == n and sorted(query["ids"]) == list(range(n)), "NATIVE_ALL_SOURCE_UNITS")
            orders = [query["ids"], catalog.lexical_order(spans, record["claim"]), list(range(n))]
            case = {k:record[k] for k in ("id","document_id","hypothesis_id","input_sha256",
                                         "source_group_sha256","source_document_sha256")}
            case.update(native_order_ids=list(query["ids"]), lexical_order_ids=orders[1],
                        source_unit_ids=orders[2], embedding_audit=prepared[record["id"]], forecasts={})
            raw["cases"].append(case)
            for arm, order in zip(C.ARMS, orders):
                before = time.monotonic()
                packed = packing.build(C, P, catalog, record, order, arm, reader, journal)
                packed_evidence = "\n\n".join("\n\n".join(spans[i]["sentence"] for i in
                                        window["source_unit_ids"]) for window in packed["windows"])
                features.assert_packed_input(record["claim"], packed_evidence)
                score_started = time.monotonic(); value, http_receipt = reader.score(packed["tokens"])
                forecast_id = record["id"] + "::" + arm
                value.update(forecast_id=forecast_id, windows=packed["windows"],
                             prompt_sha256=packed["prompt_sha256"], token_ids_sha256=packed["token_ids_sha256"],
                             fullprompttoken_count=packed["prompt_token_count"],
                             packing_final_journal_ordinal=packed["final_journal_ordinal"],
                             base_prompt_tokens=packed["base_prompt_tokens"],
                             equal_window_budget=packed["equal_window_budget"], http_exchange=http_receipt,
                             numeric_date_audit=coverage.audit(spans, packed["union_selected_unit_ids"]),
                             timings={"request_wall_seconds":http_receipt["wall_seconds"],
                                      "context_packing_seconds":score_started-before,
                                      "model_readout_HTTP_seconds":time.monotonic()-score_started,
                                      "packing_and_readout_seconds":time.monotonic()-before,
                                      "native_query_seconds":query["query_ms"]/1000,
                                      "scope":"Observed components; excludeinitialization/sharedBGE/nativeindexwait. Fullbatchcaptureincludesallinit/cleanup."})
                case["forecasts"][arm] = value; counters["forecasts_completed"] += 1
                raw["completed_forecast_ids"].append(forecast_id)
                progress({"event":"FORECAST_COMPLETE", "forecast_id":forecast_id})
        reader.event("ALL_COMPLETIONS_CLOSED", forecasts_completed=counters["forecasts_completed"])
        C.remaining(deadline)
        raw["work_completed_monotonic_seconds"] = time.monotonic()
    except BaseException as error:
        message=str(error)
        raw["errors"].append({"code":"WORKER_STAGE_FAILED", "type":type(error).__name__,
                              "reason_code":message if re.fullmatch(r'[A-Z0-9_]{1,120}',message) else None})
        failure=external/'worker.exception.txt';failure.write_text(traceback.format_exc())
        raw["external_evidence"]["worker_exception"] = C.ref(failure)
    finally:
        if reader is not None:
            try: raw["reader_state"] = reader.close()
            except BaseException as error:
                raw["reader_state"] = reader.state
                raw["errors"].append({"code":"READER_CLOSURE_FAILED", "type":type(error).__name__})
            raw["external_evidence"]["HTTP_capture_index"] = C.put(external / "HTTP_CAPTURE_INDEX.json", reader.http.receipts)
        raw["external_evidence"]["packing_journal"] = C.put(external / "PACKING_JOURNAL.json",
            {"schema_version":1,"epoch":46,"kind":C.KIND,"phase":"dev","source_plan_sha256":plan["_plan_sha"],"proposals":journal})
        state = raw["reader_state"]; native_state = raw["native_state"]
        raw["closure_facts"] = {"completion_requests_completed":counters["completion_requests_completed"],
            "first_answer_token_draws_observed":counters["first_answer_token_draws_observed"],
            "forecasts_completed":counters["forecasts_completed"], "reader_child_closed":state.get("child_closed"),
            "reader_exit_code":state.get("exit_code"), "native_child_closed":native_state.get("child_closed"),
            "native_exit_code":native_state.get("exit_code"), "semantic_gold_decodes":0,
            "all_forecasts_closed_before_gold":counters["forecasts_completed"]==36 and
                state.get("child_closed") is True and native_state.get("child_closed") is True}
        usage = resource.getrusage(resource.RUSAGE_SELF)
        raw["resources"] = {"cpu_affinity":sorted(os.sched_getaffinity(0)), "reader_threads":2,
            "reader_batch_threads":2,"HTTP_threads":1,"user_seconds":usage.ru_utime,
            "system_seconds":usage.ru_stime,"max_rss_kib":usage.ru_maxrss,
            "children_max_rss_kib":resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            "cgroup_memory_current":int(Path('/sys/fs/cgroup/memory.current').read_text()),
            "cgroup_memory_peak":int(Path('/sys/fs/cgroup/memory.peak').read_text())}
        raw["wall_seconds"] = time.monotonic()-started
        raw["completed_monotonic_seconds"] = time.monotonic()
        expected = counters_module.expected_fixed(plan["source_units_per_document"])
        complete = (not raw["errors"] and all(counters.get(k)==v for k,v in expected.items()) and
                    state.get("child_closed") is True and state.get("exit_code")==0 and
                    native_state.get("child_closed") is True and native_state.get("exit_code")==0)
        if complete: raw["status"]="DEV_FORECASTS_COMPLETE_NO_GOLD"; rc=0
        C.put(out / "raw.json", raw)
    return rc


if __name__ == "__main__": raise SystemExit(main())
