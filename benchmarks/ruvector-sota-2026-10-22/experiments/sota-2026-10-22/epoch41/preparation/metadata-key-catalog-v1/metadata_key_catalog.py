"""Structural official source key inventory only. Never a case/gold materializer."""
import argparse,hashlib,importlib.util,json,os,re,signal,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE='7a40daab6ad7caf9310f678813bfef42f907bd17';KIND='METADATA_KEY_CATALOG_ONLY'
p=HERE/'SPANJSON_SOURCE.py';b=p.read_bytes()
if hashlib.sha256(b).hexdigest()!='991bf60acd8eb56c758f65d3e059777f943fa346cbb1d7d5b38e06b632ce24e9':raise ValueError('PINNED_SCANNER_SOURCE_DRIFT')
spec=importlib.util.spec_from_file_location('metadata_only_pinned_spanjson',p);J=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),J.__dict__)
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def unique(rows):
 out={}
 for k,v in rows:require(k not in out,'DUPLICATE_METADATA_KEY');out[k]=v
 return out
def ref(p):
 b=Path(p).read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def read_ref(r):
 require(type(r)is dict and set(r)=={'path','bytes','sha256'},'EXACT_SOURCE_REF');p=Path(r['path']);require(p.is_file()and not p.is_symlink(),'REGULAR_SOURCE_REQUIRED');b=p.read_bytes();require(type(r['bytes'])is int and len(b)==r['bytes']and sha(b)==r['sha256'],'SOURCE_IDENTITY_DRIFT');return b
