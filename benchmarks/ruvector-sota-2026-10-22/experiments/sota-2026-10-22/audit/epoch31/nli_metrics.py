"""Independent native three-way NLI numerical replay; no model or label I/O."""
import hashlib
import math
import re
from data_common import require, finite, CLASSES, NATIVE_ORDER

NATIVE_TYPED = ['Contradiction','NotMentioned','Entailment']
CANONICAL_TYPED = ['Entailment','Contradiction','NotMentioned']
EPS = 1e-6
FLOOR = 1e-12

def reader_check(r,premise,hypothesis,pair_tokens,state=None,artifact_sha=None,
                 original_head_sha=None,trainable_manifest_sha=None):
    require(type(r)is dict,'Missing genuine reader result')
    logits=r['raw_logits_C_N_E'];p=r['probabilities_E_C_N']
    require(type(logits)is list and len(logits)==3 and all(finite(v)for v in logits),
            'Exactly3finite native C,N,E logits required')
    require(r['actual_logits_shape']==[1,3],'Stock three-way output shape changed')
    require(type(p)is list and len(p)==3 and all(finite(v)and 0<=v<=1 for v in p),
            'Complete three-way probability vector required')
    shifted=[math.exp(v-max(logits))for v in logits];mass=math.fsum(shifted)
    raw=[v/mass for v in shifted];replayed=[raw[2],raw[0],raw[1]]
    require(abs(math.fsum(p)-1)<=EPS and all(abs(x-y)<=EPS for x,y in zip(p,replayed)),
            'Native unit-temperature full softmax replay failed')
    winner=max(range(3),key=lambda i:logits[i])
    require(r['typed_prediction']==NATIVE_TYPED[winner],'Native C,N,E argmax/tie rule changed')
    require(abs(r['binary_yes_probability']-p[0])<=EPS
            and abs(r['binary_no_probability']-(p[1]+p[2]))<=EPS
            and r['binary_prediction']==('Yes'if p[0]>0.5 else'No'),
            'Fixed binary forecast/tie mapping changed')
    require(type(pair_tokens)is int and 0<pair_tokens<=512
            and r['pair_tokens']==r['full_pair_tokens']==pair_tokens and r['max_pair_tokens']==512,
            'True native pair length/cap mismatch')
    require(r['premise_truncated']is False and r['hypothesis_truncated']is False,
            'Hidden native pair truncation')
    require(r['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest()
            and r['hypothesis_sha256']==hashlib.sha256(hypothesis.encode()).hexdigest(),
            'Reader premise/hypothesis literal mismatch')
    require(type(r['native_pair_input_ids_sha256'])is str
            and re.fullmatch('[0-9a-f]{64}',r['native_pair_input_ids_sha256']),
            'Missing true native pair ID receipt')
    if state is not None:
        receipt=r['state_receipt'];require(receipt['state']==state,'Wrong original/adapted reader state')
        if state=='original':
            require(receipt['LoRA_injected']is False and receipt['learned_parameters_loaded']is False
                    and receipt['head_manifest_sha256']==original_head_sha,
                    'Original native baseline did not use original classifier with no learned state')
        else:
            require(receipt['LoRA_enabled']is True and receipt['LoRA_scale']==2.0
                    and receipt['parameter_artifact_sha256']==artifact_sha
                    and receipt['trainable_manifest_sha256']==trainable_manifest_sha,
                    'Adapted LoRA/head state differs from frozen MODEL artifact')
        require(finite(r['latency_seconds'])and r['latency_seconds']>=0,'Invalid reader timing')
    return {'probabilities':dict(zip(CLASSES,p)),
            'prediction':NATIVE_ORDER[winner],
            'binary_yes_probability':p[0],
            'binary_prediction':r['binary_prediction']}

def metrics(rows,reader):
    counts={c:{'n':0,'correct':0}for c in CLASSES}
    confusion={c:{p:0 for p in CLASSES}for c in CLASSES}
    scores=[]
    for row in rows:
        gold=row['gold'];require(gold in CLASSES,'Unknown canonical source gold')
        r=row['readers'][reader];p=r['probabilities'];pred=r['prediction']
        pg=p[gold];brier=math.fsum((p[c]-int(c==gold))**2 for c in CLASSES)
        correct=int(pred==gold);counts[gold]['n']+=1;counts[gold]['correct']+=correct;confusion[gold][pred]+=1
        scores.append({'id':row['id'],'document_id':row['document_id'],'gold':gold,'prediction':pred,
                       'correct':correct,'Brier':brier,'NLL_clipped_1e-12':-math.log(max(pg,FLOOR)),
                       'NLL_clipped':pg<FLOOR,'unclipped_NLL_finite':pg>0,
                       'probabilities':p})
    n=len(scores);require(n==24,'Fixed24DEV cases required')
    return {'n':n,'correct':sum(r['correct']for r in scores),'accuracy':sum(r['correct']for r in scores)/n,
            'Brier':math.fsum(r['Brier']for r in scores)/n,
            'NLL_clipped_1e-12':math.fsum(r['NLL_clipped_1e-12']for r in scores)/n,
            'NLL_clip_count':sum(r['NLL_clipped']for r in scores),
            'unclipped_NLL_finite':all(r['unclipped_NLL_finite']for r in scores),
            'by_class':counts,'confusion':confusion,
            'scores':scores}

def diagnostic_gates(results):
    candidate=results['adapted_native'];original=results['original_native']
    checks={'every_gold_class_present':all(candidate['by_class'][c]['n']>0 for c in CLASSES),
            'adapted_native_one_correct_per_class':all(candidate['by_class'][c]['correct']>0 for c in CLASSES),
            'adaptation_correct_gain_at_least2':candidate['correct']>=original['correct']+2,
            'adaptation_C_correct_gain_at_least1':candidate['by_class']['contradiction']['correct']>=original['by_class']['contradiction']['correct']+1}
    for name in ['original_native','adapted_lexical','adapted_positional']:
        other=results[name]
        checks[name+':Brier_nonincrease']=candidate['Brier']<=other['Brier']+1e-12
        checks[name+':NLL_nonincrease']=candidate['NLL_clipped_1e-12']<=other['NLL_clipped_1e-12']+1e-12
        if name!='original_native':checks[name+':correct_gain_at_least2']=candidate['correct']>=other['correct']+2
    return checks
