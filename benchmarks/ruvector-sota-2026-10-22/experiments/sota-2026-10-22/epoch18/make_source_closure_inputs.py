"""Declare immutable public sources plus exact model/native/licensed-data restores."""
from pathlib import Path
import json,hashlib,os

ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch18'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
    with p.open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())

def main():
    kit=ROOT.parent/'kit';public={}
    def regular(p):
        assert p.is_file() and not p.is_symlink(),str(p)
        for parent in p.parents:
            assert not parent.is_symlink(),str(parent)
            if parent==ROOT:break
    def admit(row):
        regular(ROOT/row['path'])
        value={k:row[k]for k in ['path','bytes','sha256']}
        if row['path']in public:assert public[row['path']]==value,row['path']
        public[row['path']]=value
    for name in ['CHECKPOINT_MANIFEST.json','KIT_MANIFEST.json']:
        for row in read(kit/name)['project_files']:admit(row)
    idx={x['path']:x for x in read(kit/'BASE_PUBLIC_MANIFEST.json')['files']}
    for name in read(kit/'BASE_DOWNLOADS.json')['paths']:admit(idx[name])
    skip={'declared-public.json','external-registry.json','source-closure-report.json','public-source-allowlist.before-native.json'}
    added=[]
    for rel in ['candidate/epoch18','controller/epoch18','legal-transfer/epoch18','audit/epoch18','epoch18']:
        for p in sorted((S/rel).rglob('*')):
            if '__pycache__'in p.parts or '/assets/'in str(p) or p.name in skip:continue
            assert not p.is_symlink(),str(p)
            if not p.is_file():continue
            regular(p)
            row={'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
            admit(row);added.append(row)
    registry=read(S/'epoch17/external-registry.json')
    assert len(registry)==20 and len({x['path']for x in registry})==20
    for asset in registry:
        p=ROOT/asset['path'];regular(p)
        assert p.stat().st_size==asset['bytes'] and sha(p)==asset['sha256']
    for r in public.values():assert sha(ROOT/r['path'])==r['sha256'],r['path']
    put(E/'declared-public.json',sorted(public.values(),key=lambda x:x['path']))
    put(E/'external-registry.json',registry)
    put(E/'public-source-allowlist.before-native.json',{'schema_version':1,'files':added,
        'derived_guard_inputs_and_output_excluded_to_avoid_self_cycle':True,'model_native_calls':0})
    print(json.dumps({'public_paths':len(public),'external_assets':len(registry),'new_public_files':len(added)}))

if __name__=='__main__':main()
