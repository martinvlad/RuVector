"""Standalone source-only feature loader. No gold/vault/model capability."""
import hashlib,importlib.util,json,os,stat,unicodedata
from pathlib import Path
EPOCH=45;KIND='REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT';SOURCE='c5608a638ecdc99a846c4901736440d1e4d40db0';WORKDIR=Path('/tmp/ruvector-sota-2026-10-22/epoch45-c5608a638ecd')
MAX_DOC_BYTES=1048576;MAX_UNIT_BYTES=262144;MAX_CLAIM_BYTES=65536;MAX_UNITS=1024;MAX_BANK_BYTES=8388608
DEV_DOCUMENT_IDS=(357,227,46,212);HYPOTHESIS_IDS=('nda-1','nda-10','nda-16');PROTECTED_DOCUMENT_IDS=(62,321,2)
DEV_CASE_IDS=tuple(f'contractnli:eced6528:test:{d}:{h}'for d in DEV_DOCUMENT_IDS for h in HYPOTHESIS_IDS)
ARCHIVE_SHA='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
def require(value,code):
 if not value:raise ValueError(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def normalized(text):return ' '.join(text.casefold().split())
def filename_key(text):return ' '.join(unicodedata.normalize('NFKC',text.replace('\\','/').rsplit('/',1)[-1]).casefold().split())
def unique(rows):
 out={}
 for k,v in rows:require(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
 return out
def read_ref(ref,project=None):
 require(type(ref)is dict and set(ref)=={'path','bytes','sha256'}and type(ref['path'])is str and type(ref['bytes'])is int and ref['bytes']>=0 and type(ref['sha256'])is str and len(ref['sha256'])==64,'EXACT_REFERENCE_REQUIRED');p=Path(ref['path']);p=p if p.is_absolute()else (Path(project)if project is not None else WORKDIR/'project')/p;require(p.absolute()==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents)),'CANONICAL_REGULAR_SOURCE_REQUIRED');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb')as f:
  before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode),'REGULAR_SOURCE_REQUIRED');require(before.st_size==ref['bytes'],'SOURCE_SIZE_BEFORE_READ_MISMATCH');b=f.read(ref['bytes']+1);after=os.fstat(f.fileno())
 require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)and len(b)==ref['bytes']and sha(b)==ref['sha256'],'STABLE_SOURCE_SHA_SIZE_MISMATCH');return b
def load_ref(ref,project=None):return json.loads(read_ref(ref,project),object_pairs_hook=unique)
def ref(path):
 p=Path(path);b=p.read_bytes();return {'path':p.relative_to(WORKDIR/'project').as_posix()if p.is_relative_to(WORKDIR/'project')else str(p),'bytes':len(b),'sha256':sha(b)}
def put_bytes(path,body):
 p=Path(path);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb')as f:f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(d)
 finally:os.close(d)
 return ref(p)
def put(path,v):return put_bytes(path,json.dumps(v,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n')
def import_source(ref,name,project=None):
 b=read_ref(ref,project);p=Path(ref['path']);p=p if p.is_absolute()else (Path(project)if project is not None else WORKDIR/'project')/p;spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),m.__dict__);return m

def validate_document(d):
 fields={'document_id','record_ordinal','source_group_sha256','source_document_sha256','normalized_document_sha256','source_filename_key_sha256','evidence'};require(type(d)is dict and set(d)==fields and type(d['document_id'])is int and type(d['record_ordinal'])is int,'EXACT_DOCUMENT_FEATURE_SCHEMA');units=d['evidence'];require(type(units)is list and 1<=len(units)<=MAX_UNITS,'SOURCE_UNIT_COUNT_CAP');end=0
 for i,u in enumerate(units):
  require(type(u)is dict and set(u)=={'unit_id','sentence','start','end'}and type(u['unit_id'])is int and u['unit_id']==i and type(u['start'])is int and type(u['end'])is int and u['start']==end and type(u['sentence'])is str and u['sentence']and u['end']==end+len(u['sentence']),'EXACT_CONTIGUOUS_SOURCE_CATALOG');require(len(u['sentence'].encode())<=MAX_UNIT_BYTES,'SOURCE_UNIT_UTF8_CAP');end=u['end']
 text=''.join(u['sentence']for u in units);require(text.strip()and len(text.encode())<=MAX_DOC_BYTES,'SOURCE_DOCUMENT_UTF8_CAP');require(sha(text.encode())==d['source_document_sha256']and sha(normalized(text).encode())==d['normalized_document_sha256'],'SOURCE_DOCUMENT_HASH_MISMATCH');return text

