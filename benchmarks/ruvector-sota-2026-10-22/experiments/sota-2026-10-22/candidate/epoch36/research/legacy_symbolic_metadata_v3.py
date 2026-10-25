"""V3 explicit legacy-only inert pickletools symbol decoder. No unpickle, import or checkpoint global execution. Forked from preserved reviewed v2 decoder; storage persistent-ID contract explicitly six-field legacy. Never calls a ZIP inspector."""
import collections,math,pickletools,re
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
   a=stack.pop();require(type(a)is tuple and len(a)==6 and a[0]=='storage','Only six-field legacy storage persistent IDs');_,typ,key,loc,count,view=a
   require(isinstance(typ,Global)and typ.module=='torch'and typ.name in DTYPES and type(key)is str and re.fullmatch('[0-9]+',key),'Storage dtype/key')
   require(type(count)is int and 0<=count<=2000000000 and type(loc)is str and re.fullmatch('cpu|cuda:[0-9]+',loc),'Storage count/location')
   storage=Storage(key,typ.name,count,loc);storage.root_count=count;storage.view_offset=0;storage.view_key=None
   if view is not None:
    require(type(view)is tuple and len(view)==3,'Legacy view metadata tuple');vk,vo,vc=view
    require(type(vk)is str and re.fullmatch('[0-9]+',vk)and type(vo)is int and type(vc)is int and 0<=vo<=count and 0<=vc<=count-vo,'Legacy view bounds')
    storage.view_key=vk;storage.view_offset=vo;storage.count=vc
   stack.append(storage)
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
