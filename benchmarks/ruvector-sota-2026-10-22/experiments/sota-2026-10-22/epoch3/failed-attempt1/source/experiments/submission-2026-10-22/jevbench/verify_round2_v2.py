"""Evaluation-only reconstruction of actual HTTP, official scores and pairs.

This module is never imported by the prediction runtime. It can read public
expected labels solely to score already-preserved responses.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
ADAPTER=ROOT/'experiments/swarm/jevbench-adapter'
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
read=lambda path:json.loads(Path(path).read_text())

def modules():
    pkg=ModuleType('verified_jevbench');pkg.__path__=[];sys.modules[pkg.__name__]=pkg
    sub=ModuleType(pkg.__name__+'.adapters');sub.__path__=[];sys.modules[sub.__name__]=sub
    loaded={}
    for name in ['tasks','scoring','adapters.base','adapters.typesafe']:
        fullname=pkg.__name__+'.'+name;path=ADAPTER/'sources'/('jevbench_'+name.replace('.','_')+'.py')
        spec=importlib.util.spec_from_file_location(fullname,path);module=importlib.util.module_from_spec(spec);sys.modules[fullname]=module;spec.loader.exec_module(module);loaded[name]=module
    return loaded

def probs(answer,kind):
    if kind=='noul':return {'yes':answer['noul'],'no':1-answer['noul']}
    return answer['probabilities']

def paired(before,after):
    counts=Counter()
    for a,b in zip(before,after):
        assert a['id']==b['id']
        old=a['official_score']['correct'];new=b['official_score']['correct']
        counts['gained' if new and not old else 'regressed' if old and not new else 'both_correct' if new else 'both_wrong']+=1
    gained,regressed=counts['gained'],counts['regressed'];discordant=gained+regressed
    p=min(1,2*sum(math.comb(discordant,k) for k in range(min(gained,regressed)+1))/2**discordant) if discordant else 1
    return {**{key:counts[key] for key in ['gained','regressed','both_correct','both_wrong']},'n':len(before),
        'accuracy_gain_pp':100*(gained-regressed)/len(before),'descriptive_exact_discordant_binomial_two_sided_p':p,
        'caution':'Observed development; original paraphrases and shared scenarios are correlated, selection used these public outcomes. This diagnostic is not fresh significance.'}

def verify_round(name,loaded,reference,native_reference):
    directory=HERE/name;plan=read(directory/'plan.json');results=read(directory/'results.json')
    spec=importlib.util.spec_from_file_location('verified_submission_rules_'+name,directory/'rules.py');rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
    spec=importlib.util.spec_from_file_location('verified_submission_engine',HERE/'engine.py');engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    for rel,digest in plan['source_sha256'].items():assert sha(ROOT/rel)==digest,rel
    assert results['plan_sha256']==sha(directory/'plan.json')
    rows=[json.loads(line) for line in (directory/'decisions.jsonl').read_text().splitlines()]
    records=read(directory/'tasks.json');assert len(rows)==len(records)==183
    assert [r['id'] for r in rows]==[r['id'] for r in reference]
    native=results['native_receipt'];assert native['backend']=='native' and native['binary_sha256']==plan['native_candidate']['binary_sha256']
    assert native['generic_rules_sha256']==sha(directory/'rules.py')
    assert len(results['cpu_affinity'])==2 and results['elapsed_seconds']<600
    cold=read(directory/'cold.json')['first_http_request'];wire=[];rule_counts=Counter();native_correct=0;overrides=0
    for row,record in [(cold,records[0]),*zip(rows,records)]:
        task=loaded['tasks'].Task.from_dict(record['task'])
        request=(directory/row['request_file']).read_bytes();response=(directory/row['response_file']).read_bytes()
        assert hashlib.sha256(request).hexdigest()==row['request_sha256'] and hashlib.sha256(response).hexdigest()==row['response_sha256']
        headers,body=request.split(b'\r\n\r\n',1);rh,rb=response.split(b'\r\n\r\n',1)
        assert headers.startswith(b'POST /v1/systemone HTTP/') and rh.startswith(b'HTTP/1.0 200')
        decoded=json.loads(body);assert set(decoded)=={'state','model','questions'}
        adapter=loaded['adapters.typesafe'].TypeSafeAdapter(model=decoded['model'],key_env='')
        assert decoded==adapter.build_request(task)
        assert json.loads(rb)==row['raw_response']
        answer=row['raw_response']['answers']['decision'];score=loaded['scoring'].score_task(probs(answer,task.question['type']),task)
        assert score==row['official_score'] and row['ok'] and score['strict_valid'] and not score['renormalized']
        state,questions=engine.server.validate_request(decoded);question=questions['decision'];pure=rules.solve(state,question);baseline_proof=rules.baseline_proof(state,question)
        original=answer['native_original_answer'];base=engine.apply_proof(original,question,baseline_proof);expected=engine.apply_proof(original,question,pure);expected.update(native_original_answer=original,baseline100_answer=base,native_fallback_used=pure is None)
        assert expected==answer,('pure normalized proof/response mismatch',row['id'])
        baseline_score=loaded['scoring'].score_task(probs(answer['baseline100_answer'],task.question['type']),task)
        native_score=loaded['scoring'].score_task(probs(original,task.question['type']),task)
        if not row['warmup']:
            index=len(wire)-1;assert native_score==native_reference[index]['official_score'],('native77 changed',index)
            assert baseline_score==reference[index]['official_score'],('frozen100 changed',index)
            native_correct+=native_score['correct']
            if 'symbolic_proof' in answer:
                proof=answer['symbolic_proof'];rule_counts[(proof['rule'],score['correct'])]+=1;overrides+=1
                assert answer['native_fallback_used'] is False
            else:assert answer['native_fallback_used'] is True and score==native_score and score==baseline_score
        wire.append({'task_id':row['id'],'warmup':row['warmup'],'request':{'path':str((directory/row['request_file']).relative_to(ROOT)),'sha256':row['request_sha256'],'bytes':len(request)},'response':{'path':str((directory/row['response_file']).relative_to(ROOT)),'sha256':row['response_sha256'],'bytes':len(response)}})
    assert native_correct==77 and len(wire)==184
    families={}
    for record,row in zip(records,rows):
        key=record['cohort']+'/'+record['task']['family'];families.setdefault(key,[]).append(row)
    per_family={key:{'n':len(seq),'correct':sum(x['official_score']['correct'] for x in seq),'accuracy':sum(x['official_score']['correct'] for x in seq)/len(seq)} for key,seq in families.items()}
    for cohort in ['original','hard','all']:
        selected=[r for r in rows if cohort=='all' or r['cohort']==cohort];correct=sum(r['official_score']['correct'] for r in selected)
        assert results['metrics'][cohort]['n']==len(selected) and results['metrics'][cohort]['correct']==correct
        assert results['metrics'][cohort]['errors']==0 and results['metrics'][cohort]['strict_valid']==len(selected)
    wire_path=directory/'wire-index.json';wire_path.write_text(json.dumps(wire,indent=2)+'\n')
    comparison=paired(reference,rows);comparison['by_cohort']={cohort:paired([r for r in reference if r['cohort']==cohort],[r for r in rows if r['cohort']==cohort]) for cohort in ['original','hard']}
    comparison['per_family']=per_family;(directory/'paired.json').write_text(json.dumps(comparison,indent=2)+'\n')
    proof={'status':'passed','verified_at':datetime.now(timezone.utc).isoformat(),'scope':'Observed development only','round':name,'complete_n':183,'literal_HTTP_pairs':184,'official_route':'/v1/systemone','direct_official_score_calls':552,'candidate_native77_baseline100_calls_each':184,'all_strict_valid':True,'errors':0,'unchanged_actual_native_baseline_correct':native_correct,'native_binary_sha256':native['binary_sha256'],'native_model_manifest_sha256':native['model_manifest_sha256'],'source_frozen_before_measurement':True,'plan_sha256':sha(directory/'plan.json'),'results_sha256':sha(directory/'results.json'),'decisions_sha256':sha(directory/'decisions.jsonl'),'wire_index_sha256':sha(wire_path),'symbolic_overrides':overrides,'symbolic_rule_counts':[{'rule':key[0],'correct':key[1],'n':value} for key,value in sorted(rule_counts.items())],'paired':comparison,'gate_passed':results['metrics']['all']['correct']>100 and results['metrics']['hard']['correct']>44 and results['metrics']['original']['correct']>=56,'baseline100_scores_exact_all183':True,'pure_proofs_and_answer_construction_replayed_all184':True,'new_paid_calls':0,'official_rank':None,'Capability':None,'goal_met':False}
    (directory/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');return proof,rows

def main():
    loaded=modules();native_reference=[json.loads(line) for line in (ADAPTER/'public-development/decisions.jsonl').read_text().splitlines()];reference=[json.loads(line) for line in (ROOT/'experiments/compounding/jevbench/cycle3/round2/decisions.jsonl').read_text().splitlines()];proofs={};rows={}
    for name in ['round1','round2-v2']:
        directory=HERE/name
        if (directory/'verification.json').exists():
            proof=read(directory/'verification.json')
            for filename,key in [('plan.json','plan_sha256'),('results.json','results_sha256'),('decisions.jsonl','decisions_sha256'),('wire-index.json','wire_index_sha256')]:
                assert sha(directory/filename)==proof[key],('preserved prior proof identity changed',name,filename)
            proofs[name]=proof;rows[name]=[json.loads(line) for line in (directory/'decisions.jsonl').read_text().splitlines()]
        elif (directory/'results.json').exists():proofs[name],rows[name]=verify_round(name,loaded,reference,native_reference)
    if len(rows)==2:
        (HERE/'round2-vs-round1.json').write_text(json.dumps(paired(rows['round1'],rows['round2']),indent=2)+'\n')
    print(json.dumps({name:{'correct':sum(row['official_score']['correct'] for row in rows[name]),'gate':proof['gate_passed'],'native_reference_correct':proof['unchanged_actual_native_baseline_correct'],'wire_pairs':proof['literal_HTTP_pairs']} for name,proof in proofs.items()},indent=2))

if __name__=='__main__':main()
