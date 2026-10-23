"""Hash, protobuf closure and pure threeway math checks; never initialize ONNX."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,mmap
import numpy as np

O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch12/project';C=S/'candidate/epoch12'
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
parser=module(S/'candidate/epoch5/preflight.py','reviewed_static_protobuf')
assert sha(S/'candidate/epoch5/preflight.py')=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
lock=obj(C/'model-assets.lock.json');choice=obj(C/'model-choice.json');contract=obj(S/'legal-transfer/epoch12/data-contract.json')
assert datetime.fromisoformat(choice['selected_at'])>datetime.fromisoformat(contract['frozen_at'])
assert choice['data_contract_sha256']==sha(S/'legal-transfer/epoch12/data-contract.json')
assert lock['repo']==choice['repo']=='Xenova/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
assert lock['revision']==choice['revision']=='a70e12f8244efae07cf6fdfa935df30e3ac4a060'
assert choice['training_fit']==choice['calibration']==[] and choice['configs_in_grid']==1
checked=[]
for item in lock['assets']:
 for root in (S.parents[1],P):
  path=root/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
  if not item['remote_path'].endswith('.onnx'):
   raw=path.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['git_blob_id']
 checked.append(item)
old11=obj(S/'candidate/epoch11/model-assets.lock.json')
for item in old11['assets']:
 path=P/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
old=obj(S/'candidate/epoch4/assets.lock.json')
for item in old['assets']:
 path=P/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
folder=P/'experiments/sota-2026-10-22/candidate/epoch11/assets/nli-large-threeway'
config=obj(folder/'config.json');assert config['id2label']=={'0':'entailment','1':'neutral','2':'contradiction'}
assert sha(folder/'tokenizer.json')=='7aa118770f066a74530d161c7d0b994d0629cc0ff3a0df213f184192773f960a'
assert sha(P/'experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/tokenizer.json')=='a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df'
assert config['hidden_size']==1024 and config['num_hidden_layers']==24 and config['num_attention_heads']==16 and config['max_position_embeddings']==512
assert config['hidden_size']>json.loads((S/'candidate/epoch9/assets/nli-broader/config.json').read_text())['hidden_size']
assert config['num_hidden_layers']>json.loads((S/'candidate/epoch9/assets/nli-broader/config.json').read_text())['num_hidden_layers']
model=P/'experiments/sota-2026-10-22/candidate/epoch12/assets/fp32/onnx/model.onnx';assert sha(model)=='9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b'
graph=parser.inspect_onnx(model)
# Recursively check tensor-valued node attributes and nested subgraphs too.
# The immutable reviewed parser checks feed/output schema and top initializers.
counts={'graphs':0,'nodes':0,'tensor_messages':0,'sparse_tensor_messages':0};tensor_types={}
with model.open('rb')as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)as buf:
 def tensor(a,b):
  counts['tensor_messages']+=1
  for n,w,x,y,v in parser.fields(buf,a,b):
   if n==2 and w==0:tensor_types[v]=tensor_types.get(v,0)+1
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
assert tensor_types.get(1,0)>0 and tensor_types.get(2,0)==tensor_types.get(3,0)==0
assert not any(x in graph['operators'] for x in ('::QuantizeLinear','::DynamicQuantizeLinear','::MatMulInteger','::DequantizeLinear'))
m=module(C/'models.py','epoch12_pure_probability_math');mapping=m.label_indices(config)
assert mapping=={'entailment':0,'neutral':1,'contradiction':2}
rng=np.random.default_rng(20261022)
for logits in rng.normal(size=(1000,3))*30:
 p=np.exp(logits-logits.max());p/=p.sum();actual=m.probabilities(logits[None,:],mapping);typed=m.threeway_probabilities(logits[None,:],mapping)
 assert abs(actual['Yes']-p[0])<1e-14 and abs(actual['No']-(p[1]+p[2]))<1e-14
 assert all(abs(typed[k]-v)<1e-14 for k,v in {'Entailment':float(p[0]),'Contradiction':float(p[2]),'NotMentioned':float(p[1])}.items())
assert m.probabilities(np.array([[0.,100.,0.]]),mapping)['No']>.999
assert m.probabilities(np.zeros((1,3)),mapping)=={'Yes':1/3,'No':2/3}
def trace(logits,precision):
 probs=np.exp(logits-logits.max());probs/=probs.sum()
 return {'precision':precision,'input_ids':[1,2,3],'attention_mask':[1,1,1],'token_type_ids':[0,0,1],'input_text_sha256':'a'*64,'raw_label_indices':mapping,'canonical_logits_E_C_N':[float(logits[i]) for i in (0,2,1)],'raw_threeway_probabilities':{'Entailment':float(probs[0]),'Contradiction':float(probs[2]),'NotMentioned':float(probs[1])}}
for _ in range(1000):
 la=rng.normal(size=3)*8;lb=rng.normal(size=3)*8;a=trace(la,'FP32');b=trace(lb,'INT8_TRAIN_DIAGNOSTIC');f=m.paired_fidelity(a,b)
 av=np.asarray(a['canonical_logits_E_C_N']);bv=np.asarray(b['canonical_logits_E_C_N']);pa=np.asarray(list(a['raw_threeway_probabilities'].values()));pb=np.asarray(list(b['raw_threeway_probabilities'].values()));mid=.5*(pa+pb)
 expected=.5*float(np.sum(pa*(np.log(pa)-np.log(mid)))+np.sum(pb*(np.log(pb)-np.log(mid))))
 assert abs(f['raw_logits_max_absolute_difference']-np.max(np.abs(av-bv)))<1e-12
 assert abs(f['centered_logits_max_absolute_difference']-np.max(np.abs((av-av.mean())-(bv-bv.mean()))))<1e-12
 assert abs(f['typed_probability_L1_difference']-np.sum(np.abs(pa-pb)))<1e-12
 assert abs(f['Jensen_Shannon_divergence_nats']-expected)<1e-12
 assert not f['source_original_fidelity_established']
a=trace(np.zeros(3),'FP32');b=trace(np.zeros(3),'INT8_TRAIN_DIAGNOSTIC');assert m.paired_fidelity(a,b)['binary_decision_agrees']
b['input_ids']=[4]
try:m.paired_fidelity(a,b)
except ValueError:pass
else:raise AssertionError('Different paired feeds accepted')
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'actual_project':str(P),'model_choice_sha256':sha(C/'model-choice.json'),'choice_after_frozen_data_verified':True,'new_assets_lock_sha256':sha(C/'model-assets.lock.json'),'new1FP32asset_verified_both_outer_actual':checked,'old16assets_verified_actual':True,'inherited6epoch11assets_and_INT8_verified_actual':True,'new_model_weight_sha256':sha(model),'config_class_mapping':mapping,'canonical_order':['Entailment','Contradiction','NotMentioned'],'production_binary':'Yes=P(E),No=P(C)+P(N),T1, all3class softmax; never E/(E+C)','pure_random_logit_checks':1000,'independent_paired_fidelity_oracle_checks':1000,'neutral_preservation_checked':True,'same_old_policy_new_model_tokenizer_bytes':False,'active_policy_tokenizer_domain_compatibility_guarded':True,'architecture':{'layers':24,'hidden_size':1024,'attention_heads':16,'unchanged_from_epoch11':True,'precision':'FP32','new_quality_or_generalization_claim':False},'context_domain_report_sha256':sha(O/'context-capacity-independent-v1.json'),'onnx_static':graph,'recursive_all_tensor_closure':{'counts':counts,'tensor_element_type_counts':tensor_types,'external_tensor_references':0,'nested_graph_tensor_attributes_checked':True,'training_info_or_functions_present':False},'provenance_scope':'One fixed co-located FP32 export from same immutable converter revision as old INT8 variant. No source-original weight identity or quantization derivation proof; differences alone cannot establish quantization causality. Same24layer1024 architecture andfive-dataset declaration as epoch11; precision is not assumedquality. UpstreamMIT/mixed terms/converter exactweight/license gaps/unknowncontamination disclosed.','model_initializations_forwards_native_paid_calls':0,'ABI_and_ORT_provider_execution_tested':False}
out=O/'model-static-independent-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'recursive':counts,'new_assets':len(checked)}))
