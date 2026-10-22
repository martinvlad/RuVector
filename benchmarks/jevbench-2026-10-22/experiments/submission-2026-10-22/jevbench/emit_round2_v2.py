"""Evaluation-only normalized result emission; never imported by inference."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
role=lambda path:{'path':str(Path(path).relative_to(ROOT)),'sha256':sha(path)}


def main():
    name=sys.argv[1];directory=HERE/name;number=int(name[-1]);target=directory/'integration-result.json'
    if name not in ['round1','round2-v2'] or target.exists():raise ValueError('Never overwrite result or extend finite cycle')
    result=read(directory/'results.json');proof=read(directory/'verification.json');terminal=read(directory/'supervisor-terminal.json');plan=read(directory/'plan.json')
    metrics=result['metrics'];all_=metrics['all'];original=metrics['original'];hard=metrics['hard']
    assert proof['status']=='passed' and terminal['status']=='completed' and all(terminal['processes_absent'].values())
    assert all_['n']==all_['strict_valid']==183 and all_['errors']==0
    gate=all_['correct']>100 and hard['correct']>44 and original['correct']>=56
    gateproof={'schema_version':1,'cycle':4,'round':number,'status':'passed','n':183,'correct':all_['correct'],
        'original_correct':original['correct'],'hard_correct':hard['correct'],'strict_valid':all_['strict_valid'],'errors':0,
        'development_joint_gate_passed':gate,'actual_HTTP_native_reference_replay':role(directory/'verification.json'),
        'result':role(directory/'results.json'),'scope':'observed_development','official_rank':None,'Capability':None,'new_paid_calls':0}
    (directory/'quality-gate.json').write_text(json.dumps(gateproof,indent=2)+'\n')
    lesson='Exact current record joins, grade/section footnotes, effective-dated team aliases and qualified bypass arithmetic preserve source-linked operation proofs. Unsupported inputs retain immutable100.' if number==1 else 'A separately frozen exact arithmetic correction was measured after preserving round1; all attempted settings and paired changes are retained.'
    journal={'cycle':4,'round':number,'scope':'observed_development','claim':lesson,'measured_correct':all_['correct'],'baseline100_correct':100,
        'paired':read(directory/'paired.json'),'evidence_paths':[str((directory/file).relative_to(ROOT)) for file in ['tests.json','verification.json','quality-gate.json','paired.json','execution-preservation.json']],
        'attribution':'Actual native RuVector BGE-small executes every request. Gains come from supported exact mathematical validators in the integrated pipeline, not demonstrated vector-index-only reasoning.',
        'generalization':'No untouched confirmation or publisher sealed evaluation; all183 are adaptive observed development.'}
    (directory/'learner-journal.json').write_text(json.dumps(journal,indent=2)+'\n')
    integration={'schema_version':1,'cycle':4,'track':'jevbench','round':number,'status':'completed','scope':'observed_development',
        'plan':role(directory/'plan.json'),'source_manifest':role(directory/'source-manifest.json'),'results':role(directory/'results.json'),
        'selection':role(directory/'rules.py'),'algorithm_source':role(directory/'typed_relations.py'),
        'selected_candidate':{'id':'ruvector-native-submission-'+name,'n':183,'correct':all_['correct'],'accuracy':all_['accuracy'],'errors':0,
            'original_correct':original['correct'],'hard_correct':hard['correct'],'strict_valid':183},
        'attempt_count':number,'attempt_count_scope':'Cumulative within separately bounded submission; max2 measured attempts',
        'lessons':[{'claim':lesson,'evidence_paths':journal['evidence_paths'],'scope':'observed_development'}],
        'learner_journal':role(directory/'learner-journal.json'),
        'next_proposal':{'status':'optional_unexecuted_final_round' if number==1 else 'unexecuted_after_finite_cycle_exhausted',
            'proposal':'One supported current-field classification/retention exception extension, separately frozen with unseen entities and counterfactuals before final measurement.' if number==1 else 'A distinct future cycle could study generic source-linked provenance joins; no extension of the exhausted submission bounds.',
            'new_paid_calls':0},'new_paid_calls':0,
        'HTTP_pairs':{**role(directory/'wire-index.json'),'pairs':184},
        'actual_native_proof':{**role(directory/'verification.json'),'backend':'native','binary_sha256':result['native_receipt']['binary_sha256'],
            'all183_native77_and_frozen100_scores_exact':True},
        'quality_gate':role(directory/'quality-gate.json'),'n':183,'correct':all_['correct'],'original_correct':original['correct'],'hard_correct':hard['correct'],'strict_valid':183,'errors':0,
        'paired_comparison':role(directory/'paired.json'),'per_source':{key:metrics[key] for key in ['original','hard']},
        'execution_preservation':role(directory/'execution-preservation.json'),'cleanup':role(directory/'supervisor-terminal.json'),
        'cycle_policy':plan['cycle_policy'],'independent_contract':plan['independent_contract'],'independent100_proof':plan['independent100_proof'],
        'producer_verification_only':True,'independent_audit_status':'Pending at emission; separate independent compact review binds this immutable result',
        'development_joint_gate_passed':gate,'confirmed_or_official_promotion':False,'official_rank':None,'Capability':None,'goal_met':False,'at':datetime.now(timezone.utc).isoformat()}
    if number==2:
        integration['incremental_vs_round1']=role(HERE/'round2-vs-round1.json')
        integration['previous_round_integration']=role(HERE/'round1/integration-result.json')
    target.write_text(json.dumps(integration,indent=2)+'\n')
    print(json.dumps({'integration':role(target),'candidate':integration['selected_candidate'],'joint_development_gate':gate},indent=2))


if __name__=='__main__':main()
