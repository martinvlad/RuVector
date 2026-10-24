"""Narrow lossless E30 learned-parameter validator; standard library only."""
from __future__ import annotations
import base64,hashlib,json,math,re,struct
from phase_schema_v1 import (KIND,BASE_MODEL,TENSORS,MODULES,ARTIFACT_CODEC,
 TRAINING_STEPS,TRAINABLE_PARAMETERS,TRAINABLE_BYTES)

MAX_JSON_BYTES=8000000
TOP_KEYS={'schema_version','epoch','kind','codec','base_model','algorithm',
 'source_plan_sha256','training_inputs_sha256','training_steps','trainable_parameter_count',
 'tensors','original_head_manifest','initial_trainable_manifest','trainable_changes',
 'frozen_pretrained_proof','effective_lora_delta'}
META_KEYS={'name','shape','dtype','numel','bytes','sha256'}

def need(test,message):
 if not test:raise ValueError(message)

def digest(value):return hashlib.sha256(value).hexdigest()

def sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def strict_loads(body):
 def pairs(items):
  out={}
  for key,value in items:need(key not in out,'Duplicate artifact JSON key');out[key]=value
  return out
 return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))

def manifest_row(row,name,shape):
 need(isinstance(row,dict) and set(row)==META_KEYS,'Exact tensor metadata keys required')
 n=math.prod(shape)
 need(row['name']==name and row['shape']==shape and all(type(x)is int and x>0 for x in shape),'Tensor name/shape identity differs')
 need(row['dtype']=='float32le' and type(row['numel'])is int and row['numel']==n and type(row['bytes'])is int and row['bytes']==4*n and sha(row['sha256']),'Tensor dtype/size/hash differs')
 return row

def metadata_only(value,depth=0):
 need(depth<=12,'Metadata nesting cap')
 if isinstance(value,dict):
  need(len(value)<=128,'Metadata object cap')
  for key,child in value.items():
   need(isinstance(key,str) and key not in {'data_base64','payload','tensor_data','values','state_dict'},'Tensor payload outside the12 fixed tensor records')
   metadata_only(child,depth+1)
 elif isinstance(value,list):
  need(len(value)<=128,'Metadata list cap')
  for child in value:metadata_only(child,depth+1)
 elif isinstance(value,str):need(len(value.encode())<=1024,'Metadata string cap')
 elif type(value)is float:need(math.isfinite(value),'Nonfinite metadata')
 elif type(value)is int:need(abs(value)<=10**12,'Metadata integer cap')
 else:need(value is None or type(value)is bool,'Unknown metadata type')

