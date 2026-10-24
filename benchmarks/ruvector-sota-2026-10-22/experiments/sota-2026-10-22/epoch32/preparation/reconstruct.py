from pathlib import Path,PurePosixPath
import os,json,hashlib,stat
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');OLD=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa');K=W/'kit';K.mkdir(mode=0o700)
def safe(p):
 assert not any(x.is_symlink()for x in(p,*p.parents)),str(p)
 assert p==p.resolve();return p
def put(path,raw):
 path.parent.mkdir(parents=True,exist_ok=True);safe(path)
 with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
def link(src,dst):
 safe(src);assert src.is_file()and stat.S_ISREG(src.stat().st_mode);dst.parent.mkdir(parents=True,exist_ok=True);safe(dst)
 if dst.exists():assert dst.read_bytes()==src.read_bytes()
 else:os.link(src,dst)
def verify(p,r):
 b=safe(p).read_bytes();assert len(b)==r['bytes']and hashlib.sha256(b).hexdigest()==r['sha256'],str(p)
rows=json.loads((W/'actual-git-map.json').read_text())['files'];assert len(rows)==4424
for r in rows:
 name=PurePosixPath(r['path']);assert not name.is_absolute()and '..'not in name.parts and '\\'not in str(name)and r['mode']=='100644'and r['type']=='blob'
 body=None
 for candidate in [OLD/'controls-final'/r['path'],OLD/'project'/r['path'],OLD/'kit'/r['path']]:
  if candidate.is_file():
   data=safe(candidate).read_bytes()
   if len(data)==r['size']and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==r['sha']:body=data;break
 assert body is not None,r['path'];put(K/r['path'],body)
C=json.loads((K/'CONTINUATION.json').read_text());assert C['active_run']['state']=='EPOCH31_CLOSED'and C['active_run']['work_active']is False
assert hashlib.sha256((K/'CHECKPOINT_MANIFEST.json').read_bytes()).hexdigest()==C['checkpoint_manifest_sha256']=='8662d03427f700179d3684f6afed91eb0f3e5c0fcf5a703178b1e20a325cc339'
cp=json.loads((K/'CHECKPOINT_MANIFEST.json').read_text())['project_files'];assert len(cp)==4350
gitpaths={r['path']for r in rows};missing=[r for r in cp if r['path']not in gitpaths]
expected={'experiments/sota-2026-10-22/epoch22/runs/dev/raw.json','experiments/sota-2026-10-22/epoch26/runs/dev/raw.json','experiments/sota-2026-10-22/epoch26/runs/dev/native-result.json'};assert{r['path']for r in missing}==expected
for r in missing:src=OLD/'project'/r['path'];verify(src,r);put(K/r['path'],src.read_bytes())
for r in cp:verify(K/r['path'],r)
km=json.loads((K/'KIT_MANIFEST.json').read_text())['project_files'];assert len(km)==61
for r in km:verify(K/r['path'],r)
bm={r['path']:r for r in json.loads((K/'BASE_PUBLIC_MANIFEST.json').read_text())['files']};base=W/'base-cache';base.mkdir(mode=0o700);paths=json.loads((K/'BASE_DOWNLOADS.json').read_text())['paths'];assert len(paths)==48
for name in paths:
 r=bm[name];src=OLD/'base-cache'/name
 if not src.is_file():src=OLD/'project'/name
 verify(src,r);put(base/name,src.read_bytes())
for name,h in [('bootstrap.py','eceb2ca259feaf642bc81172aca57a2a209cc34cd17f9b281861c51f21b95806'),('restore_checkpoint.py','affd9ecf660f380c3632f78cd14fb7a36e00797ceb097cf48c0c60136fac0be8')]:assert hashlib.sha256((K/name).read_bytes()).hexdigest()==h
for field in ['archive','extractor','publication_helper']:verify(K/C['artifact_transport'][field]['path'],C['artifact_transport'][field])
for d in C['epoch26_artifact_transports']['descriptors']:
 for field in ['archive','extractor','publication_helper']:verify(K/d[field]['path'],d[field])
verify(K/C['epoch26_artifact_transports']['manifest']['path'],C['epoch26_artifact_transports']['manifest'])
R=W/'project';R.mkdir(mode=0o700);union={}
for r in [*cp,*km,*[bm[n]for n in paths]]:
 if r['path']in union:assert r==union[r['path']],r['path']
 union[r['path']]=r
for name,r in union.items():
 src=K/name if(K/name).is_file()else base/name;verify(src,r);link(src,R/name)
for name,r in union.items():verify(R/name,r)
proof={'source_commit':'f8bcbc4ca7ec31c6732159cad60a6e223f93c539','actual_current_Git_SHA1_size_verified':4424,'CP_rows':4350,'CP_manifest_SHA256':C['checkpoint_manifest_sha256'],'KIT_rows':61,'BASE_rows':48,'fresh_project_union':len(union),'source_archives_and_three_original_virtual_artifacts_verified':True,'mode':'Fresh isolated workspace copies only after current actual Git SHA1/size; all4350CP SHA256 verified; project links solely inside fresh workspace; no prior cache trusted','archive_decoder_and_reviewed_bootstrap_status':'PENDING','model_native_gold_paid_GPU_calls':0}
put(W/'pre-restore-proof.json',(json.dumps(proof,indent=2)+'\n').encode());put(W/'expected-project-union.json',(json.dumps({'files':list(union.values())},indent=2)+'\n').encode());print(json.dumps(proof))

