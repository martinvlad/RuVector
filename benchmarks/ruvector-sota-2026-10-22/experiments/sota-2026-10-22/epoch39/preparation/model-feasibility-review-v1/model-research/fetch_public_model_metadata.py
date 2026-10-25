"""Read only public model API/card/config metadata, never model/tokenizer payloads."""
from pathlib import Path
import urllib.request,urllib.error,json,hashlib,time
B=Path(__file__).resolve().parent
REPO='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
rows=[]
def fetch(url,name,cap=2*1024*1024):
 started=time.monotonic();request=urllib.request.Request(url,headers={'User-Agent':'RuVector-public-source-metadata-review/1.0'})
 try:
  with urllib.request.urlopen(request,timeout=30)as response:
   data=response.read(cap+1)
   if len(data)>cap:raise ValueError('Public metadata size cap exceeded; no payload read permitted')
   headers={k:response.headers.get(k)for k in ['content-type','etag','last-modified','x-repo-commit']if response.headers.get(k)}
   row={'url':url,'file':name,'HTTP_status':response.status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'safe_response_headers':headers,'seconds':time.monotonic()-started}
   (B/name).write_bytes(data);rows.append(row);return data
 except urllib.error.HTTPError as error:
  rows.append({'url':url,'file':name,'HTTP_status':error.code,'error':str(error),'seconds':time.monotonic()-started});return None
api=fetch('https://huggingface.co/api/models/'+REPO+'?blobs=true','HF_MODEL_API.live.json');value=json.loads(api);revision=value['sha'];assert len(revision)==40
for name in ['README.md','config.json','tokenizer_config.json','special_tokens_map.json']:
 fetch('https://huggingface.co/'+REPO+'/resolve/'+revision+'/'+name,name)
x={'schema_version':1,'status':'PUBLIC_MODEL_METADATA_ONLY_NO_ACQUISITION_OR_EXECUTION','repository':REPO,'resolved_revision':revision,'requests':rows,'network_metadata_GETs':len(rows),'weight_or_tokenizer_payload_downloads':0,'ML_model_tokenizer_native_calls':0,'actual_FinFact_case_oracle_reads':0,'paid_API_GPU_calls':0}
(B/'PUBLIC_METADATA_REQUESTS.v1.json').write_text(json.dumps(x,indent=2)+'\n')
print(json.dumps({'repository':REPO,'revision':revision,'GETs':len(rows),'files':[r['file']for r in rows if r.get('HTTP_status')==200]}))
