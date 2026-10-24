"""Independent source-scope engineering oracle. No candidate imports or inference."""
from __future__ import annotations
import argparse, hashlib, json, math, re
from pathlib import Path
from datetime import datetime, timezone

CONTRACT_SHA256 = "e493ce94cb47022c46669750643b87ef5c79b1da840bb2f2e6741e0cc330a502"
FIXTURES_SHA256 = "d226a1cc3a2a33a730da91d803e9b954f918dd4d12c2eba3bcef7eb2876f99b3"
ARMS = ("actual_native", "lexical", "positional")
GHOST = "__engineering_unknown_seed__"
ORIGIN = "FORCED_SCOPE_GUARD_ONLY_NOT_NATIVE"
INVALID_IDS = {
 "invalid-missing-parent", "invalid-cycle", "invalid-cross-excerpt-edge",
 "invalid-out-of-range", "invalid-forged-unit-text", "invalid-duplicate-unit-id",
 "invalid-document-identity", "invalid-forged-excerpt-hash",
}
NUMBER = re.compile(r"(?<!\w)[+\-−]?\d+(?:[.,]\d+)*(?:\s*%|\s*(?:basis points|million|billion|dollars))?")
sha = lambda b: hashlib.sha256(b).hexdigest()

def graph(case):
    """Validate the entire supplied graph, independently using Kahn's cycle test."""
    errors, ex, nodes = [], {}, {}
    if not isinstance(case, dict):
        return ["case_not_object"], ex, nodes
    for e in case.get("excerpts", []):
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not isinstance(e.get("text"), str):
            errors.append("bad_excerpt"); continue
        if e["id"] in ex: errors.append("duplicate_excerpt")
        ex[e["id"]] = e
        if "sha256" in e and e["sha256"] != sha(e["text"].encode()):
            errors.append("forged_excerpt_hash")
        if "document_id" in case and "document_id" in e and e["document_id"] != case["document_id"]:
            errors.append("excerpt_document_mismatch")
    for n in case.get("units", []):
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            errors.append("bad_unit"); continue
        if n["id"] in nodes: errors.append("duplicate_unit")
        nodes[n["id"]] = n
        e = ex.get(n.get("excerpt_id"))
        start, end = n.get("start"), n.get("end")
        if e is None or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(e["text"]):
            errors.append("bad_source_range"); continue
        if "text" in n and n["text"] != e["text"][start:end]:
            errors.append("forged_unit_text")
        if "document_id" in n:
            allowed = e.get("document_id", case.get("document_id"))
            if allowed is None or n["document_id"] != allowed:
                errors.append("unit_document_mismatch")
        deps = n.get("requires")
        if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps) or len(deps) != len(set(deps)):
            errors.append("bad_requires")
    for n in nodes.values():
        deps = n.get("requires")
        if not isinstance(deps, list): continue
        for dep in deps:
            if dep not in nodes: errors.append("missing_dependency")
            elif nodes[dep].get("excerpt_id") != n.get("excerpt_id"):
                errors.append("cross_excerpt_dependency")
    budget = case.get("budget")
    if not isinstance(budget, dict) or set(budget) != {"max_utf8_bytes", "max_nodes"}:
        errors.append("bad_budget")
    elif any(type(budget[k]) is not int or budget[k] < 0 for k in budget):
        errors.append("bad_budget")
    if type(case.get("seed_limit")) is not int or case["seed_limit"] < 0:
        errors.append("bad_seed_limit")
    if "char_budget" in case: errors.append("disallowed_char_budget")
    if not isinstance(case.get("query"), str) or len(nodes) > 256:
        errors.append("bad_query_or_graph_size")
    if not errors:
        degree = {n: len(v["requires"]) for n, v in nodes.items()}
        children = {n: [] for n in nodes}
        for n, v in nodes.items():
            for p in v["requires"]: children[p].append(n)
        ready = [n for n, d in degree.items() if d == 0]; count = 0
        while ready:
            n = ready.pop(); count += 1
            for child in children[n]:
                degree[child] -= 1
                if degree[child] == 0: ready.append(child)
        if count != len(nodes): errors.append("cycle")
    return sorted(set(errors)), ex, nodes

