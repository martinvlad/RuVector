from pathlib import Path,PurePosixPath
import hashlib,json,os,stat,shutil,time
W=Path('/workspace/ruvector-epoch36-d73fcce4c45f');K=W/'kit';R=W/'project';B=W/'base-cache'
OLD=Path('/workspace/ruvector-epoch35-4d51073072c4');DONORS=[OLD/'project',OLD/'kit',OLD/'base-cache']
def sha(b):return hashlib.sha256(b).hexdigest()
def safe(root,name):
 p=PurePosixPath(name)
 assert not p.is_absolute() and all(x not in ('','.','..') for x in name.split('/')) and '\\' not in name
 q=root/name;assert not any(v.is_symlink()for v in(q,*q.parents));return q
def checked(p,size,digest,git=False):
 assert stat.S_ISREG(p.stat().st_mode) and not any(q.is_symlink()for q in(p,*p.parents))
 b=p.read_bytes();assert len(b)==size and (hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest() if git else sha(b))==digest,str(p)
 return b
def put(p,b):
 p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def jsonput(p,v):put(p,(json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode())
assert not K.exists()and not R.exists()and not B.exists(),'Fresh scope only; never replay partial reconstruction'
started=time.monotonic();K.mkdir();R.mkdir();B.mkdir()
git=json.loads((W/'actual-git-map.json').read_text());rows=git['files'];assert len(rows)==5423 and len({r['path']for r in rows})==5423
for row in rows:
 name=row['path'];dest=safe(K,name)
 if name in ('CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json'):src=W/'remote-current'/name
 else:
  src=next((safe(d,name)for d in DONORS if safe(d,name).is_file()),None)
  assert src is not None,'Public source donor missing; fetch exact connected Git path instead: '+name
 b=checked(src,row['size'],row['sha'],True);put(dest,b);checked(dest,row['size'],row['sha'],True)
C=json.loads((K/'CONTINUATION.json').read_text());assert C['active_run']['work_active']is False
assert sha((K/'CHECKPOINT_MANIFEST.json').read_bytes())==C['checkpoint_manifest_sha256']=='86c4ea1e130e849715710b65559ebe83966f247b9c044411f7a6e19b04adf311'
cp=json.loads((K/'CHECKPOINT_MANIFEST.json').read_text())['project_files'];assert len(cp)==5349
virtual=[]
for row in cp:
 p=safe(K,row['path'])
 if not p.exists():
  src=next((safe(d,row['path'])for d in DONORS if safe(d,row['path']).is_file()),None);assert src is not None,row['path'];put(p,checked(src,row['bytes'],row['sha256']));virtual.append(row['path'])
 checked(p,row['bytes'],row['sha256'])
assert len(virtual)==3,virtual
km=json.loads((K/'KIT_MANIFEST.json').read_text())['project_files'];bm_raw=(K/'BASE_PUBLIC_MANIFEST.json').read_bytes();assert sha(bm_raw)=='0db67a018ad5fd9deba1cfb0bd8897537a330dd2353f169e6e387e86e09fce7a'
bm={x['path']:x for x in json.loads(bm_raw)['files']};bp=json.loads((K/'BASE_DOWNLOADS.json').read_text())['paths'];assert(len(km),len(bp))==(61,48)
for row in km:checked(safe(K,row['path']),row['bytes'],row['sha256'])
for name in bp:
 row=bm[name];src=next((safe(d,name)for d in [OLD/'base-cache',OLD/'project',OLD/'kit']if safe(d,name).is_file()),None);assert src is not None,name
 put(safe(B,name),checked(src,row['bytes'],row['sha256']))
union={}
for original in [*cp,*km,*[bm[n]for n in bp]]:
 row={k:original[k]for k in ('path','bytes','sha256')};name=row['path']
 if name in union:assert union[name]==row,name
 union[name]=row
assert len(union)==5428,len(union)
for name,row in union.items():
 src=safe(K,name)if safe(K,name).is_file()else safe(B,name);checked(src,row['bytes'],row['sha256']);dst=safe(R,name);dst.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.link(src,dst);checked(dst,row['bytes'],row['sha256'])
for path,row in [(x['path'],x)for x in cp]:checked(safe(R,path),row['bytes'],row['sha256'])
proof=dict(source_commit='d73fcce4c45f7d8f6f1c5bfbf3599ceddf560be3',actual_current_Git_SHA1_size_verified=5423,CP_rows=5349,CP_manifest_SHA256=C['checkpoint_manifest_sha256'],KIT_rows=61,BASE_rows=48,fresh_project_union=len(union),virtual_original_archive_artifacts=virtual,all_hashes_checked=True,old_filesystem_trusted_without_hash=False,fresh_physical_source_copies=True,hardlinks_only_within_fresh_scope=True,model_native_tokenizer_gold_paid_GPU_calls=0,archive_decoders_bootstrap_restore_status='PENDING',wall_seconds=time.monotonic()-started)
jsonput(W/'expected-project-union.json',dict(files=list(union.values())));jsonput(W/'pre-restore-proof.json',proof)
for parent in [W,K,R,B]:
 fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(proof),flush=True)
