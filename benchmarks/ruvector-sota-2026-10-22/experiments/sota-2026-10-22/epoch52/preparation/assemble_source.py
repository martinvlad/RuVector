"""Root source-only exact packet adoption; no scientific or external action."""
from pathlib import Path
import hashlib,json,os
W=Path(__file__).resolve().parent
R=W/'project';P=R/'experiments/sota-2026-10-22/epoch52';A=R/'experiments/sota-2026-10-22/audit/epoch52/preparation'
def load(p):return json.loads(Path(p).read_bytes())
def ref(p):
 p=Path(p);b=p.read_bytes();return dict(path=p.relative_to(R).as_posix() if p.is_relative_to(R) else str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def exact(row):
 p=Path(row['path']);assert p.is_file() and not p.is_symlink();b=p.read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'];return b
def put(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b;return ref(p)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 return ref(p)
def main(config_ref):
 cfg=json.loads(exact(config_ref));assert cfg['epoch']==52 and cfg['scientific_calls']==0
 adopted=[]
 for entry in cfg['copies']:
  dst=R/entry['destination'];assert any(dst.is_relative_to(R/'experiments/sota-2026-10-22'/s) for s in ['epoch52','audit/epoch52','runtime/epoch52'])
  assert '..' not in Path(entry['destination']).parts
  adopted.append(put(dst,exact(entry['source'])))
 return put(W/'SOURCE_PACKET_ADOPTION.actual.v1.json',(json.dumps(dict(schema_version=1,epoch=52,adopted=adopted,actual_scientific_calls=0,actual_Git_mutations=0,source_config=config_ref),indent=2,sort_keys=True)+'\n').encode())
