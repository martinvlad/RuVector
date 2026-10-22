"""Restore exact omitted public ContractNLI archive/members; never runs models."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()


def relative(value):
    path=PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {".",".."} for part in path.parts) or "\\" in value:
        raise ValueError("Unsafe project-relative path")
    return Path(*path.parts)


def target_path(destination,name):
    destination=Path(destination).resolve()
    path=destination/relative(name)
    if not path.resolve().is_relative_to(destination):raise ValueError("Target escapes project")
    current=path
    while current!=destination:
        if current.is_symlink():raise ValueError("Restore target must not traverse a symlink")
        current=current.parent
    return path


def verify(path,item):
    return path.is_file() and path.stat().st_size==item["bytes"] and sha(path)==item["sha256"]


def write_checked(destination,item,contents):
    if len(contents)!=item["bytes"] or hashlib.sha256(contents).hexdigest()!=item["sha256"]:
        raise ValueError("Source identity mismatch: "+item["path"])
    path=target_path(destination,item["path"])
    if path.exists():
        if not verify(path,item):raise ValueError("Existing target differs; refusing overwrite: "+item["path"])
        return "VERIFIED_EXISTING"
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix=".restore-",delete=False) as stream:
            temporary=Path(stream.name);stream.write(contents);stream.flush();os.fsync(stream.fileno())
        try:os.link(temporary,path)
        except FileExistsError:
            if not verify(path,item):raise ValueError("Concurrent target differs; refusing overwrite")
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return "RESTORED"


def restore(destination,spec,archive_local=None,verify_only=False):
    destination=Path(destination).resolve()
    archive_item=spec["archive"]
    members=spec["members"]
    if verify_only:
        for item in [archive_item]+members:
            if not verify(target_path(destination,item["path"]),item):raise ValueError("Missing or changed restored input: "+item["path"])
        return {"status":"VERIFIED","archive":archive_item,"members":members,"network_requests":0,"model_calls":0}
    archive_target=target_path(destination,archive_item["path"])
    requests=0
    if archive_target.exists():
        if not verify(archive_target,archive_item):raise ValueError("Existing archive differs; refusing overwrite")
    elif archive_local is not None:
        local=Path(archive_local)
        if not verify(local,archive_item):raise ValueError("Local archive identity mismatch")
        write_checked(destination,archive_item,local.read_bytes())
    else:
        url=spec["source_url"]
        expected="https://raw.githubusercontent.com/stanfordnlp/contract-nli/"+spec["source_commit"]+"/resources/contract-nli.zip"
        if url!=expected:raise ValueError("Unexpected archive source URL")
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"RuVector pinned public data restoration"}),timeout=120) as response:
            contents=response.read(archive_item["bytes"]+1)
        requests=1
        write_checked(destination,archive_item,contents)
    with zipfile.ZipFile(archive_target) as archive:
        for item in members:
            relative(item["member"])
            info=archive.getinfo(item["member"])
            if info.file_size!=item["bytes"]:raise ValueError("Archive member size mismatch")
            write_checked(destination,item,archive.read(item["member"]))
    return {"status":"RESTORED","archive":archive_item,"members":members,"network_requests":requests,"model_calls":0}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dest",type=Path,required=True)
    parser.add_argument("--spec",type=Path,default=Path(__file__).with_name("RESTORE_EPOCH3_DATA.json"))
    parser.add_argument("--archive-local",type=Path)
    parser.add_argument("--verify-only",action="store_true")
    args=parser.parse_args()
    result=restore(args.dest,json.loads(args.spec.read_text()),args.archive_local,args.verify_only)
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
