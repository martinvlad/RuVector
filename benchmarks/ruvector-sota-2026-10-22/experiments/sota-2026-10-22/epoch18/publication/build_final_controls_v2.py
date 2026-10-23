"""Append final continuation references without changing the published helper."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE/'project';E=ROOT/'experiments/sota-2026-10-22/epoch18'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def ident(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,value):
    with p.open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-label',required=True);ap.add_argument('--out-label',required=True);a=ap.parse_args()
    for label in [a.base_label,a.out_label]:
        assert label and all(c.isalnum()or c=='-'for c in label)
    final=read(E/'EPOCH_MANIFEST.json');assert final['source_epoch_closed']is True
    assert final['actual_execution']['allowed_further_epoch18_native_attempts']==0
    assert final['published_source_commit']=='19106bac59a336accc28e5731744e08be9a825f2'
    subprocess.run([sys.executable,'-B',str(SCOPE/'build_epoch18_metadata.py'),'final','--out-label',a.base_label],check=True)
    base=SCOPE/('capsule-'+a.base_label);out=SCOPE/('capsule-'+a.out_label);out.mkdir()
    c=read(base/'CONTINUATION.json');active=read(base/'ACTIVE_RUN.json')
    c['prior_published_base_commit']='19106bac59a336accc28e5731744e08be9a825f2'
    c['epoch18_frozen_study_scope']='Historical immutable premeasurement snapshot. Current actual state is epoch18_final; every epoch18 phase slot is permanently closed.'
    c['epoch18_final'].update(source_manifest=ident(E/'SOURCE_MANIFEST.json'),results=ident(E/'RESULTS.json'),
       used_identities=ident(E/'USED_IDENTITIES.json'),rejection_ledger=ident(E/'REJECTION_LEDGER.json'),
       independent_identity_retirement=ident(ROOT/'experiments/sota-2026-10-22/legal-transfer/epoch18/postrun-identity-retirement-v1.json'))
    c['official_result_status']='UNVERIFIED. Publisher status refresh partially FORBIDDEN; queue115 was never a rank.'
    active.update(checkpoint_parent='19106bac59a336accc28e5731744e08be9a825f2',
       owned_native_groups_closed=True,closed_at=read(E/'study-completion.json')['finished_at'])
    assert active['experiments_active']is False and active['native_allowed']==0
    for name in ['CHECKPOINT_MANIFEST.json']:
        with(out/name).open('xb')as f:f.write((base/name).read_bytes())
    put(out/'CONTINUATION.json',c);put(out/'ACTIVE_RUN.json',active)
    assert c['checkpoint_manifest_sha256']==sha(out/'CHECKPOINT_MANIFEST.json')
    print(json.dumps({'status':'DERIVED_CLOSED_CONTROLS_REQUIRE_EXACT_CAPSULE_REVIEW','controls':str(out),'native_allowed':0}))
if __name__=='__main__':main()
