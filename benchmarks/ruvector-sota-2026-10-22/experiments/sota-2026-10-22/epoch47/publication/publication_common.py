"""E47 metadata only. No model, data-loader, evaluator or network imports."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import base64,fcntl,hashlib,json,os,re,stat,time
from archive_protocol import BASE,CP_SHA,FORBIDDEN,FORBIDDEN_OBJECTS,ROOTS,SCOPE,require,sha,git,same,relative,deny_old_object,verify_70_projection
W=Path('/tmp/ruvector-sota-2026-10-22/epoch47-143d1a78ea73')
OWNER_SHA=None
OWNER_GENERATION=OWNER_PID=OWNER_TICKS=OWNER_EXPIRY=OPERATIONAL_SHA=None
OWNER_REF=OPERATIONAL_REF=None
MAIN='c44d7337c0c5ad2ecd2294178475387facb96516'
REPO='ruvnet/RuVector';BRANCH='benchmarks/ruvector-sota-2026-10-22'
CONTROL={'CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json'}
QUALIFICATION_LOGS={f'experiments/sota-2026-10-22/audit/epoch47/preparation/metadata_qualification_execpath_v2/{i}.{stream}'for i in range(3)for stream in('stdout','stderr')}
REVIEWED_HEADER='experiments/sota-2026-10-22/runtime/epoch47/research/cpp-httplib.h'

def body(p):
 p=Path(p);require(p.is_absolute(),'Absolute local metadata path required')
 require(all(not q.is_symlink()for q in (p,*p.parents)),'Symlink in metadata path')
 require(stat.S_ISREG(p.stat().st_mode),'Regular metadata file required');return p.read_bytes()
def parse(p):return json.loads(body(p))
def encoded(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def pin(p):
 b=body(p);return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def checked(p,r):
 b=body(p);require(type(r.get('bytes'))is int and len(b)==r['bytes']and sha(b)==r['sha256'],'Metadata identity differs');return b
def write(p,b):
 p=Path(p);require(p.is_absolute()and not p.is_symlink(),'Absolute non-symlink output');p.parent.mkdir(parents=True,exist_ok=True)
 require(all(not q.is_symlink()for q in (p.parent,*p.parent.parents)),'Output ancestor symlink')
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  with os.fdopen(fd,'wb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 finally:
  d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def public_text(path,b):
 relative(path);header=path==REVIEWED_HEADER and len(b)==173556 and sha(b)=='84c62154f57c14ce24e38ccb95d35d5757f6b9340c4b4bb9453f6c4cb0d5b5ad'
 require(Path(path).suffix in('.py','.js','.cjs','.json','.jsonl','.md','.txt','.toml','.yaml','.yml','.csv','.sh')or path in QUALIFICATION_LOGS or header,'Unreviewed public suffix or source exception')
 s=b.decode('utf-8');require('\x00'not in s,'Binary public text')
 require(not re.search(r'<(?:html|body|head)[\s>]',s,re.I),'Raw page body excluded')
 require(not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)',s),'Credential-like public text')
 return b
def configure(path,expected_sha):
 global OWNER_SHA,OWNER_GENERATION,OWNER_PID,OWNER_TICKS,OWNER_EXPIRY,OWNER_REF,OPERATIONAL_SHA,OPERATIONAL_REF
 raw=body(path);require(sha(raw)==expected_sha,'Explicit operational binding SHA');op=json.loads(raw)
 require(type(op['generation'])is int and op['generation']==12 and op['epoch']==47 and op['source_checkpoint']==BASE and op['workdir']==str(W),'Exact E47 current12 operational binding')
 require(op.get('scope')=='NEW_EPOCH47_SOURCE_AND_FINAL_ONE_DEV_BATCH' and op.get('retired_epoch46_science_immutable')is True,'Distinct new epoch, immutable prior science')
 ref=op['owner'];owner=json.loads(checked(ref['path'],ref));review=json.loads(checked(op['owner_review']['path'],op['owner_review']))
 require(ref['sha256']=='d2ce6bd948494ce0f2698b41b0658158584488bba5141324fdca150fbfe539fe' and ref['bytes']==701,'Exact current12 owner')
 require(Path(ref['path'])==W/'owner.json'and op['owner_review']['sha256']=='887c707506f3170d3f7f202d60717f00dc54c12da04f85b07c18914dd7d664df'and op['owner_review']['bytes']==7771,'Exact independent actual held12 proof')
 require(Path(ref['path']).is_relative_to(W)and not Path(ref['path']).is_relative_to(W/'project'),'Operational owner outside public project')
 require(review.get('decision')=='APPROVED_HELD_GUARDIAN12_CURRENT_OWNER_AND_EMPTY_OLD_SCOPES','Independent actual held12 decision')
 for key in('all_old_owned_process_groups_have_no_live_members','independent_same_inode_nonblocking_FLOCK_denied','no_release_requested_or_recorded'):require(review.get(key)is True,'Independent held-owner proof '+key)
 require(review['epoch']==47 and review['generation']==op['generation'] and same(review['owner'],ref),'Exact held-owner reference')
 require(owner['generation']==op['generation'] and owner['lock_device']==33 and owner['lock_inode']==13626 and owner['pid']==150294 and owner['startticks']==36360851,'Exact same physical lock and current12 process')
 OWNER_REF=ref;OWNER_SHA=ref['sha256'];OWNER_GENERATION=op['generation'];OWNER_PID=owner['pid'];OWNER_TICKS=owner['startticks'];OWNER_EXPIRY=owner['expires_unix'];OPERATIONAL_SHA=expected_sha;OPERATIONAL_REF=pin(path)
 return op

def require_operational():require(OPERATIONAL_SHA is not None and OWNER_GENERATION is not None,'Explicit current operational binding; no defaults')
def owner_release_path():
 require_operational();return Path(OWNER_REF['path']).parent/'release.request'
def held_owner():
 require_operational();o=json.loads(checked(OWNER_REF['path'],OWNER_REF))
 require((o['pid'],o['startticks'],o['generation'],o['lock_device'],o['lock_inode'],o['expires_unix'])==(OWNER_PID,OWNER_TICKS,OWNER_GENERATION,33,13626,OWNER_EXPIRY),'Current binding owner constants')
 require(o['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()and o['PID_namespace']==os.readlink('/proc/self/ns/pid'),'Boot/namespace changed')
 release=owner_release_path();require(time.time()<o['expires_unix']and not release.exists(),'Current owner expired/releasing; old release marker untouched')
 st=Path(f"/proc/{o['pid']}/stat").read_text().split(') ')[1].split();require(int(st[19])==o['startticks']and st[0]not in('Z','X'),'Owner not live')
 fs=Path(f"/proc/{o['pid']}/fd/3").stat();ls=Path(o['lock']).stat();require(fs.st_ino==ls.st_ino==13626 and fs.st_dev==ls.st_dev==33,'Exact FD3 lock identity')
 require(os.sched_getaffinity(o['pid'])=={0,1},'Owner affinity')
 require(any('FLOCK'in x and 'WRITE'in x and x.split()[4]==str(o['pid'])and x.split()[5]=='00:21:13626'for x in Path('/proc/locks').read_text().splitlines()),'Kernel FLOCK row absent')
 with open(o['lock'],'a')as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise ValueError('Exclusive owner not held')
 return o
def validate_request(kind,a):
 require(a.get('repository_full_name')==REPO,'Repository scope');deny_old_object(kind.split('github_')[-1],a)
 if kind.endswith('create_commit'):require(a.get('additional_parent_shas',[])==[],'Sole parent required')
 if kind.endswith('update_ref'):require(a.get('branch_name')==BRANCH and a.get('force')is False,'Dedicated scoped CAS only')
def tree_sha(entries):
 rows=sorted(entries,key=lambda x:(x['path']+('/'if x['type']=='tree'else'')).encode());b=b''.join((('40000'if r['type']=='tree'else r['mode'])+' '+r['path']).encode()+b'\0'+bytes.fromhex(r['sha'])for r in rows)
 return hashlib.sha1(b'tree '+str(len(b)).encode()+b'\0'+b).hexdigest()
def full_scope_sha(files):
 root={}
 for r in files:
  parts=relative(r['path']).split('/');d=root
  for p in parts[:-1]:d=d.setdefault(p,{})
  require(parts[-1]not in d,'Duplicate/overlapping tree path');d[parts[-1]]=r
 def build(d):return tree_sha([{'path':p,'type':'tree','mode':'040000','sha':build(v)}if 'sha'not in v else {**v,'path':p}for p,v in d.items()])
 return build(root)
