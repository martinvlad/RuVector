"""One price-zero opaque archive stream. No ZIP, case, label or ML decoding."""
from pathlib import Path
import hashlib,json,os,signal,stat,time,traceback,urllib.request,shutil
W=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
PLAN_SHA='553b0eec1cdecdfe227aa1cddfbf696fccc767cceb55616333b69d28de9bb6ed'
OWNER_SHA='f18924b1456dcf51c461181c233ff4511cd3e479982f48b109a0e4126b5c3af0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(Path(p).parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def owner():
 assert sha(W/'owner.json')==OWNER_SHA
 o=json.loads((W/'owner.json').read_text());a=Path('/proc/120232/stat').read_text().rsplit(')',1)[1].split();fd=Path('/proc/120232/fd/3');s=fd.stat()
 assert int(a[19])==27979422 and a[0]not in('Z','X')and time.time()<o['expires_unix']and not(W/'release.request').exists()
 assert (s.st_dev,s.st_ino)==(33,13626)and os.readlink(fd)=='/tmp/ruvector-sota-2026-10-22/exclusive.work.lock'
 assert os.sched_getaffinity(0)=={0,1}and os.sched_getaffinity(120232)=={0,1}
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4632fb06-b0ef-4df5-b72b-0e875bbad810'and Path('/proc/self/ns/pid').stat().st_ino==4026532200
 assert any(x.split()[1:5]==['FLOCK','ADVISORY','WRITE','120232']and tuple([int(v,16) for v in x.split()[5].split(':')[:2]]+[int(x.split()[5].split(':')[2])])==(os.major(s.st_dev),os.minor(s.st_dev),13626)for x in Path('/proc/locks').read_text().splitlines())
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def main():
 started=time.monotonic();owner();q=W/'ARCHIVE_OPAQUE_PLAN.v1.json';assert sha(q)==PLAN_SHA;p=json.loads(q.read_text())
 assert p['attempts']==1 and p['allowed_retries']==0 and p['paid_API_calls']==p['GPU_calls']==p['zip_json_case_gold_model_tokenizer_native_scorer_decodes_or_calls']==0
 assert p['url']=='https://raw.githubusercontent.com/stanfordnlp/contract-nli/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/resources/contract-nli.zip'
 assert p['expected_bytes']==65362913 and p['expected_git_blob_sha1']=='757fd1dafd29a997fba00c60c6d40b2930a36159'
 target=Path(p['target']);assert target.is_absolute()and target.is_relative_to(W/'data-source')and not any(z.is_symlink()for z in(target,*target.parents))
 partial=Path(str(target)+'.part');assert not target.exists()and not partial.exists();assert shutil.disk_usage(W).free>=p['expected_bytes']+p['minimum_remaining_free_bytes']
 target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 put(W/'ARCHIVE_OPAQUE_E40_ATTEMPT.json',{'epoch':40,'plan_sha256':PLAN_SHA,'attempts_reserved':1,'allowed_retries':0,'before_network':True,'at_unix':time.time()})
 result={'schema_version':1,'epoch':40,'kind':p['kind'],'status':'FAILED_STOP_NO_RETRY','plan_sha256':PLAN_SHA,'HTTP_requests_attempted':0,'HTTP_requests_completed':0,'bytes_streamed':0,'zip_json_case_gold_model_tokenizer_native_scorer_decodes_or_calls':0,'paid_API_GPU_calls':0,'errors':[]}
 h=None;g=hashlib.sha1(b'blob '+str(p['expected_bytes']).encode()+b'\0')
 def alarm(sig,frame):raise TimeoutError('OPAQUE_CHILD_DEADLINE')
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,170)
 try:
  result['HTTP_requests_attempted']=1
  with urllib.request.build_opener(NoRedirect()).open(p['url'],timeout=45)as response,partial.open('xb')as out:
   assert response.status==200;result['HTTP_response_status']=response.status
   while True:
    owner();block=response.read(min(1048576,p['expected_bytes']+1-result['bytes_streamed']))
    if not block:break
    result['bytes_streamed']+=len(block);assert result['bytes_streamed']<=p['expected_bytes'];g.update(block);out.write(block)
   out.flush();os.fsync(out.fileno())
  assert result['bytes_streamed']==p['expected_bytes']and g.hexdigest()==p['expected_git_blob_sha1']
  # SHA256 is computed only after the first typed Git identity pass.
  h=hashlib.sha256();second_git=hashlib.sha1(b'blob '+str(p['expected_bytes']).encode()+b'\0');second_bytes=0
  with partial.open('rb')as inp:
   before=os.fstat(inp.fileno())
   for block in iter(lambda:inp.read(1048576),b''):
    owner();second_bytes+=len(block);h.update(block);second_git.update(block)
   after=os.fstat(inp.fileno())
  assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
  assert second_bytes==p['expected_bytes']and second_git.hexdigest()==p['expected_git_blob_sha1']
  result['opaque_hash_passes']=2;result['automatic_redirects_allowed']=False
  owner();os.rename(partial,target);target.chmod(0o444);d=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
  result.update(status='OPAQUE_SOURCE_ARCHIVE_GIT_SIZE_VERIFIED_NO_DECODE',HTTP_requests_completed=1,payload_sha256=h.hexdigest(),actual_git_blob_sha1=g.hexdigest(),target=str(target),source_url=p['url'],source_revision='eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',target_readonly=True)
 except BaseException as error:
  result['errors'].append({'type':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()})
  (W/'archive-opaque-exact-error.private.txt').write_text(traceback.format_exc())
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);result['inner_pre_final_capture_wall_seconds']=time.monotonic()-started
  result['source_sha256']=sha(__file__);put(W/'ARCHIVE_OPAQUE_E40_RESULT.json',result)
 print(json.dumps({'status':result['status'],'bytes_streamed':result['bytes_streamed'],'semantic_decoders':0}))
 if result['status']!='OPAQUE_SOURCE_ARCHIVE_GIT_SIZE_VERIFIED_NO_DECODE':raise SystemExit(2)
if __name__=='__main__':main()
