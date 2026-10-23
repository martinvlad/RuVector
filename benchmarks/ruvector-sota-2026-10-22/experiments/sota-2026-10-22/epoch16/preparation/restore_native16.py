from pathlib import Path
import json,hashlib,base64,urllib.request,tarfile,io,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];SCOPE=ROOT.parent
os.sched_setaffinity(0,{0,1})
row=json.loads((ROOT/'package-lock.json').read_text())['packages']['node_modules/@ruvector/typesafe']
assert row['version']=='0.2.0' and row['resolved']=='https://registry.npmjs.org/@ruvector/typesafe/-/typesafe-0.2.0.tgz'
with urllib.request.urlopen(row['resolved'],timeout=90) as r:
 raw=r.read(150_000_001)
assert len(raw)<=150_000_000,'Package archive too large; STOP'
assert 'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode()==row['integrity'],'NPM archive integrity mismatch'
spec=ROOT/'experiments/sota-2026-10-22/candidate/epoch5/reconstruction/typesafe-runtime-closure.json'
assert hashlib.sha256(spec.read_bytes()).hexdigest()=='363bb39e63fd6fb212a0aed25974443f5a286ca5eaff867314f3daad5fbe0718'
rows=json.loads(spec.read_text())['files'];assert len(rows)==14
cache=SCOPE/'typesafe-cache';cache.mkdir(mode=0o700)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
 for item in rows:
  name='package/'+item['path'].removeprefix('node_modules/@ruvector/typesafe/')
  m=tar.getmember(name);assert m.isfile() and m.size==item['bytes']
  b=tar.extractfile(m).read(item['bytes']+1);assert len(b)==item['bytes'] and hashlib.sha256(b).hexdigest()==item['sha256']
  out=cache/item['path'];out.parent.mkdir(parents=True,exist_ok=True)
  with out.open('xb') as f:f.write(b)
cmd=[sys.executable,str(ROOT/'experiments/sota-2026-10-22/candidate/epoch5/reconstruction/restore_runtime.py'),'--project-root',str(ROOT),'--core-cache-root',str(SCOPE/'core-cache'),'--typesafe-cache-root',str(cache),'--receipt',str(Path(__file__).parent/'runtime-closure.json')]
r=subprocess.run(cmd,check=True,text=True,capture_output=True)
receipt={'status':'NATIVE22_EXACT_BYTES_MATERIALIZED_NO_EXECUTION','typesafe_archive_bytes':len(raw),'typesafe_archive_SHA256':hashlib.sha256(raw).hexdigest(),'npm_integrity':row['integrity'],'source':row['resolved'],'core_acquirer':'restore_native_closure.py reviewed rootkit','materializer':'candidate/epoch5/reconstruction/restore_runtime.py','result':json.loads(r.stdout),'native_loads_or_model_sessions':0}
with (Path(__file__).parent/'native-restoration.json').open('x') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt),flush=True)