def aggregate(rows):
 return digest((json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode())

def validate_artifact(body,plan_sha=None,training_inputs_sha=None,algorithm=None):
 need(isinstance(body,bytes) and len(body)<=MAX_JSON_BYTES,'Learned-parameter JSON byte cap')
 obj=strict_loads(body)
 need(isinstance(obj,dict) and set(obj)==TOP_KEYS,'Exact E30 learned-parameter header required')
 need(obj['schema_version']==1 and obj['epoch']==30 and obj['kind']==KIND and obj['codec']==ARTIFACT_CODEC,'Wrong learned artifact epoch/kind/codec')
 need(obj['base_model']==BASE_MODEL,'Only the exact original2020 BART base identity permitted')
 need(type(obj['training_steps'])is int and obj['training_steps']==TRAINING_STEPS and type(obj['trainable_parameter_count'])is int and obj['trainable_parameter_count']==TRAINABLE_PARAMETERS,'Wrong exact trained step/parameter count')
 need(sha(obj['source_plan_sha256']) and sha(obj['training_inputs_sha256']),'Exact source/input digests required')
 if plan_sha is not None:need(obj['source_plan_sha256']==plan_sha,'Artifact source plan changed')
 if training_inputs_sha is not None:need(obj['training_inputs_sha256']==training_inputs_sha,'Artifact TRAIN inputs changed')
 metadata_only(obj['algorithm'])
 if algorithm is not None:need(obj['algorithm']==algorithm,'Artifact frozen algorithm changed')
 rows=obj['tensors'];need(isinstance(rows,list) and len(rows)==12,'Exactly12 trained tensor records required')
 total=0;trained=[]
 for row,(name,shape) in zip(rows,TENSORS):
  need(isinstance(row,dict) and set(row)==META_KEYS|{'data_base64'},'Exact learned tensor record keys required')
  meta={key:row[key] for key in META_KEYS};manifest_row(meta,name,shape)
  text=row['data_base64'];need(isinstance(text,str) and len(text)==4*((meta['bytes']+2)//3),'Exact canonical tensor base64 length required')
  try:raw=base64.b64decode(text,validate=True)
  except Exception as e:raise ValueError('Invalid tensor base64') from e
  need(len(raw)==meta['bytes'] and base64.b64encode(raw).decode()==text and digest(raw)==meta['sha256'],'Tensor bytes/canonical encoding/SHA mismatch')
  need(all(math.isfinite(value[0]) for value in struct.iter_unpack('<f',raw)),'Nonfinite trained float32 value')
  trained.append(meta);total+=len(raw)
 need(total==TRAINABLE_BYTES,'Exact4,341,772 learned bytes required')
 original=obj['original_head_manifest'];initial=obj['initial_trainable_manifest']
 need(isinstance(original,list) and len(original)==4 and isinstance(initial,list) and len(initial)==12,'Original/initial manifest lengths differ')
 for row,(name,shape) in zip(original,TENSORS[-4:]):manifest_row(row,name,shape)
 for row,(name,shape) in zip(initial,TENSORS):manifest_row(row,name,shape)
 original_head_preserved=(initial[-4:]==original)
 zero_b=digest(bytes(1024*4*4))
 initial_B_zero=all(initial[index]['sha256']==zero_b for index in (1,3,5,7))
 changes=obj['trainable_changes'];need(isinstance(changes,list) and len(changes)==12,'Exact12 change records required')
 for change,before,after in zip(changes,initial,trained):
  need(isinstance(change,dict) and set(change)=={'name','before_sha256','after_sha256','changed'},'Exact trainable change keys required')
  need(change['name']==before['name']==after['name'] and change['before_sha256']==before['sha256'] and change['after_sha256']==after['sha256'] and type(change['changed']) is bool and change['changed']==(before['sha256']!=after['sha256']),'All12 intended tensor changes must be evidenced')
 frozen=obj['frozen_pretrained_proof'];fk={'parameter_count','tensor_count','before_after','all_bit_unchanged','aggregate_before_sha256','aggregate_after_sha256'}
 need(isinstance(frozen,dict) and set(frozen)==fk and frozen['parameter_count']==406291456 and type(frozen['all_bit_unchanged']) is bool,'Frozen pretrained preservation proof differs')
 proof=frozen['before_after'];need(isinstance(proof,list) and type(frozen['tensor_count'])is int and frozen['tensor_count']==len(proof)==511,'Exact511 frozen BART parameter tensors required')
 before=[];after=[];count=0;names=[]
 for record in proof:
  need(isinstance(record,dict) and set(record)=={'name','shape','dtype','numel','bytes','sha256_before','sha256_after'},'Frozen proof record payload refused')
  name=record['name'];shape=record['shape'];need(isinstance(name,str) and name not in {n for n,_ in TENSORS} and isinstance(shape,list) and len(shape)<=4,'Frozen/trainable name collision or invalid shape')
  rb={key:record[key] for key in ('name','shape','dtype','numel','bytes')};rb['sha256']=record['sha256_before'];manifest_row(rb,name,shape)
  ra=dict(rb,sha256=record['sha256_after']);need(sha(ra['sha256']),'Invalid frozen before/after digest')
  before.append(rb);after.append(ra);names.append(name);count+=record['numel']
 need(names==sorted(set(names)) and count==406291456,'Frozen original parameter coverage/count differs')
 need(frozen['aggregate_before_sha256']==aggregate(before) and frozen['aggregate_after_sha256']==aggregate(after),'Frozen aggregate canonical manifest digest differs')
 need(frozen['all_bit_unchanged']==(before==after),'Frozen preservation declaration differs from actual hashes')
 delta=obj['effective_lora_delta'];dk={'module','shape','scale','sha256','l2_norm','max_abs','nonzero_entries','B_nonzero_gradient_steps','max_B_gradient_l2'}
 need(isinstance(delta,list) and len(delta)==4,'Four effective LoRA mechanism summaries required')
 for row,module in zip(delta,MODULES):
  need(isinstance(row,dict) and set(row)==dk and row['module']==module and row['shape']==[1024,1024] and row['scale']==2.0 and sha(row['sha256']),'Exact effective LoRA module/shape/scale/hash required')
  for key in ('l2_norm','max_abs','max_B_gradient_l2'):need(type(row[key])in(int,float) and math.isfinite(row[key]) and row[key]>=0,'Nonzero finite effective-LoRA/gradient evidence required')
  need(type(row['nonzero_entries'])is int and 0<=row['nonzero_entries']<=1048576,'Nonzero effective LoRA entries required')
  steps=row['B_nonzero_gradient_steps'];need(isinstance(steps,list) and steps==sorted(set(steps)) and all(type(v)is int and 1<=v<=24 for v in steps),'Actual finite B-gradient step evidence required')
 return {'artifact_sha256':digest(body),'artifact_bytes':len(body),'trainable_parameter_count':TRAINABLE_PARAMETERS,
  'decoded_float32_bytes':total,'training_steps':24,'source_plan_sha256':obj['source_plan_sha256'],
  'training_inputs_sha256':obj['training_inputs_sha256'],'frozen_parameter_count':406291456,
  'original_head_preserved':original_head_preserved,'initial_LoRA_B_bit_zero':initial_B_zero,'all_frozen_pretrained_bit_unchanged':frozen['all_bit_unchanged'],'all12_trainable_tensors_changed':all(r['changed'] for r in changes),'all4_effective_lora_mechanisms_nonzero':all(r['nonzero_entries']>0 and r['l2_norm']>0 and r['max_B_gradient_l2']>0 and bool(r['B_nonzero_gradient_steps']) for r in delta)}
