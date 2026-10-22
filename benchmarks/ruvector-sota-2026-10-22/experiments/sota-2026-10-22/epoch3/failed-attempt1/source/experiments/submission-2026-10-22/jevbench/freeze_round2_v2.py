"""Freeze one finite submission-development attempt after unseen tests."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
role=lambda p:{'path':str(Path(p).relative_to(ROOT)),'sha256':sha(p)}
POLICY='065da03cfc424c7f02a62e81352084ef4c279c13f23a146322f24bacd7027566'
CONTRACT='0409425579256d790fd1389e1a038b17e73cc839b22cb1f2822453fcda6e81fd'

def main():
 name=sys.argv[1]
 if name not in ['round1','round2-v2']:raise ValueError('Exactly two attempts')
 d=HERE/name;p=d/'plan.json'
 if p.exists() or (d/'launch-receipt.json').exists():raise ValueError('Immutable frozen attempt')
 tests=json.loads((d/'tests.json').read_text());assert tests['status']=='passed' and tests['test_methods']>=46
 for rel,h in tests['source_sha256'].items():assert sha(ROOT/rel)==h,rel
 policy=HERE.parent/'policy.json';contract=HERE.parent/'audit/acceptance-contract-v1.json'
 assert sha(policy)==POLICY and sha(contract)==CONTRACT
 baseline=ROOT/'experiments/compounding/jevbench/cycle3/round2/plan.json'
 old=json.loads(baseline.read_text())
 sources={rel:h for rel,h in old['source_sha256'].items()}
 for rel,h in sources.items():assert sha(ROOT/rel)==h,rel
 active=[HERE/f for f in ['engine.py','run_round2_v2.py','supervise_round2_v2.py','save_attempt.py','verify_round2_v2.py','test_engine.py','freeze_round2_v2.py','emit_round2_v2.py']]+[d/f for f in ['rules.py','typed_relations.py','test_relations.py']]
 if name=='round2-v2':active.extend(HERE/'round1'/f for f in ['rules.py','typed_relations.py','test_relations.py'])
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in active})
 template=json.loads((ROOT/'experiments/swarm/jevbench-adapter/public-development/plan.json').read_text())
 template.update(cycle=4,round=int(name[-1]),frozen_at=datetime.now(timezone.utc).isoformat(),scope='Submission-development public183 observed adaptive DEV; exact100 fallback plus finite source-linked typed joins. No official rank/Capability/sealed claim.',cycle_policy=role(policy),independent_contract=role(contract),independent100_proof=role(ROOT/'experiments/compounding/audit/jevbench-cycle3-round2-independent-verification.json'),baseline100=role(ROOT/'experiments/compounding/jevbench/cycle3/round2/integration-result.json'),tests=role(d/'tests.json'),source_sha256=sources,resources={'max_wall_seconds':600,'CPU_affinity_max':2,'new_paid_calls':0,'external_network_calls':0,'downloads':0},improvement_gate={'n':183,'correct_strictly_above':100,'hard_correct_strictly_above':44,'original_correct_at_least':56,'errors':0,'strict_valid':183,'no_lost_correct_cases':True},candidate_quality_calls_before_freeze=0)
 p.write_text(json.dumps(template,indent=2)+'\n')
 manifest={'schema_version':1,'frozen_at':template['frozen_at'],'premeasurement_plan':role(p),'source_sha256':sources,'test_receipt':role(d/'tests.json'),'cycle_policy':role(policy),'independent_contract':role(contract),'baseline100':template['baseline100'],'quality_calls_before_freeze':0,'new_paid_calls':0}
 m=d/'source-manifest.json';m.write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'plan':role(p),'source_manifest':role(m),'source_count':len(sources),'tests':tests['test_methods']}))
if __name__=='__main__':main()
