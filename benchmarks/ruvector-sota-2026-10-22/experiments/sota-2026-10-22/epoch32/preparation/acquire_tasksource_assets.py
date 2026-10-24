from pathlib import Path
import os,json,hashlib,time,urllib.request,urllib.error,subprocess
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');D=Path('/workspace/ruvector-e32-reader-assets/tasksource-212de447')
META=Path('/workspace/ruvector-e32-reader-impl/METADATA_ADMISSION.json');META_SHA='978b7e07c64b28c456a00a11c2ff5c278721f3f270de26be0e12701883b38669'
def shafile(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def sync(d):
 f=os.open(d,os.O_RDONLY|os.O_DIRECTORY);os.fsync(f);os.close(f)
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 sync(p.parent)
def guard():subprocess.run(['python','-B',str(W/'mutation_guard.py'),'guard'],check=True,capture_output=True)
def main():
 guard();assert shafile(META)==META_SHA;m=json.loads(META.read_text());assert m['repository']=='sileod/deberta-v3-large-tasksource-nli'and m['revision']=='212de447184bda8fb9415a2e5697846864ddf304';assert len(m['assets'])==9 and sum(r['bytes']for r in m['assets'])==1751462486
 assert not D.exists();D.mkdir(parents=True,mode=0o700);sync(D.parent);assert D==D.resolve()and not any(p.is_symlink()for p in(D,*D.parents))
 v=os.statvfs(D);assert v.f_bavail*v.f_frsize>=1751462486+268435456
 plan={'schema_version':1,'epoch':32,'kind':'PUBLIC_PINNED_ASSET_ACQUISITION_NO_MODEL_EXECUTION','repository':m['repository'],'revision':m['revision'],'metadata_admission_sha256':META_SHA,'exact_directory':str(D),'assets':m['assets'],'max_bytes':1751462486,'max_wall_seconds':900,'new_paid_API_calls':0,'GPU_calls':0,'no_credentials_or_signed_redirect_URLs_recorded':True,'public_license_declaration':'Apache-2.0; full training lineage remains LIMITED and CONF/promotion/official eligibility HOLD'}
 put(W/'asset-acquisition-plan.json',plan);started=time.monotonic();rows=[]
 for a in m['assets']:
  guard();assert time.monotonic()-started<900;name=a['path'];assert '/'not in name and '\\'not in name and name not in('.','..');url=a['source_url'];assert url=='https://huggingface.co/'+m['repository']+'/resolve/'+m['revision']+'/'+name
  tmp=D/(name+'.part');n=0;h=hashlib.sha256();g=hashlib.sha1(b'blob '+str(a['bytes']).encode()+b'\0');t=time.monotonic()
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'RuVector-public-source-acquisition-epoch32','Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=60)as response,tmp.open('xb')as out:
    status=response.status;assert status==200
    for b in iter(lambda:response.read(1048576),b''):
     n+=len(b);assert n<=a['bytes']and time.monotonic()-started<900;out.write(b);h.update(b);g.update(b)
    out.flush();os.fsync(out.fileno())
   assert n==a['bytes']
   if a.get('upstream_sha256'):assert h.hexdigest()==a['upstream_sha256']
   else:assert g.hexdigest()==a['upstream_git_blob_sha1']
   if a.get('metadata_body_sha256'):assert h.hexdigest()==a['metadata_body_sha256']
   dest=D/name;assert not dest.exists();os.rename(tmp,dest);sync(D);guard()
   row={'path':name,'bytes':n,'sha256':h.hexdigest(),'upstream_git_blob_sha1':a['upstream_git_blob_sha1'],'source_url':url}
   if a.get('upstream_sha256'):row['upstream_sha256']=a['upstream_sha256']
   rows.append(row);put(W/('asset-acquisition-'+name.replace('.','_')+'.json'),{'asset':row,'HTTP_status':status,'wall_seconds':time.monotonic()-t,'opaque_asset_only':True,'model_tokenizer_native_initializations':0})
   print(json.dumps({'asset':name,'bytes':n,'sha256':h.hexdigest(),'verified':True}),flush=True)
  except BaseException as error:
   put(W/'asset-acquisition-error.json',{'asset':name,'canonical_source_url':url,'error_type':type(error).__name__,'HTTP_code':getattr(error,'code',None),'bytes_captured':n,'automatic_retry':False,'no_model_tokenizer_native_init':True})
   raise
 lock={'schema_version':1,'epoch':32,'kind':'REAL_NATIVE_TASKSOURCE_PRETRAINED_NLI_DIAGNOSTIC','repository':m['repository'],'revision':m['revision'],'model_directory':str(D),'files':rows}
 put(D/'asset-lock.json',lock);receipt={'epoch':32,'directory':str(D),'asset_count':9,'total_asset_bytes':sum(r['bytes']for r in rows),'all_upstream_sha256_or_Git_blob_identities_verified':True,'model_assets_lock':{'path':str(D/'asset-lock.json'),'bytes':(D/'asset-lock.json').stat().st_size,'sha256':shafile(D/'asset-lock.json')},'wall_seconds':time.monotonic()-started,'new_paid_API_GPU_model_tokenizer_native_calls':0,'training_lineage_and_eligibility_remain_HOLD':True}
 put(W/'asset-acquisition-complete.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()

