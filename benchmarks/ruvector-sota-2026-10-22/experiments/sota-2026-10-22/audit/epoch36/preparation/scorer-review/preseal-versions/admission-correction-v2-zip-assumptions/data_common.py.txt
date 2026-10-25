"""E36 authored engineering identity utilities; no benchmark data access."""
import hashlib,json,math,os
from pathlib import Path
SOURCE_CHECKPOINT='d73fcce4c45f7d8f6f1c5bfbf3599ceddf560be3'
CLASSES=['entailment','contradiction','not_mentioned']
NATIVE_ORDER=['entailment','not_mentioned','contradiction']
GOLD_NAMES={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
# Authored CASE_PROPOSAL identity/label mapping independently reviewed before
# any runtime measurement, hashed as canonical sorted UTF8 JSON. This authenticates
# retained joined records without traversing the oracle a second time.
AUTHORED_LABEL_MAP_SHA256='285e0a995bf0243247739aee128d28c20df706420ddcfc888942ea21dde4aa49'
def require(value,message):
    if not value:raise ValueError(message)
def digest(value):return hashlib.sha256(value).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(value):return ' '.join(value.casefold().split())
def finite(value):return type(value)in(int,float)and math.isfinite(value)
def unique_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate JSON key');result[key]=value
    return result
def read(path,expected_sha=None,expected_bytes=None):
    path=Path(path);require(path.is_absolute()and path==path.resolve()and not path.is_symlink(),'Absolute materialized nonsymlink path required')
    raw=path.read_bytes();require(expected_sha is None or digest(raw)==expected_sha,'SHA mismatch: '+str(path))
    require(expected_bytes is None or len(raw)==expected_bytes,'Bytes mismatch: '+str(path))
    return json.loads(raw,object_pairs_hook=unique_object)
def identity(path):
    path=Path(path);require(path.is_file()and not path.is_symlink(),'Regular nonsymlink evidence required')
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':digest(raw)}
def write_new(path,value):
    path=Path(path);body=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as f:f.write(body);f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def expected(role):
    require(role=='engineering','E36 has no benchmark role')
    return [(f'epoch36:cc0:paired-reader:{i:02}',-36000-i,f'e36-h{i:02}')for i in range(1,10)]
