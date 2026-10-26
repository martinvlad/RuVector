"""Single admitted Qwen process, one-token conditional typed decisions."""
import os
from pathlib import Path
import subprocess
import time


class Reader:
    def __init__(self, C, P, transport, plan, counters, progress, lifecycle, deadline, external):
        self.C, self.P, self.plan = C, P, plan
        self.counters, self.progress, self.lifecycle, self.deadline = counters, progress, lifecycle, deadline
        self.external = Path(external); self.process = None; self.identity = None
        self.socket = self.external / "reader.sock"
        self.http = transport.Capture(C, self.socket, external, counters, progress, deadline)
        self.stdout = self.stderr = None
        self.state = {"popen_attempted": False, "returned_handle": False,
                      "child_closed": None, "exit_code": None}
        self.admission = None

    def event(self, event, **facts):
        row = {"event": event, "monotonic_seconds": time.monotonic(),
               "completion_requests_completed": self.counters["completion_requests_completed"], **facts}
        self.lifecycle.append(row); self.progress(row)

    def start(self):
        C = self.C
        C.require(not self.socket.exists() and not self.socket.is_symlink(), "READER_SOCKET_ALREADY_EXISTS")
        self.stdout = (self.external / "reader.stdout").open("xb")
        self.stderr = (self.external / "reader.stderr").open("xb")
        command = [self.plan["llama_server_path"], "--model", self.plan["gguf_path"],
                   "--host", str(self.socket), "--offline", "--no-warmup", "--parallel", "1",
                   "--threads", "2", "--threads-batch", "2", "--threads-http", "1",
                   "--ctx-size", "1024", "--batch-size", "512", "--ubatch-size", "512",
                   "--gpu-layers", "0", "--no-op-offload", "--fit", "off", "--cache-ram", "0",
                   "--no-cache-idle-slots", "--no-context-shift", "--no-webui", "--no-slots"]
        self.event("SERVER_POPEN_BEFORE", argv=command)
        self.counters["reader_server_starts_attempted"] += 1
        self.state["popen_attempted"] = True
        self.process = subprocess.Popen(command, cwd=self.external, env=C.child_env(self.plan),
                                        stdout=self.stdout, stderr=self.stderr, close_fds=True)
        self.state["returned_handle"] = True
        self.identity = C.proc(self.process.pid); self.state["identity"] = self.identity
        C.require(self.identity and self.identity["pgid"] == os.getpgrp() and
                  self.identity["sid"] == os.getsid(0), "SERVER_SESSION_IDENTITY")
        self.counters["reader_server_starts_completed"] += 1
        self.event("SERVER_POPEN_AFTER", identity=self.identity)
        ready = False
        for _ in range(600):
            C.remaining(self.deadline)
            C.require(self.process.poll() is None, "SERVER_EXIT_DURING_LOAD")
            if self.socket.exists():
                response, _ = self.http.request("GET", "/health", category="health")
                if response.get("status") == "ok": ready = True; break
            time.sleep(min(0.1, C.remaining(self.deadline)))
        C.require(ready, "SERVER_READY_DEADLINE")
        models, _ = self.http.request("GET", "/v1/models")
        C.require(type(models.get("data")) is list and len(models["data"]) == 1, "SERVER_MODEL_COUNT")
        meta = models["data"][0]["meta"]
        C.require(type(meta.get("n_ctx")) is int and meta["n_ctx"] == 1024, "SERVER_ACTUAL_CONTEXT_SIZE")
        responses = {}
        for label in self.P.CANONICAL_LABELS:
            value, receipt = self.http.request("POST", "/tokenize", self.P.label_tokenize_request(label),
                                               category="label_tokenize")
            C.require(receipt["status"] == 200, "LABEL_TOKENIZE_HTTP")
            responses[label] = value
        self.admission = self.P.admit_label_tokens(meta["n_vocab"], responses)
        self.runtime_receipt = {"model_meta": meta, "label_admission": self.admission,
                                "argv": command, "warmup": False, "context_size": 1024,
                                "reader_threads": 2, "reader_batch_threads": 2, "HTTP_threads": 1,
                                "backend_forward_batch_count": None}
        self.event("SERVER_READY", model_meta=meta, label_admission=self.admission)

    def tokenize(self, prompt):
        result, receipt = self.http.request("POST", "/tokenize", self.P.prompt_tokenize_request(prompt),
                                           category="prompt_tokenize")
        self.C.require(receipt["status"] == 200 and type(result.get("tokens")) is list and
                       all(type(t) is int and 0 <= t < self.admission["vocab_size"]
                           for t in result["tokens"]), "PROMPT_TOKENIZE_CAPTURE")
        return result["tokens"], receipt

    def score(self, prompt_tokens):
        self.C.remaining(self.deadline)
        request = self.P.build_completion_request(prompt_tokens, self.admission)
        result, body_receipt = self.http.request("POST", "/completion", request, category="completion")
        if type(result.get("tokens_predicted")) is int and result["tokens_predicted"] == 1:
            self.counters["first_answer_token_draws_observed"] += 1
        self.C.require(body_receipt["status"] == 200, "COMPLETION_HTTP_STATUS")
        value = self.P.validate_completion_response(result, self.admission, len(prompt_tokens))
        return value, {**self.http.receipts[-1], **body_receipt}

    def close(self):
        C = self.C
        self.event("SERVER_STOP_BEFORE")
        if self.process is not None:
            self.counters["reader_server_stops_attempted"] += 1
            current = C.proc(self.process.pid)
            C.require(current is None or self.identity and current["ticks"] == self.identity["ticks"],
                      "SERVER_CLEANUP_IDENTITY_UNKNOWN")
            if current is not None and current["state"] not in ("Z", "X"):
                fields = dict(line.split(":", 1) for line in
                              Path(f"/proc/{self.process.pid}/status").read_text().splitlines() if ":" in line)
                self.state["memory_before_stop"] = {key: fields.get(key, "UNKNOWN").strip()
                                                    for key in ("VmHWM", "VmRSS", "Threads", "Cpus_allowed_list")}
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=2)
            self.state.update(child_closed=True, exit_code=self.process.returncode)
            self.counters["reader_server_stops_completed"] += 1
            self.event("SERVER_REAPED", identity=self.identity, exit_code=self.process.returncode)
        for stream in (self.stdout, self.stderr):
            if stream is not None: stream.close()
        return self.state
