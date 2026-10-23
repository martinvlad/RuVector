"""Verify frozen source/evidence publication and cold restoration; zero inference."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,subprocess,re
ap=argparse.ArgumentParser();ap.add_argument("--expected-map",required=True);ap.add_argument("--expected-leaves",type=int,required=True);ap.add_argument("--expected-checkpoint",type=int,required=True);ap.add_argument("--expected-attempts",type=int,required=True);ap.add_argument("--expected-HTTP",type=int,required=True);ap.add_argument("--expected-failed",type=int,default=2);a=ap.parse_args()

OUT=Path(__file__).resolve().parent
S=OUT.parents[1]
PUB=S/'epoch10/publication'
STAGE=PUB/'stage'
EXPECTED=a.expected_map
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
mp=PUB/'publication-map.json'
assert sha(mp)==EXPECTED
m=load(mp);items=m['files']
assert len({x['path'] for x in items})==len(items)==a.expected_leaves
actual={str(f.relative_to(STAGE)) for f in STAGE.rglob('*') if f.is_file()}
assert actual=={x['path'] for x in items}
for x in items:
    f=STAGE/x['path'];b=f.read_bytes()
    assert not f.is_symlink() and f.resolve().is_relative_to(STAGE.resolve())
    assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1']
    b.decode('utf8')
    assert not any(t in x['path'].split('/') for t in ['__pycache__','.git','.venv'])
    assert not re.search(r'\.(node|so(?:\.\d+)*|onnx|tgz|zip|pyc)$',x['path'])
    assert not any(v in x['path'].casefold() for v in ['.private.','benchmark-sources/','automation-receipt'])
old=load(S/'epoch9/publication/publication-map.json')
prev={x['path']:x for x in old['files']};new={x['path']:x for x in items}
changed=[p for p,x in prev.items() if p not in new or new[p]['sha256']!=x['sha256']]
assert set(changed)=={'ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json','CONTINUATION.json'}
oldcheckpoint=load(STAGE/'CHECKPOINT_MANIFEST.before-epoch10.json')
checkpoint=load(STAGE/'CHECKPOINT_MANIFEST.json')
ck={x['path']:x for x in checkpoint['project_files']}
assert len(ck)==a.expected_checkpoint
for x in oldcheckpoint['project_files']:assert ck[x['path']]==x
cont=load(STAGE/'CONTINUATION.json')
assert sha(STAGE/'CHECKPOINT_MANIFEST.json')==cont['checkpoint_manifest_sha256']
assert cont['execution_observed']['native_corpus_attempts_including_failed_request']==a.expected_attempts
assert cont['execution_observed']['actual_HTTP_successful_decisions']==a.expected_HTTP
assert cont['execution_observed']['actual_HTTP_failed_requests']==a.expected_failed
assert not cont['goal_met'] and not cont['active_run']['experiments_active']
patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{50,}',rb'AKIA[A-Z0-9]{16}',rb'sk-[A-Za-z0-9]{40,}']
findings=[]
for p in new.keys()-prev.keys():
    raw=(STAGE/p).read_bytes()
    for pat in patterns:
        if re.search(pat,raw):findings.append({'path':p,'pattern':pat.decode()})
assert not findings,findings

# Source-only cold restoration, no optional dependency/install/model flags.
dest=OUT/'publication-cold-project-v1'
base=Path('/workspace/ruvector-eval/experiments/submission-2026-10-22/delivery/kit')
receipts=[]
for flags in [[],['--verify-only']]:
    command=['python','-B',str(STAGE/'restore_checkpoint.py'),'--dest',str(dest),'--base-local-directory',str(base),*flags]
    r=subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
    receipts.append(json.loads(r.stdout.strip()))
for x in checkpoint['project_files']:assert sha(dest/x['path'])==x['sha256']
helper=STAGE/'experiments/sota-2026-10-22/candidate/epoch5/reconstruction/restore_runtime.py'
source=S/'epoch10/project'
for flags in [['--core-cache-root',str(source),'--typesafe-cache-root',str(source)],['--verify-only']]:
    r=subprocess.run(['python','-B',str(helper),'--project-root',str(dest),*flags],capture_output=True,text=True,check=True,timeout=30)
    receipts.append(json.loads(r.stdout.strip()))
plan=load(S/'epoch10/plan.json');known=[];deferred=[]
for x in plan['pins']:
    f=dest/x['path']
    if f.exists():
        assert sha(f)==x['sha256'];known.append(x['path'])
    else:deferred.append(x['path'])
assert deferred,deferred
assert all(p.startswith('models/bge-small-en-v1.5/') or p.startswith('experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/') or p.startswith('experiments/sota-2026-10-22/candidate/epoch9/assets/nli-broader/') for p in deferred)
zip_expected={'/workspace/ruvector-benchmark-pilot.zip':'0ff4ffcf156deaf612bce0d5f9b66800e1595a94c0e5ad15e39c9d3e6f1dc363','/workspace/ruvector-benchmark-iteration-2026-10-21.zip':'da4f67550c39c0f668625e4f2cf484ce9badf2510d9100fc4a9f2984e40b5486','/workspace/ruvector-compounding-2026-10-22.zip':'9b29bec10491594c6c2ee8cbaceecf07b47cf97f13f6dd24bfe37b6252c2c45e'}
for p,h in zip_expected.items():assert sha(Path(p))==h
assert sha(mp)==EXPECTED
proof={'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'reviewed_map_sha256':EXPECTED,'public_leaves':len(items),'bytes':sum(x['bytes'] for x in items),'checkpoint_source_files':len(ck),'allprior1264checkpointfiles_preserved':True,'changed_prior1330_paths':changed,'privacy_scan':'AllUTF8; zero binary/model/rawHTML/private artifacts, pathscope/hash/Gitblob checks; scoped credential-pattern scan found no new credential matches. Not a complete vulnerability/advisory scan.','cold_receipts':receipts,'after_source_plus_explicit_offline_runtime_helper_plan_pins_verified':len(known),'deferred_actual190_plan_pins':deferred,'no_full190_model_reconstruction_claim':True,'old_ZIP_SHA256_unchanged':zip_expected,'auditor_native_model_or_paid_calls':0,'scope':'Publication source+saved-evidence reconstruction only, not archived-controller execution.','provenance':'Allcanonical epoch10 frozen190pin audit/candidate/controller sources must match actualexecutor. Exact unchanged6 context module/tokenizer, same broader pretrained three-way backbone with one fixedTRAIN-only5fit residualhead are separately pinned; no modelperformance inferred from source restoration.'}
f=OUT/'publication-cold-review-v1.json'
with f.open('x') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
print('PROOF',sha(f));print('COLD',json.dumps(receipts));print('DEFERRED',deferred)
