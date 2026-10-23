"""Reproduce pure/injected engineering tests; no real sessions or model/native calls."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
O=Path(__file__).resolve().parent;S=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
entries=['candidate/epoch13/test_models.py','candidate/epoch13/test_context.py','controller/epoch13/test_loop.py'];proofs=[]
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
for rel in entries:
 p=S/rel;r=subprocess.run([sys.executable,'-B',str(p)],capture_output=True,text=True,env=env,timeout=60)
 assert r.returncode==0,(rel,r.stdout,r.stderr)
 proofs.append({'source':rel,'source_sha256':sha(p),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'tests':proofs,'source_review':'Controller diff against reviewed e11 changes only newsource/prior15ledger plus conservativeDEV retirement; inherited rawsource/scorer/DEV/runtimeadmission/premarkers/deadline/cleanup verified. Candidate tests use __new__ injected fake session and pure probabilities; context tests use actual BPE tokenization only and exact epoch6source.','coverage':['C0/E1/N2 config and label permutations','fullNeutral posterior and exacthalftieNo','invalid/nonfinite logits','raw singleton int64/mask/type0 feeds and graphnames','overflow/padding reject beforeforward','Unicode/whitespace/oversizefallback fullsource conservation','wholepair <s>A</s></s>B</s> serialization','DEVgain/proper/all3controls/errors/missing/nonfinite gates','prior15closed/CPU2/600paid0GPU0','DEV/CONF Popen/noPID conservative consumption','no retry/CONF onDEV/runtimefailure','separatephaseprocess deadline and ownedcleanup'], 'tests_are_engineering_not_benchmark_scores':True,'model_initializations_real_forwards_native_or_paid_calls':0}
p=O/'source-tests-independent-v1.json'
with p.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p),'suites':len(proofs)}))