def load_ref(r):return json.loads(read_ref(r),object_pairs_hook=unique)
def put(path,v):
 p=Path(path);b=(json.dumps(v,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return ref(p)

def catalog_only(member):
 """Generic structural byte skip occurs; no JSON STRING VALUE decoder occurs."""
 s=J.SpanJSON(member);root=s.value(0);require(root[2]=='object'and s.ws(root[1])==len(member),'EXACT_ROOT_OBJECT');top=s.members(root);require('labels'in top,'GLOBAL_CATALOG_REQUIRED');catalog=s.members(top['labels']);keys=list(catalog);require(1<=len(keys)<=128 and all(re.fullmatch('[A-Za-z0-9_-]{1,64}',k)for k in keys),'BOUNDED_SAFE_KEYS');require(s.gold_values_decoded==0 and all(x==0 for k,x in s.decoded.items()if k!='field_name'),'NO_STRING_VALUES_DECODED');return {'source_order_keys':keys,'sorted_keys':sorted(keys),'key_count':len(keys),'canonical_sorted_key_list_sha256':sha(json.dumps(sorted(keys),ensure_ascii=False,separators=(',',':')).encode()),'author_advertised_count':17,'matches_advertised_count':len(keys)==17,'decoder_counts':s.decoded,'string_value_decodes':0,'semantic_gold_values_decoded':0,'selected_document_text_decodes':0,'selected_hypothesis_text_decodes':0,'annotation_choice_value_decodes':0,'old_Legal96_text_decodes':0,'per_document_members_or_arrays_enumerated':0,'structural_JSON_byte_walk_to_skip_values':True,'hypothesis_or_case_selection':False}

def safe_error(e):
 msg=str(e);allowed={'EXACT_ROOT_OBJECT','GLOBAL_CATALOG_REQUIRED','BOUNDED_SAFE_KEYS','NO_STRING_VALUES_DECODED','EXACT_ARCHIVE_IDENTITY','EXACT_MEMBER_IDENTITY','SAFE_SINGLE_TEST_MEMBER','METADATA_INVENTORY_WORK_TIMEOUT','OBJECT_REQUIRED','DUPLICATE_JSON_KEY'};return {'code':msg if type(e)in[ValueError,TimeoutError]and msg in allowed else'METADATA_SOURCE_INVENTORY_STOP','exception_type':type(e).__name__,'message_sha256':sha(msg.encode())}
def deadline(_s,_f):raise TimeoutError('METADATA_INVENTORY_WORK_TIMEOUT')

def inventory(archive,out,policy_ref,seal_ref,authorization_ref):
 old=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,9.)
 try:
  policy=load_ref(policy_ref);seal=load_ref(seal_ref);auth=load_ref(authorization_ref);require(policy['epoch']==41 and policy['kind']==KIND and policy['purpose']=='FUTURE_SOURCE_POLICY_ONLY_NO_E41_REOPEN','EXACT_METADATA_ONLY_PURPOSE');require(auth['epoch']==41 and auth['source_checkpoint']==SOURCE and auth['root_metadata_key_catalog_once_authorized']is True and auth['no_E41_materializer_or_model_retry']is True and auth['policy_sha256']==policy_ref['sha256']and auth['source_seal_sha256']==seal_ref['sha256'],'EXACT_ROOT_ONCE_METADATA_AUTHORIZATION')
  for r in seal['source_files']:read_ref(r)
  sr=next(r for r in seal['source_files']if Path(r['path']).name=='metadata_key_catalog.py');require(sha(Path(__file__).read_bytes())==sr['sha256'],'EXECUTED_SOURCE_DIFFERS_FROM_SEAL');affinity=sorted(os.sched_getaffinity(0));require(affinity==[0,1],'TWO_CPU_AFFINITY_REQUIRED');out=Path(out);scope=Path(policy['external_scope']);require(out.is_absolute()and out.resolve()==out and out.is_relative_to(scope)and not out.is_relative_to(scope/'project')and not out.exists(),'NEW_SEPARATE_METADATA_OUTPUT_REQUIRED');out.mkdir(mode=0o700);put(out/'METADATA_KEY_CATALOG_ATTEMPT.json',{'schema_version':1,'epoch':41,'kind':KIND,'purpose':policy['purpose'],'authorization':authorization_ref,'policy':policy_ref,'source_seal':seal_ref,'CPU_affinity':affinity,'automatic_retry':False,'materializer_calls':0,'model_tokenizer_native_calls':0,'semantic_gold_values_decoded':0});v={'schema_version':1,'epoch':41,'kind':KIND,'status':'METADATA_INVENTORY_FAILED_NO_RETRY','purpose':policy['purpose'],'source_checkpoint':SOURCE,'policy':policy_ref,'source_seal':seal_ref,'materializer_calls':0,'model_tokenizer_native_calls':0,'semantic_gold_values_decoded':0,'string_value_decodes':0,'old_Legal96_text_decodes':0,'errors':[]}
  try:
   b=Path(archive).read_bytes();a=policy['archive'];require(len(b)==a['bytes']and sha(b)==a['sha256']and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==a['git_blob_sha1'],'EXACT_ARCHIVE_IDENTITY')
   with zipfile.ZipFile(archive)as z:
    matches=[i for i in z.infolist()if Path(i.filename).name=='test.json'and not i.is_dir()];require(len(matches)==1,'SAFE_SINGLE_TEST_MEMBER');i=matches[0];require(not Path(i.filename).is_absolute()and '..'not in Path(i.filename).parts and i.file_size<=33554432,'SAFE_SINGLE_TEST_MEMBER');member=z.read(i);m=policy['member'];require(i.filename==m['path']and len(member)==m['bytes']and sha(member)==m['sha256'],'EXACT_MEMBER_IDENTITY');v['archive_source']=a;v['member_source']=m
   v['catalog']=catalog_only(member);v['status']='OFFICIAL_STRUCTURAL_KEY_CATALOG_RECORDED_FUTURE_POLICY_ONLY'
  except Exception as e:v['errors'].append(safe_error(e))
  put(out/'METADATA_KEY_CATALOG_REPORT.json',v);return v
 finally:signal.setitimer(signal.ITIMER_REAL,0.);signal.signal(signal.SIGALRM,old)

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['archive','out','policy','seal','authorization']:p.add_argument('--'+n,required=True)
 for n in ['policy','seal','authorization']:p.add_argument('--expected-'+n+'-sha256',required=True)
 a=p.parse_args();refs={}
 for n in ['policy','seal','authorization']:
  r=ref(getattr(a,n));require(r['sha256']==getattr(a,'expected_'+n+'_sha256'),'EXACT_COMMAND_SOURCE_REFERENCE');refs[n]=r
 v=inventory(a.archive,a.out,refs['policy'],refs['seal'],refs['authorization']);print(json.dumps({'status':v['status'],'semantic_gold_values_decoded':v['semantic_gold_values_decoded'],'string_value_decodes':v['string_value_decodes'],'materializer_calls':v['materializer_calls'],'model_tokenizer_native_calls':v['model_tokenizer_native_calls'],'errors':v['errors']}))
