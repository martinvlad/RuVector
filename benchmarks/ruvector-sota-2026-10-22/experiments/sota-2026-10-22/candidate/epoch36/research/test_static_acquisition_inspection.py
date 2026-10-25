import ast,hashlib,importlib.util,json,struct,tempfile,zipfile
from pathlib import Path
W=Path(__file__).parent
s=importlib.util.spec_from_file_location('e36_safe_inspect',W/'inspect_original_zip_pickle_metadata.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def u(v):
 b=v.encode();return b'X'+struct.pack('<I',len(b))+b
def g(module,name):return b'c'+module.encode()+b'\n'+name.encode()+b'\n'
def k(i):return b'K'+bytes([i])
def tensor(storage='HalfStorage',key='0',count=6,offset=0):
 return g('torch._utils','_rebuild_tensor_v2')+b'('+b'('+u('storage')+g('torch',storage)+u(key)+u('cpu')+k(count)+b'tQ'+k(offset)+k(2)+k(3)+b'\x86'+k(3)+k(1)+b'\x86\x89'+g('collections','OrderedDict')+b')R'+b'tR'
def pick(t=None):return b'\x80\x02'+g('collections','OrderedDict')+b')R('+u('classifier.weight')+(tensor()if t is None else t)+b'u.'
def fail(call):
 try:call()
 except(ValueError,KeyError,TypeError,IndexError):return
 raise AssertionError('Expected closed refusal')
def inspect(p):return m.inspect_archive(p,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)
checks=[]
def check(name,fn):fn();checks.append(dict(name=name,passed=True))
with tempfile.TemporaryDirectory(prefix='e36-pure-static-fixtures-')as td:
 d=Path(td)
 def make(name,body=None,extra=None,compression=zipfile.ZIP_STORED):
  p=d/name
  with zipfile.ZipFile(p,'w',compression=compression)as z:
   z.writestr('archive/data.pkl',pick()if body is None else body);z.writestr('archive/data/0',bytes(12));z.writestr('archive/version',b'3\n')
   if extra:z.writestr(*extra)
  return p
 good=make('valid.zip');r=inspect(good)
 assert r['dtype_summaries']=={'F16':dict(tensor_count=1,tensor_elements=6)}and r['unique_storage_bytes']==12 and r['archive']['weight_storage_payloads_decoded']==0
 checks.append(dict(name='safe_symbolic_F16_tensor_no_unpickle',passed=True))
 check('reject_hash_mismatch',lambda:fail(lambda:m.inspect_archive(good,'0'*64,good.stat().st_size)))
 check('reject_length_mismatch',lambda:fail(lambda:m.inspect_archive(good,hashlib.sha256(good.read_bytes()).hexdigest(),1)))
 check('reject_arbitrary_GLOBAL_without_execution',lambda:fail(lambda:m.symbolic_pickle(b'\x80\x02'+g('os','system')+b'.')))
 bad=make('badbounds.zip',pick(tensor(offset=1)));check('reject_tensor_view_outside_storage',lambda:fail(lambda:inspect(bad)))
 bad=make('trailing.zip',pick()+b'garbage');check('reject_trailing_pickle_payload',lambda:fail(lambda:inspect(bad)))
 bad=make('unusedstorage.zip',extra=('archive/data/1',b'00'));check('reject_unreferenced_storage',lambda:fail(lambda:inspect(bad)))
 bad=make('compressed.zip',compression=zipfile.ZIP_DEFLATED);check('reject_compressed_payload',lambda:fail(lambda:inspect(bad)))
 bad=make('traversal.zip',extra=('archive/../escape',b'0'));check('reject_ZIP_parent_traversal',lambda:fail(lambda:inspect(bad)))
 bad=d/'notzip.bin';bad.write_bytes(b'not a checkpoint');check('reject_legacy_nonZIP_without_fallback',lambda:fail(lambda:inspect(bad)))
 check('reject_unknown_persistent_storage_dtype',lambda:fail(lambda:m.symbolic_pickle(pick(tensor(storage='UnknownStorage')))))
 check('reject_missing_STOP',lambda:fail(lambda:m.symbolic_pickle(pick()[:-1])))
 check('reject_new_object_opcode',lambda:fail(lambda:m.symbolic_pickle(b'\x80\x02)\x81.')))
 check('reject_unknown_memo_reference',lambda:fail(lambda:m.symbolic_pickle(b'\x80\x02h\x01.')))
 check('reject_non_tensor_state',lambda:fail(lambda:inspect(make('nontensor.zip',b'\x80\x02}'+u('name')+u('arbitrary')+b's.'))))
 for file in('acquire_original_assets_once.py','inspect_original_zip_pickle_metadata.py'):
  tree=ast.parse((W/file).read_text());imports=[]
  for node in ast.walk(tree):
   if isinstance(node,ast.Import):imports +=[a.name.split('.')[0]for a in node.names]
   if isinstance(node,ast.ImportFrom):imports.append((node.module or'').split('.')[0])
  assert not set(imports)&{'torch','transformers','numpy','onnxruntime','tokenizers','pickle'}
  assert not any(isinstance(node,ast.Call)and isinstance(node.func,ast.Attribute)and node.func.attr in('loads','load')and isinstance(node.func.value,ast.Name)and node.func.value.id=='pickle'for node in ast.walk(tree))
  checks.append(dict(name='AST_no_ML_or_unsafe_pickle_import_'+file,passed=True))
s=importlib.util.spec_from_file_location('e36_acquire_static',W/'acquire_original_assets_once.py');ac=importlib.util.module_from_spec(s);s.loader.exec_module(ac)
for url,expected in [('https://huggingface.co/a',True),('https://cdn-lfs.hf.co/a?opaque=not-persisted',True),('https://cas-bridge.xethub.hf.co/a',True),('http://huggingface.co/a',False),('https://'+'synthetic-user:synthetic-value'+'@'+'huggingface.co/a',False),('https://huggingface.co.evil.example/a',False),('https://example.com/a',False)]:
 assert ac.safe_host(url)is expected;checks.append(dict(name='allowlisted_TLS_redirect_host_'+str(len(checks)),passed=True))
report=dict(schema_version=1,epoch=36,checks_passed=True,checks=checks,total_checks=len(checks),scope='Pure handcrafted inert pickle opcodes/tiny temporary ZIP fixtures and URL allowlist checks only; no original weight bytes, checkpoint function invocation, network, model, tokenizer, native, labels or live guard actions.',actual_external_or_model_calls=0)
p=W/'ACQUISITION_INSPECTION_PREFLIGHT_v2.json'
with p.open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(checks_passed=True,total_checks=len(checks),report_sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
