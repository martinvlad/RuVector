"""One distinct archive publication; never executes models or old transactions."""
import json,hashlib,os,stat,re,base64,time,fcntl
from pathlib import Path,PurePosixPath
SCOPE='benchmarks/ruvector-sota-2026-10-22/'
NEW='recoveries/epoch42-publication-20261026/'
PARENT='4201146a603127e9a536d266e38058deec4c3658'
FORBIDDEN='486888de9602bbb5d817a55f707b4fcfd11c65e0'
W=Path('/tmp/ruvector-sota-2026-10-22/epoch42-archive-recovery-20261026T040538')
ARCHIVE=Path('/workspace/ruvector-epoch42-public-recovery.zip')
ARCHIVE_SHA='b1563d4bd7b8ea54e69f6a2d1047130b95a94748d58e83fabcf465431c64cbca'
ARCHIVE_GIT='22669777496cdcb3d957bbe237bb8e5b70f5fde5'
OLD_WAL=Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b/mutation-journal.jsonl')
OLD_WAL_SHA='9b37c2a5513a89e439e0fee44bc1c4ea142b48ff329c41288a47e554c054501b'
OWNER_SHA='b503f119766f65dd85c6eff140483e2140b1279a9e33b467ccce204f96d0297c'
TREE_CAP=175904
BLOB_CAP=8384512

def need(value,message):
 if not value:raise ValueError(message)
def encoded(v):return(json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(',',':'))).encode()
def pretty(v):return(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def relative(s):
 need(isinstance(s,str)and s and '\\'not in s and not PurePosixPath(s).is_absolute()and all(x not in('','.','..')for x in s.split('/')),'Unsafe relative path');return s
def canonical(p):
 p=Path(p).absolute();need(p==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents)),'Noncanonical path');return p
def body(p):
 p=canonical(p);need(stat.S_ISREG(p.stat().st_mode),'Regular file required');return p.read_bytes()
def parse(p):return json.loads(body(p))
def ref(p,path):
 b=body(p);return {'path':path,'bytes':len(b),'sha256':sha(b)}
def write(p,b):
 p=canonical(p);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def same(a,b):
 if type(a)is not type(b):return False
 if isinstance(a,dict):return set(a)==set(b)and all(same(a[k],b[k])for k in a)
 if isinstance(a,list):return len(a)==len(b)and all(same(x,y)for x,y in zip(a,b))
 return a==b

def held_owner():
 b=body(W/'owner.json');need(sha(b)==OWNER_SHA,'Original generation3 owner changed');o=json.loads(b)
 need((o['pid'],o['startticks'],o['lock_inode'],o['generation'],o['expires_unix'])==(129095,31124033,13626,3,1792991138.4223573),'Exact generation3 owner required')
 need(time.time()<o['expires_unix']and not(W/'release.request').exists(),'Owner expired/released')
 s=Path('/proc/129095/stat').read_text().rsplit(')',1)[1].split();need(s[0]not in('Z','X')and int(s[19])==31124033,'Owner not live')
 need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==o['kernel_boot_id']and os.readlink('/proc/129095/ns/pid')==o['PID_namespace'],'Boot/namespace changed')
 need(os.sched_getaffinity(129095)=={0,1},'CPU2 affinity changed');f=Path('/proc/129095/fd/3').stat();lock=canonical(o['lock']);l=lock.stat();need(f.st_dev==l.st_dev==33 and f.st_ino==l.st_ino==13626,'Owned FD3 lock identity changed')
 need(any('FLOCK' in x and 'WRITE' in x and x.split()[4]=='129095' and tuple(int(v,16)for v in x.split()[5].split(':')[:2])==(os.major(l.st_dev),os.minor(l.st_dev)) and int(x.split()[5].split(':')[2])==13626 for x in Path('/proc/locks').read_text().splitlines()),'Owned exact-device kernel FLOCK absent')
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise ValueError('Exclusive lock not held')
 finally:os.close(fd)
 need(sha(body(OLD_WAL))==OLD_WAL_SHA,'Original UNKNOWN journal changed')
 return o

def request_bytes(args):
 need(set(args)>={'content','encoding'},'Blob encoding required')
 if args['encoding']=='utf-8':return args['content'].encode('utf-8')
 need(args['encoding']=='base64','Unsupported encoding');return base64.b64decode(args['content'],validate=True)
def no_old_reference(value):
 if isinstance(value,dict):
  for k,v in value.items():
   if k in('sha','base_tree_sha','tree_sha','parent_sha','expected_sha'):need(v!=FORBIDDEN,'Forbidden old object reference')
   no_old_reference(v)
 elif isinstance(value,list):
  for v in value:no_old_reference(v)
def validate_request(kind,args,meta):
 need(args.get('repository_full_name')=='ruvnet/RuVector','Wrong repository');no_old_reference(args)
 if kind.endswith('github_create_blob'):
  b=request_bytes(args);identity=git(b);need(identity!=FORBIDDEN,'Forbidden decoded blob recreation');need(identity in{r['GitSHA']for r in meta['blobs']},'Unreviewed blob identity')
  row=next(r for r in meta['blobs']if r['GitSHA']==identity);need(len(b)==row['body_bytes']and sha(b)==row['body_sha256'],'Blob byte identity drift')
 elif kind.endswith('github_create_tree'):
  need(isinstance(args.get('tree_elements'),list)and 1<=len(args['tree_elements'])<=32,'Bounded tree group required')
  for e in args['tree_elements']:
   p=relative(e['path']);need(p.startswith(SCOPE)and(e['path'][len(SCOPE):]in('ACTIVE_RUN.json','CONTINUATION.json','CHECKPOINT_MANIFEST.json')or p.startswith(SCOPE+NEW)),'Recovery scope escape')
   need(e['mode']=='100644'and e['type']=='blob','Only public blob leaves')
   if 'content'in e:need(git(e['content'].encode())!=FORBIDDEN,'Forbidden inline old object')
   need(e.get('sha')!=FORBIDDEN,'Forbidden tree object')
 elif kind.endswith('github_create_commit'):need(args.get('parent_sha')==PARENT and args.get('additional_parent_shas',[])==[],'Sole original SOURCE parent required')
 elif kind.endswith('github_update_ref'):need(args.get('branch_name')=='benchmarks/ruvector-sota-2026-10-22'and args.get('expected_sha')==PARENT and args.get('force')is False,'Exact new recovery CAS only')
 else:raise ValueError('Unapproved mutation tool')

def tree_sha(rows):
 root={}
 for p,r in rows.items():
  relative(p);need(r['mode']=='100644'and r['type']=='blob','Only exact source blobs');node=root;parts=p.split('/')
  for name in parts[:-1]:node=node.setdefault(name,{})
  need(parts[-1]not in node,'Duplicate Git path');node[parts[-1]]=r['sha']
 def digest(node):
  values=[]
  for name,value in node.items():
   d=isinstance(value,dict);identity=digest(value)if d else value;values.append((name.encode()+(b'/'if d else b''),(b'40000'if d else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(identity)))
  b=b''.join(v for k,v in sorted(values));return hashlib.sha1(b'tree '+str(len(b)).encode()+b'\0'+b).hexdigest()
 return digest(root)
