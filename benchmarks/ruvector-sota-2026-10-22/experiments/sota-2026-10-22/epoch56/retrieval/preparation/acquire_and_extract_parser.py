"""Bounded public asset acquisition and parser extraction only; never import parser/model or decode qrels."""
from pathlib import Path
import argparse,hashlib,json,os,stat,sys,time,urllib.request,zipfile
W=Path('/dev/shm/ruvector-e56-retrieval')
A=Path('/tmp/ruvector-sota-2026-10-22/epoch56-parser-ffdd0699f325')
OWNER=Path('/dev/shm/ruvector-sota-2026-10-22/epoch56-ffdd0699f325/owner.json')
OWNER_SHA='1cd0cb9c7ac46476cba887ef0e9ef751daebea307fc8eb0678531af2a7799086'
def digest(p,kind='sha256'):
 h=hashlib.new(kind)
 if kind=='sha1':h.update(b'blob '+str(p.stat().st_size).encode()+b'\0')
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def put(p,v):
 b=(json.dumps(v,indent=2,sort_keys=True)+'\n').encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
def fence():
 assert digest(OWNER)==OWNER_SHA;o=json.loads(OWNER.read_bytes());assert time.time()<o['expires_unix'] and not(OWNER.parent/'release.request').exists();p=Path('/proc')/str(o['pid']);assert int((p/'stat').read_text().rsplit(')',1)[1].split()[19])==o['startticks'];s=(p/'fd/3').stat();assert(s.st_dev,s.st_ino)==(o['lock_device'],o['lock_inode']);assert 'FLOCK' in(p/'fdinfo/3').read_text()
def safe_root():
 assert not A.exists() and all(not p.is_symlink()for p in A.parents);A.mkdir(mode=0o700);(A/'assets').mkdir();(A/'parser').mkdir()
def main():
 if sys.flags.optimize!=0:raise ValueError('NONOPTIMIZED_PYTHON_REQUIRED')
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);a=p.parse_args();assert sorted(os.sched_getaffinity(0))==[0,1];planp=Path(a.plan);assert digest(planp)==a.sha256;plan=json.loads(planp.read_bytes());assert plan['epoch']==56 and plan['maximum_total_payload_bytes']==52*1024*1024 and len(plan['assets'])==4;fence();safe_root();put(A/'ACQUISITION_ATTEMPT.actual.v1.json',{'epoch':56,'plan_sha256':a.sha256,'maximum_invocations':1,'parser_imports':0,'qrels_label_decodes':0,'native_corpus_batches':0,'time_unix':time.time()})
 started=time.monotonic();receipts=[];total=0
 for row in plan['assets']:
  fence();assert row['name']==Path(row['name']).name;dest=A/'assets'/row['name'];partial=dest.with_suffix(dest.suffix+'.partial');before=time.monotonic();size=0
  with urllib.request.urlopen(row['url'],timeout=5)as response,partial.open('xb')as out:
   while True:
    assert time.monotonic()-before<60 and time.monotonic()-started<260;b=response.read(1048576)
    assert time.monotonic()-before<60 and time.monotonic()-started<260
    if not b:break
    size+=len(b);total+=len(b);assert size<=row['bytes'] and total<=plan['maximum_total_payload_bytes'];out.write(b)
   out.flush();os.fsync(out.fileno())
  assert size==row['bytes'];sha=digest(partial);git=digest(partial,'sha1')
  if 'sha256'in row:assert sha==row['sha256']
  if 'Git_blob'in row:assert git==row['Git_blob']
  partial.rename(dest);os.chmod(dest,0o400);receipts.append({'path':str(dest),'bytes':size,'sha256':sha,'Git_blob':git,'url':row['url'],'wall_seconds':time.monotonic()-before,'payload_decoded':False})
 wheel=next(A/'assets'/r['name']for r in plan['assets']if r['name'].endswith('.whl'));members=[]
 with zipfile.ZipFile(wheel)as z:
  infos=z.infolist();assert len(infos)<=5000 and sum(x.file_size for x in infos)<=400*1024*1024
  names=[x.filename for x in infos];assert len(names)==len(set(names))
  for i in infos:
   assert time.monotonic()-started<290
   n=Path(i.filename);assert not n.is_absolute()and '..'not in n.parts and n.parts[0]in('pyarrow','pyarrow-20.0.0.dist-info');mode=i.external_attr>>16;assert not stat.S_ISLNK(mode);target=A/'parser'/n
   if i.is_dir():target.mkdir(parents=True,exist_ok=True);continue
   assert i.file_size<=128*1024*1024;target.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();actual=0
   with z.open(i)as src,target.open('xb')as out:
    while True:
     assert time.monotonic()-started<290
     b=src.read(1048576)
     if not b:break
     actual+=len(b);assert actual<=i.file_size;h.update(b);out.write(b)
    out.flush();os.fsync(out.fileno())
   assert actual==i.file_size;os.chmod(target,0o400);members.append({'path':str(target),'bytes':actual,'sha256':h.hexdigest()})
 metadata=(A/'parser/pyarrow-20.0.0.dist-info/METADATA').read_text();assert '\nName: pyarrow\n'in'\n'+metadata and '\nVersion: 20.0.0\n'in'\n'+metadata
 licences=[x for x in members if 'license'in Path(x['path']).name.lower()or'notice'in Path(x['path']).name.lower()];assert licences
 fence();put(A/'PARSER_AND_DATA_ASSETS.actual.v1.json',{'epoch':56,'status':'OPAQUE_ASSETS_AND_PARSER_FILES_HASHED_NO_IMPORT_OR_LABEL_DECODE','assets':receipts,'parser_members':members,'parser_licence_and_notice_files':licences,'parser_imports':0,'qrels_label_decodes':0,'query_feature_decodes':0,'model_tokenizer_BGE_native_imports':0,'paid_API_GPU_calls':0,'native_corpus_batches':0,'wall_seconds':time.monotonic()-started,'existing_venv_mutations':0,'automatic_retries':0});print(json.dumps({'assets':len(receipts),'parser_members':len(members),'total_download_bytes':total,'manifest':str(A/'PARSER_AND_DATA_ASSETS.actual.v1.json'),'sha256':digest(A/'PARSER_AND_DATA_ASSETS.actual.v1.json')}))
if __name__=='__main__':main()
