"""Bounded stdlib ZIP + symbolic pickletools metadata inspection; never unpickle.
No checkpoint global/function is imported or invoked. Tensor storage bytes are not decoded.
"""
import argparse,collections,hashlib,json,math,os,pickletools,re,sys,zipfile
from pathlib import Path
EXPECTED_BYTES=3133958098
EXPECTED_SHA='5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db'
ASSET=Path('/workspace/ruvector-e36-reader-assets/ms-xxlarge-8f8b43dd/pytorch_model.bin')
DTYPES={'HalfStorage':('F16',2),'FloatStorage':('F32',4),'DoubleStorage':('F64',8),'LongStorage':('I64',8),'IntStorage':('I32',4),'ShortStorage':('I16',2),'CharStorage':('I8',1),'ByteStorage':('U8',1),'BoolStorage':('BOOL',1),'BFloat16Storage':('BF16',2)}
class Global:
 def __init__(self,module,name):self.module,self.name=module,name
class Storage:
 def __init__(self,key,dtype,count,location):self.key,self.dtype,self.count,self.location=key,dtype,count,location
class Tensor:
 def __init__(self,s,offset,shape,stride,requires_grad):self.storage,self.offset,self.shape,self.stride,self.requires_grad=s,offset,shape,stride,requires_grad
def require(v,msg):
 if not v:raise ValueError(msg)
