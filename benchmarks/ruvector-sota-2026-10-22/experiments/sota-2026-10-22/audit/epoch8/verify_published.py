"""Read-only public Git identities/status plus local cleanup; no inference."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
import argparse,fcntl,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--commit",required=True);ap.add_argument("--tree",required=True);ap.add_argument("--leaves",type=int,required=True);ap.add_argument("--checkpoint",type=int,required=True);cli=ap.parse_args()

OUT=Path(__file__).resolve().parent;S=OUT.parents[1]
P=S/'epoch8/publication';STAGE=P/'stage'
COMMIT=cli.commit
TREE=cli.tree
PARENT='7aec0e09052ed478ac4aea2a31e8fef6508436cd'
MAIN='46d816ddc4c2a8a06cd3613534a79b1d557d858b'
API='https://api.github.com/repos/ruvnet/RuVector/'
def get(url):
    with urlopen(Request(url,headers={'User-Agent':'RuVector-independent-readonly-audit','Accept':'application/vnd.github+json'}),timeout=20) as response:
        assert response.status==200
        raw=response.read()
    return raw
def js(url):return json.loads(get(url))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bypath(tree):
    assert not tree.get('truncated',False)
    return {x['path']:x for x in tree['tree']}

manifest=json.loads((P/'publication-map.json').read_text())
expected={x['path']:x for x in manifest['files']};assert len(expected)==cli.leaves
with ThreadPoolExecutor(max_workers=4) as pool:
    jobs=[pool.submit(js,API+path) for path in ['git/commits/'+COMMIT,'git/refs/heads/main','git/refs/heads/benchmarks/ruvector-sota-2026-10-22','git/trees/'+TREE,'git/trees/'+manifest['base_tree']]]
    commit,main,branch,root,oldroot=[job.result() for job in jobs]
assert commit['sha']==COMMIT and commit['tree']['sha']==TREE and [p['sha'] for p in commit['parents']]==[PARENT]
assert main['object']['sha']==MAIN and branch['object']['sha']==COMMIT
r=bypath(root);o=bypath(oldroot)
assert r.keys()==o.keys()
assert all(r[k]==o[k] for k in r if k!='benchmarks')
with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(js,API+'git/trees/'+r['benchmarks']['sha'])
    b=pool.submit(js,API+'git/trees/'+o['benchmarks']['sha'])
    bench,oldbench=a.result(),b.result()
nb,ob=bypath(bench),bypath(oldbench)
assert nb.keys()==ob.keys()
target='ruvector-sota-2026-10-22'
assert all(nb[k]==ob[k] for k in nb if k!=target)
sub=js(API+'git/trees/'+nb[target]['sha']+'?recursive=1');files={k:v for k,v in bypath(sub).items() if v['type']=='blob'}
assert files.keys()==expected.keys()
for name,x in expected.items():assert files[name]['sha']==x['git_blob_sha1'] and files[name]['size']==x['bytes'] and files[name]['mode']=='100644'
rawnames=['CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json','experiments/sota-2026-10-22/epoch8/EPOCH_MANIFEST.json','experiments/sota-2026-10-22/audit/epoch8/final-publication-review-v1.json']
prefix='https://raw.githubusercontent.com/ruvnet/RuVector/'+COMMIT+'/benchmarks/'+target+'/'
with ThreadPoolExecutor(max_workers=4) as pool:raws=list(pool.map(lambda n:get(prefix+n),rawnames))
for name,raw in zip(rawnames,raws):assert raw==(STAGE/name).read_bytes() and hashlib.sha256(raw).hexdigest()==expected[name]['sha256']
cont,active,checkpoint,epoch,review=[json.loads(raw) for raw in raws]
assert not cont['goal_met'] and not cont['active_run']['experiments_active'] and cont['execution_observed']['native_corpus_attempts_including_failed_request']==epoch['budget']['lifetime_native_attempts']
assert active['state'].startswith('COMPLETE') and not active['experiments_active']
assert epoch==json.loads((STAGE/'experiments/sota-2026-10-22/epoch8/EPOCH_MANIFEST.json').read_text())
assert len(checkpoint['project_files'])==cli.checkpoint and cont['checkpoint_manifest_sha256']==hashlib.sha256(raws[2]).hexdigest()
owner=json.loads((S/'epoch8/lock-owner.json').read_text())
phase_pids={}
for phase in ('development','confirmation'):
    run=S/'epoch8/project/experiments/sota-2026-10-22/epoch8/runs'/phase
    runtime=json.loads((run/'runtime.json').read_text())
    phase_pids[phase]=[runtime['pid'],*runtime['native_child_pids']]
pids=[*dict.fromkeys(pid for group in phase_pids.values() for pid in group),owner['pid']]
assert all(not Path('/proc',str(pid)).exists() for pid in pids[:-1]),pids
supervisor=Path('/proc',str(owner['pid']),'stat')
supervisor_state=supervisor.read_text().rsplit(')',1)[1].split()[0] if supervisor.exists() else 'ABSENT'
assert supervisor_state in ('Z','X','ABSENT'),supervisor_state
with (S/'.loop.lock').open('rb') as handle:
    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.flock(handle,fcntl.LOCK_UN)
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'actual_published_commit':COMMIT,'actual_published_tree':TREE,'actual_parent_commit':PARENT,'branch_ref_exact':True,'actual_main_unchanged':MAIN,'all_public_Git_blob_SHA1_sizes_modes_verified':len(expected),'all_root_entries_except_benchmarks_unchanged':True,'all_benchmarks_siblings_except_checkpoint_unchanged':True,'final_local_publication_map_sha256':sha(P/'publication-map.json'),'raw_immutable_readbacks':[{'path':n,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for n,raw in zip(rawnames,raws)],'checkpoint_project_files':cli.checkpoint,'terminal_state':active['state'],'official_SOTA_established':False,'confirmation96_model_consumed':epoch['confirmation_consumed'],'worker_and_native_child_PIDs_absent':pids[:-1],'supervisor_PID':owner['pid'],'supervisor_state':supervisor_state,'supervisor_live_or_holding_lock':False,'cleanup_review_diagnostic':'Initial review correctly found no worker/nativechild but supervisor/proc persists as exitedZ PPid1; use explicit stoppedstate plus actual lockrelease, notfalse supervisorabsence.','exclusive_lock_nonblocking_reacquire_and_release_pass':True,'prior9plusactual_epoch8_closed_lifetime':epoch['budget']['lifetime_native_attempts'],'models_native_paid_calls_or_external_writes_by_auditor':0,'scope':'Publication and stopped-state evidence verified read-only; no futureexecution or officialplacement claim.'}
f=OUT/'published-epoch8-independent-review-v1.json'
with f.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(f),'commit':COMMIT,'public_files':len(expected),'main_unchanged':MAIN,'lock_released':True}))
