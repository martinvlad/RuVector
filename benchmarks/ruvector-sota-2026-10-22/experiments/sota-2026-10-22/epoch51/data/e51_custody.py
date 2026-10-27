"""E51 source-frozen, label-blind DATA and strictly late one-time Gold custody.

No model/tokenizer/native/network imports or calls. Dataset selection is frozen
in IDENTITY_POLICY.v3.json before source payload access. Only selected source
texts decode during DATA; raw JSON choice tokens are copied opaquely.
"""
import argparse,base64,hashlib,importlib.util,io,json,os,re,stat,time,unicodedata,zipfile
from pathlib import Path
EPOCH=51
KIND='REAL_CONTRACTNLI_CONTRACT_BERT_WHOLE_SOURCE_PILOT'
SOURCE='0e1f4181df1f738fe104f294dbf5267badfed4a7'
SOURCE_CHECKPOINT_RESOLVED=True
WORKDIR=Path('/dev/shm/ruvector-sota-2026-10-22/epoch51-0e1f4181df1f')
POLICY_SHA='122fae7af00439a7b23dc17a1d81a7ba3f8a646595a83e05878a803614a7a757'
ARCHIVE_SHA='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
ARCHIVE_BYTES=65362913
ARCHIVE_GIT='757fd1dafd29a997fba00c60c6d40b2930a36159'
MEMBER_SHA='310af7d661d2ab50ee3700169cef524c75f39fb296bbf5a515c229eb0f42e68e'
MEMBER_BYTES=1183107
CODEC_SHA='9c63102a01576c230da94695f593fd7bd4fe2d0b20672b74e8a7f62aba426fc4'
CATALOG_SHA='46b8ab06ec6030df94797307b3ad1da7b5a5a60e4d4479bc11af1b718467bc6a'
DEV_DOCS=(7,28,406,73)
CONF_DOCS=(18,225,293,361)
HYPOTHESES=('nda-1','nda-10','nda-16')
CATALOG_KEYS=('nda-1','nda-10','nda-11','nda-12','nda-13','nda-15','nda-16','nda-17','nda-18','nda-19','nda-2','nda-20','nda-3','nda-4','nda-5','nda-7','nda-8')
ARMS=('native','lexical','source_order','whole_source')
LABELS=('Entailment','Contradiction','NotMentioned')
MAX_DOC_BYTES=1048576
MAX_CLAIM_BYTES=65536
MAX_BANK_BYTES=8388608
NUMBER=re.compile(rb'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
WS=b' \t\r\n'
def require(v,code):
 if not v:raise ValueError(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def unique(rows):
 out={}
 for k,v in rows:require(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
 return out
def normalized(text):return ' '.join(text.casefold().split())
def filename_key(text):return ' '.join(unicodedata.normalize('NFKC',text.replace('\\','/').rsplit('/',1)[-1]).casefold().split())
def resolve_path(name,project):
 p=Path(name);p=p if p.is_absolute()else Path(project)/p
 require(p.absolute()==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents)),'CANONICAL_NO_SYMLINK_PATH');return p
def read_ref(ref,project):
 require(type(ref)is dict and set(ref)=={'path','bytes','sha256'} and type(ref['path'])is str and type(ref['bytes'])is int and ref['bytes']>=0 and type(ref['sha256'])is str and len(ref['sha256'])==64,'EXACT_REFERENCE_REQUIRED')
 p=resolve_path(ref['path'],project);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb')as f:
  before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode),'REGULAR_FILE_REQUIRED');b=f.read();after=os.fstat(f.fileno())
 require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)and len(b)==ref['bytes']and sha(b)==ref['sha256'],'STABLE_FILE_IDENTITY_MISMATCH');return b
def load_ref(ref,project):return json.loads(read_ref(ref,project),object_pairs_hook=unique)
def ref(path):
 p=Path(path);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def put_bytes(path,b):
 p=Path(path);require(p.absolute()==p.resolve()and not p.is_symlink(),'CANONICAL_OUTPUT');p.parent.mkdir(parents=True,exist_ok=True);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);return ref(p)