def symbolic_pickle(body):
 require(len(body)<=8388608,'Pickle metadata exceeds8MiB');stack=[];memo={};mark=object();globals_seen=set();ops=0
 def popmark():
  require(mark in stack,'Missing MARK');i=len(stack)-1-stack[::-1].index(mark);a=stack[i+1:];del stack[i:];return a
 def glob(module,name):
  allowed=(module=='collections'and name=='OrderedDict')or(module=='torch._utils'and name in('_rebuild_tensor','_rebuild_tensor_v2'))or(module=='torch'and name in DTYPES)
  require(allowed,'Unapproved checkpoint GLOBAL: '+module+'.'+name);globals_seen.add(module+'.'+name);return Global(module,name)
 for op,arg,pos in pickletools.genops(body):
  ops+=1;require(ops<=2000000 and len(stack)<=20000 and len(memo)<=50000,'Opcode/stack/memo cap')
  n=op.name
  if n=='PROTO':require(2<=arg<=5,'Unsupported pickle protocol');continue
  if n=='FRAME':continue
  if n=='MARK':stack.append(mark)
  elif n in('BINUNICODE','SHORT_BINUNICODE','BINUNICODE8','UNICODE','STRING','BINSTRING','SHORT_BINSTRING'):
   if isinstance(arg,bytes):arg=arg.decode('utf-8')
   require(type(arg)is str and len(arg)<=65536,'Invalid/oversized string');stack.append(arg)
  elif n in('INT','BININT','BININT1','BININT2','LONG','LONG1','LONG4','FLOAT','BINFLOAT'):
   require(type(arg)in(int,float,bool)and(type(arg)is not float or math.isfinite(arg)),'Nonfinite number');stack.append(arg)
  elif n=='NONE':stack.append(None)
  elif n=='NEWTRUE':stack.append(True)
  elif n=='NEWFALSE':stack.append(False)
  elif n=='EMPTY_TUPLE':stack.append(())
  elif n=='TUPLE':stack.append(tuple(popmark()))
  elif n in('TUPLE1','TUPLE2','TUPLE3'):
   count=int(n[-1]);a=stack[-count:];del stack[-count:];stack.append(tuple(a))
  elif n=='EMPTY_LIST':stack.append([])
  elif n=='LIST':stack.append(popmark())
  elif n=='APPEND':v=stack.pop();require(type(stack[-1])is list,'APPEND target');stack[-1].append(v)
  elif n=='APPENDS':a=popmark();require(type(stack[-1])is list,'APPENDS target');stack[-1].extend(a)
  elif n=='EMPTY_DICT':stack.append({})
  elif n=='DICT':
   a=popmark();require(len(a)%2==0,'DICT pairs');stack.append(dict(zip(a[::2],a[1::2])))
  elif n=='SETITEM':
   value,key=stack.pop(),stack.pop();require(isinstance(stack[-1],dict)and type(key)in(str,int),'SETITEM target/key');require(key not in stack[-1],'Duplicate dict key');stack[-1][key]=value
  elif n=='SETITEMS':
   a=popmark();require(len(a)%2==0 and isinstance(stack[-1],dict),'SETITEMS pairs/target')
   for key,value in zip(a[::2],a[1::2]):require(type(key)in(str,int)and key not in stack[-1],'Invalid/duplicate key');stack[-1][key]=value
  elif n=='GLOBAL':module,name=arg.split(' ',1);stack.append(glob(module,name))
  elif n=='STACK_GLOBAL':name,module=stack.pop(),stack.pop();require(type(name)is str and type(module)is str,'STACK_GLOBAL strings');stack.append(glob(module,name))
  elif n=='REDUCE':
   args,fn=stack.pop(),stack.pop();require(isinstance(fn,Global)and type(args)is tuple,'REDUCE symbolic signature')
   if fn.module=='collections':
    require(args==(),'Only empty safe OrderedDict construction accepted');stack.append(collections.OrderedDict())
   else:
    require(fn.module=='torch._utils'and len(args)in(4,6),'Only tensor metadata rebuild accepted');s,offset,shape,stride=args[:4];grad=args[4]if len(args)==6 else False
    require(isinstance(s,Storage)and type(offset)is int and offset>=0 and type(shape)is tuple and type(stride)is tuple and len(shape)==len(stride)<=8,'Tensor storage/shape/stride metadata')
    require(all(type(v)is int and 0<=v<=2000000000 for v in shape+stride)and type(grad)is bool,'Tensor dimensions/type')
    numel=math.prod(shape);require(numel<=2000000000,'Tensor element cap');last=offset+sum((d-1)*st for d,st in zip(shape,stride))+1 if numel else offset
    require(last<=s.count,'Tensor view outside storage');require(len(args)==4 or isinstance(args[5],dict),'Unexpected backward hooks');stack.append(Tensor(s,offset,shape,stride,grad))
  elif n=='BINPERSID':
   a=stack.pop();require(type(a)is tuple and len(a)==5 and a[0]=='storage','Only storage persistent IDs');_,typ,key,loc,count=a
   require(isinstance(typ,Global)and typ.module=='torch'and typ.name in DTYPES and type(key)is str and re.fullmatch('[0-9]+',key),'Storage dtype/key')
   require(type(count)is int and 0<=count<=2000000000 and type(loc)is str and re.fullmatch('cpu|cuda:[0-9]+',loc),'Storage count/location');stack.append(Storage(key,typ.name,count,loc))
  elif n in('BINPUT','LONG_BINPUT','PUT'):require(type(arg)is int and arg not in memo,'Duplicate memo assignment');memo[arg]=stack[-1]
  elif n=='MEMOIZE':require(len(memo)not in memo,'Ambiguous MEMOIZE');memo[len(memo)]=stack[-1]
  elif n in('BINGET','LONG_BINGET','GET'):require(arg in memo,'Unknown memo reference');stack.append(memo[arg])
  elif n=='BUILD':
   state=stack.pop();target=stack[-1];require(isinstance(target,collections.OrderedDict)and type(state)is dict and set(state)=={'_metadata'},'Only inert state_dict metadata BUILD')
   meta=state['_metadata'];require(isinstance(meta,dict)and all(type(k)is str and isinstance(v,dict)and set(v)<={'version'}and all(type(x)is int for x in v.values())for k,v in meta.items()),'Unsupported state metadata')
  elif n=='DUP':stack.append(stack[-1])
  elif n=='POP':stack.pop()
  elif n=='POP_MARK':popmark()
  elif n=='STOP':require(len(stack)==1 and pos==len(body)-1,'Unexpected trailing pickle content');return stack[0],sorted(globals_seen),ops
  else:raise ValueError('Unsupported pickle opcode: '+n)
 raise ValueError('Missing pickle STOP')
