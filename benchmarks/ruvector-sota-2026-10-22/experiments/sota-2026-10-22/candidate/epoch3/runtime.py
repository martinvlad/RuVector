"""Matched RuVector evidence-selection/NLI ablation, entirely local CPU."""
from __future__ import annotations
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out


MODELS=module("epoch3_models",HERE/"models.py")
BASE=module("epoch3_frozen104_engine",ROOT/"experiments/submission-2026-10-22/jevbench/engine.py")


def chunk_offsets(offsets,text_length,max_tokens=180,overlap=30,max_chunks=64):
    if not offsets:return [(0,text_length)]
    spans=[]
    for start in range(0,len(offsets),max_tokens-overlap):
        end=min(start+max_tokens,len(offsets))
        spans.append((offsets[start][0],offsets[end-1][1]))
        if end==len(offsets):break
    if len(spans)>max_chunks:raise ValueError("State exceeds64 complete chunks; reject instead of silent truncation")
    return spans


def lexical_ids(chunks,hypothesis,k):
    query=set(re.findall(r"\w+",hypothesis.casefold()))
    def score(index):
        words=set(re.findall(r"\w+",chunks[index].casefold()))
        return len(query&words)/max(1,len(query|words))
    return sorted(range(len(chunks)),key=lambda i:(-score(i),i))[:k]


def validate_question(question):
    if question.get("type")!="choice" or set(question.get("criteria",{}))!={"Yes","No"}:
        raise ValueError("Epoch3 supports binary ContractNLI Yes/No choice semantics only")
    positive=question["criteria"]["Yes"]
    if not isinstance(positive,str) or not positive.strip():raise ValueError("Positive predicate text required")
    return positive


def answer_for(probabilities):
    label=min(probabilities,key=lambda k:(-probabilities[k],k))
    return {"type":"choice","choice":label,"probabilities":probabilities,"confidence":max(probabilities.values()),"calibrated":False,"head":"pretrained-NLI-over-selected-evidence","model":"Xenova/nli-deberta-v3-xsmall@2a4f614a701367a02d51389039afc998faeda637"}


def preserve_bundle(bundle_bytes,directory):
    """Persist literal native-input bytes by SHA256 without overwriting evidence."""
    if not isinstance(bundle_bytes,bytes):raise ValueError("Literal bundle bytes required")
    digest=hashlib.sha256(bundle_bytes).hexdigest()
    folder=Path(directory)
    folder.mkdir(parents=True,exist_ok=True)
    filename=digest+".json"
    target=folder/filename
    if target.is_symlink():raise ValueError("Bundle evidence path must not be a symlink")
    try:
        with target.open("xb") as stream:
            stream.write(bundle_bytes);stream.flush();os.fsync(stream.fileno())
    except FileExistsError:
        if not target.is_file() or target.read_bytes()!=bundle_bytes:
            raise ValueError("Existing content-addressed bundle differs; refusing overwrite")
    return {"sha256":digest,"bytes":len(bundle_bytes),"relativefilename":filename,"encoding":"Literal UTF-8 JSON bytes passed to native RuVector worker"}