def load_private_features(path,expected_sha256,expected_ids):
 p=Path(path);b=read_ref({'path':str(p),'bytes':73969,'sha256':expected_sha256});require(len(b)==73969 and expected_sha256=='73443811bc58206012d6abbb1d1e738418d99a691706f19e9e1966722abdd21f' and sha(b)==expected_sha256,'EXACT_BOUNDED_PRIVATE_FEATURE_BANK');bank=json.loads(b,object_pairs_hook=unique);require(set(bank)=={'schema_version','epoch','kind','role','source_archive_sha256','documents','cases'}and bank['schema_version']==1 and type(bank['epoch'])is int and bank['epoch']==44 and bank['kind']==KIND and bank['role']=='dev','EXACT_PRIVATE_BANK_SCHEMA');docs=bank['documents'];cases=bank['cases'];require(tuple(expected_ids)==DEV_CASE_IDS and bank['source_archive_sha256']==ARCHIVE_SHA,'FROZEN_DEV_IDENTITIES_AND_ARCHIVE_REQUIRED');require(type(docs)is list and len(docs)==4 and len({d['document_id']for d in docs})==4 and type(cases)is list and len(cases)==12 and [c['id']for c in cases]==list(expected_ids)and len(set(expected_ids))==12,'EXACT_FOUR_DOCUMENT_TWELVE_PAIR_DESIGN');require(tuple(d['document_id']for d in docs)==DEV_DOCUMENT_IDS,'ONLY_FROZEN_DEV_DOCUMENTS_NO_PROTECTED_INPUTS');by={d['document_id']:d for d in docs};texts={k:validate_document(d)for k,d in by.items()};require(len({d['normalized_document_sha256']for d in docs})==4 and all(d['source_group_sha256']==sha(('ContractNLI|'+bank['source_archive_sha256']+'|test|'+str(d['document_id'])).encode())for d in docs),'FOUR_DISTINCT_SOURCE_DOCUMENTS_AND_GROUP_BINDING');require(len({c['input_sha256']for c in cases})==12,'TWELVE_DISTINCT_INPUT_PAIRS');records=[];groups={}
 for c in cases:
  require(set(c)=={'id','document_id','hypothesis_id','input_sha256','claim'}and type(c['claim'])is str and c['claim'].strip()and len(c['claim'].encode())<=MAX_CLAIM_BYTES and type(c['document_id'])is int and c['document_id']in by and c['id']==f'contractnli:eced6528:test:{c["document_id"]}:{c["hypothesis_id"]}','EXACT_LINKED_CASE_FEATURE_SCHEMA');d=by[c['document_id']];text=texts[c['document_id']];require(sha(canonical({'claim':c['claim'],'document':text}))==c['input_sha256']and normalized(c['claim'])!=normalized(text),'EXACT_SOURCE_PAIR_HASH');r=dict(d,**{k:c[k]for k in ['id','hypothesis_id','input_sha256','claim']});records.append(r);groups.setdefault(c['document_id'],[]).append(c['hypothesis_id'])
 require(list(groups)==[d['document_id']for d in docs]and len({tuple(v)for v in groups.values()})==1 and all(tuple(v)==HYPOTHESIS_IDS for v in groups.values()),'EXACT_SHARED_THREE_HYPOTHESIS_DESIGN');return records

def assert_packed_input(claim,premise):
 require(type(claim)is str and claim.strip()and len(claim.encode())<=MAX_CLAIM_BYTES and type(premise)is str and premise.strip()and normalized(claim)!=normalized(premise),'NONEMPTY_ORIGINAL_INPUT_REQUIRED');return {'passed':True,'semantic_completeness_claim':False}
