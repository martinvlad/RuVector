"""E44 source/owner/slot admission and safe capture; no model imports."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import time
import shutil

EPOCH = 44
KIND = "REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT"
BASE = "02ed8c9567255f862776f7a983b9d3ed9142e56e"
W = Path("/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725")
ROOT = W / "project"
HERE = ROOT / "experiments/sota-2026-10-22/runtime/epoch44"
CANDIDATE = HERE
NATIVE_ROOT = Path("/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f/project")
BINARY_SHA = "ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e"
ARMS = ["qwen_native_joint_context", "qwen_lexical_joint_context", "qwen_source_order_joint_context"]
DOCS = [357, 227, 46, 212]
HYPS = ["nda-1", "nda-10", "nda-16"]
CASES = [f"contractnli:eced6528:test:{d}:{h}" for d in DOCS for h in HYPS]
_PLAN = None
_PINS = None


def require(value, code):
    if not value: raise RuntimeError(code)


def no_symlink(path):
    p = Path(path)
    require(p.is_absolute(), "ABSOLUTE_PATH_REQUIRED")
    require(not any(q.is_symlink() for q in (p, *p.parents)), "SYMLINK_REFUSED")
    return p


def sha(path):
    h = hashlib.sha256()
    with no_symlink(path).open("rb") as f:
        for b in iter(lambda: f.read(8388608), b""): h.update(b)
    return h.hexdigest()


def checked(relative):
    require(type(relative) is str and not Path(relative).is_absolute() and
            all(x not in ("", ".", "..") for x in relative.split("/")), "RELATIVE_SOURCE_PATH")
    return no_symlink(ROOT / relative)


def pairs(items):
    d = {}
    for k, v in items:
        require(k not in d, "DUPLICATE_JSON_KEY"); d[k] = v
    return d


def read(path):
    return json.loads(no_symlink(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def read_json_line(text): return json.loads(text, object_pairs_hook=pairs)


def put(path, value):
    p = no_symlink(path); p.parent.mkdir(parents=True, exist_ok=True)
    b = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f: f.write(b); f.flush(); os.fsync(f.fileno())
    return ref(p)


def ref(path):
    p = no_symlink(path)
    if ROOT in p.parents:
        return {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)}
    external = W / 'private/run'
    require(external in p.parents, 'PRIVATE_CAPTURE_REFERENCE_SCOPE')
    return {"path":str(p.relative_to(external)), "reference_root":"external_run_directory",
            "bytes":p.stat().st_size,"sha256":sha(p)}


def resolve_ref(row):
    relative = row['path']
    require(type(relative)is str and not Path(relative).is_absolute() and
            all(x not in ('','.','..')for x in relative.split('/')), 'REFERENCE_RELATIVE_PATH')
    base = W/'private/run' if row.get('reference_root')=='external_run_directory' else ROOT
    require('reference_root'not in row or row['reference_root']=='external_run_directory', 'REFERENCE_ROOT')
    return no_symlink(base/relative)


def sha_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                                    sort_keys=True, allow_nan=False).encode()).hexdigest()


def proc(pid):
    try:
        p = Path("/proc") / str(pid); a = (p / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": int(pid), "state": a[0], "ppid": int(a[1]), "pgid": int(a[2]),
                "sid": int(a[3]), "ticks": int(a[19]),
                "exit_wait_status": int(a[49]) if len(a) >= 50 else None}
    except (FileNotFoundError, ProcessLookupError): return None


def stable_identity(observation):
    return {'pid':observation['pid'],'startticks':observation['ticks'],
            'pgid':observation['pgid'],'sid':observation['sid']}


def owner_fence(plan=None):
    p = plan or _PLAN
    require(type(p) is dict, "BOUND_OPERATIONAL_PLAN_REQUIRED")
    row = p["owner_ref"]
    relative = row["path"]
    require(type(relative) is str and not Path(relative).is_absolute() and
            all(x not in ("", ".", "..") for x in relative.split("/")), "OWNER_RELATIVE_PATH")
    file = no_symlink(W / relative)
    require(sha(file) == row["sha256"] and file.stat().st_size == row["bytes"], "OWNER_BYTES")
    owner = read(file); slot = p["worker_slot_reservation"]
    require(owner["generation"] == slot["generation"] and owner["pid"] == slot["pid"] and
            owner["startticks"] == slot["startticks"] and row["sha256"] == slot["owner_sha256"],
            "OPERATIONAL_OWNER_SLOT_BINDING")
    state = proc(owner["pid"])
    require(state and state["state"] not in ("Z", "X") and state["ticks"] == owner["startticks"]
            and time.time() < owner["expires_unix"] and not (file.parent / "release.request").exists(), "OWNER_LOST")
    require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == owner["kernel_boot_id"]
            and os.readlink(f"/proc/{owner['pid']}/ns/pid") == owner["PID_namespace"], "OWNER_BOOT_NS")
    lock = Path(f"/proc/{owner['pid']}/fd/3").stat()
    require((lock.st_dev, lock.st_ino) == (owner["lock_device"], owner["lock_inode"]), "OWNER_LOCK_FD")
    held = False
    for line in Path("/proc/locks").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 6 and fields[1:5] == ["FLOCK", "ADVISORY", "WRITE", str(owner["pid"])]:
            major, minor, inode = fields[5].split(":")
            held = (os.makedev(int(major,16),int(minor,16)),int(inode)) == (owner["lock_device"],owner["lock_inode"])
    require(held,"OWNER_LOCK_NOT_HELD")
    return owner


def load_module(name, path):
    p = no_symlink(path)
    if _PLAN is not None:
        row = next((r for r in _PINS if checked(r["path"]) == p), None)
        require(row and p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], "UNPINNED_IMPORT")
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def remaining(deadline):
    value = deadline - time.monotonic()
    require(value > 0, "WORKER_SOFT_DEADLINE")
    return value


def host_admission(plan):
    g = Path('/sys/fs/cgroup')
    limit = int((g/'memory.max').read_text()); current = int((g/'memory.current').read_text())
    s = dict((k,int(v)) for k,v in (line.split() for line in (g/'memory.stat').read_text().splitlines()))
    keys = {'file','shmem','active_file','inactive_file','file_dirty','file_writeback'}
    require(keys <= set(s) and all(s[k]>=0 for k in keys) and s['file']>=s['shmem'], 'MEMORY_STAT_UNKNOWN')
    clean=max(0,min(s['file']-s['shmem'],s['active_file']+s['inactive_file'])-s['file_dirty']-s['file_writeback'])
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    headroom=min(limit,available,max(0,limit-current+clean))
    workspace=shutil.disk_usage('/workspace').free; temporary=shutil.disk_usage('/tmp').free
    resident=no_symlink(plan['gguf_path']).stat()
    require(str(plan['gguf_path']).startswith('/dev/shm/ruvector-epoch43-cab16abb5795/') and
            resident.st_dev==26 and resident.st_size==2497281120 and resident.st_blocks*512>=resident.st_size, 'RESIDENT_SHMEM_MODEL_IDENTITY')
    require(limit>=17179869184 and headroom>=4294967296 and workspace>=67108864
            and temporary>=268435456, 'MODEL_RESOURCE_ADMISSION_FAILED')
    return {'cgroup_limit_bytes':limit,'memory_current_bytes':current,
            'reclaim_adjusted_headroom_bytes':headroom,'shmem_credit_excluded':True,
            'already_charged_resident_GGUF_bytes':resident.st_size,'additional_required_headroom_bytes':4294967296,
            'workspace_free_bytes':workspace,'workspace_measurement_path':'/workspace',
            'tmp_free_bytes':temporary,'tmp_measurement_path':'/tmp'}


def verify_post_data(data, review, dispatch, source, expected_sha, freeze_sha):
    require(data.get('epoch')==44 and data.get('kind')==KIND and data.get('phase')=='dev'
            and data.get('status')=='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT'
            and data.get('errors')==[] and data.get('selected_ids')==CASES, 'DATA_ADMISSION_NOT_SUCCESSFUL')
    require(data.get('source_checkpoint')==BASE and data.get('source_commit')==dispatch['source_commit']
            and data.get('source_plan_sha256')==expected_sha and data.get('source_freeze_sha256')==freeze_sha,
            'DATA_ADMISSION_SOURCE_BINDING')
    require(type(data.get('semantic_gold_values_decoded'))is int and data['semantic_gold_values_decoded']==0
            and data.get('selected_raw_choice_tokens_copied')==12
            and type(data.get('protected_confirmation_body_or_choice_decodes'))is int
            and data['protected_confirmation_body_or_choice_decodes']==0
            and data.get('used_confirmation_identities')==[], 'DATA_ADMISSION_ROLE_BOUNDARY')
    require(data.get('private_features')==dispatch['private_features_ref'] and
            data['evidence']['source_admission']==dispatch['source_admission'] and
            data['evidence']['source_plan']['sha256']==expected_sha, 'DATA_ADMISSION_FEATURE_AND_PLAN')
    require(review.get('epoch')==44 and review.get('kind')==KIND and review.get('checks_passed')is True
            and review.get('data_admission')==dispatch['data_admission']
            and review.get('private_features_ref')==dispatch['private_features_ref']
            and review.get('source_commit')==dispatch['source_commit']
            and review.get('source_plan_sha256')==expected_sha
            and type(review.get('semantic_gold_decodes'))is int and review['semantic_gold_decodes']==0
            and type(review.get('protected_unused_body_or_choice_decodes'))is int
            and review['protected_unused_body_or_choice_decodes']==0, 'INDEPENDENT_DATA_ADMISSION_NOT_SUCCESSFUL')
    require(data['statistics']['unique_source_units']==dispatch['source_units_total']
            and data['statistics']['expanded_pair_source_units']==3*dispatch['source_units_total'],
            'DATA_ADMISSION_UNIT_BINDING')


def admit(plan_path, expected_sha, admission_path):
    global _PLAN, _PINS
    require(Path(plan_path) == ROOT / "experiments/sota-2026-10-22/epoch44/plan.json"
            and sha(plan_path) == expected_sha, "PLAN_IDENTITY")
    p = read(plan_path); dispatch = read(admission_path)
    require(dispatch.get("dispatch_authorized") is True, "POST_DATA_DISPATCH_NOT_AUTHORIZED")
    require(dispatch["source_plan_sha256"] == expected_sha, "DISPATCH_PLAN_HASH")
    source_ref = dispatch["source_admission"]
    source_file = resolve_ref(source_ref)
    require(source_ref["path"] == p["source_admission_path"] and sha(source_file) == source_ref["sha256"]
            and source_file.stat().st_size == source_ref["bytes"], "SOURCE_ADMISSION_REF")
    a = read(source_file)
    require(p["epoch"] == 44 and p["kind"] == KIND and p["source_checkpoint"] == BASE
            and p["source_bindings_ready"] is True and p["arms"] == ARMS
            and p["data_roles"] == {"train": [], "dev": CASES, "calibration": [], "confirmation": []},
            "PLAN_SCOPE")
    require(p["full_prompt_token_cap"] == 767 and p["server_context_size"] == 1024
            and p["completion_readouts"] == 36 and p["derived_forecasts"] == 36, "PLAN_READER_CAPS")
    slot = p["worker_slot_reservation"]
    require(p["worker_slot_reservation"] == slot == a["worker_slot_reservation"] == dispatch["worker_slot_reservation"], "BURNED_SLOT_BINDING")
    require(type(slot["generation"]) is int and slot["generation"] >= 4 and slot["owner_sha256"] == p["owner_ref"]["sha256"] and
            re.fullmatch(r"[0-9a-f]{64}", slot["reservation_token"]) and
            slot["permanently_burned_at_SOURCE_publication"] is True, "SLOT_OWNER_CAPABILITY")
    require(a["epoch"] == 44 and a["kind"] == KIND and a["phase"] == "dev" and
            a["plan_sha256"] == expected_sha and a["source_freeze_sha256"] == p["source_freeze"]["sha256"]
            and a.get('checks_passed')is True and a["verified_actual_remote_readback"] is True and
            a['actual_source_commit']==a['published_source_commit']==a['source_commit'] and
            a['source_plan_sha256']==a['plan_sha256']==expected_sha and
            re.fullmatch(r"[0-9a-f]{40}", a["actual_source_commit"]), "ACTUAL_SOURCE_READBACK_REQUIRED")
    freeze = checked(p["source_freeze"]["path"])
    require(sha(freeze) == p["source_freeze"]["sha256"], "SOURCE_FREEZE_BYTES")
    freeze_data = read(freeze)
    _PINS = freeze_data["files"]
    require(type(_PINS) is list and len({r["path"] for r in _PINS}) == len(_PINS), "SOURCE_PIN_LIST")
    for row in _PINS:
        file = checked(row["path"])
        require(file.stat().st_size == row["bytes"] and sha(file) == row["sha256"], "FROZEN_SOURCE_CHANGED")
    require(dispatch["source_freeze_sha256"] == p["source_freeze"]["sha256"] and
            dispatch["source_commit"] == a["actual_source_commit"], "DISPATCH_SOURCE_READBACK_BINDING")
    for role in ("data_admission", "independent_data_admission"):
        row = dispatch[role]
        file = resolve_ref(row)
        require(sha(file) == row["sha256"] and file.stat().st_size == row["bytes"],
                "POST_DATA_ADMISSION_REF")
    require(dispatch['data_admission']['path']==p['data_admission_path'], 'FROZEN_POST_DATA_ADMISSION_PATH')
    data = read(resolve_ref(dispatch["data_admission"]))
    review = read(resolve_ref(dispatch['independent_data_admission']))
    verify_post_data(data,review,dispatch,a,expected_sha,p['source_freeze']['sha256'])
    features = dispatch["private_features_ref"]
    require(features["path"] == p["private_features_path"] and
            sha(features["path"]) == features["sha256"] and Path(features["path"]).stat().st_size == features["bytes"],
            "POST_DATA_FEATURE_REF")
    counts = dispatch["source_units_per_document"]
    require(set(counts) == {str(d) for d in DOCS} and all(type(n) is int and 1 <= n <= 1024 for n in counts.values())
            and sum(counts.values()) == dispatch["source_units_total"], "POST_DATA_SOURCE_COUNTS")
    owner_fence(p)
    view = dict(p)
    view.update(_plan_sha=expected_sha, _dispatch_admission_path=str(admission_path),
                private_features=features, source_units_per_document=counts,
                source_units_total=dispatch["source_units_total"])
    _PLAN = view
    table = load_module("e44_admitted_counter_formula", HERE / "counters.py").expected_fixed(counts)
    require(table == dispatch["expected_operation_counters"]["dev"], "POST_DATA_COUNTER_FORMULA")
    return view


def child_env(plan):
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "TOKENIZERS_PARALLELISM": "false",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "E44_PROJECT": str(ROOT), "E44_PLAN": str(ROOT / "experiments/sota-2026-10-22/epoch44/plan.json"),
            "E44_PLAN_SHA": plan["_plan_sha"], "E44_ADMISSION": plan["_dispatch_admission_path"],
            "E44_NATIVE_ROOT": str(NATIVE_ROOT), "E44_EXTERNAL_RUN": plan["external_run_directory"],
            "E44_ROLE": "dev"}
