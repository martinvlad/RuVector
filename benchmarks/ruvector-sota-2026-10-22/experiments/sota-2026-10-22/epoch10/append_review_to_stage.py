from pathlib import Path
import json,hashlib,shutil,sys
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch10';pub=e/'publication';st=pub/'stage'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
m=json.loads((st/'CHECKPOINT_MANIFEST.json').read_text());files={x['path']:x for x in m['project_files']}
for rel in sys.argv[1:]:
 src=r/rel;b=src.read_bytes();b.decode('utf8');dst=st/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b);assert rel not in files or files[rel]['sha256']==sha(b)
 files[rel]={'path':rel,'bytes':len(b),'sha256':sha(b)}
m['project_files']=[files[q] for q in sorted(files)];save(st/'CHECKPOINT_MANIFEST.json',m)
c=json.loads((st/'CONTINUATION.json').read_text());c['checkpoint_manifest_sha256']=sha((st/'CHECKPOINT_MANIFEST.json').read_bytes());save(st/'CONTINUATION.json',c)
p=json.loads((pub/'publication-map.json').read_text());entries=[]
for f in sorted(st.rglob('*')):
 if f.is_file():
  b=f.read_bytes();entries.append({'path':str(f.relative_to(st)),'bytes':len(b),'sha256':sha(b),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
p['files']=entries;p['checkpoint_project_files']=len(files);p['new_project_files']=len(files)-1264;save(pub/'publication-map.json',p);print(json.dumps({'public_files':len(entries),'checkpoint_files':len(files),'bytes':sum(x['bytes'] for x in entries)}))
