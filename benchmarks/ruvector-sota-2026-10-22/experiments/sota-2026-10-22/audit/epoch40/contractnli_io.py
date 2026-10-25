"""Source-bound stdlib references and exclusive durable metadata writes."""
import hashlib,json,os
from pathlib import Path
KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT';EPOCH=40;SOURCE='2cf5aba60a050079506a5e9aa5463f44c1efcd5a'
def require(v,message):
 if not v:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def unique(pairs):
 out={}
 for k,v in pairs:
  require(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
 return out
def raw_ref(path):
 p=Path(path);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def read_ref(r,project=None):
 require(type(r)is dict and set(r)=={'path','bytes','sha256'}and type(r['bytes'])is int and r['bytes']>=0,'EXACT_SOURCE_REFERENCE_REQUIRED');p=Path(r['path'])
 if not p.is_absolute():require(project is not None,'PROJECT_ROOT_REQUIRED');p=Path(project)/p
 require(p.is_file()and not p.is_symlink(),'REGULAR_REFERENCE_REQUIRED');b=p.read_bytes();require(len(b)==r['bytes']and sha(b)==r['sha256'],'REFERENCE_HASH_SIZE_MISMATCH');return b

def load_ref(r,project=None):return json.loads(read_ref(r,project),object_pairs_hook=unique)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def put(path,value):
 p=Path(path);b=json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n';fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 finally:
  d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(d)
  finally:os.close(d)
 return raw_ref(p)
def envelope(v):require(type(v)is dict and type(v.get('schema_version'))is int and v['schema_version']==1 and type(v.get('epoch'))is int and v['epoch']==40 and v.get('kind')==KIND and v.get('phase')=='dev','E40_DEV_ENVELOPE_REQUIRED')
def command_ref(path,project):
 p=Path(path);p=p if p.is_absolute()else Path(project)/p;p=p.resolve();r=raw_ref(p);root=Path(project).resolve()
 if p.is_relative_to(root):r['path']=p.relative_to(root).as_posix()
 return r

def same_fact(a,b):
 """Recursive JSON fact equality preserving bool/int/float and container types."""
 if type(a)is not type(b):return False
 if type(a)is dict:return set(a)==set(b)and all(same_fact(a[k],b[k])for k in a)
 if type(a)is list:return len(a)==len(b)and all(same_fact(x,y)for x,y in zip(a,b))
 return a==b
