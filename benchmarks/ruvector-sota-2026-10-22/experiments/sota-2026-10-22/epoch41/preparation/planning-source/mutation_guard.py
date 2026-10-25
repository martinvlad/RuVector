import argparse,base64,fcntl,hashlib,json,os,time,re,stat
from pathlib import Path
G=Path('/tmp/ruvector-sota-2026-10-22/epoch41-7a40daab6ad7');S=Path('/tmp/ruvector-sota-2026-10-22/epoch41-7a40daab6ad7')
def guard():
 assert hashlib.sha256((G/'owner.json').read_bytes()).hexdigest()=='e17ab327cf6d820e4bdc03b85b1f5aab31aa0f9b55debe38896d5b0654f5ec28';o=json.loads((G/'owner.json').read_text());assert (o['pid'],o['startticks'],o['lock_inode'],o['expires_unix'])==(124007, 29209782, 13626, 1792979195.910732);assert o['run_id']=='epoch41-7a40daab6ad7' and o['generation']==1 and o['kernel_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and o['PID_namespace']==os.readlink('/proc/self/ns/pid');p=o['pid'];st=Path(f'/proc/{p}/stat').read_text().split(') ')[1].split();assert int(st[19])==o['startticks'] and st[0] not in ('Z','X')
 assert not (G/'release.request').exists() and time.time()<o['expires_unix']
 fd=Path(f'/proc/{p}/fd/3');fs=fd.stat();ls=Path(o['lock']).stat();assert fs.st_ino==o['lock_inode']==ls.st_ino and fs.st_dev==ls.st_dev
 assert os.sched_getaffinity(p)=={0,1}
 rows=Path('/proc/locks').read_text().splitlines();assert any('FLOCK' in x and 'WRITE' in x and x.split()[4]==str(p) and tuple(int(y,16) for y in x.split()[5].split(':')[:2])==(os.major(ls.st_dev),os.minor(ls.st_dev)) and x.split()[5].endswith(':'+str(o['lock_inode'])) for x in rows)
 with open(o['lock'],'a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise AssertionError('exclusive owner absent')
 return o
def append(x):
 with (S/'mutation-journal.jsonl').open('a') as f:f.write(json.dumps(x,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 fd=os.open(S,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['intent','response','guard','reserve']);a.add_argument('--id');a.add_argument('--kind');a.add_argument('--payload');n=a.parse_args();o=guard()
 if n.mode=='guard':print(json.dumps({'held':True,'pid':o['pid'],'ticks':o['startticks']}));raise SystemExit
 rows=[json.loads(x) for x in (S/'mutation-journal.jsonl').read_text().splitlines()] if (S/'mutation-journal.jsonl').exists() else []
 if n.mode=='reserve':
  assert re.fullmatch(r'[A-Za-z0-9_-]{1,100}',n.id or '')
  assert not any(x['id']==n.id for x in rows),'duplicate mutation ID'
  assert all(any(y['id']==x['id'] and y['phase']=='response' and y['payload'].get('ok') for y in rows) for x in rows if x['phase']=='intent'),'uncertain earlier mutation'
  d=S/'mutation-requests';d.mkdir(mode=0o700,exist_ok=True);assert not d.is_symlink() and stat.S_ISDIR(d.stat().st_mode)
  f=d/(n.id+'.json');fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.fsync(fd);os.close(fd)
  for parent in [d,S]:
   df=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(df);os.close(df)
  print(json.dumps({'reserved_unique_request':str(f),'id':n.id}));raise SystemExit
 payload=json.loads(base64.b64decode(n.payload)); prior=[x for x in rows if x['id']==n.id]
 if n.mode=='intent':
  assert not prior,'duplicate mutation';assert all(any(y['id']==x['id'] and y['phase']=='response' and y['payload'].get('ok') for y in rows) for x in rows if x['phase']=='intent'),'uncertain earlier mutation'
 else:assert len(prior)==1 and prior[0]['phase']=='intent','response without unique intent'
 append({'id':n.id,'phase':n.mode,'kind':n.kind,'time':time.time(),'owner':o['pid'],'payload':payload});print(json.dumps({'recorded':n.id,'phase':n.mode}))
