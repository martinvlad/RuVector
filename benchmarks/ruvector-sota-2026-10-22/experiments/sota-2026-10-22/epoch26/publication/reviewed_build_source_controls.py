from pathlib import Path
import hashlib,json,os,copy,shutil
S=Path(__file__).resolve().parent;R=S/'project';K=S/'kit';P='experiments/sota-2026-10-22/'
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(p,name=None):
 b=p.read_bytes();return {'path':name or p.relative_to(R).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def grow(name,p):
 b=p.read_bytes();return {'path':name,'mode':'100644','type':'blob','sha':hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest(),'size':len(b)}
parent='b7f8285206189ba1ee0de95057957585ac097874';assert json.loads((S/'lease-readback.json').read_text())['commit']==parent
current=[]
for d in ['candidate/epoch26','audit/epoch26','legal-transfer/epoch26','epoch26']:
 for f in sorted((R/P/d).rglob('*')):
  if f.is_file():
   assert not f.is_symlink() and '__pycache__' not in f.parts
   current.append(ref(f))
old=json.loads((K/'CHECKPOINT_MANIFEST.json').read_text());assert len(old['project_files'])==3541
cp=copy.deepcopy(old);cp['project_files']+=sorted(current,key=lambda r:r['path']);cp['epoch26_source']={'kind':'REAL_DEV_ONLY_TYPED_NLI_DIAGNOSTIC','source_checkpoint':'5acc487d6f968319a95a211fb7b3287900ca4a22','frozen_source_parent':parent,'new_source_files':len(current),'plan':ref(R/P/'epoch26/plan.json'),'source_freeze':ref(R/P/'epoch26/source-freeze.json')}
out=S/'controls-source';out.mkdir();put(out/'CHECKPOINT_MANIFEST.json',cp)
c=json.loads((S/'controls-lease/CONTINUATION.json').read_text());a=json.loads((S/'controls-lease/ACTIVE_RUN.json').read_text());a.update(state='EPOCH26_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',checkpoint_parent=parent,native_allowed=0,native_allowed_after_exact_remote_readback=1,conditional_confirmation_allowed=0,confirmation_allowed=0,instruction='One nonretryable real legal DEV-only diagnostic worker after exact independent actual remote source readback and local NATIVE_ADMISSION; fixed24queries72same-head typed pairs CPU2 <=600s incl init cleanup. No CONF/train/calibration/generation/paid/GPU/promotion/submission; unknown supervised data lineage. Preserve Native104.')
c['active_run']={**a,'path':'ACTIVE_RUN.json'};c['checkpoint_manifest_sha256']=ref(out/'CHECKPOINT_MANIFEST.json','CHECKPOINT_MANIFEST.json')['sha256'];c['prior_published_base_commit']=parent;c['epoch26_frozen_study']={key:ref(R/P/('epoch26/'+name)) for key,name in [('plan','plan.json'),('source_freeze','source-freeze.json'),('PLAN_SPEC','PLAN_SPEC.json')]};c['epoch26_official_refresh']=ref(R/P/'legal-transfer/epoch26/benchmark-refresh.json');c['benchmark_refresh']=c['epoch26_official_refresh']
c['epoch26_data_roles']={'train':[],'dev_document_ids':[437,614,194,174,256,490,317,196],'dev_hypotheses':['nda-17','nda-7','nda-3'],'calibration':[],'confirmation':[],'input_identities':ref(R/P/'epoch26/data/input-identities.json'),'projected_input_bank':ref(R/P/'epoch26/data/dev.inputs.json'),'permanent_DEV_after_projection':True,'original_TRAIN_pool_after_projection':{'exposed':253,'reserved_confirmation':24,'unreserved':146,'total':423},'unknown_supervised_lineage_no_fresh_CONFIRM':True};put(out/'CONTINUATION.json',c);put(out/'ACTIVE_RUN.json',a);put(S/'source-reviewed-files.json',{'files':sorted(current,key=lambda r:r['path'])})
prior=S/'controls-source-prior';prior.mkdir()
for n in ['CONTINUATION.json','ACTIVE_RUN.json']:shutil.copyfile(S/'controls-lease'/n,prior/n)
shutil.copyfile(K/'CHECKPOINT_MANIFEST.json',prior/'CHECKPOINT_MANIFEST.json')
rows={r['path']:r for r in json.loads((S/'source-filemap.json').read_text())['files']}
for n in ['CONTINUATION.json','ACTIVE_RUN.json']:rows[n]=grow(n,prior/n)
put(S/'source-prior-expected.json',{'scope':'benchmarks/ruvector-sota-2026-10-22/','files':[rows[n] for n in sorted(rows)]})
print(json.dumps({'new_source_files':len(current),'CP_rows':len(cp['project_files']),'parent':parent,'source_CP_sha256':c['checkpoint_manifest_sha256']}))