def put(path,obj):return put_bytes(path,json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n')
def phase_ids(phase):
 require(phase in('dev','confirmation'),'FROZEN_PHASE_REQUIRED');split='dev'if phase=='dev'else'test';return [f'contractnli:eced6528:{split}:{d}:{h}'for d in (DEV_DOCS if phase=='dev'else CONF_DOCS)for h in HYPOTHESES]
def phase_stem(phase):return 'DEV'if phase=='dev'else'CONF'
def phase_report_name(phase):return 'DATA_ADMISSION.json'if phase=='dev'else'CONFIRMATION_DATA_ADMISSION.json'
def owner_guard(owner_ref,project):
 o=load_ref(owner_ref,project);require(owner_ref['path']==str(WORKDIR/'owner.json')and owner_ref['bytes']==699 and owner_ref['sha256']=='b8d2ac6cb7d59abd21f5873626f61f90167701673bd043716892d00eb65c9889','FROZEN_OWNER_REF')
 require(o['epoch']==51 and o['generation']==16 and o['pid']==162664 and o['startticks']==39101510 and o['CPU_affinity']==[0,1]and time.time()<o['expires_unix']and not(WORKDIR/'release.request').exists()and not(WORKDIR/'released.json').exists(),'CURRENT_UNEXPIRED_HELD_OWNER')
 p=Path('/proc')/str(o['pid']);v=(p/'stat').read_text().rsplit(')',1)[1].split();require(v[0]not in('Z','X')and int(v[19])==o['startticks'],'SAME_LIVE_GUARDIAN')
 require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==o['kernel_boot_id']and os.readlink(p/'ns/pid')==o['PID_namespace'],'SAME_BOOT_NAMESPACE')
 a=os.stat(p/'fd/3');b=os.stat(o['lock']);require((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==(33,13626),'ORIGINAL_GLOBAL_LOCK_INODE');fi=(p/'fdinfo/3').read_text();require('FLOCK'in fi and '162664'in fi and ':13626'in fi,'GUARDIAN_KERNEL_FLOCK');require(set(os.sched_getaffinity(0))<={0,1},'CUSTODIAN_TWO_CORE_AFFINITY');return o

class SpanJSON:
 def __init__(self,data):
  if type(data)is not bytes:raise ValueError('BYTES_REQUIRED')
  self.data=data;self.decoded={'field_name':0,'metadata':0,'selected_document':0,'selected_hypothesis':0,'legacy_dev_text':0};self.gold_values_decoded=0
 def ws(self,i):
  while i<len(self.data)and self.data[i]in WS:i+=1
  return i
 def string_end(self,i):
  if i>=len(self.data)or self.data[i]!=34:raise ValueError('STRING_REQUIRED')
  j=i+1
  while j<len(self.data):
   x=self.data[j]
   if x==34:return j+1
   if x<32:raise ValueError('UNESCAPED_CONTROL')
   if x==92:
    j+=1
    if j>=len(self.data):raise ValueError('INCOMPLETE_ESCAPE')
    if self.data[j]==117:
     if j+4>=len(self.data)or any(c not in b'0123456789abcdefABCDEF'for c in self.data[j+1:j+5]):raise ValueError('UNICODE_ESCAPE')
     j+=4
    elif self.data[j]not in b'"\\/bfnrt':raise ValueError('JSON_ESCAPE')
   j+=1
  raise ValueError('UNTERMINATED_STRING')
 def value(self,i,depth=0):
  if depth>64:raise ValueError('JSON_DEPTH')
  i=self.ws(i)
  if i>=len(self.data):raise ValueError('MISSING_VALUE')
  c=self.data[i]
  if c==34:return(i,self.string_end(i),'string')
  if c in(123,91):
   close=125 if c==123 else 93;j=self.ws(i+1)
   if j<len(self.data)and self.data[j]==close:return(i,j+1,'object'if c==123 else'array')
   while True:
    if c==123:
     j=self.string_end(j);j=self.ws(j)
     if j>=len(self.data)or self.data[j]!=58:raise ValueError('MISSING_COLON')
     j+=1
    _,j,_=self.value(j,depth+1);j=self.ws(j)
    if j>=len(self.data):raise ValueError('UNFINISHED_CONTAINER')
    if self.data[j]==close:return(i,j+1,'object'if c==123 else'array')
    if self.data[j]!=44:raise ValueError('MISSING_COMMA')
    j=self.ws(j+1)
  for literal,kind in [(b'true','bool'),(b'false','bool'),(b'null','null')]:
   if self.data.startswith(literal,i):return(i,i+len(literal),kind)
  m=NUMBER.match(self.data,i)
  if m:return(i,m.end(),'number')
  raise ValueError('INVALID_JSON_VALUE')
 def decode_string(self,span,field):
  if field not in self.decoded:raise ValueError('FORBIDDEN_VALUE_DECODER')
  a,b,kind=span
  if kind!='string':raise ValueError('STRING_DECODER_TYPE')
  value=json.loads(self.data[a:b]);self.decoded[field]+=1
  if type(value)is not str:raise ValueError('STRING_DECODER_RESULT')
  return value
 def members(self,span):
  a,b,kind=span
  if kind!='object':raise ValueError('OBJECT_REQUIRED')
  i=self.ws(a+1);out={}
  if i==b-1:return out
  while i<b-1:
   end=self.string_end(i);key=self.decode_string((i,end,'string'),'field_name');i=self.ws(end)
   if i>=b or self.data[i]!=58:raise ValueError('OBJECT_COLON')
   value=self.value(i+1);i=self.ws(value[1])
   if key in out:raise ValueError('DUPLICATE_JSON_KEY')
   out[key]=value
   if i==b-1:return out
   if self.data[i]!=44:raise ValueError('OBJECT_COMMA')
   i=self.ws(i+1)
  raise ValueError('OBJECT_TERMINATION')
 def items(self,span):
  a,b,kind=span
  if kind!='array':raise ValueError('ARRAY_REQUIRED')
  i=self.ws(a+1)
  if i==b-1:return
  while i<b-1:
   value=self.value(i);yield value;i=self.ws(value[1])
   if i==b-1:return
   if self.data[i]!=44:raise ValueError('ARRAY_COMMA')
   i=self.ws(i+1)
  raise ValueError('ARRAY_TERMINATION')
 def root_records(self):
  root=self.value(0)
  if root[2]!='array'or self.ws(root[1])!=len(self.data):raise ValueError('EXACT_ROOT_ARRAY_REQUIRED')
  for i,span in enumerate(self.items(root)):
   if span[2]!='object':raise ValueError('RECORD_OBJECT_REQUIRED')
   yield i,span
 def string_nonempty(self,span):
  """Compute a whitespace-only flag without constructing/decoding text value."""
  a,b,kind=span
  if kind!='string':return False
  i=a+1
  while i<b-1:
   c=self.data[i]
   if c==92:
    i+=1;x=self.data[i]
    if x==117:ch=chr(int(self.data[i+1:i+5],16));i+=5
    else:ch={34:'"',92:'\\',47:'/',98:'\b',102:'\f',110:'\n',114:'\r',116:'\t'}[x];i+=1
   elif c<128:ch=chr(c);i+=1
   else:
    n=2 if c&224==192 else 3 if c&240==224 else 4 if c&248==240 else 0
    if not n:raise ValueError('INVALID_UTF8')
    ch=self.data[i:i+n].decode('utf-8');i+=n
   if not ch.isspace():return True
  return False
 def raw(self,span):return self.data[span[0]:span[1]]

def source_catalog():
 p=Path(__file__).resolve().parent/'source_catalog.py';b=p.read_bytes();require(len(b)==3100 and sha(b)==CATALOG_SHA,'EXACT_SOURCE_CATALOG')
 spec=importlib.util.spec_from_file_location('e51_source_catalog',p);m=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),m.__dict__);return m

