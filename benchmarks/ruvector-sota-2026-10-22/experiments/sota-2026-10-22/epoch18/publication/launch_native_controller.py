"""Execute the unchanged admitted controller once and record outer OS resources."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,resource,subprocess,time
scope=Path(__file__).resolve().parent;root=scope/'project';e=root/'experiments/sota-2026-10-22/epoch18'
assert not(e/'launch.json').exists()and not(e/'runs').exists()
assert hashlib.sha256((e/'plan.json').read_bytes()).hexdigest()=='f2eb56b436bc499f4a63d724dc6055a5e1e69e82892cb41d1db4e023af49e7eb'
admission=json.loads((scope/'native-admission.json').read_text())
assert admission['checks_passed']is True and admission['independent_remote_readback_passed']is True
assert admission['source_commit']and admission['owner_pid']==40632
os.kill(40632,0);os.sched_setaffinity(0,[0,1])
env=dict(os.environ)
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[key]='2'
env.update(TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
start=time.monotonic();at=datetime.now(timezone.utc).isoformat()
with(e/'controller-outer.log').open('x')as log:
    result=subprocess.run([str(root/'retrieval/.venv/bin/python'),'-B',str(root/'experiments/sota-2026-10-22/controller/epoch18/loop.py'),'--plan',str(e/'plan.json')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
out={'schema_version':1,'started_at':at,'finished_at':datetime.now(timezone.utc).isoformat(),'exit_code':result.returncode,
 'wall_seconds':time.monotonic()-start,'allowed_CPU_ids':sorted(os.sched_getaffinity(0)),
 'children_CPU_user_seconds':usage.ru_utime,'children_CPU_system_seconds':usage.ru_stime,
 'children_largest_peak_RSS_bytes':usage.ru_maxrss*1024,
 'resource_scope':'Linux outer waited child/descendant counters. RSS is largest process high-water mark, not simultaneous aggregate memory. Actual per-phase reservations/watchdogs/cleanup are recorded by the frozen controller.',
 'unchanged_controller':True,'additional_model_native_calls_from_outer_recorder':0,'paid_GPU_calls':0}
with(e/'controller-outer-resources.json').open('x')as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out),flush=True)
raise SystemExit(result.returncode)
