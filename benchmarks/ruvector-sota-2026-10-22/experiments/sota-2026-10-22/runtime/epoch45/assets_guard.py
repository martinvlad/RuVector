"""Fresh GGUF/CPU binary/runtime/native hashes, never model initialization."""
import hashlib
from pathlib import Path
import stat
import struct
import time

GGUF_BYTES = 2497281120
GGUF_SHA = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
CPU_TAR_SHA = "cf07c1c112d709bd67e522017471de57ed0ec8bea031d732c5422351c07f65ac"


def gguf_metadata(path):
    maximum = 33554432
    used = 0
    with Path(path).open("rb") as f:
        def take(n):
            nonlocal used
            if n < 0 or used + n > maximum: raise ValueError("GGUF_METADATA_CAP")
            value = f.read(n); used += len(value)
            if len(value) != n: raise ValueError("GGUF_SHORT_METADATA")
            return value
        def unpack(fmt): return struct.unpack("<" + fmt, take(struct.calcsize("<" + fmt)))[0]
        def string():
            n = unpack("Q")
            if n > 16777216: raise ValueError("GGUF_STRING_CAP")
            return take(n).decode("utf-8")
        def value(kind, depth=0):
            if depth > 2: raise ValueError("GGUF_NESTING")
            formats = {0:"B",1:"b",2:"H",3:"h",4:"I",5:"i",6:"f",7:"?",10:"Q",11:"q",12:"d"}
            if kind in formats: return unpack(formats[kind])
            if kind == 8: return string()
            if kind == 9:
                child, length = unpack("I"), unpack("Q")
                if length > 500000: raise ValueError("GGUF_ARRAY_CAP")
                for _ in range(length): value(child, depth + 1)
                return {"array_length": length, "element_type": child}
            raise ValueError("GGUF_METADATA_TYPE")
        if take(4) != b"GGUF" or unpack("I") != 3: raise ValueError("GGUF_VERSION")
        tensors, count = unpack("Q"), unpack("Q")
        if tensors > 5000 or count > 1000: raise ValueError("GGUF_HEADER_COUNTS")
        metadata = {}
        for _ in range(count):
            key = string()
            if key in metadata: raise ValueError("GGUF_DUPLICATE_KEY")
            metadata[key] = value(unpack("I"))
    expected = {"general.architecture":"qwen3", "qwen3.block_count":36,
                "qwen3.embedding_length":2560, "qwen3.attention.head_count":32,
                "qwen3.attention.head_count_kv":8}
    if any(metadata.get(k) != v for k, v in expected.items()): raise ValueError("GGUF_ARCHITECTURE")
    tokens = metadata.get("tokenizer.ggml.tokens", {})
    if tokens.get("array_length") != 151936: raise ValueError("GGUF_VOCAB_SIZE")
    template = metadata.get("tokenizer.chat_template")
    return {"metadata_bytes_read": used, "tensor_count": tensors, "metadata_count": count,
            "architecture": expected, "vocab_size": tokens["array_length"],
            "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest() if type(template) is str else None,
            "model_initialized": False, "learned_three_way_head": False}


def verify(C, plan):
    started = time.monotonic()
    path = C.no_symlink(plan["gguf_path"])
    C.require(path.stat().st_size == GGUF_BYTES and not path.stat().st_mode & 0o222,
              "GGUF_SIZE_READONLY")
    C.require(C.sha(path) == GGUF_SHA, "GGUF_REAL_SHA256")
    metadata = gguf_metadata(path)
    tar = C.no_symlink(plan["cpu_runtime_tar_path"])
    C.require(tar.stat().st_size == 17851611 and C.sha(tar) == CPU_TAR_SHA, "CPU_PUBLISHER_TAR")
    manifest = C.read(C.checked(plan["cpu_runtime_manifest"]["path"]))
    C.require(C.sha(C.checked(plan["cpu_runtime_manifest"]["path"])) ==
              plan["cpu_runtime_manifest"]["sha256"], "CPU_RUNTIME_MANIFEST_PIN")
    files = manifest["files"]
    C.require(type(files) is list and 1 <= len(files) <= 512, "CPU_RUNTIME_FILE_SET")
    root = C.no_symlink(plan["cpu_runtime_directory"])
    observed = []
    for row in files:
        file = C.no_symlink(root / row["path"])
        C.require(root in file.parents and stat.S_ISREG(file.stat().st_mode) and
                  not file.stat().st_mode & 0o222 and file.stat().st_size == row["bytes"] and
                  C.sha(file) == row["sha256"], "CPU_RUNTIME_REAL_FILE")
        observed.append(row["path"])
    C.require(sorted(observed) == sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file()),
              "CPU_RUNTIME_INVENTORY")
    C.require(C.no_symlink(plan["llama_server_path"]) in [root / r["path"] for r in files],
              "PINNED_SERVER_EXECUTABLE")
    lock = C.read(C.checked(plan["native_runtime_lock"]["path"]))
    C.require(C.sha(C.checked(plan["native_runtime_lock"]["path"])) ==
              plan["native_runtime_lock"]["sha256"], "INHERITED_RUNTIME_LOCK_PIN")
    guard = C.load_module("e45_fresh_python_native_guard", C.HERE / "python_native_guard.py")
    receipt = guard.verify_runtime_files(Path(lock["external_environment"]),
                C.checked(lock["python_member_manifest"]["path"]), lock["python_member_manifest"]["sha256"],
                lock["assets"], root=C.ROOT, wheel_identity_path=C.checked(lock["python_wheel_lock"]["path"]),
                native_asset_root=C.NATIVE_ROOT)
    return {"epoch":45, "kind":C.KIND, "gguf_path":str(path), "gguf_bytes":GGUF_BYTES,
            "gguf_sha256":GGUF_SHA, "gguf_metadata":metadata, "CPU_runtime_files":len(files),
            "CPU_tar_sha256":CPU_TAR_SHA, "Python_native_runtime":receipt,
            "wall_seconds":time.monotonic()-started, "model_tokenizer_native_initializations":0}