def descendants_required(ids, nodes):
    out, pending = set(ids), list(ids)
    while pending:
        n = pending.pop()
        for parent in nodes[n]["requires"]:
            if parent not in out: out.add(parent); pending.append(parent)
    return out

def exact_spans(ids, ex, nodes):
    """Independent sweep of source intervals; touching intervals join."""
    result = []
    for eid, e in ex.items():
        intervals = sorted((nodes[n]["start"], nodes[n]["end"]) for n in ids if nodes[n]["excerpt_id"] == eid)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]: merged[-1][1] = max(end, merged[-1][1])
            else: merged.append([start, end])
        for start, end in merged:
            result.append({"excerpt_id": eid, "start": start, "end": end, "text": e["text"][start:end]})
    return result

def rendered(spans):
    return "\n".join(s["text"] for s in spans)

def semantic_guard(out, violations):
    if out.get("global_evidence_completeness") != "UNKNOWN":
        violations.append("global_evidence_completeness_not_UNKNOWN")
    for field in ("semantic_decision", "semanticdecision", "entailment_or_insufficiency_decision"):
        if field in out and out[field] != "NOT_EVALUATED":
            violations.append(field + "_not_NOT_EVALUATED")
    if out.get("retrieval_miss_implies_insufficient_evidence", False) is not False:
        violations.append("retrieval_miss_implies_insufficient_evidence")