class CandidateEngine:
    name="ruvector-native-evidence-nli-epoch3"
    attribution="Actual native@ruvector/core evidence retrieval + pretrained DeBERTa NLI. Native104 control reads the same concatenated selected RuVector evidence, not full input. Same-decoder lexical and positional controls isolate evidence selection."

    def __init__(self,artifact_path=None):
        bundle_directory=os.environ.get("RUVECTOR_SOTA_BUNDLE_DIR")
        if not bundle_directory:raise ValueError("RUVECTOR_SOTA_BUNDLE_DIR required for independently replayable native evidence")
        self.bundle_directory=Path(bundle_directory).resolve()
        self.bundle_directory.mkdir(parents=True,exist_ok=True)
        lock=json.loads((HERE/"assets.lock.json").read_text())
        for package,version in lock["python_versions"].items():
            if importlib.metadata.version(package)!=version:raise ValueError("Pinned Python dependency changed: "+package)
        for item in lock["assets"]:
            p=ROOT/item["path"]
            # The isolated executor may link existing reviewed read-only asset
            # caches. Identity is checked on the resolved file's actual bytes.
            if not p.is_file() or p.stat().st_size!=item["bytes"] or MODELS.sha(p)!=item["sha256"]:
                raise ValueError("Pinned epoch3 asset changed: "+item["path"])
        self.config=json.loads((HERE/"config.json").read_text())
        if MODELS.sha(HERE/"config.json")!="73dbc1483b307de55de9752e9bd54114cb7ebeabd32dd138eaedfb2b1e45011e":raise ValueError("Frozen epoch3 config identity changed")
        if artifact_path:
            provided=json.loads(Path(artifact_path).read_text())
            if provided!=self.config:raise ValueError("Unfrozen epoch3 configuration")
        selected=ROOT/"experiments/submission-2026-10-22/jevbench/round2-v2/plan.json"
        plan=json.loads(selected.read_text())
        if MODELS.sha(selected)!="782db4034b2eb51ad9520a632ee94f7bdbb5bf0e8826ca44a91a055c15971f17":raise ValueError("Frozen104 plan identity mismatch")
        for name,expected in plan["source_sha256"].items():
            if MODELS.sha(ROOT/name)!=expected:raise ValueError("Frozen104 source changed: "+name)
        self.bge=MODELS.BgeEncoder(ROOT)
        self.nli=MODELS.NliDecoder(ROOT)
        self.base=BASE.CompositeEngine(ROOT/"experiments/submission-2026-10-22/jevbench/round2-v2/rules.py")
        self.native_process=self.base.native.process;self.native_pid=self.native_process.pid
        if self.base.receipt["binary_sha256"]!=plan["native_candidate"]["binary_sha256"]:
            self.base.close();raise ValueError("Native104 binary changed")
        self.last_usage=None
        self.evidence_cache={}
        self.receipt={**self.base.receipt,"architecture":self.attribution,"config":self.config,"nli":self.nli.receipt,"bge":self.bge.receipt,"assets_lock_sha256":MODELS.sha(HERE/"assets.lock.json"),"native_core_binary_sha256":lock["native_core_binary_sha256"],"decoder_weight_history":"Same cached pretrained NLI was previously measured in experiments/optimization/decision_loop.py. New hypothesis is native RuVector evidence selection versus identical decoder controls."}

    def retrieve(self,chunks,hypothesis):
        cache_key=hashlib.sha256(json.dumps(chunks,ensure_ascii=False,separators=(",",":" )).encode()).hexdigest()
        hit=cache_key in self.evidence_cache
        if hit:
            chunk_vectors=self.evidence_cache[cache_key]
            chunk_diagnostics={"examples":[],"elapsed_ms":0.,"model_batches":0,"cache_hit":True}
        else:
            chunk_vectors,chunk_diagnostics=self.bge.encode(chunks)
            if len(self.evidence_cache)>=64:self.evidence_cache.pop(next(iter(self.evidence_cache)))
            self.evidence_cache[cache_key]=chunk_vectors
            chunk_diagnostics["cache_hit"]=False
        query_vectors,query_diagnostics=self.bge.encode([self.config["query_prefix"]+hypothesis])
        embed_diagnostics={"chunks":chunk_diagnostics,"query":query_diagnostics,"cached_chunk_vectors":len(chunks) if hit else 0,"actual_embedded_texts":1+(0 if hit else len(chunks)),"cache_key":cache_key}
        bundle={"vectors":chunk_vectors.tolist(),"query_vectors":query_vectors.tolist()}
        with tempfile.TemporaryDirectory(prefix="ruvector-epoch3-") as folder:
            path=Path(folder);source=path/"bundle.json";target=path/"native.json"
            bundle_bytes=json.dumps(bundle,separators=(",",":"),allow_nan=False).encode("utf-8")
            source.write_bytes(bundle_bytes)
            bundle_evidence=preserve_bundle(bundle_bytes,self.bundle_directory)
            started=time.perf_counter()
            result=subprocess.run(["node",str(ROOT/"retrieval/native-candidates.cjs"),str(source),str(target)],cwd=path,capture_output=True,text=True,timeout=60)
            if result.returncode:raise RuntimeError("Native RuVector search failed: "+result.stderr[-500:])
            observed=json.loads(target.read_text())
            if observed.get("native") is not True or observed.get("package_version")!="0.1.33" or observed["native_binary_sha256"]!=self.receipt["native_core_binary_sha256"]:
                raise ValueError("Actual native retrieval identity mismatch")
            if observed["bundle_sha256"]!=MODELS.sha(source):raise ValueError("Native retrieval input mismatch")
            if observed["bundle_sha256"]!=bundle_evidence["sha256"]:raise ValueError("Preserved native evidence input mismatch")
            ids=observed["queries"][0]["ids"][:min(self.config["top_k"],len(chunks))]
            if not ids or len(ids)!=len(set(ids)) or any(i<0 or i>=len(chunks) for i in ids):raise ValueError("Invalid native retrieval ids")
            return ids,{"embedding":embed_diagnostics,"native":observed,"bundle_evidence":bundle_evidence,"native_process_wall_ms":(time.perf_counter()-started)*1000}

    def predict(self,state,questions):
        if not isinstance(state,str):state=json.dumps(state,ensure_ascii=False,separators=(",",":"))
        predicates={key:validate_question(q) for key,q in questions.items()}
        started=time.perf_counter()
        offsets=self.bge.raw_tokenizer.encode(state,add_special_tokens=False).offsets
        spans=chunk_offsets(offsets,len(state),self.config["chunk_tokens"],self.config["overlap_tokens"],self.config["max_chunks"])
        chunks=[state[a:b] for a,b in spans]
        arm_answers={name:{} for name in ("ruvector_top2","lexical_top2","positional_first2")};diagnostics={}
        baseline_answers={};baseline_usage={}
        nli_pairs=0
        for key,hypothesis in predicates.items():
            ids,retrieval=self.retrieve(chunks,hypothesis)
            control_input={"state":"\n\n".join(chunks[index] for index in ids),"questions":{key:questions[key]}}
            if len(control_input["state"].encode("utf-8"))>16*1024:
                raise ValueError("Selected native104 evidence exceeds16KiB; no hidden context truncation")
            control_input_bytes=json.dumps(control_input,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")
            control_started=time.perf_counter()
            control=self.base.predict(control_input["state"],control_input["questions"])
            control_wall_ms=(time.perf_counter()-control_started)*1000
            baseline_answers[key]=copy.deepcopy(control["answers"][key])
            baseline_usage[key]=copy.deepcopy(control.get("usage",{}))
            selected={"ruvector_top2":ids,"lexical_top2":lexical_ids(chunks,hypothesis,min(self.config["top_k"],len(chunks))),"positional_first2":list(range(min(self.config["top_k"],len(chunks))))}
            arm_diagnostics={}
            for name,indices in selected.items():
                probabilities,decoding=self.nli.decode([chunks[i] for i in indices],hypothesis)
                arm_answers[name][key]=answer_for(probabilities)
                nli_pairs+=len(indices)
                arm_diagnostics[name]={"chunk_ids":indices,"chunk_spans":[spans[i] for i in indices],"decoding":decoding}
            diagnostics[key]={"hypothesis_sha256":hashlib.sha256(hypothesis.encode()).hexdigest(),"hypothesis_source":"Exact supplied positive Yes criterion; no task ID lookup or spelling correction","state_bytes":len(state.encode()),"total_state_bge_tokens":len(offsets),"total_chunks":len(chunks),"chunk_spans":spans,"retrieval":retrieval,"arms":arm_diagnostics,
                "baseline_control_label":"native104_on_ruvector_evidence","baseline_control_input":control_input,
                "baseline_control_input_sha256":hashlib.sha256(control_input_bytes).hexdigest(),
                "baseline_control_input_hash_encoding":"UTF8 JSON ensure_ascii=False separators=(',',':') allow_nan=False",
                "baseline_control_source_chunk_ids":list(ids),"baseline_control_state_bytes":len(control_input["state"].encode("utf-8")),"baseline_control_wall_ms":control_wall_ms}
        common_keys=set.intersection(*(set(usage) for usage in baseline_usage.values())) if baseline_usage else set()
        aggregate_usage={k:sum(usage[k] for usage in baseline_usage.values()) for k in common_keys if all(isinstance(usage[k],(int,float)) and not isinstance(usage[k],bool) for usage in baseline_usage.values())}
        aggregate_usage.update(native_requests=len(baseline_usage),per_question_native_usage=baseline_usage,accounting="Only numeric keys present in every native response are summed; all original per-question observations retained; unknown tokens/cost stay unknown")
        baseline={"model":"native104_on_ruvector_evidence","answers":baseline_answers,"usage":aggregate_usage,"attribution":"Real native104 receives the exact same concatenated native RuVector top2 source chunks and original question. This is an evidence-conditioned reader control, not the original full-input104 benchmark configuration."}
        self.last_usage={**aggregate_usage,"native_core_searches":len(questions),"bge_evidence_texts":sum(d["retrieval"]["embedding"]["actual_embedded_texts"] for d in diagnostics.values()),"cached_chunk_vectors":sum(d["retrieval"]["embedding"]["cached_chunk_vectors"] for d in diagnostics.values()),"nli_pairs_all_arms":nli_pairs,"paid_calls":0,"latency_scope":"End-to-end includes evidence-conditioned native104, embedding/retrieval and all matched decoder controls; not isolated deployment latency"}
        def response(name):return {"model":self.name+"-"+name,"answers":copy.deepcopy(arm_answers[name]),"usage":copy.deepcopy(self.last_usage),"attribution":self.attribution}
        result=response("ruvector_top2")
        result["baseline104_response"]=baseline
        result["ablation_responses"]={"same_nli_lexical_top2":response("lexical_top2"),"same_nli_positional_first2":response("positional_first2")}
        result["diagnostics"]=diagnostics
        result["whole_request_wall_ms"]=(time.perf_counter()-started)*1000
        return result

    def close(self):
        self.base.close()
