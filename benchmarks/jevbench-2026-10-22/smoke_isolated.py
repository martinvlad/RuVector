"""Clean npm install plus one unseen HTTP protocol smoke; no benchmark scoring.

Existing pinned model bytes are reused from --assets-from (default: this kit after
acquire_models.py). npm gets a fresh isolated cache; no workspace node_modules
is copied or reused. The temporary project is removed after preserving receipts.
"""
import argparse,datetime,hashlib,json,math,os
from pathlib import Path
import selectors,shutil,signal,socket,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--assets-from',type=Path,default=ROOT);parser.add_argument('--work-parent',type=Path,default=ROOT);parser.add_argument('--out-directory',type=Path,default=ROOT/'validation');args=parser.parse_args()
 out=args.out_directory.resolve();out.mkdir(parents=True,exist_ok=True)
 started=time.monotonic();manifest=json.loads((ROOT/'PUBLIC_MANIFEST.json').read_text());runtime=json.loads((ROOT/'experiments/submission-2026-10-22/jevbench/runtime-manifest.json').read_text());server=None;native_pids=[];status='failed';error=None;receipt={}
 try:
  with tempfile.TemporaryDirectory(prefix='.isolated-native-',dir=args.work_parent.resolve()) as temp:
   target=Path(temp)/'project';target.mkdir()
   for row in manifest['files']:
    source=ROOT/row['path'];assert sha(source)==row['sha256'];p=target/row['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)
   shutil.copyfile(ROOT/'PUBLIC_MANIFEST.json',target/'PUBLIC_MANIFEST.json')
   assets=[]
   for row in runtime['model_assets']:
    source=args.assets_from.resolve()/row['path'];assert sha(source)==row['sha256'];p=target/row['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p);assert sha(p)==row['sha256'];assets.append({'path':row['path'],'sha256':row['sha256'],'method':'byte-copy from existing pinned local model asset'})
   assert not (target/'node_modules').exists()
   cmd=['npm','ci','--ignore-scripts','--no-audit','--no-fund','--cache',str(Path(temp)/'fresh-npm-cache')]
   npm_started=time.monotonic()
   with (out/'npm-ci.log').open('w') as log:npm=subprocess.run(cmd,cwd=target,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   receipt.update(clean_npm_ci_returncode=npm.returncode,clean_npm_ci_seconds=time.monotonic()-npm_started,dependency_method='npm ci --ignore-scripts --no-audit --no-fund; fresh isolated npm cache; no copied workspace node_modules',model_asset_method=assets)
   if npm.returncode:raise RuntimeError('Clean npm ci failed; no fallback attempted')
   cpus=sorted(os.sched_getaffinity(0))[:2]
   environment={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','RAYON_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
   entry=target/'experiments/submission-2026-10-22/jevbench/serve.py'
   command=[sys.executable,'-B',str(entry),'--policy-directory',str(target/'experiments/submission-2026-10-22/jevbench/round2-v2'),'--runtime-manifest',str(target/'experiments/submission-2026-10-22/jevbench/runtime-manifest.json'),'--host','127.0.0.1','--port','0']
   with (out/'server.log').open('w') as log:
    server=subprocess.Popen(command,cwd=target,stdout=subprocess.PIPE,stderr=log,text=True,env=environment,start_new_session=True);os.sched_setaffinity(server.pid,cpus)
    try:
     selector=selectors.DefaultSelector();selector.register(server.stdout,selectors.EVENT_READ)
     if not selector.select(45):raise TimeoutError('Native startup timed out')
     line=server.stdout.readline();ready=json.loads(line);assert ready['status']=='ready' and ready['model']==runtime['candidate_id'];assert ready['receipt']['backend']=='native' and ready['receipt']['binary_sha256']==runtime['native_binary_sha256']
     native_pids=[]
     for proc in Path('/proc').glob('[0-9]*'):
      try:
       fields=dict(line.split(':',1) for line in (proc/'status').read_text().splitlines() if ':' in line)
       if int(fields.get('PPid','-1'))==server.pid:native_pids.append(int(proc.name))
      except (FileNotFoundError,PermissionError,ProcessLookupError):continue
     assert len(native_pids)==1 and Path('/proc',str(native_pids[0]),'cwd').resolve()==target
     maps=Path('/proc',str(native_pids[0]),'maps').read_text().splitlines();loaded=sorted({line.split()[-1] for line in maps if 'typesafe.linux-x64-gnu.node' in line});assert loaded and all(str(target/'node_modules') in p for p in loaded)
     onnx=[line.split()[-1] for line in maps if 'onnxruntime' in line and line.split()[-1].startswith('/')];assert all(not p.startswith(str(args.assets_from.resolve())) or p.startswith(str(target)) for p in onnx)
     receipt['loaded_onnxruntime_shared_libraries']=[p.replace(str(target)+'/','') for p in sorted(set(onnx))]
     receipt['native_loaded_paths']=[p.replace(str(target)+'/','') for p in loaded]
     assert all(len(os.sched_getaffinity(pid))==2 for pid in [server.pid,*native_pids])
     port=int(ready['endpoint'].split(':')[2].split('/')[0])
     body={'state':'An amber inspection tag is attached to a copper gate. The gate is open. The tag has code VELO-73.','model':runtime['candidate_id'],'questions':{'decision':{'type':'choice','instructions':'Which supplied description matches the current gate state?','criteria':{'current_open':'The copper gate is open.','current_closed':'The copper gate is closed.'}}}}
     raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();request=b'POST /v1/systemone HTTP/1.1\r\nHost: 127.0.0.1:'+str(port).encode()+b'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw)).encode()+b'\r\nConnection: close\r\n\r\n'+raw
     with socket.create_connection(('127.0.0.1',port),timeout=30) as connection:
      connection.sendall(request);parts=[]
      while part:=connection.recv(65536):parts.append(part)
     response=b''.join(parts);header,payload=response.split(b'\r\n\r\n',1);assert header.startswith(b'HTTP/1.0 200');answer=json.loads(payload);decision=answer['answers']['decision'];probabilities=decision['probabilities']
     assert set(probabilities)=={'current_open','current_closed'} and all(type(p) in [int,float] and math.isfinite(p) and 0<=p<=1 for p in probabilities.values()) and abs(sum(probabilities.values())-1)<1e-6
     assert decision['native_fallback_used'] is True and decision['baseline100_answer']==decision['native_original_answer'] and answer['usage']['native_requests']==1
     (out/'unseen.request.http').write_bytes(request);(out/'unseen.response.http').write_bytes(response)
     receipt.update(ready_receipt=ready,unseen_HTTP_requests=1,HTTP_status=200,strict_distribution_valid=True,actual_native_request_usage=answer['usage'],native_loaded_only_from_clean_install=True,source_relocation_verified=True,CPU_affinity=cpus,request_sha256=hashlib.sha256(request).hexdigest(),response_sha256=hashlib.sha256(response).hexdigest(),synthetic_request_not_benchmark_data=True,synthetic_accuracy_not_scored=True)
    finally:
     if server.poll() is None:
      server.send_signal(signal.SIGTERM)
      try:server.wait(timeout=8)
      except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait(timeout=3)
     receipt['server_returncode']=server.returncode;receipt['owned_server_PID']=server.pid;receipt['owned_native_PIDs']=native_pids
     receipt['all_owned_processes_absent']=all(not Path('/proc',str(pid)).exists() for pid in [server.pid,*native_pids]);assert receipt['all_owned_processes_absent']
   status='passed'
 except Exception as exc:error=type(exc).__name__+': '+str(exc)
 receipt.update(schema_version=1,status=status,error=error,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,public_manifest_sha256_at_test=sha(ROOT/'PUBLIC_MANIFEST.json'),temporary_project_removed=True,existing_scientific_outputs_changed=False,new_model_downloads=0,hosted_inference_API_or_paid_calls=0,benchmark_quality_measurements=0,official_rank=None)
 save(out/'isolated-native-smoke.json',receipt);print(json.dumps({'status':status,'error':error,'clean_npm_ci_returncode':receipt.get('clean_npm_ci_returncode'),'unseen_HTTP_requests':receipt.get('unseen_HTTP_requests'),'all_owned_processes_absent':receipt.get('all_owned_processes_absent'),'elapsed_seconds':receipt['elapsed_seconds']}))
 if status!='passed':raise SystemExit(1)

if __name__=='__main__':main()
