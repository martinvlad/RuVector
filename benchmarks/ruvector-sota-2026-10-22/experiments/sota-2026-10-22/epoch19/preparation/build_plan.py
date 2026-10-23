"""Freeze the reconstructed public source and one qualification-only CPU plan."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os,stat,time
from datetime import datetime,timezone

P='experiments/sota-2026-10-22/'
SOURCE='6eb624feef9ea93c3b1a8f76c20e8442c6bece50'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def identity(root,name):
    assert isinstance(name,str) and name and '\\' not in name
    assert not PurePosixPath(name).is_absolute() and not any(x in ('','.','..') for x in name.split('/'))
    path=root/name
    assert path.resolve().is_relative_to(root)
    assert not any(x.is_symlink() for x in [path,*path.parents])
    assert stat.S_ISREG(path.lstat().st_mode)
    return {'path':name,'bytes':path.stat().st_size,'sha256':digest(path)}

def write(path,value):
    with path.open('x') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n');f.flush();os.fsync(f.fileno())

def build(args):
    root=args.project.resolve();kit=args.kit.resolve();scope=args.scope.resolve()
    owner=json.loads((scope/'owner.json').read_text())
    assert time.time()+650<owner['expires_unix']
    os.kill(owner['pid'],0)
    assert Path('/proc/'+str(owner['pid'])+'/stat').read_text().split()[2]!='Z'
    freeze_name=P+'epoch19/candidate-source-freeze.json'
    plan_name=P+'epoch19/plan.json'
    for name in (freeze_name,plan_name): assert not os.path.lexists(root/name)
    historical={}
    for manifest,key in [('CHECKPOINT_MANIFEST.json','project_files'),('KIT_MANIFEST.json','project_files')]:
        for row in json.loads((kit/manifest).read_text())[key]:
            row={k:row[k] for k in ('path','bytes','sha256')}
            if row['path'] in historical: assert historical[row['path']]==row
            historical[row['path']]=row
    base={r['path']:r for r in json.loads((kit/'BASE_PUBLIC_MANIFEST.json').read_text())['files']}
    for name in json.loads((kit/'BASE_DOWNLOADS.json').read_text())['paths']:
        row={k:base[name][k] for k in ('path','bytes','sha256')}
        if name in historical: assert historical[name]==row
        historical[name]=row
    assert len(historical)==2797
    for name,row in historical.items(): assert identity(root,name)==row,name
    names=set(historical)
    for directory in [P+x for x in ('candidate/epoch19','controller/epoch19','audit/epoch19','legal-transfer/epoch19','epoch19')]:
        folder=root/directory
        assert not any(x.is_symlink() for x in [folder,*folder.parents])
        if not folder.exists():
            assert directory!=P+'epoch19'
            continue
        assert folder.is_dir()
        for base,dirs,files in os.walk(folder,followlinks=False):
            for child in dirs:
                path=Path(base)/child
                assert not path.is_symlink() and path.is_dir()
            for child in files:
                path=Path(base)/child
                name=path.relative_to(root).as_posix()
                if '__pycache__' in path.parts or path.suffix=='.pyc': raise ValueError('Unexpected generated source')
                if name.endswith(('/plan.json','/candidate-source-freeze.json','/NATIVE_ADMISSION.json')):
                    raise ValueError('Freeze/plan/late admission already exists')
                if name==P+'epoch19/launch.json' or name.startswith(P+'epoch19/runs/') or name in {P+'epoch19/'+n for n in ('RESULTS.json','USED_IDENTITIES.json','EPOCH_MANIFEST.json')}:
                    raise ValueError('Prior qualification attempt or final result evidence exists')
                names.add(name)
    rows=[identity(root,n) for n in sorted(names)]
    snapshot={'schema_version':1,'epoch':19,'at':datetime.now(timezone.utc).isoformat(),
        'source_checkpoint':SOURCE,'files':rows,'historical_sources':len(historical),
        'scope':'All exact restored public CP/KIT/BASE sources and stable new19 source/protocol/roles/preparation only. External model/native bytes separately verified inside bounded worker. No new legal inputs/labels/confirmation roles.',
        'model_native_calls_before_freeze':0}
    named={
        'spec':P+'epoch18/reporting/SEMANTIC_PRECISION_QUALIFICATION_SPEC.json',
        'fixtures':P+'legal-transfer/epoch19/canaries.json',
        'native_addendum':P+'epoch19/NATIVE_ENGINEERING_ADDENDUM.json',
        'model_assets_lock':P+'candidate/epoch17/model-assets.lock.json',
        'wheel_lock':P+'epoch17/preparation/python-wheel-identities.json',
        'native_closure':P+'epoch17/preparation/runtime-closure.json',
        'source_freeze':freeze_name}
    by_path={r['path']:r for r in rows}
    refs={key:identity(root,name) for key,name in named.items() if key!='source_freeze'}
    audit_ref=identity(root,P+'audit/epoch19/protocol.json')
    for row in [*refs.values(),audit_ref]: assert by_path.get(row['path'])==row
    # Every known input has passed before the first immutable output is created.
    write(root/freeze_name,snapshot)
    freeze_row=identity(root,freeze_name)
    refs['source_freeze']=freeze_row
    pins=[{'path':r['path'],'sha256':r['sha256']} for r in rows+[freeze_row]]
    plan={'schema_version':1,'epoch':19,'study_id':'native-semantic-precision-qualification-e19',
        'source_checkpoint':SOURCE,'planning_lease_commit':'f55bc2c77247a67ea84d6b2db1cbed192f16b94c',
        'actual_project':str(root),'lease_expires_unix':owner['expires_unix'],
        'inference_python':str(root/'retrieval/.venv/bin/python'),
        'pins':pins,'audit_protocol':audit_ref,
        'train':[],'calibration':[],'datasets':[],'confirmation':[],
        'limits':{'native_batches':1,'worker_attempts':1,'threads':2,'interop_threads':1,
            'seconds_per_batch':600,'seconds_per_decision':30,'candidate_configs':1,'paid_calls':0,
            'GPU_calls':0,'nli_forwards':6,'native_invocations':1,'native_queries':3,
            'other_model_forwards':0,'benchmark_corpora':0},
        'scope':'Engineering-only six frozen semantic pair forwards plus three deterministic native searches. No benchmark score, retrieval efficacy, promotion or submission.',
        'price_plan':{'new_paid_API_GPU_USD':0,'remaining_authorized_paid_USD':0},
        'champion':'SubmittedNative104/RRF10 unchanged','official_score':None,'official_rank':None}
    for key,name in named.items():
        row=refs[key];plan[key+'_path']=name;plan[key+'_sha256']=row['sha256']
    write(root/plan_name,plan)
    return {'source_files':len(rows),'plan_pins':len(pins),'snapshot':freeze_row,
        'plan':identity(root,P+'epoch19/plan.json'),'native_calls':0}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('project','kit','scope'): ap.add_argument('--'+key,type=Path,required=True)
    print(json.dumps(build(ap.parse_args())))
