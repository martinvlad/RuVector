"""Restore a hash-pinned projected project without credentials or implicit inference.

The default performs text-only source reconstruction. Native dependencies and
model assets are acquired only through explicit flags. No benchmark is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
BASE_URL = "https://raw.githubusercontent.com/ruvnet/RuVector/11983d212b951305bcab06ad868bca5a12ea2954/benchmarks/jevbench-2026-10-22/"
BASE_MANIFEST_SHA256 = "0db67a018ad5fd9deba1cfb0bd8897537a330dd2353f169e6e387e86e09fce7a"


def sha(raw): return hashlib.sha256(raw).hexdigest()


def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("Unsafe projected file path")
    return Path(*p.parts)


def checked_target(root, name):
    p = root / relative(name)
    if not p.resolve().is_relative_to(root) or any(x.is_symlink() for x in [p, *p.parents] if x != root.parent):
        raise ValueError("Unsafe destination or symlink")
    return p


def write_checked(root, item, raw, verify_only=False):
    if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
        raise ValueError("Source identity mismatch: " + item["path"])
    target = checked_target(root, item["path"])
    if target.exists():
        if not target.is_file() or sha(target.read_bytes()) != item["sha256"]:
            raise ValueError("Preserving mismatched destination: " + str(target))
        return
    if verify_only:
        raise FileNotFoundError(str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(raw)


def reconstruct(destination, base_local_directory=None, verify_only=False):
    destination = Path(destination).resolve()
    if destination == HERE or destination in HERE.parents:
        raise ValueError("Choose an isolated destination, outside the kit")
    manifest_raw = (HERE / "BASE_PUBLIC_MANIFEST.json").read_bytes()
    if sha(manifest_raw) != BASE_MANIFEST_SHA256:
        raise ValueError("Immutable base public manifest identity mismatch")
    base_manifest = json.loads(manifest_raw)
    base_index = {x["path"]: x for x in base_manifest["files"]}
    manifest = json.loads((HERE / "KIT_MANIFEST.json").read_text())
    base_paths = json.loads((HERE / "BASE_DOWNLOADS.json").read_text())["paths"]
    if not verify_only:
        destination.mkdir(parents=True, exist_ok=True)
    restored = []
    for item in manifest["project_files"]:
        raw = (HERE / relative(item["path"])).read_bytes()
        write_checked(destination, item, raw, verify_only)
        restored.append(item["path"])
    network_gets = 0
    for name in base_paths:
        item = base_index[name]
        destination_path = checked_target(destination, name)
        if destination_path.exists() and sha(destination_path.read_bytes()) == item["sha256"]:
            restored.append(name)
            continue
        if verify_only:
            raise FileNotFoundError(str(destination_path))
        if base_local_directory is not None:
            raw = (Path(base_local_directory) / relative(name)).read_bytes()
        else:
            with urllib.request.urlopen(BASE_URL + name, timeout=45) as response:
                raw = response.read(item["bytes"] + 1)
            network_gets += 1
        write_checked(destination, item, raw)
        restored.append(name)
    return {"status": "PROJECTED_SOURCES_VERIFIED", "destination": str(destination),
            "project_files": len(manifest["project_files"]), "base_files": len(base_paths),
            "base_manifest_sha256": BASE_MANIFEST_SHA256, "kit_manifest_sha256": sha((HERE / "KIT_MANIFEST.json").read_bytes()),
            "restored": sorted(set(restored)), "network_gets": network_gets,
            "model_weights_copied": False, "native_inference_calls": 0,
            "limits": "Source reconstruction only; runtime dependencies and assets require documented opt-in installation/acquisition."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--base-local-directory", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--install-npm", action="store_true")
    parser.add_argument("--install-python", action="store_true")
    parser.add_argument("--acquire-models", action="store_true")
    parser.add_argument("--verify-models", action="store_true")
    args = parser.parse_args()
    if args.verify_only and any([args.install_npm, args.install_python, args.acquire_models]):
        parser.error("verify-only cannot install or acquire resources")
    result = reconstruct(args.dest, args.base_local_directory, args.verify_only)
    dest = Path(result["destination"])
    if args.install_npm:
        subprocess.run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=dest, check=True)
    if args.install_python:
        subprocess.run([sys.executable, "-m", "pip", "install", "numpy==2.3.5", "scipy==1.17.0"], cwd=dest, check=True)
    if args.acquire_models or args.verify_models:
        command = [sys.executable, str(dest / "acquire_models.py")]
        if args.verify_models and not args.acquire_models:
            command.append("--verify-only")
        subprocess.run(command, cwd=dest, check=True)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
