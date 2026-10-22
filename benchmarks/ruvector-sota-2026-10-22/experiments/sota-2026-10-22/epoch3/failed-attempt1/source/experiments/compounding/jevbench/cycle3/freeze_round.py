"""Freeze one separately bounded cycle3 attempt after synthetic tests, before HTTP."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
role=lambda path:{'path':str(Path(path).relative_to(ROOT)),'sha256':sha(path)}


def main():
    name=sys.argv[1]
    if name not in ['round1','round2']:raise ValueError('Only two declared attempts')
    directory=HERE/name;target=directory/'plan.json'
    if target.exists() or (directory/'launch-receipt.json').exists():raise ValueError('Never overwrite a frozen/launched setting')
    tests=json.loads((directory/'tests.json').read_text())
    if tests['status']!='passed' or tests['test_methods']<1:raise ValueError('Synthetic tests required')
    for relative,digest in tests['source_sha256'].items():
        if sha(ROOT/relative)!=digest:raise ValueError('Tested source changed')
    prerequisites=HERE/'premeasurement-prerequisites.json';pr=json.loads(prerequisites.read_text())
    for key in ['cycle_policy','independent_contract','independent97_proof']:
        record=pr[key]
        if sha(ROOT/record['path'])!=record['sha256']:raise ValueError('New cycle3 prerequisite changed')
    if pr['cycle_policy']['sha256']!='9e0ca0a1cb88737f28960ffb8954c14589d1dbf334eaac3d6ab42354c6d57568':raise ValueError('Root policy pin')
    if pr['independent_contract']['sha256']!='36a7b4a181cde16122a3e9ae6708bb48fa83f0d16bd264b85285c8e26255fafd':raise ValueError('Audit contract pin')
    if pr['independent97_proof']['sha256']!='1abfdfd68358d50ce22160466b2974e1081c0595ac03ac090fc2d25a71dfce2c':raise ValueError('Independent97 pin')
    baseline=json.loads((HERE/'baseline97-freeze.json').read_text())
    for relative,digest in baseline['immutable_source_sha256'].items():
        if sha(ROOT/relative)!=digest:raise ValueError('Baseline97 source changed')
    base=ROOT/'experiments/swarm/jevbench-adapter';old=HERE.parent/'cycle2'
    sources=[HERE/file for file in ['run.py','engine.py','freeze_round.py','supervise.py','save_attempt.py','test_engine.py','verify.py']]
    sources.extend([directory/file for file in ['rules.py','probability.py','test_probability.py']])
    sources.extend([old/'round2/rules.py',old/'round2/typed_numeric.py',old/'frozen-baseline/rules.py'])
    sources.extend([base/'server.py',base/'native-worker.cjs',ROOT/'experiments/optimization/baseline-server.cjs'])
    sources.extend(base/'sources'/file for file in ['jevbench_tasks.py','jevbench_scoring.py','jevbench_adapters_base.py','jevbench_adapters_typesafe.py'])
    if name=='round2':
        first=json.loads((HERE/'round1/plan.json').read_text())
        for relative in first['source_sha256']:
            path=ROOT/relative
            if path not in sources:sources.append(path)
    plan=json.loads((base/'public-development/plan.json').read_text())
    plan.update(cycle=3,round=int(name[-1]),frozen_at=datetime.now(timezone.utc).isoformat(),
        scope='Cycle3 public183 observed DEVELOPMENT; immutable97 fallback plus exact explicit probability operations. No fresh/Capability/sealed1200/official rank claim.',
        cycle_policy=pr['cycle_policy'],independent_contract=pr['independent_contract'],independent97_proof=pr['independent97_proof'],
        premeasurement_prerequisites=role(prerequisites),baseline97=role(HERE/'baseline97-freeze.json'),science=role(HERE/'hypotheses.json'),tests=role(directory/'tests.json'),
        source_sha256={str(path.relative_to(ROOT)):sha(path) for path in sources},
        resources={'max_wall_seconds':600,'CPU_affinity_max':2,'new_paid_calls':0,'external_network_calls':0,'downloads':0},
        improvement_gate={'n':183,'correct_strictly_above':97,'hard_correct_strictly_above':41,'original_correct_at_least':56,'errors':0,'strict_valid':183},candidate_quality_calls_before_freeze=0)
    target.write_text(json.dumps(plan,indent=2)+'\n')
    manifest={'schema_version':1,'frozen_at':plan['frozen_at'],'premeasurement_plan':role(target),'source_sha256':plan['source_sha256'],'test_receipt':role(directory/'tests.json'),
        'cycle_policy':pr['cycle_policy'],'independent_contract':pr['independent_contract'],'independent97_proof':pr['independent97_proof'],'new_paid_calls':0,'quality_calls_before_freeze':0}
    (directory/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'plan':role(target),'source_manifest':role(directory/'source-manifest.json'),'sources':len(sources),'test_methods':tests['test_methods']},indent=2))


if __name__=='__main__':main()
