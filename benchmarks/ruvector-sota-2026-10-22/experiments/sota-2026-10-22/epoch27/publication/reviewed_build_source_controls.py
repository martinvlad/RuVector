from pathlib import Path
import hashlib,json,os,copy,shutil
S=Path(__file__).resolve().parent;R=S/'project';K=S/'kit';P='experiments/sota-2026-10-22/'
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(p,name=None):
 b=p.read_bytes();return {'path':name or p.relative_to(R).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def grow(name,p):
 b=p.read_bytes();return {'path':name,'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest(),'size':len(b)}
parent='4fed2fd4d8d94df71d52ac47c61c6f59ffbd2a67';assert json.loads((S/'lease-readback.json').read_text())['commit']==parent
current=[]
for d in ['candidate/epoch27','audit/epoch27','legal-transfer/epoch27','epoch27']:
 for f in sorted((R/P/d).rglob('*')):
  if f.is_file():
   assert not f.is_symlink() and '__pycache__' not in f.parts
   current.append(ref(f))
old=json.loads((K/'CHECKPOINT_MANIFEST.json').read_text());assert len(old['project_files'])==3660
cp=copy.deepcopy(old);cp['project_files']+=sorted(current,key=lambda r:r['path']);cp['epoch27_source']={'kind':'REAL_DEV_ONLY_TYPED_NLI_DIAGNOSTIC','source_checkpoint':'6e4ad4ab0b6a09a6a1083335ed0401637227d17f','frozen_source_parent':parent,'new_source_files':len(current),'plan':ref(R/P/'epoch27/plan.json'),'source_freeze':ref(R/P/'epoch27/source-freeze.json')}
out=S/'controls-source';out.mkdir();put(out/'CHECKPOINT_MANIFEST.json',cp)
c=json.loads((S/'controls-lease/CONTINUATION.json').read_text());a=json.loads((S/'controls-lease/ACTIVE_RUN.json').read_text());a.update(state='EPOCH27_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',checkpoint_parent=parent,native_allowed=0,native_allowed_after_exact_remote_readback=1,conditional_confirmation_allowed=0,confirmation_allowed=0,instruction='One nonretryable real legal DEV-only diagnostic worker after exact independent actual remote source readback and local NATIVE_ADMISSION; fixed24queries72same-head typed pairs CPU2 <=600s incl init cleanup. No CONF/train/calibration/generation/paid/GPU/promotion/submission; missing full-input104 comparator. Preserve Native104.')
c['active_run']={**a,'path':'ACTIVE_RUN.json'};c['checkpoint_manifest_sha256']=ref(out/'CHECKPOINT_MANIFEST.json','CHECKPOINT_MANIFEST.json')['sha256'];c['prior_published_base_commit']=parent;c['epoch27_frozen_study']={key:ref(R/P/('epoch27/'+name)) for key,name in [('plan','plan.json'),('source_freeze','source-freeze.json'),('PLAN_SPEC','PLAN_SPEC.json')]};c['epoch27_official_refresh']=ref(R/P/'legal-transfer/epoch27/benchmark-refresh.json');c['benchmark_refresh']=c['epoch27_official_refresh']
c['epoch27_data_roles']={'train':[],'dev_document_ids':[609,380,592,454,559,515,349,223],'dev_hypotheses':['nda-17','nda-7','nda-3'],'calibration':[],'confirmation':[],'input_identities':ref(R/P/'epoch27/data/input-identities.json'),'projected_input_bank':ref(R/P/'epoch27/data/dev.inputs.json'),'permanent_DEV_after_projection':True,'original_TRAIN_pool_after_projection':{'exposed':261,'reserved_confirmation':24,'unreserved':138,'total':423},'confirmation_HOLD_without_full104_comparator':True};put(out/'CONTINUATION.json',c);put(out/'ACTIVE_RUN.json',a);put(S/'source-reviewed-files.json',{'files':sorted(current,key=lambda r:r['path'])})
prior=S/'controls-source-prior';prior.mkdir()
for n in ['CONTINUATION.json','ACTIVE_RUN.json']:shutil.copyfile(S/'controls-lease'/n,prior/n)
shutil.copyfile(K/'CHECKPOINT_MANIFEST.json',prior/'CHECKPOINT_MANIFEST.json')
rows={r['path']:r for r in json.loads((S/'source-filemap.json').read_text())['files']}
for n in ['CONTINUATION.json','ACTIVE_RUN.json']:rows[n]=grow(n,prior/n)
put(S/'source-prior-expected.json',{'scope':'benchmarks/ruvector-sota-2026-10-22/','files':[rows[n] for n in sorted(rows)]})
print(json.dumps({'new_source_files':len(current),'CP_rows':len(cp['project_files']),'parent':parent,'source_CP_sha256':c['checkpoint_manifest_sha256']}))

