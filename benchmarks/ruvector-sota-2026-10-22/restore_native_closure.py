"""Restore a pinned npm package closure without installing or executing it.

Offline: --archive-dir DIR (ruvector--core.tgz and
ruvector-core-linux-x64-gnu.tgz). Network is opt-in via --acquire and uses only
the two immutable official registry URLs in the hash-pinned specification.
The destination must be NEW. No package scripts, imports or native calls run.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "official-package-closure.json"
SPEC_SHA256 = "3efc9666b549da8f70a22b0fca285dca68112f6835c767d08fd7f5946fc31726"
NODE_WITNESS = r"""
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[1];
const packages = JSON.parse(process.argv[2]);
let nativeLoads = 0;
process.dlopen = () => { nativeLoads++; throw new Error('Native loading forbidden'); };
const resolved = packages.map(name => {
  const expected = path.join(root, 'retrieval', 'node_modules', name, 'index.js');
  const actual = require.resolve(name, {paths: [path.join(root, 'retrieval')]});
  if (actual !== expected || fs.realpathSync(actual) !== expected) {
    throw new Error('Package resolved outside exact restored entry point');
  }
  return {package: name, resolved: actual};
});
console.log(JSON.stringify({kind: 'require.resolve-only', resolved,
  package_imports_executed: 0, native_addon_load_attempts: nativeLoads}));
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_spec(path=SPEC_PATH):
    if Path(path).is_symlink():
        raise ValueError("Specification symlink refused")
    raw = Path(path).read_bytes()
    if sha(raw) != SPEC_SHA256:
        raise ValueError("Pinned package closure specification changed")
    value = json.loads(raw)
    if len(value["packages"]) != 2 or sum(len(p["files"]) for p in value["packages"]) != 8:
        raise ValueError("Expected exactly two packages and eight files")
    return value


def cache_name(package):
    return package.replace("@", "").replace("/", "--") + ".tgz"


def safe_parts(value):
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or any(p in ("..", ".", "") for p in value.split("/")):
        raise ValueError("Unsafe relative path")
    return path.parts


def open_directory(path):
    """Walk from / with no-follow handles, rejecting every symlink ancestor."""
    path = Path(path).absolute()
    if ".." in path.parts:
        raise ValueError("Parent traversal refused")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_offline(directory, filename):
    fd = open_directory(directory)
    try:
        file_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise ValueError("Offline archive must be a regular file")
        with os.fdopen(file_fd, "rb") as stream:
            return stream.read(3_000_001)
    finally:
        os.close(fd)


def verify_tarball(package, raw):
    if len(raw) != package["tarball_bytes"] or sha(raw) != package["tarball_sha256"]:
        raise ValueError("Official archive length/SHA256 mismatch")
    algorithm, expected = package["npm_integrity"].split("-", 1)
    if algorithm != "sha512" or hashlib.sha512(raw).digest() != base64.b64decode(expected, validate=True):
        raise ValueError("Official npm SHA512 integrity mismatch")


def verify_closure(package, files):
    expected = {f["path"]: f for f in package["files"]}
    if set(files) != set(expected):
        raise ValueError("Incomplete or expanded package file closure")
    for path, data in files.items():
        spec = expected[path]
        if len(data) != spec["bytes"] or sha(data) != spec["sha256"]:
            raise ValueError("Unpacked package file identity mismatch: " + path)
    prefix = "retrieval/node_modules/" + package["package"] + "/"
    metadata = json.loads(files[prefix + "package.json"])
    if metadata.get("name") != package["package"] or metadata.get("version") != package["version"]:
        raise ValueError("Package name/version mismatch")
    if metadata.get("main", "index.js").removeprefix("./") != "index.js" or prefix + "index.js" not in files:
        raise ValueError("Package main entry point is missing or unexpected")


def unpack(package, raw):
    verify_tarball(package, raw)
    prefix = "retrieval/node_modules/" + package["package"] + "/"
    expected = {f["path"]: f for f in package["files"]}
    result, seen = {}, set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = safe_parts(member.name)
            if parts[0] != "package" or len(parts) < 2:
                raise ValueError("Unexpected archive root")
            if member.name in seen or not member.isfile():
                raise ValueError("Duplicate, link or non-regular archive member")
            seen.add(member.name)
            target = prefix + "/".join(parts[1:])
            if target not in expected:
                raise ValueError("Archive contains an unreviewed file")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing archive payload")
            result[target] = stream.read(expected[target]["bytes"] + 1)
    verify_closure(package, result)
    return result


def get_archive(package, archive_dir, acquire):
    if not acquire:
        return read_offline(archive_dir, cache_name(package["package"]))
    url = package["source_url"]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "registry.npmjs.org" or parsed.query or parsed.username:
        raise ValueError("Only pinned official registry HTTPS URLs are allowed")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RuVector-closure-restore/1.0"}), timeout=30) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.scheme != "https" or final.hostname != "registry.npmjs.org":
            raise ValueError("Registry redirected outside official host")
        return response.read(package["tarball_bytes"] + 1)


def write_new_file(root_fd, relative, data):
    parts = safe_parts(relative)
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        file_fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(file_fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def restore(destination, archive_dir=None, acquire=False, spec_path=SPEC_PATH):
    spec = load_spec(spec_path)
    if acquire == (archive_dir is not None):
        raise ValueError("Choose exactly one of offline archive directory or explicit acquisition")
    destination = Path(destination).absolute()
    if ".." in destination.parts or os.path.lexists(destination):
        raise ValueError("Destination must be new; never overwrite an existing path")
    parent_fd = open_directory(destination.parent)
    files = {}
    try:
        # All official archives/files pass before any destination is created.
        for package in spec["packages"]:
            files.update(unpack(package, get_archive(package, archive_dir, acquire)))
        os.mkdir(destination.name, 0o700, dir_fd=parent_fd)
        root_fd = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        for path, data in files.items():
            write_new_file(root_fd, path, data)
    finally:
        os.close(root_fd)
    for path, data in files.items():
        actual = destination / path
        if actual.is_symlink() or actual.read_bytes() != data:
            raise ValueError("Restored file verification failed")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node is required for the resolve-only witness; restored files preserved")
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env.pop("NODE_PATH", None)
    process = subprocess.run([node, "--no-addons", "--no-global-search-paths", "-e", NODE_WITNESS,
                              str(destination), json.dumps([p["package"] for p in spec["packages"]])],
                             env=env, capture_output=True, text=True, timeout=15)
    if process.returncode:
        raise RuntimeError("Resolve-only witness failed: " + process.stderr[:1000])
    witness = json.loads(process.stdout)
    if witness.get("native_addon_load_attempts") != 0 or witness.get("package_imports_executed") != 0:
        raise ValueError("Unexpected native/package execution")
    return {"schema_version": 1, "status": "RESTORED_RESOLUTION_VERIFIED", "spec_sha256": SPEC_SHA256,
            "destination": str(destination), "files_verified": len(files), "source": "official npm registry" if acquire else "offline hash-pinned official archives",
            "witness": witness, "npm_install_scripts_executed": 0, "package_imports_executed": 0,
            "native_calls": 0, "model_forwards": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive-dir", type=Path)
    source.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    print(json.dumps(restore(args.destination, args.archive_dir, args.acquire), indent=2))


if __name__ == "__main__": main()
