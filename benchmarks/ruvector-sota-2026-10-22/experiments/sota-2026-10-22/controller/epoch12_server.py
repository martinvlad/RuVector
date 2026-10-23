"""Epoch12 explicit TRAIN-sanity wire operation; no labels passed to the engine."""
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/swarm/jevbench-adapter"))
from server import MAX_BYTES, RequestError, ContextError, strict_loads, validate_request


def dispatch_request(engine, body, phase):
    if not isinstance(body, dict) or set(body) - {"state", "questions", "operation", "training_example_id"}:
        raise RequestError("Only native inputs and explicit operation metadata are permitted")
    state, questions = validate_request(body)
    operation = body.get("operation")
    if operation == "train_sanity":
        identity = body.get("training_example_id")
        if phase != "development" or not isinstance(identity, str) or not identity:
            raise RequestError("TRAIN sanity is limited to phase1 with an exact frozen identity")
        return engine.predict_train_sanity(state, questions, identity)
    if operation == "predict" and "training_example_id" not in body:
        return engine.predict(state, questions)
    raise RequestError("Unknown or inconsistent operation")


def make_server(engine, host="127.0.0.1", port=8787, audit_path=None, phase="development"):
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
            operation = None
            training_example_id = None
            def audit(ok, status, response_bytes=None, error=None):
                if audit_path:
                    record = {"at":datetime.now(timezone.utc).isoformat(),"request_sha256":hashlib.sha256(raw).hexdigest(),
                        "model":engine.name,"ok":ok,"status":status,"usage":getattr(engine,"last_usage",None),
                        "server_request_ms":(time.perf_counter()-start)*1000,"cost_per_decision_usd":None,
                        "response_sha256":hashlib.sha256(response_bytes).hexdigest() if response_bytes is not None else None,
                        "error":error,"operation":operation,"training_example_id":training_example_id}
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
                operation = body.get("operation") if isinstance(body,dict) else None
                training_example_id = body.get("training_example_id") if isinstance(body,dict) else None
                with lock:
                    result = dispatch_request(engine, body, phase)
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

