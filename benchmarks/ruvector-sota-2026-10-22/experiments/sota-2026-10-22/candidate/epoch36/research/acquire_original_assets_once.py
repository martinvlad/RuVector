"""Root-admitted E36 original public payload acquisition. No ML imports/execution.
Default is plan-only. Never resume/retry a failed or uncertain acquisition.
"""
import argparse,fcntl,hashlib,json,os,signal,stat,sys,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
W=Path('/workspace/ruvector-epoch36-d73fcce4c45f');G=Path('/tmp/ruvector-sota-2026-10-22/epoch36-d73fcce4c45f')
A=Path('/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd');REV='8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06'
ASSETS=[dict(path='pytorch_model.bin',bytes=3133958098,sha256='5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db'),dict(path='spm.model',bytes=2447305,sha256='5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17')]
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def guard():
 assert hashlib.sha256((G/'owner.json').read_bytes()).hexdigest()=='9267c9ff873f510ba4ca8e2992d6f0634189023787bd551bf70c4fc32eb084f6'
 o=json.loads((G/'owner.json').read_text());assert(o['pid'],o['startticks'],o['lock_device'],o['lock_inode'],o['expires_unix'])==(106933,23768446,33,13626,1792924782.5591424)
 assert not(G/'release.request').exists()and time.time()<o['expires_unix']-615
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4632fb06-b0ef-4df5-b72b-0e875bbad810'and Path('/proc/self/ns/pid').stat().st_ino==4026532200
 f=Path('/proc/106933/stat').read_text().rsplit(')',1)[1].split();assert int(f[19])==23768446 and f[0]not in('Z','X')
 p=Path('/proc/106933/fd/3');s=p.stat();assert(s.st_dev,s.st_ino)==(33,13626)and os.sched_getaffinity(106933)=={0,1}
 lock=Path(o['lock']);assert(lock.stat().st_dev,lock.stat().st_ino)==(33,13626)and os.readlink(p)==str(lock)
 rows=Path('/proc/locks').read_text().splitlines();assert any('FLOCK' in x and 'WRITE' in x and x.split()[4]=='106933'and x.split()[5].endswith(':13626')and tuple(int(v,16)for v in x.split()[5].split(':')[:2])==(os.major(33),os.minor(33))for x in rows)
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:fcntl.flock(fd,fcntl.LOCK_UN);raise AssertionError('Exact scoped owner absent')
 finally:os.close(fd)
 assert not any((W/'project/experiments/sota-2026-10-22/epoch36'/n).exists()for n in('DISPATCH_RESERVATION.json','DISPATCH_ATTEMPT.json','runs'))
 return o
def safe_host(url):
 u=urllib.parse.urlsplit(url);h=u.hostname or''
 return u.scheme=='https'and not u.username and not u.password and(u.port in(None,443))and(h=='huggingface.co'or h.endswith('.huggingface.co')or h.endswith('.hf.co')or h.endswith('.xethub.hf.co'))
