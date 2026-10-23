from pathlib import Path
import json,hashlib,sys
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch13';pub=e/'publication';st=pub/'stage'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
report_rel='experiments/sota-2026-10-22/audit/epoch13/final-publication-review-v1.json';report=json.loads((r/report_rel).read_text());assert report['checks_passed'];allow={x['path']:x for x in report['remaining_exact_allowed_additions']};assert len(allow)==3 and report['allowed_final_addition_count']==4;assert report['allow_this_report_at']==report_rel;allow[report_rel]={'path':report_rel,'bytes':(r/report_rel).stat().st_size,'sha256':sha((r/report_rel).read_bytes())};assert len(sys.argv[1:])==len(set(sys.argv[1:]))==4 and set(sys.argv[1:])==set(allow),'Require exact independently allowed four proofs'
m=json.loads((st/'CHECKPOINT_MANIFEST.json').read_text());files={x['path']:x for x in m['project_files']}
for rel in sys.argv[1:]:
 src=r/rel;b=src.read_bytes();b.decode('utf8');x=allow[rel];assert len(b)==x['bytes'] and sha(b)==x['sha256'];dst=st/rel;assert rel not in files and not dst.exists(),'Proof already staged';dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b);files[rel]={'path':rel,'bytes':len(b),'sha256':sha(b)}
m['project_files']=[files[q] for q in sorted(files)];save(st/'CHECKPOINT_MANIFEST.json',m)
c=json.loads((st/'CONTINUATION.json').read_text());c['checkpoint_manifest_sha256']=sha((st/'CHECKPOINT_MANIFEST.json').read_bytes());save(st/'CONTINUATION.json',c)
p=json.loads((pub/'publication-map.json').read_text());entries=[]
for f in sorted(st.rglob('*')):
 if f.is_file():
  b=f.read_bytes();entries.append({'path':str(f.relative_to(st)),'bytes':len(b),'sha256':sha(b),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
p['files']=entries;p['checkpoint_project_files']=len(files);p['new_project_files']=len(files)-1847;save(pub/'publication-map.json',p);print(json.dumps({'public_files':len(entries),'checkpoint_files':len(files),'bytes':sum(x['bytes'] for x in entries)}))
