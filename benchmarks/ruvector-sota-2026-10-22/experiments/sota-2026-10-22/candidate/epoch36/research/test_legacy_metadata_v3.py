"""Hand-authored tiny legacy-format metadata fixtures only. Never original weights."""
import ast,hashlib,importlib.util,json,struct,sys,tempfile
from pathlib import Path
W=Path(__file__).parent;sys.path.insert(0,str(W));s=importlib.util.spec_from_file_location('e36_legacy_pure',W/'inspect_original_legacy_metadata_v3.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def u(v):b=v.encode();return b'X'+struct.pack('<I',len(b))+b
def g(module,name):return b'c'+module.encode()+b'\n'+name.encode()+b'\n'
def val(v):
 if v is None:return b'N'
 if type(v)is bool:return b'\x88'if v else b'\x89'
 if type(v)is str:return u(v)
 if type(v)is int:
  if 0<=v<256:return b'K'+bytes([v])
  if 0<=v<65536:return b'M'+struct.pack('<H',v)
  b=v.to_bytes((v.bit_length()+8)//8,'little',signed=True);return b'\x8a'+bytes([len(b)])+b
 if type(v)is tuple:return b'('+b''.join(val(x)for x in v)+b't'
 if type(v)is list:return b']('+b''.join(val(x)for x in v)+b'e'
 if type(v)is dict:return b'}('+b''.join(val(k)+val(x)for k,x in v.items())+b'u'
 raise AssertionError('Fixture type')
def obj(v):return b'\x80\x02'+val(v)+b'.'
def tensor(dtype='HalfStorage',root='0',count=6,shape=(2,3),stride=(3,1),offset=0,view=None,fields=6):
 storage=b'('+u('storage')+g('torch',dtype)+u(root)+u('cpu')+val(count)+(val(view)if fields==6 else b'')+b'tQ'
 return g('torch._utils','_rebuild_tensor_v2')+b'('+storage+val(offset)+val(shape)+val(stride)+b'\x89'+g('collections','OrderedDict')+b')R'+b'tR'
def state(rows):return b'\x80\x02'+g('collections','OrderedDict')+b')R('+b''.join(u(k)+v for k,v in rows)+b'u.'
def failure(call):
 try:call()
 except(ValueError,KeyError,TypeError,IndexError,struct.error):return
 raise AssertionError('Expected refusal')
checks=[]
def check(name,call):call();checks.append(dict(name=name,passed=True))
with tempfile.TemporaryDirectory(prefix='e36-legacy-inert-fixtures-')as td:
 d=Path(td)
 def make(name,rows=None,magic=m.MAGIC,protocol=1001,little=True,keys=None,headers=None,tail=b'',cut=0,state_override=None,sys_override=None):
  rows=rows if rows is not None else [('classifier.weight',tensor())];keys=['0']if keys is None else keys;headers=[(6,bytes(12))]if headers is None else headers
  info=dict(protocol_version=1001,little_endian=little,type_sizes=dict(short=2,int=4,long=4))if sys_override is None else sys_override
  b=obj(magic)+obj(protocol)+obj(info)+(state(rows)if state_override is None else state_override)+obj(keys)+b''.join(struct.pack('<Q',n)+data for n,data in headers)+tail
  if cut:b=b[:-cut]
  p=d/name;p.write_bytes(b);return p
 def inspect(p):return m.inspect_legacy(p,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)
 good=make('valid.bin');r=inspect(good);assert r['status']==m.STATUS and r['source_parameter_dtype']=='F16'and r['floating_state_tensor_elements']==6 and r['storage_data_ends_at_filelength']and r['storage_payloads_decoded']==0;checks.append(dict(name='five_inert_streams_F16_exact_storage_and_EOF',passed=True))
 def rejected(name,p):failure(lambda:inspect(p));checks.append(dict(name=name,passed=True))
 rejected('reject_wrong_magic',make('magic.bin',magic=123))
 rejected('reject_wrong_protocol',make('protocol.bin',protocol=1000))
 rejected('reject_nonlittle_endian',make('endian.bin',little=False))
 rejected('reject_sys_info_schema',make('sys.bin',sys_override={}))
 rejected('reject_missing_storage_key',make('keys.bin',keys=[]))
 rejected('reject_duplicate_storage_key',make('dup.bin',keys=['0','0']))
 rejected('reject_storage_header_count_mismatch',make('header.bin',headers=[(7,bytes(12))]))
 rejected('reject_raw_storage_over_file_length',make('truncated.bin',cut=1))
 rejected('reject_trailing_bytes',make('trailing.bin',tail=b'0'))
 check('reject_wrong_hash',lambda:failure(lambda:m.inspect_legacy(good,'0'*64,good.stat().st_size)))
 check('reject_wrong_length',lambda:failure(lambda:m.inspect_legacy(good,hashlib.sha256(good.read_bytes()).hexdigest(),1)))
 rejected('reject_non_tensor_state',make('nontensor.bin',state_override=obj({'bad':'text'})))
 rejected('reject_arbitrary_GLOBAL_no_invocation',make('global.bin',state_override=b'\x80\x02'+g('os','system')+b'.'))
 rejected('reject_fivefield_ZIP_storage_tuple_in_legacy',make('five.bin',rows=[('classifier.weight',tensor(fields=5))]))
 rejected('reject_tensor_offset_over_view_bounds',make('offset.bin',rows=[('classifier.weight',tensor(offset=1))]))
 view=make('view.bin',rows=[('main',tensor()),('view',tensor(shape=(1,2),stride=(2,1),view=('1',1,2)))]);v=inspect(view);assert v['unique_storage_count']==1 and v['floating_state_tensor_elements']==8 and v['unique_floating_storage_elements']==6 and v['tensors'][1]['root_storage_offset']==1;checks.append(dict(name='valid_storage_alias_view_and_distinct_tensor_vs_storage_counts',passed=True))
 rejected('reject_legacy_view_outside_root',make('viewbad.bin',rows=[('view',tensor(shape=(1,2),stride=(2,1),view=('1',6,2)))]))
 mixed=make('mixed.bin',rows=[('float',tensor()),('position_ids',tensor(dtype='LongStorage',root='1',count=3,shape=(3,),stride=(1,)))],keys=['0','1'],headers=[(6,bytes(12)),(3,bytes(24))]);mres=inspect(mixed);assert mres['dtype_summaries']['I64']['tensor_elements']==3 and mres['source_parameter_dtype']=='F16';checks.append(dict(name='integer_buffer_recorded_without_calling_it_parameters',passed=True))
 opaque=make('opaque.bin',headers=[(6,b'cos\nsystem\n0')]);assert len(b'cos\nsystem\n0')==12;ores=inspect(opaque);assert ores['unique_storage_bytes']==12;checks.append(dict(name='raw_payload_opcode_like_bytes_are_sought_past_not_interpreted',passed=True))
 rejected('reject_unknown_storage_dtype',make('dtype.bin',rows=[('bad',tensor(dtype='NotAStorage'))]))
 for name in('legacy_symbolic_metadata_v3.py','inspect_original_legacy_metadata_v3.py'):
  tree=ast.parse((W/name).read_text());imports=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Import):imports.extend(a.name.split('.')[0]for a in n.names)
   if isinstance(n,ast.ImportFrom):imports.append((n.module or'').split('.')[0])
  assert not set(imports)&{'torch','transformers','numpy','onnxruntime','tokenizers','pickle','tarfile','zipfile'};checks.append(dict(name='AST_no_ML_pickle_unpickle_or_archive_fallback_'+name,passed=True))
assert 'pickle' in sys.modules
for filename in('legacy_symbolic_metadata_v3.py','inspect_original_legacy_metadata_v3.py'):
 tree=ast.parse((W/filename).read_text())
 assert not any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and isinstance(n.func.value,ast.Name)and n.func.value.id=='pickle'for n in ast.walk(tree))
checks.append(dict(name='pickletools_transitive_stdlib_pickle_import_allowed_no_pickle_API_invocation',passed=True))
report=dict(schema_version=3,epoch=36,checks_passed=True,checks=checks,total_checks=len(checks),real_checkpoint_inspections=0,network_GETs=0,model_tokenizer_native_or_unsafe_unpickle_calls=0,scope='Handcrafted inert concatenated pickle and tiny raw byte fixtures only. No original model payload opened or inspected and no live guard or training/data labels accessed. pickletools may import stdlib pickle for opcode definitions; no unsafe data-deserialization API is invoked.')
p=W/'LEGACY_INSPECTION_PREFLIGHT.v3.1.json'
with p.open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(checks_passed=True,total_checks=len(checks),report_sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
