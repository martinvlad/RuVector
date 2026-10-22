"""Read-only package/asset/runtime metadata gate. No addons or models execute."""
from __future__ import annotations
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import struct
import subprocess

CLOSURE_SHA='3efc9666b549da8f70a22b0fca285dca68112f6835c767d08fd7f5946fc31726'
ASSETS_SHA='91f035c3bd5e24d6094a4656b2c2c35257bd0346eb7d278e5a8faf1ce817cfbd'
CANDIDATE_SHA='86a0f900c2dc1a8ae46c49a5c50af4da8ef98a2e7a0c3726b155ab96fa3530c1'
PREFIX='experiments/sota-2026-10-22/candidate/epoch4/'

NODE_WITNESS=r"""
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(process.argv[1]);
let addonAttempts=0;process.dlopen=()=>{addonAttempts++;throw new Error('Addon loading prohibited');};
const packages=['@ruvector/core','ruvector-core-linux-x64-gnu'];
const resolved=packages.map(name=>{
  const expected=path.join(root,'retrieval','node_modules',name,'index.js');
  const actual=require.resolve(name,{paths:[path.join(root,'retrieval')]});
  if(actual!==expected||fs.realpathSync(actual)!==expected)throw new Error('Entrypoint escapes exact isolated closure');
  const metadata=JSON.parse(fs.readFileSync(path.join(path.dirname(expected),'package.json'),'utf8'));
  if((metadata.main||'index.js').replace(/^\.\//,'')!=='index.js')throw new Error('Unexpected package main');
  return {package:name,version:metadata.version,main:metadata.main||'index.js',resolved:actual,engines:metadata.engines||null,os:metadata.os||null,cpu:metadata.cpu||null};
});
const addon=require.resolve('ruvector-core-linux-x64-gnu/ruvector.node',{paths:[path.join(root,'retrieval')]});
const expectedAddon=path.join(root,'retrieval','node_modules','ruvector-core-linux-x64-gnu','ruvector.node');
if(addon!==expectedAddon||fs.realpathSync(addon)!==expectedAddon)throw new Error('Addon resolution escaped closure');
const imported=Object.keys(require.cache).filter(p=>p.includes('node_modules'));
if(imported.length||addonAttempts)throw new Error('Unexpected package or addon execution');
console.log(JSON.stringify({kind:'require.resolve-only',project_root:root,resolved,addon_resolved_without_loading:addon,
  package_imports_executed:0,native_addon_load_attempts:addonAttempts,exec_argv:process.execArgv,
  node:{version:process.version,platform:process.platform,arch:process.arch,modules_abi:process.versions.modules,napi:process.versions.napi,v8:process.versions.v8,executable:process.execPath},
  limitation:'Resolution and static byte checks do not establish successful native ABI loading or execution.'}));
"""

PYTHON_WITNESS="""import importlib.metadata,json,sys,platform
names=['numpy','onnxruntime','tokenizers']
print(json.dumps({'executable':sys.executable,'python_version':platform.python_version(),'versions':{n:importlib.metadata.version(n) for n in names},'model_packages_imported':[n for n in names if n in sys.modules],'onnx_session_initializations':0,'model_forwards':0}))
"""


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def relative(value):
    if not isinstance(value,str) or '\\' in value or any(p in {'','.','..'} for p in value.split('/')):raise ValueError('Unsafe relative input path')
    path=PurePosixPath(value)
    if path.is_absolute():raise ValueError('Absolute input path')
    return Path(*path.parts)


def checked_file(root,item,regular_closure=False):
    path=root/relative(item['path'])
    if regular_closure:
        current=path
        while current!=root:
            if current.is_symlink():raise ValueError('Native closure has symlink ancestor: '+item['path'])
            current=current.parent
        if not stat.S_ISREG(path.stat().st_mode):raise ValueError('Native closure file is not regular')
    if not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('File identity mismatch: '+item['path'])
    return {'path':item['path'],'bytes':item['bytes'],'sha256':item['sha256'],'resolved_path':str(path.resolve()),'direct_symlink':path.is_symlink()}


def pinned_json(path,expected):
    if sha(path)!=expected:raise ValueError('Pinned specification identity mismatch: '+str(path))
    return json.loads(Path(path).read_text())


def varint(buffer,start,end):
    value=0;shift=0
    while start<end and shift<70:
        byte=buffer[start];start+=1;value|=(byte&127)<<shift
        if not byte&128:return value,start
        shift+=7
    raise ValueError('Malformed protobuf varint')


