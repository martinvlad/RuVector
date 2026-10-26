"""Standalone label-blind root custodian; no semantic gold decoder/model calls."""
import argparse,hashlib,importlib.util,json,os,re,struct,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
FEATURES_SHA='41327b58e30e789a5c03a795e8750d1e2f3b75db986661dc7b192b0fa3b765b3'
def feature_source():
 p=HERE/'e42_features.py';b=p.read_bytes()
 if hashlib.sha256(b).hexdigest()!=FEATURES_SHA:raise ValueError('FEATURE_SOURCE_SHA_DRIFT')
 spec=importlib.util.spec_from_file_location('e42_materializer_features',p);m=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),m.__dict__);return m
F=feature_source()
NUMBER=re.compile(rb'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
WS=b' \t\r\n'
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

ARCHIVE_SHA='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
ARCHIVE_BYTES=65362913;ARCHIVE_GIT='757fd1dafd29a997fba00c60c6d40b2930a36159'
CODEC_SHA='9c63102a01576c230da94695f593fd7bd4fe2d0b20672b74e8a7f62aba426fc4'
def decode_id(scan,s):
 F.require(s[2]=='number','INTEGER_DOCUMENT_ID_REQUIRED');v=json.loads(scan.raw(s));F.require(type(v)is int and v>=0,'INTEGER_DOCUMENT_ID_REQUIRED');return v

def prepare_member(member,policy,legacy_states,catalog,progress):
 selected=policy['selected_document_ids'];hyp=policy['selected_hypothesis_ids'];ids=policy['case_ids'];F.require(len(selected)==len(set(selected))==4 and len(hyp)==len(set(hyp))==3 and ids==[f'contractnli:eced6528:test:{d}:{h}'for d in selected for h in hyp],'FIXED_FOUR_DOCUMENT_THREE_HYPOTHESIS_IDENTITIES');pool=policy['eligible_pool'];F.require(len(pool)==11 and len({r['document_id']for r in pool})==11 and all(r['source_split']=='test'and not r['metadata_exclusion_flags']for r in pool),'EXACT_ELEVEN_METADATA_POOL');by={r['document_id']:r for r in pool};salt=policy['selection_salt'];ranked=sorted(by,key=lambda d:(F.sha((salt+'|test|'+str(d)+'|'+by[d]['normalized_document_sha256']).encode()),d));F.require(selected==ranked[:4],'FIXED_DOCUMENT_HASH_RANKING');scan=SpanJSON(member);progress.update(selected_case_ids=ids,value_decoder_counts=scan.decoded,document_IDs_seen=0,global_hypothesis_keyset_validated=False);root=scan.value(0);F.require(root[2]=='object'and scan.ws(root[1])==len(member),'EXACT_DATASET_OBJECT');top=scan.members(root);labels=scan.members(top['labels']);F.require(set(labels)==set(policy['expected_structural_hypothesis_catalog_keys'])and len(labels)==17,'EXACT_GLOBAL_HYPOTHESIS_KEYSET');hk=sorted(labels,key=lambda k:(F.sha((salt+'|hypothesis|'+k).encode()),k));F.require(hyp==hk[:3],'FIXED_HYPOTHESIS_KEY_HASH_RANKING');progress['global_hypothesis_keyset_validated']=True
 claims={h:scan.decode_string(scan.members(labels[h])['hypothesis'],'selected_hypothesis')for h in hyp};F.require(all(v.strip()and len(v.encode())<=F.MAX_CLAIM_BYTES for v in claims.values()),'ORIGINAL_HYPOTHESIS_CAP');found={};choices={};all_ids=set();forbidden_ids=set(policy['excluded_prior_document_ids']);blocked_hashes=set(policy['excluded_prior_normalized_document_hashes']);F.require(set(selected).isdisjoint(forbidden_ids),'EXPOSED_PRIOR_DOCUMENT_EXCLUSION')
 for ordinal,span in enumerate(scan.items(top['documents'])):
  fields=scan.members(span);did=decode_id(scan,fields['id']);F.require(did not in all_ids,'UNIQUE_DOCUMENT_IDS');all_ids.add(did);progress['document_IDs_seen']=len(all_ids)
  if did not in selected:continue
  expected=by[did];name=scan.decode_string(fields['file_name'],'metadata');F.require(F.sha(F.filename_key(name).encode())==expected['document_filename_key_sha256'],'SOURCE_FILENAME_IDENTITY_MISMATCH');text=scan.decode_string(fields['text'],'selected_document');norm=F.normalized(text);F.require(F.sha(norm.encode())==expected['normalized_document_sha256']and F.sha(norm.encode())not in blocked_hashes,'SOURCE_DOCUMENT_IDENTITY_MISMATCH');F.require(not any(x and x in norm for x in legacy_states),'OLD_LEGAL96_EXPOSED_SUBSTRING_ALIAS_STOP');units=catalog.sentence_catalog(text);doc={'document_id':did,'record_ordinal':ordinal,'source_group_sha256':F.sha(('ContractNLI|'+policy['archive']['sha256']+'|test|'+str(did)).encode()),'source_document_sha256':F.sha(text.encode()),'normalized_document_sha256':expected['normalized_document_sha256'],'source_filename_key_sha256':expected['document_filename_key_sha256'],'evidence':units};F.validate_document(doc);F.require(all(F.normalized(c)!=norm for c in claims.values()),'SOURCE_EQUALS_HYPOTHESIS');found[did]=doc
  sets=list(scan.items(fields['annotation_sets']));F.require(len(sets)==1,'EXACT_ONE_ANNOTATION_SET');ann=scan.members(scan.members(sets[0])['annotations'])
  for h in hyp:
   choice=scan.members(ann[h])['choice'];F.require(choice[2]=='string','OPAQUE_RAW_CHOICE_STRING_REQUIRED');choices[(did,h)]=choice
 F.require(all_ids==set(policy['all_official_test_document_ids'])and len(all_ids)==123 and set(found)==set(selected),'EXACT_TEST_IDS_AND_SELECTED_DOCUMENTS');docs=[found[d]for d in selected];cases=[];records=[]
 for d in docs:
  text=''.join(u['sentence']for u in d['evidence'])
  for h in hyp:
   cid=f'contractnli:eced6528:test:{d["document_id"]}:{h}';c={'id':cid,'document_id':d['document_id'],'hypothesis_id':h,'input_sha256':F.sha(F.canonical({'claim':claims[h],'document':text})),'claim':claims[h]};cases.append(c);records.append({k:v for k,v in dict(d,**{k:c[k]for k in ['id','hypothesis_id','input_sha256']},source_units=len(d['evidence'])).items()if k!='evidence'})
 F.require(len({d['normalized_document_sha256']for d in docs})==4 and len({c['input_sha256']for c in cases})==12,'DISTINCT_DOCUMENT_AND_PAIR_INPUT_IDENTITIES');bank={'schema_version':1,'epoch':42,'kind':F.KIND,'role':'dev','source_archive_sha256':policy['archive']['sha256'],'documents':docs,'cases':cases};F.require(len(F.canonical(bank))<=F.MAX_BANK_BYTES,'FEATURE_BANK_UTF8_CAP');header={'schema_version':1,'epoch':42,'kind':F.KIND,'role':'dev','source_archive_sha256':policy['archive']['sha256'],'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','official_codec_source_sha256':CODEC_SHA};enc=lambda b:struct.pack('<I',len(b))+b;vault=F.MAGIC+enc(F.canonical(header))+b''.join(enc(scan.raw(choices[(d,h)]))for d in selected for h in hyp);F.require(scan.gold_values_decoded==0,'SEMANTIC_GOLD_DECODE_FORBIDDEN');units=sum(len(d['evidence'])for d in docs);return {'features':bank,'vault':vault,'identities':records,'document_metadata':[{k:v for k,v in d.items()if k!='evidence'}|{'source_units':len(d['evidence'])}for d in docs],'statistics':{'selected_document_text_decodes':4,'selected_hypothesis_text_decodes':3,'test_document_IDs_seen':123,'global_hypothesis_keyset_validated_before_any_new_text':True,'selected_raw_choice_tokens_copied':12,'semantic_gold_values_decoded':0,'unselected_document_text_or_choice_decodes':0,'unique_source_units':units,'expanded_pair_source_units':3*units,'expected_BGE_texts':units+12,'expected_BGE_forward_calls':sum((len(d['evidence'])+7)//8 for d in docs)+12,'native_indexes':4,'native_queries':12,'value_decoder_counts':scan.decoded}}

def old_legal96_states(ref):
 states=[];lines=F.read_ref(ref).splitlines();F.require(len(lines)==96,'EXACT_EXPOSED_LEGAL96_ROWS')
 for line in lines:
  s=SpanJSON(line);t=s.members(s.value(0));v=s.decode_string(s.members(t['input'])['state'],'legacy_dev_text');F.require(v.strip(),'EXPOSED_DEV_SOURCE_EMPTY');states.append(F.normalized(v));F.require(s.gold_values_decoded==0,'OLD_GOLD_DECODE_FORBIDDEN')
 return states

def safe_error(error):
 msg=str(error);allowed={'VERIFIED_STRUCTURAL_CATALOG_ONLY_AUTHORITY','AUTHORITATIVE_CATALOG_IDENTITY_AND_ZERO_VALUE_BOUNDARY','CATALOG_DATASET_VERSION_BINDING','DISTINCT_DOCUMENT_AND_PAIR_INPUT_IDENTITIES','FIXED_FOUR_DOCUMENT_THREE_HYPOTHESIS_IDENTITIES','EXACT_ELEVEN_METADATA_POOL','FIXED_DOCUMENT_HASH_RANKING','EXACT_DATASET_OBJECT','EXACT_GLOBAL_HYPOTHESIS_KEYSET','FIXED_HYPOTHESIS_KEY_HASH_RANKING','ORIGINAL_HYPOTHESIS_CAP','EXPOSED_PRIOR_DOCUMENT_EXCLUSION','UNIQUE_DOCUMENT_IDS','SOURCE_FILENAME_IDENTITY_MISMATCH','SOURCE_DOCUMENT_IDENTITY_MISMATCH','OLD_LEGAL96_EXPOSED_SUBSTRING_ALIAS_STOP','SOURCE_EQUALS_HYPOTHESIS','EXACT_ONE_ANNOTATION_SET','OPAQUE_RAW_CHOICE_STRING_REQUIRED','EXACT_TEST_IDS_AND_SELECTED_DOCUMENTS','FEATURE_BANK_UTF8_CAP','SOURCE_UNIT_COUNT_CAP','SOURCE_DOCUMENT_UTF8_CAP','SOURCE_UNIT_UTF8_CAP','SOURCE_DOCUMENT_EMPTY_OR_TYPE','SOURCE_DOCUMENT_CAP','SOURCE_UNIT_CAP_NO_SPLITTING','EXACT_OFFICIAL_ARCHIVE_IDENTITY','EXACT_BOUNDED_TEST_MEMBER'};row={'code':msg if type(error)is ValueError and msg in allowed else'ROOT_CUSTODIAN_SOURCE_OR_INPUT_STOP','exception_type':type(error).__name__,'message_sha256':F.sha(msg.encode())};return row

def verified_catalog_authority(policy):
 source=F.load_ref(policy['catalog_authority']);F.require(source['epoch']==41 and source['purpose']=='FUTURE_SOURCE_POLICY_ONLY_NO_E41_REOPEN'and source['kind']=='METADATA_KEY_CATALOG_ONLY'and source['status']=='OFFICIAL_STRUCTURAL_KEY_CATALOG_RECORDED_FUTURE_POLICY_ONLY'and source['materializer_calls']==source['model_tokenizer_native_calls']==source['semantic_gold_values_decoded']==source['string_value_decodes']==source['old_Legal96_text_decodes']==0,'VERIFIED_STRUCTURAL_CATALOG_ONLY_AUTHORITY');c=source['catalog'];keys=c['sorted_keys'];F.require(type(keys)is list and len(keys)==len(set(keys))==c['key_count']==17 and keys==sorted(keys)and c['canonical_sorted_key_list_sha256']==policy['catalog_keys_sha256']==F.sha(json.dumps(keys,ensure_ascii=False,separators=(',',':')).encode())and c['string_value_decodes']==c['semantic_gold_values_decoded']==c['selected_document_text_decodes']==c['selected_hypothesis_text_decodes']==c['annotation_choice_value_decodes']==c['old_Legal96_text_decodes']==0 and c['hypothesis_or_case_selection']is False and all(x==0 for k,x in c['decoder_counts'].items()if k!='field_name'),'AUTHORITATIVE_CATALOG_IDENTITY_AND_ZERO_VALUE_BOUNDARY');F.require(source['archive_source']['sha256']==policy['archive']['sha256']and source['member_source']['sha256']==policy['member']['sha256'],'CATALOG_DATASET_VERSION_BINDING');return keys

def materialize(archive,out,policy_ref,seal_ref,approval_ref):
 policy=F.load_ref(policy_ref);seal=F.load_ref(seal_ref);approval=F.load_ref(approval_ref);F.require(policy['epoch']==42 and policy['kind']==F.KIND and policy['data_roles']=={'train':[],'dev':policy['case_ids'],'calibration':[],'confirmation':[]},'FROZEN_DEV_ONLY_POLICY');F.require(approval['epoch']==42 and approval['source_checkpoint']==F.SOURCE and approval['root_one_custodian_authorized']is True and approval['policy_sha256']==policy_ref['sha256']and approval['predataseal_sha256']==seal_ref['sha256'],'EXACT_ROOT_PREDATA_AUTHORIZATION')
 for r in seal['source_files']:F.read_ref(r)
 selfref=next(r for r in seal['source_files']if Path(r['path']).name=='e42_materialize.py');F.require(F.sha(Path(__file__).read_bytes())==selfref['sha256'],'EXECUTED_SOURCE_DIFFERS_FROM_SEAL');catalog_keys=verified_catalog_authority(policy);policy=dict(policy,expected_structural_hypothesis_catalog_keys=catalog_keys);catalog=F.import_source(policy['source_catalog'],'e42_root_custodian_sentence_catalog');out=Path(out);scope=Path(policy['external_scope']);F.require(out.is_absolute()and out==out.resolve()and out.is_relative_to(scope)and not out.is_relative_to(scope/'project')and not out.exists(),'NEW_EXTERNAL_OUTPUT_REQUIRED');out.mkdir(mode=0o700);F.put(out/'MATERIALIZER_ATTEMPT.json',{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','policy':policy_ref,'source_seal':seal_ref,'automatic_retry':False,'semantic_gold_values_decoded':0});report={'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','status':'DATA_ADMISSION_FAILED','selected_ids':policy['case_ids'],'semantic_gold_values_decoded':0,'selected_raw_choice_tokens_copied':0,'model_tokenizer_native_calls':0,'partial_input_parse_metadata':{},'errors':[],'used_confirmation_identities':[]}
 try:
  b=Path(archive).read_bytes();F.require(len(b)==ARCHIVE_BYTES and F.sha(b)==policy['archive']['sha256']==ARCHIVE_SHA and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==ARCHIVE_GIT,'EXACT_OFFICIAL_ARCHIVE_IDENTITY')
  with zipfile.ZipFile(archive)as z:
   matches=[i for i in z.infolist()if Path(i.filename).name=='test.json'and not i.is_dir()];F.require(len(matches)==1,'EXACT_BOUNDED_TEST_MEMBER');info=matches[0];F.require(not Path(info.filename).is_absolute()and '..'not in Path(info.filename).parts and info.file_size<=33554432,'EXACT_BOUNDED_TEST_MEMBER');member=z.read(info);F.require(len(member)==policy['member']['bytes']and F.sha(member)==policy['member']['sha256'],'EXACT_BOUNDED_TEST_MEMBER');report['archive_member']={'path':info.filename,'bytes':len(member),'sha256':F.sha(member),'CRC32':info.CRC}
  legacy=old_legal96_states(policy['old_exposed_legal96']);report['legacy_exposed_DEV_text_decodes']=len(legacy);result=prepare_member(member,policy,legacy,catalog,report['partial_input_parse_metadata']);bank=out/'dev_features.json';vault=out/'dev_oracle.bin';F.put(bank,result['features']);F.put_bytes(vault,result['vault']);identity=F.put(out/'selected_identities.json',{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','selected_ids':policy['case_ids'],'records':result['identities'],'documents':result['document_metadata'],'all_selected_DEV_forever':True,'used_confirmation_identities':[]});report.update(status='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT',identity_manifest=identity,statistics=result['statistics'],selected_raw_choice_tokens_copied=12,external_data_assets=[dict(F.ref(bank),role='dev_features'),dict(F.ref(vault),role='dev_oracle')])
 except Exception as error:report['errors'].append(safe_error(error))
 F.put(out/'materialization_report.json',report);return report

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['archive','out','policy','seal','approval']:p.add_argument('--'+n,required=True)
 for n in ['policy','seal','approval']:p.add_argument('--expected-'+n+'-sha256',required=True)
 a=p.parse_args();refs={}
 for n in ['policy','seal','approval']:
  r=F.ref(getattr(a,n));F.require(r['sha256']==getattr(a,'expected_'+n+'_sha256'),'EXACT_COMMAND_SOURCE_REFERENCE');refs[n]=r
 v=materialize(a.archive,a.out,refs['policy'],refs['seal'],refs['approval']);print(json.dumps({'status':v['status'],'selected_ids':v['selected_ids'],'semantic_gold_values_decoded':v['semantic_gold_values_decoded'],'selected_raw_choice_tokens_copied':v['selected_raw_choice_tokens_copied'],'errors':v['errors']}))
