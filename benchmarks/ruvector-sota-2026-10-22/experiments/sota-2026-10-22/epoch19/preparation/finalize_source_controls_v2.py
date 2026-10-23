"""Clarify source publication0/conditional1 without changing frozen science."""
from pathlib import Path
import argparse,hashlib,json,os,stat
PLAN_SHA='c65eaafcef514f7ec0aa7c3489d6c851974e1cd0a2bd1293a8d87c9d7b2e6d31'
FILES={'ACTIVE_RUN.json','CONTINUATION.json','CHECKPOINT_MANIFEST.json'}
def check(path,directory=False):
    assert ".." not in path.parts
    path=path.absolute()
    assert not any(x.is_symlink() for x in [path,*path.parents])
    assert path.is_dir() if directory else stat.S_ISREG(path.lstat().st_mode)
    return path
def read(path):return json.loads(check(path).read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return (json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def run(args):
    assert ".." not in args.out.parts
    folder=check(args.input,True);project=check(args.project,True);out=args.out.absolute()
    assert set(x.name for x in folder.iterdir())==FILES
    assert not os.path.lexists(out) and not out.is_relative_to(project)
    assert not any(x.is_symlink() for x in [out,*out.parents])
    plan_path=check(project/'experiments/sota-2026-10-22/epoch19/plan.json')
    assert sha(plan_path.read_bytes())==PLAN_SHA
    plan=read(plan_path);cap=plan['limits']['worker_attempts']
    assert type(cap) is int and cap==1 and plan['limits']['paid_calls']==plan['limits']['GPU_calls']==0
    active=read(folder/'ACTIVE_RUN.json');cont=read(folder/'CONTINUATION.json')
    assert active['state']=='EPOCH19_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION'
    assert active['experiments_active'] is True
    assert type(active['native_allowed']) is int and active['native_allowed']==0
    assert type(active['native_allowed_after_exact_remote_readback']) is int and active['native_allowed_after_exact_remote_readback']==0
    assert active['limits']['qualification_worker_attempt_cap']==cap
    assert cont['active_run']['run_id']==active['run_id'] and cont['active_run']['native_allowed']==0
    assert cont['epoch19_frozen_study']['plan']['sha256']==PLAN_SHA
    cp=check(folder/'CHECKPOINT_MANIFEST.json').read_bytes()
    assert sha(cp)==cont['checkpoint_manifest_sha256']
    conditions='Exactly one frozen qualification worker only after matching independent source publication readback, unchanged plan '+PLAN_SHA+', and fresh live exclusive scoped kernel-lock admission. Publication alone admits zero calls; no automatic retry or benchmark continuation.'
    active['native_allowed_after_exact_remote_readback']=cap
    active['conditional_native_admission_conditions']=conditions
    cont['active_run']['native_allowed_after_exact_remote_readback']=cap
    cont['epoch19_frozen_study']['conditional_native_allowance_after_exact_remote_readback']=cap
    cont['epoch19_frozen_study']['conditional_native_admission_conditions']=conditions
    cont['cumulative_budget_ledger']['conditional_qualification_allowance_after_exact_remote_readback']=cap
    out.mkdir(mode=0o700)
    outputs={'ACTIVE_RUN.json':raw(active),'CONTINUATION.json':raw(cont),'CHECKPOINT_MANIFEST.json':cp}
    for name,b in outputs.items():
        with (out/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return {'scope':'Source publication metadata only; original frozen files unchanged',
        'publication_native_allowed':0,'conditional_allowance':cap,'final_allowance_changed':False,
        'plan_sha256':PLAN_SHA,'outputs':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in outputs.items()},
        'model_native_Git_calls':0}
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('input','out','project'):ap.add_argument('--'+key,type=Path,required=True)
    print(json.dumps(run(ap.parse_args())))
