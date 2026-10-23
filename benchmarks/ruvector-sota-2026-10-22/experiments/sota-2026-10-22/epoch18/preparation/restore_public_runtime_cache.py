"""Restore exact public runtime bytes from verified caches, without inference.

Fresh venv and only the 31 hash-pinned official wheel members are admitted.
Byte-identical installed cache members may be hardlinked to conserve space.
Other members are extracted from the verified wheel. No pip hooks, model
imports, model warmups, network calls, or console entrypoint generation.
"""
from pathlib import Path,PurePosixPath
import argparse,base64,csv,hashlib,io,json,os,shutil,stat,subprocess,sys,zipfile
from datetime import datetime,timezone

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def relative(value):
    p=PurePosixPath(value)
    if not value or p.is_absolute()or'\\'in value or any(x in ('','.','..')for x in value.split('/')):
        raise ValueError('Unsafe public member path')
    return Path(*p.parts)

def no_symlink(path):
    for p in [Path(path),*Path(path).parents]:
        if p.is_symlink():raise ValueError('Symlink public file ancestor refused')

def identity(path,row):
    no_symlink(path)
    return path.is_file()and stat.S_ISREG(path.stat().st_mode)and path.stat().st_size==row['bytes']and digest(path)==row['sha256']

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);no_symlink(path)
    with path.open('x')as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def link_asset(src,dst,row):
    if not identity(src,row):raise ValueError('Public asset cache identity mismatch: '+row['path'])
    if dst.exists():
        if not identity(dst,row):raise ValueError('Preserve mismatched destination')
        return 'VERIFIED_EXISTING'
    no_symlink(dst);dst.parent.mkdir(parents=True,exist_ok=True)
    os.link(src,dst,follow_symlinks=False)
    if not identity(dst,row):raise ValueError('Postlink identity changed')
    return 'HARDLINKED_EXACT_PUBLIC_BYTES'

def wheel_target(name,venv,site):
    p=relative(name);parts=p.parts
    if parts[0].endswith('.data'):
        if len(parts)<3:raise ValueError('Incomplete wheel data scheme')
        tail=Path(*parts[2:])
        schemes={'purelib':site,'platlib':site,'scripts':venv/'bin','data':venv,'headers':venv/'include'}
        if parts[1]not in schemes:raise ValueError('Unknown wheel data scheme')
        return schemes[parts[1]]/tail
    return site/p

def wheel_members(archive):
    infos=[x for x in archive.infolist()if not x.is_dir()]
    if len({x.filename for x in infos})!=len(infos):raise ValueError('Duplicate wheel member')
    record=[x for x in infos if x.filename.endswith('.dist-info/RECORD')]
    if len(record)!=1:raise ValueError('Exactly one official wheel RECORD required')
    record_rows=list(csv.reader(io.StringIO(archive.read(record[0]).decode('utf-8'))))
    if len({x[0]for x in record_rows})!=len(record_rows):raise ValueError('Duplicate wheel RECORD row')
    records={x[0]:x[1:]for x in record_rows}
    for info in infos:
        relative(info.filename)
        if stat.S_ISLNK(info.external_attr>>16):raise ValueError('Wheel symlink refused')
        h=hashlib.sha256()
        with archive.open(info)as stream:
            for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
        actual=h.hexdigest()
        if info.filename!=record[0].filename:
            row=records.get(info.filename)
            if not row or len(row)!=2 or int(row[1])!=info.file_size or not row[0].startswith('sha256='):
                raise ValueError('Exact SHA256 wheel RECORD required')
            expected=base64.urlsafe_b64decode(row[0].split('=',1)[1]+'===').hex()
            if actual!=expected:raise ValueError('Wheel member RECORD disagreement')
        yield info,actual

