"""Independent E37 identity utilities. No model, candidate, or benchmark import."""
import hashlib,json,math,os
from pathlib import Path
SOURCE_CHECKPOINT='b4e9e4f7a8a40b95b87ed8e418435b2d5757bb0e'
KIND='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
CLASSES=['entailment','contradiction','not_mentioned']
NATIVE_LABELS=['Contradiction','NotMentioned','Entailment']
GOLD_NAMES={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
CANONICAL_LABELS=['Entailment','Contradiction','NotMentioned']
AUTHORED_LABEL_MAP_SHA256='ab9dfb6493806c877a6d3132db76f3fc53fe33e1ee338ab7323b5469a4a6ffbd'
ROOT_CONTRACT_REF={'path':'experiments/sota-2026-10-22/epoch37/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json','bytes':5055,'sha256':'13ffef77c48bcca8ea5c1c72826269b88b6ac3386358b03588819d414e7c920e'}
def require(value,message):
 if not value:raise ValueError(message)
def digest(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def finite(value):return type(value)in(int,float)and math.isfinite(value)
def unique_object(pairs):
 result={}
 for key,value in pairs:
  require(key not in result,'Duplicate JSON key');result[key]=value
 return result
def read(path,sha=None,bytes_=None):
 p=Path(path);require(p.is_absolute()and p==p.resolve()and p.is_file()and not any(x.is_symlink()for x in(p,*p.parents)),'Absolute regular nonsymlink evidence required')
 b=p.read_bytes();require(sha is None or digest(b)==sha,'Evidence SHA mismatch');require(bytes_ is None or len(b)==bytes_,'Evidence length mismatch')
 return json.loads(b,object_pairs_hook=unique_object,parse_constant=lambda _:(_ for _ in()).throw(ValueError('Nonfinite JSON constant')))
def identity(path):
 p=Path(path);b=p.read_bytes();require(p.is_file()and p==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents)),'Regular nonsymlink evidence required');return {'path':str(p),'bytes':len(b),'sha256':digest(b)}
def write_new(path,value):
 p=Path(path);require(p.is_absolute()and p.parent==p.parent.resolve()and not p.exists(),'Exclusive absolute output required')
 b=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_DIRECTORY);os.fsync(d);os.close(d)
def expected(role):
 require(role=='engineering','No E37 benchmark role')
 return [(f'epoch37:cc0:typed-source:{i:02}',-37000-i,f'e37-h{i:02}')for i in range(1,13)]
