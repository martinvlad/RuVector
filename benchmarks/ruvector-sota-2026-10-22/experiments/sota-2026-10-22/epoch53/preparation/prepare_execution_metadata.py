"""Root-only DEV metadata writer. No DATA, model, native, Gold or Git invocation."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, re, stat
W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34');R=W/'project'
P=R/'experiments/sota-2026-10-22/epoch53';A=R/'experiments/sota-2026-10-22/audit/epoch53'
RT=R/'experiments/sota-2026-10-22/runtime/epoch53';BASE='655e7aa57e34b0d5b0702e3a5957640a932b9d23'
PLAN_SHA=None
SF_SHA=None
def configure(plan_sha,source_freeze_sha):
    global PLAN_SHA,SF_SHA
    assert PLAN_SHA is None and SF_SHA is None,'one exact frozen binding per imported module'
    assert type(plan_sha) is str and re.fullmatch('[0-9a-f]{64}',plan_sha)
    assert type(source_freeze_sha) is str and re.fullmatch('[0-9a-f]{64}',source_freeze_sha)
    PLAN_SHA=plan_sha;SF_SHA=source_freeze_sha
def ref(p):
    p=Path(p);assert p.is_file() and not p.is_symlink();h=hashlib.sha256();before=p.stat()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    after=p.stat();assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest())
def load(p):return json.loads(Path(p).read_bytes())
def put(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return ref(p)
def fence():
    assert PLAN_SHA is not None and SF_SHA is not None,'explicit frozen plan/source binding required'
    spec=importlib.util.spec_from_file_location('admission_owner',W/'publication-helpers/guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.owner_fence()
    assert ref(P/'plan.json')['sha256']==PLAN_SHA and ref(P/'SOURCE_FREEZE.json')['sha256']==SF_SHA
    plan=load(P/'plan.json');assert plan['epoch']==53 and plan['source_checkpoint']==BASE and plan['confirmation_lineage_status']=='UNQUALIFIED_HOLD'
    assert plan['phase_limits']['dev']['forecasts']==48 and plan['phase_limits']['dev']['maximum_model_forward_calls']==324
    assert len(plan['data_roles']['dev'])==12 and plan['data_roles']['train']==plan['data_roles']['calibration']==[]
    return plan
def common(mode,plan):return dict(schema_version=1,epoch=53,kind=plan['kind'],mode=mode,phase='dev',owner_ref=ref(W/'owner.json'),plan_ref=ref(P/'plan.json'),source_freeze_ref=ref(P/'SOURCE_FREEZE.json'))
def source_data(proof):
    plan=fence();receipt=load(W/'publication/publication-source-result.json');q=load(proof)
    assert receipt['epoch']==q['epoch']==53 and receipt['phase']=='source' and receipt['parent']==BASE
    assert receipt['kind']==plan['kind'] and receipt['commit']!=BASE and q['commit']==receipt['commit']
    assert q['checks_passed'] and q['verified_actual_remote_readback'] and q['tree_sha']==receipt['root']
    assert q['source_plan_sha256']==PLAN_SHA and q['source_freeze_sha256']==SF_SHA
    assert receipt['verified_actual_full_tree'] and receipt['source_plan_sha256']==PLAN_SHA and receipt['source_freeze_sha256']==SF_SHA
    source=dict(schema_version=1,epoch=53,kind=plan['kind'],owner_ref=ref(W/'owner.json'),parent=BASE,
        plan_ref=ref(P/'plan.json'),source_freeze_ref=ref(P/'SOURCE_FREEZE.json'),source_commit=receipt['commit'],
        source_full_tree_verified=True,source_publication_independently_verified=True,scientific_dispatch_authorized=False,
        actual_SOURCE_receipt=ref(W/'publication/publication-source-result.json'),independent_SOURCE_readback=ref(proof))
    sr=put(P/'SOURCE_ADMISSION.json',source);d=common('DATA',plan)
    d.update(data_policy_ref=ref(R/plan['data_policy']['path']),source_admission_ref=sr,allowed_cases=plan['data_roles']['dev'],private_output=str(W/'private'),confirmation_materialization_authorized=False)
    return dict(SOURCE=sr,DATA=put(A/'ROOT_DATA_ADMISSION.json',d),actual_DATA_or_SCI_invocations=0)
def sci():
    plan=fence();source=load(P/'SOURCE_ADMISSION.json');assert source['scientific_dispatch_authorized'] is False and source['source_publication_independently_verified']
    data=load(A/'DATA_ADMISSION.json');assert data['status']=='READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT' and not data['errors']
    features=data['features'];assert features==data['private_features'] and set(features)=={'path','bytes','sha256'}
    fp=Path(features['path']);assert fp==W/'private/DEV_FEATURES.json' and not fp.is_symlink()
    fs=fp.lstat();assert stat.S_ISREG(fs.st_mode) and type(features['bytes']) is int and fs.st_size==features['bytes']
    assert re.fullmatch('[0-9a-f]{64}',features['sha256']) and stat.S_IMODE(fs.st_mode)==0o600
    sf=load(P/'SOURCE_FREEZE.json');sourcefiles=[]
    for row in sf['files']:
        absolute=ref(R/row['path']);assert absolute['bytes']==row['bytes'] and absolute['sha256']==row['sha256'];sourcefiles.append(absolute)
    owner=ref(W/'owner.json');dr=ref(A/'DATA_ADMISSION.json')
    ad=dict(schema_version=1,epoch=53,kind=plan['kind'],phase='dev',allowed=True,plan_sha256=PLAN_SHA,plan_ref=ref(P/'plan.json'),source_commit=source['source_commit'],
        source_freeze_sha256=SF_SHA,source_freeze_ref=ref(P/'SOURCE_FREEZE.json'),source_files=sourcefiles,source_admission_ref=ref(P/'SOURCE_ADMISSION.json'),
        owner=owner,owner_ref=owner,data_admission=dr,data_admission_ref=dr,features=features,features_ref=features,worker_slot_token=plan['phase_slots']['dev']['token'],native_batch_ordinal=1)
    ar=put(A/'ROOT_SCI_ADMISSION.json',ad)
    argv=[plan['python_executable'],'-I','-B',str(RT/'phase_runner.py'),'--plan',str(P/'plan.json'),'--expected-plan-sha256',PLAN_SHA,
        '--admission',ar['path'],'--expected-admission-sha256',ar['sha256'],'--phase','dev','--out-dir',str(W/'runs/dev')]
    intent=dict(schema_version=1,epoch=53,kind=plan['kind'],phase='dev',argv=argv,SCI_admission_ref=ar,plan_ref=ref(P/'plan.json'),
        nonsecret_environment_overrides=plan['launch_environment'],supervisor_stdout_path=str(W/'DEV_SUPERVISOR.stdout'),supervisor_stderr_path=str(W/'DEV_SUPERVISOR.stderr'),automatic_retry=False)
    return dict(SCI=ar,intent=put(W/'DEV_LAUNCH_INTENT.v1.json',intent),actual_scientific_Popen_attempts=0)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['SOURCE_DATA','SCI']);parser.add_argument('--independent-source');parser.add_argument('--plan-sha',required=True);parser.add_argument('--source-freeze-sha',required=True);args=parser.parse_args();configure(args.plan_sha,args.source_freeze_sha)
    if args.mode=='SOURCE_DATA':assert args.independent_source;out=source_data(Path(args.independent_source))
    else:out=sci()
    print(json.dumps(out,sort_keys=True))