def verify_policy(policy,policy_ref):
 require(policy_ref['sha256']==POLICY_SHA and policy['schema_version']==1 and policy['epoch']==51 and policy['kind']==KIND and policy['source_checkpoint']==SOURCE and policy['source_checkpoint_resolved']is True,'EXACT_METADATA_POLICY')
 require(tuple(policy['selected_dev_document_ids'])==DEV_DOCS and tuple(policy['conditional_confirmation_document_ids'])==CONF_DOCS and tuple(policy['hypothesis_ids'])==HYPOTHESES,'FROZEN_IDENTITIES')
 require(policy['data_roles']=={'train':[],'dev':phase_ids('dev'),'calibration':[],'confirmation':phase_ids('confirmation')},'FROZEN_FOUR_ROLES')
 require(policy['confirmation_lineage_status']=='UNQUALIFIED_HOLD'and policy['confirmation_currently_admitted']is False,'CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD')
 pool=policy['all13_ranked_DEV_metadata'];require(len(pool)==13 and len({x['document_id']for x in pool})==13 and all(x['source_split']=='dev'and not x['metadata_exclusion_flags']and not x['exclusion_reasons']and x['project_unused_unassigned_metadata_eligible']is True for x in pool),'EXACT_13_UNUSED_METADATA_POOL')
 seed=policy['selection_seed'];require(seed=='e51-contract-bert-context-v1','EXACT_PREDECLARED_SEED')
 key=lambda x:(sha((seed+'\n'+x['normalized_document_sha256']+'\n'+str(x['document_id'])).encode()),x['document_id'])
 ranked=sorted(pool,key=key);require(pool==ranked and [x['document_id']for x in ranked[:4]]==list(DEV_DOCS)and all(x['ranking_sha256']==key(x)[0]for x in ranked),'EXACT_LABEL_BLIND_HASH_RANKING')
 selected=policy['selected_dev_documents']+policy['conditional_confirmation_documents'];require(len(selected)==8 and len({x['normalized_document_sha256']for x in selected})==8 and len({x['document_filename_key_sha256']for x in selected})==8,'EIGHT_DISTINCT_ROLE_DOCUMENT_HASHES_AND_NAMES')
 require(policy['selected_dev_documents']==ranked[:4]and [x['document_id']for x in policy['conditional_confirmation_documents']]==list(CONF_DOCS)and all(x['source_split']=='test'and not x['exclusion_reasons']for x in policy['conditional_confirmation_documents']),'EXACT_DEV_AND_TEST_HOLD_METADATA')
 require(policy['archive']=={'bytes':ARCHIVE_BYTES,'sha256':ARCHIVE_SHA,'git_blob_sha1':ARCHIVE_GIT}and policy['member']=={'path':'contract-nli/dev.json','bytes':MEMBER_BYTES,'sha256':MEMBER_SHA},'FROZEN_ARCHIVE_AND_DEV_MEMBER')
 budget=policy['phase_budget'];require(budget['DEV_cases']==12 and budget['arms']==list(ARMS)and budget['DEV_final_forecasts']==48 and budget['DEV_maximum_physical_model_forwards']==228 and budget['whole_source_maximum_windows_per_case']==16 and budget['pair_token_cap']==512 and budget['native_CONFIRMATION_slots_admitted']==0 and budget['confirmation_slot_status']=='CLOSED_HOLD','EXACT_FOUR_ARM_DEV_ONLY_BUDGET')
 return policy

def verify_source_binding(admission,project,mode):
 require(SOURCE_CHECKPOINT_RESOLVED is True and re.fullmatch('[0-9a-f]{40}',SOURCE) is not None,'ACTUAL_RECOVERY_SOURCE_CHECKPOINT_UNRESOLVED_NO_EXECUTION')
 require(admission['schema_version']==1 and admission['epoch']==51 and admission['kind']==KIND and admission['mode']==mode,'EXACT_ROOT_ADMISSION_KIND')
 owner_guard(admission['owner_ref'],project)
 plan=load_ref(admission['plan_ref'],project);freeze=load_ref(admission['source_freeze_ref'],project)
 require(plan['epoch']==51 and plan['kind']==KIND and plan['source_checkpoint']==SOURCE,'EXACT_FROZEN_PLAN')
 require(plan['data_roles']=={'train':[],'dev':phase_ids('dev'),'calibration':[],'confirmation':phase_ids('confirmation')},'PLAN_FROZEN_DATA_ROLES')
 require(plan['arms']==list(ARMS)and plan['confirmation_lineage_status']=='UNQUALIFIED_HOLD'and plan['phase_limits']['dev']['forecasts']==48 and plan['phase_limits']['dev']['maximum_model_forward_calls']==228,'PLAN_DEV_ONLY_FOUR_ARM_FORWARD_BUDGET')
 files=freeze['files'];require(type(files)is list and files and len({x['path']for x in files})==len(files),'UNIQUE_SOURCE_FREEZE_FILES')
 for r in files:read_ref(r,project)
 def frozen(refx):
  return any(resolve_path(r['path'],project)==resolve_path(refx['path'],project)and r['bytes']==refx['bytes']and r['sha256']==refx['sha256']for r in files)
 require(frozen(ref(Path(__file__).resolve()))and frozen(ref(Path(__file__).resolve().parent/'source_catalog.py')),'EXECUTED_CUSTODY_SOURCE_IN_FREEZE')
 return plan,freeze,frozen

