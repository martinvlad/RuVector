"""Independent native three-way NLI numerical replay; no model or label I/O."""
import hashlib
import math
import re
from data_common import require, finite, CLASSES, NATIVE_ORDER

NATIVE_TYPED = ['Entailment','NotMentioned','Contradiction']
CANONICAL_TYPED = ['Entailment','Contradiction','NotMentioned']
EPS = 1e-6
FLOOR = 1e-12

def reader_check(r,premise,hypothesis,pair_tokens):
    require(type(r)is dict,'Missing genuine reader result')
    logits=r['raw_logits_E_N_C'];p=r['probabilities_E_C_N']
    require(type(logits)is list and len(logits)==3 and all(finite(v)for v in logits),
            'Exactly3finite native E,N,C logits required')
    require(r['actual_logits_shape']==[1,3],'Stock three-way output shape changed')
    require(type(p)is list and len(p)==3 and all(finite(v)and 0<=v<=1 for v in p),
            'Complete three-way probability vector required')
    shifted=[math.exp(v-max(logits))for v in logits];mass=math.fsum(shifted)
    raw=[v/mass for v in shifted];replayed=[raw[0],raw[2],raw[1]]
    require(abs(math.fsum(p)-1)<=EPS and all(abs(x-y)<=EPS for x,y in zip(p,replayed)),
            'Native unit-temperature full softmax replay failed')
    original=r['probabilities_E_N_C']
    require(type(original)is list and len(original)==3 and all(finite(v)for v in original)
            and all(abs(x-y)<=EPS for x,y in zip(original,raw)), 'Original full E,N,C probabilities changed')
    require(finite(r['temperature'])and r['temperature']==1 and r['calibrated']is False
            and r['semantic_decision_override']is False
            and r['model_weights_sha256']=='534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc',
            'Fixed original uncalibrated T1 readout/head changed')
    winner=max(range(3),key=lambda i:logits[i])
    require(type(r['native_label_index'])is int and r['native_label_index']==winner
            and r['native_typed_argmax']==NATIVE_TYPED[winner],'Native E,N,C argmax/tie rule changed')
    binary=r['native_binary_probabilities_Yes_No']
    require(set(binary)=={'Yes','No'} and all(finite(v)for v in binary.values())
            and abs(binary['Yes']-p[0])<=EPS and abs(binary['No']-(p[1]+p[2]))<=EPS
            and r['native_binary_decision']==('Yes'if p[0]>0.5 else'No'),
            'Fixed binary forecast/tie mapping changed')
    require(type(pair_tokens)is int and 0<pair_tokens<=512
            and r['pair_tokens']==r['full_pair_tokens']==pair_tokens and r['max_pair_tokens']==512,
            'True native pair length/cap mismatch')
    require(r['hidden_truncation']is False,'Hidden native pair truncation')
    require(r['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest()
            and r['hypothesis_sha256']==hashlib.sha256(hypothesis.encode()).hexdigest(),
            'Reader premise/hypothesis literal mismatch')
    require(type(r['native_pair_input_ids_sha256'])is str
            and re.fullmatch('[0-9a-f]{64}',r['native_pair_input_ids_sha256']),
            'Missing true native pair ID receipt')
    require(all(finite(r[k])and r[k]>=0 for k in ['forward_seconds','reader_seconds'])
            and r['reader_seconds']+1e-9>=r['forward_seconds'],'Invalid reader/forward timing')
    return {'probabilities':dict(zip(CLASSES,p)),
            'prediction':NATIVE_ORDER[winner],
            'binary_yes_probability':p[0],
            'binary_prediction':r['native_binary_decision']}

def metrics(rows,reader,expected_n=24):
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
    n=len(scores);require(n==expected_n,'Fixed case count required')
    return {'n':n,'correct':sum(r['correct']for r in scores),'accuracy':sum(r['correct']for r in scores)/n,
            'Brier':math.fsum(r['Brier']for r in scores)/n,
            'NLL_clipped_1e-12':math.fsum(r['NLL_clipped_1e-12']for r in scores)/n,
            'NLL_clip_count':sum(r['NLL_clipped']for r in scores),
            'unclipped_NLL_finite':all(r['unclipped_NLL_finite']for r in scores),
            'by_class':counts,'confusion':confusion,
            'scores':scores}

def diagnostic_gates(results):
    candidate=results['native']
    checks={'every_gold_class_present':all(candidate['by_class'][c]['n']>0 for c in CLASSES),
            'native_one_correct_per_class':all(candidate['by_class'][c]['correct']>0 for c in CLASSES)}
    for name in ['lexical','positional']:
        other=results[name]
        checks[name+':Brier_nonincrease']=candidate['Brier']<=other['Brier']+1e-12
        checks[name+':NLL_nonincrease']=candidate['NLL_clipped_1e-12']<=other['NLL_clipped_1e-12']+1e-12
        checks[name+':correct_gain_at_least2']=candidate['correct']>=other['correct']+2
    return checks

def paired_differences(results):
    candidate=results['native'];answer={}
    for name in ['lexical','positional']:
        other=results[name];groups={}
        for a,b in zip(candidate['scores'],other['scores']):
            require(a['id']==b['id'] and a['document_id']==b['document_id'] and a['gold']==b['gold'],'Unmatched case comparison')
            g=groups.setdefault(a['document_id'],{'document_id':a['document_id'],'n':0,'native_minus_correct':0,'native_minus_Brier_sum':0.0,'native_minus_NLL_sum':0.0})
            g['n']+=1;g['native_minus_correct']+=a['correct']-b['correct'];g['native_minus_Brier_sum']+=a['Brier']-b['Brier'];g['native_minus_NLL_sum']+=a['NLL_clipped_1e-12']-b['NLL_clipped_1e-12']
        require(len(groups)==8 and all(g['n']==3 for g in groups.values()),'Eight matched three-case document groups required')
        answer[name]={'native_minus_correct':candidate['correct']-other['correct'],
            'native_minus_accuracy':candidate['accuracy']-other['accuracy'],
            'native_minus_Brier':candidate['Brier']-other['Brier'],
            'native_minus_NLL':candidate['NLL_clipped_1e-12']-other['NLL_clipped_1e-12'],
            'document_clusters':list(groups.values()),'n_document_clusters':8,
            'document_correct_delta_positive':sum(g['native_minus_correct']>0 for g in groups.values()),
            'document_correct_delta_zero':sum(g['native_minus_correct']==0 for g in groups.values()),
            'document_correct_delta_negative':sum(g['native_minus_correct']<0 for g in groups.values()),
            'uncertainty':'Descriptive paired differences across8correlated document groups; no24-independent-case or population-superiority confidence claim.'}
    return answer
