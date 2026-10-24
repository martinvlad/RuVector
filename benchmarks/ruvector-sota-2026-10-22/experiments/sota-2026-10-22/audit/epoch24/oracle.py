"""CC0 epoch24 independent saved-trace oracle; never imports candidate code."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Review:
    def __init__(self):
        self.checks = []

    def check(self, name, condition, detail=None):
        self.checks.append(dict(name=name, passed=bool(condition), detail=detail))


def span_ok(span, source):
    if not isinstance(span, dict):
        return False
    a, b = span.get("start"), span.get("end")
    return (isinstance(a, int) and not isinstance(a, bool) and
            isinstance(b, int) and not isinstance(b, bool) and 0 <= a <= b <= len(source) and
            span.get("text") == source[a:b] and
            span.get("source_byte_start") == len(source[:a].encode("utf-8")) and
            span.get("source_byte_end") == len(source[:b].encode("utf-8")))


def closure(seed, graph):
    seen, todo = set(), [seed]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        todo.extend(graph.get(node, ()))
    return seen


def rendering(ids, gold, sources):
    order = {e: i for i, e in enumerate(sources)}
    units = {u["id"]: u for u in gold["units"]}
    ordered = sorted((units[x] for x in ids), key=lambda u: (order[u["id"].split("::", 1)[0]], *u["whole"], u["id"]))
    groups = []
    for u in ordered:
        eid = u["id"].split("::", 1)[0]
        a, b = u["whole"]
        if groups and groups[-1][0] == eid and a <= groups[-1][2]:
            groups[-1][2] = max(groups[-1][2], b)
            groups[-1][3].append(u["id"])
        else:
            groups.append([eid, a, b, [u["id"]]])
    return "\n".join(sources[e][a:b] for e, a, b, _ in groups), groups


def expected_pack(seeds, close, inp, gold, sources):
    units = {u["id"]: u for u in gold["units"]}
    graph = {u: [] for u in units}
    for a, b in gold["edges"]:
        graph[a].append(b)
    effective = list(dict.fromkeys(seeds))[:inp["seed_limit"]]
    chosen, dropped = set(), []
    for seed in effective:
        component = closure(seed, graph) if close else {seed}
        candidate = chosen | component
        text, _ = rendering(candidate, gold, sources)
        if len(candidate) > inp["budget"]["max_nodes"] or len(text.encode("utf-8")) > inp["budget"]["max_utf8_bytes"]:
            dropped.append(seed)
        else:
            chosen = candidate
    text, spans = rendering(chosen, gold, sources)
    missing = {seed: sorted(closure(seed, graph) - chosen) for seed in effective if seed in chosen}
    missing = {k: v for k, v in missing.items() if v}
    return effective, chosen, dropped, text, spans, missing


def expected_headings(unit, byid, sources):
    chain, parent = [], unit["parent_id"]
    while parent is not None:
        pu = byid[parent]
        eid = parent.split("::", 1)[0]
        a, b = pu["content"]
        content = sources[eid][a:b]
        if content.endswith(":"):
            last = content.rsplit("\n", 1)[-1]
            trimmed = last.lstrip(" \t\r")
            start = b - len(trimmed)
            chain.append((eid, start, b, trimmed))
        parent = pu["parent_id"]
    return list(reversed(chain))


def audit_parser(review, inp, gold, parser):
    cid = inp["id"]
    src = {e["id"]: e["text"] for e in inp["excerpts"]}
    expected = {u["id"]: u for u in gold["units"]}
    actual = parser.get("units", {})
    review.check(cid + ":parser_policy", parser.get("parser_policy_version") == "epoch24-raw-structure-v1")
    review.check(cid + ":input_schema_valid", parser.get("valid") is True and parser.get("errors") == [])
    review.check(cid + ":unit_identity_and_order", list(actual) == list(expected), {"expected": list(expected), "observed": list(actual)})
    graph = {u: [] for u in expected}
    for a, b in gold["edges"]:
        graph[a].append(b)
    for uid, u in expected.items():
        a = actual.get(uid, {})
        eid = uid.split("::", 1)[0]
        source = src[eid]
        review.check(cid + ":" + uid + ":manual_bounds", all(a.get(k) == v for k, v in {
            "start": u["whole"][0], "end": u["whole"][1], "marker_start": u["marker"][0],
            "marker_end": u["marker"][1], "content_start": u["content"][0], "content_end": u["content"][1],
            "parent_id": u["parent_id"], "excerpt_id": eid, "clause_id": u["label"]}.items()))
        for key, bounds in [("marker_span", u["marker"]), ("content_span", u["content"]), ("whole_span", u["whole"])]:
            span = a.get(key, {})
            review.check(cid + ":" + uid + ":" + key, span_ok(span, source) and [span.get("start"), span.get("end")] == bounds)
        review.check(cid + ":" + uid + ":exact_dependencies", sorted(a.get("requires", [])) == sorted(graph[uid]) and len(a.get("requires", [])) == len(set(a.get("requires", []))))
        headings = a.get("heading_spans", [])
        want = expected_headings(u, expected, src)
        review.check(cid + ":" + uid + ":inherited_heading_spans", len(headings) == len(want) and all(
            span_ok(h, src[e]) and [h.get("start"), h.get("end"), h.get("text")] == [lo, hi, text]
            for h, (e, lo, hi, text) in zip(headings, want)))
    refs = parser.get("references", [])
    wanted = gold["references"]
    review.check(cid + ":reference_count", len(refs) == len(wanted), {"expected": len(wanted), "observed": len(refs)})
    for n, (a, w) in enumerate(zip(refs, wanted)):
        eid = w["owner_id"].split("::", 1)[0]
        good = all(a.get(k) == w[k] for k in ["owner_id", "target_literal", "resolved_target_id", "status"])
        good = good and a.get("inherited") is False
        trigger = w["trigger_literal"].lower()
        kind = "subject_to" if trigger == "subject to" else "exception_reference" if trigger.startswith("except ") else "condition_reference"
        good = good and a.get("trigger_kind") == kind
        for k, bounds in [("trigger_span", w["trigger"]), ("target_span", w["target"])]:
            span = a.get(k, {})
            good = good and span_ok(span, src[eid]) and [span.get("start"), span.get("end")] == bounds
        review.check(cid + ":reference:" + str(n), good, {"expected": w, "observed": a})
    unknowns = parser.get("unknowns", [])
    codes = {u.get("reason") for u in unknowns}
    wanted_codes = set(gold["unknown_codes"])
    allowed = wanted_codes | ({"no_supported_units"} if not expected else set())
    review.check(cid + ":unknown_reason_codes", wanted_codes <= codes <= allowed, {"expected_required": sorted(wanted_codes), "observed": sorted(codes)})
    for n, u in enumerate(unknowns):
        eid = u.get("excerpt_id")
        review.check(cid + ":unknown_span:" + str(n), eid in src and span_ok(u.get("span"), src[eid]) and
                     (u.get("owner_id") is None or u.get("owner_id") in actual))
    for w in wanted:
        if w["status"] != "resolved":
            review.check(cid + ":unknown_reference_owner:" + w["owner_id"], any(
                u.get("owner_id") == w["owner_id"] and u.get("reason") == w["status"] for u in unknowns))
    duplicate_labels = {(u["id"].split("::", 1)[0], u["label"]) for u in expected.values() if sum(
        (v["id"].split("::", 1)[0], v["label"]) == (u["id"].split("::", 1)[0], u["label"])
        for v in expected.values()) > 1}
    for uid, u in expected.items():
        if (uid.split("::", 1)[0], u["label"]) in duplicate_labels:
            review.check(cid + ":duplicate_owner:" + uid, any(x.get("reason") == "ambiguous_scope" and x.get("owner_id") == uid for x in unknowns))
    review.check(cid + ":cycles", parser.get("cycles") == gold["cycle_components"], {"expected": gold["cycle_components"], "observed": parser.get("cycles")})
    return src, graph


def audit_pack(review, cid, arm_name, phase, output, seeds, inp, gold, src, parser):
    effective, chosen, dropped, text, spans, missing = expected_pack(seeds, phase == "closure", inp, gold, src)
    name = cid + ":" + arm_name + ":" + phase
    review.check(name + ":same_effective_seeds", output.get("observed_effective_seed_ids") == effective)
    review.check(name + ":atomic_gold_selection", set(output.get("selected_unit_ids", [])) == chosen and len(output.get("selected_unit_ids", [])) == len(chosen), {"expected": sorted(chosen), "observed": output.get("selected_unit_ids")})
    review.check(name + ":literal_rendering", output.get("context") == text and output.get("context_utf8_bytes") == len(text.encode("utf-8")) and output.get("context_codepoints") == len(text))
    actual_spans = output.get("spans", [])
    review.check(name + ":merged_span_count", len(actual_spans) == len(spans))
    for n, (a, (eid, lo, hi, ids)) in enumerate(zip(actual_spans, spans)):
        review.check(name + ":source_span:" + str(n), a.get("excerpt_id") == eid and span_ok(a, src[eid]) and [a.get("start"), a.get("end")] == [lo, hi] and a.get("unit_ids") == ids)
    review.check(name + ":budget", len(chosen) <= inp["budget"]["max_nodes"] and len(text.encode("utf-8")) <= inp["budget"]["max_utf8_bytes"])
    relevant_unknown = any(u.get("owner_id") is None or u.get("owner_id") in chosen for u in parser.get("unknowns", []))
    must_unknown = bool(relevant_unknown or dropped or missing or not effective)
    review.check(name + ":conservative_unknown", output.get("unknown") is must_unknown)
    review.check(name + ":semantic_boundary", output.get("global_evidence_completeness") == "UNKNOWN" and output.get("entailment_or_insufficiency_decision") == "NOT_EVALUATED" and output.get("retrieval_miss_implies_insufficient_evidence") is False)
    return chosen, missing


def audit(inputs, gold, raw):
    review = Review()
    imap = {c["id"]: c for c in inputs["cases"]}
    gmap = {c["id"]: c for c in gold["cases"]}
    records = raw.get("cases", [])
    review.check("exact24_saved_case_identities", len(imap) == len(gmap) == len(records) == 24 and list(imap) == [c.get("id") for c in records])
    repair_rows = []
    extraction_sets = {name: {"gold": set(), "actual": set()} for name in ("units", "dependencies", "references")}
    stats = {a: dict(queries=0, baseline_missing_dependencies=0, closure_missing_dependencies=0, retained_seed_repairs=0) for a in ["actual_native", "lexical", "positional"]}
    for record in records:
        cid = record.get("id")
        if cid not in imap or cid not in gmap:
            review.check("unexpected_case", False, cid)
            continue
        inp, expected = imap[cid], gmap[cid]
        parser = record.get("parser", {})
        src, graph = audit_parser(review, inp, expected, parser)
        extraction_sets["units"]["gold"].update((cid, u["id"], *u["whole"]) for u in expected["units"])
        extraction_sets["units"]["actual"].update((cid, uid, u.get("start"), u.get("end")) for uid, u in parser.get("units", {}).items())
        extraction_sets["dependencies"]["gold"].update((cid, a, b) for a, b in expected["edges"])
        extraction_sets["dependencies"]["actual"].update((cid, uid, dep) for uid, u in parser.get("units", {}).items() for dep in u.get("requires", []))
        extraction_sets["references"]["gold"].update((cid, w["owner_id"], *w["trigger"], *w["target"], w["resolved_target_id"], w["status"]) for w in expected["references"])
        extraction_sets["references"]["actual"].update((cid, w.get("owner_id"), w.get("trigger_span", {}).get("start"), w.get("trigger_span", {}).get("end"), w.get("target_span", {}).get("start"), w.get("target_span", {}).get("end"), w.get("resolved_target_id"), w.get("status")) for w in parser.get("references", []))
        arms = record.get("arms", {})
        if not expected["units"]:
            review.check(cid + ":no_native_without_units", not arms and record.get("native") is None)
            out = record.get("closure", {})
            review.check(cid + ":empty_structure_unknown", out.get("unknown") is True and out.get("global_evidence_completeness") == "UNKNOWN" and out.get("entailment_or_insufficiency_decision") == "NOT_EVALUATED")
            continue
        review.check(cid + ":three_matched_arms", set(arms) == {"actual_native", "lexical", "positional"})
        native = record.get("native")
        review.check(cid + ":actual_native_receipt", isinstance(native, dict) and isinstance(native.get("ids"), list) and isinstance(native.get("raw_hits"), list))
        if isinstance(native, dict):
            unit_order = list(parser.get("units", {}))
            indexes = native.get("ids", [])
            expected_ids = [unit_order[i] for i in indexes if type(i) is int and 0 <= i < len(unit_order)]
            review.check(cid + ":actual_native_ranking_identity", len(expected_ids) == len(indexes) and
                         arms.get("actual_native", {}).get("observed_seed_ids") == expected_ids)
        for arm_name, arm in arms.items():
            if arm_name not in stats:
                continue
            seeds = arm.get("observed_seed_ids", [])
            review.check(cid + ":" + arm_name + ":valid_observed_seeds", all(s in graph for s in seeds))
            effective = list(dict.fromkeys(seeds))[:inp["seed_limit"]]
            review.check(cid + ":" + arm_name + ":effective_seed_identity", arm.get("effective_seed_ids") == effective)
            if arm_name == "actual_native":
                review.check(cid + ":actual_native_origin", arm.get("seed_origin") == "ACTUAL_NATIVE_OBSERVATION")
            if not all(s in graph for s in seeds):
                continue
            baseline, bm = audit_pack(review, cid, arm_name, "baseline", arm.get("baseline", {}), seeds, inp, expected, src, parser)
            closed, cm = audit_pack(review, cid, arm_name, "closure", arm.get("closure", {}), seeds, inp, expected, src, parser)
            stats[arm_name]["queries"] += 1
            stats[arm_name]["baseline_missing_dependencies"] += sum(len(x) for x in bm.values())
            stats[arm_name]["closure_missing_dependencies"] += sum(len(x) for x in cm.values())
            for seed in effective:
                repaired = seed in baseline and seed in closed and bool(bm.get(seed)) and not cm.get(seed)
                if repaired:
                    stats[arm_name]["retained_seed_repairs"] += 1
                    if arm_name == "actual_native":
                        repair_rows.append(dict(case_id=cid, seed=seed, newly_retained_dependencies=sorted((closure(seed, graph) - baseline) & closed)))
    review.check("nonempty_actual_native_retained_seed_repair", len(repair_rows) >= 1, repair_rows)
    review.check("raw_worker_errors_empty", raw.get("errors") == [])
    structural_metrics = {}
    for name, sets in extraction_sets.items():
        wanted, actual = sets["gold"], sets["actual"]
        tp, fp, fn = len(wanted & actual), len(actual - wanted), len(wanted - actual)
        structural_metrics[name] = dict(true_positive=tp, false_positive=fp, false_negative=fn,
            precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
            scope="Exact manual authored structural identities/spans over all24cases, including failures; not semantic benchmark accuracy.")
    failures = [c for c in review.checks if not c["passed"]]
    return dict(schema_version=1, epoch=24, oracle_policy="independent-manual-raw-structure-v1",
                engineering_accepted=not failures, benchmark_accepted=False, champion_promoted=False,
                official_SOTA_verified=False, accuracy=None, Brier=None, NLL=None, proper_scores=None,
                scope="Newly authored narrow-grammar source-structure engineering only; no benchmark or synthetic-generalization claim.",
                fixture_count=len(imap), structural_outcomes=stats, actual_native_retained_seed_repairs=repair_rows,
                structural_extraction=structural_metrics,
                check_count=len(review.checks), failure_count=len(failures), failures=failures, checks=review.checks)


def quantiles(values):
    xs = sorted(values)
    def one(p):
        if not xs:
            return None
        position = (len(xs)-1)*p
        lo = int(position)
        hi = min(lo+1, len(xs)-1)
        return xs[lo] + (xs[hi]-xs[lo])*(position-lo)
    return dict(n=len(xs), p50=one(.5), p95=one(.95), method="Linear interpolation at (n-1)*p")


def runtime_review(raw_path, raw, args):
    """Saved receipts plus current /proc, never a second candidate execution."""
    r = Review()
    run = Path(raw_path).resolve().parent
    study = run.parent.parent
    project = study.parents[2]
    plan_path = study / "plan.json"
    plan = json.loads(plan_path.read_text())
    execute = json.loads((study / "execution.json").read_text())
    attempt = json.loads((run / "attempt.json").read_text())
    native = json.loads((run / "native-result.json").read_text())
    admission = json.loads((study / "NATIVE_ADMISSION.json").read_text())
    freeze_path = project / plan["source_freeze_path"]
    freeze = json.loads(freeze_path.read_text())
    seal = freeze["independent_scorer_seal"]
    r.check("runtime:plan_raw_binding", digest(plan_path) == raw.get("plan_sha256") == admission.get("plan_sha256"))
    r.check("runtime:source_freeze_binding", digest(freeze_path) == plan["source_freeze_sha256"] == admission.get("source_freeze_sha256"))
    r.check("runtime:remote_source_admission", admission.get("verified_actual_remote_readback") is True and admission.get("epoch") == 24)
    pin_failures = []
    for pin in plan["pins"]:
        f = project / pin["path"]
        if not f.is_file() or f.stat().st_size != pin["bytes"] or digest(f) != pin["sha256"]:
            pin_failures.append(pin["path"])
    r.check("runtime:frozen_source_pins_unchanged", not pin_failures, pin_failures)
    for key, path in [("oracle", __file__), ("manual_gold", args.gold), ("inputs", args.inputs)]:
        pin = seal[key]
        f = Path(path)
        r.check("runtime:sealed_" + key, f.stat().st_size == pin["bytes"] and digest(f) == pin["sha256"])
    r.check("runtime:exact_input_binding", digest(args.inputs) == raw.get("fixtures_sha256") == plan["fixtures_sha256"])
    r.check("runtime:one_completed_attempt", execute.get("worker_attempts_reserved") == 1 and execute.get("verified_worker_starts") == 1 and execute.get("uncertain_start") is False and execute.get("exit_code") == 0 and execute.get("status") == "WORKER_COMPLETED")
    r.check("runtime:worker_start_identity", attempt.get("verified_process_start") is True and attempt.get("uncertain_start") is False and attempt.get("pid") == raw.get("worker_pid") == execute.get("Popen_returned_pid") and attempt.get("pgid") == raw.get("worker_pgid") == raw.get("worker_pid"))
    r.check("runtime:bounded_cpu_wall", execute.get("CPU_affinity") == raw.get("resources", {}).get("CPU_affinity") == [0, 1] and
            0 <= execute.get("wall_seconds_including_init_cleanup", 601) <= 600 and
            0 <= raw.get("wall_seconds_including_initialization_cleanup", 601) <= 600)
    r.check("runtime:cleanup_receipts", execute.get("owned_live_processes_closed") is True and execute.get("owned_live_group_members") == [] and execute.get("cleanup_errors") == [] and execute.get("allowed_further_epoch24_workers") == 0)
    r.check("runtime:raw_receipt_identity", execute.get("raw_sha256") == digest(raw_path) and execute.get("raw_bytes") == Path(raw_path).stat().st_size)
    live_group = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == raw["worker_pgid"] and fields[0] not in ("Z", "X"):
                    live_group.append(int(proc.name))
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
    r.check("runtime:physical_owned_group_closed", not live_group, live_group)
    r.check("runtime:native_helper_closed", native.get("helper_exited") is True and native.get("helper_exit_code") == 0 and not (Path("/proc") / str(native.get("helper_pid"))).exists())
    r.check("runtime:native_binary_identity", native.get("native") is True and native.get("native_binary_sha256") == "ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e")
    counters = raw.get("counters", {})
    native_count = sum(bool(c.get("native")) for c in raw.get("cases", []))
    r.check("runtime:actual_native_BGE_counts", counters.get("native_helper_starts") == 1 and counters.get("native_queries_completed") == native_count == len(native.get("cases", [])) and 1 <= native_count <= 24 and
            counters.get("BGE_initializations_attempted") == counters.get("BGE_initializations_completed") == 1 and counters.get("BGE_forwards_completed", 0) > 0 and counters.get("parser_cases_completed") == 24)
    r.check("runtime:prohibited_operations_zero", all(counters.get(k) == 0 for k in ["NLI_forwards", "fits", "paid_calls", "GPU_calls", "Python_network_operations_attempted"]) and
            all(execute.get(k) == 0 for k in ["confirmation_calls", "paid_calls", "GPU_calls"]))
    r.check("runtime:benchmark_roles_empty", raw.get("roles_used") == dict.fromkeys(("train", "dev", "calibration", "confirmation"), []) and raw.get("accuracy") is None and raw.get("proper_scores") is None and raw.get("benchmark_results") is None)
    receipts = {n: dict(path=str(p), sha256=digest(p), bytes=p.stat().st_size) for n, p in [
        ("plan", plan_path), ("execution", study / "execution.json"), ("attempt", run / "attempt.json"),
        ("native_result", run / "native-result.json"), ("admission", study / "NATIVE_ADMISSION.json"), ("source_freeze", freeze_path)]}
    return r.checks, receipts, execute


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    inputs, gold, raw = (json.loads(Path(p).read_text()) for p in [args.inputs, args.gold, args.raw])
    result = audit(inputs, gold, raw)
    runtime_checks, runtime_receipts, execute = runtime_review(args.raw, raw, args)
    result["checks"].extend(runtime_checks)
    result["failures"] = [c for c in result["checks"] if not c["passed"]]
    result["check_count"] = len(result["checks"])
    result["failure_count"] = len(result["failures"])
    result["engineering_qualified"] = not result["failures"]
    result["engineering_accepted"] = result["engineering_qualified"]
    result["latency_seconds"] = {"parser_extraction": quantiles([c["parser_seconds"] for c in raw["cases"]]),
        "case_components": quantiles([c["latency_seconds"] for c in raw["cases"] if "latency_seconds" in c]),
        "case_with_amortized_encoder_initialization": quantiles([c["latency_with_amortized_encoder_initialization_seconds"] for c in raw["cases"] if "latency_with_amortized_encoder_initialization_seconds" in c])}
    result["resources"] = dict(worker_observed=raw.get("resources"), outer_execution=execute,
                               scope="Reported observations retain errors/failures; high-water memory is not simultaneous aggregate RSS.")
    result["runtime_receipts"] = runtime_receipts
    result["source_receipts"] = {k: dict(path=str(Path(p).resolve()), sha256=digest(p), bytes=Path(p).stat().st_size)
                                 for k, p in [("inputs", args.inputs), ("manual_gold", args.gold), ("raw", args.raw), ("oracle", __file__)]}
    with Path(args.output).open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: result[k] for k in ["engineering_accepted", "fixture_count", "check_count", "failure_count", "structural_outcomes"]}))


if __name__ == "__main__":
    main()
