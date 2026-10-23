"""Confirm public cached-diagnostic bytes and descriptive summary only; zero inference."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,tempfile
O=Path(__file__).resolve().parent;S=O.parents[1];R=S.parents[1];D=S/'candidate/epoch11/postrun'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
allow=D/'public-allowlist-v1.json';assert sha(allow)=='31ea6e2e4249ba0f3e40de1310d16818d11a395c707d38e8f720b19fb42a8ffc'
for x in load(allow)['files']:
 p=R/x['path'];assert p.resolve().is_relative_to(D) and not p.is_symlink() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256'];p.read_bytes().decode('utf8')
assert len(load(allow)['files'])==7
with tempfile.TemporaryDirectory(prefix='ruvector-e11-cached-audit-') as tmp:
 target=Path(tmp)/'diagnostic.json';r=subprocess.run(['python','-B',str(D/'build_diagnostic_v1.py'),'--root',str(R),'--annotations',str(O/'development-evidence-projection-v1.json'),'--output',str(target)],capture_output=True,text=True,check=True,timeout=30)
 assert target.read_bytes()==(D/'diagnostic-v1.json').read_bytes()
 findings=Path(tmp)/'findings.json';rr=subprocess.run(['python','-B',str(D/'build_findings_v1.py'),'--diagnostic',str(target),'--output',str(findings)],capture_output=True,text=True,check=True,timeout=30)
 assert findings.read_bytes()==(D/'findings-v1.json').read_bytes()
f=load(D/'findings-v1.json');assert f['status']=='REJECTED_DEV_GATE' and f['official_score'] is None and f['official_rank'] is None
assert not any(f['frozen_gate_failure'][k] for k in ['primary_two_correct_gain_vs_each_control','proper_nonincrease_vs_all_controls'])
assert load(O/'postrun-independent-v1.json')['checks_passed']
proof={'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'public_allowlist_sha256':sha(allow),'public_files_reviewed':7,'diagnostic_sha256':sha(D/'diagnostic-v1.json'),'findings_sha256':sha(D/'findings-v1.json'),'exact_byte_replay_both':True,'independent_diagnostic_review_sha256':sha(O/'postrun-independent-v1.json'),'interpretation':'All3selectors collapse toYes/E onall24. RetainingNeutral inrawreadout excludes discarded-Neutral mechanism for thisrun; source-conversion fidelity versus legal-domain semantic competence remain unmeasured alternatives. Nativeannotation retention advantage does not rescue fixed all-controls gate. No causalarchitecture/benchmarkgeneralization claim.','limits':'8correlated documentgroups, exposedDEV, unknownpretrainingoverlap, unverifiedupstreamweightconversionrevision/mixedtrainingterms; noCONF use, fitting, candidates, model/nativecalls or paidwork.','candidate_manifest_unchanged':sha(S/'candidate/epoch11/proposal-manifest.json'),'official_score':None,'official_rank':None,'champions_unchanged':True,'new_inference_native_fit_paid_calls':0}
p=O/'postrun-findings-independent-v1.json'
with p.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p)}))
