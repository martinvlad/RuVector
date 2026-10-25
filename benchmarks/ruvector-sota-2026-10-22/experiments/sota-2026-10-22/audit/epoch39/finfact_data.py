"""Label-blind Fin-Fact custody and independent late gold reader; stdlib only.

Actual archive access requires ROOT's locally sealed source approval. Ordinary
json.load on the archive is never used. Feature readers cannot access raw gold.
"""
import argparse,hashlib,importlib.util,json,os,struct,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
HERE=Path(__file__).resolve().parent

def module(name,filename):
 s=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
J=module('e39_json_span_custody','finfact_json_spans.py');G=module('e39_input_stop_guard','finfact_guard.py')
KIND='REAL_FINFACT_DEV_TRANSFER_PILOT';SOURCE='74dbbcb10508ced7e0edf53a0c736f14c19a19a1'
ARCHIVE_SHA='5e36d32a0e0149f5d86b1f81ab6fd85144136cb7975374364060f8fcf43629fd';ARCHIVE_BYTES=29972446
ARMS=['b354_source_order','b354_native','b354_lexical','xxlarge_source_order'];MAGIC=b'RUVECTOR_FINFACT_GOLD_RAW_V1\x00'

def require(v,message):
 if not v:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def read_bytes(path,expected_sha=None):
 p=Path(path);require(p.is_absolute()and p==p.resolve()and not any(q.is_symlink()for q in(p,*p.parents))and p.is_file(),'REGULAR_ABSOLUTE_NONSYMLINK_FILE_REQUIRED');b=p.read_bytes();require(expected_sha is None or sha(b)==expected_sha,'FILE_SHA_MISMATCH');return b
def metadata(path,expected_sha=None):return json.loads(read_bytes(path,expected_sha),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in()).throw(ValueError('NONFINITE_JSON')))
def unique(pairs):
 d={}
 for k,v in pairs:require(k not in d,'DUPLICATE_JSON_KEY');d[k]=v
 return d
def ref(path):
 p=Path(path);b=read_bytes(p);return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def put_bytes(path,b):
 p=Path(path);require(p.is_absolute()and p.parent==p.parent.resolve()and not p.exists(),'EXCLUSIVE_OUTPUT_REQUIRED');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 directory=os.open(p.parent,os.O_DIRECTORY);os.fsync(directory);os.close(directory)
