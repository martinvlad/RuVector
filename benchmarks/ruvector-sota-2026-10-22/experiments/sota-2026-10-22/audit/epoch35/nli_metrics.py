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
            and r['model_weights_sha256']=='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b',
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

def engineering_gates(results):
    candidate=results['native']
    checks={'native_all12_correct':candidate['correct']==12,
            'authored_class_balance4each':all(candidate['by_class'][c]['n']==4 for c in CLASSES),
            'native_all4_per_class_correct':all(candidate['by_class'][c]['correct']==4 for c in CLASSES)}
    for name in ['native_original','lexical','positional']:
        other=results[name]
        checks[name+':Brier_nonincrease']=candidate['Brier']<=other['Brier']+1e-12
        checks[name+':NLL_nonincrease']=candidate['NLL_clipped_1e-12']<=other['NLL_clipped_1e-12']+1e-12
    return checks

def paired_differences(results):
    candidate=results['native'];answer={}
    for name in ['native_original','lexical','positional']:
        other=results[name];rows=[]
        for a,b in zip(candidate['scores'],other['scores']):
            require(a['id']==b['id']and a['document_id']==b['document_id']and a['gold']==b['gold'],'Unmatched same-model engineering comparison')
            rows.append({'id':a['id'],'document_id':a['document_id'],'native_minus_correct':a['correct']-b['correct'],'native_minus_Brier':a['Brier']-b['Brier'],'native_minus_NLL':a['NLL_clipped_1e-12']-b['NLL_clipped_1e-12']})
        require(len(rows)==12 and len({r['document_id']for r in rows})==12,'Twelve distinct authored source clusters required')
        answer[name]={'native_minus_correct':candidate['correct']-other['correct'],
            'native_minus_accuracy':candidate['accuracy']-other['accuracy'],
            'native_minus_Brier':candidate['Brier']-other['Brier'],
            'native_minus_NLL':candidate['NLL_clipped_1e-12']-other['NLL_clipped_1e-12'],
            'authored_case_differences':rows,'authored_source_clusters':12,
            'uncertainty':'Twelve source-authored CC0 engineering challenges, intentionally structured and class-balanced; descriptive paired ablation, not benchmark or population generalization.'}
    return answer
