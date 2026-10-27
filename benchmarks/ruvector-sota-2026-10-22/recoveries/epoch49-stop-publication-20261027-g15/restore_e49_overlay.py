"""Verify the exact public ZIP, then restore ONLY its 76 project overlay files.

No Git, subprocess, network, import of recovered source, or scientific action.
Old requests/journals/tokens remain closed evidence inside the text envelope.
"""
import sys
sys.dont_write_bytecode=True
import argparse,base64,hashlib,io,json,os,stat,zipfile
from pathlib import Path,PurePosixPath
ARCHIVE_SHA='2b7e357a7058f8fd850810589cdfbc41937ccac20cd49ac985a7600bb9881194'
ARCHIVE_BYTES=2909023
PREFIXES=tuple('experiments/sota-2026-10-22/'+p for p in ('epoch49/','audit/epoch49/','runtime/epoch49/'))
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def unique(items):
    out={}
    for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
    return out
def parse(b):return json.loads(b,object_pairs_hook=unique,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite')))
def safe(p):
    require(type(p) is str and p and not PurePosixPath(p).is_absolute() and '\\' not in p and all(x not in ('','.','..') for x in p.split('/')),'canonical archive path')
    return p
def verified(envelope,manifest):
    e=parse(Path(envelope).read_bytes());m=parse(Path(manifest).read_bytes())
    raw=base64.b64decode(e['archive_base64'],validate=True)
    require(len(raw)==ARCHIVE_BYTES==e['archive']['bytes'] and sha(raw)==ARCHIVE_SHA==e['archive']['sha256'],'exact reviewed ZIP identity')
    require(m['canonical_members']==76 and m['CP_project_files_includes_overlay76'] is False and m['direct_Git_member_blobs']==0,'separate overlay, no member publication')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[safe(i.filename) for i in infos]
        require(len(infos)==268 and len(set(names))==len(names),'exact unique archive inventory')
        require(all(not i.is_dir() and not (i.flag_bits&1) and stat.S_IFMT(i.external_attr>>16)!=stat.S_IFLNK for i in infos),'regular unencrypted ZIP members')
        bundle=parse(z.read('BUNDLE_MANIFEST.json'));rows=bundle['files'];expected={safe(r['path']):r for r in rows}
        require(len(expected)==len(rows) and set(expected)|{'BUNDLE_MANIFEST.json'}==set(names),'whole ZIP manifest closure')
        require(bundle['actual_publication']=={'UNKNOWN':1,'acknowledged':40,'create_blob_attempts':41,'create_commit':0,'create_tree':0,'update_ref':0} and bundle['actual_native_model_DATA_Gold_EVAL_calls']==0,'closed E49 actual facts')
        for name,row in expected.items():
            b=z.read(name);require(type(row['bytes']) is int and len(b)==row['bytes'] and sha(b)==row['sha256'],'whole ZIP member hash')
        project={safe(r['path']):r for r in m['project_files']}
        require(len(project)==76==len(m['project_files']) and {'project/'+p for p in project}=={p for p in names if p.startswith('project/')},'exact 76 project-only members')
        result={}
        for p,row in project.items():
            require(p.startswith(PREFIXES),'E49 overlay prefix only');b=z.read('project/'+p)
            require(len(b)==row['bytes'] and sha(b)==row['sha256'],'overlay member hash');result[p]=b
        return result
def apply(envelope,manifest,project,verify_only=False):
    files=verified(envelope,manifest);root=Path(project).resolve()
    require(root.is_dir() and all(not p.is_symlink() for p in (Path(project),*Path(project).parents)),'existing isolated project, no symlinks')
    for p,b in files.items():
        dest=root/p;require(all(not q.is_symlink() for q in (dest,*dest.parents)),'overlay symlink excluded')
        if dest.exists():require(dest.is_file() and dest.read_bytes()==b,'never overwrite a differing overlay member')
        else:require(not verify_only,'missing overlay member')
    written=0
    if not verify_only:
        for p,b in files.items():
            dest=root/p
            if dest.exists():continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
            d=os.open(dest.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d);written+=1
    return dict(checks_passed=True,canonical_members=76,written=written,verify_only=verify_only,CP_rows_added=0,Git_member_blobs_created=0,old_requests_or_slots_executed=0,scientific_authorization_granted=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--envelope',required=True);p.add_argument('--manifest',required=True);p.add_argument('--project',required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    print(json.dumps(apply(a.envelope,a.manifest,a.project,a.verify_only),sort_keys=True))
