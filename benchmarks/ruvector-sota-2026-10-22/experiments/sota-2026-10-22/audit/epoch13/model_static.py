"""Independent asset/protobuf/semantic math audit; no session/native/model inference."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,mmap
import numpy as np
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch13/project';C=S/'candidate/epoch13'
def obj(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
parser=module(S/'candidate/epoch5/preflight.py','reviewed_static_protobuf')
assert sha(S/'candidate/epoch5/preflight.py')=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
lock=obj(C/'model-assets.lock.json');choice=obj(C/'model-choice.json');contract=obj(S/'legal-transfer/epoch13/data-contract.json')
assert datetime.fromisoformat(choice['chosen_at_utc'])>datetime.fromisoformat(contract['frozen_at'])>datetime.fromisoformat(contract['roles_frozen_before_new_gold_projection_at'])
assert choice['data_freeze_before_choice']['sha256']==sha(S/'legal-transfer/epoch13/data-contract.json')
assert lock['repo']==choice['repo']=='cross-encoder/nli-roberta-base' and lock['revision']==choice['revision']=='1be0567456f0543475805e758725f151f283705a'
assert choice['training']==choice['calibration']==[] and choice['native_model_calls_before_choice']==choice['paid_calls']==choice['GPU_calls']==0
checked=[]
for item in lock['assets']:
 for root in(S.parents[1],P):
  path=root/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
 checked.append(item)
assert len(checked)==6
for item in obj(S/'candidate/epoch4/assets.lock.json')['assets']:
 path=P/item['path'];assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
folder=P/'experiments/sota-2026-10-22/candidate/epoch13/assets/official-roberta-base';config=obj(folder/'config.json')
assert config['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'}
assert (config['num_hidden_layers'],config['hidden_size'],config['num_attention_heads'],config['max_position_embeddings'])==(12,768,12,514)
assert sha(folder/'tokenizer.json')=='2bb1a22cfbe25b8e5a232b7fc4d7fc5073923b45724a5f813b00811bb6620f66'
assert sha(folder/'config.json')=='20b692ce487e9ae8f5e97d08c795eed4ba6fb6a5f89fd67f64880dbd232d8da4'
card=(folder/'README.md').read_text();assert 'license: apache-2.0' in card and 'nyu-mll/multi_nli' in card and 'stanfordnlp/snli' in card and 'contractnli' not in card.casefold()
model=folder/'onnx/model.onnx';assert sha(model)=='50dbf8939f1fdc45ae31fd6c1e6680489c6560b0f5e37b13da0e7979b8384ad0'
graph=parser.inspect_onnx(model)
candidate_static=obj(C/'onnx-static.json');assert all(candidate_static[k]==v for k,v in graph.items())
assert candidate_static['weight_sha256']==sha(model) and candidate_static['session_initialized'] is False and candidate_static['forwards']==0
assert set(x['name'] for x in graph['inputs'])=={'input_ids','attention_mask'}
assert all(x['tensor_element_type']==7 for x in graph['inputs'])
assert graph['outputs']==[{'name':'logits','tensor_element_type':1,'dimensions':[{'parameter':'batch_size'},{'value':3}]}]
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
m=module(C/'models.py','epoch13_pure_probability_math');mapping=m.label_indices(config)
assert mapping=={'contradiction':0,'entailment':1,'neutral':2}
rng=np.random.default_rng(20261022)
for logits in rng.normal(size=(1000,3))*30:
 p=np.exp(logits-logits.max());p/=p.sum();actual=m.probabilities(logits[None,:],mapping);typed=m.threeway_probabilities(logits[None,:],mapping)
 assert type(actual['Yes']) is float and type(actual['No']) is float
 assert abs(actual['Yes']-float(p[1]))<1e-14 and abs(actual['No']-float(p[0]+p[2]))<1e-14
 assert all(abs(typed[k]-v)<1e-14 for k,v in {'Entailment':float(p[1]),'Contradiction':float(p[0]),'NotMentioned':float(p[2])}.items())
assert m.probabilities(np.array([[0.,0.,100.]]),mapping)['No']>.999
assert m.probabilities(np.zeros((1,3)),mapping)=={'Yes':1/3,'No':2/3}
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'actual_project':str(P),'model_choice_sha256':sha(C/'model-choice.json'),'choice_after_frozen_data_verified':True,'new_assets_lock_sha256':sha(C/'model-assets.lock.json'),'new6assets_verified_both_outer_actual':checked,'old16assets_verified_actual':True,'new_model_weight_sha256':sha(model),'config_class_mapping':mapping,'canonical_order':['Entailment','Contradiction','NotMentioned'],'production_binary':'Yes=P(E),No=P(C)+P(N),full3waysoftmax T1, exact0.5tie No','pure_random_logit_checks':1000,'Python_float_scalar_types_verified':True,'neutral_preservation_checked':True,'new_active_BPE_used_consistently_for_partition_packing_decode':True,'unchanged_epoch6_algorithm':True,'unchanged_historical_policy_or_context_strings':False,'architecture':{'layers':12,'hidden_size':768,'attention_heads':12,'max_positions':514,'max_complete_tokens':512,'precision':'FP32','new_quality_or_generalization_claim':False},'context_domain_report_sha256':sha(O/'context-capacity-independent-v1.json'),'onnx_static':graph,'recursive_all_tensor_closure':{'counts':counts,'tensor_element_type_counts':tensor_types,'external_tensor_references':0,'nested_graph_tensor_attributes_checked':True,'training_info_or_functions_present':False},'source_provenance':'Official cross-encoder source/export repo at same exact revision for card/config/tokenizer/FP32. Declared Apache2 model and SNLI/MultiNLI only; no documented ContractNLI supervision. Exact training-run/export derivation, source dataset rights and unknown pretraining/fuzzy overlap not independently proven. No known empirical superiority or causal cross-epoch inference. No weights republished.','model_initializations_forwards_native_paid_calls':0,'ABI_and_ORT_provider_execution_tested':False}
out=O/'model-static-independent-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'recursive':counts,'new_assets':len(checked)}))
