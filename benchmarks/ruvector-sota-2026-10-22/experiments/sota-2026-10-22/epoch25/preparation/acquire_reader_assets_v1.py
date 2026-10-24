"""CC0-1.0. Acquire exact public, licensed reader bytes; never initialize a model.
Only original pinned public URLs, hashes, sizes/statuses are recorded. Redirect
URLs and authentication material are excluded. Streaming avoids duplicate files.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,time,urllib.request
P='experiments/sota-2026-10-22/'
def put(p,x):
 with p.open('x')as f:json.dump(x,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
 a=argparse.ArgumentParser();a.add_argument('--project',type=Path,required=True);n=a.parse_args();root=n.project;assert root.resolve()==root;study=root/P/'epoch25';manifest=root/P/'candidate/epoch25/MODEL_ASSETS.json';lock=json.loads(manifest.read_text());assert lock['revision']=='c1899de289a04d12100db370d81485cdf75e47ca' and lock['license']=='Apache-2.0' and len(lock['assets'])==8
 expected=sum(r['bytes'] for r in lock['assets']);assert expected==1519193708
 cap=int(Path('/sys/fs/cgroup/memory.max').read_text());current=int(Path('/sys/fs/cgroup/memory.current').read_text());projected=current+expected+751632384*4+1200000000
 assert shutil.disk_usage(root).free-expected>=512000000,'Need512MBfree disk reserve after acquisition'
 assert projected+1000000000<=cap,'Need1GBmemory reserve after conservative FP32+download+1.2GBaux estimate'
 out={'schema_version':1,'epoch':25,'kind':'PUBLIC_PINNED_READER_ASSET_ACQUISITION_ONLY','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'declared_price_USD':0,'paid_API_calls':0,'GPU_calls':0,'native_model_tokenizer_initializations':0,'disk_free_before':shutil.disk_usage(root).free,'memory_current_before':current,'memory_cap':cap,'conservative_projected_model_peak':projected,'memory_reserve_bytes':1000000000,'download_seconds_cap':240,'assets':[]};start=time.monotonic();error=None
 try:
  for r in lock['assets']:
   assert r['source_url'].startswith('https://huggingface.co/Qwen/Qwen3-0.6B/resolve/'+lock['revision']+'/')
   path=root/r['path'];assert path.resolve()==path and not path.exists();path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.download-part');h=hashlib.sha256();count=0;t=time.monotonic()
   try:
    with urllib.request.urlopen(r['source_url'],timeout=30)as response,tmp.open('xb')as f:
     status=response.status;assert status==200
     while True:
      assert time.monotonic()-start<=240,'Acquisition deadline'
      b=response.read(1024*1024)
      if not b:break
      count+=len(b);assert count<=r['bytes'],'Unexpected oversized body';h.update(b);f.write(b)
     f.flush();os.fsync(f.fileno())
    assert count==r['bytes'] and h.hexdigest()==r['sha256'],'Asset hash/byte mismatch';tmp.rename(path)
    out['assets'].append({'path':r['path'],'bytes':count,'sha256':h.hexdigest(),'source_url':r['source_url'],'HTTP_status':status,'seconds':time.monotonic()-t,'verified':True})
   except BaseException:
    if tmp.exists():tmp.unlink()
    raise
 except BaseException as e:error={'type':type(e).__name__,'message':str(e)}
 out.update(complete=error is None and len(out['assets'])==8,error=error,seconds=time.monotonic()-start,disk_free_after=shutil.disk_usage(root).free)
 put(study/'preparation/reader-assets-acquisition.json',out);print(json.dumps({'complete':out['complete'],'assets':len(out['assets']),'bytes':sum(r['bytes'] for r in out['assets']),'seconds':out['seconds'],'error':error,'model_native_tokenizer_calls':0}))
 return 0 if out['complete'] else 2
if __name__=='__main__':raise SystemExit(main())
