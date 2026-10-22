"""Extend the reviewed source bootstrap with exact public experiment evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--base-local-directory", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    import bootstrap
    manifest_path = here / "CHECKPOINT_MANIFEST.json"
    continuation = json.loads((here / "CONTINUATION.json").read_text())
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != continuation["checkpoint_manifest_sha256"]:
        raise ValueError("Checkpoint manifest identity mismatch")
    result = bootstrap.reconstruct(args.dest, args.base_local_directory, args.verify_only)
    destination = Path(result["destination"])
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["project_files"]:
        source = here / bootstrap.relative(item["path"])
        bootstrap.write_checked(destination, item, source.read_bytes(), args.verify_only)
    print(json.dumps({"status": "PUBLIC_CHECKPOINT_RESTORED", "projected_base_files": result["base_files"],
                      "checkpoint_files": len(manifest["project_files"]), "destination": str(destination),
                      "native_or_paid_calls": 0, "dependency_or_model_installation": False}))


if __name__ == "__main__":
    main()
