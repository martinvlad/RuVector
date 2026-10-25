"""Explicit original PyTorch legacy format only. No ZIP fallback or unpickling.
Exactly five bounded metadata pickle streams; raw storage contents are sought past.
"""
import argparse,hashlib,json,math,os,pickletools,re,struct,sys
from pathlib import Path
from legacy_symbolic_metadata_v3 import DTYPES,Tensor,symbolic_pickle,require
ASSET=Path('/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd/pytorch_model.bin')
EXPECTED_BYTES=3133958098
EXPECTED_SHA='5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db'
FORMAT='PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES'
STATUS='ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE'
MAGIC=0x1950A86A20F9469CFC6C
class BoundedMetadata:
 def __init__(self,stream):self.stream=stream;self.total=0;self.parts=[]
 def tell(self):return self.stream.tell()
 def read(self,n):
  require(type(n)is int and 0<=n<=8388608-self.total,'Combined metadata exceeds8MiB or unbounded read');b=self.stream.read(n);require(len(b)==n,'Truncated metadata');self.total+=n;self.parts.append(b);return b
 def readline(self):
  chunks=[]
  while True:
   b=self.read(1);chunks.append(b)
   if b==b'\n':return b''.join(chunks)
 def object(self,name):
  self.parts=[];start=self.tell();count=0
  for op,arg,pos in pickletools.genops(self):
   count+=1;require(count<=2000000,'Metadata opcode cap')
  body=b''.join(self.parts);value,globals_seen,count2=symbolic_pickle(body);require(count==count2,'Opcode replay differs')
  return value,dict(name=name,offset=start,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),opcode_count=count,checkpoint_globals_as_inert_symbols=globals_seen)
