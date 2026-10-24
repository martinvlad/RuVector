from pathlib import Path
import os,json,hashlib,stat
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');K=W/'kit';R=W/'project'
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(p,r):
 assert not any(q.is_symlink()for q in(p,*p.parents))and p==p.resolve()and stat.S_ISREG(p.stat().st_mode)
 b=p.read_bytes();assert len(b)==r['bytes']and sha(b)==r['sha256'],str(p)
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
assert R.is_dir()and not any(R.iterdir()),'Known V1 stopped before project files; refuse unexpected partial root'
rows=json.loads((W/'actual-git-map.json').read_text())['files'];assert len(rows)==4424
for r in rows:
 p=K/r['path'];b=p.read_bytes();assert len(b)==r['size']and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['sha'],r['path']
C=json.loads((K/'CONTINUATION.json').read_text());assert sha((K/'CHECKPOINT_MANIFEST.json').read_bytes())==C['checkpoint_manifest_sha256']=='8662d03427f700179d3684f6afed91eb0f3e5c0fcf5a703178b1e20a325cc339';assert C['active_run']['state']=='EPOCH31_CLOSED'and C['active_run']['work_active']is False
cp=json.loads((K/'CHECKPOINT_MANIFEST.json').read_text())['project_files'];km=json.loads((K/'KIT_MANIFEST.json').read_text())['project_files'];bm={r['path']:r for r in json.loads((K/'BASE_PUBLIC_MANIFEST.json').read_text())['files']};paths=json.loads((K/'BASE_DOWNLOADS.json').read_text())['paths'];assert(len(cp),len(km),len(paths))==(4350,61,48)
for r in cp:verify(K/r['path'],r)
for r in km:verify(K/r['path'],r)
for name in paths:verify(W/'base-cache'/name,bm[name])
union={};common=('path','bytes','sha256')
for row in [*cp,*km,*[bm[n]for n in paths]]:
 r={k:row[k]for k in common}
 if r['path']in union:assert r==union[r['path']],r['path']
 union[r['path']]=r
assert len(union)==4429,len(union)
for name,r in union.items():
 src=K/name if(K/name).is_file()else W/'base-cache'/name;verify(src,r);dst=R/name;dst.parent.mkdir(parents=True,exist_ok=True);assert not dst.exists()and not dst.is_symlink();os.link(src,dst)
for name,r in union.items():verify(R/name,r)
proof={'source_commit':'f8bcbc4ca7ec31c6732159cad60a6e223f93c539','actual_current_Git_SHA1_size_verified':4424,'CP_rows':4350,'CP_manifest_SHA256':C['checkpoint_manifest_sha256'],'KIT_rows':61,'BASE_rows':48,'fresh_project_union':len(union),'all_three_virtual_original_archive_artifacts_verified':True,'prior_source_or_filesystem_trusted_without_hash':False,'V1_source_only_error':'Common source content matched; initial union compared KIT source_path provenance against CP ref3. V2 compares exact common path/bytes/SHA, preserving every original manifest byte. V1 created no project files.','archive_decoders_bootstrap_restore_status':'PENDING','model_native_gold_paid_GPU_calls':0}
put(W/'pre-restore-proof.json',proof);put(W/'expected-project-union.json',{'files':list(union.values())});print(json.dumps(proof))

