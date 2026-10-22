"""Independent saved-output/vector/logit audit; never loads an ONNX session.

Prepared after failed first attempt, before auditor inspection of any successful
epoch3 predictions. Tokenizers only inspect saved text. No native/model calls.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
import numpy as np
from tokenizers import Tokenizer

HERE = Path(__file__).resolve().parent
OUTER = HERE.parents[1]
PROJECT = OUTER / "epoch3/project"
SOURCE = PROJECT / "experiments/sota-2026-10-22"
sys.path.insert(0, str(OUTER / "audit"))
from verify_epoch_v2 import proper_scores, paired_bootstrap_interval


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def obj(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def digest(x): return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
def literal(x): return json.dumps(x, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def model_tokenizer(p):
    t = Tokenizer.from_file(str(p)); t.no_padding(); t.no_truncation(); return t


def softmax(x):
    x = np.asarray(x, dtype=np.float64); e = np.exp(x - x.max(axis=-1, keepdims=True)); return e / e.sum(axis=-1, keepdims=True)


def close(a, b, tol=1e-10):
    assert math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol), (a, b)


def lexical(chunks, hypothesis, k):
    q = set(re.findall(r"\w+", hypothesis.casefold()))
    vals = []
    for i, text in enumerate(chunks):
        words = set(re.findall(r"\w+", text.casefold()))
        vals.append((-(len(q & words) / max(1, len(q | words))), i))
    return [i for _, i in sorted(vals)[:k]]


def span_overlap(a, b): return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--study", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); assert not args.out.exists()
    plan = obj(args.plan)
    for pin in plan["pins"]: assert sha(PROJECT / pin["path"]) == pin["sha256"], pin["path"]
    r = args.study / "runs/development"
    actual, wire, server = [rows(r / f) for f in ("records.jsonl", "wire.jsonl", "server-audit.jsonl")]
    source = rows(PROJECT / plan["datasets"]["development"])
    attempt, runtime, collect, cleanup = [obj(r / f) for f in ("attempt.json", "runtime.json", "collection.json", "cleanup.json")]
    assert attempt["status"] == collect["status"] == "COMPLETE" and attempt["exit_code"] == 0
    assert len(actual) == len(wire) == len(server) == len(source) == collect["expected"] == collect["n"] == 24
    assert sha(r / "records.jsonl") == collect["records_sha256"] and sha(r / "wire.jsonl") == collect["wire_sha256"]
    for k, v in plan["expected_native_receipt"].items(): assert runtime["receipt"][k] == v
    assert cleanup["engine_close_called"] and cleanup["completed"] == len(actual) and cleanup["native_child_pids_absent"]
    pids = [obj(r / "process.json")["pid"], *runtime["native_child_pids"]]
    assert not any((Path("/proc") / str(p)).exists() for p in pids)
    bge = model_tokenizer(PROJECT / "models/bge-small-en-v1.5/tokenizer.json")
    nli = model_tokenizer(PROJECT / "models/nli/tokenizer.json")
    id2label = {int(k): v.lower() for k, v in obj(PROJECT / "models/nli/config.json")["id2label"].items()}
    assert id2label == {0: "contradiction", 1: "entailment", 2: "neutral"}
    docs = {d["id"]: d for d in obj(SOURCE / "legal-transfer/epoch3/sources/original-train.json")["documents"]}
    config = obj(SOURCE / "candidate/epoch3/config.json")
    spec = importlib.util.spec_from_file_location("independent_epoch3_scoring", SOURCE / "benchmark/sources/jevbench_scoring.py")
    scorer = importlib.util.module_from_spec(spec); spec.loader.exec_module(scorer)
    armkeys = {"ruvector_top2": None, "same_nli_lexical_top2": "lexical_top2", "same_nli_positional_first2": "positional_first2", "native104_on_ruvector_evidence": "baseline"}
    scored = {name: [] for name in armkeys}; rowproofs = []; logits_by_pair = {}; max_repeat_difference = 0.
    embed_texts = cached_vectors = nli_pairs = 0
    for expected, rec, pair, event in zip(source, actual, wire, server):
        assert rec["id"] == pair["id"] == expected["id"]
        assert rec["evaluation"] == expected["evaluation"] and digest(rec["input"]) == expected["input_sha256"]
        assert json.loads(pair["request"]) == rec["input"] and set(json.loads(pair["request"])) == {"state", "questions"}
        assert pair["status"] == event["status"] == 200 and event["ok"]
        for side in ("request", "response"):
            h = hashlib.sha256(pair[side].encode()).hexdigest(); assert h == pair[side + "_sha256"] == event[side + "_sha256"]
        response = rec["response"]; assert json.loads(pair["response"]) == response
        usage = response["usage"]; assert usage["native_requests"] == event["usage"]["native_requests"] == usage["native_core_searches"] == 1
        assert usage["nli_pairs_all_arms"] == 6 and usage["paid_calls"] == 0
        assert 0 <= rec["elapsed_s"] <= plan["limits"]["seconds_per_decision"]
        state = rec["input"]["state"]; hyp = rec["input"]["questions"]["decision"]["criteria"]["Yes"]
        diag = response["diagnostics"]["decision"]
        assert diag["hypothesis_sha256"] == hashlib.sha256(hyp.encode()).hexdigest()
        offsets = bge.encode(state, add_special_tokens=False).offsets
        spans = []
        for start in range(0, len(offsets), config["chunk_tokens"] - config["overlap_tokens"]):
            end = min(start + config["chunk_tokens"], len(offsets)); spans.append([offsets[start][0], offsets[end-1][1]])
            if end == len(offsets): break
        assert diag["chunk_spans"] == spans and diag["total_chunks"] == len(spans) <= 64 and diag["total_state_bge_tokens"] == len(offsets)
        chunks = [state[a:b] for a, b in spans]
        rt = diag["retrieval"]; be = rt["bundle_evidence"]; bundlepath = r / "bundles" / be["relativefilename"]
        assert bundlepath.name == be["sha256"] + ".json" and not bundlepath.is_symlink()
        assert sha(bundlepath) == be["sha256"] == rt["native"]["bundle_sha256"] and bundlepath.stat().st_size == be["bytes"]
        bundle = obj(bundlepath); vectors = np.asarray(bundle["vectors"], dtype=np.float64); query = np.asarray(bundle["query_vectors"], dtype=np.float64)
        assert vectors.shape == (len(chunks),384) and query.shape == (1,384) and np.isfinite(vectors).all() and np.isfinite(query).all()
        assert np.max(np.abs(np.linalg.norm(vectors, axis=1)-1)) < 1e-5 and abs(np.linalg.norm(query)-1) < 1e-5
        native = rt["native"]; assert native["native"] and native["package_version"] == "0.1.33" and native["native_binary_sha256"] == runtime["receipt"]["native_core_binary_sha256"]
        ids = native["queries"][0]["ids"]; assert native["vectors"] == len(chunks) and len(ids) == len(set(ids)) == min(40,len(chunks))
        assert all(type(i) is int and 0 <= i < len(chunks) for i in ids)
        cosine = (vectors @ query[0]) / (np.linalg.norm(vectors,axis=1)*np.linalg.norm(query[0]))
        exact = sorted(range(len(chunks)), key=lambda i:(-cosine[i],i))[:2]
        selected = ids[:2]; assert len(selected) == 2
        ci = diag["baseline_control_input"]
        assert ci == {"state":"\n\n".join(chunks[i] for i in selected),"questions":rec["input"]["questions"]}
        assert hashlib.sha256(literal(ci)).hexdigest() == diag["baseline_control_input_sha256"]
        assert diag["baseline_control_label"] == "native104_on_ruvector_evidence" and diag["baseline_control_source_chunk_ids"] == selected
        assert len(ci["state"].encode()) == diag["baseline_control_state_bytes"] <= 16*1024
        assert response["baseline104_response"]["model"] == "native104_on_ruvector_evidence"
        ed = rt["embedding"]; assert ed["actual_embedded_texts"] == usage["bge_evidence_texts"] and ed["cached_chunk_vectors"] == usage["cached_chunk_vectors"]
        assert ed["cache_key"] == hashlib.sha256(json.dumps(chunks,ensure_ascii=False,separators=(",", ":")).encode()).hexdigest()
        qexample = ed["query"]["examples"]; assert len(qexample) == 1
        expected_qtokens = len(bge.encode(config["query_prefix"]+hyp).ids)
        assert qexample[0] == {"raw_tokens":expected_qtokens,"used_tokens":expected_qtokens,"truncated":False} and expected_qtokens <= 256
        if ed["chunks"]["cache_hit"]:
            assert ed["chunks"]["examples"] == [] and ed["cached_chunk_vectors"] == len(chunks) and ed["actual_embedded_texts"] == 1
        else:
            assert ed["cached_chunk_vectors"] == 0 and ed["actual_embedded_texts"] == len(chunks)+1
            for text, tok in zip(chunks, ed["chunks"]["examples"]):
                count=len(bge.encode(text).ids); assert tok == {"raw_tokens":count,"used_tokens":count,"truncated":False} and count<=256
            assert len(ed["chunks"]["examples"]) == len(chunks)
        doc=docs[expected["provenance"]["document_id"]]; assert doc["text"] == state
        ann=doc["annotation_sets"][0]["annotations"][expected["provenance"]["hypothesis_id"]]
        goldspans=[doc["spans"][i] for i in ann["spans"]]
        proof = {"id": rec["id"], "group":rec["source_group"],"gold":rec["evaluation"]["gold"],"source_threeway":ann["choice"],"native_top2":selected,"exact_cosine_top2":exact,"exact_top2_set_agreement":set(selected)==set(exact),"exact_recall_at2":len(set(selected)&set(exact))/2,"arms":{}}
        for name, alias in armkeys.items():
            output = response if alias is None else response["baseline104_response"] if alias == "baseline" else response["ablation_responses"][name]
            answer=output["answers"]["decision"]; p=answer["probabilities"]
            assert set(p)=={"Yes","No"} and all(isinstance(x,(int,float)) and math.isfinite(x) and 0<=x<=1 for x in p.values())
            assert abs(sum(p.values())-1)<=1e-3
            expected_answer=min(p,key=lambda k:(-p[k],k)); assert answer["choice"]==expected_answer
            canonical=scorer.score_task(p,SimpleNamespace(labels=["Yes","No"],expected=rec["evaluation"]["gold"],question={"type":"choice"}))
            assert canonical["strict_valid"] and canonical["valid"]
            score={"correct":bool(canonical["correct"]),**proper_scores(canonical["probs"],rec["evaluation"]["gold"],["Yes","No"])}
            scored[name].append(score)
            if alias == "baseline": continue
            diagname = alias or name; ad=diag["arms"][diagname]; cids=ad["chunk_ids"]
            desired=selected if alias is None else lexical(chunks,hyp,2) if alias=="lexical_top2" else [0,1]
            assert cids==desired and ad["chunk_spans"]==[spans[i] for i in cids]
            dec=ad["decoding"]; logits=np.asarray(dec["logits"],dtype=np.float64)
            assert logits.shape==(2,3) and np.isfinite(logits).all() and len(dec["examples"])==2
            probs=softmax(logits)
            for idx,row,tok in zip(cids,dec["nli_probabilities"],dec["examples"]):
                count=len(nli.encode(chunks[idx],hyp).ids);assert tok=={"raw_tokens":count,"used_tokens":count,"truncated":False} and count<=512
            for i,row in enumerate(dec["nli_probabilities"]):
                for j,label in id2label.items(): close(row[label],probs[i,j])
            yes=max(probs[:,1]);close(p["Yes"],yes);close(p["No"],1-yes)
            assert dec["model_batches"]==1 and dec["pool"]=="maximum entailment across selected chunks"
            assert dec["binary_mapping"]=="Yes=entailment; No=contradiction+neutral"
            for idx,logit in zip(cids,logits):
                key=(hashlib.sha256(chunks[idx].encode()).hexdigest(),hashlib.sha256(hyp.encode()).hexdigest())
                if key in logits_by_pair:
                    drift=float(np.max(np.abs(logit-logits_by_pair[key])));max_repeat_difference=max(max_repeat_difference,drift)
                else: logits_by_pair[key]=logit
            overlap=[any(span_overlap(gs,spans[idx]) for idx in cids) for gs in goldspans]
            proof["arms"][name]={"selected":cids,"gold_span_count":len(goldspans),"gold_spans_with_any_overlap":sum(overlap),"any_gold_overlap":any(overlap),"all_gold_spans_overlap":bool(goldspans) and all(overlap),"decoding_ms":dec["elapsed_ms"],"correct":score["correct"]}
        # Dynamic ONNX quantization may depend on the companion/padded batch.
        # Preserve observed same-pair drift rather than inventing determinism.
        embed_texts+=ed["actual_embedded_texts"];cached_vectors+=ed["cached_chunk_vectors"];nli_pairs+=usage["nli_pairs_all_arms"]
        rowproofs.append(proof)
    metrics={name:{"n":len(vals),"correct":sum(x["correct"] for x in vals),"strict_valid":len(vals),"errors":0,"brier":statistics.mean(x["brier"] for x in vals),"nll":statistics.mean(x["nll"] for x in vals)} for name,vals in scored.items()}
    controller=obj(args.study/"runs/development-comparison.json")
    for name,m in metrics.items():
        for key,value in m.items(): close(controller["metrics"][name][key],value)
    primary=metrics["ruvector_top2"]
    gate=all(primary["correct"]>=m["correct"] and primary["brier"]<=m["brier"]+1e-12 and primary["nll"]<=m["nll"]+1e-12 for name,m in metrics.items() if name!="ruvector_top2")
    gate=gate and all(primary["brier"]<metrics[name]["brier"]-1e-12 or primary["nll"]<metrics[name]["nll"]-1e-12 for name in ["same_nli_lexical_top2","same_nli_positional_first2"])
    assert controller["frozen_development_gate_passed"]==gate
    # Confirmation is disallowed for this final availability-only retry regardless of DEV result.
    assert not (args.study/"runs/confirmation").exists() and not (args.study/"runs/confirmation-lock.json").exists()
    groups=sorted({x["source_group"] for x in actual}); assert len(groups)==8 and all(sum(r["source_group"]==g for r in actual)==3 for g in groups)
    uncertainty={}
    for name,vals in scored.items():
        if name=="ruvector_top2":continue
        gains={key:[] for key in ["accuracy","brier","nll"]}
        for g in groups:
            indices=[i for i,r in enumerate(actual) if r["source_group"]==g]
            gains["accuracy"].append(statistics.mean(int(scored["ruvector_top2"][i]["correct"])-int(vals[i]["correct"]) for i in indices))
            for key in ["brier","nll"]:gains[key].append(statistics.mean(vals[i][key]-scored["ruvector_top2"][i][key] for i in indices))
        uncertainty[name]={k:paired_bootstrap_interval(v) for k,v in gains.items()}
    result={"schema_version":1,"at":datetime.now(timezone.utc).isoformat(),"checks_passed":True,"scope":"Original ContractNLI public train24/8doc DEV only, availability-amended native104 excerpt control, no fresh confirmation and no generalization/official-score claim.","plan_sha256":sha(args.plan),"pins_verified":len(plan["pins"]),"metrics":metrics,"gate_passed":gate,"doc_group_DEV_bootstrap_diagnostic":uncertainty,"actual_request_count":len(actual),"actual_native_core_searches":len(actual),"actual_evidence_conditioned_native104_calls":len(actual),"actual_NLI_pairs_all_arms":nli_pairs,"actual_BGE_text_embeddings":embed_texts,"cached_chunk_vectors_reused":cached_vectors,"max_repeated_pair_logit_difference":max_repeat_difference,"same_pair_logit_drift_scope":"Quantized batching/companion padding may alter logits; actual outputs retained and decoded independently, no cross-arm logit cache.","ANN_exact_top2_set_agreement_count":sum(x["exact_top2_set_agreement"] for x in rowproofs),"ANN_mean_exact_recall_at2":statistics.mean(x["exact_recall_at2"] for x in rowproofs),"rows":rowproofs,"whole_pipeline_latency_seconds":{"p50":statistics.median(x["elapsed_s"] for x in actual),"max":max(x["elapsed_s"] for x in actual),"scope":"Actual loopback HTTP including all3NLI arms+evidence-conditioned104+retrieval; not primary-only deployment latency"},"closed_worker_native_pids":pids,"confirmation96_consumed":False,"promotion_permitted":False,"champion_unchanged":True,"official_rank":None,"official_score":None,"sota_established":False,"auditor_native_calls":0,"auditor_onnx_calls":0,"artifact_pins":[{"path":str(p.relative_to(PROJECT)),"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(args.study.rglob('*')) if p.is_file()]}
    result["whole_pipeline_latency_seconds"]["p95"] = float(np.percentile([x["elapsed_s"] for x in actual],95))
    result["per_arm_NLI_decode_ms"] = {name:{"p50":statistics.median(x["arms"][name]["decoding_ms"] for x in rowproofs),"p95":float(np.percentile([x["arms"][name]["decoding_ms"] for x in rowproofs],95)),"scope":"NLI decode only; each arm executes both pairs independently"} for name in ["ruvector_top2","same_nli_lexical_top2","same_nli_positional_first2"]}
    result["evidence_conditioned_native104_ms"] = {"p50":statistics.median(x["response"]["diagnostics"]["decision"]["baseline_control_wall_ms"] for x in actual),"p95":float(np.percentile([x["response"]["diagnostics"]["decision"]["baseline_control_wall_ms"] for x in actual],95))}
    result["native_retrieval_process_ms"] = {"p50":statistics.median(x["response"]["diagnostics"]["decision"]["retrieval"]["native_process_wall_ms"] for x in actual),"p95":float(np.percentile([x["response"]["diagnostics"]["decision"]["retrieval"]["native_process_wall_ms"] for x in actual],95)),"scope":"Native node process+index creation+insert+search, excludes BGE embedding"}
    result["annotation_coverage_diagnostic"] = {name:{"queries_with_gold_spans":sum(bool(x["arms"][name]["gold_span_count"]) for x in rowproofs),"queries_any_gold_span_overlap":sum(x["arms"][name]["any_gold_overlap"] for x in rowproofs),"queries_all_gold_spans_overlap":sum(x["arms"][name]["all_gold_spans_overlap"] for x in rowproofs),"scope":"Posthoc original gold-evidence offset overlap only; no spans provided to inference and overlap alone does not prove sufficient evidence"} for name in ["ruvector_top2","same_nli_lexical_top2","same_nli_positional_first2"]}
    args.out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({"checks_passed":True,"out":str(args.out),"sha256":sha(args.out),"metrics":metrics,"gate_passed":gate}))


if __name__=="__main__": main()
