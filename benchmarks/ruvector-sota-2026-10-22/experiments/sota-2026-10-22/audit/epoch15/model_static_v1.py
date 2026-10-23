"""Independent current selected asset, recursive protobuf and pure decoder audit.

Imports no onnxruntime, initializes no sessions and performs no native/model call.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,importlib.metadata,json,mmap
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def obj(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def module(p,name):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();s=ROOT/'experiments/sota-2026-10-22';c=s/'candidate/epoch15';proposal=obj(c/'proposal-manifest.json');assert sha(c/'proposal-manifest.json')=='d08312546400cbab7e7be0c4b597d699fdadd5898afef7a97187dbb247b748c5'
 checked=[]
 for item in proposal['sources']+proposal['read_only_code_dependencies']+[proposal['config'],proposal['assets_manifest'],*proposal['data_role_pins']]:
  p=ROOT/item['path'];assert p.is_file() and not any(x.is_symlink() for x in [p,*p.parents]);assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],item['path'];checked.append(item['path'])
 lock=obj(c/'assets.lock.json');model_lock=obj(c/'model-assets.lock.json');choice=obj(c/'model-choice.json');assert choice['repo']==model_lock['repo']=='cross-encoder/nli-deberta-v3-large' and choice['revision']==model_lock['revision']=='bab4bc7178836f731dcfd18c06ca9def0a137712'
 for package,version in lock['python_versions'].items():assert importlib.metadata.version(package)==version
 for item in lock['assets']:
  p=ROOT/item['path'];assert p.is_file() and not any(x.is_symlink() for x in [p,*p.parents]);assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],item['path']
 closure_files=[]
 core=obj(s/'epoch4/runtime-repair/official-package-closure.json');typesafe=obj(s/'epoch5/typesafe-runtime-closure.json')
 for item in [f for package in core['packages'] for f in package['files']]+typesafe['files']:
  p=ROOT/item['path'];assert p.is_file() and not any(x.is_symlink() for x in [p,*p.parents]);assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'];closure_files.append(item['path'])
 assert len(closure_files)==22
 folder=c/'assets/official-deberta-v3-large';cfg=obj(folder/'config.json');card=(folder/'README.md').read_text();assert cfg['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'} and cfg['num_hidden_layers']==24 and cfg['hidden_size']==1024
 assert 'license: apache-2.0' in card and 'snli' in card.casefold() and ('multi_nli' in card.casefold() or 'multinli' in card.casefold()) and 'contractnli' not in card.casefold()
 model=folder/'onnx/model_quint8_avx2.onnx';assert model.stat().st_size==642857089 and sha(model)=='821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
 parser_path=s/'candidate/epoch5/preflight.py';assert sha(parser_path)=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35';parser=module(parser_path,'audit15_reviewed_static_parser');graph=parser.inspect_onnx(model);static=obj(c/'onnx-static.json');assert all(static[k]==v for k,v in graph.items())
 assert graph['outputs']==[{'name':'logits','tensor_element_type':1,'dimensions':[{'parameter':'batch_size'},{'value':3}]}] and {x['name'] for x in graph['inputs']}=={'input_ids','attention_mask'} and all(x['tensor_element_type']==7 for x in graph['inputs'])
 assert not graph['external_initializers'] and graph['operators'].get('::DynamicQuantizeLinear',0)>0 and graph['operators'].get('::MatMulInteger',0)>0
 counts={'graphs':0,'nodes':0,'tensor_messages':0,'sparse_tensor_messages':0};types={}
 with model.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as buf:
  def tensor(a,b):
   counts['tensor_messages']+=1
   for n,w,x,y,v in parser.fields(buf,a,b):
    if n==2 and w==0:types[v]=types.get(v,0)+1
    if n==13 and w==2:raise ValueError('External tensor metadata anywhere in graph')
    if n==14 and w==0 and v==1:raise ValueError('External data location anywhere in graph')
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
    if w==2 and n==1:node(x,y)
    elif w==2 and n==5:tensor(x,y)
    elif w==2 and n==15:sparse(x,y)
  for n,w,x,y,v in parser.fields(buf,0,len(buf)):
   if w==2 and n==7:walk_graph(x,y)
   elif w==2 and n in (20,25):raise ValueError('Unsupported TrainingInfo/FunctionProto closure')
 assert counts['graphs']>=1 and counts['tensor_messages']>0 and types.get(1,0)>0 and (types.get(2,0)>0 or types.get(3,0)>0)
 math=module(c/'models.py','audit15_pure_selected_decoder');mapping=math.label_indices(cfg);assert mapping=={'contradiction':0,'entailment':1,'neutral':2};rng=np.random.default_rng(20261022)
 for z in rng.normal(size=(1000,3))*30:
  q=np.exp(z-z.max());q/=q.sum();p=math.probabilities(z[None,:],mapping);typed=math.threeway_probabilities(z[None,:],mapping);assert abs(p['Yes']-q[1])<1e-14 and abs(p['No']-q[0]-q[2])<1e-14
  assert typed=={'Entailment':float(q[1]),'Contradiction':float(q[0]),'NotMentioned':float(q[2])}
 assert math.probabilities(np.array([[0.,0.,100.]]),mapping)['No']>.999 and math.probabilities(np.zeros((1,3)),mapping)=={'Yes':1/3,'No':2/3}
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'proposal_SHA256':sha(c/'proposal-manifest.json'),'candidate_source_and_dependency_records_verified':len(checked),'required_asset_records_verified':len(lock['assets']),'complete_native_regular_file_closure_verified':len(closure_files),'selected_repo':choice['repo'],'selected_revision':choice['revision'],'selected_model_SHA256':sha(model),'model_tokenizer_SHA256':sha(folder/'tokenizer.json'),'config_class_mapping':mapping,'decoder_math_random_logit_checks':1000,'neutral_preservation':True,'static_graph':graph,'recursive_tensor_closure':{'counts':counts,'tensor_data_types':types,'external_references':0,'unsupported_functions_or_training_info':False},'no_documented_ContractNLI_supervision':True,'source_training_and_license_limit':'Official card declaresSNLI+MultiNLI/Apache2, not independently exhaustive run lineage, componentdata rights, unknownpretraining/fuzzyoverlap or proven legal superiority. AuthorfixedQUINT8 conversion fidelity not independently compared tooriginal PyTorch. No weights republished.','ABI_provider_execution_or_performance_verified':False,'model_native_session_fit_paid_GPU_calls':0,'candidate_measurement_admission':'Requires root finaldata/sourceplan/sourceclosure and independent fullprelaunch report'}
 raw=(json.dumps(result,indent=2)+'\n').encode()
 with a.out.open('xb') as f:f.write(raw)
 print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(raw).hexdigest(),'recursive':counts,'assets':len(lock['assets']),'sources':len(checked)}))
if __name__=='__main__':main()
