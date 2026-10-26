"""Root-approved ELF/help/version/GGUF metadata only; never model arguments."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE=Path(__file__).parent
RUNTIME=HERE/'project/experiments/sota-2026-10-22/runtime/epoch43'
MANIFEST=RUNTIME/'CPU_RUNTIME_MANIFEST.json'
ASSET_RECEIPT_SHA='13449320563a5a6f8100d2f7c4cea3bd06b72af7e16245d5d9c80aea4843dad8'
PUBLIC_PROJECT=Path('/tmp/ruvector-sota-2026-10-22/epoch43-cab16abb5795/project')


def require(x,code):
    if not x:raise RuntimeError(code)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True)
    p.add_argument('--output',required=True);args=p.parse_args()
    require(sha(args.approval)==args.approval_sha256,'QUALIFICATION_APPROVAL_BYTES')
    approval=json.loads(Path(args.approval).read_text())
    require(approval['authorized']is True and approval['epoch']==43 and time.time()<approval['expires_unix'],
            'ROOT_QUALIFICATION_AUTHORIZATION')
    required={Path(__file__).resolve(),RUNTIME/'assets_guard.py',MANIFEST,RUNTIME/'MODEL_PROFILE.json'}
    require({Path(row['path']).resolve()for row in approval['source_files']}==required and
            len(approval['source_files'])==len(required),'QUALIFICATION_EXACT_SOURCE_SET')
    for row in approval['source_files']:
        require(Path(row['path']).stat().st_size==row['bytes']and sha(row['path'])==row['sha256'],'QUALIFICATION_SOURCE')
    require(os.sched_getaffinity(0)=={0,1},'QUALIFICATION_CPU')
    out=Path(args.output);require(PUBLIC_PROJECT in out.parents and not out.exists(),'QUALIFICATION_NEW_PUBLIC_OUTPUT_SCOPE')
    require(not any(p.is_symlink()for p in(out,*out.parents)),'QUALIFICATION_OUTPUT_SYMLINK')
    out.mkdir(mode=0o700)
    def timeout(s,f):raise TimeoutError('QUALIFICATION_DEADLINE')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,50)
    started=time.monotonic();result={'schema_version':1,'epoch':43,'status':'FAILED','errors':[],
        'model_tokenizer_native_case_gold_calls':0,'commands':[]}
    rc=1
    try:
        manifest=json.loads(MANIFEST.read_text());root=Path(manifest['directory'])
        require(manifest['source_preparation_receipt']['sha256']==ASSET_RECEIPT_SHA,'ACTUAL_PREPARATION_AUTHORITY')
        for row in manifest['files']:
            file=root/row['path'];require(not file.is_symlink()and file.stat().st_size==row['bytes']
                and sha(file)==row['sha256'],'QUALIFICATION_CPU_BINARY_HASH')
        server=root/'llama-b11669/llama-server'
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2',
             'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        commands=[['/usr/bin/readelf','-l','-d',str(server)],
                  [str(server),'--version'],[str(server),'--help']]
        for index,command in enumerate(commands):
            require('--model'not in command and '-m'not in command,'MODEL_ARGUMENT_FORBIDDEN')
            completed=subprocess.run(command,cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                     timeout=12,close_fds=True)
            require(len(completed.stdout)+len(completed.stderr)<=1048576,'QUALIFICATION_CAPTURE_CAP')
            a=out/f'{index}.stdout';b=out/f'{index}.stderr';a.write_bytes(completed.stdout);b.write_bytes(completed.stderr)
            result['commands'].append({'argv':command,'returncode':completed.returncode,
                'stdout':{'path':str(a.relative_to(PUBLIC_PROJECT)),'bytes':len(completed.stdout),'sha256':sha(a)},
                'stderr':{'path':str(b.relative_to(PUBLIC_PROJECT)),'bytes':len(completed.stderr),'sha256':sha(b)}})
            require(completed.returncode==0,'QUALIFICATION_COMMAND_EXIT')
            if index==1:require(b'620d222'in completed.stdout+completed.stderr,'PINNED_BUILD_COMMIT')
            if index==2:
                helptext=completed.stdout+completed.stderr
                for flag in [b'--threads-batch',b'--threads-http',b'--no-warmup',b'--offline',
                             b'--no-context-shift',b'--no-cache-idle-slots',b'--no-webui',b'--no-slots']:
                    require(flag in helptext,'REQUIRED_RUNTIME_FLAG')
        source=RUNTIME/'assets_guard.py';spec=importlib.util.spec_from_file_location('e43_gguf_metadata_only',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        profile=json.loads((RUNTIME/'MODEL_PROFILE.json').read_text())
        result['GGUF_metadata_only']=module.gguf_metadata(profile['gguf_path'])
        result['CPU_manifest_sha256']=sha(MANIFEST)
        result['status']='ELF_VERSION_HELP_AND_BOUNDED_GGUF_METADATA_PASSED_NO_MODEL_LOAD';rc=0
    except BaseException as error:result['errors'].append({'type':type(error).__name__,'code':'QUALIFICATION_FAILED'})
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        result['wall_seconds_before_capture']=time.monotonic()-started
        with (out/'RESULT.json').open('x')as f:json.dump(result,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':result['status'],'result':str(out/'RESULT.json'),'rc':rc}))
    return rc


if __name__=='__main__':raise SystemExit(main())
