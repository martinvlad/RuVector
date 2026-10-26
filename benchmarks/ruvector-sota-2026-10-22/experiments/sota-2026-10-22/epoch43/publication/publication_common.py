"""E43 metadata only. No model, data-loader, evaluator or network imports."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import base64,fcntl,hashlib,json,os,re,stat,time
from archive_protocol import BASE,CP_SHA,FORBIDDEN,ROOTS,SCOPE,require,sha,git,same,relative,deny_old_object
W=Path('/tmp/ruvector-sota-2026-10-22/epoch43-cab16abb5795')
OWNER_SHA=None
OWNER_GENERATION=OWNER_PID=OWNER_TICKS=OWNER_EXPIRY=OPERATIONAL_SHA=None
OWNER_REF=OPERATIONAL_REF=None
MAIN='c44d7337c0c5ad2ecd2294178475387facb96516'
REPO='ruvnet/RuVector';BRANCH='benchmarks/ruvector-sota-2026-10-22'
CONTROL={'CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json'}
QUALIFICATION_LOGS={f'experiments/sota-2026-10-22/audit/epoch43/preparation/metadata_qualification_execpath_v2/{i}.{stream}'for i in range(3)for stream in('stdout','stderr')}
REVIEWED_HEADER='experiments/sota-2026-10-22/runtime/epoch43/research/cpp-httplib.h'

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
 require(op['epoch']==43 and op['generation']==6 and op['source_checkpoint']==BASE and op['workdir']==str(W),'Exact unmeasured E43 gen6 operational binding')
 require(op['first_SOURCE_parent']=='fadb176e645b8ba5ba87a6caf088444bac650e67'and op['old_reserve_journal_sha256']=='b962a860e8ee341ad0920c44b9b59ee1f2442aee12a5bbfd7593ada0904b11d3','Historical reserve bridge immutable')
 zero=json.loads(checked(op['pre_SOURCE_known_zero_review']['path'],op['pre_SOURCE_known_zero_review']))
 require(op['pre_SOURCE_known_zero_review']['sha256']=='03643fad0797d0c07721d6a05b811c8fe5d0904549fc67c375438467832e5e9d','Exact independent known-zero proof')
 require(zero['controlled_pre_SOURCE_handoff_allowed']is True and zero['known_zero_pre_SOURCE_scientific_state_verified']is True and zero['SOURCE_ever_published']is False and zero['source_slot_generation4_published_or_burned']is False and type(zero['actual_native_or_model_or_tokenizer_or_data_or_Gold_or_EVAL_calls'])is int and zero['actual_native_or_model_or_tokenizer_or_data_or_Gold_or_EVAL_calls']==0,'No previous SOURCE/experiment capability reset')
 expired=json.loads(checked(op['prior_generation5_expiry_review']['path'],op['prior_generation5_expiry_review']))
 require(op['prior_generation5_expiry_review']['sha256']=='ebec682d265b8b9e3a75af37d1a76a45a84483f5747515d771a58eb79e747100','Exact prior generation5 expiry proof')
 require(expired['checks_passed']is True and expired['guardian_closed']is True and expired['bounded_lease_expiry_and_physical_unlock_observed']is True and expired['actual_SOURCE_published']is False and expired['SOURCE_slot5_published_or_burned']is False and expired['new_SOURCE_journal_or_requests_present']is False and type(expired['actual_model_tokenizer_native_data_Gold_EVAL_calls_in_E43'])is int and expired['actual_model_tokenizer_native_data_Gold_EVAL_calls_in_E43']==0,'No previous Source/measurement or burned capability reset')
 review=json.loads(checked(op['actual_handoff_review']['path'],op['actual_handoff_review']))
 for key in('checks_passed','old_guardian_closed_and_lock_free_before_new_acquisition','new_generation6_guardian_held','no_guardian_overlap'):require(review.get(key)is True,'Actual nonoverlapping handoff proof '+key)
 require(review['previous_generation5_expiry_review_sha256']==op['prior_generation5_expiry_review']['sha256'],'Actual gen6 proof binds prior5 closure');ref=op['owner'];require(Path(ref['path']).parent==W/'lease-generation6','Current owner and release namespace');owner=json.loads(checked(ref['path'],ref))
 require(owner['generation']==6 and review['generation']==6 and review['epoch']==43 and same(review['owner'],ref),'Exact actual gen6 owner reference')
 require(op['old_nonce_abandoned_unburned_sha256']=='3608379e8233f72315c1b710c94875c7eb30bc5702ab1a6d5b8f01a56f05736b','Old nonce never reset/reused')
 OWNER_REF=ref;OWNER_SHA=ref['sha256'];OWNER_GENERATION=6;OWNER_PID=owner['pid'];OWNER_TICKS=owner['startticks'];OWNER_EXPIRY=owner['expires_unix'];OPERATIONAL_SHA=expected_sha;OPERATIONAL_REF=pin(path)
 return op

def require_operational():require(OPERATIONAL_SHA is not None and OWNER_GENERATION==6,'No default or older-generation operational fallback')
def owner_release_path():
 require_operational();return Path(OWNER_REF['path']).parent/'release.request'
def held_owner():
 require_operational();o=json.loads(checked(OWNER_REF['path'],OWNER_REF))
 require((o['pid'],o['startticks'],o['generation'],o['lock_device'],o['lock_inode'],o['expires_unix'])==(OWNER_PID,OWNER_TICKS,6,33,13626,OWNER_EXPIRY),'Current binding owner constants')
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
