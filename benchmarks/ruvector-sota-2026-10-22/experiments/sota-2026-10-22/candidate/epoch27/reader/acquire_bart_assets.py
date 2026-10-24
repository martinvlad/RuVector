"""One-shot pinned original-BART acquisition, gated by a root preparation permit.

Default mode prints a plan and never opens a URL. This module uses stdlib only;
it never imports torch/transformers, parses pickle, constructs a tokenizer or
loads tensors. The weight file receives only a16-byte static header read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.request

HERE = Path(__file__).resolve().parent
BASE_CHECKPOINT = "6e4ad4ab0b6a09a6a1083335ed0401637227d17f"
DURABLE_LEASE_CHECKPOINT = "4fed2fd4d8d94df71d52ac47c61c6f59ffbd2a67"
REPOSITORY = "facebook/bart-large-mnli"
REVISION = "d7645e127eaf1aefc7862fd59a17a5aa8558b8ce"
WEIGHT_NAME = "pytorch_model.bin"
WEIGHT_BYTES = 1629486723
WEIGHT_SHA256 = "ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17"
LEASE_PID = 75591
LEASE_START_TICKS = 15190845
MIN_DISK_RESERVE_BYTES = 64 * 1024 * 1024
ACQUISITION_SECONDS_CAP = 300
REQUIRED_SOURCE_FILES = frozenset({
    "bart_reader.py", "acquire_bart_assets.py", "asset-acquisition-plan.json",
    "test_bart_reader.py", "prepare-permit.example.json", "pinned-config.json",
    "pinned-card.md", "LICENSE.fairseq", "IMPLEMENTATION_NOTES.md",
})
REQUIRED_ASSETS = frozenset({
    "README.md", "LICENSE.fairseq", "config.json", WEIGHT_NAME,
    "tokenizer.json", "tokenizer_config.json", "merges.txt", "vocab.json",
})


def read_object(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("JSON source must be a regular file")
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict):
        raise ValueError("Expected a JSON object")
    return obj


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_absolute_path(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("An absolute path is required")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink path components are forbidden")
    return path.resolve()


def verify_source_manifest(path: Path) -> dict:
    manifest = read_object(path)
    checkpoint = manifest.get("source_git_commit", "")
    if checkpoint != DURABLE_LEASE_CHECKPOINT:
        raise ValueError("Source manifest must bind the actual published durable root lease checkpoint")
    if manifest.get("base_checkpoint") != BASE_CHECKPOINT:
        raise ValueError("Source manifest base checkpoint mismatch")
    files = manifest.get("files", [])
    names = [item["path"] for item in files]
    if len(names) != len(REQUIRED_SOURCE_FILES) or set(names) != REQUIRED_SOURCE_FILES:
        raise ValueError("Reviewed source closure is incomplete, duplicated or unexpected")
    for item in files:
        target = HERE / item["path"]
        if target.is_symlink() or not target.is_file() or target.resolve().parent != HERE:
            raise ValueError("Reviewed sources must be direct regular files")
        if target.stat().st_size != item["bytes"] or sha256_file(target) != item["sha256"]:
            raise ValueError("Reviewed source identity mismatch: " + item["path"])
    return manifest


def process_start_ticks(pid: int) -> int:
    # Linux stat field22; process comm may itself contain spaces/parentheses.
    stat = Path("/proc") / str(pid) / "stat"
    tail = stat.read_text().rsplit(") ", 1)[1].split()
    if tail[0] in ("Z", "X"):
        raise ValueError("Root lease process is no longer live")
    return int(tail[19])


def verify_plan(plan: dict) -> None:
    if plan.get("repository") != REPOSITORY or plan.get("revision") != REVISION:
        raise ValueError("Acquisition checkpoint mismatch")
    files = plan.get("files", [])
    names = [item["path"] for item in files]
    if len(names) != len(REQUIRED_ASSETS) or set(names) != REQUIRED_ASSETS:
        raise ValueError("Acquisition asset closure is incomplete, duplicated or unexpected")
    for item in files:
        name = item["path"]
        if not isinstance(item.get("bytes"), int) or item["bytes"] <= 0:
            raise ValueError("Positive exact asset bytes are required")
        if not item.get("sha256") and not item.get("git_blob_sha1"):
            raise ValueError("Every asset requires a publisher digest pin")
        if item.get("sha256") and not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid SHA256 pin")
        if item.get("git_blob_sha1") and not re.fullmatch(r"[0-9a-f]{40}", item["git_blob_sha1"]):
            raise ValueError("Invalid publisher Git blob pin")
        if item.get("metadata_local_path"):
            if item["metadata_local_path"] not in REQUIRED_SOURCE_FILES:
                raise ValueError("Local metadata origin is outside reviewed source closure")
        else:
            expected_url = "https://huggingface.co/" + REPOSITORY + "/resolve/" + REVISION + "/" + name
            if item.get("source_url") != expected_url:
                raise ValueError("Only the exact immutable public model URL is admitted")
    weight = next(item for item in files if item["path"] == WEIGHT_NAME)
    if weight.get("sha256") != WEIGHT_SHA256 or weight["bytes"] != WEIGHT_BYTES:
        raise ValueError("Original2020 .bin byte/hash pin changed")


def verify_permit(path: Path, manifest_path: Path, manifest: dict,
                  plan_path: Path, destination: Path) -> dict:
    permit = read_object(path)
    expected = {
        "preparation_go": True, "allow_network_asset_acquisition": True,
        "base_checkpoint": BASE_CHECKPOINT,
        "source_git_commit": manifest["source_git_commit"],
        "source_manifest_sha256": sha256_file(manifest_path),
        "acquisition_plan_sha256": sha256_file(plan_path),
        "repository": REPOSITORY, "revision": REVISION,
        "weight_sha256": WEIGHT_SHA256, "weight_bytes": WEIGHT_BYTES,
        "destination": str(destination), "diagnostic_only": True,
        "confirmation_ids": [], "training_ids": [], "calibration_ids": [],
        "max_pair_tokens": 512, "attention": "sdpa", "precision": "FP32",
        "cpu_threads": 2, "interop_threads": 1, "require_no_truncation": True,
        "use_safetensors": False, "weights_only": True,
        "allow_model_initialization": False, "allow_tokenizer_initialization": False,
        "acquisition_seconds_cap": ACQUISITION_SECONDS_CAP,
    }
    for key, value in expected.items():
        if type(permit.get(key)) is not type(value) or permit.get(key) != value:
            raise ValueError("Root preparation permit mismatch: " + key)
    expected_lease = {
        "pid": LEASE_PID, "start_ticks": LEASE_START_TICKS,
        "checkpoint": manifest["source_git_commit"],
    }
    if permit.get("lease") != expected_lease:
        raise ValueError("Permit does not bind the frozen physical root lease")
    if process_start_ticks(LEASE_PID) != LEASE_START_TICKS:
        raise ValueError("Physical root lease PID was reused or is absent")
    return permit


def reserve_attempt(destination: Path, record: dict) -> Path:
    """Persistent O_EXCL receipt consumes this destination even after a failure."""
    destination = checked_absolute_path(destination)
    if destination.exists():
        raise ValueError("Destination already exists; reuse/retry/resume is forbidden")
    if not destination.parent.is_dir():
        raise ValueError("Root must prepare the destination parent directory")
    receipt = destination.parent / ("." + destination.name + ".acquisition-attempt.json")
    try:
        with receipt.open("x") as handle:
            json.dump({"status": "STARTED", **record}, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ValueError("Persistent attempt receipt exists; retry/resume is forbidden") from error
    return receipt


def update_receipt(path: Path, record: dict) -> None:
    # The existing inode remains: a killed or partial update still blocks replay.
    with path.open("r+") as handle:
        handle.seek(0)
        json.dump(record, handle, indent=2)
        handle.write("\n")
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())


def verify_file_identity(path: Path, item: dict) -> dict:
    if path.stat().st_size != item["bytes"]:
        raise ValueError("Downloaded byte count mismatch: " + item["path"])
    digest = hashlib.sha256()
    blob = hashlib.sha1()
    blob.update(("blob " + str(item["bytes"]) + "\0").encode())
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
            blob.update(chunk)
    if item.get("sha256") and digest.hexdigest() != item["sha256"]:
        raise ValueError("Publisher SHA256 mismatch: " + item["path"])
    if item.get("git_blob_sha1") and blob.hexdigest() != item["git_blob_sha1"]:
        raise ValueError("Publisher Git blob mismatch: " + item["path"])
    return {
        "path": item["path"], "bytes": item["bytes"], "sha256": digest.hexdigest(),
        "publisher_sha256": item.get("sha256"),
        "publisher_git_blob_sha1": item.get("git_blob_sha1"),
        "source_url": item["source_url"],
    }


def acquire(destination: Path, manifest_path: Path, permit_path: Path) -> dict:
    destination = checked_absolute_path(destination)
    plan_path = HERE / "asset-acquisition-plan.json"
    plan = read_object(plan_path)
    verify_plan(plan)
    manifest = verify_source_manifest(manifest_path)
    permit = verify_permit(permit_path, manifest_path, manifest, plan_path, destination)
    total_bytes = sum(item["bytes"] for item in plan["files"])
    if shutil.disk_usage(destination.parent).free < total_bytes + MIN_DISK_RESERVE_BYTES:
        raise ValueError("Insufficient disk for one streamed copy and64MiB reserve")
    record = {
        "schema_version": 1, "epoch": 27, "repository": REPOSITORY, "revision": REVISION,
        "source_git_commit": manifest["source_git_commit"],
        "source_manifest_sha256": sha256_file(manifest_path),
        "permit_sha256": sha256_file(permit_path), "destination": str(destination),
        "lease": permit["lease"], "created_unix_ns": time.time_ns(),
        "network_retries": 0, "model_initializations": 0, "tokenizer_initializations": 0,
    }
    receipt = reserve_attempt(destination, record)
    stage = destination.parent / ("." + destination.name + ".acquiring")
    start = time.monotonic()
    downloaded_bytes = 0
    files = []
    stage_created = False
    try:
        stage.mkdir(mode=0o700)
        stage_created = True
        for item in plan["files"]:
            if time.monotonic() - start >= ACQUISITION_SECONDS_CAP:
                raise TimeoutError("Acquisition deadline")
            if process_start_ticks(LEASE_PID) != LEASE_START_TICKS:
                raise ValueError("Physical root lease changed during acquisition")
            target = stage / item["path"]
            if item.get("metadata_local_path"):
                source = HERE / item["metadata_local_path"]
                with source.open("rb") as source_handle, target.open("xb") as output:
                    shutil.copyfileobj(source_handle, output, 1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
            else:
                request = urllib.request.Request(
                    item["source_url"], headers={"User-Agent": "ruvector-epoch27-pinned-public-acquisition"},
                )
                remaining = ACQUISITION_SECONDS_CAP - (time.monotonic() - start)
                with urllib.request.urlopen(request, timeout=min(30, remaining)) as response, target.open("xb") as output:
                    if response.status != 200:
                        raise ValueError("Public asset HTTP status was not200")
                    count = 0
                    while True:
                        if time.monotonic() - start >= ACQUISITION_SECONDS_CAP:
                            raise TimeoutError("Acquisition deadline")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > item["bytes"]:
                            raise ValueError("Public asset exceeded frozen byte count")
                        output.write(chunk)
                        downloaded_bytes += len(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            files.append(verify_file_identity(target, item))
        if time.monotonic() - start >= ACQUISITION_SECONDS_CAP:
            raise TimeoutError("Acquisition deadline after complete byte verification")
        if process_start_ticks(LEASE_PID) != LEASE_START_TICKS:
            raise ValueError("Physical root lease changed before acquisition completion")
        with (stage / WEIGHT_NAME).open("rb") as handle:
            header = handle.read(16)
        if len(header) != 16:
            raise ValueError("Original bin is missing its16-byte file header")
        lock = {
            "schema_version": 1, "epoch": 27, "repository": REPOSITORY, "revision": REVISION,
            "source_git_commit": manifest["source_git_commit"],
            "source_manifest_sha256": record["source_manifest_sha256"],
            "root_preparation_permit_sha256": record["permit_sha256"],
            "acquisition_plan_sha256": sha256_file(plan_path), "lease": permit["lease"],
            "diagnostic_only": True, "confirmation_ids": [], "training_ids": [],
            "calibration_ids": [], "fitting_or_calibration": False,
            "model_initializations": 0, "tokenizer_initializations": 0,
            "reader_contract": {
                "max_pair_tokens": 512, "attention": "sdpa", "batch_size": 1,
                "truncation": "only_first", "require_no_truncation": True,
                "precision": "FP32", "cpu_threads": 2, "interop_threads": 1,
                "raw_labels": ["C", "N", "E"], "canonical_permutation": [2, 0, 1],
                "temperature": 1, "use_safetensors": False, "weights_only": True,
            },
            "static_file_header": {
                "bytes_read": 16, "first_16_bytes_hex": header.hex(),
                "tensor_metadata_parsed": False, "pickle_parsed": False,
                "model_loaded_or_initialized": False,
            },
            "runtime_tensor_checks": "DEFERRED_INSIDE_SINGLE_BOUNDED_ADMITTED_WORKER",
            "license_provenance": plan["license_provenance"],
            "source_lineage_limits": plan["source_lineage_limits"],
            "files": files, "downloaded_bytes": downloaded_bytes,
            "copied_metadata_bytes": total_bytes - downloaded_bytes,
            "HTTP_retries": 0, "original_bin_only": True,
            "launch_admission": "PENDING_ROOT_AND_INDEPENDENT_SOURCE_ASSET_REVIEW",
        }
        with (stage / "asset-lock.json").open("x") as handle:
            json.dump(lock, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if destination.exists():
            raise ValueError("Destination appeared during acquisition")
        os.rename(stage, destination)
        update_receipt(receipt, {
            **record, "status": "COMPLETE", "seconds": time.monotonic() - start,
            "downloaded_bytes": downloaded_bytes,
            "asset_lock_sha256": sha256_file(destination / "asset-lock.json"),
        })
        return lock
    except BaseException as error:
        # Only this attempt's own stage is removed; persistent receipt forbids retry.
        if stage_created and stage.exists():
            shutil.rmtree(stage)
        update_receipt(receipt, {
            **record, "status": "FAILED_NO_RETRY", "error_type": type(error).__name__,
            "seconds": time.monotonic() - start, "downloaded_bytes": downloaded_bytes,
            "completed_asset_paths": [item["path"] for item in files],
        })
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    plan = read_object(HERE / "asset-acquisition-plan.json")
    verify_plan(plan)
    if not args.execute:
        print(json.dumps({
            "mode": "PLAN_ONLY_NO_NETWORK_OR_INIT", "repository": REPOSITORY,
            "revision": REVISION, "original_bin_only": True,
            "weight_bytes": WEIGHT_BYTES, "weight_sha256": WEIGHT_SHA256,
            "total_asset_bytes": sum(item["bytes"] for item in plan["files"]),
            "planned_download_bytes": sum(item["bytes"] for item in plan["files"] if not item.get("metadata_local_path")),
            "min_disk_reserve_bytes": MIN_DISK_RESERVE_BYTES,
            "acquisition_seconds_cap": ACQUISITION_SECONDS_CAP,
            "files": [item["path"] for item in plan["files"]],
        }, indent=2))
        return
    if args.permit is None or args.destination is None or args.source_manifest is None:
        parser.error("--execute requires root-authored --permit, --source-manifest and unused --destination")
    lock = acquire(args.destination, args.source_manifest.resolve(), args.permit.resolve())
    print(json.dumps({
        "destination": str(args.destination), "downloaded_bytes": lock["downloaded_bytes"],
        "model_initializations": 0, "tokenizer_initializations": 0,
        "asset_lock_sha256": sha256_file(args.destination / "asset-lock.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
