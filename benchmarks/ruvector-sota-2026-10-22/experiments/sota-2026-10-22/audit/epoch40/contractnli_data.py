"""Frozen-policy ContractNLI TEST custodian; no gold semantic decoder here."""
import argparse,hashlib,importlib.util,json,os,re,struct,unicodedata,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT';SOURCE='2cf5aba60a050079506a5e9aa5463f44c1efcd5a';EPOCH=40
MAGIC=b'RUVECTOR_CONTRACTNLI40_CHOICE_RAW_V1\x00'
ARMS=['tasksource_source_order','tasksource_native','tasksource_lexical','b354_source_order']
ARCHIVE_BYTES=65362913;ARCHIVE_GIT_BLOB='757fd1dafd29a997fba00c60c6d40b2930a36159'
def local(name):
 spec=importlib.util.spec_from_file_location('e40_'+name,HERE/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
J=local('contractnli_json_spans');G=local('contractnli_guard')
def require(value,message):
 if not value:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def unique(pairs):
 out={}
 for k,v in pairs:require(k not in out,'DUPLICATE_METADATA_KEY');out[k]=v
 return out
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def read_bytes(path,expected=None):
 p=Path(path);require(p.is_file()and not p.is_symlink(),'REGULAR_SOURCE_FILE_REQUIRED');b=p.read_bytes();require(expected is None or sha(b)==expected,'SOURCE_SHA_MISMATCH');return b
def metadata(path,expected=None):return json.loads(read_bytes(path,expected),object_pairs_hook=unique)
def ref(path):
 b=read_bytes(path);return {'path':str(path),'bytes':len(b),'sha256':sha(b)}
def put_bytes(path,b):
 p=Path(path);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def put(path,value):put_bytes(path,(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def filename_key(value):return ' '.join(unicodedata.normalize('NFKC',value.replace('\\','/').rsplit('/',1)[-1]).casefold().split())
def decode_metadata(scan,span):
 if span[2]=='string':return scan.decode_string(span,'metadata')
 require(span[2]=='number','METADATA_ID_TYPE');value=json.loads(scan.raw(span));require(type(value)is int,'INTEGER_METADATA_ID_REQUIRED');return value
def check_archive(path,expected_sha):
 b=read_bytes(path,expected_sha);require(len(b)==ARCHIVE_BYTES,'EXACT_OFFICIAL_ARCHIVE_SIZE');require(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==ARCHIVE_GIT_BLOB,'OFFICIAL_ARCHIVE_GIT_BLOB_MISMATCH');return b

def prepare_member(member,policy,pool,legacy_states,archive_sha,progress=None):
 """Only authorized custodian invokes this after reviewed local predata seal."""
 selected=policy['selected_document_ids'];require(len(selected)==len(set(selected))==12,'TWELVE_FIXED_TEST_DOCUMENTS_REQUIRED');by_id={r['document_id']:r for r in pool if r['source_split']=='test'and not r['metadata_exclusion_flags']};require(set(selected)<=set(by_id),'SELECTED_IDS_NOT_IN_FROZEN_POOL');require(len(by_id)==policy['eligible_pool_document_count'],'EXACT_PRIOR_ELIGIBLE_POOL_COUNT');salt=policy['selection_salt'];ranked=sorted(by_id,key=lambda did:(sha((salt+'|test|'+str(did)+'|'+by_id[did]['normalized_document_sha256']).encode()),did));require(selected==ranked[:12],'FIXED_METADATA_HASH_SELECTION_MISMATCH');scan=J.SpanJSON(member)
 if progress is not None:progress['value_decoder_counts']=scan.decoded;progress['document_IDs_seen']=0
 root=scan.value(0);require(root[2]=='object'and scan.ws(root[1])==len(member),'EXACT_DATASET_OBJECT');top=scan.members(root);require('labels'in top and 'documents'in top,'OFFICIAL_TOP_SCHEMA');labels=scan.members(top['labels']);require(len(labels)==17,'EXACT_FIXED_SEVENTEEN_HYPOTHESIS_KEYS');salt=policy['selection_salt'];hyp_id=min(labels,key=lambda key:sha((salt+'|hypothesis|'+key).encode()));require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}',hyp_id),'SAFE_OFFICIAL_HYPOTHESIS_KEY');hyp_info=scan.members(labels[hyp_id])
 if progress is not None:progress['selected_hypothesis_id']=hyp_id;progress['selected_case_ids']=[f'contractnli:eced6528:test:{did}:{hyp_id}'for did in selected]
 claim=scan.decode_string(hyp_info['hypothesis'],'selected_hypothesis');found={};all_ids=set();raw_choice_spans={};source_ordinal={}
 for ordinal,span in enumerate(scan.items(top['documents'])):
  fields=scan.members(span);did=decode_metadata(scan,fields['id']);require(type(did)is int and did>=0 and did not in all_ids,'UNIQUE_INTEGER_DOCUMENT_IDS_REQUIRED');all_ids.add(did)
  if progress is not None:progress['document_IDs_seen']=len(all_ids)
  if did not in selected:continue
  expected=by_id[did];name=scan.decode_string(fields['file_name'],'metadata');require(sha(filename_key(name).encode())==expected['document_filename_key_sha256'],'SOURCE_FILENAME_IDENTITY_MISMATCH');document=scan.decode_string(fields['text'],'selected_document');require(G.digest(G.normalized(document))==expected['normalized_document_sha256'],'SOURCE_NORMALIZED_DOCUMENT_IDENTITY_MISMATCH');spans=[]
  for row in scan.items(fields['spans']):
   coords=list(scan.items(row));require(len(coords)==2,'SPAN_PAIR_REQUIRED');spans.append([decode_metadata(scan,c)for c in coords])
  units=G.partition(document,spans);checks=G.guard_features(claim,[u['sentence']for u in units],document);require(checks['passed'],'INPUT_ADMISSION_STOP:'+','.join(checks['flags']));norm=G.normalized(document)
  require(not any(s and s in norm for s in legacy_states),'OLD_EXPOSED_LEGAL96_NORMALIZED_CLAUSE_SUBSTRING_STOP')
  sets=list(scan.items(fields['annotation_sets']));require(len(sets)==1,'ONE_AUTHOR_ANNOTATION_SET_REQUIRED');annotations=scan.members(scan.members(sets[0])['annotations']);require(hyp_id in annotations,'SELECTED_ANNOTATION_KEY_REQUIRED');annotation=scan.members(annotations[hyp_id]);choice=annotation['choice'];require(choice[2]=='string','OPAQUE_RAW_CHOICE_STRING_REQUIRED')
  case_id=f'contractnli:eced6528:test:{did}:{hyp_id}';record={'id':case_id,'record_ordinal':ordinal,'document_id':did,'hypothesis_id':hyp_id,'input_sha256':sha(canonical({'claim':claim,'document':document}).encode()),'source_group_sha256':sha(('ContractNLI|'+archive_sha+'|test|'+str(did)).encode()),'source_document_sha256':sha(document.encode()),'normalized_document_sha256':expected['normalized_document_sha256'],'source_filename_key_sha256':expected['document_filename_key_sha256'],'claim':claim,'evidence':units};require(len(canonical(record).encode())<=G.MAX_CASE_FEATURE_BYTES,'CASE_FEATURE_UTF8_CAP');found[did]=record;raw_choice_spans[did]=choice;source_ordinal[did]=ordinal
 require(all_ids==set(policy['all_official_test_document_ids']),'EXACT123_TEST_ID_SET_CORRESPONDENCE_REQUIRED');require(len(all_ids)==123 and set(found)==set(selected),'ALL_SELECTED_DOCUMENTS_FOUND_NO_REPLACEMENT');records=[found[i]for i in selected];ids=[r['id']for r in records];header={'schema_version':1,'epoch':40,'kind':KIND,'role':'dev','source_archive_sha256':archive_sha,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','official_codec_source_sha256':'9c63102a01576c230da94695f593fd7bd4fe2d0b20672b74e8a7f62aba426fc4'};enc=lambda b:struct.pack('<I',len(b))+b;vault=MAGIC+enc(canonical(header).encode())+b''.join(enc(scan.raw(raw_choice_spans[i]))for i in selected);require(scan.gold_values_decoded==0,'NO_GOLD_DECODER_IN_CUSTODIAN');identity=[{k:r[k]for k in ['id','record_ordinal','document_id','hypothesis_id','input_sha256','source_group_sha256','source_document_sha256','normalized_document_sha256','source_filename_key_sha256']}|{'source_units':len(r['evidence'])}for r in records]
 return {'features':{'schema_version':1,'epoch':40,'kind':KIND,'role':'dev','source_archive_sha256':archive_sha,'records':records},'vault':vault,'identities':identity,'selected_ids':ids,'statistics':{'test_documents_ID_only_seen':123,'selected_document_text_decodes':12,'selected_hypothesis_text_decodes':1,'raw_gold_tokens_copied':12,'semantic_gold_values_decoded':0,'source_units':sum(len(r['evidence'])for r in records),'selected_document_ids':selected,'selected_hypothesis_id':hyp_id,'value_decoder_counts':scan.decoded,'unselected_document_text_or_choice_decodes':0}}

def old_legal96_states(path,expected_sha):
 """Already exposed DEV-only source, skip every evaluation/gold value."""
 states=[];rows=read_bytes(path,expected_sha).splitlines();require(len(rows)==96,'EXACT_ALREADY_EXPOSED_LEGAL96_ROWS')
 for line in rows:
  scan=J.SpanJSON(line);top=scan.members(scan.value(0));value=scan.decode_string(scan.members(top['input'])['state'],'legacy_dev_text');require(value.strip(),'OLD_DEV_SOURCE_STATE_NONEMPTY');states.append(G.normalized(value));require(scan.gold_values_decoded==0,'NO_OLD_GOLD_DECODE')
 return states


SAFE_PUBLIC_ERROR_CODES=frozenset(['EXACT_DATASET_OBJECT','OFFICIAL_TOP_SCHEMA','EXACT_FIXED_SEVENTEEN_HYPOTHESIS_KEYS','SAFE_OFFICIAL_HYPOTHESIS_KEY','UNIQUE_INTEGER_DOCUMENT_IDS_REQUIRED','SOURCE_FILENAME_IDENTITY_MISMATCH','SOURCE_NORMALIZED_DOCUMENT_IDENTITY_MISMATCH','OLD_EXPOSED_LEGAL96_NORMALIZED_CLAUSE_SUBSTRING_STOP','ONE_AUTHOR_ANNOTATION_SET_REQUIRED','SELECTED_ANNOTATION_KEY_REQUIRED','OPAQUE_RAW_CHOICE_STRING_REQUIRED','CASE_FEATURE_UTF8_CAP','EXACT123_TEST_ID_SET_CORRESPONDENCE_REQUIRED','ALL_SELECTED_DOCUMENTS_FOUND_NO_REPLACEMENT','SPAN_PAIR_REQUIRED','SOURCE_DOCUMENT_SPAN_SCHEMA','SOURCE_SPAN_OFFSET_SCHEMA','SOURCE_PARTITION_COVERAGE','EXACT_OFFICIAL_ARCHIVE_SIZE','OFFICIAL_ARCHIVE_GIT_BLOB_MISMATCH','SOURCE_SHA_MISMATCH','REGULAR_SOURCE_FILE_REQUIRED','EXACT_UNIQUE_OFFICIAL_TEST_MEMBER','SAFE_BOUNDED_TEST_MEMBER','EXACT_TEST_MEMBER_SIZE','EXACT_ALREADY_EXPOSED_LEGAL96_ROWS','OLD_DEV_SOURCE_STATE_NONEMPTY','TWELVE_FIXED_TEST_DOCUMENTS_REQUIRED','SELECTED_IDS_NOT_IN_FROZEN_POOL','FIXED_METADATA_HASH_SELECTION_MISMATCH','EXACT_PRIOR_ELIGIBLE_POOL_COUNT','INTEGER_METADATA_ID_REQUIRED','METADATA_ID_TYPE','OBJECT_REQUIRED','ARRAY_REQUIRED','JSON_DEPTH','INVALID_JSON_VALUE','DUPLICATE_JSON_KEY','UNTERMINATED_STRING','INVALID_UTF8'])
SAFE_INPUT_FLAGS=frozenset(['NONEMPTY_ORIGINAL_HYPOTHESIS_REQUIRED','SOURCE_UNIT_COUNT_CAP','HYPOTHESIS_UTF8_CAP','SOURCE_UNIT_UTF8_CAP','SOURCE_PARTITION_NOT_COMPLETE','EMPTY_SOURCE_DOCUMENT','SOURCE_DOCUMENT_UTF8_CAP','SOURCE_EQUALS_HYPOTHESIS'])
def safe_error(error):
 message=str(error);row={'type':type(error).__name__,'message_sha256':sha(message.encode()),'code':'CUSTODIAN_SOURCE_OR_INPUT_ADMISSION_STOP'}
 if type(error)is ValueError and message in SAFE_PUBLIC_ERROR_CODES:row['code']=message
 elif type(error)is ValueError and message.startswith('INPUT_ADMISSION_STOP:'):
  flags=message.split(':',1)[1].split(',')
  if flags and all(flag in SAFE_INPUT_FLAGS for flag in flags):row['code']='INPUT_ADMISSION_STOP';row['input_flags']=flags
 elif isinstance(error,zipfile.BadZipFile):row['code']='ZIP_STRUCTURE_OR_CHECKSUM_ERROR'
 elif isinstance(error,KeyError):row['code']='REQUIRED_SOURCE_SCHEMA_KEY_MISSING'
 elif isinstance(error,OSError):row['code']='CUSTODIAN_FILE_IO_ERROR';row['errno']=error.errno
 return row

def materialize(archive_path,out_path,policy_path,seal_path,approval_path,approval_sha):
 policy=metadata(policy_path);seal=metadata(seal_path);approval=metadata(approval_path,approval_sha);require(policy['epoch']==40 and policy['kind']==KIND and policy['roles']=={'train':[],'calibration':[],'confirmation':[],'dev_document_ids':policy['selected_document_ids']},'FROZEN_DEV_ONLY_POLICY');require(approval['approved']is True and approval['only_label_blind_custodian_parser_authorized']is True and approval['epoch']==40 and approval['source_checkpoint']==SOURCE and approval['predataseal_sha256']==sha(read_bytes(seal_path))and approval['policy_sha256']==sha(read_bytes(policy_path)),'ROOT_EXACT_PREDATA_SOURCE_APPROVAL_REQUIRED')
 for r in seal['source_files']:require(len(read_bytes(r['path'],r['sha256']))==r['bytes'],'SEALED_SOURCE_SIZE')
 for name in ['contractnli_data.py','contractnli_json_spans.py','contractnli_guard.py']:
  r=next(x for x in seal['source_files']if Path(x['path']).name==name);require(sha(read_bytes(HERE/name))==r['sha256'],'EXECUTED_SOURCE_DIFFERS_FROM_SEAL')
 out=Path(out_path);scope=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05');require(out.is_absolute()and out==out.resolve()and out.is_relative_to(scope)and not out.is_relative_to(scope/'project')and not out.exists(),'NEW_EXTERNAL_OUTPUT_REQUIRED');out.mkdir(mode=0o700);put(out/'MATERIALIZER_ATTEMPT.json',{'schema_version':1,'epoch':40,'kind':KIND,'phase':'dev','automatic_retry':False,'semantic_gold_values_decoded':0,'policy_sha256':sha(read_bytes(policy_path)),'predataseal_sha256':sha(read_bytes(seal_path))});report={'schema_version':1,'epoch':40,'kind':KIND,'phase':'dev','status':'DATA_ADMISSION_FAILED','selected_document_ids':policy['selected_document_ids'],'selected_ids':[],'semantic_gold_values_decoded':0,'raw_gold_tokens_copied':0,'model_tokenizer_native_calls':0,'errors':[],'used_confirmation_identities':[],'partial_input_parse_metadata':{},'legacy_DEV_text_decodes':None}
 try:
  archive_sha=policy['archive']['sha256'];require(re.fullmatch('[0-9a-f]{64}',archive_sha),'FROZEN_OPAQUE_ARCHIVE_SHA_REQUIRED');check_archive(archive_path,archive_sha)
  with zipfile.ZipFile(archive_path)as archive:
   all_infos=archive.infolist();matches=[i for i in all_infos if Path(i.filename).name=='test.json'and not i.is_dir()];require(len(matches)==1,'EXACT_UNIQUE_OFFICIAL_TEST_MEMBER');info=matches[0];require(not Path(info.filename).is_absolute()and '..'not in Path(info.filename).parts and info.file_size<=33554432,'SAFE_BOUNDED_TEST_MEMBER');member=archive.read(info);require(len(member)==info.file_size,'EXACT_TEST_MEMBER_SIZE');report['archive_member']={'path':info.filename,'bytes':len(member),'sha256':sha(member),'CRC32':info.CRC}
  prior=metadata(policy['prior_identity_pool']['path'],policy['prior_identity_pool']['sha256']);legacy=old_legal96_states(policy['old_exposed_legal96']['path'],policy['old_exposed_legal96']['sha256']);report['legacy_DEV_text_decodes']=len(legacy);result=prepare_member(member,policy,prior['official_dev_test_metadata'],legacy,archive_sha,report['partial_input_parse_metadata']);report.update(selected_ids=result['selected_ids'],statistics=result['statistics'],raw_gold_tokens_copied=12);put(out/'selected_identities.json',{'schema_version':1,'epoch':40,'kind':KIND,'phase':'dev','source_archive_sha256':archive_sha,'selected_ids':result['selected_ids'],'records':result['identities'],'all_selected_become_DEV_forever':True,'used_confirmation_identities':[]});put(out/'dev_features.json',result['features']);put_bytes(out/'dev_oracle.bin',result['vault']);report['identity_manifest']=ref(out/'selected_identities.json');report['external_data_assets']=[dict(ref(out/'dev_features.json'),role='dev_features'),dict(ref(out/'dev_oracle.bin'),role='dev_oracle')];report['status']='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT'
 except Exception as error:report['status']='DATA_ADMISSION_FAILED';report['selected_ids']=report['partial_input_parse_metadata'].get('selected_case_ids',[]);report['errors'].append(safe_error(error))
 put(out/'materialization_report.json',report);return report

def load_private_features(path,expected_sha256,expected_ids):
 bank=metadata(path,expected_sha256);require(set(bank)=={'schema_version','epoch','kind','role','source_archive_sha256','records'}and bank['epoch']==40 and bank['kind']==KIND and bank['role']=='dev','EXACT_PRIVATE_BANK_SCHEMA');records=bank['records'];require(len(records)==12 and [r['id']for r in records]==list(expected_ids)and len(set(expected_ids))==12,'EXACT_TWELVE_IDENTITIES')
 for r in records:
  require(set(r)=={'id','record_ordinal','document_id','hypothesis_id','input_sha256','source_group_sha256','source_document_sha256','normalized_document_sha256','source_filename_key_sha256','claim','evidence'},'FORBIDDEN_FEATURE_FIELD');require(type(r['document_id'])is int and r['id']==f'contractnli:eced6528:test:{r["document_id"]}:{r["hypothesis_id"]}','SOURCE_CASE_IDENTITY');units=r['evidence'];pos=0
  for i,u in enumerate(units):
   require(set(u)=={'unit_id','sentence','start','end'}and type(u['unit_id'])is int and u['unit_id']==i and type(u['sentence'])is str and type(u['start'])is int and type(u['end'])is int and u['start']==pos and u['end']==pos+len(u['sentence']),'CONTIGUOUS_SOURCE_QUOTE_UNITS');pos=u['end']
  text=''.join(u['sentence']for u in units);check=G.guard_features(r['claim'],[u['sentence']for u in units]);require(check['passed'],'INPUT_GUARD_STOP');require(sha(text.encode())==r['source_document_sha256']and G.digest(G.normalized(text))==r['normalized_document_sha256']and sha(canonical({'claim':r['claim'],'document':text}).encode())==r['input_sha256'],'COMPLETE_SOURCE_INPUT_HASH_MISMATCH')
 return records

def assert_packed_input(claim,premise):
 report=G.guard_premise(claim,premise);require(report['passed'],'PACKED_INPUT_GUARD_STOP');return report

def check_physical_gold_fence(closure,expected_ids):
 ids=[i+'::'+a for i in expected_ids for a in ARMS]
 require(closure['physical_readouts_completed']==48 and type(closure['physical_readouts_completed'])is int and len(closure['required_readout_ids'])==len(closure['completed_readout_ids'])==48 and set(closure['required_readout_ids'])==set(closure['completed_readout_ids'])==set(ids),'ALL_FORTY_EIGHT_REAL_READOUTS_REQUIRED')
 require(closure['model_profiles_disposed']==['b354','tasksource']and closure['native_child_closed']is True and closure['all_forecasts_closed_before_gold']is True,'MODEL_NATIVE_CLOSURE_REQUIRED')
 pin=closure['physical_closure_evidence'];b=read_bytes(pin['path'],pin['sha256']);require(len(b)==pin['bytes'],'PHYSICAL_PROOF_SIZE_MISMATCH');proof=json.loads(b,object_pairs_hook=unique)
 require(proof['schema_version']==1 and proof['epoch']==40 and proof['kind']==KIND and proof['phase']=='dev'and proof['source_plan_sha256']==closure['source_plan_sha256']and proof['physical_closure_passed']is True and proof['physical_supervisor_closed']is True and proof['unknown_physical_ownership']is False and proof['owned_worker_group_members']==[],'INDEPENDENT_PHYSICAL_CLOSURE_PROOF_REQUIRED')
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


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['materialize'])
 for n in ['archive','out','policy','seal','approval','expected-approval-sha']:p.add_argument('--'+n,required=True)
 a=p.parse_args();r=materialize(a.archive,a.out,a.policy,a.seal,a.approval,a.expected_approval_sha);print(json.dumps({'status':r['status'],'selected_document_ids':r['selected_document_ids'],'selected_ids':r['selected_ids'],'semantic_gold_values_decoded':0,'raw_gold_tokens_copied':r['raw_gold_tokens_copied'],'errors':r['errors']}))
