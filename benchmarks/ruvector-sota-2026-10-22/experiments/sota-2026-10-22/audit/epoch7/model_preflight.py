"""Independent immutable model identity/provenance and protobuf-only audit; no ORT import."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,importlib.util,json,mmap,math,random
S=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
C=S/'candidate/epoch7';R=C/'research'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def blob(p):
 b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load(p):return json.loads(p.read_text())
choice=load(C/'model-choice.json');lock=load(C/'model-assets.lock.json');api=load(R/'conversion-api.json');up=load(R/'upstream-api.json')
assert api['sha']==choice['revision']==lock['revision']=='81795c444c24c634d3d5a6142988837b40313b3b'
assert up['sha']==choice['upstream']['revision']=='cf44676c28ba7312e5c5f8f8d2c22b3e0c9cdae2'
assert up['cardData']['license']=='mit' and 'license' not in api['cardData']
for name,remote_api,prefix in [('conversion',api,'conversion'),('upstream',up,'upstream')]:
 for f in ['README.md','config.json']:
  p=R/(prefix+'-'+f);remote=next(x for x in remote_api['siblings'] if x['rfilename']==f)
  assert p.stat().st_size==remote['size'] and blob(p)==remote['blobId']
asset_results=[]
for x in lock['assets']:
 p=S.parents[1]/x['path'];remote=next(r for r in api['siblings'] if r['rfilename']==x['remote_path'])
 assert p.stat().st_size==x['bytes']==remote['size'] and sha(p)==x['sha256']
 if x['lfs_sha256']:assert remote['lfs']['sha256']==x['sha256'] and remote['lfs']['size']==x['bytes']
 else:assert blob(p)==remote['blobId']==x['git_blob_id']
 asset_results.append({**x,'verified':True})
conf=load(C/'assets/nli-large/config.json');assert conf['id2label']=={'0':'entailment','1':'not_entailment'}
assert conf['num_hidden_layers']==24 and conf['hidden_size']==1024 and conf['max_position_embeddings']==512
source_card=(R/'upstream-README.md').read_text();csv_path=R/'training-datasets-overview.csv'
assert '7f82e4ab88d7aa82a4776f161b368cc9fa778001' in source_card
csv_rows=list(csv.DictReader(csv_path.open()));used=[r for r in csv_rows if r['used_in_v1.1'].strip().casefold()=='true']
assert not any('contractnli' in json.dumps(r).replace('-','').replace('_','').casefold() for r in csv_rows)
assert not any('contractnli' in x.replace('-','').replace('_','').casefold() for x in [source_card])
assert any('nc' in r['license'].casefold() or 'non-commercial' in r['license'].casefold() for r in used)
sp=importlib.util.spec_from_file_location('pure_proto',S/'candidate/epoch5/preflight.py');P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
st=importlib.util.spec_from_file_location('pure_static',C/'static_model.py');M=importlib.util.module_from_spec(st);st.loader.exec_module(M)
model=C/'assets/nli-large/onnx/model_quantized.onnx';static=M.inspect(model);assert static==load(C/'onnx-static.json')
counts={'graphs':0,'tensors':0,'nodes':0};external=[]
with model.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as b:
 def tensor(a,z):
  counts['tensors']+=1
  for k,w,c,d,v in P.fields(b,a,z):
   if (k==13 and w==2) or (k==14 and w==0 and v==1):external.append([a,z])
 def sparse(a,z):
  for k,w,c,d,v in P.fields(b,a,z):
   if k in (1,2) and w==2:tensor(c,d)
 def attr(a,z):
  for k,w,c,d,v in P.fields(b,a,z):
   if w!=2:continue
   if k in (5,10):tensor(c,d)
   elif k in (6,11):graph(c,d)
   elif k in (22,23):sparse(c,d)
 def node(a,z):
  counts['nodes']+=1
  for k,w,c,d,v in P.fields(b,a,z):
   if k==5 and w==2:attr(c,d)
 def graph(a,z):
  counts['graphs']+=1
  for k,w,c,d,v in P.fields(b,a,z):
   if w!=2:continue
   if k==1:node(c,d)
   elif k==5:tensor(c,d)
   elif k==15:sparse(c,d)
 for k,w,a,z,v in P.fields(b,0,len(b)):
  if k==7 and w==2:graph(a,z)
assert not external
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'model_choice_sha256':sha(C/'model-choice.json'),'assets_lock_sha256':sha(C/'model-assets.lock.json'),'assets':asset_results,'static_ONNX':static,'recursive_graph_tensor_inspection':counts,'external_tensors_any_nested_graph':external,'label_mapping':'Yes=softmax(logits)[0] entailment;No=[1] not_entailment;T1','declared_model_license':'MIT upstream; conversion card has no own license declaration','training_source_rows_used_in_v1_1':[{k:r[k] for k in ['dataset_name','license','dataset_link']} for r in used],'provenance_limits':'Declared card/CSV contain no ContractNLI entry; cannot prove no record-level or pretraining overlap. Source has mixed training licenses including noncommercial/unknown; not a wholly permissive training claim. Converter does not identify exact upstream weight commit; upstream immutable revision pins reviewed card/config only.','source_pins':[{'path':str(p.relative_to(S)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(R.iterdir()) if p.is_file()],'actual_model_or_native_calls':0,'scope':'Static identity/schema/provenance only, no ABI/ORT/session/performance claim.'}
p=O/'model-independent-v1.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(p),'recursive_counts':counts,'used_training_datasets':len(used)}))