class Redirect(urllib.request.HTTPRedirectHandler):
 def __init__(self):self.events=[]
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  assert len(self.events)<2 and safe_host(newurl),'Unapproved redirect or cap'
  self.events.append(dict(code=code,source_host=urllib.parse.urlsplit(req.full_url).hostname,target_host=urllib.parse.urlsplit(newurl).hostname))
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--plan',type=Path,required=True);p.add_argument('--admission',type=Path);p.add_argument('--metadata-dir',type=Path,required=True);a=p.parse_args()
 plan=json.loads(a.plan.read_text());assert plan['asset_root']==str(A)and plan['assets']==ASSETS and plan['maximum_seconds_including_cleanup']==600
 if not a.execute:print(json.dumps(dict(status='PLAN_ONLY_NO_NETWORK_OR_WRITES',assets=ASSETS,asset_root=str(A))));return 0
 assert a.admission and a.admission==W/'ASSET_ACQUISITION_ADMISSION.json';approved=json.loads(a.admission.read_text())
 assert approved['checks_passed']is True and approved['plan_sha256']==sha(a.plan)and approved['helper_sha256']==sha(Path(__file__))and approved['asset_root']==str(A)
 assert approved['additional_metadata_GETs_authorized']==0 and approved['paid_calls']==approved['GPU_calls']==0
 guard();os.sched_setaffinity(0,{0,1});assert not A.exists()and not any(x.is_symlink()for x in(A,*A.parents))
 required=sum(x['bytes']for x in ASSETS)+536870912;assert os.statvfs(W).f_bavail*os.statvfs(W).f_frsize>=required
 config=a.metadata_dir/'xxlarge-config.json';license=a.metadata_dir/'upstream-MIT-LICENSE.txt'
 assert config.stat().st_size==952 and sha(config)=='2c2de12b575824b4caec3ae5cc03c3f80837b1b3617541b8a5333cdc3db9b57c'
 assert license.stat().st_size==1141 and sha(license)=='c2cfccb812fe482101a8f04597dfc5a9991a6b2748266c47ac91b6a5aae15383'
 A.mkdir(parents=True);started=time.monotonic();put(A/'ACQUISITION_RESERVATION.json',dict(epoch=36,assets=ASSETS,admission_sha256=sha(a.admission),allowed_attempts_per_asset=1,wall_limit_seconds=600,started_unix=time.time(),model_tokenizer_native_calls=0))
 def expired(signum,frame):raise TimeoutError('Acquisition wall budget exhausted')
 signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,600)
 try:
  for row in ASSETS:
   guard();name=row['path'];url='https://huggingface.co/microsoft/deberta-v2-xxlarge-mnli/resolve/'+REV+'/'+name;tmp=A/(name+'.partial');dest=A/name;assert not tmp.exists()and not dest.exists()
   put(A/(name+'.intent.json'),dict(epoch=36,asset=row,url=url,GET_attempt=1,redirects_maximum=2,initial_content_bytes=0,time=time.time()))
   fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);h=hashlib.sha256();count=0;redirect=Redirect()
   try:
    with os.fdopen(fd,'wb')as out,urllib.request.build_opener(redirect).open(urllib.request.Request(url,headers={'User-Agent':'RuVector-reviewed-original-asset/36'}),timeout=30)as response:
     assert response.status==200 and safe_host(response.url)
     length=response.headers.get('Content-Length');assert length is None or int(length)==row['bytes']
     while True:
      chunk=response.read(1048576)
      if not chunk:break
      count+=len(chunk);assert count<=row['bytes'];h.update(chunk);out.write(chunk)
     out.flush();os.fsync(out.fileno());os.fchmod(out.fileno(),0o444)
    assert count==row['bytes']and h.hexdigest()==row['sha256'];guard();assert not dest.exists();before=tmp.stat();os.rename(tmp,dest);after=dest.stat();assert(before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
    d=os.open(A,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
    put(A/(name+'.response.json'),dict(epoch=36,bytes=count,sha256=h.hexdigest(),expected_identity_verified=True,atomic_rename_once=True,request_url=url,redirect_events=redirect.events,total_GETs=1+len(redirect.events),final_host=urllib.parse.urlsplit(response.url).hostname,final_query_or_headers_persisted=False,wall_seconds=time.monotonic()-started))
   except BaseException as error:
    # Never serialize signed redirect URLs, headers, exception messages or credentials.
    put(A/(name+'.failure.json'),dict(epoch=36,error_type=type(error).__name__,HTTP_status=getattr(error,'code',None),captured_bytes=count,partial_exists=tmp.exists(),final_exists=dest.exists(),repeat_or_resume_allowed=False,redirect_events=redirect.events,full_exception_or_signed_URL_omitted=True))
    print(json.dumps(dict(status='ACQUISITION_STOPPED_NO_RETRY',asset=name,error_type=type(error).__name__,captured_bytes=count)));return 2
  for source,name in[(config,'config.json'),(license,'LICENSE')]:
   with(A/name).open('xb')as out:out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
  tok=a.metadata_dir/'tokenizer_config.json'
  if tok.is_file():
   b=tok.read_bytes();assert len(b)==52 and hashlib.sha1(b'blob 52\0'+b).hexdigest()=='acfd94e399c5659e4bed75f91b4ee24b111fc7a6'
   with(A/'tokenizer_config.json').open('xb')as out:out.write(b);out.flush();os.fsync(out.fileno())
  put(A/'ACQUISITION_COMPLETED.json',dict(epoch=36,assets=ASSETS,verified_bytes=sum(x['bytes']for x in ASSETS),wall_seconds=time.monotonic()-started,model_native_tokenizer_calls=0,tokenizer_config_copied=tok.is_file(),metadata_GETs=0,paid_calls=0,GPU_calls=0,original_weights_republished=False));print(json.dumps(dict(status='ORIGINAL_PAYLOADS_ACQUIRED_HASH_VERIFIED_NO_ML',wall_seconds=time.monotonic()-started)));return 0
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':raise SystemExit(main())
