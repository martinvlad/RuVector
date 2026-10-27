from pathlib import Path
import urllib.request,json,hashlib,datetime,time
R=Path('/dev/shm/ruvector-e54-candidate/research');R.mkdir(mode=0o700,exist_ok=True)
def fetch(name,url):
 start=time.monotonic();req=urllib.request.Request(url,headers={'User-Agent':'RuVector-authorized-public-source-qualification/epoch54'})
 record={'name':name,'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'max_body_bytes':2097152,'timeout_seconds':20,'retries':0,'model_tokenizer_native_DATA_Gold_calls':0}
 try:
  with urllib.request.urlopen(req,timeout=20) as f:
   b=f.read(2097153);assert len(b)<=2097152,'metadata body cap';record.update(status=f.status,final_url=f.url,bytes=len(b),sha256=hashlib.sha256(b).hexdigest());(R/(name+'.body')).write_bytes(b)
 except Exception as e:record['error']=str(e);b=None
 record['wall_seconds']=time.monotonic()-start
 (R/(name+'.receipt.json')).write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps(record),flush=True)
 return b
if __name__=='__main__':
 for model in ['tasksource/ModernBERT-base-nli','tasksource/ModernBERT-large-nli']:
  name=model.rsplit('/',1)[-1];b=fetch(name+'-api','https://huggingface.co/api/models/'+model)
  if b:
   d=json.loads(b);rev=d['sha'];print('REV',model,rev)
   for file in ['README.md','config.json']:
    fetch(name+'-'+file.replace('.','-'),'https://huggingface.co/'+model+'/raw/'+rev+'/'+file)
