"""Download only immutable public model assets, or verify already present bytes."""
import argparse,hashlib,json
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parent

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 lock=json.loads((ROOT/'assets.lock.json').read_text())
 for row in lock['assets']:
  target=ROOT/row['path']
  if not target.resolve().is_relative_to(ROOT) or target.is_symlink():raise ValueError('Unsafe asset path')
  if not target.exists():
   if a.verify_only:raise FileNotFoundError(str(target))
   target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.download')
   try:
    with urllib.request.urlopen(row['url'],timeout=60) as response,temp.open('xb') as output:
     while chunk:=response.read(1024*1024):output.write(chunk)
    if temp.stat().st_size!=row['bytes'] or digest(temp)!=row['sha256']:raise ValueError('Downloaded asset identity mismatch')
    temp.replace(target)
   finally:
    if temp.exists():temp.unlink()
  if target.stat().st_size!=row['bytes'] or digest(target)!=row['sha256']:raise ValueError('Existing asset identity mismatch; preserve it and resolve explicitly')
  print(json.dumps({'path':row['path'],'sha256':row['sha256'],'status':'verified'}))

if __name__=='__main__':main()
