"""Public137 overlay AFTER normal bootstrap/restore; never runs scientific code."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path,PurePosixPath
import argparse,base64,hashlib,io,json,os,tarfile,stat
OLD=Path('/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725')
BLOCKED=[OLD/x for x in('project','kit','base-cache','publication')]
ROOTS=tuple('experiments/sota-2026-10-22/'+x+'/'for x in('epoch44','audit/epoch44','runtime/epoch44'))
ARCHIVE_SHA='cadeb366a64fee95f90d55ea7d2516738e861710b1567b20df9ad0216c235f0f'
def require(ok,s):
 if not ok:raise ValueError(s)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(p):
 p=Path(p);require(p.is_absolute()and '..'not in p.parts and p.resolve()==p,'Canonical absolute path')
 require(not any(q.is_symlink()for q in(p,*p.parents)),'No symlink');return p
def body(p):
 p=canonical(p);require(stat.S_ISREG(p.stat().st_mode),'Regular input');return p.read_bytes()
def rel(s):
 require(type(s)is str and s and not PurePosixPath(s).is_absolute()and '\\'not in s and all(x not in('','.','..')for x in s.split('/')),'Canonical project path');return s
def exact(p,r):
 b=body(p);require(type(r['bytes'])is int and len(b)==r['bytes']and sha(b)==r['sha256'],'Exact file identity');return b
def write(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);canonical(p.parent)
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def validate(envelope,overlay):
 require(set(envelope)=={'schema_version','format','archive_bytes','archive_sha256','content_base64'},'Exact envelope keys')
 require(type(envelope['schema_version'])is int and envelope['schema_version']==1 and envelope['format']=='tar.gz','Explicit archive format')
 require(envelope['archive_bytes']==367801 and envelope['archive_sha256']==ARCHIVE_SHA and len(envelope['content_base64'])<600000,'Pinned bounded archive')
 raw=base64.b64decode(envelope['content_base64'],validate=True);require(len(raw)==367801 and sha(raw)==ARCHIVE_SHA,'Archive exact SHA/size')
 rows=overlay['files'];require(overlay['schema_version']==1 and overlay['epoch']==44 and overlay['source_commit']=='3e6259950c02850d2ce256afea7727a3c1a946bb'and len(rows)==137,'Exact overlay scope')
 expected={rel(r['path']):r for r in rows};require(len(expected)==137 and sum(r['source_Git_present']is True for r in rows)==82 and sum(r['source_Git_present']is False for r in rows)==55,'Separate82existing/55overlay; no CP mutation')
 require(all(type(r['bytes'])is int and 0<=r['bytes']<=2000000 and type(r['source_Git_present'])is bool and any(p.startswith(root)for root in ROOTS)for p,r in expected.items()),'Only reviewed science roots')
 require(sum(r['bytes']for r in rows)==1469537,'Exact bounded uncompressed size')
 files={}
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz')as archive:
  members=archive.getmembers();require(len(members)==137,'Exact137members')
  for m in members:
   require(m.isreg()and not m.issym()and not m.islnk()and m.name.startswith('epoch44-public-artifacts/'),'Only canonical regular members')
   name=rel(m.name[len('epoch44-public-artifacts/'):]);require(name in expected and name not in files,'Exact unique membership');row=expected[name];require(m.size==row['bytes'],'Member size')
   f=archive.extractfile(m);b=f.read(row['bytes']+1);require(len(b)==row['bytes']and sha(b)==row['sha256'],'Member exact content');files[name]=b
 require(set(files)==set(expected),'Every reviewed member present');return files,expected

def run(a):
 scope=canonical(a.restore_scope);kit=canonical(a.kit);dest=canonical(a.dest);require(scope.is_dir()and kit.is_dir()and dest.is_dir()and kit!=dest and not kit.is_relative_to(dest)and not dest.is_relative_to(kit),'Existing isolated KIT/project')
 for p in(scope,kit,dest):
  require(not any(p==bad or p.is_relative_to(bad)or bad.is_relative_to(p)for bad in BLOCKED),'Never current or old public cache')
 require(kit.is_relative_to(scope)and dest.is_relative_to(scope),'Fresh explicit restore scope')
 eb=body(a.envelope);ob=body(a.overlay);require(sha(eb)==a.expected_envelope_sha and sha(ob)==a.expected_overlay_sha,'Exact outer envelope/overlay descriptors');files,expected=validate(json.loads(eb),json.loads(ob))
 for root in(kit,dest):
  for path,b in files.items():
   target=root/rel(path);canonical(target)
   if a.verify_only or expected[path]['source_Git_present']:require(target.exists()and body(target)==b,'Source82/allverified-existing exact')
   else:require(not target.exists(),'Fresh55mustnotexist before overlay; no silent overwrite/replay')
 if not a.verify_only:
  write(scope/'E44_ARCHIVE_OVERLAY_ATTEMPT.json',json.dumps({'epoch':44,'operation':'PUBLIC_METADATA_OVERLAY_ONLY_NO_SCIENCE','files':137,'new_files_per_root':55}).encode())
  for root in(kit,dest):
   for path,b in files.items():
    if not expected[path]['source_Git_present']:write(root/path,b)
 return {'checks_passed':True,'epoch':44,'verify_only':a.verify_only,'all137_members_validated_before_write':True,'source82_byte_identical':True,'new55_canonical_overlay_per_root':55,'CP_project_files_modified':False,'science_or_model_or_Gold_or_API_calls':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--restore-scope',type=Path,required=True);p.add_argument('--kit',type=Path,required=True);p.add_argument('--dest',type=Path,required=True);p.add_argument('--envelope',type=Path,required=True);p.add_argument('--expected-envelope-sha',required=True);p.add_argument('--overlay',type=Path,required=True);p.add_argument('--expected-overlay-sha',required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args();print(json.dumps(run(a),sort_keys=True))