def inspect_archive(path,expected_sha,expected_bytes):
 require(path.is_file()and not any(p.is_symlink()for p in(path,*path.parents)),'Missing/nonregular/symlink weight')
 require(path.stat().st_size==expected_bytes,'Unexpected original length')
 with path.open('rb')as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
 require(actual==expected_sha,'Original payload hash differs');require(zipfile.is_zipfile(path),'Unsupported non-ZIP serialization; no unsafe fallback')
 with zipfile.ZipFile(path)as archive:
  info=archive.infolist();require(1<=len(info)<=10000 and len({i.filename for i in info})==len(info),'ZIP entry cap/duplicates')
  for i in info:require(not i.flag_bits&1 and i.compress_type==zipfile.ZIP_STORED and not i.is_dir()and'\\'not in i.filename and not i.filename.startswith('/')and all(x not in('','.','..')for x in i.filename.split('/')),'ZIP entry format/path/compression')
  picks=[i for i in info if i.filename.endswith('/data.pkl')];require(len(picks)==1 and picks[0].file_size<=8388608,'Unique bounded data.pkl required');p=picks[0];prefix=p.filename[:-len('data.pkl')]
  require(all(i.filename.startswith(prefix)for i in info),'Multiple archive roots');entries={i.filename[len(prefix):]:i for i in info};require(set(entries)<={'data.pkl','version','byteorder','.data/serialization_id'}|{x for x in entries if re.fullmatch('data/[0-9]+',x)},'Unexpected archive member')
  body=archive.read(p);state,globals_seen,opcode_count=symbolic_pickle(body);require(isinstance(state,dict)and state,'Flat state mapping required')
  tensors=[];storages={}
  for name,t in state.items():
   require(type(name)is str and re.fullmatch('[A-Za-z0-9_.]{1,256}',name)and isinstance(t,Tensor),'State has non-tensor/unexpected key')
   s=t.storage;dtype,width=DTYPES[s.dtype];entry=entries.get('data/'+s.key);require(entry is not None and entry.file_size==s.count*width,'ZIP storage length differs from metadata')
   row=dict(dtype=dtype,elements=s.count,bytes=entry.file_size,location_tag=s.location)
   if s.key in storages:require(storages[s.key]==row,'Inconsistent shared storage')
   storages[s.key]=row;tensors.append(dict(name=name,dtype=dtype,shape=list(t.shape),stride=list(t.stride),numel=math.prod(t.shape),storage_key=s.key,storage_offset=t.offset,requires_grad_tag=t.requires_grad))
  require({x for x in entries if x.startswith('data/')}=={'data/'+k for k in storages},'Unreferenced/missing storage member')
  summaries={}
  for t in tensors:
   v=summaries.setdefault(t['dtype'],dict(tensor_count=0,tensor_elements=0));v['tensor_count']+=1;v['tensor_elements']+=t['numel']
  return dict(schema_version=1,epoch=36,status='ORIGINAL_ZIP_PICKLETOOLS_SYMBOLIC_METADATA_VERIFIED_NO_UNPICKLE',weights=dict(bytes=expected_bytes,sha256=actual),archive=dict(kind='ZIP_STORED',entries=len(info),data_pickle_bytes=len(body),data_pickle_sha256=hashlib.sha256(body).hexdigest(),pickle_opcodes=opcode_count,checkpoint_globals_as_inert_symbols=globals_seen,weight_storage_payloads_decoded=0),state_tensor_count=len(tensors),dtype_summaries=summaries,unique_storage_count=len(storages),unique_storage_bytes=sum(s['bytes']for s in storages.values()),storages=storages,tensors=tensors,model_parameter_count='NOT_INFERRED_FROM_STATE_DICT_ALONE; named parameters/buffers require strict model-class validation later',unsafe_unpickling_calls=0,checkpoint_functions_invoked=0,ML_imports=0,model_tokenizer_native_calls=0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();require(a.file.absolute()==ASSET,'Only exact reviewed original asset path');require(not a.output.exists(),'Immutable metadata output only');result=inspect_archive(a.file,EXPECTED_SHA,EXPECTED_BYTES)
 require(not any(n.split('.')[0]in('torch','transformers','numpy','onnxruntime','tokenizers')for n in sys.modules),'Unexpected ML import')
 with a.output.open('x')as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(a.output.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);print(json.dumps(dict(status=result['status'],tensors=result['state_tensor_count'],dtype_summaries=result['dtype_summaries'],output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))
if __name__=='__main__':main()