def inspect_legacy(path,expected_sha,expected_bytes):
 require(path.is_file()and not any(p.is_symlink()for p in(path,*path.parents)),'Missing/nonregular/symlink source')
 require(path.stat().st_size==expected_bytes,'Original source length mismatch')
 with path.open('rb')as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
 require(actual==expected_sha,'Original source SHA differs')
 with path.open('rb')as f:
  require(f.read(4)!=b'PK\x03\x04','This is a legacy-only inspector, not a ZIP fallback');f.seek(0);reader=BoundedMetadata(f);objects=[];values=[]
  for name in('magic','protocol','sys_info','state_dict','serialized_storage_keys'):
   v,r=reader.object(name);values.append(v);objects.append(r)
  magic,protocol,info,state,keys=values
  require(magic==MAGIC and protocol==1001,'Legacy magic/protocol mismatch')
  require(type(info)is dict and set(info)=={'protocol_version','little_endian','type_sizes'}and info['protocol_version']==1001 and info['little_endian']is True,'Unsupported legacy sys_info/endian')
  require(type(info['type_sizes'])is dict and set(info['type_sizes'])=={'short','int','long'}and info['type_sizes']['short']==2 and info['type_sizes']['int']==4 and info['type_sizes']['long']in(4,8),'Unsupported legacy type sizes')
  require(isinstance(state,dict)and 1<=len(state)<=10000,'Flat bounded state mapping')
  require(type(keys)is list and len(keys)<=10000 and all(type(k)is str and re.fullmatch('[0-9]+',k)for k in keys)and len(set(keys))==len(keys),'Bounded unique legacy storage keys')
  tensors=[];storage={};summaries={};shared={}
  for name,t in state.items():
   require(type(name)is str and re.fullmatch('[A-Za-z0-9_.]{1,256}',name)and isinstance(t,Tensor),'Non-tensor or unsupported state key')
   s=t.storage;dtype,width=DTYPES[s.dtype];root_count=s.root_count;row=dict(dtype=dtype,elements=root_count,bytes=root_count*width,location_tag=s.location)
   require(row['bytes']<=expected_bytes,'Storage byte bound')
   if s.key in storage:require(storage[s.key]==row,'Inconsistent aliased root storage')
   storage[s.key]=row;shared.setdefault(s.key,[]).append(name)
   tensors.append(dict(name=name,dtype=dtype,shape=list(t.shape),stride=list(t.stride),numel=math.prod(t.shape),storage_key=s.key,storage_offset=t.offset,root_storage_offset=s.view_offset+t.offset,legacy_view_key=s.view_key,legacy_view_offset=s.view_offset,legacy_view_elements=s.count,requires_grad_tag=t.requires_grad))
   summary=summaries.setdefault(dtype,dict(tensor_count=0,tensor_elements=0));summary['tensor_count']+=1;summary['tensor_elements']+=math.prod(t.shape)
  require(set(keys)==set(storage),'Serialized root-storage list differs from tensor catalogue')
  metadata_end=f.tell();raw_bytes=0
  for key in keys:
   row=storage[key];header_offset=f.tell();header=f.read(8);require(len(header)==8,'Truncated legacy storage header');count=struct.unpack('<Q',header)[0];require(count==row['elements'],'Legacy8-byte storage count differs from metadata')
   data_offset=f.tell();end=data_offset+row['bytes'];require(end<=expected_bytes,'Legacy raw storage exceeds file');f.seek(row['bytes'],os.SEEK_CUR)
   row.update(header_offset=header_offset,header_bytes=8,header_hex=header.hex(),header_element_count=count,data_offset=data_offset,data_bytes=row['bytes'],data_end_offset=end,raw_payload_decoded=False);raw_bytes+=row['bytes']
  require(f.tell()==expected_bytes and f.read(1)==b'','Legacy storage catalogue does not account for exact EOF')
 floating=[k for k in summaries if k.startswith('F')or k=='BF16'];source_dtype=floating[0]if len(floating)==1 else'MIXED_OR_NO_FLOATING_STATE'
 return dict(schema_version=3,epoch=36,status=STATUS,format=FORMAT,weights=dict(bytes=expected_bytes,sha256=actual),magic_number_hex=hex(magic),protocol_version=protocol,sys_info=info,metadata_objects=objects,combined_metadata_bytes=metadata_end,metadata_pickle_count=5,source_parameter_dtype=source_dtype,state_tensor_count=len(tensors),dtype_summaries=summaries,floating_state_tensor_elements=sum(v['tensor_elements']for k,v in summaries.items()if k.startswith('F')or k=='BF16'),unique_floating_storage_elements=sum(v['elements']for v in storage.values()if v['dtype'].startswith('F')or v['dtype']=='BF16'),unique_storage_count=len(storage),unique_storage_bytes=raw_bytes,storage_header_bytes=8*len(storage),serialized_storage_keys_in_physical_order=keys,storage_data_ends_at_filelength=True,storage_payloads_decoded=0,storages=storage,tensors=tensors,shared_storage_keys={k:v for k,v in shared.items()if len(v)>1},model_parameter_count='NOT_INFERRED_FROM_STATE_DICT_ALONE; frozen model class must verify exact named parameter/buffer contract',unsafe_unpickling_calls=0,checkpoint_functions_invoked=0,ML_imports=0,model_tokenizer_native_calls=0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 require(a.file.absolute()==ASSET,'Only the exact original asset');require(a.output.is_absolute()and a.output.parent==Path('/workspace/ruvector-epoch36-d73fcce4c45f')and a.output.name=='XXL_ORIGINAL_WEIGHT_METADATA.json'and not a.output.exists(),'Canonical exclusive outside-project output required')
 result=inspect_legacy(a.file,EXPECTED_SHA,EXPECTED_BYTES);require(not any(n.split('.')[0]in('torch','transformers','numpy','onnxruntime','tokenizers')for n in sys.modules),'Unexpected ML import')
 with a.output.open('x')as out:json.dump(result,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
 d=os.open(a.output.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d);print(json.dumps(dict(status=result['status'],format=result['format'],source_parameter_dtype=result['source_parameter_dtype'],tensors=result['state_tensor_count'],dtype_summaries=result['dtype_summaries'],output_bytes=a.output.stat().st_size,output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))
if __name__=='__main__':main()
