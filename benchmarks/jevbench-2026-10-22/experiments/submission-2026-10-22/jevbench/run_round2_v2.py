"""Frozen compounding candidate measured through the unmodified official HTTP adapter."""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import threading
import time
from types import ModuleType
from unittest.mock import patch

import argparse
ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT/'experiments/swarm/jevbench-adapter'
BASE = Path(__file__).resolve().parent
_parser = argparse.ArgumentParser()
_parser.add_argument('--round',choices=['round1','round2-v2'],required=True)
_args = _parser.parse_args()
HERE = BASE/_args.round
sys.path.insert(0,str(ADAPTER))
import server
from engine import CompositeEngine


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    temporary = Path(path).with_suffix(".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    temporary.replace(path)


def official_modules():
    root = ModuleType("measured_jevbench")
    root.__path__ = []
    sys.modules[root.__name__] = root
    adapters = ModuleType(root.__name__+".adapters")
    adapters.__path__ = []
    sys.modules[adapters.__name__] = adapters
    loaded = {}
    for name in ["tasks","scoring","adapters.base","adapters.typesafe"]:
        full = root.__name__+"."+name
        source = ADAPTER/"sources"/("jevbench_"+name.replace(".","_")+".py")
        spec = importlib.util.spec_from_file_location(full,source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[full] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


class TeeReader:
    def __init__(self,reader,chunks):
        self.reader,self.chunks = reader,chunks
    def read(self,*args):
        value = self.reader.read(*args)
        self.chunks.append(value)
        return value
    def readline(self,*args):
        value = self.reader.readline(*args)
        self.chunks.append(value)
        return value
    def readinto(self,buffer):
        count = self.reader.readinto(buffer)
        if count:
            self.chunks.append(bytes(memoryview(buffer)[:count]))
        return count
    def __getattr__(self,key):
        return getattr(self.reader,key)


@contextmanager
def wire_capture():
    request,response = [],[]
    original_send = http.client.HTTPConnection.send
    original_begin = http.client.HTTPResponse.begin
    def send(connection,data):
        if not isinstance(data,(bytes,bytearray,memoryview)):
            raise TypeError("Unexpected streaming request; refusing incomplete wire capture")
        request.append(bytes(data))
        return original_send(connection,data)
    def begin(reply):
        if not getattr(reply,"_native_jev_captured",False):
            reply._native_jev_captured = True
            reply.fp = TeeReader(reply.fp,response)
        return original_begin(reply)
    with patch.object(http.client.HTTPConnection,"send",send),patch.object(http.client.HTTPResponse,"begin",begin):
        yield {"request":request,"response":response}


def percentiles(values):
    ordered = sorted(values)
    def percentile(q):
        position = (len(ordered)-1)*q
        low = int(position)
        fraction = position-low
        return ordered[low]*(1-fraction)+ordered[min(low+1,len(ordered)-1)]*fraction
    return {"p50_ms":percentile(.5),"p95_ms":percentile(.95),"mean_ms":statistics.mean(ordered)} if ordered else None


def run_task(adapter,task,cohort,index,warmup,scorer):
    with wire_capture() as captured:
        start = time.perf_counter()
        result = adapter.run(task)
        runner_ms = (time.perf_counter()-start)*1000
    # Byte persistence and scoring are deliberately outside caller request time.
    request = b"".join(captured["request"])
    response = b"".join(captured["response"])
    stem = "warmup" if warmup else f"{index:04d}"
    request_path,response_path = HERE/"wire"/(stem+".request.http"),HERE/"wire"/(stem+".response.http")
    request_path.write_bytes(request)
    response_path.write_bytes(response)
    request_headers,request_body = request.split(b"\r\n\r\n",1)
    if not request_headers.startswith(b"POST /v1/systemone HTTP/"):
        raise RuntimeError("Observed actual route differs from official TypeSafe source")
    decoded = json.loads(request_body)
    if decoded != adapter.build_request(task):
        raise RuntimeError("Actual HTTP body differs from unmodified official build_request")
    if "expected" in decoded or "answer_key" in decoded:
        raise RuntimeError("Scoring metadata was sent to the decision server")
    if result.ok:
        scored = scorer.score_task(result.probs,task)
    else:
        scored = {"valid":False,"strict_valid":False,"renormalized":False,"correct":False,"predicted":None,"error":result.error}
    return {"id":task.id,"cohort":cohort,"warmup":warmup,"question_type":task.question["type"],"family":task.family,
        "group":task.group or task.id,"labels":task.labels,"expected":task.expected,"ok":result.ok,
        "http_status":result.status,"runner_wall_ms":runner_ms,"adapter_internal_ms":result.latency_s*1000,
        "probs_source":result.probs_source,"model":result.model,"usage":result.usage,"official_score":scored,
        "request_file":str(request_path.relative_to(HERE)),"response_file":str(response_path.relative_to(HERE)),
        "request_sha256":hashlib.sha256(request).hexdigest(),"response_sha256":hashlib.sha256(response).hexdigest(),
        "request_body_sha256":hashlib.sha256(request_body).hexdigest(),"raw_response":result.raw,"error":result.error}


def main():
    started = time.perf_counter()
    plan = json.loads((HERE/"plan.json").read_text())
    for key in ["cycle_policy","independent_contract"]:
        rec=plan[key]
        if sha(ROOT/rec["path"])!=rec["sha256"]:raise RuntimeError("Frozen submission policy/contract changed")
    policy=json.loads((ROOT/plan["cycle_policy"]["path"]).read_text())
    if policy["cycle"]!=4 or policy["limits"]["jevbench_rounds"]!=2 or policy["limits"]["cpu_threads_per_worker"]!=2 or policy["limits"]["seconds_per_round"]!=600:raise RuntimeError("Separate finite submission bounds required")
    if (HERE/"launch-receipt.json").exists() or (HERE/"state.json").exists():raise RuntimeError("Never overwrite a launched or failed attempt")
    for rel,expected in plan["source_sha256"].items():
        if sha(ROOT/rel)!=expected:raise RuntimeError("Frozen candidate source changed: "+rel)
    if (HERE/"decisions.jsonl").exists():
        raise RuntimeError("Refuse to overwrite measured evidence")
    cpus = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0,cpus)
    for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","RAYON_NUM_THREADS"]:
        os.environ[key] = "2"
    modules = official_modules()
    tasks = []
    for cohort in ["original","hard"]:
        path = ROOT/"data/jevbench"/(cohort+".jsonl")
        if sha(path)!=plan["input_files"][str(path.relative_to(ROOT))]:
            raise RuntimeError("Frozen public source changed")
        values = [modules["tasks"].Task.from_dict(json.loads(line)) for line in path.read_text().splitlines()]
        if [task.id for task in values]!=plan["ids"][cohort]:
            raise RuntimeError("Frozen available public IDs changed")
        tasks.extend((cohort,task) for task in values)
    (HERE/"wire").mkdir(exist_ok=False)
    save(HERE/"tasks.json",[{"cohort":cohort,"task":json.loads(task.to_json())} for cohort,task in tasks])
    save(HERE/"launch-receipt.json",{"status":"launched","pid":os.getpid(),"at":datetime.now(timezone.utc).isoformat(),"plan_sha256":sha(HERE/"plan.json"),"cycle_policy_sha256":plan["cycle_policy"]["sha256"],"max_seconds":600,"cpu_affinity":cpus})
    initialization = time.perf_counter()
    engine = CompositeEngine(HERE/"rules.py")
    if engine.receipt["binary_sha256"]!=plan["native_candidate"]["binary_sha256"]:
        engine.close()
        raise RuntimeError("Actual native binary differs from frozen baseline")
    native_initialization_ms = (time.perf_counter()-initialization)*1000
    save(HERE/"native-process.json",{"pid":engine.native.process.pid,"parent_pid":os.getpid(),"affinity":sorted(os.sched_getaffinity(engine.native.process.pid)),"receipt":engine.receipt})
    httpd = server.make_server(engine,port=0,audit_path=HERE/"server-audit.jsonl")
    thread = threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{httpd.server_port}"
    adapter = modules["adapters.typesafe"].TypeSafeAdapter(endpoint=endpoint,model=engine.name,key_env="",timeout_s=60)
    rows = []
    try:
        warmup = run_task(adapter,tasks[0][1],tasks[0][0],0,True,modules["scoring"])
        save(HERE/"cold.json",{"native_initialization_ms":native_initialization_ms,"first_http_request":warmup,"scored_in_denominator":False})
        with (HERE/"decisions.jsonl").open("x") as stream:
            consecutive_errors = 0
            for index,(cohort,task) in enumerate(tasks):
                if time.perf_counter()-started>plan["resources"]["max_wall_seconds"]-5:
                    raise TimeoutError("Frozen ten-minute wall bound reached")
                row = run_task(adapter,task,cohort,index,False,modules["scoring"])
                rows.append(row)
                stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+"\n")
                stream.flush()
                consecutive_errors = consecutive_errors+1 if not row["ok"] else 0
                if row["http_status"] in [401,403,429] or consecutive_errors>=3:
                    raise RuntimeError("Official-style infrastructure stop; no retries")
                if (index+1)%20==0:
                    save(HERE/"state.json",{"status":"running","done":index+1,"total":len(tasks),"updated_at":datetime.now(timezone.utc).isoformat(),"official_rank":None,"goal_met":False})
                    print(json.dumps({"done":index+1,"total":len(tasks)}),flush=True)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        engine.close()
    save(HERE/"native-worker-cleanup.json",{"status":"complete","native_pid":engine.native.process.pid,"native_returncode":engine.native.process.poll(),"native_worker_absent":not Path("/proc",str(engine.native.process.pid)).exists()})
    summaries = {}
    for cohort in ["original","hard","all"]:
        selected = [row for row in rows if cohort=="all" or row["cohort"]==cohort]
        correct = sum(row["official_score"]["correct"] is True for row in selected)
        summaries[cohort] = {"n":len(selected),"correct":correct,"accuracy":correct/len(selected),
            "errors":sum(not row["ok"] for row in selected),"valid":sum(row["official_score"]["valid"] for row in selected),
            "strict_valid":sum(row["official_score"]["strict_valid"] for row in selected),"renormalized":sum(row["official_score"]["renormalized"] for row in selected),
            "end_to_end_http":percentiles([row["runner_wall_ms"] for row in selected]),
            "adapter_internal":percentiles([row["adapter_internal_ms"] for row in selected])}
    source_paths = [ROOT/relative for relative in plan["source_sha256"]]
    result = {"scope":plan["scope"],"complete":len(rows)==183,"metrics":summaries,"native_receipt":engine.receipt,
        "cold_initialization_ms":native_initialization_ms,"first_http_request_ms":warmup["runner_wall_ms"],"scored_requests":len(rows),"warmup_requests":1,
        "wire_records":len(rows)+1,"official_scorer_executed":True,"official_route":"/v1/systemone","cpu_affinity":cpus,
        "python":sys.version,"elapsed_seconds":time.perf_counter()-started,"source_sha256":{str(path.relative_to(ROOT)):sha(path) for path in source_paths},
        "plan_sha256":sha(HERE/"plan.json"),"market_token_price":None,"Capability":None,"official_rank":None,"goal_met":False,
        "release_gap":plan["release_gap"],"latency_caution":"Local CPU2 loopback measurement with transparent byte capture and concurrent workspace load; not matching official current-draw latency."}
    save(HERE/"results.json",result)
    save(HERE/"state.json",{"status":"complete","done":len(rows),"total":183,"updated_at":datetime.now(timezone.utc).isoformat(),"official_rank":None,"goal_met":False})
    print(json.dumps(summaries,indent=2),flush=True)


if __name__=="__main__":
    try:
        main()
    except Exception as error:
        failure={"status":"failed","error":type(error).__name__+": "+str(error),"updated_at":datetime.now(timezone.utc).isoformat(),"official_rank":None,"goal_met":False}
        save(HERE/("failed-attempt-"+str(time.time_ns())+".json"),failure)
        if not (HERE/"state.json").exists():save(HERE/"state.json",failure)
        raise
