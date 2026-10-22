"""Pinned DeBERTa-base singleton inference, without truncation or padding."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CountedSession:
    def __init__(self,session,counters):self.session=session;self.counters=counters
    def run(self,outputs,feed):
        n=int(feed["input_ids"].shape[0]);self.counters["bge_forward_batches_attempted"]+=1;self.counters["bge_texts_attempted"]+=n
        started=time.perf_counter()
        try:
            result=self.session.run(outputs,feed)
            self.counters["bge_forward_batches_completed"]+=1;self.counters["bge_texts_completed"]+=n
            return result
        finally:self.counters["bge_forward_wall_seconds"]+=time.perf_counter()-started


class SingletonNli:
    def __init__(self,folder,counters):
        import onnxruntime as ort
        import tokenizers
        from tokenizers import Tokenizer
        folder=Path(folder);self.counters=counters
        self.config=json.loads((folder/"config.json").read_text())
        self.label_indices={str(v).casefold():int(k) for k,v in self.config["id2label"].items()}
        if set(self.label_indices)!={"entailment","contradiction","neutral"}:raise ValueError("Unsupported NLI labels")
        self.tokenizer=Tokenizer.from_file(str(folder/"tokenizer.json"))
        self.tokenizer.no_truncation();self.tokenizer.no_padding()
        opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(folder/"onnx/model_quantized.onnx"),sess_options=opts,providers=["CPUExecutionProvider"])
        self.inputs={x.name for x in self.session.get_inputs()}
        self.receipt={"repo":"Xenova/nli-deberta-v3-base","revision":"80a99030ce45a69a39ea2a6f50756d03859ff521","model_sha256":sha(folder/"onnx/model_quantized.onnx"),"tokenizer_sha256":sha(folder/"tokenizer.json"),"config_sha256":sha(folder/"config.json"),"label_indices":self.label_indices,"hidden_size":self.config["hidden_size"],"layers":self.config["num_hidden_layers"],"onnxruntime":ort.__version__,"tokenizers":tokenizers.__version__,"numpy":np.__version__,"provider":"CPUExecutionProvider","threads":2,"batch_size":1,"padding":False,"truncation":False,"pair_token_cap":512,"temperature":1.0,"training_or_calibration_fit":False}

    def decode(self,premise,hypothesis):
        encoding=self.tokenizer.encode(premise,hypothesis)
        if len(encoding.ids)>512:raise ValueError("Complete joint evidence+claim exceeds512 tokens; no clipping")
        if any(v!=1 for v in encoding.attention_mask):raise ValueError("Singleton NLI must be unpadded")
        arrays={"input_ids":np.asarray([encoding.ids],dtype=np.int64),"attention_mask":np.asarray([encoding.attention_mask],dtype=np.int64),"token_type_ids":np.asarray([encoding.type_ids],dtype=np.int64)}
        feed={k:v for k,v in arrays.items() if k in self.inputs}
        trace={"input_tokens":len(encoding.ids),"raw_tokens":len(encoding.ids),"used_tokens":len(encoding.ids),"batch_size":1,"padding_tokens":0,"truncated":False,"input_ids":encoding.ids,"attention_mask":encoding.attention_mask,"token_type_ids":encoding.type_ids,"input_text_sha256":hashlib.sha256(json.dumps({"premise":premise,"hypothesis":hypothesis},ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()}
        self.counters["nli_forward_pairs_attempted"]+=1
        self.counters["nli_input_tokens_attempted"]+=len(encoding.ids)
        started=time.perf_counter()
        try:
            logits=np.asarray(self.session.run(None,feed)[0],dtype=np.float64)
            if logits.shape!=(1,3) or not np.isfinite(logits).all():raise ValueError("Invalid singleton NLI logits")
            self.counters["nli_forward_pairs_completed"]+=1
            self.counters["nli_input_tokens_completed"]+=len(encoding.ids)
        finally:self.counters["nli_forward_wall_seconds"]+=time.perf_counter()-started
        p=np.exp(logits[0]-logits[0].max());p/=p.sum()
        classes={name:float(p[index]) for name,index in self.label_indices.items()}
        trace.update(logits=logits[0].tolist(),nli_probabilities=classes,elapsed_ms=(time.perf_counter()-started)*1000,mapping="Yes=entailment;No=contradiction+neutral",pool="One joint evidence premise; no per-chunk maximum")
        return {"Yes":classes["entailment"],"No":classes["contradiction"]+classes["neutral"]},trace
