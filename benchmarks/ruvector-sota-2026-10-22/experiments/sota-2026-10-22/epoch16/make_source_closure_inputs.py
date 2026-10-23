"""Declare immutable public sources plus exact model/native/licensed-data restores."""
from pathlib import Path
import json,hashlib,os

ROOT=Path(__file__).resolve().parents[3]
S=ROOT/'experiments/sota-2026-10-22'
E=S/'epoch16'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
    with p.open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write(chr(10));f.flush();os.fsync(f.fileno())

def main():
    kit=ROOT.parent/'kit';public={}
    def admit(row):
        value={k:row[k]for k in ['path','bytes','sha256']}
        if row['path']in public:assert public[row['path']]==value,row['path']
        public[row['path']]=value
    for name in ['CHECKPOINT_MANIFEST.json','KIT_MANIFEST.json']:
        for row in read(kit/name)['project_files']:admit(row)
    idx={x['path']:x for x in read(kit/'BASE_PUBLIC_MANIFEST.json')['files']}
    for name in read(kit/'BASE_DOWNLOADS.json')['paths']:admit(idx[name])
    skip={'declared-public.json','external-registry.json','source-closure-report.json','public-source-allowlist.before-native.json'}
    added=[]
    for rel in ['candidate/epoch16','controller/epoch16','legal-transfer/epoch16','audit/epoch16','epoch16']:
        for p in sorted((S/rel).rglob('*')):
            if not p.is_file() or '__pycache__'in p.parts or '/assets/'in str(p) or p.name in skip:continue
            row={'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
            admit(row);added.append(row)
    registry=read(S/'epoch15/external-registry.json')
    data={'path':'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json',
        'sha256':'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
        'bytes':7608211,'kind':'licensed_dataset_asset','license':'CC-BY-4.0',
        'source_commit':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'source_url':'https://raw.githubusercontent.com/stanfordnlp/contract-nli/eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/resources/contract-nli.zip',
        'archive_sha256':'e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b',
        'archive_member':'contract-nli/train.json',
        'provenance_manifest':{'path':'experiments/sota-2026-10-22/candidate/epoch3/publication/RESTORE_EPOCH3_DATA.json','sha256':'c3073e56747e89eadf3ab7ce4cc6c68838b561df82cdb9d023ba1206437606be'},
        'acquisition_helper':{'path':'experiments/sota-2026-10-22/candidate/epoch3/publication/restore_original_data.py','sha256':'03b716e9a225c5efa60e4aeab16df3c6d53906bd1d36edcc12f9514e34d68c5a'},
        'license_file':{'path':'experiments/sota-2026-10-22/epoch16/source-data-LICENSE.txt','sha256':'9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94'}}
    assert sha(ROOT/data['path'])==data['sha256'] and (ROOT/data['path']).stat().st_size==data['bytes']
    assert len(registry)==13;registry.append(data)
    for r in public.values():assert sha(ROOT/r['path'])==r['sha256'],r['path']
    put(E/'declared-public.json',sorted(public.values(),key=lambda x:x['path']))
    put(E/'external-registry.json',registry)
    put(E/'public-source-allowlist.before-native.json',{'schema_version':1,'files':added,
        'derived_guard_inputs_and_output_excluded_to_avoid_self_cycle':True,'model_native_calls':0})
    print(json.dumps({'public_paths':len(public),'external_assets':len(registry),'new_public_files':len(added)}))

if __name__=='__main__':main()
