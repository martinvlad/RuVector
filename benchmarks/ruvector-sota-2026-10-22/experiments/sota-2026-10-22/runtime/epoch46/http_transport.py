"""Exact private HTTP wire capture over one owned AF_UNIX socket only."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import socket
import time

MAX_REQUEST_BYTES = 4194304
MAX_RESPONSE_BYTES = 16777216


class Capture:
    def __init__(self, C, path, external, counters, progress, deadline):
        self.C, self.path, self.external = C, str(path), Path(external)
        self.counters, self.progress, self.deadline = counters, progress, deadline
        self.ordinal = 0
        self.receipts = []
        (self.external / "http").mkdir(mode=0o700)

    def request(self, method, endpoint, value=None, category="metadata"):
        C = self.C
        C.remaining(self.deadline)
        C.require(method in ("GET", "POST") and endpoint in
                  ("/health", "/v1/models", "/tokenize", "/completion"), "HTTP_ROUTE")
        self.ordinal += 1
        body = b"" if value is None else json.dumps(value, ensure_ascii=False,
                                                     separators=(",", ":"), allow_nan=False).encode()
        C.require(len(body) <= MAX_REQUEST_BYTES, "HTTP_REQUEST_FRAME_CAP")
        header = (f"{method} {endpoint} HTTP/1.1\r\nHost: localhost\r\n"
                  f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
                  "Connection: close\r\n\r\n").encode("ascii")
        request = header + body
        name = f"{self.ordinal:06d}"
        rq = self.external / "http" / (name + ".request.http")
        rp = self.external / "http" / (name + ".response.http")
        rq.write_bytes(request)
        self.counters["local_HTTP_requests_attempted"] += 1
        self.counters[category + "_requests_attempted"] += 1
        started = time.monotonic(); raw = bytearray(); status = None
        exchange = {"request_ordinal": self.ordinal, "endpoint": endpoint, "category": category,
                    "request_body_sha256": hashlib.sha256(body).hexdigest(),
                    "response_body_sha256": None, "parsed_response_canonical_sha256": None}
        self.progress({"event": "LOCAL_HTTP_BEFORE", "category": category, "ordinal": self.ordinal})
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(C.remaining(self.deadline))
                sock.connect(self.path)
                sock.sendall(request)
                while True:
                    sock.settimeout(C.remaining(self.deadline))
                    block = sock.recv(65536)
                    if not block: break
                    raw.extend(block)
                    C.require(len(raw) <= MAX_RESPONSE_BYTES, "HTTP_RESPONSE_FRAME_CAP")
            class Wire:
                def makefile(self, mode): return io.BytesIO(bytes(raw))
            parsed = http.client.HTTPResponse(Wire()); parsed.begin()
            payload = parsed.read(MAX_RESPONSE_BYTES + 1); status = parsed.status
            C.require(len(payload) <= MAX_RESPONSE_BYTES, "HTTP_BODY_CAP")
            result = json.loads(payload, object_pairs_hook=C.pairs)
            self.counters["local_HTTP_requests_completed"] += 1
            self.counters[category + "_requests_completed"] += 1
            exchange.update(response_body_sha256=hashlib.sha256(payload).hexdigest(),
                            parsed_response_canonical_sha256=C.sha_json(result))
            return result, exchange
        finally:
            rp.write_bytes(raw)
            exchange.update(request=C.ref(rq), response=C.ref(rp), status=status,
                            wall_seconds=time.monotonic()-started)
            self.receipts.append(exchange)
            self.progress({"event": "LOCAL_HTTP_CAPTURE_CLOSED", **exchange})
