from pathlib import Path
import os,sys,json,hashlib,urllib.request,tempfile,base64,tarfile,io,subprocess
ROOT=Path(__file__).resolve().parents[4]
SCOPE=ROOT.parent
os.sched_setaffinity(0,{0,1})
def download(url,size,sha,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():raise ValueError('Preserve existing asset')
 h=hashlib.sha256();n=0
 with tempfile.NamedTemporaryFile(dir=target.parent,prefix='.download-',delete=False) as f:
  tmp=Path(f.name)
  with urllib.request.urlopen(url,timeout=120) as r:
   while block:=r.read(1024*1024):
    n+=len(block)
    if n>size:raise ValueError('Exceeded exact size')
    h.update(block);f.write(block)
  f.flush();os.fsync(f.fileno())
 try:
  if n!=size or h.hexdigest()!=sha:raise ValueError('Asset hash/size mismatch')
  os.link(tmp,target)
 finally:tmp.unlink(missing_ok=True)
 return {'url':url,'path':str(target.relative_to(ROOT)),'bytes':n,'sha256':h.hexdigest(),'model_native_calls':0}
url='https://huggingface.co/cross-encoder/nli-deberta-v3-large/resolve/bab4bc7178836f731dcfd18c06ca9def0a137712/onnx/model_quint8_avx2.onnx'
target=ROOT/'experiments/sota-2026-10-22/candidate/epoch15/assets/official-deberta-v3-large/onnx/model_quint8_avx2.onnx'
r=download(url,642857089,'821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754',target)
with (Path(__file__).parent/'selected-weight-acquisition.json').open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r),flush=True)