def check_pack(case, seeds, out, closure):
    violations = []
    errors, ex, nodes = graph(case)
    if not isinstance(out, dict):
        return {"violations": ["pack_output_not_object"], "missing_dependencies": [], "retained_seeds": [], "utf8_bytes": 0}
    semantic_guard(out, violations)
    ids = out.get("selected_unit_ids")
    spans = out.get("spans")
    text = out.get("context")
    if not isinstance(ids, list) or not isinstance(spans, list) or not isinstance(text, str):
        return {"violations": violations + ["pack_shape"], "missing_dependencies": [], "retained_seeds": [], "utf8_bytes": 0}
    invalid_seed = any(not isinstance(n, str) or n not in nodes for n in seeds)
    duplicate_seed = len(seeds) != len(set(seeds))
    if errors or invalid_seed:
        if ids or spans or text: violations.append("invalid_input_not_empty_fail_closed")
        if out.get("unknown") is not True: violations.append("invalid_input_not_unknown")
        if not out.get("errors"): violations.append("invalid_input_missing_error")
        if errors and out.get("status") != "INVALID_GRAPH_UNKNOWN": violations.append("bad_invalid_graph_status")
        return {"violations": violations, "missing_dependencies": [], "retained_seeds": [], "utf8_bytes": len(text.encode())}
    # Duplicate-seed guards may reject explicitly or normalize without duplication.
    if duplicate_seed and not ids and not spans and not text and out.get("errors"):
        if out.get("unknown") is not True: violations.append("duplicate_failure_not_unknown")
        return {"violations": violations, "missing_dependencies": [], "retained_seeds": [], "utf8_bytes": 0}
    seeds = list(dict.fromkeys(seeds))
    if len(ids) != len(set(ids)): violations.append("duplicate_selected_unit")
    if any(n not in nodes for n in ids):
        return {"violations": violations + ["fabricated_selected_unit"], "missing_dependencies": [], "retained_seeds": [], "utf8_bytes": len(text.encode())}
    chosen = set(ids); selected_seeds = chosen.intersection(seeds)
    justified = descendants_required(selected_seeds, nodes) if closure else set(selected_seeds)
    if not chosen.issubset(justified): violations.append("unjustified_or_orphan_selected_unit")
    required = descendants_required(chosen, nodes)
    missing = sorted(required - chosen)
    if closure and missing: violations.append("silent_dependency_omission")
    expected = exact_spans(chosen, ex, nodes)
    essential = []
    for span in spans:
        if not isinstance(span, dict) or any(k not in span for k in ("excerpt_id", "start", "end", "text")):
            violations.append("bad_span_shape"); continue
        essential.append({k: span[k] for k in ("excerpt_id", "start", "end", "text")})
        e = ex.get(span["excerpt_id"])
        if e is None: violations.append("cross_or_fabricated_source"); continue
        a, b = span["start"], span["end"]
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(e["text"]):
            violations.append("invalid_span_range"); continue
        if span["text"] != e["text"][a:b]: violations.append("rewritten_source_quote")
        if "source_sha256" in span and span["source_sha256"] != sha(e["text"].encode()):
            violations.append("source_hash_mismatch")
        if "quote_sha256" in span and span["quote_sha256"] != sha(span["text"].encode()):
            violations.append("quote_hash_mismatch")
        for field, val in (("source_byte_start", len(e["text"][:a].encode())), ("source_byte_end", len(e["text"][:b].encode()))):
            if field in span and span[field] != val: violations.append("source_byte_offset_mismatch")
    if essential != expected: violations.append("source_interval_union_mismatch")
    if text != rendered(expected): violations.append("rendered_context_mismatch")
    size = len(text.encode())
    if size > case["budget"]["max_utf8_bytes"]: violations.append("UTF8_budget_overflow")
    if len(chosen) > case["budget"]["max_nodes"]: violations.append("node_budget_overflow")
    retained = [n for n in seeds if n in chosen]
    dropped = [n for n in seeds if n not in chosen]
    if out.get("dropped_seed_ids") != dropped: violations.append("dropped_seed_trace_mismatch")
    incomplete = bool(missing or dropped or not seeds or not ids)
    if incomplete and out.get("unknown") is not True: violations.append("incomplete_not_unknown")
    if incomplete and out.get("status") != "INCOMPLETE_UNKNOWN": violations.append("bad_incomplete_status")
    if seeds and not ids:
        any_fit = False
        for n in seeds:
            component = descendants_required([n], nodes) if closure else {n}
            quote = rendered(exact_spans(component, ex, nodes))
            any_fit |= len(component) <= case["budget"]["max_nodes"] and len(quote.encode()) <= case["budget"]["max_utf8_bytes"]
        if any_fit: violations.append("empty_despite_fitting_observed_component")
    numeric = []
    for eid, e in ex.items():
        for m in NUMBER.finditer(e["text"]):
            kept = any(s["excerpt_id"] == eid and s["start"] <= m.start() and m.end() <= s["end"] for s in expected)
            numeric.append({"excerpt_id": eid, "start": m.start(), "end": m.end(), "literal": m.group(), "retained": kept})
    return {"violations": sorted(set(violations)), "missing_dependencies": missing, "retained_seeds": retained,
            "dropped_seeds": dropped, "utf8_bytes": size, "selected_nodes": len(chosen), "numeric_source_literals": numeric}

def lexical_ids(case):
    qt = set(re.findall(r"\w+", case["query"].casefold()))
    ex = {e["id"]: e["text"] for e in case["excerpts"]}
    scores = []
    for i, n in enumerate(case["units"]):
        nt = set(re.findall(r"\w+", ex[n["excerpt_id"]][n["start"]:n["end"]].casefold()))
        score = len(qt & nt) / max(1, len(qt | nt))
        scores.append((-score, i, n["id"]))
    return [x[2] for x in sorted(scores)]

