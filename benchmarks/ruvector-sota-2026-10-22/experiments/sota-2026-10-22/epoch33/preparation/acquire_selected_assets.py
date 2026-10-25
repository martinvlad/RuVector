from pathlib import Path
import hashlib,json,os,stat,time,urllib.request,ssl
W=Path('/workspace/ruvector-epoch33-0522a2c521c9');R=W/'project';M=Path('/workspace/ruvector-e33-reader-assets/moritz-b3546ea6')
LOCK=R/'experiments/sota-2026-10-22/legal-transfer/epoch21/model-assets.lock.json';EXPECTED='fafdae110e1f0dfb97bc51e61af3d012d64be3f18236ae1addab7c56a19b5400'
REPO='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli';REV='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
CACHES=[Path('/tmp/ruvector-sota-2026-10-22/epoch21-dd6da5427108/project/experiments/sota-2026-10-22/candidate/epoch21/assets/official-deberta-v3-large-nli'),Path('/tmp/ruvector-sota-2026-10-22/epoch22-f190247e1a30/project/experiments/sota-2026-10-22/candidate/epoch22/assets/official-deberta-v3-large-nli'),Path('/workspace/ruvector-e32-reader-assets/tasksource-212de447')]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def put(path,value):
 with path.open('x')as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
assert sha(LOCK)==EXPECTED;old=json.loads(LOCK.read_text());assert old['repository']==REPO and old['revision']==REV and len(old['assets'])==9
assert not M.exists();M.mkdir(mode=0o700,parents=True);assert not any(p.is_symlink()for p in(M,*M.parents))
plan=dict(epoch=33,repository=REPO,revision=REV,model_directory=str(M),files=[dict(path=r['remote_path'],bytes=r['bytes'],sha256=r['sha256'],source_url=r['source_url'])for r in old['assets']],maximum_free_public_GETs=9,maximum_acquisition_seconds=300,paid_calls=0,GPU_calls=0,model_native_tokenizer_initializations=0,rule='Verify current-CP official exact-revision identities; use only hash-matching public caches or free official pinned HTTPS through inherited proxy/TLS. No probes or automatic retries. Never persist signed redirect URLs.')
put(W/'asset-acquisition-plan.json',plan);started=time.monotonic();rows=[];receipts=[];gets=0
ca=os.environ.get('SSL_CERT_FILE')or os.environ.get('REQUESTS_CA_BUNDLE');ctx=ssl.create_default_context(cafile=ca if ca else None)
for item in old['assets']:
 name=item['remote_path'];assert name==Path(name).name and item['source_url']=='https://huggingface.co/'+REPO+'/resolve/'+REV+'/'+name
 dest=M/name;source=None
 for cache in CACHES:
  p=cache/name
  if p.is_file()and not any(q.is_symlink()for q in(p,*p.parents))and p.stat().st_size==item['bytes']and sha(p)==item['sha256']:source=p;break
 h=hashlib.sha256();size=0;method='VERIFIED_PUBLIC_CACHE_COPY'if source else'FREE_PINNED_OFFICIAL_HTTPS';t=time.monotonic()
 with dest.open('xb')as out:
  if source:incoming=source.open('rb')
  else:
   assert gets<9 and time.monotonic()-started<300;gets+=1;request=urllib.request.Request(item['source_url'],headers={'Accept-Encoding':'identity','User-Agent':'RuVector-public-source-reproduction'})
   incoming=urllib.request.urlopen(request,timeout=45,context=ctx);assert incoming.status==200
  with incoming:
   for b in iter(lambda:incoming.read(1048576),b''):
    assert time.monotonic()-started<300,'Asset deadline reached; stop, no retry';size+=len(b);assert size<=item['bytes'];h.update(b);out.write(b)
  out.flush();os.fsync(out.fileno())
 assert size==item['bytes']and h.hexdigest()==item['sha256'],name
 if not item.get('upstream_lfs_sha256'):
  b=dest.read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==item['upstream_git_blob_sha1']
 else:assert h.hexdigest()==item['upstream_lfs_sha256']
 row=dict(path=name,bytes=size,sha256=h.hexdigest(),upstream_git_blob_sha1=item['upstream_git_blob_sha1'],source_url=item['source_url']);rows.append(row)
 receipt=dict(row,method=method,elapsed_seconds=time.monotonic()-t,paid_or_GPU_calls=0,raw_redirect_URL_persisted=False);receipts.append(receipt);put(W/('asset-acquisition-'+str(len(rows))+'.json'),receipt);print(json.dumps(dict(path=name,method=method,bytes=size)),flush=True)
lock=dict(schema_version=1,epoch=33,kind='REAL_NATIVE_PROOF_CARRYING_NLI_DIAGNOSTIC',repository=REPO,revision=REV,model_directory=str(M),files=rows)
put(M/'asset-lock.json',lock);put(W/'asset-acquisition-complete.json',dict(epoch=33,files=9,bytes=sum(r['bytes']for r in rows),free_public_GETs=gets,total_seconds=time.monotonic()-started,asset_lock_sha256=sha(M/'asset-lock.json'),model_native_tokenizer_paid_GPU_calls=0,TLS_verification_enabled=True,inherited_proxy_preserved=True))
print(json.dumps(dict(acquisition_complete=True,files=9,asset_lock_sha256=sha(M/'asset-lock.json'),model_native_initializations=0)),flush=True)