def verify_data_admission(admission,project,phase):
 require(phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS')
 plan,freeze,frozen=verify_source_binding(admission,project,'DATA');require(admission['phase']==phase and admission['allowed_cases']==phase_ids(phase)and admission['private_output']==str(WORKDIR/'private'),'EXACT_DATA_SCOPE')
 policy_ref=admission['data_policy_ref'];require(frozen(policy_ref),'METADATA_POLICY_IN_ACTUAL_SOURCE');policy=verify_policy(load_ref(policy_ref,project),policy_ref)
 require(admission['owner_ref']==policy['owner_ref'],'SAME_POLICY_OWNER')
 source=load_ref(admission['source_admission_ref'],project)
 require(source['schema_version']==1 and source['epoch']==51 and source['kind']==KIND and source['owner_ref']==admission['owner_ref']and source['parent']==SOURCE and source['plan_ref']==admission['plan_ref']and source['source_freeze_ref']==admission['source_freeze_ref'],'EXACT_ACTUAL_SOURCE_ADMISSION')
 require(type(source['source_commit'])is str and re.fullmatch('[0-9a-f]{40}',source['source_commit'])and source['source_commit']not in(SOURCE,'486888de9602bbb5d817a55f707b4fcfd11c65e0','3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5','a68b7ba587332f176f65d0348de3e910aa16e77a') and source['source_full_tree_verified']is True and source['source_publication_independently_verified']is True and source['scientific_dispatch_authorized']is False,'ACTUAL_REVIEWED_SOURCE_BEFORE_PAYLOAD')
 require(admission['confirmation_materialization_authorized']is False and plan['confirmation_lineage_status']=='UNQUALIFIED_HOLD','NO_CONFIRMATION_MATERIALIZATION_LINEAGE_HOLD')
 return policy,source

def decode_id(scan,s):
 require(s[2]=='number','INTEGER_DOCUMENT_ID_REQUIRED');v=json.loads(scan.raw(s));require(type(v)is int and v>=0,'INTEGER_DOCUMENT_ID_REQUIRED');return v

def metadata_boundaries(policy,project):
 census=load_ref(policy['source_inputs'][0],project);lineage=load_ref(policy['source_inputs'][1],project)
 require(census['epoch']==51 and census['source_checkpoint']==SOURCE and census['metadata_only']is True and census['roles_selected_or_frozen']is False and census['eligible_metadata_counts']=={'dev':13,'test':4}and len(census['all423_TRAIN_source_IDs'])==423 and len(census['historical_TRAIN_normalized_document_hashes'])==422,'EXACT_FULL_HISTORICAL_SOURCE_CENSUS')
 require(lineage['epoch']==51 and lineage['checks_passed']is True,'EXACT_INDEPENDENT_MODEL_DEV_ONLY_ADMISSION')
 all_rows=census['all184_official_dev_test_metadata_and_exclusion_census'];all_dev=[r for r in all_rows if r['source_split']=='dev'];require(len(all_rows)==184 and len(all_dev)==61,'ALL_OFFICIAL_SPLIT_METADATA')
 clean=lambda r:{k:v for k,v in r.items()if k!='ranking_sha256'}
 require({r['document_id']:r for r in census['eligible_metadata_pools']['dev']}=={r['document_id']:clean(r)for r in policy['all13_ranked_DEV_metadata']},'EXACT_UNUSED_DEV_POOL_REPLAY')
 require(census['eligible_metadata_pools']['test']==policy['conditional_confirmation_documents'],'EXACT_UNUSED_TEST_HOLD_REPLAY')
 blocked=[r for r in all_rows if r['exclusion_reasons']]
 audit={'Legal96_identity_hashes':[{'document_filename_key_sha256':h}for h in census['Legal96_exposed_filename_hashes']],
  'blocked_names':sorted({r['document_filename_key_sha256']for r in blocked}|set(census['Legal96_exposed_filename_hashes'])),
  'blocked_hashes':sorted({r['normalized_document_sha256']for r in blocked}|set(census['historical_TRAIN_normalized_document_hashes'])),
  'excluded_DEV_document_ids':sorted(r['document_id']for r in all_dev if r['exclusion_reasons'])}
 return audit,all_dev

def old_legal96_states(project):
 source={'path':'experiments/sota-2026-10-22/legal-transfer/confirmation96.jsonl','bytes':180878,'sha256':'80324c3c68cd2d178d9418c3736323ded2eee23f7c45585e5eb04a9aa0a05f53'}
 lines=read_ref(source,project).splitlines();require(len(lines)==96,'EXACT_EXPOSED_LEGAL96_ROWS');states=[]
 for line in lines:
  s=SpanJSON(line);t=s.members(s.value(0));states.append(normalized(s.decode_string(s.members(t['input'])['state'],'legacy_dev_text')));require(s.gold_values_decoded==0,'NO_OLD_GOLD_DECODE')
 require(all(states),'NONEMPTY_EXPOSED_DEV_STATES');return states

def prepare_member(member,policy,phase,legacy_states,audit,all_dev_metadata,catalog,progress):
 selected=list(DEV_DOCS if phase=='dev'else CONF_DOCS);ids=phase_ids(phase);expected_rows=policy['selected_dev_documents']if phase=='dev'else policy['conditional_confirmation_documents'];by={x['document_id']:x for x in expected_rows}
 require(phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS');require(list(by)==selected and set(selected).isdisjoint(audit['excluded_DEV_document_ids']),'ONLY_FROZEN_FRESH_SELECTED_DOCUMENTS')
 scan=SpanJSON(member);progress.update(value_decoder_counts=scan.decoded,document_IDs_seen=0,selected_raw_choice_tokens_copied=0)
 root=scan.value(0);require(root[2]=='object'and scan.ws(root[1])==len(member),'EXACT_DATASET_OBJECT');top=scan.members(root);labels=scan.members(top['labels']);require(set(labels)==set(CATALOG_KEYS),'EXACT_17_HYPOTHESIS_CATALOG')
 claims={h:scan.decode_string(scan.members(labels[h])['hypothesis'],'selected_hypothesis')for h in HYPOTHESES};require(all(v.strip()and len(v.encode())<=MAX_CLAIM_BYTES for v in claims.values()),'NONEMPTY_BOUNDED_ORIGINAL_HYPOTHESES')
 blocked_names=set(audit['blocked_names']);blocked_hashes=set(audit['blocked_hashes']);all_ids=set();found={};choices={}
 for ordinal,span in enumerate(scan.items(top['documents'])):
  fields=scan.members(span);did=decode_id(scan,fields['id']);require(did not in all_ids,'UNIQUE_DOCUMENT_IDS');all_ids.add(did);progress['document_IDs_seen']=len(all_ids)
  if did not in selected:continue
  expected=by[did];name=scan.decode_string(fields['file_name'],'metadata');name_sha=sha(filename_key(name).encode());require(name_sha==expected['document_filename_key_sha256']and name_sha not in blocked_names,'SOURCE_FILENAME_IDENTITY_OR_LEGAL96_ALIAS')
  text=scan.decode_string(fields['text'],'selected_document');norm=normalized(text);require(text.strip()and len(text.encode())<=MAX_DOC_BYTES and sha(norm.encode())==expected['normalized_document_sha256']and sha(norm.encode())not in blocked_hashes,'SOURCE_DOCUMENT_IDENTITY_OR_PRIOR_ALIAS')
  require(not any(s and s in norm for s in legacy_states),'EXPOSED_LEGAL96_SUBSTRING_ALIAS_NO_REPLACEMENT');require(all(normalized(h)!=norm for h in claims.values()),'SOURCE_EQUALS_HYPOTHESIS')
  units=catalog.sentence_catalog(text);catalog.validate_spans(units);require(''.join(x['sentence']for x in units)==text,'EXACT_ORIGINAL_SOURCE_PARTITION')
  found[did]={'document_id':did,'record_ordinal':ordinal,'source_group_sha256':sha(('ContractNLI|'+ARCHIVE_SHA+'|dev|'+str(did)).encode()),'source_document_sha256':sha(text.encode()),'normalized_document_sha256':sha(norm.encode()),'source_filename_key_sha256':name_sha,'evidence':units}
  sets=list(scan.items(fields['annotation_sets']));require(len(sets)==1,'EXACT_ONE_ANNOTATION_SET');ann=scan.members(scan.members(sets[0])['annotations'])
  for h in HYPOTHESES:
   choice=scan.members(ann[h])['choice'];require(choice[2]=='string','OPAQUE_CHOICE_MUST_BE_STRING_TOKEN');choices[(did,h)]=choice
 require(all_ids=={r['document_id']for r in all_dev_metadata}and len(all_ids)==61 and set(found)==set(selected),'EXACT_DEV_MEMBER_IDS_AND_SELECTED_FOUR')
 docs=[found[d]for d in selected];cases=[];records=[];tokens=[]
 for doc in docs:
  text=''.join(u['sentence']for u in doc['evidence'])
  for h in HYPOTHESES:
   cid=f'contractnli:eced6528:dev:{doc["document_id"]}:{h}';case={'id':cid,'document_id':doc['document_id'],'hypothesis_id':h,'input_sha256':sha(canonical({'claim':claims[h],'document':text})),'claim':claims[h]};cases.append(case)
   records.append({k:v for k,v in dict(doc,**{k:case[k]for k in ['id','hypothesis_id','input_sha256']},source_units=len(doc['evidence'])).items()if k!='evidence'})
   tokens.append(base64.b64encode(scan.raw(choices[(doc['document_id'],h)])).decode('ascii'));progress['selected_raw_choice_tokens_copied']=len(tokens)
 require(len({d['normalized_document_sha256']for d in docs})==4 and len({c['input_sha256']for c in cases})==12 and [c['id']for c in cases]==ids,'DISTINCT_FIXED_DOCUMENTS_AND_CASES')
 bank={'schema_version':1,'epoch':51,'kind':KIND,'role':phase,'source_archive_sha256':ARCHIVE_SHA,'documents':docs,'cases':cases};require(len(canonical(bank))<=MAX_BANK_BYTES,'BOUNDED_FEATURE_BANK')
 vault={'schema_version':1,'epoch':51,'kind':KIND,'role':phase,'source_archive_sha256':ARCHIVE_SHA,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','opaque_token_encoding':'BASE64_OF_ORIGINAL_RAW_JSON_STRING_TOKEN','official_codec_source_sha256':CODEC_SHA,'opaque_raw_choice_tokens_base64':tokens}
 require(scan.gold_values_decoded==0 and scan.decoded['selected_document']==4 and scan.decoded['selected_hypothesis']==3,'LABEL_BLIND_EXACT_SELECTED_VALUE_BOUNDARY')
 return bank,vault,records,{'selected_document_text_decodes':4,'selected_hypothesis_text_decodes':3,'semantic_gold_values_decoded':0,'selected_raw_choice_tokens_copied':12,'unselected_document_text_or_choice_decodes':0,'unique_source_units':sum(len(d['evidence'])for d in docs),'value_decoder_counts':scan.decoded}

def safe_error(error):return {'code':'CUSTODY_STOP_NO_RETRY','exception_type':type(error).__name__,'message_sha256':sha(str(error).encode())}

def materialize(admission_ref,archive_path,project,phase):
 require(phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS')
 admission=load_ref(admission_ref,project);policy,source=verify_data_admission(admission,project,phase);audit,all_dev=metadata_boundaries(policy,project)
 out=WORKDIR/'private';out.mkdir(mode=0o700,exist_ok=True);stem=phase_stem(phase);attempt=out/(stem+'_DATA_ATTEMPT.json');bank_path=out/(stem+'_FEATURES.json');vault_path=out/(stem+'_GOLD.vault.json');report_path=Path(project)/'experiments/sota-2026-10-22/audit/epoch51'/phase_report_name(phase)
 require(not any(p.exists()or p.is_symlink()for p in[attempt,bank_path,vault_path,report_path]),'DATA_ONCE_OUTPUTS_ABSENT')
 put(attempt,{'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'admission':admission_ref,'automatic_retry':False,'semantic_gold_values_decoded':0})
 report={'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'status':'DATA_FAILED_CLOSED_NO_RETRY','plan_sha256':admission['plan_ref']['sha256'],'source_freeze_sha256':admission['source_freeze_ref']['sha256'],'source_commit':source['source_commit'],'selected_ids':phase_ids(phase),'source_checkpoint':SOURCE,'semantic_gold_values_decoded':0,'selected_raw_choice_tokens_copied':0,'DATA_calls':1,'model_tokenizer_native_calls':0,'confirmation_materialization_authorized':phase=='confirmation','used_confirmation_identities':phase_ids(phase)if phase=='confirmation'else[],'partial_parse_metadata':{},'errors':[],'evidence':{'root_data_admission':admission_ref,'data_policy':admission['data_policy_ref'],'source_admission':admission['source_admission_ref']}}
 try:
  owner_guard(admission['owner_ref'],project);archive_ref={'path':str(resolve_path(archive_path,project)),'bytes':ARCHIVE_BYTES,'sha256':ARCHIVE_SHA};b=read_ref(archive_ref,project);require(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==ARCHIVE_GIT,'EXACT_OFFICIAL_ARCHIVE_GIT_IDENTITY')
  with zipfile.ZipFile(io.BytesIO(b))as z:
   entries=[x for x in z.infolist()if x.filename=='contract-nli/dev.json'and not x.is_dir()];require(len(entries)==1,'ONE_EXACT_DEV_MEMBER');info=entries[0];require(info.file_size==MEMBER_BYTES,'DEV_MEMBER_SIZE');member=z.read(info);require(len(member)==MEMBER_BYTES and sha(member)==MEMBER_SHA,'DEV_MEMBER_SHA')
  states=old_legal96_states(project);catalog=source_catalog();bank,vault,records,stats=prepare_member(member,policy,phase,states,audit,all_dev,catalog,report['partial_parse_metadata']);owner_guard(admission['owner_ref'],project)
  features_ref=put(bank_path,bank);vault_ref=put(vault_path,vault);identity_ref=put(out/(stem+'_SELECTED_IDENTITIES.json'),{'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'selected_ids':phase_ids(phase),'records':records,'all_selected_DEV_forever_on_access':phase=='dev','used_confirmation_identities':report['used_confirmation_identities']})
  report.update(status='READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT',features=features_ref,private_features=features_ref,private_vault=vault_ref,identity_manifest=identity_ref,statistics=stats,selected_raw_choice_tokens_copied=12,old_exposed_DEV_texts_decoded_for_collision_only=96,protected_existing_confirmation_body_or_choice_decodes=0,current_confirmation_document_text_decodes=4 if phase=='confirmation'else 0,current_confirmation_semantic_choice_decodes=0)
 except Exception as error:report['errors'].append(safe_error(error));report['selected_raw_choice_tokens_copied']=report['partial_parse_metadata'].get('selected_raw_choice_tokens_copied',0)
 put(report_path,report);return report

def check_physical_closure(physical,owner):
 require(physical['schema_version']==1 and physical['epoch']==51 and physical['kind']==KIND and physical['checks_passed']is True,'PHYSICAL_CLOSURE_REPORT_REQUIRED')
 require(physical['kernel_boot_id']==owner['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()and physical['PID_namespace']==owner['PID_namespace']==os.readlink('/proc/self/ns/pid'),'CLOSURE_SAME_BOOT_NAMESPACE')
 identities=physical['owned_process_identities'];require(type(identities)is list and identities and len({x['pid']for x in identities})==len(identities),'OWNED_PROCESS_IDENTITIES_REQUIRED')
 groups=set();sessions=set();checked=[]
 for x in identities:
  require(all(type(x[k])is int and x[k]>1 for k in['pid','startticks','pgid','sid'])and x['pid']!=owner['pid'],'EXACT_TARGET_PROCESS_IDENTITY');groups.add(x['pgid']);sessions.add(x['sid']);p=Path('/proc')/str(x['pid'])
  try:s=(p/'stat').read_text().rsplit(')',1)[1].split()
  except FileNotFoundError:checked.append({'pid':x['pid'],'state':'ABSENT_OLD_TARGET_CLOSED'});continue
  if int(s[19])!=x['startticks']:checked.append({'pid':x['pid'],'state':'PID_REUSED_OLD_TARGET_CLOSED'});continue
  status=(p/'status').read_text();fdsize=next(int(line.split(':',1)[1].strip())for line in status.splitlines()if line.startswith('FDSize:'));memory=[int(v)for v in(p/'statm').read_text().split()]
  require(s[0]=='Z'and int(s[49])==0 and fdsize==0 and not any(memory),'OWNED_TARGET_NOT_TERMINAL_ZERO_RESOURCE');checked.append({'pid':x['pid'],'state':'Z','wait_status':0,'FDSize':fdsize,'statm':memory})
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:s=(p/'stat').read_text().rsplit(')',1)[1].split()
  except(FileNotFoundError,ProcessLookupError):continue
  if int(s[2])in groups or int(s[3])in sessions:require(s[0]=='Z'and int(s[49])==0,'LIVE_OR_FAILED_MEMBER_OF_OWNED_TARGET_SCOPE')
 return checked

def verify_forecast_work_counts(raw):
 rows=raw['rows'];require(len(rows)==48 and raw['counters']['forecasts_completed']==48,'EXACT_48_FINAL_FORECASTS')
 expected=0
 for row in rows:
  if row['arm']=='whole_source':
   windows=row['window_forecasts'];require(type(windows)is list and 1<=len(windows)<=16 and row['evidence']['aggregation']['all_window_count']==len(windows),'COMPLETE_WHOLE_SOURCE_WINDOW_COUNT')
   count=len(windows)
  else:require(row['arm']in ARMS[:3],'FROZEN_ARM');count=1
  require(row['model_forward_calls']==count and row['window_count']==count,'PER_FORECAST_PHYSICAL_FORWARD_COUNT');expected+=count
 require(type(expected)is int and 48<=expected<=228 and raw['expected_physical_forwards']==expected and raw['counters']['NLI_forwards_attempted']==raw['counters']['NLI_forwards_completed']==expected,'EXACT_VARIABLE_PHYSICAL_FORWARD_COUNTS')
 return expected

def verify_late_bundle(admission,project,phase):
 require(phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS')
 verify_source_binding(admission,project,'GOLD');require(admission['phase']==phase and admission['expected_forecasts']==48 and admission['max_model_forward_calls']==228 and admission['expected_native_corpus_batches']==1,'EXACT_LATE_GOLD_PHASE_COUNTS')
 data=load_ref(admission['data_admission_ref'],project);require(data['epoch']==51 and data['kind']==KIND and data['phase']==phase and data['status']=='READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT'and data['errors']==[]and data['selected_ids']==phase_ids(phase)and data['semantic_gold_values_decoded']==0,'QUALIFIED_LABEL_BLIND_DATA_REQUIRED')
 require(data['plan_sha256']==admission['plan_ref']['sha256']and data['source_freeze_sha256']==admission['source_freeze_ref']['sha256'],'DATA_SOURCE_BINDING')
 raw=load_ref(admission['raw_ref'],project);require(raw['schema_version']==1 and raw['epoch']==51 and raw['kind']==KIND and raw['phase']==phase and raw['errors']==[]and raw['plan_sha256']==admission['plan_ref']['sha256']and raw['source_freeze_sha256']==admission['source_freeze_ref']['sha256'],'ACTUAL_RAW_PHASE_AND_SOURCE')
 rows=raw['rows'];require(type(rows)is list and len(rows)==48 and [(r['case_id'],r['arm'])for r in rows]==[(cid,arm)for cid in phase_ids(phase)for arm in ARMS],'ALL_48_FORECASTS_CAPTURED_IN_FROZEN_ORDER')
 require(raw['counters']['native_corpus_batches_attempted']==raw['counters']['native_corpus_batches_completed']==raw['counters']['native_corpus_batches']==1,'EXACT_ONE_ACTUAL_NATIVE_BATCH')
 physical_count=verify_forecast_work_counts(raw)

 seal=load_ref(admission['raw_seal_ref'],project);require(seal['schema_version']==1 and seal['epoch']==51 and seal['kind']==KIND and seal['phase']==phase and seal['raw_ref']==admission['raw_ref']and seal['plan_sha256']==admission['plan_ref']['sha256']and seal['source_freeze_sha256']==admission['source_freeze_ref']['sha256']and seal['forecast_count']==48,'EXACT_SEALED_RAW_BEFORE_GOLD')
 q=load_ref(admission['qualification_ref'],project)
 require(q['epoch']==51 and q['kind']==KIND and q['phase']==phase and q['checks_passed']is True and q['plan_sha256']==admission['plan_ref']['sha256']and q['source_freeze_sha256']==admission['source_freeze_ref']['sha256']and q['raw_sha256']==admission['raw_ref']['sha256']and q['actual_forecasts']==48 and q['actual_model_forward_calls']==physical_count and q['actual_native_corpus_batches']==1 and q['all_owned_processes_physically_closed']is True and q['all_forecasts_complete_before_gold']is True,'INDEPENDENT_QUALIFIED_ALL_FORECASTS_AND_CLOSURE')
 physical=load_ref(admission['physical_closure_ref'],project);require(physical['phase']==phase,'PHYSICAL_PHASE_BINDING');owner=owner_guard(admission['owner_ref'],project);physical_checked=check_physical_closure(physical,owner)
 return data,physical_checked

def join_gold(admission_ref,project,phase):
 require(phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS')
 admission=load_ref(admission_ref,project);out=WORKDIR/'private';stem=phase_stem(phase);joined=out/(stem+'_GOLD_JOINED.json');attempt=out/(stem+'_GOLD_ATTEMPT.json');vault_attempt=out/(stem+'_GOLD.vault.json.DECODE_ATTEMPT.json');report_path=Path(project)/'experiments/sota-2026-10-22/audit/epoch51'/('GOLD_JOIN_REPORT.json'if phase=='dev'else'CONFIRMATION_GOLD_JOIN_REPORT.json')
 require(admission['schema_version']==1 and admission['epoch']==51 and admission['kind']==KIND and admission['mode']=='GOLD'and admission['phase']==phase,'EXACT_ROOT_GOLD_ADMISSION');owner_guard(admission['owner_ref'],project)
 require(out.is_dir()and not any(p.exists()or p.is_symlink()for p in[joined,attempt,vault_attempt,report_path]),'GOLD_ONCE_ATTEMPT_AND_OUTPUTS_ABSENT')
 put(attempt,{'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'admission':admission_ref,'late_custodian_function_calls':1,'semantic_label_decodes':0,'automatic_retry':False})
 report={'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'status':'GOLD_JOIN_FAILED_CLOSED_NO_RETRY','late_custodian_function_calls':1,'label_reader_calls':0,'semantic_label_decodes':0,'decode_attempted_tokens':0,'semantic_decode_count_uncertain':False,'original_archive_gold_traversals':0,'model_tokenizer_native_calls':0,'used_confirmation_identities':phase_ids(phase)if phase=='confirmation'else[],'errors':[],'evidence':{'root_gold_admission':admission_ref}}
 try:
  data,closed=verify_late_bundle(admission,project,phase);vault_ref=data['private_vault'];require(vault_ref['path']==str(out/(stem+'_GOLD.vault.json')),'EXACT_PRIVATE_VAULT_PATH')
  put(vault_attempt,{'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'semantic_label_decodes':0,'automatic_retry':False,'admission':admission_ref});report['label_reader_calls']=1
  # FIRST vault bytes occur after source, independent qualification, all48 rows,
  # sealed raw, and live /proc verification of every owned target scope.
  vault=load_ref(vault_ref,project);require(vault['schema_version']==1 and vault['epoch']==51 and vault['kind']==KIND and vault['role']==phase and vault['source_archive_sha256']==ARCHIVE_SHA and vault['ids']==phase_ids(phase)and vault['label_encoding']=='OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED'and vault['opaque_token_encoding']=='BASE64_OF_ORIGINAL_RAW_JSON_STRING_TOKEN'and vault['official_codec_source_sha256']==CODEC_SHA,'EXACT_VAULT_ORIGIN_SCHEMA_AND_CODEC')
  tokens=vault['opaque_raw_choice_tokens_base64'];require(type(tokens)is list and len(tokens)==12 and all(type(x)is str for x in tokens),'EXACT_TWELVE_OPAQUE_TOKENS');labels={};token_hashes={}
  for i,(cid,encoded)in enumerate(zip(phase_ids(phase),tokens)):
   owner_guard(admission['owner_ref'],project);token=base64.b64decode(encoded,validate=True);put(out/(stem+f'_GOLD_PROGRESS_{i:02d}_BEFORE.json'),{'id':cid,'previous_semantic_label_decodes':report['semantic_label_decodes'],'token_sha256':sha(token),'decode_started':True,'decode_completed':False});report['decode_attempted_tokens']+=1
   value=json.loads(token);report['semantic_label_decodes']+=1
   put(out/(stem+f'_GOLD_PROGRESS_{i:02d}_AFTER.json'),{'id':cid,'semantic_label_decodes':report['semantic_label_decodes'],'decode_completed':True,'supported_exact_literal':type(value)is str and value in LABELS});require(type(value)is str and value in LABELS,'UNSUPPORTED_AUTHOR_CHOICE_NO_REMAP');labels[cid]=value;token_hashes[cid]=sha(token)
  require(report['semantic_label_decodes']==len(labels)==12,'EXACT_TWELVE_LATE_LABELS_NO_DROP')
  joined_ref=put(joined,{'schema_version':1,'epoch':51,'kind':KIND,'phase':phase,'selected_ids':phase_ids(phase),'labels':labels,'label_token_sha256s':token_hashes,'semantic_label_decodes':12,'label_reader_calls':1,'all_labels_decoded_after_forecasts_and_ALL_physical_closure':True,'plan_sha256':admission['plan_ref']['sha256'],'source_freeze_sha256':admission['source_freeze_ref']['sha256'],'source_archive_sha256':ARCHIVE_SHA,'used_confirmation_identities':report['used_confirmation_identities']})
  report.update(status='GOLD_JOIN_COMPLETE_AFTER_ALL_PHYSICAL_CLOSURE',joined_gold=joined_ref,physical_targets_checked=closed,plan_sha256=admission['plan_ref']['sha256'],source_freeze_sha256=admission['source_freeze_ref']['sha256'])
 except Exception as error:
  report['errors'].append(safe_error(error));report['semantic_decode_count_uncertain']=len(list(out.glob(stem+'_GOLD_PROGRESS_*_BEFORE.json')))!=len(list(out.glob(stem+'_GOLD_PROGRESS_*_AFTER.json')))
 put(report_path,report);return report

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['DATA','GOLD']);p.add_argument('--phase',choices=['dev','confirmation'],required=True);p.add_argument('--project',required=True);p.add_argument('--admission',required=True);p.add_argument('--expected-admission-sha256',required=True);p.add_argument('--archive');a=p.parse_args()
 require(a.phase=='dev','CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS')
 require(resolve_path(a.project,a.project)==WORKDIR/'project','EXACT_ISOLATED_PROJECT');admission_ref=ref(resolve_path(a.admission,a.project));require(admission_ref['sha256']==a.expected_admission_sha256,'EXACT_ROOT_ADMISSION_SHA')
 if a.mode=='DATA':require(a.archive is not None,'ARCHIVE_REQUIRED');result=materialize(admission_ref,a.archive,a.project,a.phase)
 else:require(a.archive is None,'NO_ARCHIVE_FOR_LATE_GOLD');result=join_gold(admission_ref,a.project,a.phase)
 fields=['status','phase','semantic_gold_values_decoded','selected_raw_choice_tokens_copied','semantic_label_decodes','decode_attempted_tokens','semantic_decode_count_uncertain','errors'];print(json.dumps({k:result[k]for k in fields if k in result},sort_keys=True))
 return 0 if result['errors']==[]else 1

if __name__=='__main__':raise SystemExit(main())
