"""Acquire one immutable diagnostic checkpoint only after root preparation go.

Default mode prints a byte/pin plan and performs no network calls. Execution
requires a root-authored permit binding the reviewed source manifest SHA256,
source Git commit, exact checkpoint/weight identity, and DEV-only contract.
This helper never imports torch, transformers, tokenizers or safetensors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import urllib.request

SOURCE_GIT_COMMIT = "b7f8285206189ba1ee0de95057957585ac097874"
REPOSITORY = "mrm8488/ModernBERT-large-ft-all-nli"
REVISION = "afa5e4b89a8a23d3b19da2ed0fa7daf2496c7c47"
WEIGHT_SHA256 = "a00110cace66b50896ea585c3aa4385812c5cd201d7fd948b1b04239d9b68af4"
WEIGHT_BYTES = 1583355740
HERE = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object: " + str(path))
    return value


def verify_source_manifest(path: Path) -> dict:
    manifest = read_object(path)
    if manifest.get("source_git_commit") != SOURCE_GIT_COMMIT:
        raise ValueError("Reviewed source Git commit differs from the frozen checkpoint")
    files = manifest.get("files", [])
    expected_names = set(manifest.get("required_source_files", []))
    if not files or {item["path"] for item in files} != expected_names:
        raise ValueError("Source manifest closure is incomplete or duplicated")
    if len(files) != len(expected_names):
        raise ValueError("Duplicate source-manifest entries")
    for item in files:
        target = HERE / item["path"]
        if target.is_symlink() or target.resolve().parent != HERE:
            raise ValueError("Source closure must contain direct regular files")
        if target.stat().st_size != item["bytes"] or sha256_file(target) != item["sha256"]:
            raise ValueError("Reviewed source file mismatch: " + item["path"])
    return manifest


def verify_permit(permit_path: Path, manifest_path: Path, plan: dict) -> dict:
    permit = read_object(permit_path)
    expected = {
        "preparation_go": True,
        "source_git_commit": SOURCE_GIT_COMMIT,
        "source_manifest_sha256": sha256_file(manifest_path),
        "repository": REPOSITORY,
        "revision": REVISION,
        "weight_sha256": WEIGHT_SHA256,
        "weight_bytes": WEIGHT_BYTES,
        "diagnostic_only": True,
        "confirmation_ids": [],
        "training_ids": [],
        "calibration_ids": [],
        "max_pair_tokens": 512,
        "attention": "sdpa",
        "allow_model_initialization": False,
    }
    for key, value in expected.items():
        if permit.get(key) != value:
            raise ValueError("Root preparation permit mismatch: " + key)
    if permit.get("acquisition_plan_sha256") != sha256_file(HERE / "asset-acquisition-plan.json"):
        raise ValueError("Root permit does not bind the reviewed acquisition plan")
    if plan.get("repository") != REPOSITORY or plan.get("revision") != REVISION:
        raise ValueError("Acquisition plan checkpoint mismatch")
    return permit


def verify_file_identity(path: Path, item: dict) -> dict:
    if path.stat().st_size != item["bytes"]:
        raise ValueError("Downloaded byte count mismatch: " + item["path"])
    digest = sha256_file(path)
    if item.get("sha256") and digest != item["sha256"]:
        raise ValueError("Publisher SHA256 mismatch: " + item["path"])
    if item.get("git_blob_sha1"):
        blob = hashlib.sha1()
        blob.update(("blob " + str(item["bytes"]) + "\0").encode())
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                blob.update(chunk)
        if blob.hexdigest() != item["git_blob_sha1"]:
            raise ValueError("Publisher Git blob identity mismatch: " + item["path"])
    return {"path": item["path"], "bytes": item["bytes"], "sha256": digest,
            "publisher_sha256": item.get("sha256"),
            "publisher_git_blob_sha1": item.get("git_blob_sha1")}


def inspect_safetensors_header(path: Path) -> dict:
    """Parse the bounded JSON header, without tensor loading or pickle."""
    with path.open("rb") as handle:
        length_bytes = handle.read(8)
        if len(length_bytes) != 8:
            raise ValueError("Missing safetensors header length")
        length = struct.unpack("<Q", length_bytes)[0]
        if length <= 0 or length > 32 * 1024 * 1024:
            raise ValueError("Safetensors header is outside the static bound")
        header = json.loads(handle.read(length))
    tensors = {key: value for key, value in header.items() if key != "__metadata__"}
    classifier = tensors.get("classifier.weight")
    if not classifier or classifier.get("shape") != [3, 1024] or classifier.get("dtype") != "F32":
        raise ValueError("Checkpoint is not the pinned native FP32 three-way classifier")
    floating_dtypes = sorted({value["dtype"] for value in tensors.values() if value["dtype"].startswith(("F", "BF"))})
    if floating_dtypes != ["F32"]:
        raise ValueError("Checkpoint contains unexpected floating tensor precision")
    payload_bytes = path.stat().st_size - 8 - length
    intervals = []
    for name, value in tensors.items():
        start, end = value["data_offsets"]
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= payload_bytes):
            raise ValueError("Invalid safetensors offset: " + name)
        intervals.append((start, end))
    intervals.sort()
    if not intervals or intervals[0][0] != 0 or intervals[-1][1] != payload_bytes:
        raise ValueError("Safetensors data coverage differs from the complete payload")
    if any(previous[1] != following[0] for previous, following in zip(intervals, intervals[1:])):
        raise ValueError("Safetensors tensor data is overlapping or has gaps")
    return {"header_bytes": length, "tensor_count": len(tensors),
            "native_classifier_shape": classifier["shape"],
            "floating_dtypes": floating_dtypes,
            "model_loaded_or_initialized": False}


def acquire(plan: dict, destination: Path, manifest_path: Path, permit_path: Path) -> dict:
    verify_source_manifest(manifest_path)
    permit = verify_permit(permit_path, manifest_path, plan)
    if destination.exists():
        raise ValueError("Destination already exists; no reuse, retry or resume is automatic")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=destination.name + ".acquiring-", dir=destination.parent))
    received_bytes = 0
    files = []
    try:
        for item in plan["files"]:
            target = stage / item["path"]
            if item.get("metadata_local_path"):
                origin = HERE / item["metadata_local_path"]
                shutil.copyfile(origin, target)
            else:
                url = "https://huggingface.co/" + REPOSITORY + "/resolve/" + REVISION + "/" + item["path"]
                request = urllib.request.Request(url, headers={"User-Agent": "ruvector-epoch26-metadata-pinned-acquisition"})
                with urllib.request.urlopen(request, timeout=45) as response, target.open("xb") as output:
                    while True:
                        chunk = response.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        received_bytes += len(chunk)
                        output.write(chunk)
                        if output.tell() > item["bytes"]:
                            raise ValueError("Asset exceeded frozen byte count: " + item["path"])
            files.append(verify_file_identity(target, item))
        check = inspect_safetensors_header(stage / "model.safetensors")
        lock = {
            "schema_version": 1, "repository": REPOSITORY, "revision": REVISION,
            "source_git_commit": SOURCE_GIT_COMMIT,
            "source_manifest_sha256": sha256_file(manifest_path),
            "acquisition_plan_sha256": sha256_file(HERE / "asset-acquisition-plan.json"),
            "root_preparation_permit_sha256": sha256_file(permit_path),
            "diagnostic_only": True, "confirmation_ids": [], "training_ids": [],
            "calibration_ids": [], "fitting_or_calibration": False,
            "model_initializations": 0, "tokenizer_initializations": 0,
            "reader_contract": {"max_pair_tokens": permit["max_pair_tokens"],
                                "attention": permit["attention"], "batch_size": 1,
                                "truncation": "only_first", "precision": "FP32",
                                "reference_compile": False, "cpu_threads": 2,
                                "interop_threads": 1, "raw_labels": ["E", "N", "C"],
                                "canonical_permutation": [0, 2, 1], "temperature": 1},
            "license_provenance": plan["license_provenance"],
            "static_tensor_check": check, "files": files,
            "downloaded_bytes": received_bytes,
            "copied_metadata_bytes": sum(item["bytes"] for item in plan["files"] if item.get("metadata_local_path")),
            "HTTP_retries_or_model_sessions": 0,
            "launch_admission": "PENDING_ROOT_AND_INDEPENDENT_SOURCE_ASSET_REVIEW",
        }
        (stage / "asset-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
        os.rename(stage, destination)
        return lock
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-manifest", type=Path, default=HERE / "implementation-source-manifest.json")
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    plan = read_object(HERE / "asset-acquisition-plan.json")
    if not args.execute:
        print(json.dumps({"mode": "PLAN_ONLY_NO_NETWORK_OR_INIT", "repository": REPOSITORY,
                          "revision": REVISION, "weight_bytes": WEIGHT_BYTES,
                          "weight_sha256": WEIGHT_SHA256,
                          "total_asset_bytes": sum(item["bytes"] for item in plan["files"]),
                          "planned_download_bytes": sum(item["bytes"] for item in plan["files"] if not item.get("metadata_local_path")),
                          "files": [item["path"] for item in plan["files"]]}, indent=2))
        return
    if args.permit is None or args.destination is None:
        parser.error("--execute requires a reviewed --permit and an unused --destination")
    lock = acquire(plan, args.destination.resolve(), args.source_manifest.resolve(), args.permit.resolve())
    print(json.dumps({"destination": str(args.destination), "downloaded_bytes": lock["downloaded_bytes"],
                      "model_initializations": 0, "tokenizer_initializations": 0,
                      "asset_lock_sha256": sha256_file(args.destination / "asset-lock.json")}, indent=2))


if __name__ == "__main__":
    main()
