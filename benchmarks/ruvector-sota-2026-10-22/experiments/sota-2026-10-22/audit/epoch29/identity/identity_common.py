"""Pure standard-library utilities for frozen document identity qualification."""
import hashlib
import json
import math
import unicodedata
from pathlib import Path

KIND = 'REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_BYTES = 7608211

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(value):
    return hashlib.sha256(value).hexdigest()

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def normalize(value):
    return ' '.join(value.casefold().split())

def model_text(normalized_text):
    return unicodedata.normalize('NFKC',normalized_text).casefold()

def pairs(items):
    result={}
    for key,value in items:
        require(key not in result,'Duplicate JSON key')
        result[key]=value
    return result

def read(path,expected_sha=None,expected_bytes=None):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve() and not path.is_symlink(),'Absolute materialized nonsymlink file required')
    raw=path.read_bytes()
    require(expected_sha is None or sha(raw)==expected_sha,'SHA mismatch: '+str(path))
    require(expected_bytes is None or len(raw)==expected_bytes,'Byte mismatch: '+str(path))
    return json.loads(raw,object_pairs_hook=pairs)

def identity(path):
    path=Path(path);raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':sha(raw)}

def write_new(path,value):
    import os
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def cosine(a,b):
    return math.fsum(x*y for x,y in zip(a,b))/(math.sqrt(math.fsum(x*x for x in a))*math.sqrt(math.fsum(y*y for y in b)))

def quantile(values,q):
    if not values:return None
    a=sorted(values);x=(len(a)-1)*q;l=math.floor(x);h=math.ceil(x)
    return a[l]+(x-l)*(a[h]-a[l])
