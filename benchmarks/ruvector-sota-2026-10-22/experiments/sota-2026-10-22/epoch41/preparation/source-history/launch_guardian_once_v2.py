from pathlib import Path
import sys,os,json,hashlib,time,subprocess
W=Path('/tmp/ruvector-sota-2026-10-22/epoch41-7a40daab6ad7')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(name,value):
 p=W/name
 with p.open('x')as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
assert len(sys.argv)==3
review_path=Path(sys.argv[1]);assert review_path.is_absolute()and digest(review_path)==sys.argv[2]
review=json.loads(review_path.read_text());plan=json.loads((W/'PREPARATION_SOURCE_PLAN.v2.json').read_text())
assert review['checks_passed']is True and review['scoped_guardian_execution_allowed']is True and review['restoration_execution_allowed']is True and review['preparation_source_plan_sha256']==digest(W/'PREPARATION_SOURCE_PLAN.v2.json')
assert plan['source_commit']=='7a40daab6ad7caf9310f678813bfef42f907bd17'and plan['native_model_label_payload_calls_allowed']==0
for row in plan['code_files']:
 p=Path(row['path']);assert p.is_file()and not p.is_symlink()and p.stat().st_size==row['bytes']and digest(p)==row['sha256']
assert not any((W/x).exists()for x in['owner.json','LOCK_DISPATCH_RESERVATION.json','LOCK_DISPATCH.json','release.request','released.json'])
argv=['taskset','-c','0,1','python3','-I','-B',str(W/'lock_supervisor.py')]
put('LOCK_DISPATCH_RESERVATION.json',{'schema_version':1,'epoch':41,'argv':argv,'once':True,'retries':0,'source_review':{'path':str(review_path),'sha256':sys.argv[2]},'source_plan_sha256':digest(W/'PREPARATION_SOURCE_PLAN.v2.json'),'reserved_at_unix':time.time()})
child=None
try:
 with (W/'guardian.stdout').open('xb')as out,(W/'guardian.stderr').open('xb')as err:
  child=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True,close_fds=True)
  out.flush();os.fsync(out.fileno());err.flush();os.fsync(err.fileno())
 fields=Path('/proc/'+str(child.pid)+'/stat').read_text().rsplit(')',1)[1].split();ticks=int(fields[19])
 put('LOCK_DISPATCH.json',{'schema_version':1,'epoch':41,'pid':child.pid,'startticks':ticks,'pgid':int(fields[2]),'sid':int(fields[3]),'allowed_retries':0,'Popen_returned':True})
 until=time.monotonic()+5;owner=None
 while time.monotonic()<until:
  if(W/'owner.json').is_file():
   try:
    candidate=json.loads((W/'owner.json').read_text());lines=(W/'guardian.stdout').read_text().splitlines();emitted=json.loads(lines[0])if lines else None
   except json.JSONDecodeError:pass
   else:
    if emitted is not None:
     assert candidate==emitted;owner=candidate;break
  if child.poll()is not None:break
  time.sleep(.05)
 if owner is None:raise RuntimeError('GUARDIAN_OWNER_NOT_CAPTURED_STOP_NO_RETRY')
 assert owner['pid']==child.pid and owner['startticks']==ticks and owner['CPU_affinity']==[0,1]and owner['expires_unix']-owner['started_unix']==10800
 assert child.poll()is None
 put('LOCK_LAUNCH_RESULT.json',{'status':'OWNED_GUARDIAN_ACQUIRED','owner_json_sha256':digest(W/'owner.json'),'pid':child.pid,'startticks':ticks,'actual_native_model_label_payload_calls':0,'allowed_retries':0,'capture_at_unix':time.time()})
 print(json.dumps(owner))
except BaseException as error:
 put('LOCK_LAUNCH_FAILURE_FINAL_NO_RETRY.json',{'status':'STOP_NO_RETRY','error_type':type(error).__name__,'Popen_returned':child is not None,'pid':None if child is None else child.pid,'at_unix':time.time(),'rule':'Do not launch another guardian or repeat uncertain external operation; independently reconcile exact process/owner.'})
 raise
