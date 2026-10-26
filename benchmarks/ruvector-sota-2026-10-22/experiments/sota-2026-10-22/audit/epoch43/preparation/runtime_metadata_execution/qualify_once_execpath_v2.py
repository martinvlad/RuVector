"""Root once-only, owner-fenced metadata qualification; no model initialization."""
import hashlib, json, os, signal, subprocess, time
from pathlib import Path

W = Path('/tmp/ruvector-sota-2026-10-22/epoch43-cab16abb5795')
D = W/'lease-generation5'
E = Path('/workspace/ruvector-e43-engineering/implementation-v1')
OWNER_SHA = '620f1417b818070b91d365e900e1abbcc4309fe040ba42e87a498ae28af36cd5'
REVIEW = Path('/workspace/ruvector-e43-acceptance-audit/RUNTIME_METADATA_QUALIFICATION_SOURCE_APPROVAL.v1.json')
REVIEW_SHA = 'eb087b6104021baa454c518dd21e7f088196eafebf2e6196222e72dd079d16e3'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_once(p, value):
    b=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(f,'wb') as out: out.write(b);out.flush();os.fsync(out.fileno())
    finally:
        d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)

start=time.monotonic();owner=json.loads((D/'owner.json').read_text())
assert sha(D/'owner.json')==OWNER_SHA and sha(REVIEW)==REVIEW_SHA
assert not (D/'release.request').exists() and time.time()+90<owner['expires_unix']
stat=Path('/proc')/str(owner['pid'])/'stat'
assert stat.read_text().rsplit(')',1)[1].split()[19]==str(owner['startticks'])
assert any('FLOCK' in line and int(line.split()[4])==owner['pid'] and
           line.split()[5].endswith(':'+str(owner['lock_inode']))
           for line in Path('/proc/locks').read_text().splitlines())
assert os.sched_getaffinity(0)=={0,1}
approval=json.loads((E/'RUNTIME_QUALIFICATION_APPROVAL.TEMPLATE.json').read_text())
approval.update(authorized=True,expires_unix=min(time.time()+80,owner['expires_unix']),
                current_owner_sha256=OWNER_SHA,independent_source_review_sha256=REVIEW_SHA)
ap=D/'RUNTIME_QUALIFICATION_APPROVAL.execpath-v2.root.json';write_once(ap,approval)
marker=D/'METADATA_QUALIFICATION_INVOCATION.execpath-v2.once.json'
write_once(marker,{'started_unix':time.time(),'owner_sha256':OWNER_SHA,
                  'approved_source_review_sha256':REVIEW_SHA,'retry_authorized':False})
out=W/'project/experiments/sota-2026-10-22/audit/epoch43/preparation/metadata_qualification_execpath_v2'
assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
assert not any(p.is_symlink() for p in (out,*out.parents))
argv=['/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python','-I','-B',str(E/'qualify_runtime.py'),'--approval',str(ap),
      '--approval-sha256',sha(ap),'--output',str(out)]
p=None;record={'schema_version':1,'epoch':43,'owner_sha256':OWNER_SHA,
               'model_tokenizer_native_case_gold_calls':0,'outer_total_seconds_limit':60,
               'invocation_once_marker_sha256':sha(marker),'argv':argv,'rc':None}
try:
    p=subprocess.Popen(argv,start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
    record['pid']=p.pid
    child_stat=(Path('/proc')/str(p.pid)/'stat').read_text().rsplit(')',1)[1].split()
    record['startticks']=int(child_stat[19]);record['pgid']=os.getpgid(p.pid);record['sid']=os.getsid(p.pid)
    assert record['pgid']==record['sid']==p.pid
    stdout,stderr=p.communicate(timeout=max(1,53-(time.monotonic()-start)))
    record.update(rc=p.returncode,stdout=stdout.decode('utf-8'),stderr=stderr.decode('utf-8'))
except BaseException as e:
    record['error_type']=type(e).__name__
finally:
    if p is not None:
        if p.poll() is None:
            now=(Path('/proc')/str(p.pid)/'stat').read_text().rsplit(')',1)[1].split()
            assert int(now[19])==record['startticks'] and os.getpgid(p.pid)==os.getsid(p.pid)==p.pid
            os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=4)
        record['owned_process_wait_returncode']=p.returncode
        record['owned_group_absent']=False
        try:os.killpg(p.pid,0)
        except ProcessLookupError:record['owned_group_absent']=True
    record['wall_seconds']=time.monotonic()-start
    record['within_outer_bound']=record['wall_seconds']<=60
    if (out/'RESULT.json').exists():
        record['result']={'path':str((out/'RESULT.json').relative_to(W/'project')),
                          'bytes':(out/'RESULT.json').stat().st_size,'sha256':sha(out/'RESULT.json')}
    write_once(D/'METADATA_QUALIFICATION_ROOT_EXECUTION.execpath-v2.json',record)
print(json.dumps(record,sort_keys=True))
raise SystemExit(0 if record['rc']==0 and record.get('owned_group_absent') and record['within_outer_bound'] else 1)
