"""Pinned CPU ONNX inference, with observed token/truncation accounting."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def softmax(values):
    values=np.asarray(values,dtype=np.float64)
    ex=np.exp(values-np.max(values,axis=-1,keepdims=True))
    return ex/ex.sum(axis=-1,keepdims=True)


class OnnxText:
    def __init__(self,model_path,tokenizer_path,max_tokens,pad_id=0,threads=2):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer=Tokenizer.from_file(str(tokenizer_path))
        self.raw_tokenizer=Tokenizer.from_file(str(tokenizer_path))
        self.raw_tokenizer.no_padding();self.raw_tokenizer.no_truncation()
        self.tokenizer.enable_truncation(max_length=max_tokens,strategy="longest_first")
        self.tokenizer.enable_padding(pad_id=pad_id,pad_token="[PAD]")
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model_path),sess_options=options,providers=["CPUExecutionProvider"])
        self.inputs={entry.name for entry in self.session.get_inputs()}
        self.max_tokens=max_tokens
        self.receipt={"model_sha256":sha(model_path),"tokenizer_sha256":sha(tokenizer_path),"onnxruntime":ort.__version__,"max_tokens":max_tokens,"threads":threads,"provider":"CPUExecutionProvider"}

    def predict(self,examples,pooling=None,batch_size=8):
        output=[];diagnostics=[];started=time.perf_counter()
        for start in range(0,len(examples),batch_size):
            batch=examples[start:start+batch_size]
            raw=self.raw_tokenizer.encode_batch(batch)
            if any(len(encoded.ids)>self.max_tokens for encoded in raw):
                raise ValueError("Model token limit exceeded; refusing hidden hypothesis/evidence truncation")
            encoded=self.tokenizer.encode_batch(batch)
            feed={"input_ids":np.asarray([x.ids for x in encoded],dtype=np.int64),"attention_mask":np.asarray([x.attention_mask for x in encoded],dtype=np.int64),"token_type_ids":np.asarray([x.type_ids for x in encoded],dtype=np.int64)}
            y=self.session.run(None,{k:v for k,v in feed.items() if k in self.inputs})[0]
            if pooling=="cls":y=y[:,0,:]
            if not np.isfinite(y).all():raise ValueError("Nonfinite ONNX output")
            output.append(y)
            diagnostics.extend({"raw_tokens":len(a.ids),"used_tokens":sum(b.attention_mask),"truncated":len(a.ids)>self.max_tokens} for a,b in zip(raw,encoded))
        if not output:raise ValueError("No inference examples")
        return np.concatenate(output),{"examples":diagnostics,"elapsed_ms":(time.perf_counter()-started)*1000,"model_batches":(len(examples)+batch_size-1)//batch_size}


class BgeEncoder(OnnxText):
    def __init__(self,root):
        folder=Path(root)/"models/bge-small-en-v1.5"
        super().__init__(folder/"model.onnx",folder/"tokenizer.json",256)

    def encode(self,texts):
        vectors,diagnostics=self.predict(texts,pooling="cls")
        norms=np.linalg.norm(vectors,axis=1,keepdims=True)
        if np.any(norms<=0):raise ValueError("Zero BGE embedding")
        return (vectors/norms).astype(np.float32),diagnostics


class NliDecoder(OnnxText):
    def __init__(self,root):
        folder=Path(root)/"models/nli"
        self.config=json.loads((folder/"config.json").read_text())
        mapping={str(k):v.casefold() for k,v in self.config["id2label"].items()}
        if set(mapping.values())!={"entailment","contradiction","neutral"}:raise ValueError("Unsupported NLI label semantics")
        self.label_indices={value:int(key) for key,value in mapping.items()}
        super().__init__(folder/"onnx/model_quantized.onnx",folder/"tokenizer.json",512,pad_id=self.config.get("pad_token_id",0))
        self.receipt["label_indices"]=self.label_indices

    def decode(self,premises,hypothesis):
        logits,diagnostics=self.predict([(text,hypothesis) for text in premises])
        if logits.ndim!=2 or logits.shape[1]!=3:raise ValueError("Invalid NLI logits shape")
        distributions=softmax(logits)
        rows=[{label:float(p[index]) for label,index in self.label_indices.items()} for p in distributions]
        # ContractNLI's binarization maps contradiction AND neutral to No.
        yes=max(row["entailment"] for row in rows)
        return {"Yes":yes,"No":1-yes},{**diagnostics,"logits":logits.tolist(),"nli_probabilities":rows,"pool":"maximum entailment across selected chunks","binary_mapping":"Yes=entailment; No=contradiction+neutral"}