def put(path,v):put_bytes(path,(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
def canonical_url(value):
 require(type(value)is str,'URL_TYPE');value=value.strip();require(value and not any(c.isspace()for c in value),'URL_EMPTY_OR_WHITESPACE');p=urlsplit(value);require(p.scheme.lower()in ['http','https']and p.hostname and p.username is None and p.password is None,'URL_IDENTITY_REQUIRED')
 # Exact prospective rule: lowercase scheme/hostname only, preserve path/query.
 netloc=p.netloc
 if netloc.startswith('['):
  close=netloc.find(']');require(close>0,'URL_IPV6_HOST');host=netloc[:close+1].lower();suffix=netloc[close+1:];require(not suffix or suffix.startswith(':'),'URL_AUTHORITY_SUFFIX')
 else:
  host,separator,port=netloc.rpartition(':')
  if separator:host=host.lower();suffix=separator+port
  else:host=netloc.lower();suffix=''
 # Validate a declared port without reformatting its original text.
 unused_validated_port=p.port
 fragment_free=value.split('#',1)[0];authority_start=fragment_free.find('://')+3;require(authority_start>=3,'URL_AUTHORITY_DELIMITER');tail_start=len(fragment_free)
 for delimiter in ['/', '?']:
  found=fragment_free.find(delimiter,authority_start)
  if found>=0:tail_start=min(tail_start,found)
 return p.scheme.lower()+'://'+host+suffix+fragment_free[tail_start:]
def evidence_spans(index,value):
 require(value[2]=='array','EVIDENCE_ARRAY');out=[]
 for item in index.items(value):
  require(item[2]=='object','EVIDENCE_OBJECT');fields=index.members(item);s=fields.get('sentence');require(s is not None and s[2]=='string','EVIDENCE_SENTENCE_STRING');out.append(s)
 return out

def prepare_bytes(data,allow_actual=False):
 """Fixture-callable selection/custody core; never decodes label values."""
 digest=sha(data)
 require(allow_actual or digest!=ARCHIVE_SHA,'ACTUAL_ARCHIVE_REQUIRES_ROOT_SEAL')
 index=J.SpanJSON(data);groups={};total=0;ineligible=0
 for ordinal,record in index.root_records():
  total+=1;fields=index.members(record)
  try:
   u,c,e=fields['url'],fields['claim'],fields['evidence'];require(u[2]==c[2]=='string'and index.string_nonempty(c),'CLAIM_STRUCTURE');url=canonical_url(index.decode_string(u,'url'));sentences=evidence_spans(index,e);require(sentences and any(index.string_nonempty(x)for x in sentences),'NONEMPTY_EVIDENCE')
  except (KeyError,ValueError,UnicodeError):ineligible+=1;continue
  gid=sha(('FinFact-url|'+url).encode())
  if gid not in groups:groups[gid]={'ordinal':ordinal,'record':record,'claim':c,'sentences':sentences,'label':fields.get('label'),'group_id':gid}
 ordered=sorted(groups,key=lambda gid:sha(('ruvector-finfact-e39-v1|'+digest+'|'+gid).encode()));require(len(ordered)>=12,'FEWER_THAN_TWELVE_ELIGIBLE_URL_GROUPS');selected=[groups[x]for x in ordered[:12]]
 ids=[f'finfact:b3038781:ordinal:{r["ordinal"]}'for r in selected];records=[];identities=[];flags=[];label_spans=[]
 for caseid,r in zip(ids,selected):
  identity={'id':caseid,'record_ordinal':r['ordinal'],'url_group_sha256':r['group_id'],'source_record_span':[r['record'][0],r['record'][1]],'source_record_sha256':sha(index.raw(r['record']))}
  try:
   claim=index.decode_string(r['claim'],'selected_claim');sentences=[index.decode_string(x,'selected_evidence')for x in r['sentences']];payload={'claim':claim,'evidence_sentences':sentences};input_hash=sha(canonical(payload).encode());identity['input_sha256']=input_hash;guard=G.guard_features(claim,sentences);identity['input_guard']=guard
   records.append({'id':caseid,'record_ordinal':r['ordinal'],'document_id':'finfact-url:'+r['group_id'],'url_group_sha256':r['group_id'],'hypothesis_id':caseid+'::claim','input_sha256':input_hash,'claim':claim,'evidence':[{'unit_id':i,'sentence':s}for i,s in enumerate(sentences)]})
   if not guard['passed']:flags.append({'id':caseid,'flags':guard['flags']})
   label=r['label'];require(label is not None and label[2]=='string','SELECTED_LABEL_TOKEN_NOT_STRING');label_spans.append(label)
  except (ValueError,UnicodeError)as error:identity['input_guard']={'passed':False,'flags':[str(error)]};flags.append({'id':caseid,'flags':[str(error)]})
  identities.append(identity)
 require(index.gold_values_decoded==0,'GOLD_DECODE_BEFORE_FENCE')
 stats={'archive_records':total,'eligible_unique_URL_groups':len(groups),'structurally_ineligible_rows':ineligible,'selected_ids':ids,'selected_count':12,'decoded_value_counts':index.decoded,'semantic_gold_values_decoded':0,'no_label_stratification_or_replacement':True}
 if flags:return {'status':'STOP_INPUT_ADMISSION_NO_REPLACEMENT','identities':identities,'input_stops':flags,'statistics':stats,'features':None,'vault':None,'raw_gold_tokens_copied':0}
 require(len(records)==len(label_spans)==12,'COMPLETE_SELECTED_TWELVE_REQUIRED')
 raw_tokens=[index.raw(span)for span in label_spans]
 features={'schema_version':1,'epoch':39,'kind':KIND,'role':'dev','source_archive_sha256':digest,'records':records}
 header=canonical({'schema_version':1,'epoch':39,'kind':KIND,'role':'dev','source_archive_sha256':digest,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED'}).encode()
 vault=MAGIC+struct.pack('<I',len(header))+header+b''.join(struct.pack('<I',len(x))+x for x in raw_tokens)
 return {'status':'READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT','identities':identities,'input_stops':[],'statistics':stats,'features':features,'vault':vault,'raw_gold_tokens_copied':12}

def verify_local_approval(policy_path,seal_path,approval_path,approval_sha):
 policy=metadata(policy_path);seal=metadata(seal_path);approval=metadata(approval_path,approval_sha)
 require(policy['epoch']==39 and policy['kind']==KIND and policy['DEV_cases']==12 and policy['roles']=={'train':[],'calibration':[],'confirmation':[]},'WRONG_FROZEN_DATA_POLICY')
 require(seal['epoch']==39 and seal['kind']==KIND and seal['policy_sha256']==sha(read_bytes(policy_path)),'PREDATA_SEAL_POLICY_MISMATCH')
 by_name={Path(r['path']).name:r for r in seal['source_files']}
 require(all(name in by_name for name in ['finfact_data.py','finfact_json_spans.py','finfact_guard.py']),'COMPLETE_CUSTODIAN_SOURCE_SEAL_REQUIRED')
 for name in ['finfact_data.py','finfact_json_spans.py','finfact_guard.py']:require(sha(read_bytes(HERE/name))==by_name[name]['sha256'],'EXECUTED_CUSTODIAN_DIFFERS_FROM_SEAL')
 for row in seal['source_files']:
  body=read_bytes(row['path'],row['sha256']);require(len(body)==row['bytes'],'PREDATA_SOURCE_SIZE_MISMATCH')
 require(approval['epoch']==39 and approval['kind']==KIND and approval['source_checkpoint']==SOURCE and approval['predataseal_sha256']==sha(read_bytes(seal_path))and approval['policy_sha256']==sha(read_bytes(policy_path))and approval['approved']is True and approval['only_label_blind_custodian_parser_authorized']is True,'ROOT_LOCAL_PREDATA_APPROVAL_REQUIRED')
 return policy,seal,approval

def materialize(archive_path,out_dir,policy_path,seal_path,approval_path,approval_sha):
 verify_local_approval(policy_path,seal_path,approval_path,approval_sha);out=Path(out_dir);scope=Path('/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508');require(out.is_relative_to(scope)and not out.is_relative_to(scope/'project'),'FEATURE_AND_VAULT_MUST_STAY_OUTSIDE_PUBLIC_PROJECT');require(out.is_absolute()and out==out.resolve()and not out.exists(),'NEW_PRIVATE_OUTPUT_DIRECTORY_REQUIRED');out.mkdir(mode=0o700)
 put(out/'MATERIALIZER_ATTEMPT.json',{'schema_version':1,'epoch':39,'kind':KIND,'phase':'dev','one_attempt':True,'policy_sha256':sha(read_bytes(policy_path)),'predataseal_sha256':sha(read_bytes(seal_path)),'semantic_gold_decodes':0,'NNI_tokenizer_native_calls':0})
 report={'schema_version':1,'epoch':39,'kind':KIND,'phase':'dev','status':'DATA_ADMISSION_FAILED','source_archive_sha256':ARCHIVE_SHA,'selected_ids':[],'selected_count':None,'raw_gold_tokens_copied':0,'semantic_gold_values_decoded':0,'NNI_tokenizer_native_calls':0,'used_confirmation_identities':[],'errors':[]}
 try:
  data=read_bytes(archive_path,ARCHIVE_SHA);require(len(data)==ARCHIVE_BYTES,'ARCHIVE_BYTE_COUNT_MISMATCH');result=prepare_bytes(data,allow_actual=True);report.update(status=result['status'],selected_ids=result['statistics']['selected_ids'],selected_count=12,statistics=result['statistics'],raw_gold_tokens_copied=result['raw_gold_tokens_copied'],input_stops=result['input_stops'])
  put(out/'selected_identities.json',{'schema_version':1,'epoch':39,'kind':KIND,'phase':'dev','source_archive_sha256':ARCHIVE_SHA,'selected_ids':report['selected_ids'],'records':result['identities'],'all_selected_become_DEV_forever':True,'used_confirmation_identities':[]})
  report['identity_manifest']=ref(out/'selected_identities.json')
  if result['status']=='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT':
   put(out/'dev_features.json',result['features']);put_bytes(out/'dev_oracle.bin',result['vault']);report['external_data_assets']=[dict(ref(out/'dev_features.json'),role='dev_features'),dict(ref(out/'dev_oracle.bin'),role='dev_oracle')]
 except (ValueError,KeyError,UnicodeError)as error:report['errors'].append(type(error).__name__+':'+str(error))
 put(out/'materialization_report.json',report);return report

def load_private_features(path,expected_sha256,expected_ids):
 bank=metadata(path,expected_sha256);require(set(bank)=={'schema_version','epoch','kind','role','source_archive_sha256','records'}and bank['schema_version']==1 and bank['epoch']==39 and bank['kind']==KIND and bank['role']=='dev','PRIVATE_FEATURE_BANK_SCHEMA');records=bank['records'];require(type(records)is list and len(records)==12 and [r['id']for r in records]==list(expected_ids)and len(set(expected_ids))==12,'EXACT_TWELVE_DEV_IDENTITIES_REQUIRED')
 for row in records:
  require(set(row)=={'id','record_ordinal','document_id','url_group_sha256','hypothesis_id','input_sha256','claim','evidence'},'FORBIDDEN_FEATURE_FIELD')
  require(row['id']==f'finfact:b3038781:ordinal:{row["record_ordinal"]}'and type(row['record_ordinal'])is int and row['record_ordinal']>=0 and row['hypothesis_id']==row['id']+'::claim'and row['document_id']=='finfact-url:'+row['url_group_sha256'],'FEATURE_IDENTITY_MISMATCH')
  e=row['evidence'];require(type(e)is list and all(type(x)is dict and set(x)=={'unit_id','sentence'}and type(x['unit_id'])is int and x['unit_id']==i and type(x['sentence'])is str for i,x in enumerate(e)),'EVIDENCE_UNIT_SCHEMA')
  sentences=[x['sentence']for x in e];require(sha(canonical({'claim':row['claim'],'evidence_sentences':sentences}).encode())==row['input_sha256'],'INPUT_HASH_MISMATCH');check=G.guard_features(row['claim'],sentences);require(check['passed'],'FROZEN_INPUT_STOP:'+','.join(check['flags']))
 return records

def assert_packed_input(claim,premise):
 report=G.guard_premise(claim,premise);require(report['passed'],'FROZEN_PACKED_INPUT_STOP:'+','.join(report['flags']));return report

def check_physical_gold_fence(closure,expected_ids):
 ids=[i+'::'+a for i in expected_ids for a in ARMS]
 require(closure['physical_readouts_completed']==48 and type(closure['physical_readouts_completed'])is int and len(closure['required_readout_ids'])==len(closure['completed_readout_ids'])==48 and set(closure['required_readout_ids'])==set(closure['completed_readout_ids'])==set(ids),'ALL_FORTY_EIGHT_REAL_READOUTS_REQUIRED')
 require(closure['model_profiles_disposed']==['xxlarge','b354']and closure['native_child_closed']is True and closure['all_forecasts_closed_before_gold']is True,'MODEL_NATIVE_CLOSURE_REQUIRED')
 pin=closure['physical_closure_evidence'];b=read_bytes(pin['path'],pin['sha256']);require(len(b)==pin['bytes'],'PHYSICAL_PROOF_SIZE_MISMATCH');proof=json.loads(b,object_pairs_hook=unique)
 require(proof['schema_version']==1 and proof['epoch']==39 and proof['kind']==KIND and proof['phase']=='dev'and proof['source_plan_sha256']==closure['source_plan_sha256']and proof['physical_closure_passed']is True and proof['physical_supervisor_closed']is True and proof['unknown_physical_ownership']is False and proof['owned_worker_group_members']==[],'INDEPENDENT_PHYSICAL_CLOSURE_PROOF_REQUIRED')
 require(proof['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()and proof['pid_namespace_inode']==os.stat('/proc/self/ns/pid').st_ino,'PHYSICAL_PROOF_BOOT_NAMESPACE_MISMATCH')
 owner=proof['supervisor_identity'];require(type(owner)is dict and all(type(owner[k])is int and owner[k]>0 for k in ['pid','startticks','pgid','sid']),'ACTUAL_SUPERVISOR_IDENTITY_REQUIRED')
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   f=(p/'stat').read_text().rsplit(')',1)[1].split();pid=int(p.name);ticks=int(f[19]);state=f[0];group,session=int(f[2]),int(f[3])
  except (OSError,ValueError,IndexError):continue
  if pid==owner['pid']and ticks==owner['startticks']:require(state in ['Z','X'],'SUPERVISOR_STILL_LIVE_BEFORE_GOLD')
  # The independent observer already binds the owned worker identity/session;
  # a known surviving member in the supervisor session is an additional stop.
  if group==owner['pgid']or session==owner['sid']:require(state in ['Z','X'],'OWNED_SESSION_STILL_LIVE_BEFORE_GOLD')
 return proof

def read_selected_gold(vault_path,expected_sha256,expected_ids,closure):
 require(len(expected_ids)==len(set(expected_ids))==12,'TWELVE_SELECTED_GOLD_IDS_REQUIRED');proof=check_physical_gold_fence(closure,expected_ids)
 marker=Path(str(vault_path)+'.DECODE_ATTEMPT.json');put(marker,{'schema_version':1,'epoch':39,'kind':KIND,'vault_sha256':expected_sha256,'after_all48_and_physical_closure':True,'selected_ids':list(expected_ids),'automatic_retry':False})
 b=read_bytes(vault_path,expected_sha256);require(b.startswith(MAGIC),'OPAQUE_VAULT_MAGIC');cursor=len(MAGIC)
 def sized():
  nonlocal cursor
  require(cursor+4<=len(b),'VAULT_LENGTH_HEADER');n=struct.unpack_from('<I',b,cursor)[0];cursor+=4;require(cursor+n<=len(b),'VAULT_TRUNCATED');out=b[cursor:cursor+n];cursor+=n;return out
 header=json.loads(sized());require(header['schema_version']==1 and header['epoch']==39 and header['kind']==KIND and header['role']=='dev'and header['ids']==list(expected_ids)and header['label_encoding']=='OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','GOLD_VAULT_HEADER_MISMATCH');labels={};token_hashes={}
 for caseid in expected_ids:
  token=sized();value=json.loads(token);require(type(value)is str and value in ['true','false','neutral'],'UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP');labels[caseid]=value;token_hashes[caseid]=sha(token)
 require(cursor==len(b),'EXTRA_GOLD_VAULT_DATA')
 receipt={'schema_version':1,'epoch':39,'kind':KIND,'role':'dev','selected_ids':list(expected_ids),'vault_sha256':expected_sha256,'source_archive_sha256':header['source_archive_sha256'],'physical_raw_tokens_copied_before_measurement':12,'semantic_labels_decoded':12,'label_reader_calls':1,'original_archive_gold_traversals_by_reader':0,'label_token_sha256s':token_hashes,'physical_closure_evidence':closure['physical_closure_evidence'],'closure':closure,'model_tokenizer_native_calls_by_reader':0,'used_confirmation_identities':[]}
 return labels,receipt

if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);m=sub.add_parser('materialize')
 for n in ['archive','out','policy','seal','approval','expected-approval-sha']:m.add_argument('--'+n,required=True)
 a=p.parse_args();r=materialize(a.archive,a.out,a.policy,a.seal,a.approval,a.expected_approval_sha);print(json.dumps({'status':r['status'],'selected_count':r['selected_count'],'source_case_text_printed':False,'semantic_gold_values_decoded':0,'raw_gold_tokens_copied':r['raw_gold_tokens_copied'],'errors':r['errors']}))