def fields(buffer,start,end):
    while start<end:
        tag,start=varint(buffer,start,end);number,wire=tag>>3,tag&7
        if not number:raise ValueError('Invalid protobuf field')
        if wire==0:
            value,start=varint(buffer,start,end);yield number,wire,start,start,value
        elif wire==2:
            size,start=varint(buffer,start,end);stop=start+size
            if stop>end:raise ValueError('Protobuf length exceeds enclosing message')
            yield number,wire,start,stop,None;start=stop
        elif wire in (1,5):
            stop=start+(8 if wire==1 else 4)
            if stop>end:raise ValueError('Truncated protobuf fixed-width field')
            yield number,wire,start,stop,None;start=stop
        else:raise ValueError('Unsupported protobuf wire type')


def value_info(buffer,start,end):
    result={}
    for n,w,a,b,v in fields(buffer,start,end):
        if n==1 and w==2:result['name']=buffer[a:b].decode()
        if n==2 and w==2:
            for tn,tw,ta,tb,tv in fields(buffer,a,b):
                if tn!=1 or tw!=2:continue
                for en,ew,ea,eb,ev in fields(buffer,ta,tb):
                    if en==1 and ew==0:result['tensor_element_type']=ev
                    if en==2 and ew==2:
                        dimensions=[]
                        for dn,dw,da,db,dv in fields(buffer,ea,eb):
                            if dn!=1 or dw!=2:continue
                            dimension={}
                            for kn,kw,ka,kb,kv in fields(buffer,da,db):
                                if kn==1 and kw==0:dimension['value']=kv
                                if kn==2 and kw==2:dimension['parameter']=buffer[ka:kb].decode()
                            dimensions.append(dimension)
                        result['dimensions']=dimensions
    return result


def inspect_onnx(path):
    result={'inputs':[],'outputs':[],'opsets':[],'operators':{},'external_initializers':[],'session_initialized':False,'model_forwards':0}
    with Path(path).open('rb') as file,mmap.mmap(file.fileno(),0,access=mmap.ACCESS_READ) as buffer:
        graph=None
        for n,w,a,b,v in fields(buffer,0,len(buffer)):
            if n==1 and w==0:result['ir_version']=v
            elif n==7 and w==2:graph=(a,b)
            elif n==8 and w==2:
                item={'domain':''}
                for k,kw,ka,kb,kv in fields(buffer,a,b):
                    if k==1 and kw==2:item['domain']=buffer[ka:kb].decode()
                    if k==2 and kw==0:item['version']=kv
                result['opsets'].append(item)
        if graph is None:raise ValueError('ONNX graph missing')
        for n,w,a,b,v in fields(buffer,*graph):
            if n==1 and w==2:
                operator='';domain=''
                for k,kw,ka,kb,kv in fields(buffer,a,b):
                    if k==4 and kw==2:operator=buffer[ka:kb].decode()
                    if k==7 and kw==2:domain=buffer[ka:kb].decode()
                name=domain+'::'+operator;result['operators'][name]=result['operators'].get(name,0)+1
            elif n==5 and w==2:
                name='';external=False
                for k,kw,ka,kb,kv in fields(buffer,a,b):
                    if k==8 and kw==2:name=buffer[ka:kb].decode()
                    if k==13 and kw==2:external=True
                    if k==14 and kw==0 and kv==1:external=True
                if external:result['external_initializers'].append(name)
            elif n in (11,12) and w==2:result['inputs' if n==11 else 'outputs'].append(value_info(buffer,a,b))
    if result['external_initializers']:raise ValueError('Model requires external tensor files outside six-asset closure')
    inputs={item['name']:item for item in result['inputs']}
    if not {'input_ids','attention_mask'}<=set(inputs) or not set(inputs)<={'input_ids','attention_mask','token_type_ids'}:raise ValueError('Frozen decoder feed names do not cover ONNX graph')
    if any(item.get('tensor_element_type')!=7 or len(item.get('dimensions',[]))!=2 for item in inputs.values()):raise ValueError('ONNX input tensor must be int64 rank2')
    if len(result['outputs'])!=1 or result['outputs'][0].get('tensor_element_type')!=1:raise ValueError('Expected one float32 logits output')
    dimensions=result['outputs'][0].get('dimensions',[])
    if len(dimensions)!=2 or dimensions[1].get('value')!=3:raise ValueError('Expected singleton-compatible three-way NLI output')
    return result


