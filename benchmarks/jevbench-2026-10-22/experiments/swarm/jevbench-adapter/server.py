"""Pinned JevBench TypeSafe wire server, with explicitly separate engines.

The Qwen engine is an external decision component, not an evaluated RuVector
integration. The native engine invokes the actual published RuVector package.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
import signal
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = "Qwen/Qwen2.5-14B-Instruct"
REVISION = "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"
TOKENIZER_SHA256 = "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"
INDEX_SHA256 = "46627f7a9e851d9cede6a7a4c49999082148ced9c22d2b9cfaaa5ba8b65dc68f"
SYSTEM = "You make bounded decisions. Apply the supplied rules to the input. Choose exactly one option. Reply with only the option letter."
TEMPERATURE = 2.0
MAX_BYTES = 1024 * 1024


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RequestError(ValueError):
    status = 400


class ContextError(ValueError):
    status = 413


def strict_loads(raw):
    def bad_constant(value):
        raise RequestError("Nonfinite JSON number")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RequestError("Duplicate JSON key")
            result[key] = value
        return result
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise RequestError("Nonfinite JSON number")
        return number
    return json.loads(raw, parse_constant=bad_constant, parse_float=finite_float, object_pairs_hook=unique)


def question_options(question):
    if not isinstance(question, dict):
        raise RequestError("A question must be an object")
    if not isinstance(question.get("instructions"), str):
        raise RequestError("Question instructions must be a string")
    kind = question.get("type")
    criteria = question.get("criteria")
    if kind == "noul":
        if criteria is None:
            criteria = {}
        if not isinstance(criteria, dict) or any(not isinstance(x, str) for x in criteria.values()):
            raise RequestError("noul criteria must contain string descriptions")
        return ["no", "yes"], [criteria.get("false", "no"), criteria.get("true", "yes")]
    if kind == "choice":
        if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 26:
            raise RequestError("choice requires 2..26 exact label criteria")
        labels, descriptions = list(criteria), []
        if any(not isinstance(label, str) or not label for label in labels):
            raise RequestError("choice labels must be nonempty strings")
        for value in criteria.values():
            description = value if isinstance(value, str) else value.get("what") if isinstance(value, dict) else None
            if not isinstance(description, str):
                raise RequestError("choice criterion must be a string or contain string what")
            descriptions.append(description)
        return labels, descriptions
    if kind == "score":
        if not isinstance(criteria, list) or not 2 <= len(criteria) <= 26 or any(not isinstance(v, str) for v in criteria):
            raise RequestError("score requires 2..26 ordered string criteria")
        return [str(i) for i in range(len(criteria))], criteria
    raise RequestError("Unknown question type")


def validate_request(body):
    if not isinstance(body, dict) or "state" not in body or body["state"] is None:
        raise RequestError("state is required")
    questions = body.get("questions")
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 32:
        raise RequestError("questions must be a nonempty map with at most32entries")
    for key, question in questions.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            raise RequestError("Invalid question ID")
        question_options(question)
    # Compact JSON matches the baseline server's JSON.stringify boundary.
    state = body["state"] if isinstance(body["state"], str) else json.dumps(body["state"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return state, questions


def prompt_for(state, question):
    labels, descriptions = question_options(question)
    menu = "\n".join(f"{chr(65+i)}. {label}: {description}" for i, (label, description) in enumerate(zip(labels, descriptions)))
    # The frozen Qwen experiment has no train demonstrations for JevBench.
    user = f'{question["instructions"]}\n\nOptions:\n{menu}\n\nInput:\n{state}\n\nCorrect option:'
    return f"<|im_start|>system\n{SYSTEM}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"


def distribution(logits, count):
    if not isinstance(logits, list) or len(logits) != count or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in logits):
        raise RuntimeError("Backend returned invalid class logits")
    scaled = [x / TEMPERATURE for x in logits]
    peak = max(scaled)
    values = [math.exp(x - peak) for x in scaled]
    total = sum(values)
    return [x / total for x in values]


class QwenEngine:
    name = "qwen14-external-component"
    attribution = "External Qwen decision component; no RuVector lookup or native RuVector reasoning contribution"

    def __init__(self, receipt_path):
        start = time.perf_counter()
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if not torch.cuda.is_available():
            raise RuntimeError("Qwen14 engine requires CUDA; no CPU or smaller-model fallback")
        self.torch = torch
        torch.set_num_threads(4)
        self.folder = Path(snapshot_download(REPO, revision=REVISION, token=False,
            allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model"]))
        if sha(self.folder / "tokenizer.json") != TOKENIZER_SHA256 or sha(self.folder / "model.safetensors.index.json") != INDEX_SHA256:
            raise RuntimeError("Pinned tokenizer or weight index hash mismatch")
        self.tokenizer = AutoTokenizer.from_pretrained(self.folder, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(self.folder, local_files_only=True,
            torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa")
        self.model.eval()
        self.letter_ids = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            ids = self.tokenizer.encode(letter, add_special_tokens=False)
            if len(ids) != 1:
                raise RuntimeError("Readout requires single-token option letters")
            self.letter_ids.append(ids[0])
        self.receipt = {"repo": REPO, "revision": REVISION, "tokenizer_sha256": TOKENIZER_SHA256,
            "weight_index_sha256": INDEX_SHA256, "weights": [{"name":p.name,"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(self.folder.glob("*.safetensors"))],
            "torch":torch.__version__, "gpu":torch.cuda.get_device_name(), "dtype":"bfloat16",
            "temperature":TEMPERATURE,"attribution":self.attribution,"initialization_ms":(time.perf_counter()-start)*1000}
        receipt_path = Path(receipt_path)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(self.receipt,indent=2)+"\n")

    def logits(self, prompt, count):
        torch = self.torch
        inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        tokens = inputs.input_ids.shape[-1]
        if tokens > self.model.config.max_position_embeddings:
            raise ContextError("Model context exceeded; no input was truncated")
        # Preserve attempted prefill usage even if the model raises afterwards.
        self.last_usage["input_tokens"] += tokens
        self.last_usage["model_calls"] += 1
        with torch.inference_mode():
            output = self.model(**inputs, use_cache=False, logits_to_keep=1)
            y = output.logits[0,-1].float()
            logits = y[self.letter_ids[:count]]
            mass = torch.logsumexp(logits,0)-torch.logsumexp(y,0)
            result = {"class_logits":logits.cpu().double().tolist(),"input_tokens":tokens,"option_log_probability_mass":mass.item()}
        del output, inputs
        return result

    def predict(self, state, questions):
        self.last_usage = {"input_tokens":0,"output_tokens":0,"model_calls":0,
            "token_count_basis":"actual tokenizer tokens for every attempted prefill; no generation"}
        answers, diagnostics, token_count = {}, {}, 0
        for key, question in questions.items():
            labels, _ = question_options(question)
            prompt = prompt_for(state, question)
            start = time.perf_counter()
            raw = self.logits(prompt,len(labels))
            probabilities = distribution(raw["class_logits"], len(labels))
            if not isinstance(raw.get("input_tokens"), int) or isinstance(raw["input_tokens"], bool) or raw["input_tokens"] <= 0:
                raise RuntimeError("Backend returned invalid input token count")
            mass = raw.get("option_log_probability_mass")
            if not isinstance(mass,(int,float)) or not math.isfinite(mass) or mass > 1e-5:
                raise RuntimeError("Backend returned invalid option probability mass")
            best = max(range(len(labels)),key=lambda i:probabilities[i])
            answer = {"type":question["type"],"probabilities":dict(zip(labels,probabilities)),
                "calibrated":False,"head":"causal-option-logits","temperature":TEMPERATURE,"model":REPO+"@"+REVISION[:12]}
            if question["type"] == "noul":
                answer["noul"] = probabilities[1]
            elif question["type"] == "choice":
                answer["choice"] = labels[best]
            else:
                answer["score"] = sum(i*p for i,p in enumerate(probabilities))/(len(labels)-1)
            answers[key] = answer
            diagnostics[key] = {**raw,"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),"prefill_readout_ms":(time.perf_counter()-start)*1000}
            token_count += raw["input_tokens"]
        if self.last_usage["model_calls"] != len(questions) or self.last_usage["input_tokens"] != token_count:
            raise RuntimeError("Actual usage accounting mismatch")
        return {"model":self.name,"answers":answers,"usage":dict(self.last_usage),
            "diagnostics":diagnostics,"attribution":self.attribution}

    def close(self):
        pass


class NativeEngine:
    name = "ruvector-native-baseline"
    attribution = "Actual @ruvector/typesafe native BGE-small similarity baseline; no Qwen component"

    def __init__(self):
        self.process = subprocess.Popen(["node",str(HERE/"native-worker.cjs")], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, bufsize=1, cwd=ROOT)
        self.receipt = json.loads(self.process.stdout.readline())
        if self.receipt.get("status") != "ready" or self.receipt.get("backend") != "native":
            self.close()
            raise RuntimeError("Native worker failed initialization")

    def predict(self,state,questions):
        self.last_usage = None
        self.process.stdin.write(json.dumps({"state":state,"questions":questions},ensure_ascii=False)+"\n")
        self.process.stdin.flush()
        raw = self.process.stdout.readline()
        if not raw:
            raise RuntimeError("Native worker terminated")
        result = json.loads(raw)
        if not result.get("ok"):
            raise RuntimeError(result.get("error","Native decision failed"))
        response = result["response"]
        response["attribution"] = self.attribution
        # Native usage reports embedding calls/texts/bytes, not tokenizer tokens.
        response["usage"]["token_count_basis"] = "native package does not report tokenizer input/output counts; unknown, not zero"
        self.last_usage = response["usage"]
        return response

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()


def make_server(engine, host="127.0.0.1", port=8787, audit_path=None):
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send(self,status,value):
            payload = json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path != "/health":
                return self.send(404,{"error":"Unknown route"})
            return self.send(200,{"model":engine.name,"attribution":engine.attribution,"receipt":engine.receipt})

        def do_POST(self):
            start = time.perf_counter()
            raw = b""
            def audit(ok, status, response_bytes=None, error=None):
                if audit_path:
                    record = {"at":datetime.now(timezone.utc).isoformat(),"request_sha256":hashlib.sha256(raw).hexdigest(),
                        "model":engine.name,"ok":ok,"status":status,"usage":getattr(engine,"last_usage",None),
                        "server_request_ms":(time.perf_counter()-start)*1000,"cost_per_decision_usd":None,
                        "response_sha256":hashlib.sha256(response_bytes).hexdigest() if response_bytes is not None else None,
                        "error":error}
                    with Path(audit_path).open("a") as stream:
                        stream.write(json.dumps(record)+"\n")
            if self.path != "/v1/systemone":
                return self.send(404,{"error":"Unknown route"})
            try:
                engine.last_usage = None
                if self.headers.get("Transfer-Encoding"):
                    raise RequestError("Transfer-Encoding is unsupported; send Content-Length")
                try:
                    length = int(self.headers.get("Content-Length","-1"))
                except ValueError:
                    raise RequestError("Invalid Content-Length")
                if length < 0:
                    raise RequestError("Content-Length is required")
                if length > MAX_BYTES:
                    audit(False,413,error="Request exceeds1MiB")
                    return self.send(413,{"error":"Request exceeds1MiB"})
                self.connection.settimeout(30)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise RequestError("Incomplete request body")
                body = strict_loads(raw)
                state,questions = validate_request(body)
                with lock:
                    result = engine.predict(state,questions)
                result["timing"] = {"server_request_ms":(time.perf_counter()-start)*1000,
                    "boundary":"read body, parse, validate, all decision calls, response construction before JSON serialization; caller HTTP wall time is authoritative"}
                payload = json.dumps(result,ensure_ascii=False,allow_nan=False).encode()
                audit(True,200,response_bytes=payload)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (RequestError,ContextError,json.JSONDecodeError,UnicodeDecodeError) as error:
                audit(False,getattr(error,"status",400),error=str(error))
                self.send(getattr(error,"status",400),{"error":str(error)})
            except Exception as error:
                audit(False,500,error=type(error).__name__+": "+str(error))
                self.send(500,{"error":type(error).__name__+": "+str(error)})
    return HTTPServer((host,port),Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine",choices=["native","qwen14"],required=True)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8787)
    parser.add_argument("--receipt",default=str(HERE/"qwen-runtime-receipt.json"))
    parser.add_argument("--audit",default=str(HERE/"requests.jsonl"))
    args = parser.parse_args()
    start = time.perf_counter()
    engine = NativeEngine() if args.engine=="native" else QwenEngine(args.receipt)
    server = make_server(engine,args.host,args.port,args.audit)
    signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
    print(json.dumps({"status":"ready","model":engine.name,"endpoint":f"http://{args.host}:{server.server_port}/v1/systemone",
        "cold_start_ms":(time.perf_counter()-start)*1000,"attribution":engine.attribution}),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        engine.close()


if __name__=="__main__":
    main()
