"""Reserve exactly one offline, owned native engineering worker; never retry."""
from pathlib import Path
import argparse,json,hashlib,os,sys,subprocess,time,signal,resource,fcntl,stat,re

def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def put(p,obj):
 assert p.resolve()==p and not p.is_symlink();p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def proc(pid):
 try:
  a=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'state':a[0],'ppid':int(a[1]),'pgid':int(a[2]),'sid':int(a[3]),'ticks':int(a[19])}
 except (FileNotFoundError,ProcessLookupError):return None

def group(pgid):
 result=[]
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   row=proc(int(p.name))
   if row and row['pgid']==pgid and row['state'] not in ('Z','X'):result.append(row)
 return result

def guard(scope):
 o=json.loads((scope/'owner.json').read_text());assert o['pid']==66088 and o['startticks']==12864421 and time.time()<o['expires_unix'] and not(scope/'release.request').exists();row=proc(o['pid']);assert row and row['ticks']==o['startticks'] and row['state'] not in ('Z','X');lock=Path(o['lock']);assert lock.resolve()==lock
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);assert stat.S_ISREG(st.st_mode) and st.st_ino==13626;target=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);found=False
  for line in Path('/proc/locks').read_text().splitlines():
   a=line.split()
   if len(a)>=8 and a[1:5]==['FLOCK','ADVISORY','WRITE','66088']:
    x,y,z=a[5].split(':');found|=(int(x,16),int(y,16),int(z))==target
  assert found
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise AssertionError('Scoped contender unexpectedly acquired; STOP')
 finally:os.close(fd)
 return o

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--expected-plan-sha',required=True);ap.add_argument('--admission',type=Path,required=True);ap.add_argument('--scope',type=Path,required=True);a=ap.parse_args();start=time.monotonic();startwall=time.time();os.sched_setaffinity(0,{0,1});owner=guard(a.scope)
 assert digest(a.plan)==a.expected_plan_sha;plan=json.loads(a.plan.read_text());project=Path(plan['actual_project']);study=project/'experiments/sota-2026-10-22/epoch23';assert project==a.scope/'project' and a.plan==study/'plan.json' and a.admission==study/'NATIVE_ADMISSION.json';admission=json.loads(a.admission.read_text());assert admission['verified_actual_remote_readback'] is True and admission['epoch']==23 and admission['phase']=='engineering' and admission['plan_sha256']==a.expected_plan_sha and admission['source_freeze_sha256']==plan['source_freeze_sha256'];assert plan['benchmark_roles']==dict.fromkeys(['train','dev','calibration','confirmation'],[])
 for r in plan['pins']:
  p=project/r['path'];assert p.resolve()==p and p.is_file() and p.stat().st_size==r['bytes'] and digest(p)==r['sha256']
 bypath={r['path']:r for r in plan['pins']};assert len(bypath)==len(plan['pins'])
 exactworker='experiments/sota-2026-10-22/candidate/epoch23/worker.py';assert plan['worker_path']==exactworker and exactworker in bypath
 assert plan['inference_python']==str(project/'retrieval/.venv/bin/python') and Path(plan['inference_python']).is_file()
 assert admission['scope']=='benchmarks/ruvector-sota-2026-10-22/' and admission['owner_pid']==66088 and admission['owner_startticks']==12864421
 assert re.fullmatch('[0-9a-f]{40}',admission['published_source_commit'])
 assert bypath[plan['source_freeze_path']]['sha256']==plan['source_freeze_sha256'] and digest(project/plan['source_freeze_path'])==plan['source_freeze_sha256']
 assert plan['limits']['worker_attempts']==1 and plan['limits']['native_corpus_batches']<=2 and plan['limits']['seconds_per_batch']==600 and plan['limits']['cpu_threads']==2 and plan['limits']['paid_calls']==0 and plan['limits']['GPU_calls']==0
 out=study/'runs/engineering';assert not out.exists();out.mkdir(parents=True)
 reservation={'epoch':23,'phase':'engineering','reserved_workers':1,'allowed_further_workers':0,'permanently_closed_unspent_slot':True,'before_Popen':True,'plan_sha256':a.expected_plan_sha,'at_unix':time.time()};put(study/'ATTEMPT_RESERVATION.json',reservation)
 env=dict(os.environ)
 env.update({x:'2' for x in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS','TOKIO_WORKER_THREADS','UV_THREADPOOL_SIZE']});env.update({'TOKENIZERS_PARALLELISM':'false','PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
 deadline=startwall+585;cmd=[plan['inference_python'],'-I','-B',str(project/plan['worker_path']),'--plan',str(a.plan),'--expected-plan-sha',a.expected_plan_sha,'--admission',str(a.admission),'--out',str(out),'--deadline',str(deadline)];put(out/'launch-intent.json',{'argv':cmd,'start_new_session':True,'outer_total_seconds_cap':600,'CPU_affinity':[0,1],'secret_values_recorded':False})
 worker=None;signals=[];error=None;cleanup_errors=[];stdout=b'';stderr=b'';identity=None;uncertain_start=False;communicated=False;returned_pid=None
 def signal_owned(sig):
  members=group(worker.pid)
  if not members:return
  if identity is None or identity['pgid']!=worker.pid or identity['sid']!=worker.pid:raise RuntimeError('Cannot prove exact original process session; refuse signals')
  leader=proc(worker.pid)
  if leader is not None and leader['state'] not in ('Z','X'):
   assert leader['ticks']==identity['ticks'] and leader['pgid']==worker.pid and leader['sid']==worker.pid
  assert all(r['pgid']==worker.pid and r['sid']==worker.pid for r in members)
  for row in members:
   current=proc(row['pid'])
   if current is not None:assert current['ticks']==row['ticks'] and current['pgid']==worker.pid and current['sid']==worker.pid
  try:os.killpg(worker.pid,sig);signals.append(signal.Signals(sig).name)
  except ProcessLookupError:pass
 try:
  guard(a.scope);worker=subprocess.Popen(cmd,cwd=project,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);returned_pid=worker.pid;identity=proc(worker.pid);uncertain_start=identity is None or identity['pgid']!=worker.pid or identity['sid']!=worker.pid
  put(out/'attempt.json',{'pid':worker.pid,'pgid':identity['pgid'] if identity else None,'sid':identity['sid'] if identity else None,'startticks':identity['ticks'] if identity else None,'verified_process_start':not uncertain_start,'uncertain_start':uncertain_start,'Popen_returned_pid':worker.pid,'at_unix':time.time()})
  if uncertain_start:raise RuntimeError('Popen returned but exact process/session identity not sealed; no retry')
  stdout,stderr=worker.communicate(timeout=max(.001,deadline-time.time()));communicated=True
 except BaseException as e:
  error={'type':type(e).__name__,'message':str(e)}
  if isinstance(e,subprocess.TimeoutExpired):stdout=e.output or b'';stderr=e.stderr or b''
 finally:
  if worker is not None:
   try:
    if group(worker.pid):
     signal_owned(signal.SIGTERM);until=time.monotonic()+3
     while group(worker.pid) and time.monotonic()<until:time.sleep(.05)
    if group(worker.pid):signal_owned(signal.SIGKILL)
    if worker.poll() is None:worker.wait(timeout=3)
   except BaseException as e:cleanup_errors.append({'stage':'owned_group_cleanup','type':type(e).__name__,'message':str(e)})
   if not communicated:
    try:stdout,stderr=worker.communicate(timeout=1);communicated=True
    except BaseException as e:cleanup_errors.append({'stage':'final_output_capture','type':type(e).__name__,'message':str(e)})
  (out/'worker.stdout').write_bytes(stdout);(out/'worker.stderr').write_bytes(stderr)
  living=group(worker.pid) if worker is not None else [];r=resource.getrusage(resource.RUSAGE_CHILDREN);rawpath=out/'raw.json';report={'epoch':23,'phase':'engineering','status':'WORKER_COMPLETED' if worker and worker.returncode==0 and error is None and not cleanup_errors and not uncertain_start and not living else 'WORKER_FAILED_OR_TIMEOUT','worker_attempts_reserved':1,'verified_worker_starts':1 if identity and not uncertain_start else 0,'Popen_returned_pid':returned_pid,'uncertain_start':uncertain_start,'worker_identity':identity,'exit_code':worker.returncode if worker else None,'launcher_error':error,'cleanup_signals':signals,'cleanup_errors':cleanup_errors,'stdout_stderr_capture_completed':communicated,'owned_live_group_members':living,'owned_live_processes_closed':not living,'wall_seconds_including_init_cleanup':time.monotonic()-start,'CPU_affinity':sorted(os.sched_getaffinity(0)),'largest_child_peak_RSS_bytes':r.ru_maxrss*1024,'children_user_seconds':r.ru_utime,'children_system_seconds':r.ru_stime,'memory_scope':'RUSAGE_CHILDREN largest-child high-water, not simultaneous aggregate RSS','raw_bytes':rawpath.stat().st_size if rawpath.exists() else None,'raw_sha256':digest(rawpath) if rawpath.exists() else None,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest(),'allowed_further_epoch23_workers':0,'confirmation_calls':0,'paid_calls':0,'GPU_calls':0};put(study/'execution.json',report);print(json.dumps(report))
 if report['wall_seconds_including_init_cleanup']>600:raise RuntimeError('Whole process bound exceeded; no retry')
 return 0 if report['status']=='WORKER_COMPLETED' else 2

if __name__=='__main__':raise SystemExit(main())
