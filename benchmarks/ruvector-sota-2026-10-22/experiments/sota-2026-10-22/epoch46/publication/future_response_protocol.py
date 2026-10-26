"""Future-only local response primitives. No Git, guardian or study entrypoint."""
import json,os
from pathlib import Path
CURRENT_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch46-d3aa1b569848/publication')
OLD_SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725')
RETIRED_OBJECTS={'486888de9602bbb5d817a55f707b4fcfd11c65e0','3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5'}
def require(ok,why):
 if not ok:raise ValueError(why)
def completed(rows):
 require(len(rows)%2==0,'Earlier mutation remains open')
 for a,b in zip(rows[::2],rows[1::2]):require(a['phase']=='intent'and b['phase']=='response'and a['id']==b['id']and b['payload'].get('ok')is True,'Earlier mutation uncertain')
 require(len({a['id']for a in rows[::2]})==len(rows)//2,'Earlier duplicate ID')
def response_intent(rows,id,kind):
 require(bool(rows),'Missing intent');completed(rows[:-1]);last=rows[-1]
 require(last['phase']=='intent'and last['id']==id and last['kind']==kind and sum(r['id']==id for r in rows)==1,'Exactly own current intent required');return last
def capture_raw_reply(path,reply):
 """Called BEFORE owner/guard re-entry and BEFORE un()/ACK parsing."""
 path=Path(path);require(path.is_absolute()and '..'not in path.parts and path.resolve()==path and not path.is_relative_to(OLD_SCOPE),'Fresh E46 transport namespace only')
 require(path.is_relative_to(CURRENT_SCOPE/'requests') and path.name.startswith(('e46-source-g11-','e46-final-g11-')) and path.name.endswith('.raw-tool-return.json'),'Only exact current E46 raw namespace')
 require(not any(p.is_symlink()for p in(path,*path.parents)),'No symlink');raw=(json.dumps(reply,sort_keys=True,allow_nan=False)+'\n').encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(d)
 finally:os.close(d)
 return raw
