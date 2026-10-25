"""Independent E38 identity utilities. No model, candidate, or benchmark import."""
import hashlib,json,math,os
from pathlib import Path
SOURCE_CHECKPOINT='7c50ba99848f6a13707eeec6c4947291a8478e5c'
KIND='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
CLASSES=['entailment','contradiction','not_mentioned']
NATIVE_LABELS=['Contradiction','NotMentioned','Entailment']
GOLD_NAMES={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
CANONICAL_LABELS=['Entailment','Contradiction','NotMentioned']
AUTHORED_LABEL_MAP_SHA256='2245ffb93510ec483095cb64f5e7483b46b3a28b799720a36aabb58e2414b149'
ROOT_CONTRACT_REF={'path':'experiments/sota-2026-10-22/epoch38/preparation/ROOT_PROSPECTIVE_CONTRACT.v1.json','bytes':6846,'sha256':'226cd756b41c881e5131a175a470ac06c96ed158ffd9c5bc216d42b3cac41a67'}
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
 require(role=='engineering','No E38 benchmark role')
 return [(f'epoch38:cc0:typed-source:{i:02}',-38000-i,f'e38-h{i:02}')for i in range(1,13)]
