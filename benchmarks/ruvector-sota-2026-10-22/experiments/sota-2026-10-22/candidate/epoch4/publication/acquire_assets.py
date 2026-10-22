"""Verified optional DeBERTa-base asset copy/download. Never runs inference."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.request

REPO='Xenova/nli-deberta-v3-base'
REVISION='80a99030ce45a69a39ea2a6f50756d03859ff521'
MEMBERS={'config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','onnx/model_quantized.onnx','README.md'}
PREFIX='experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/'
SPEC_SHA256='b9beaff596fc16ac2e036e003bed5e3e281361c32b0aaf703d975865caa33dc0'


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def relative(value):
    if not isinstance(value,str) or '\\' in value or any(p in {'','.','..'} for p in value.split('/')):
        raise ValueError('Unsafe relative asset path')
    path=PurePosixPath(value)
    if path.is_absolute():raise ValueError('Absolute asset path forbidden')
    return Path(*path.parts)


def checked(root,name):
    root=Path(root).resolve();path=root/relative(name)
    current=path
    while current!=root:
        if current.is_symlink():raise ValueError('Asset path traverses a symlink')
        current=current.parent
    if not path.resolve().is_relative_to(root):raise ValueError('Asset escapes destination')
    return path


def validate_spec(spec):
    if spec.get('repo')!=REPO or spec.get('revision')!=REVISION:raise ValueError('Unreviewed model identity')
    if len(spec.get('assets',[]))!=len(MEMBERS):raise ValueError('Exactly six pinned assets required')
    seen=set()
    for item in spec['assets']:
        name=item['relative_model_path'];relative(name);relative(item['path'])
        if name not in MEMBERS or name in seen or item['path']!=PREFIX+name:raise ValueError('Unreviewed asset path')
        seen.add(name)
        if item['source_url']!=f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}':raise ValueError('Unexpected asset URL')
        if type(item['bytes']) is not int or not 0<item['bytes']<500_000_000 or not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('Invalid pinned asset metadata')


def load_spec(path):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SPEC_SHA256:raise ValueError('Pinned six-asset manifest identity mismatch')
    spec=json.loads(raw);validate_spec(spec);return spec


def verify(path,item):
    return path.is_file() and not path.is_symlink() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']


def install_stream(target,item,source):
    """Hash while copying and atomically admit only matching, complete bytes."""
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix='.asset-',delete=False) as out:
            temporary=Path(out.name);digest=hashlib.sha256();size=0
            while True:
                block=source.read(1024*1024)
                if not block:break
                size+=len(block)
                if size>item['bytes']:raise ValueError('Asset exceeds pinned size')
                digest.update(block);out.write(block)
            out.flush();os.fsync(out.fileno())
        if size!=item['bytes'] or digest.hexdigest()!=item['sha256']:raise ValueError('Asset size/SHA256 mismatch')
        try:os.link(temporary,target)
        except FileExistsError:
            if target.is_symlink() or not verify(target,item):raise ValueError('Concurrent target mismatch; refusing overwrite')
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def acquire(destination,spec,cache_dir=None,download=False,verify_only=False):
    validate_spec(spec)
    if verify_only and (download or cache_dir is not None):raise ValueError('Verify-only cannot copy or download')
    destination=Path(destination).resolve()
    results=[];requests=0;copied=0
    for item in spec['assets']:
        target=checked(destination,item['path'])
        if target.exists():
            if not verify(target,item):raise ValueError('Existing target differs; refusing overwrite: '+item['path'])
            results.append({'path':item['path'],'status':'VERIFIED_EXISTING'});continue
        if verify_only:raise ValueError('Missing asset: '+item['path'])
        if cache_dir is not None:
            source=checked(cache_dir,item['relative_model_path'])
            if not verify(source,item):raise ValueError('Cache asset identity mismatch: '+item['relative_model_path'])
            with source.open('rb') as stream:install_stream(target,item,stream)
            copied+=1;status='COPIED_VERIFIED_CACHE'
        elif download:
            request=urllib.request.Request(item['source_url'],headers={'User-Agent':'RuVector pinned public asset acquisition'})
            with urllib.request.urlopen(request,timeout=120) as response:install_stream(target,item,response)
            requests+=1;status='DOWNLOADED_VERIFIED'
        else:raise ValueError('Missing asset; provide --cache-dir or explicitly opt in with --download')
        results.append({'path':item['path'],'status':status})
    return {'status':'ASSETS_VERIFIED','repo':REPO,'revision':REVISION,'files':results,'network_requests':requests,'cache_files_copied':copied,'model_calls':0,'native_calls':0,'dependency_installations':0}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dest',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,default=Path(__file__).with_name('EPOCH4_MODEL_ASSETS.json'))
    parser.add_argument('--cache-dir',type=Path,help='Regular-file model directory containing config.json and onnx/model_quantized.onnx')
    parser.add_argument('--download',action='store_true',help='Explicitly allow public pinned HuggingFace downloads')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    print(json.dumps(acquire(args.dest,load_spec(args.manifest),args.cache_dir,args.download,args.verify_only),indent=2))


if __name__=='__main__':main()