def audit(fixtures, raw):
    failures, case_reports, case_latencies = [], [], []
    if raw.get("contract_sha256") != CONTRACT_SHA256: failures.append("raw_contract_pin")
    if raw.get("fixtures_sha256") != FIXTURES_SHA256: failures.append("raw_fixture_pin")
    if fixtures.get("contract_sha256") != CONTRACT_SHA256: failures.append("fixture_contract_pin")
    cases = fixtures.get("cases", [])
    if len(cases) != 25 or len({c["id"] for c in cases}) != 25: failures.append("fixture_identity_count")
    by = {c["id"]: c for c in cases}
    invalid = {c["id"] for c in cases if graph(c)[0]}
    if invalid != INVALID_IDS: failures.append("independent_graph_validation_partition")
    traces = raw.get("cases", [])
    if not isinstance(traces, list): return {"checks_passed": False, "failures": ["raw_cases_not_list"]}
    if len(traces) != 25 or {x.get("id") for x in traces} != set(by): failures.append("raw_case_identity_coverage")
    trace_by = {x.get("id"): x for x in traces}
    totals = {a: {"queries": 0, "baseline_missing_dependencies": 0, "closure_missing_dependencies": 0,
                  "corrected_nonempty_cases": 0, "baseline_retained_seeds": 0, "closure_retained_seeds": 0,
                  "effective_seed_count": 0, "baseline_UTF8_bytes": [], "closure_UTF8_bytes": []} for a in ARMS}
    for cid, case in by.items():
        trace = trace_by.get(cid, {})
        report = {"id": cid, "valid_graph": cid not in invalid, "arms": {}}
        if cid in invalid:
            if trace.get("native") is not None or trace.get("arms") not in ({}, None):
                failures.append(cid + ":invalid_graph_native_or_arms_executed")
            pack = trace.get("closure", trace.get("pack"))
            if pack is None and isinstance(trace.get("graph_validation"), dict):
                pack = trace["graph_validation"].get("closure")
            cr = check_pack(case, [], pack, True)
            failures.extend(cid + ":" + f for f in cr["violations"])
            report["invalid_graph_result"] = cr
            case_reports.append(report); continue
        if not isinstance(trace.get("native"), dict): failures.append(cid + ":native_receipt_absent")
        latency = trace.get("latency_seconds")
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
            failures.append(cid + ":invalid_actual_case_latency")
        else: case_latencies.append(float(latency))
        for arm in ARMS:
            ar = trace.get("arms", {}).get(arm, {})
            observed, effective = ar.get("observed_seed_ids"), ar.get("effective_seed_ids")
            unit_ids = [n["id"] for n in case["units"]]
            if not isinstance(observed, list) or not isinstance(effective, list):
                failures.append(cid + ":" + arm + ":seed_trace_shape"); continue
            if len(observed) != len(set(observed)) or any(n not in unit_ids for n in observed):
                failures.append(cid + ":" + arm + ":invalid_observed_ranking"); continue
            if arm == "actual_native" and len(observed) != min(max(1, case["seed_limit"]), len(unit_ids)):
                failures.append(cid + ":native_observed_count")
            if arm == "lexical" and observed != lexical_ids(case): failures.append(cid + ":lexical_origin_mismatch")
            if arm == "positional" and observed != unit_ids: failures.append(cid + ":positional_origin_mismatch")
            if effective != observed[:case["seed_limit"]]: failures.append(cid + ":" + arm + ":effective_seed_origin")
            baseline = check_pack(case, effective, ar.get("baseline"), False)
            closure = check_pack(case, effective, ar.get("closure"), True)
            for mode, cr in (("baseline", baseline), ("closure", closure)):
                failures.extend(cid + ":" + arm + ":" + mode + ":" + f for f in cr["violations"])
            t = totals[arm]; t["queries"] += 1
            t["baseline_missing_dependencies"] += len(baseline["missing_dependencies"])
            t["closure_missing_dependencies"] += len(closure["missing_dependencies"])
            t["effective_seed_count"] += len(effective)
            t["baseline_retained_seeds"] += len(baseline["retained_seeds"])
            t["closure_retained_seeds"] += len(closure["retained_seeds"])
            t["baseline_UTF8_bytes"].append(baseline["utf8_bytes"])
            t["closure_UTF8_bytes"].append(closure["utf8_bytes"])
            if baseline["missing_dependencies"] and not closure["missing_dependencies"] and closure["retained_seeds"]:
                t["corrected_nonempty_cases"] += 1
            report["arms"][arm] = {"observed_seed_ids": observed, "effective_seed_ids": effective,
                                   "baseline": baseline, "closure": closure}
        case_reports.append(report)
    expected_guards = {(c["id"], kind): seeds for c in cases if c["id"] not in invalid for kind, seeds in (
        ("unknown_seed", [GHOST]), ("duplicate_seed", [c["units"][0]["id"], c["units"][0]["id"]]), ("empty_seed", []))}
    guards = raw.get("forced_seed_checks", [])
    seen, guard_reports = set(), []
    for g in guards:
        key = (g.get("case_id"), g.get("kind"))
        if key in seen or key not in expected_guards:
            failures.append("unexpected_or_duplicate_forced_guard"); continue
        seen.add(key); seeds = expected_guards[key]
        if g.get("origin") != ORIGIN or g.get("seed_ids") != seeds:
            failures.append(str(key) + ":forced_guard_origin")
        outputs = {}
        for mode in ("baseline", "closure"):
            cr = check_pack(by[key[0]], seeds, g.get(mode), mode == "closure")
            failures.extend(str(key) + ":" + mode + ":" + f for f in cr["violations"])
            outputs[mode] = cr
        guard_reports.append({"case_id": key[0], "kind": key[1], "origin": ORIGIN, **outputs})
    if seen != set(expected_guards): failures.append("forced_guard_coverage")
    if totals["actual_native"]["queries"] != 17: failures.append("actual_native_query_coverage")
    if totals["actual_native"]["corrected_nonempty_cases"] < 1:
        failures.append("native_closure_no_demonstrated_nonempty_scope_repair")
    def percentile(values, q):
        if not values: return None
        a = sorted(values); x = (len(a)-1)*q; lo = math.floor(x); hi = math.ceil(x)
        return a[lo] + (a[hi]-a[lo])*(x-lo)
    latency_report = {"n": len(case_latencies), "p50_seconds": percentile(case_latencies, 0.5), "p95_seconds": percentile(case_latencies, 0.95), "scope": "Saved actual valid-case worker latency; no additional model or native calls by oracle."}
    return {"checks_passed": not failures, "accepted": not failures, "failures": failures, "case_reports": case_reports, "latency": latency_report,
            "forced_guard_reports": guard_reports, "engineering_metrics": totals, "valid_retrieval_cases": 17,
            "invalid_graph_cases": 8, "forced_seed_guard_records": len(seen), "benchmark_accuracy": None,
            "proper_scores": None, "benchmark_accepted": False, "champion_promoted": False, "submission_allowed": False,
            "used_confirmation_identities": [], "scope": "Author-supplied source graph engineering only; no legal parsing, NLI, benchmark generalization, official rank, or semantic insufficiency proof."}

