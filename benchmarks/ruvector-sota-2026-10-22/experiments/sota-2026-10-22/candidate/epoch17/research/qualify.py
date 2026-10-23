from pathlib import Path
import urllib.request,urllib.error,json,hashlib,concurrent.futures
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
MODELS=['microsoft/deberta-v2-xlarge-mnli','microsoft/deberta-v2-xxlarge-mnli']
def fetch(url,name):
    at=datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(url,timeout=45)as r:
            b=r.read(3000000);status=r.status;final=r.url
        assert len(b)<3000000
    except urllib.error.HTTPError as e:
        b=e.read(100000);status=e.code;final=e.url
    with(P/name).open('xb')as f:f.write(b)
    return {'url':url,'at':at,'status':status,'final_url':final,'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},b

def one(i,repo):
    api,b=fetch('https://huggingface.co/api/models/'+repo+'?blobs=true',f'model-{i}-api.json')
    if api['status']!=200:return {'repo':repo,'api':api,'qualified':False}
    x=json.loads(b);rev=x['sha'];files=x.get('siblings',[]);wanted=['README.md','config.json','tokenizer_config.json','special_tokens_map.json']
    wanted += [v['rfilename']for v in files if v['rfilename'].lower()in ['license','license.txt','license.md']]
    receipts=[api];small={}
    for f in wanted:
        receipt,raw=fetch('https://huggingface.co/'+repo+'/resolve/'+rev+'/'+f,f'model-{i}-'+f.replace('/','_'));receipts.append(receipt)
        if receipt['status']==200 and f.endswith('.json'):small[f]=json.loads(raw)
    return {'repo':repo,'revision':rev,'cardData':x.get('cardData'),'pipeline_tag':x.get('pipeline_tag'),'tags':x.get('tags'),
      'files':files,'config':small.get('config.json'),'tokenizer_config':small.get('tokenizer_config.json'),'receipts':receipts,
      'official_ONNX':[v for v in files if v['rfilename'].endswith('.onnx')],'weight_files':[v for v in files if any(v['rfilename'].endswith(z)for z in ['.bin','.safetensors'])],
      'weights_downloaded':0,'model_sessions':0,'native_fit_paid_GPU_calls':0}
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as ex:r=list(ex.map(lambda z:one(*z),enumerate(MODELS)))
with(P/'qualification-metadata.json').open('x')as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write(chr(10))
for x in r:
 print(json.dumps({'repo':x['repo'],'revision':x.get('revision'),'config':x.get('config'),'cardData':x.get('cardData'),'weight_files':x.get('weight_files'),'official_ONNX':x.get('official_ONNX'),'api_error':x.get('api')}))