def restore(args):
    project=args.project.absolute();cache=args.public_cache.absolute();wcache=args.wheel_cache.absolute()
    for p in [project,cache,wcache]:no_symlink(p)
    s=project/'experiments/sota-2026-10-22';prep=s/'epoch18/preparation';prep.mkdir(parents=True,exist_ok=True)
    native=json.loads((s/'epoch17/preparation/runtime-closure.json').read_text())['files']
    registry=json.loads((s/'epoch17/external-registry.json').read_text())
    if len(native)!=22 or len(registry)!=20:raise ValueError('Frozen public runtime closure counts changed')
    assets={}
    for row in native+registry:
        key=row['path'];relative(key)
        value={k:row[k]for k in ('path','bytes','sha256')}
        if key in assets and assets[key]!=value:raise ValueError('Conflicting asset identity')
        assets[key]=value
    # Source and target checks all finish before first hardlink.
    for row in assets.values():
        if not identity(cache/row['path'],row):raise ValueError('Exact public byte cache unavailable')
        dst=project/row['path'];no_symlink(dst)
        if dst.exists()and not identity(dst,row):raise ValueError('Existing target changed')
    rows=[]
    for row in assets.values():
        rows.append({**row,'restoration':link_asset(cache/row['path'],project/row['path'],row)})
    put(prep/'public-runtime-asset-cache-receipt.json',{'schema_version':1,'status':'EXACT_PUBLIC_NATIVE_MODEL_AND_LICENSED_SOURCE_BYTES_RESTORED',
        'files':rows,'unique_files':len(rows),'native_files':22,'explicit_external_registry':20,
        'cache_files_are_not_trusted_without_actual_hashes':True,'original_source_case_or_choice_JSON_parses':0,
        'model_native_fit_paid_GPU_calls':0})
    locked=json.loads((s/'epoch17/preparation/python-wheel-identities.json').read_text())
    wheels=locked['wheels']
    if len(wheels)!=31:raise ValueError('Exactly31 fixed CPU runtime wheels required')
    for row in wheels:
        name=relative(row['filename'])
        if len(name.parts)!=1 or not identity(wcache/name,row):raise ValueError('Official exact wheel cache unavailable')
    venv=project/'retrieval/.venv'
    if venv.exists():raise ValueError('Fresh venv required, never overlay')
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(venv)],check=True)
    query='import sysconfig,json;print(json.dumps(sysconfig.get_paths()))'
    new_paths=json.loads(subprocess.check_output([str(venv/'bin/python'),'-B','-I','-c',query],text=True))
    site=Path(new_paths['purelib']);oldvenv=cache/'retrieval/.venv'
    oldsite=oldvenv/site.relative_to(venv)
    if not site.is_relative_to(venv)or not oldsite.is_relative_to(oldvenv):
        raise ValueError('Unexpected interpreter package prefix')
    manifest=[];seen={};links=0;extracts=0
    for wheel in wheels:
        with zipfile.ZipFile(wcache/wheel['filename'])as archive:
            for info,h in wheel_members(archive):
                dst=wheel_target(info.filename,venv,site);src=wheel_target(info.filename,oldvenv,oldsite)
                no_symlink(dst)
                if not dst.is_relative_to(venv):raise ValueError('Wheel path escaped fresh venv')
                rel=str(dst.relative_to(venv))
                row={'path':rel,'bytes':info.file_size,'sha256':h,'wheel':wheel['filename']}
                if rel in seen:
                    if seen[rel]['sha256']!=h or seen[rel]['bytes']!=info.file_size:raise ValueError('Conflicting wheel target')
                    continue
                dst.parent.mkdir(parents=True,exist_ok=True)
                if dst.exists():raise ValueError('Preserve unexpected venv member')
                if src.exists()and identity(src,row):
                    os.link(src,dst,follow_symlinks=False);links+=1
                else:
                    with archive.open(info)as inp,dst.open('xb')as out:shutil.copyfileobj(inp,out,1024*1024)
                    os.chmod(dst,(info.external_attr>>16)&0o777 or 0o644);extracts+=1
                if not identity(dst,row):raise ValueError('Restored wheel member mismatch')
                seen[rel]=row;manifest.append(row)
    raw=(json.dumps(sorted(manifest,key=lambda r:r['path']),sort_keys=True,separators=(',',':'))+'\n').encode()
    with(args.receipt_dir/'python-wheel-member-identities.json').open('xb')as f:f.write(raw)
    versions_code='import importlib.metadata as m,json,sys;print(json.dumps({"Python":sys.version,"packages":sorted([{"name":d.metadata["Name"],"version":d.version}for d in m.distributions()],key=lambda x:x["name"].lower())}))'
    versions=json.loads(subprocess.check_output([str(venv/'bin/python'),'-B','-I','-c',versions_code],text=True))
    if len(versions['packages'])!=31:raise ValueError('Unexpected isolated package closure')
    report={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'status':'FRESH_VENV_EXACT_31_OFFICIAL_WHEEL_MEMBERS_RESTORED',
        'wheel_lock_path':'experiments/sota-2026-10-22/epoch17/preparation/python-wheel-identities.json',
        'wheel_lock_SHA256':digest(s/'epoch17/preparation/python-wheel-identities.json'),'official_wheels_verified':31,
        'actual_members':len(manifest),'actual_member_bytes':sum(r['bytes']for r in manifest),
        'hardlinked_byte_equal_cache_members':links,'official_wheel_members_extracted':extracts,
        'canonical_member_manifest_SHA256':hashlib.sha256(raw).hexdigest(),'versions':versions,
        'pip_console_entrypoints_not_installed_or_used':True,'fresh_venv_created':True,'all_zip_and_restored_member_SHA256_verified':True,
        'old_venv_not_blindly_copied':True,'model_native_fit_paid_GPU_calls':0,'original_case_or_choice_JSON_parses':0}
    put(prep/'python-runtime-restoration.json',report)
    return {'public_asset_files':len(rows),'wheel_files':31,'wheel_members':len(manifest),'hardlinks':links,'small_extractions':extracts,
        'model_native_fit_paid_GPU_calls':0,'original_case_or_choice_JSON_parses':0,'status':report['status']}

def main():
    ap=argparse.ArgumentParser()
    for flag in ['project','public-cache','wheel-cache','receipt-dir']:ap.add_argument('--'+flag,required=True,type=Path)
    args=ap.parse_args();os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:2]))
    print(json.dumps(restore(args)))
if __name__=='__main__':main()
