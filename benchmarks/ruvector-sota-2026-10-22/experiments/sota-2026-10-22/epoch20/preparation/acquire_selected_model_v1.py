import pathlib,json,hashlib,urllib.request,os,time,signal,datetime
os.sched_setaffinity(0,{0,1})
s=pathlib.Path('/tmp/ruvector-sota-2026-10-22/epoch20-f5588491b31d');p=s/'project';lock=p/'experiments/sota-2026-10-22/legal-transfer/epoch20/model-assets.lock.json'
assert hashlib.sha256(lock.read_bytes()).hexdigest()=='ea5e4c687e3f2d046837f3792e8fa43409d26c3e2f8dd8791137c1db8a6e54f9'
def timeout(*a):raise TimeoutError('one public asset acquisition exceeded300seconds')
signal.signal(signal.SIGALRM,timeout);signal.alarm(300);start=time.monotonic();rows=[];gets=0
for r in json.loads(lock.read_bytes())['assets']:
 f=p/r['path'];assert f.resolve().is_relative_to(p)and not any(x.is_symlink()for x in [f,*f.parents]);f.parent.mkdir(parents=True,exist_ok=True)
 if f.exists():
  h=hashlib.sha256(f.read_bytes()).hexdigest();assert f.stat().st_size==r['bytes']and h==r['sha256'];mode='EXACT_PUBLIC_METADATA_REVERIFIED'
 else:
  assert r['remote_path']=='pytorch_model.bin';temp=f.with_name(f.name+'.partial');assert not temp.exists();h=hashlib.sha256();n=0;gets+=1
  with urllib.request.urlopen(r['source_url'],timeout=60)as response,temp.open('xb')as out:
   assert response.status==200
   while True:
    b=response.read(1024*1024)
    if not b:break
    n+=len(b);assert n<=r['bytes'];h.update(b);out.write(b)
   out.flush();os.fsync(out.fileno())
  assert n==r['bytes']and h.hexdigest()==r['sha256'];temp.rename(f);mode='ONE_OFFICIAL_PUBLIC_TLS_GET_SHA256_VERIFIED'
 rows.append({'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256'],'source_url':r['source_url'],'mode':mode})
signal.alarm(0);v={'schema_version':1,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'EXACT_SELECTED_ORIGINAL_PUBLIC_ASSETS_ACQUIRED_NO_INFERENCE','model':'ynie/roberta-large-snli_mnli_fever_anli_R1_R2_R3-nli','revision':'5b605abab9b75bc87ab66cfc049ef58d9d64b8ed','assets':rows,'actual_weight_TLS_GETs':gets,'elapsed_seconds':time.monotonic()-start,'model_native_fit_paid_GPU_calls':0,'models_imported':[],'weights_republished':False}
o=p/'experiments/sota-2026-10-22/epoch20/preparation/selected-model-acquisition-v1.json'
with o.open('x')as out:json.dump(v,out,sort_keys=True,indent=2);out.write('\n')
print(json.dumps({'status':v['status'],'files':len(rows),'weight_TLS_GETs':gets,'elapsed_seconds':v['elapsed_seconds'],'receipt_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'model_native_calls':0},sort_keys=True))