def self_check(fixtures):
    """Falsification guards for the oracle itself; never imports the candidate."""
    import copy
    cases = {c["id"]: c for c in fixtures["cases"]}
    tests = []
    def record(name, ok):
        tests.append({"id": name, "passed": bool(ok)})
        if not ok: raise AssertionError("Oracle self-check failed: " + name)
    record("fixture_partition_17_valid_8_invalid", {c["id"] for c in cases.values() if graph(c)[0]} == INVALID_IDS)
    c = cases["consent-header"]
    unit = {n["id"]: n for n in c["units"]}
    source = c["excerpts"][0]["text"]
    spans = [{"excerpt_id": "source", "start": unit[n]["start"], "end": unit[n]["end"],
              "text": source[unit[n]["start"]:unit[n]["end"]]} for n in ("rule", "consent")]
    good = {"status": "ANNOTATED_SCOPE_COMPLETE", "selected_unit_ids": ["rule", "consent"],
            "spans": spans, "context": "\n".join(x["text"] for x in spans), "dropped_seed_ids": [],
            "errors": [], "unknown": False, "global_evidence_completeness": "UNKNOWN",
            "semantic_decision": "NOT_EVALUATED"}
    record("accept_exact_complete_source", not check_pack(c, ["consent"], good, True)["violations"])
    bad = copy.deepcopy(good); bad["selected_unit_ids"] = ["consent"]; bad["spans"] = [spans[1]]; bad["context"] = spans[1]["text"]
    record("reject_silent_dependency_omission", "silent_dependency_omission" in check_pack(c, ["consent"], bad, True)["violations"])
    record("reject_incomplete_false_claim", "incomplete_not_unknown" in check_pack(c, ["consent"], bad, False)["violations"])
    bad = copy.deepcopy(good); bad["spans"][1]["text"] += " invented"
    record("reject_rewritten_source_quote", "rewritten_source_quote" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["selected_unit_ids"].append("not-a-source-unit")
    record("reject_fabricated_unit", "fabricated_selected_unit" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["selected_unit_ids"].append("marketing")
    record("reject_unjustified_unit", "unjustified_or_orphan_selected_unit" in check_pack(c, ["consent"], bad, True)["violations"])
    low = copy.deepcopy(c); low["budget"]["max_utf8_bytes"] = 1
    record("reject_byte_budget_violation", "UTF8_budget_overflow" in check_pack(low, ["consent"], good, True)["violations"])
    low = copy.deepcopy(c); low["budget"]["max_nodes"] = 1
    record("reject_node_budget_violation", "node_budget_overflow" in check_pack(low, ["consent"], good, True)["violations"])
    bad = copy.deepcopy(good); bad["global_evidence_completeness"] = "COMPLETE"
    record("reject_global_evidence_claim", "global_evidence_completeness_not_UNKNOWN" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["semantic_decision"] = "INSUFFICIENT_EVIDENCE"
    record("reject_semantic_insufficiency_claim", "semantic_decision_not_NOT_EVALUATED" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["entailment_or_insufficiency_decision"] = "INSUFFICIENT_EVIDENCE"
    record("reject_actual_candidate_semantic_claim", "entailment_or_insufficiency_decision_not_NOT_EVALUATED" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["retrieval_miss_implies_insufficient_evidence"] = True
    record("reject_retrieval_miss_proves_insufficiency", "retrieval_miss_implies_insufficient_evidence" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["context"] = "A rewritten summary."
    record("reject_rendered_summary", "rendered_context_mismatch" in check_pack(c, ["consent"], bad, True)["violations"])
    bad = copy.deepcopy(good); bad["spans"][0]["excerpt_id"] = "remote-source"
    record("reject_cross_source_span", "cross_or_fabricated_source" in check_pack(c, ["consent"], bad, True)["violations"])
    empty = {"status": "INCOMPLETE_UNKNOWN", "selected_unit_ids": [], "spans": [], "context": "",
             "dropped_seed_ids": ["consent"], "errors": [], "unknown": True,
             "global_evidence_completeness": "UNKNOWN", "semantic_decision": "NOT_EVALUATED"}
    record("reject_empty_when_component_fits", "empty_despite_fitting_observed_component" in check_pack(c, ["consent"], empty, True)["violations"])
    empty["dropped_seed_ids"] = []
    record("accept_empty_unknown_guard", not check_pack(c, [], empty, True)["violations"])
    invalid = copy.deepcopy(empty); invalid["status"] = "INVALID_GRAPH_UNKNOWN"; invalid["errors"] = ["missing_dependency"]
    record("accept_explicit_invalid_graph_guard", not check_pack(cases["invalid-missing-parent"], [], invalid, True)["violations"])
    invalid["context"] = "fabricated"
    record("reject_nonempty_invalid_graph", "invalid_input_not_empty_fail_closed" in check_pack(cases["invalid-missing-parent"], [], invalid, True)["violations"])
    ex, nodes = graph(cases["touching-intervals"])[1:]
    expected = [{"excerpt_id": "source", "start": 0, "end": len(ex["source"]["text"]), "text": ex["source"]["text"]}]
    record("touching_source_intervals_merge_once", exact_spans({"prefix", "condition"}, ex, nodes) == expected)
    ex, nodes = graph(cases["overlap-source-union"])[1:]
    expected = [{"excerpt_id": "source", "start": 0, "end": len("Amount: $5 million."), "text": "Amount: $5 million."}]
    record("overlapping_source_intervals_merge_once", exact_spans({"amount", "number"}, ex, nodes) == expected)
    ex, nodes = graph(cases["utf8-exact-fit"])[1:]
    text = rendered(exact_spans({"accent-rule", "cafe"}, ex, nodes))
    record("UTF8_bytes_are_not_character_budget", len(text.encode()) == cases["utf8-exact-fit"]["budget"]["max_utf8_bytes"] and len(text.encode()) > len(text))
    return {"checks_passed": all(t["passed"] for t in tests), "tests": tests,
            "test_count": len(tests), "candidate_imports": 0, "native_model_tokenizer_gold_calls": 0,
            "scope": "Independent oracle falsification checks only; no candidate or benchmark score."}

def checked_bytes(path):
    path = Path(path)
    if path.resolve() != path or path.is_symlink() or not path.is_file(): raise ValueError("Unsafe source path")
    return path.read_bytes()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fixtures", type=Path, required=True)
    p.add_argument("--raw", type=Path)
    p.add_argument("--expected-raw-sha256")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    fb = checked_bytes(args.fixtures)
    if args.self_check:
        if sha(fb) != FIXTURES_SHA256: raise ValueError("Frozen fixture hash mismatch")
        result = self_check(json.loads(fb))
        result.update({"schema_version": 1, "epoch": 23, "oracle_sha256": sha(Path(__file__).read_bytes()), "fixtures_sha256": sha(fb)})
        with args.out.open("xb") as f: f.write((json.dumps(result, sort_keys=True, indent=2)+"\n").encode())
        print(json.dumps({"checks_passed": result["checks_passed"], "test_count": result["test_count"]})); return
    if args.raw is None or args.expected_raw_sha256 is None: p.error("raw and expected-raw-sha256 required outside self-check")
    rb = checked_bytes(args.raw)
    if sha(fb) != FIXTURES_SHA256 or sha(rb) != args.expected_raw_sha256:
        raise ValueError("Frozen fixture or sealed raw hash mismatch")
    result = audit(json.loads(fb), json.loads(rb))
    result.update({"schema_version": 1, "epoch": 23, "at": datetime.now(timezone.utc).isoformat(),
                   "status": "ACCEPTED_ENGINEERING_SCOPE_QUALIFICATION" if result.get("accepted") else "REJECTED_ENGINEERING_SCOPE_QUALIFICATION",
                   "fixtures": {"path": str(args.fixtures), "bytes": len(fb), "sha256": sha(fb)},
                   "raw": {"path": str(args.raw), "bytes": len(rb), "sha256": sha(rb)},
                   "oracle_sha256": sha(Path(__file__).read_bytes()), "contract_sha256": CONTRACT_SHA256,
                   "native_model_tokenizer_gold_calls_by_oracle": 0})
    with args.out.open("xb") as f:
        f.write((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"],
                      "accepted": result.get("accepted", False), "failure_count": len(result.get("failures", []))}))

if __name__ == "__main__": main()
