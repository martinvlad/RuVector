"""Hash, protobuf closure and pure threeway math checks; never initialize ONNX."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,mmap
import numpy as np

O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch10/project';C=S/'candidate/epoch9'
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
parser=module(S/'candidate/epoch5/preflight.py','reviewed_static_protobuf')
assert sha(S/'candidate/epoch5/preflight.py')=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
lock=obj(C/'model-assets.lock.json');choice=obj(C/'model-choice.json');contract=obj(S/'legal-transfer/epoch9/data-contract.json')
assert datetime.fromisoformat(choice['selected_at'])>datetime.fromisoformat(contract['frozen_at'])
assert choice['data_contract_sha256']==sha(S/'legal-transfer/epoch9/data-contract.json')
assert lock['repo']==choice['repo']=='Xenova/DeBERTa-v3-base-mnli-fever-anli'
assert lock['revision']==choice['revision']=='72a1ce83a0144efaf828b3c3844320a61197a53d'
assert choice['training']==choice['calibration']==[] and choice['configs_in_grid']==1
checked=[]
for item in lock['assets']:
 for root in (S.parents[1],P):
  path=root/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
  if not item['remote_path'].endswith('.onnx'):
   raw=path.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['git_blob_id']
 checked.append(item)
old=obj(S/'candidate/epoch4/assets.lock.json')
for item in old['assets']:
 path=P/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
folder=P/'experiments/sota-2026-10-22/candidate/epoch9/assets/nli-broader'
config=obj(folder/'config.json');assert config['id2label']=={'0':'entailment','1':'neutral','2':'contradiction'}
assert sha(folder/'tokenizer.json')==sha(P/'experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/tokenizer.json')=='a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df'
model=folder/'onnx/model_quantized.onnx';assert sha(model)=='ab9da76bb06054ea6b921560c1ecf5683a9e4d96f0ea73d78d3b4a8990aea882'
graph=parser.inspect_onnx(model)
# Recursively check tensor-valued node attributes and nested subgraphs too.
# The immutable reviewed parser checks feed/output schema and top initializers.
counts={'graphs':0,'nodes':0,'tensor_messages':0,'sparse_tensor_messages':0}
with model.open('rb')as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)as buf:
 def tensor(a,b):
  counts['tensor_messages']+=1
  for n,w,x,y,v in parser.fields(buf,a,b):
   if n==13 and w==2:raise ValueError('External tensor metadata in initializer/attribute')
   if n==14 and w==0 and v==1:raise ValueError('External tensor data_location')
 def sparse(a,b):
  counts['sparse_tensor_messages']+=1
  for n,w,x,y,v in parser.fields(buf,a,b):
   if n in (1,2) and w==2:tensor(x,y)
 def attribute(a,b):
  for n,w,x,y,v in parser.fields(buf,a,b):
   if w!=2:continue
   if n in (5,10):tensor(x,y)
   elif n in (6,11):walk_graph(x,y)
   elif n in (22,23):sparse(x,y)
 def node(a,b):
  counts['nodes']+=1
  for n,w,x,y,v in parser.fields(buf,a,b):
   if n==5 and w==2:attribute(x,y)
 def walk_graph(a,b):
  counts['graphs']+=1
  for n,w,x,y,v in parser.fields(buf,a,b):
   if w!=2:continue
   if n==1:node(x,y)
   elif n==5:tensor(x,y)
   elif n==15:sparse(x,y)
 for n,w,a,b,v in parser.fields(buf,0,len(buf)):
  if w==2 and n==7:walk_graph(a,b)
  elif w==2 and n in (20,25):raise ValueError('TrainingInfo/FunctionProto closure unsupported in this frozen inference model')
assert counts['graphs']>=1 and counts['tensor_messages']>0
m=module(C/'models.py','epoch9_pure_probability_math');mapping=m.label_indices(config)
assert mapping=={'entailment':0,'neutral':1,'contradiction':2}
rng=np.random.default_rng(20261022)
for logits in rng.normal(size=(1000,3))*30:
 p=np.exp(logits-logits.max());p/=p.sum();actual=m.probabilities(logits[None,:],mapping);typed=m.threeway_probabilities(logits[None,:],mapping)
 assert abs(actual['Yes']-p[0])<1e-14 and abs(actual['No']-(p[1]+p[2]))<1e-14
 assert typed=={'Entailment':float(p[0]),'Contradiction':float(p[2]),'NotMentioned':float(p[1])}
assert m.probabilities(np.array([[0.,100.,0.]]),mapping)['No']>.999
assert m.probabilities(np.zeros((1,3)),mapping)=={'Yes':1/3,'No':2/3}
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'actual_project':str(P),'final_models_source_sha256':sha(C/'models.py'),'final_runtime_source_sha256':sha(C/'runtime.py'),'final_config_sha256':sha(C/'config.json'),'final_proposal_manifest_sha256':sha(C/'proposal-manifest.json'),'model_choice_sha256':sha(C/'model-choice.json'),'choice_after_frozen_data_verified':True,'new_assets_lock_sha256':sha(C/'model-assets.lock.json'),'new6assets_verified_both_outer_actual':checked,'old16assets_verified_actual':True,'new_model_weight_sha256':sha(model),'config_class_mapping':mapping,'canonical_order':['Entailment','Contradiction','NotMentioned'],'production_binary':'Yes=P(E),No=P(C)+P(N),T1, all3class softmax; never E/(E+C)','pure_random_logit_checks':1000,'neutral_preservation_checked':True,'same_old_policy_new_model_tokenizer_bytes':True,'context_domain_report_sha256':sha(O/'context-capacity-independent-v1.json'),'onnx_static':graph,'recursive_all_tensor_closure':{'counts':counts,'external_tensor_references':0,'nested_graph_tensor_attributes_checked':True,'training_info_or_functions_present':False},'provenance_scope':'Different broader pretrained model, same12layer768architecture. Upstream MIT declaration and mixed dataset terms; converter has no separate license/exact upstream weight commit. No known ContractNLI roster entry does not prove absence of pretraining contamination.','model_initializations_forwards_native_paid_calls':0,'ABI_and_ORT_provider_execution_tested':False}
out=O/'model-static-independent-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'recursive':counts,'new_assets':len(checked)}))
