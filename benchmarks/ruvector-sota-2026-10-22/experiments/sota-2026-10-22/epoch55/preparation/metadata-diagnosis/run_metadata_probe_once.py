from pathlib import Path
import json,os,hashlib,time,subprocess,sys
W=Path(__file__).resolve().parent;C=Path('/dev/shm/ruvector-e55-candidate');Q=Path('/dev/shm/ruvector-e55-audit')
def read(p,expected):
 b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==expected;return json.loads(b)
def put(p,x):
 with p.open('x')as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def owner():
 p=W/'owner.json';assert hashlib.sha256(p.read_bytes()).hexdigest()=='bf6380ac1d3776ba3f0f2e28a4aa3acc9eb9d79bb3c9358eebf701a6dbccbec7';o=json.loads(p.read_text());assert time.time()<o['expires_unix'];assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==o['kernel_boot_id'];s=Path('/proc/'+str(o['pid'])+'/stat').read_text().rsplit(')',1)[1].split();assert int(s[19])==o['startticks'];assert Path('/proc/'+str(o['pid'])+'/fd/3').stat().st_ino==o['lock_inode'];assert not(W/'release.request').exists()
assert sorted(os.sched_getaffinity(0))==[0,1];owner()
p=read(C/'METADATA_PROBE_SOURCE_PACKET.v3.json','a53ba078c1b37a281075ac1b36dc0ed43b112f64156db7fa1b02b15427722a11');a=read(Q/'METADATA_PROBE_SOURCE_INDEPENDENT_APPROVAL.v2.json','210fc46bc74f8a3a36a7044f8b364a16068591bd95ec97119b23c09431e92576')
for r in p['files']:
 b=Path(r['path']).read_bytes();assert len(b)==r['bytes']and hashlib.sha256(b).hexdigest()==r['sha256']
assert not Path(p['launch_argv'][-1]).exists()
put(W/'METADATA_PROBE_FROZEN_INTENT.actual.v1.json',{'epoch':55,'packet_sha256':'a53ba078c1b37a281075ac1b36dc0ed43b112f64156db7fa1b02b15427722a11','approval_sha256':'210fc46bc74f8a3a36a7044f8b364a16068591bd95ec97119b23c09431e92576','argv':p['launch_argv'],'timeout_seconds':15,'maximum_attempts':1,'native_batches_authorized':0,'remediation_selected':False,'time_unix':time.time()})
started=time.monotonic()
try:
 r=subprocess.run(p['launch_argv'],capture_output=True,text=True,timeout=15);result={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'timed_out':False}
except subprocess.TimeoutExpired as e:
 result={'exit_code':None,'stdout':str(e.stdout or ''),'stderr':str(e.stderr or ''),'timed_out':True}
result.update(epoch=55,wall_seconds=time.monotonic()-started,automatic_retry=False,scope='Metadata diagnosis only, not a native batch or benchmark measurement.');put(W/'METADATA_PROBE_ROOT_OUTER.actual.v1.json',result);owner();print(json.dumps(result));assert result['exit_code']==0 and not result['timed_out']