def inspect_elf(path):
    raw=Path(path).read_bytes()
    if raw[:4]!=b'\x7fELF' or raw[4]!=2 or raw[5]!=1:raise ValueError('Native artifact must be little-endian ELF64')
    machine=struct.unpack_from('<H',raw,18)[0]
    if machine!=62:raise ValueError('Native artifact must target x86_64')
    glibc=sorted({x.decode() for x in re.findall(rb'GLIBC_\d+(?:\.\d+)+',raw)},key=lambda x:tuple(map(int,x.split('_')[1].split('.'))))
    return {'format':'ELF64 little-endian','e_machine':machine,'architecture':'x86_64','glibc_symbol_versions_observed':glibc,'has_napi_register_module_v1_symbol':b'napi_register_module_v1' in raw,'host':{'system':platform.system(),'machine':platform.machine(),'libc':platform.libc_ver()},'ABI_loading_tested':False,'limitation':'Static ELF/symbol metadata and Node ABI observations do not prove successful addon loading or ABI compatibility.'}


def preflight(project_root,closure_spec,inference_python=None):
    root=Path(project_root).resolve()
    closure=pinned_json(closure_spec,CLOSURE_SHA)
    package_files=[item for package in closure['packages'] for item in package['files']]
    if len(closure['packages'])!=2 or len(package_files)!=8:raise ValueError('Expected exact two-package eight-file closure')
    closure_checked=[checked_file(root,item,True) for item in package_files]
    asset_lock=pinned_json(root/(PREFIX+'assets.lock.json'),ASSETS_SHA)
    if len(asset_lock['assets'])!=16:raise ValueError('Expected exact sixteen candidate assets')
    assets_checked=[checked_file(root,item) for item in asset_lock['assets']]
    candidate=pinned_json(root/(PREFIX+'proposal-manifest.json'),CANDIDATE_SHA)
    candidate_sources=[checked_file(root,item) for item in candidate['sources']]
    for item in candidate['read_only_code_dependencies']:
        if sha(root/relative(item['path']))!=item['sha256']:raise ValueError('Read-only code dependency changed')
    node=shutil.which('node')
    if node is None:raise ValueError('Node unavailable')
    env=dict(os.environ);env.pop('NODE_OPTIONS',None);env.pop('NODE_PATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
    command=[node,'--no-addons','--no-global-search-paths','-e',NODE_WITNESS,str(root)]
    process=subprocess.run(command,cwd=root,env=env,text=True,capture_output=True,timeout=20)
    if process.returncode:raise ValueError('Resolve-only witness failed: '+process.stderr[:1200])
    witness=json.loads(process.stdout)
    if witness['package_imports_executed'] or witness['native_addon_load_attempts']:raise ValueError('Unexpected native/package execution')
    if witness['node']['platform']!='linux' or witness['node']['arch']!='x64':raise ValueError('Native target platform mismatch')
    python=Path(inference_python) if inference_python else root/'retrieval/.venv/bin/python'
    observed=subprocess.run([str(python),'-I','-B','-c',PYTHON_WITNESS],cwd=root,env=env,text=True,capture_output=True,timeout=20)
    if observed.returncode:raise ValueError('Python metadata witness failed: '+observed.stderr[:1200])
    versions=json.loads(observed.stdout)
    if versions['versions']!=asset_lock['python_versions'] or versions['model_packages_imported']:raise ValueError('Python dependency versions/import boundary mismatch')
    model_path=root/(PREFIX+'assets/nli-base/onnx/model_quantized.onnx')
    graph=inspect_onnx(model_path)
    elf=inspect_elf(root/'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node')
    return {'schema_version':1,'status':'READ_ONLY_PREFLIGHT_PASS','project_root':str(root),'closure_spec_sha256':CLOSURE_SHA,'candidate_manifest_sha256':CANDIDATE_SHA,'assets_lock_sha256':ASSETS_SHA,'native_package_files_verified':closure_checked,'candidate_assets_verified':assets_checked,'candidate_sources_verified':candidate_sources,'node_resolution':witness,'python_metadata':versions,'onnx_static_metadata':graph,'native_static_metadata':elf,'native_addon_executions':0,'onnx_session_initializations':0,'model_forwards':0,'corpus_inputs_or_labels_read':0,'scope':'Metadata and exact-file closure only; actual addon ABI loading, ORT session/provider support, forwards, benchmarks and performance remain untested.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-root',type=Path,required=True)
    parser.add_argument('--closure-spec',type=Path,required=True)
    parser.add_argument('--inference-python',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=preflight(args.project_root,args.closure_spec,args.inference_python)
    encoded=(json.dumps(result,indent=2)+'\n').encode()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:stream.write(encoded)
    print(json.dumps({'status':result['status'],'native_files':len(result['native_package_files_verified']),'assets':len(result['candidate_assets_verified']),'output':str(args.output),'sha256':hashlib.sha256(encoded).hexdigest(),'model_native_calls':0}))


if __name__=='__main__':main()
