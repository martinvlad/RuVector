"""Root metadata-only final binding and source freeze. No science/Git entrypoint."""
from pathlib import Path
import json, hashlib, secrets, importlib.util, os
W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34');R=W/'project'
P=R/'experiments/sota-2026-10-22/epoch53';BASE='655e7aa57e34b0d5b0702e3a5957640a932b9d23'
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p,canonical=False):
    p=Path(p);assert p.is_file() and not p.is_symlink();before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    after=p.stat();assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return dict(path=p.relative_to(R).as_posix() if canonical else str(p),bytes=after.st_size,sha256=h.hexdigest())
def put(p,d):
    b=(json.dumps(d,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return ref(p,Path(p).is_relative_to(R))
def main(template_ref):
    spec=importlib.util.spec_from_file_location('source_freeze_owner',W/'publication-helpers/guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.owner_fence()
    assert type(template_ref) is dict and set(template_ref)=={'path','bytes','sha256'}
    source=Path(template_ref['path'])
    assert source.is_absolute() and source.is_relative_to(Path('/dev/shm/ruvector-e53-candidate'))
    assert ref(source)==template_ref
    b=source.read_bytes()
    plan=json.loads(b);assert plan['source_checkpoint']==BASE and plan['epoch']==53 and plan['confirmation_lineage_status']=='UNQUALIFIED_HOLD'
    binding_receipts=[]
    for row in plan['unresolved_Root_final_bindings']:
        field=row['field']
        if field.startswith('model_assets.'):continue
        parts=field.split('.');target=plan
        for part in parts[:-1]:target=target[part]
        if field.endswith('.token'):value=secrets.token_hex(32)
        else:value=ref(R/row['path'],True)
        target[parts[-1]]=value;binding_receipts.append(dict(field=field,value=value))
    acquisition_path=P/'preparation/CURRENT_MODEL_AND_ARCHIVE_VERIFICATION.v1.json'
    assert acquisition_path.read_bytes()==(W/'CURRENT_MODEL_AND_ARCHIVE_VERIFICATION.v1.json').read_bytes()
    assets=json.loads(acquisition_path.read_bytes())
    assert assets['epoch']==53 and assets['source_checkpoint']==BASE and assets['checks_passed'] is True
    assert assets['actual_acquisition_GETs']==0 and assets['model_tokenizer_native_DATA_Gold_EVAL_calls']==0 and assets['source_archive_parsed'] is False
    byname={Path(x['path']).name:x for x in assets['model_assets']};assert len(byname)==7 and len(plan['model_assets'])==7
    for row in plan['model_assets']:
        actual=byname[row['file']];assert row['path']==actual['path'] and row['bytes']==actual['bytes']
        assert row.get('sha256') in (None,actual['sha256'])
        row['sha256']=actual['sha256']
    plan['current_runtime_version_proof']=plan['runtime_verified_members']
    plan['unresolved_Root_final_bindings']=[]
    plan['status']='FROZEN_DEV_ONLY_SOURCE_NOT_SCIENTIFIC_ADMISSION'
    plan['actual_asset_acquisition_at_freeze']=dict(kind='READ_ONLY_EXACT_HASH_REUSE_NO_NEW_ACQUISITION',result=ref(acquisition_path,True),initial_asset_GETs=0,redirect_count=0,verified_files=7,elapsed_seconds=None,framework_tokenizer_model_native_initializations=0,paid_API_GPU_calls=0)
    plan['confirmation_lineage_status']='UNQUALIFIED_HOLD';plan['confirmation_materialization_authorized']=False;plan['promotion_authorized']=False
    assert plan['phase_slots']['dev']['token']!=plan['phase_slots']['confirmation']['token']
    def refs(x):
        if isinstance(x,dict):
            if {'path','bytes','sha256'}<=set(x) and x.get('path')!=plan['source_archive_member']['path']:yield x
            for v in x.values():yield from refs(v)
        elif isinstance(x,list):
            for v in x:yield from refs(v)
    for row in refs(plan):
        assert type(row['bytes']) is int and type(row['sha256']) is str and len(row['sha256'])==64,row
        path=Path(row['path']);path=path if path.is_absolute() else R/path
        assert ref(path)['bytes']==row['bytes'] and ref(path)['sha256']==row['sha256'],row
    planref=put(P/'plan.json',plan)
    roots=[R/'experiments/sota-2026-10-22'/s for s in ['epoch53','audit/epoch53','runtime/epoch53']]
    current={f.relative_to(R).as_posix():ref(f,True) for root in roots for f in root.rglob('*') if f.is_file()}
    frozen=dict(current);inherited=[];cp=json.loads((W/'remote-current/CHECKPOINT_MANIFEST.json').read_bytes());cpmap={x['path']:x for x in cp['project_files']};gm=json.loads((W/'actual-git-map.json').read_bytes());gitmap={x['path']:x for x in gm['files']}
    for row in refs(plan):
        name=row['path']
        if Path(name).is_absolute() or name in frozen:continue
        frozen[name]={k:row[k] for k in ['path','bytes','sha256']}
        if name in cpmap:assert cpmap[name]==frozen[name]
        else:
            b=(R/name).read_bytes();assert gitmap[name]['sha']==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        inherited.append(dict(reference=frozen[name],actual_base_CP_member=name in cpmap,actual_base_Git_member=name in gitmap))
    sf=dict(schema_version=1,epoch=53,kind=plan['kind'],source_checkpoint=BASE,files=[frozen[k] for k in sorted(frozen)],inherited_source_provenance=inherited,
        actual_model_tokenizer_native_DATA_Gold_initializations_or_measurements_at_freeze=0,actual_free_asset_acquisition_completed=False,current_exact_hash_asset_reuse_verified=True,
        confirmation_lineage_status='UNQUALIFIED_HOLD',no_training_or_calibration=True,no_hidden_warmup_or_canary=True,
        scientific_dispatch_authorized=False,scope='All current public SOURCE artifacts except this manifest, plus exact inherited execution/scorer provenance. Immutable candidate/roles before DATA.')
    sfref=put(P/'SOURCE_FREEZE.json',sf)
    current[sfref['path']]=sfref
    owner=ref(W/'owner.json');source_record=dict(schema_version=1,epoch=53,kind=plan['kind'],status='FROZEN_SOURCE_NOT_SCIENTIFIC_ADMISSION',source_checkpoint=BASE,plan=planref,source_freeze=sfref,owner=owner,
        actual_benchmark_model_native_DATA_Gold_calls=0,actual_free_asset_acquisition_completed=False,current_exact_hash_asset_reuse_verified=True,confirmation_lineage_status='UNQUALIFIED_HOLD',champion_preserved=True,official_goal_verified=False,official_rank=None)
    roles=dict(train=[],calibration=[],dev=plan['data_roles']['dev'],confirmation=plan['data_roles']['confirmation'],DEV_scope='Project-unused groups; publisher checkpoint-development/model-selection exposure is acknowledged.',confirmation_lineage_status='UNQUALIFIED_HOLD',confirmation_materialization_authorized=False,used_confirmation_identities=[])
    active=dict(epoch=53,phase='source',kind=plan['kind'],source_checkpoint=BASE,owner_sha256=owner['sha256'],work_active=True,experiments_active=False,OS_lock_observation_scope='PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE',publication_is_not_scientific_authorization=True)
    inp=dict(schema_version=1,epoch=53,kind=plan['kind'],phase='source',source_checkpoint=BASE,parent=BASE,owner=owner,plan=planref,source_freeze=sfref,transport_sources=plan['transport_sources'],
        source_map=ref(W/'actual-git-map.json'),root_baseline=ref(W/'remote-current/root.raw.json'),bench_baseline=ref(W/'remote-current/bench.raw.json'),current_CP=ref(W/'remote-current/CHECKPOINT_MANIFEST.json'),current_CONT=ref(W/'remote-current/CONTINUATION.json'),
        artifacts=[dict(current[name],local_path=str(R/name)) for name in sorted(current)],ACTIVE=active,
        CONT_patch=dict(epoch53_source=source_record,epoch53_frozen_study=dict(kind=plan['kind'],scientific_design=plan['scientific_design'],model_lineage_DEV_only_admission=plan['model_lineage_DEV_only_admission'],confirmation_lineage_status='UNQUALIFIED_HOLD',confirmation_materialization_authorized=False,publication_grants_scientific_authority=False),epoch53_data_roles=roles),
        CP_phase_record=dict(source_record,source_artifacts=len(current),data_roles=roles),commit_message='benchmarks: freeze E53 contract BERT source-fragment context DEV pilot')
    inputref=put(W/'SOURCE_PHASE_INPUT.v1.json',inp)
    out=dict(schema_version=1,epoch=53,plan=planref,source_freeze=sfref,input=inputref,current_SOURCE_artifacts=len(current),frozen_files=len(frozen),inherited_files=len(inherited),bindings=binding_receipts,actual_Git_or_scientific_calls=0)
    result=put(W/'FROZEN_SOURCE_PREPARATION.actual.v1.json',out)
    return dict(receipt=result,plan=planref,source_freeze=sfref,input=inputref,current_SOURCE_artifacts=len(current),frozen_files=len(frozen))
