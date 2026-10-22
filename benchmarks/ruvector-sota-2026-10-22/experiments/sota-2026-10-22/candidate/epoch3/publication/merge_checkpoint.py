"""Append reviewed project files to a checkpoint manifest without hidden edits."""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath


def merge(base,extension,extra=None):
    result=copy.deepcopy(base)
    files={item["path"]:copy.deepcopy(item) for item in base["project_files"]}
    if len(files)!=len(base["project_files"]):raise ValueError("Duplicate paths in base checkpoint")
    for item in extension["project_files"]+(extra or {}).get("project_files",[]):
        path=PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts or "\\" in item["path"]:raise ValueError("Unsafe project path")
        if item["path"] in files and (files[item["path"]]["sha256"]!=item["sha256"] or files[item["path"]]["bytes"]!=item["bytes"]):
            raise ValueError("Existing checkpoint file changed: "+item["path"])
        files[item["path"]]=copy.deepcopy(item)
    result["project_files"]=sorted(files.values(),key=lambda item:item["path"])
    result["scope"]=base.get("scope","")+" Append-only epoch3 source/data and exact restoration metadata; existing project files preserved."
    result["epoch3_restoration"]=copy.deepcopy(extension["omitted_restorable_inputs"])
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base",type=Path,required=True)
    parser.add_argument("--extension",type=Path,required=True)
    parser.add_argument("--extra-file-manifest",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    extra=json.loads(args.extra_file_manifest.read_text()) if args.extra_file_manifest else None
    result=merge(json.loads(args.base.read_text()),json.loads(args.extension.read_text()),extra)
    raw=(json.dumps(result,indent=2)+"\n").encode()
    if args.output.exists():
        if args.output.read_bytes()!=raw:raise ValueError("Output differs; choose a new reviewable manifest path")
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("xb") as stream:stream.write(raw)
    print(json.dumps({"status":"MERGED","project_files":len(result["project_files"]),"output":str(args.output)}))


if __name__=="__main__":main()
